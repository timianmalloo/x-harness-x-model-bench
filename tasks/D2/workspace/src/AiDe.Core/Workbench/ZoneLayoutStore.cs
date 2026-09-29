using System.Collections.Immutable;
using System.Text.Json;
using System.Text.Json.Serialization;

namespace AiDe.Core.Workbench;

// Persistence DTOs for the zone model. Separate from the tree LayoutStore because zones carry state
// the projected tree cannot (collapsed content, per-zone extent), so saving the projection would be
// lossy. Kept deliberately small; schema v1.
public sealed record ZoneEnvelope(
    [property: JsonPropertyName("schemaVersion")] int SchemaVersion,
    [property: JsonPropertyName("appVersion")] string AppVersion,
    [property: JsonPropertyName("savedUtc")] DateTimeOffset SavedUtc,
    [property: JsonPropertyName("layout")] ZoneLayoutDto Layout);

public sealed record ZoneLayoutDto(
    [property: JsonPropertyName("zones")] List<ZoneStateDto> Zones,
    [property: JsonPropertyName("floating")] List<ZoneStackDto> Floating);

public sealed record ZoneStateDto(
    [property: JsonPropertyName("id")] string Id,
    [property: JsonPropertyName("content")] ZoneContentDto? Content,
    [property: JsonPropertyName("extent")] double Extent,
    [property: JsonPropertyName("collapsed")] bool Collapsed);

public sealed record ZoneContentDto(
    [property: JsonPropertyName("kind")] string Kind, // "stack" | "split"
    [property: JsonPropertyName("tabs")] List<ZoneSurfaceDto>? Tabs,
    [property: JsonPropertyName("activeIndex")] int ActiveIndex,
    [property: JsonPropertyName("orientation")] string? Orientation,
    [property: JsonPropertyName("children")] List<ZoneContentDto>? Children,
    [property: JsonPropertyName("weights")] List<double>? Weights);

public sealed record ZoneStackDto(
    [property: JsonPropertyName("id")] string Id,
    [property: JsonPropertyName("surfaces")] List<ZoneSurfaceDto> Surfaces,
    [property: JsonPropertyName("activeIndex")] int ActiveIndex);

public sealed record ZoneSurfaceDto(
    [property: JsonPropertyName("surfaceId")] string SurfaceId,
    [property: JsonPropertyName("kind")] string Kind,
    [property: JsonPropertyName("title")] string Title);

/// <summary>Why <see cref="ZoneLayoutStore.Read"/> returned no layout (ADR-0032 rule 4). <see cref="None"/> when it returned one.</summary>
public enum ZoneLoadRefusal
{
    None,

    /// <summary>No file at the slot's path — a first run, or a slot never written.</summary>
    NoFile,

    /// <summary>A <c>schemaVersion</c> this build does not read; the file is refused whole, never partially applied.</summary>
    NewerSchema,

    /// <summary>Unreadable JSON, no layout, or an arrangement that breaks the frame invariant (a duplicated surface id).</summary>
    Corrupt,
}

/// <summary>What a read produced: the layout, or null with the reason.</summary>
public sealed record ZoneLoadResult(WorkbenchLayout? Layout, ZoneLoadRefusal Refusal);

/// <summary>
/// Saves and restores a <see cref="WorkbenchLayout"/> of named zones as JSON (ADR-0021 dz-persist),
/// preserving what the projected tree cannot: collapsed-zone content, per-zone extent, and exact
/// placement. Restore filters out surfaces the app can no longer provide, so a saved terminal whose
/// process is gone (or a surface kind the build dropped) does not resurrect — an empty zone simply
/// becomes a placeholder, never a broken pane.
/// </summary>
public sealed class ZoneLayoutStore(string filePath, string appVersion = "0.3.0")
{
    public const int CurrentSchemaVersion = 1;

    private static readonly JsonSerializerOptions Json = new()
    {
        WriteIndented = true,
        DefaultIgnoreCondition = JsonIgnoreCondition.WhenWritingNull,
    };

