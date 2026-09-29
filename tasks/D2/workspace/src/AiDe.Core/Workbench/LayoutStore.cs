using System.Collections.Immutable;
using System.Text.Json;
using System.Text.Json.Serialization;

namespace AiDe.Core.Workbench;

/// <summary>
/// The owned persistence envelope (ADR-0013). The payload is ours, not the docking library's,
/// because <c>LayoutRootDto</c> ships no version field — without an envelope there is no way to
/// tell "written by an older build" from "corrupt", and both would surface as the same failure.
/// </summary>
public sealed record LayoutEnvelope(
    [property: JsonPropertyName("schemaVersion")] int SchemaVersion,
    [property: JsonPropertyName("appVersion")] string AppVersion,
    [property: JsonPropertyName("savedAt")] DateTimeOffset SavedAt,
    [property: JsonPropertyName("payload")] LayoutDto Payload);

/// <summary>Serializable projection of the layout tree. Deliberately dumb: no behaviour, no invariants.</summary>
public sealed record LayoutDto(NodeDto Root, List<NodeDto> Floating);

public sealed record NodeDto(
    string Id,
    string Kind,                       // "split" | "stack"
    string? Orientation,
    List<NodeDto>? Children,
    List<double>? Weights,
    List<SurfaceDto>? Surfaces,
    int ActiveIndex,
    string? State,
    double? FloatX = null,
    double? FloatY = null,
    double? FloatWidth = null,
    double? FloatHeight = null);

public sealed record SurfaceDto(string SurfaceId, string Kind, string Title);

/// <summary>
/// What the application can currently provide, as the restore's reconciliation asks it.
/// </summary>
/// <remarks>
/// <para><b>Ids alone were wrong.</b> The shell passed the surface ids present in the DEFAULT
/// layout, so anything created at runtime — an agent terminal, whose id is
/// <c>agent:claude#&lt;guid&gt;</c> — was unknown at restore and dropped as "no longer available".
/// The user was told their agent pane was gone, every launch, because the check asked the wrong
/// question.</para>
///
/// <para><b>The right question is whether content can be BUILT for it</b>, which is a property of
/// the surface's kind. Ids are still honoured for the fixed surfaces. A surface whose kind this
/// build no longer has is still dropped and still reported — the control keeps firing for the case
/// it was written for.</para>
/// </remarks>
public sealed record SurfaceAvailability(IReadOnlySet<string> Ids, IReadOnlySet<string> Kinds)
{
    public static SurfaceAvailability OfIds(IReadOnlySet<string> ids) =>
        new(ids, new HashSet<string>(StringComparer.Ordinal));

    public bool CanProvide(Surface surface) =>
        Kinds.Contains(surface.Kind) || Ids.Contains(surface.SurfaceId);
}

/// <summary>What a restore actually managed to do — never a silent success.</summary>
public sealed record RestoreResult(
    Layout Layout,
    bool WasDefaulted,
    string? ErrorCode,
    IReadOnlyList<string> MissingSurfaces,
    IReadOnlyList<string> RehomedFloating,
    string Announcement);

