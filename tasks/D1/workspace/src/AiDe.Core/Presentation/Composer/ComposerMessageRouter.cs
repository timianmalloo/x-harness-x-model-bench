using System.Text;
using System.Text.Json;

namespace AiDe.Core.Presentation.Composer;

/// <summary>Everything the host may do in response to a page message. There is no send.</summary>
/// <remarks>
/// <b>The absence of a send method is Security C11's structural half.</b> The router cannot start a
/// run because it holds nothing that could; the WPF Send button and the host's accelerator handler
/// are the only callers of the send gate, and neither is reachable from here.
/// </remarks>
public interface IComposerMessageSink
{
    /// <summary>The page mounted. A second ready for one instance is dropped and counted.</summary>
    void MarkReady();

    /// <summary>Replace the host-side mirror of one host-minted field.</summary>
    void SetFieldText(string fieldId, long revision, string text);

    /// <summary>
    /// Move WPF focus off the web control: forward (Tab from the page's last stop — existing
    /// behaviour) or backward (Shift+Tab from its first stop — DS-1 seam 3, into the thread's last
    /// stop). The page only ever says which way; where focus lands is the host's.
    /// </summary>
    void MoveFocus(bool backward);

    /// <summary>
    /// A drop was offered. The paths came from <c>CoreWebView2File.Path</c> in
    /// <c>AdditionalObjects</c> — never from the message body (Security C13).
    /// </summary>
    void OfferAttachment(IReadOnlyList<string> filePaths);

    /// <summary>Move a diagnostic counter. Touches no state outside diagnostics.</summary>
    void RecordMetric(string name, long value);
}

/// <summary>What the router did with one message, and why.</summary>
/// <param name="Accepted">Whether any effect was applied.</param>
/// <param name="Kind">The kind as read, or the empty string when it could not be read.</param>
/// <param name="Reason">Why it was dropped. Empty when accepted.</param>
public sealed record ComposerRouteResult(bool Accepted, string Kind, string Reason);

/// <summary>
/// The page-to-host message router: a <b>pure function of its arguments</b> (Security C9).
/// </summary>
/// <remarks>
/// <para><b>Why a pure function rather than an event handler.</b> The WebView2 handler passes the
/// frame source, the raw JSON and the file objects, and does nothing else — so every rule below is
/// testable headlessly, and a rule that can only be exercised by driving a real browser is a rule
/// that is exercised once.</para>
///
/// <para><b>Origin is checked first and compared ordinally against the exact page URL.</b> Not the
/// host, not a prefix: an attacker-controlled <c>aide.assets.invalid.evil.test</c> and a second
/// document on the real origin both pass a prefix test written the obvious way. The check is only
/// sound because frame navigation is cancelled host-side (C10) — the two are one control in two
/// places.</para>
///
/// <para><b>Nothing here throws.</b> A malformed body, a very large string, a duplicate key and a
/// null where an object was expected all reach drop-and-count (C20). An exception escaping into a
/// WebView2 event handler is an unhandled exception on the UI thread.</para>
/// </remarks>
public sealed class ComposerMessageRouter
{
    /// <summary>The envelope version. A missing or different value is dropped.</summary>
    public const int ProtocolVersion = 1;

    /// <summary>
    /// The per-message byte ceiling on a field's text. Over-cap <b>refuses the message</b>; it never
    /// truncates, because a truncated draft is a draft the operator did not write.
    /// </summary>
    public const int MaxFieldTextBytes = 256 * 1024;

    /// <summary>The cap on how many dropped objects one attach offer may carry (Ruling 43).</summary>
    public const int MaxOfferedObjects = 5;

    private static readonly string[] ForbiddenBodyMembers = ["path", "uri", "name", "content", "bytes"];

    private readonly string _pageUrl;
    private readonly string _instance;
    private readonly IComposerMessageSink _sink;
    private readonly HashSet<string> _fieldIds;
    private readonly Dictionary<string, long> _revisions = new(StringComparer.Ordinal);

    /// <param name="pageUrl">The composer page's exact URL. Nothing else is an accepted source.</param>
    /// <param name="instance">The host-minted identifier for this composer surface.</param>
    /// <param name="fieldIds">Every field id the host minted. The page may only match one.</param>
    /// <param name="sink">Where accepted effects go.</param>
    public ComposerMessageRouter(
        string pageUrl, string instance, IReadOnlyList<string> fieldIds, IComposerMessageSink sink)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(pageUrl);
        ArgumentException.ThrowIfNullOrWhiteSpace(instance);
        ArgumentNullException.ThrowIfNull(fieldIds);
        ArgumentNullException.ThrowIfNull(sink);

