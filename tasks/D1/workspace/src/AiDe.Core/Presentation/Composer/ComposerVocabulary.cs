namespace AiDe.Core.Presentation.Composer;

/// <summary>
/// The closed page-to-host message vocabulary — five kinds, and no more (Security C20).
/// </summary>
/// <remarks>
/// <para><b>The one-line rule this whole namespace holds in its head:</b> the page contributes
/// <b>text</b>; it never contributes a <b>verb</b>, a <b>path</b>, or an <b>identity</b>.</para>
///
/// <para><b>The send verb is not here, and its absence is the control (C11).</b> Send is a WPF
/// control plus a host-side accelerator handler. There is no spelling of "send" a page can post
/// that reaches a run, because the router has no send effect to reach — the sink interface
/// <see cref="IComposerMessageSink"/> does not declare one. A page message can never evidence a
/// human gesture, because a page can post one in a loop.</para>
///
/// <para><b>Comparison is <c>Ordinal</c>, always.</b> <c>JsonSerializerDefaults.Web</c> sets
/// <c>PropertyNameCaseInsensitive</c>, so a case-varied member name can still bind; the allow-list
/// is on the <i>value</i>, and this comparison must never become case-insensitive.</para>
/// </remarks>
public static class ComposerMessageKinds
{
    /// <summary>The page finished mounting. The host may flush queued host-to-page pushes.</summary>
    public const string EditorReady = "editor.ready";

    /// <summary>One field's text changed. Carries a host-minted field id and a monotonic revision.</summary>
    public const string DraftChanged = "draft.changed";

    /// <summary>Focus left the page's last focusable element. Existing WPF focus behaviour.</summary>
    public const string FocusLeave = "focus.leave";

    /// <summary>A file was dropped. The PATHS come from <c>AdditionalObjects</c>, never from the body.</summary>
    public const string AttachOffered = "attach.offered";

    /// <summary>A diagnostic counter moved. Touches nothing outside diagnostics.</summary>
    public const string Metrics = "metrics";

    /// <summary>Every kind the host will act on. Anything else is dropped and counted.</summary>
    public static readonly IReadOnlyList<string> All =
        [EditorReady, DraftChanged, FocusLeave, AttachOffered, Metrics];

    /// <summary>
    /// Names that are <b>not</b> in the vocabulary and are not to be added — the refused-outright
    /// list (a), (b), (i), written down so a later reader adds one and a test goes red.
    /// </summary>
    /// <remarks>
    /// A list of refusals is only a control while something reads it: <c>TheFiveKindsAreTheWholeVocabularyAndTheRefusedNamesAreNotInIt</c>
    /// asserts every entry here is absent from <see cref="All"/>, and C11's oracle posts each of
    /// them and asserts the send counter never moves.
    /// </remarks>
    public static readonly IReadOnlyList<string> RefusedNames =
    [
        "send", "send.requested", "run.start", "attach.path", "file.read", "open", "navigate",
        "exec", "lease.set", "lease.exclusive", "template.apply", "attach.enabled",
        "attachEnabled", "draft.fields", "fields.set",
    ];

    /// <summary>Whether <paramref name="kind"/> is one of the five, compared ordinally.</summary>
    public static bool IsKnown(string? kind) =>
        kind is not null && All.Contains(kind, StringComparer.Ordinal);
}