    public string FilePath => filePath;

    /// <summary>The sibling a save is written to before it replaces the file: <c>&lt;file&gt;.tmp</c>.</summary>
    public string TempPath => filePath + ".tmp";

    /// <summary>
    /// Writes the arrangement — atomically (ADR-0032 rule 3). The envelope is serialised to
    /// <see cref="TempPath"/> and then moved over the destination in one step, so the file the
    /// product reads is never a torn write: a crash before the move leaves the original, and a
    /// stale temp file is overwritten by the next save.
    /// </summary>
    /// <param name="backupPath">
    /// When given and the destination exists, the SAME call that replaces the original preserves
    /// it there (<see cref="File.Replace(string, string, string?)"/>): the pre-perspective bytes,
    /// or a refused file, are kept by the write that would otherwise lose them. A backup that
    /// cannot be created fails the save and leaves the destination untouched — the caller reports
    /// it; the original is never written over on a best-effort promise.
    /// </param>
    public void Save(WorkbenchLayout layout, string? backupPath = null)
    {
        ArgumentNullException.ThrowIfNull(layout);

        var dto = new ZoneLayoutDto(
            [.. Enum.GetValues<ZoneId>().Select(id => ToDto(layout.Zone(id)))],
            [.. layout.Floating.Select(ToStackDto)]);
        var envelope = new ZoneEnvelope(CurrentSchemaVersion, appVersion, DateTimeOffset.UtcNow, dto);

        var directory = Path.GetDirectoryName(filePath);
        if (!string.IsNullOrEmpty(directory))
        {
            Directory.CreateDirectory(directory);
        }

        File.WriteAllText(TempPath, JsonSerializer.Serialize(envelope, Json));
        try
        {
            if (backupPath is not null && File.Exists(filePath))
            {
                File.Replace(TempPath, filePath, backupPath);
            }
            else
            {
                File.Move(TempPath, filePath, overwrite: true);
            }
        }
        finally
        {
            // A replace that failed leaves the temp file beside the intact original; it is removed
            // so the next save starts clean, and the failure still propagates to the caller.
            try { File.Delete(TempPath); } catch (IOException) { } catch (UnauthorizedAccessException) { }
        }
    }

    /// <summary>
    /// Loads the saved zone layout, dropping surfaces that are no longer available, and, when
    /// nothing is returned, says why (ADR-0032 rule 4): no file · a newer schema than this build
    /// reads · a corrupt file (unreadable JSON, a missing layout, or an arrangement that breaks
    /// the frame invariant). Never throws on a bad file. The file is never rewritten by a read; a
    /// refused file is left in place for the caller to back up before its slot is next saved.
    /// </summary>
    public ZoneLoadResult Read(IReadOnlySet<string> availableSurfaces, IReadOnlySet<string> restorableKinds)
    {
        if (!File.Exists(filePath))
        {
            return new ZoneLoadResult(null, ZoneLoadRefusal.NoFile);
        }

        ZoneEnvelope? envelope;
        try
        {
            envelope = JsonSerializer.Deserialize<ZoneEnvelope>(File.ReadAllText(filePath), Json);
        }
        catch (JsonException)
        {
            return new ZoneLoadResult(null, ZoneLoadRefusal.Corrupt); // the file is left in place for inspection
        }

        if (envelope?.Layout is null)
        {
            return new ZoneLoadResult(null, ZoneLoadRefusal.Corrupt);
        }

        if (envelope.SchemaVersion > CurrentSchemaVersion)
        {
            return new ZoneLoadResult(null, ZoneLoadRefusal.NewerSchema);
        }

        if (envelope.SchemaVersion < CurrentSchemaVersion)
        {
            // No store ever wrote a lower version (schema 1 is the first); a 0 or a missing field
            // is a file this store did not write, not a newer build's.
            return new ZoneLoadResult(null, ZoneLoadRefusal.Corrupt);
        }

        bool Available(ZoneSurfaceDto s) =>
            availableSurfaces.Contains(s.SurfaceId) || restorableKinds.Contains(s.Kind);

        var zones = ImmutableDictionary.CreateBuilder<ZoneId, ZoneState>();
        foreach (var id in Enum.GetValues<ZoneId>())
        {
            var dto = envelope.Layout.Zones.FirstOrDefault(z => z.Id == id.ToString());
            zones[id] = dto is null
                ? new ZoneState(id, Content: null, id == ZoneId.Center ? 1.0 : ZoneState.DefaultExtent, Collapsed: false)
                : new ZoneState(id, FromDto(dto.Content, Available), dto.Extent,
                    Collapsed: id != ZoneId.Center && dto.Collapsed);
        }

        var floating = envelope.Layout.Floating
            .Select(f => FromStackDto(f, Available))
            .Where(f => f is not null)
            .Cast<StackNode>()
            .ToImmutableList();

        var layout = new WorkbenchLayout(zones.ToImmutable(), floating, Maximized: null);

        try
        {
            layout.AssertInvariant();
        }
        catch (InvalidOperationException)
        {
            return new ZoneLoadResult(null, ZoneLoadRefusal.Corrupt); // e.g. a duplicated surface → keep current
        }

        return new ZoneLoadResult(layout, ZoneLoadRefusal.None);
    }