        _pageUrl = pageUrl;
        _instance = instance;
        _sink = sink;
        _fieldIds = new HashSet<string>(fieldIds, StringComparer.Ordinal);
    }

    /// <summary>How many messages were refused. Drops are counted, never recorded with their content.</summary>
    public long Dropped { get; private set; }

    /// <summary>Whether the page has reported ready for this instance.</summary>
    public bool IsReady { get; private set; }

    /// <summary>
    /// Re-mints the acceptable field set, after the host changed the form.
    /// </summary>
    /// <remarks>
    /// <b>The host mints; the page matches — and that stays true when the form changes.</b> Choosing
    /// a template replaces the fields on screen, so the ids the page may address must be replaced
    /// too: an id from the previous form is an id the host no longer holds, and continuing to accept
    /// it would let a page write into a field that is not there. The stored revisions are cleared
    /// with them, because a revision is per field and the fields are new.
    /// </remarks>
    public void ReplaceFields(IReadOnlyList<string> fieldIds)
    {
        ArgumentNullException.ThrowIfNull(fieldIds);

        _fieldIds.Clear();
        _fieldIds.UnionWith(fieldIds);
        _revisions.Clear();
    }

    /// <summary>
    /// The host declared a navigation: the document that reported ready is being replaced, so the
    /// next <c>editor.ready</c> is a <b>new page's mount</b>, not a duplicate.
    /// </summary>
    /// <remarks>
    /// The once-gate in <see cref="Ready"/> is per <b>document</b>, not per surface (DC-138): only the
    /// host can start a navigation, so only the host resets it — nothing in the page's vocabulary
    /// reaches this method. The per-field revisions go with it: a new document counts from its own
    /// 1, and the old page's high-water marks would drop every keystroke as "not strictly greater".
    /// </remarks>
    public void BeginNavigation()
    {
        IsReady = false;
        _revisions.Clear();
    }

    /// <summary>Routes one message. Never throws.</summary>
    /// <param name="sourceUri">The frame's own URI, as WebView2 reported it.</param>
    /// <param name="json">The raw message body.</param>
    /// <param name="additionalObjectPaths">
    /// Paths read from the message's file objects, in order. Empty when the message carried none —
    /// including when its body named one, which is exactly the case C13 refuses.
    /// </param>
    public ComposerRouteResult Route(
        string? sourceUri, string? json, IReadOnlyList<string>? additionalObjectPaths)
    {
        try
        {
            return RouteCore(sourceUri, json, additionalObjectPaths ?? []);
        }
        catch (Exception error) when (error is JsonException or InvalidOperationException
            or ArgumentException or FormatException or OverflowException)
        {
            return Drop(string.Empty, "the message could not be read at all");
        }
    }

    private ComposerRouteResult RouteCore(
        string? sourceUri, string? json, IReadOnlyList<string> additionalObjectPaths)
    {
        if (!string.Equals(sourceUri, _pageUrl, StringComparison.Ordinal))
        {
            return Drop(string.Empty, "the message did not come from the composer page's own document");
        }

        if (string.IsNullOrEmpty(json))
        {
            return Drop(string.Empty, "the message body was empty");
        }

        using var document = JsonDocument.Parse(json);
        if (document.RootElement.ValueKind != JsonValueKind.Object)
        {
            return Drop(string.Empty, "the message body was not an object");
        }

        var root = document.RootElement;

        if (HasDuplicateMember(root))
        {
            // FOUND BY THE FUZZ CORPUS, and kept because it is a real smuggling shape rather than a
            // curiosity. System.Text.Json resolves a duplicate member to the LAST occurrence, so
            // {"kind":"nope","kind":"editor.ready"} routes as editor.ready — while any other reader of
            // the same bytes (a logger, a proxy, a future parser) may take the first. A message whose
            // meaning depends on which parser reads it has no meaning, so it is refused outright.
            return Drop(string.Empty, "the message body declared a member twice");
        }

        if (!root.TryGetProperty("v", out var version)
            || version.ValueKind != JsonValueKind.Number
            || !version.TryGetInt32(out var declared)
            || declared != ProtocolVersion)
        {
            return Drop(string.Empty, "the envelope did not declare the pinned protocol version");
        }

        if (!root.TryGetProperty("kind", out var kindElement)
            || kindElement.ValueKind != JsonValueKind.String)
        {
            return Drop(string.Empty, "the envelope carried no kind");
        }

        var kind = kindElement.GetString() ?? string.Empty;
        if (!ComposerMessageKinds.IsKnown(kind))
        {
            return Drop(kind, "the kind is not one of the five");
        }

        if (!root.TryGetProperty("instance", out var instanceElement)
            || instanceElement.ValueKind != JsonValueKind.String
            || !string.Equals(instanceElement.GetString(), _instance, StringComparison.Ordinal))
        {
            return Drop(kind, "the instance is unknown or stale");
        }

        return kind switch
        {
            ComposerMessageKinds.EditorReady => Ready(kind),
            ComposerMessageKinds.DraftChanged => DraftChanged(kind, root),
            ComposerMessageKinds.FocusLeave => Accept(kind, () => _sink.MoveFocus(IsBackward(root))),
            ComposerMessageKinds.AttachOffered => AttachOffered(kind, root, additionalObjectPaths),
            ComposerMessageKinds.Metrics => Metrics(kind, root),
            _ => Drop(kind, "the kind is not one of the five"),
        };
    }

    /// <summary>Whether any top-level member name appears more than once.</summary>
    private static bool HasDuplicateMember(JsonElement root)
    {
        var seen = new HashSet<string>(StringComparer.Ordinal);
        foreach (var member in root.EnumerateObject())
        {
            if (!seen.Add(member.Name))
            {
                return true;
            }
        }

        return false;
    }

    private ComposerRouteResult Ready(string kind)
    {
        if (IsReady)
        {
            return Drop(kind, "this instance already reported ready");
        }

        IsReady = true;
        _sink.MarkReady();
        return new ComposerRouteResult(true, kind, string.Empty);
    }

    private ComposerRouteResult DraftChanged(string kind, JsonElement root)
    {
        if (!IsReady)
        {
            return Drop(kind, "a draft change arrived before the page reported ready");
        }

        if (!root.TryGetProperty("fieldId", out var fieldElement)
            || fieldElement.ValueKind != JsonValueKind.String
            || fieldElement.GetString() is not { } fieldId
            || !_fieldIds.Contains(fieldId))
        {
            // NEVER CREATE ONE. A field id the host did not mint is a field the host does not have,
            // and minting it here would let the page choose what it is editing.
            return Drop(kind, "the field id was not one the host minted");
        }

        if (!root.TryGetProperty("rev", out var revElement)
            || revElement.ValueKind != JsonValueKind.Number
            || !revElement.TryGetInt64(out var revision))
        {
            return Drop(kind, "the revision was missing or not a number");
        }

        if (_revisions.TryGetValue(fieldId, out var stored) && revision <= stored)
        {
            return Drop(kind, "the revision was not strictly greater than the stored one");
        }

        if (!root.TryGetProperty("text", out var textElement)
            || textElement.ValueKind != JsonValueKind.String
            || textElement.GetString() is not { } text)
        {
            return Drop(kind, "the text was missing or not a string");
        }

        if (Encoding.UTF8.GetByteCount(text) > MaxFieldTextBytes)
        {
            return Drop(kind, "the text was over the per-message byte cap; the message is refused, not truncated");
        }

        _revisions[fieldId] = revision;
        _sink.SetFieldText(fieldId, revision, text);
        return new ComposerRouteResult(true, kind, string.Empty);
    }

    private ComposerRouteResult AttachOffered(
        string kind, JsonElement root, IReadOnlyList<string> additionalObjectPaths)
    {
        foreach (var forbidden in ForbiddenBodyMembers)
        {
            if (root.TryGetProperty(forbidden, out _))
            {
                // C13. A path that crosses as a string is a path the page chose.
                return Drop(kind, "the body named a path-shaped member; no path crosses the bridge as a string");
            }
        }

        if (additionalObjectPaths.Count == 0)
        {
            return Drop(kind, "the message carried no file object");
        }

        if (additionalObjectPaths.Count > MaxOfferedObjects)
        {
            return Drop(kind, "more objects were offered at once than the cap allows");
        }

        _sink.OfferAttachment(additionalObjectPaths);
        return new ComposerRouteResult(true, kind, string.Empty);
    }

    private ComposerRouteResult Metrics(string kind, JsonElement root)
    {
        if (!root.TryGetProperty("name", out var nameElement)
            || nameElement.ValueKind != JsonValueKind.String
            || nameElement.GetString() is not { } name
            || !root.TryGetProperty("value", out var valueElement)
            || valueElement.ValueKind != JsonValueKind.Number
            || !valueElement.TryGetInt64(out var value))
        {
            return Drop(kind, "the metric was not a name and a number");
        }

        _sink.RecordMetric(name, value);
        return new ComposerRouteResult(true, kind, string.Empty);
    }

    /// <summary>A <c>focus.leave</c>'s optional direction: <c>"backward"</c>, else forward. Anything else is forward — never a third way.</summary>
    private static bool IsBackward(JsonElement root) =>
        root.TryGetProperty("direction", out var direction)
        && direction.ValueKind == JsonValueKind.String
        && string.Equals(direction.GetString(), "backward", StringComparison.Ordinal);

    private ComposerRouteResult Accept(string kind, Action effect)
    {
        effect();
        return new ComposerRouteResult(true, kind, string.Empty);
    }

    private ComposerRouteResult Drop(string kind, string reason)
    {
        Dropped++;
        return new ComposerRouteResult(false, kind, reason);
    }
}