/// <summary>
/// Reads and writes the workbench layout for one workspace.
/// </summary>
/// <remarks>
/// The contract US-9 sets is that a layout which cannot be honoured **degrades to the default
/// arrangement and says so, preserving the original file** — never to a broken window and never to a
/// silently dropped surface.
/// </remarks>
public sealed class LayoutStore(
    string filePath,
    string appVersion = "0.3.0",
    IReadOnlyList<LayoutMigration>? migrations = null)
{
    /// <summary>
    /// Bumped to 2 when the Joins pane was added.
    /// </summary>
    /// <remarks>
    /// The version is what makes a shipped surface reach a user who has already arranged their
    /// workbench. Adding a pane to <see cref="Layout.Default"/> alone reaches only people with no
    /// saved layout, which is nobody who has used the product.
    /// </remarks>
    public const int CurrentSchemaVersion = 4;

    private static readonly JsonSerializerOptions Json = new()
    {
        WriteIndented = true,
        DefaultIgnoreCondition = JsonIgnoreCondition.WhenWritingNull,
    };

    public string BackupPath => filePath + ".bak";

    private IReadOnlyList<LayoutMigration> Migrations => migrations ?? LayoutMigrations.Default;

    public void Save(Layout layout)
    {
        var envelope = new LayoutEnvelope(CurrentSchemaVersion, appVersion, DateTimeOffset.UtcNow,
            new LayoutDto(ToDto(layout.Root), [.. layout.Floating.Select(f => ToDto(f))]));

        var directory = Path.GetDirectoryName(filePath);
        if (!string.IsNullOrEmpty(directory))
        {
            Directory.CreateDirectory(directory);
        }

        File.WriteAllText(filePath, JsonSerializer.Serialize(envelope, Json));
    }

    /// <summary>
    /// Restores the layout, reconciling it against the surfaces that actually exist and the displays
    /// that are actually connected.
    /// </summary>
    /// <param name="availableSurfaces">Surface ids the application can currently provide.</param>
    /// <param name="displayIsConnected">Whether a floating pane's display is still present.</param>
    public RestoreResult Load(
        IReadOnlySet<string> availableSurfaces,
        Func<StackNode, bool>? displayIsConnected = null,
        int? assumedCurrentVersion = null)
        => Load(SurfaceAvailability.OfIds(availableSurfaces), displayIsConnected, assumedCurrentVersion);

    /// <inheritdoc cref="Load(IReadOnlySet{string}, Func{StackNode, bool}, int?)"/>
    public RestoreResult Load(
        SurfaceAvailability availability,
        Func<StackNode, bool>? displayIsConnected = null,
        int? assumedCurrentVersion = null)
    {
        var currentVersion = assumedCurrentVersion ?? CurrentSchemaVersion;
        if (!File.Exists(filePath))
        {
            return new RestoreResult(Layout.Default(), true, null, [], [],
                "Starting from the default workbench layout.");
        }

        LayoutEnvelope? envelope;
        try
        {
            envelope = JsonSerializer.Deserialize<LayoutEnvelope>(File.ReadAllText(filePath), Json);
        }
        catch (JsonException)
        {
            return Degrade(LayoutErrorCodes.Unreadable,
                "Workbench layout could not be read and was reset to the default. " +
                "Your previous layout file was kept.");
        }

        if (envelope is null)
        {
            return Degrade(LayoutErrorCodes.Unreadable,
                "Workbench layout could not be read and was reset to the default. " +
                "Your previous layout file was kept.");
        }

        if (envelope.SchemaVersion > currentVersion)
        {
            // Written by a newer build. Degrading is the honest move: guessing at a format we do not
            // know would produce a plausible-looking but wrong arrangement.
            return Degrade(LayoutErrorCodes.VersionUnsupported,
                $"This workbench layout was written by a newer version (schema {envelope.SchemaVersion}) " +
                "and was reset to the default. Your previous layout file was kept.");
        }

        // Walk the migration chain from the file's version up to the current one. A gap in the
        // chain is a hard stop, not a silent "read it anyway": the shape on disk is one this build
        // cannot interpret, and guessing at it would produce a plausible but wrong arrangement.
        var payload = envelope.Payload;
        var migrated = false;
        for (var version = envelope.SchemaVersion; version < currentVersion; version++)
        {
            var step = Migrations.FirstOrDefault(m => m.FromVersion == version);
            if (step is null)
            {
                return Degrade(LayoutErrorCodes.VersionUnsupported,
                    $"This workbench layout was written at schema {envelope.SchemaVersion} and " +
                    $"could not be upgraded to schema {currentVersion}. It was reset to the default " +
                    "and your previous layout file was kept.");
            }

            payload = step.Apply(payload);
            migrated = true;
        }

        Layout restored;
        try
        {
            restored = new Layout(
                FromDto(payload.Root),
                [.. payload.Floating.Select(f => (StackNode)FromDto(f))],
                ImmutableDictionary<string, StackState>.Empty);
        }
        catch (Exception ex) when (ex is ArgumentException or InvalidCastException or NullReferenceException)
        {
            return Degrade(LayoutErrorCodes.Unreadable,
                "Workbench layout could not be read and was reset to the default. " +
                "Your previous layout file was kept.");
        }

        // Drop surfaces the application can no longer provide, then let the tree heal itself —
        // Detach destroys an emptied stack and collapses the orphaned split.
        var missing = restored.AllStacks()
            .SelectMany(s => s.Surfaces)
            .Where(s => !availability.CanProvide(s))
            .Select(s => s.Title)
            .ToList();

        foreach (var id in restored.AllStacks().SelectMany(s => s.Surfaces)
                     .Where(s => !availability.CanProvide(s))
                     .Select(s => s.SurfaceId).ToList())
        {
            restored = LayoutService.Detach(restored, id) ?? Layout.Default();
        }

        // A floating pane whose display is gone must come back onto a connected one, not stay
        // off-screen where the user cannot reach it.
        var rehomed = new List<string>();
        if (displayIsConnected is not null)
        {
            foreach (var floating in restored.Floating.Where(f => !displayIsConnected(f)).ToList())
            {
                rehomed.Add(floating.Active.Title);
                // Reporting an off-screen pane without moving it would leave the user told about a
                // window they still cannot reach. Clearing the bounds re-homes it to the shell's
                // default placement on a connected display.
                restored = restored with
                {
                    Floating = restored.Floating.Replace(floating, floating with { FloatingBounds = null }),
                };
            }
        }

        try
        {
            restored.AssertInvariant();
        }
        catch (InvalidOperationException)
        {
            return Degrade(LayoutErrorCodes.Unreadable,
                "Workbench layout was not valid and was reset to the default. " +
                "Your previous layout file was kept.");
        }

        // Rewrite once, on read, so an upgraded layout is not re-migrated on every launch.
        if (migrated)
        {
            Save(restored);
        }

        if (missing.Count == 0 && rehomed.Count == 0)
        {
            return new RestoreResult(restored, false, null, [], [],
                migrated ? "Workbench layout upgraded and restored." : "Workbench layout restored.");
        }

        var parts = new List<string>();
        if (missing.Count > 0)
        {
            parts.Add($"{string.Join(", ", missing.Select(m => $"“{m}”"))} " +
                      $"{(missing.Count == 1 ? "is" : "are")} no longer available and " +
                      $"{(missing.Count == 1 ? "was" : "were")} not restored");
        }

        if (rehomed.Count > 0)
        {
            parts.Add($"{string.Join(", ", rehomed.Select(r => $"“{r}”"))} " +
                      $"moved onto this display because the saved display is not connected");
        }

        return new RestoreResult(restored, false, LayoutErrorCodes.PartialRestore, missing, rehomed,
            string.Join(". ", parts) + ".");
    }

    private RestoreResult Degrade(string code, string announcement)
    {
        // The user's file is evidence of their intent. Keep it — overwriting it would destroy the
        // only copy of an arrangement they may have spent real time on.
        try
        {
            File.Copy(filePath, BackupPath, overwrite: true);
        }
        catch (IOException)
        {
            // Preserving the original is best-effort; failing to back it up must not also
            // prevent the user from getting a usable window.
        }

        return new RestoreResult(Layout.Default(), true, code, [], [], announcement);
    }

    internal static NodeDto ToDto(LayoutNode node) => node switch
    {
        SplitNode s => new NodeDto(s.Id, "split", s.Orientation.ToString(),
            [.. s.Children.Select(ToDto)], [.. s.Weights], null, 0, null),
        StackNode s => new NodeDto(s.Id, "stack", null, null, null,
            [.. s.Surfaces.Select(f => new SurfaceDto(f.SurfaceId, f.Kind, f.Title))],
            s.ActiveIndex, s.State.ToString(),
            s.FloatingBounds?.X, s.FloatingBounds?.Y,
            s.FloatingBounds?.Width, s.FloatingBounds?.Height),
        _ => throw new ArgumentException("unknown node", nameof(node)),
    };

    internal static LayoutNode FromDto(NodeDto dto) => dto.Kind switch
    {
        "split" => new SplitNode(dto.Id,
            Enum.Parse<Orientation>(dto.Orientation ?? nameof(Orientation.Horizontal)),
            [.. (dto.Children ?? []).Select(FromDto)],
            [.. dto.Weights ?? []]),
        "stack" => new StackNode(dto.Id,
            [.. (dto.Surfaces ?? []).Select(s => new Surface(s.SurfaceId, s.Kind, s.Title))],
            dto.ActiveIndex,
            Enum.Parse<StackState>(dto.State ?? nameof(StackState.Docked)),
            floatingBounds: dto is { FloatX: { } fx, FloatY: { } fy, FloatWidth: { } fw, FloatHeight: { } fh }
                ? new LayoutRect(fx, fy, fw, fh)
                : null),
        _ => throw new ArgumentException($"unknown node kind '{dto.Kind}'", nameof(dto)),
    };
}