    // ── mapping ────────────────────────────────────────────────────────────────────────────

    private static ZoneStateDto ToDto(ZoneState zone) =>
        new(zone.Id.ToString(), ToDto(zone.Content), zone.Extent, zone.Collapsed);

    private static ZoneContentDto? ToDto(ZoneContent? content) => content switch
    {
        null => null,
        ZoneStack s => new ZoneContentDto("stack", [.. s.Tabs.Select(ToDto)], s.ActiveIndex, null, null, null),
        ZoneSplit p => new ZoneContentDto("split", null, 0, p.Orientation.ToString(),
            [.. p.Children.Select(c => ToDto(c)!)], [.. p.Weights]),
        _ => null,
    };

    private static ZoneStackDto ToStackDto(StackNode s) =>
        new(s.Id, [.. s.Surfaces.Select(ToDto)], s.ActiveIndex);

    private static ZoneSurfaceDto ToDto(Surface s) => new(s.SurfaceId, s.Kind, s.Title);

    private static ZoneContent? FromDto(ZoneContentDto? dto, Func<ZoneSurfaceDto, bool> available)
    {
        if (dto is null)
        {
            return null;
        }

        if (string.Equals(dto.Kind, "split", StringComparison.Ordinal)
            && dto.Children is { Count: > 0 } childrenDto)
        {
            var children = childrenDto
                .Select(c => FromDto(c, available))
                .Where(c => c is not null)
                .Cast<ZoneContent>()
                .ToImmutableList();

            return children.Count switch
            {
                0 => null,
                1 => children[0],
                _ => new ZoneSplit(
                    Enum.TryParse<Orientation>(dto.Orientation, out var o) ? o : Orientation.Horizontal,
                    children,
                    dto.Weights is { Count: > 0 } && dto.Weights.Count == children.Count
                        ? [.. dto.Weights]
                        : [.. Enumerable.Repeat(1.0 / children.Count, children.Count)]),
            };
        }

        var tabs = (dto.Tabs ?? [])
            .Where(available)
            .Select(FromDto)
            .ToImmutableList();

        return tabs.Count == 0 ? null : new ZoneStack(tabs, Math.Clamp(dto.ActiveIndex, 0, tabs.Count - 1));
    }

    private static StackNode? FromStackDto(ZoneStackDto dto, Func<ZoneSurfaceDto, bool> available)
    {
        var surfaces = dto.Surfaces.Where(available).Select(FromDto).ToImmutableList();
        return surfaces.Count == 0 ? null : new StackNode(dto.Id, surfaces, dto.ActiveIndex, StackState.Floating);
    }

    private static Surface FromDto(ZoneSurfaceDto s) => new(s.SurfaceId, s.Kind, s.Title);
}

