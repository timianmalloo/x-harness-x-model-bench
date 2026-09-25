using AiDe.Core.Watcher;

namespace AiDe.Core.Presentation;

/// <summary>
/// One row of the Message Board surface (US-4): a per-repository post rendered as a dense, scannable,
/// screen-reader-complete line. <see cref="BoardMessage.Content"/> is <b>quarantined untrusted data</b> -
/// it is shown to the operator but never treated as instruction; an injection-shaped post is marked
/// with a visible flag (US-4 #5), a redacted post shows a tombstone, and neither is silently blank.
/// </summary>
public sealed record WatcherBoardRow(
    string Repository,
    string Kind,
    string Author,
    string Trust,
    string Preview,
    bool InjectionFlagged,
    bool Tombstoned)
{
    private const int PreviewLength = 80;

    /// <summary>The literal shown for a post whose content was redacted (spec line 210).</summary>
    public const string RedactedText = "[redacted]";

    /// <summary>The prefix a flagged post carries so it reads as untrusted, not as a directive (US-4 #5).</summary>
    public const string FlagPrefix = "⚠ flagged · ";

    /// <summary>The dense one-line label (G6 density). Untrusted content is prefixed, never blank.</summary>
    public string DisplayLabel =>
        $"{Repository} · {Kind} · {Author} · {Trust} · {(InjectionFlagged ? FlagPrefix : string.Empty)}{Preview}";

    /// <summary>The full row a screen reader announces (WCAG 2.2 AA).</summary>
    public string AccessibleName =>
        $"{Kind} in {Repository} by {Author}, trust {Trust}" +
        (InjectionFlagged ? ", flagged as possible injection" : string.Empty) +
        (Tombstoned ? ", redacted" : $": {Preview}");

    /// <summary>Builds an honest row: a tombstone shows [redacted], never the (now null) content.</summary>
    public static WatcherBoardRow From(BoardMessage message)
    {
        var preview = message.Tombstoned
            ? RedactedText
            : Trim(message.Content ?? WatcherSessionText.NotRecorded);
        return new WatcherBoardRow(
            message.RepositoryKey,
            message.Kind.ToString(),
            message.AuthorSessionId,
            message.AuthorTrust.ToString(),
            preview,
            message.InjectionFlagged,
            message.Tombstoned);
    }

    private static string Trim(string content)
    {
        var oneLine = content.ReplaceLineEndings(" ").Trim();
        return oneLine.Length <= PreviewLength ? oneLine : oneLine[..PreviewLength] + "…";
    }
}

/// <summary>The read seam the Board pane consumes. A null query means no watcher store is wired.</summary>
public interface IWatcherBoardQuery
{
    IReadOnlyList<BoardMessage> GetMessages();
}

/// <summary>Folds the observation store's cross-repo board into the pane's read (US-4). Order preserved.</summary>
public sealed class WatcherBoardQuery(IWatcherObservationStore store) : IWatcherBoardQuery
{
    private readonly IWatcherObservationStore _store = store ?? throw new ArgumentNullException(nameof(store));

    public IReadOnlyList<BoardMessage> GetMessages() => _store.AllBoardMessages();
}

/// <summary>
/// The Loomkeeper Message Board surface view model - the compute reader for shared agent communication
/// (US-4). Renders posts across repositories with quarantined untrusted content shown but never as
/// instruction, injection flags visible, and redactions as tombstones. Synchronous load (a local store
/// fold), so it degrades to an explicit state and never strands on "Loading…" (DC-011).
/// </summary>
public sealed class WatcherBoardPaneViewModel(IWatcherBoardQuery? query)
{
    public PaneState State { get; private set; } = PaneState.Loading;

    public IReadOnlyList<WatcherBoardRow> Rows { get; private set; } = [];

    public string StatusMessage { get; private set; } = "Loading board…";

    public string LiveAnnouncement { get; private set; } = string.Empty;

    public void Load()
    {
        if (query is null)
        {
            State = PaneState.Empty;
            StatusMessage = "The message board is not available — no watcher store is attached.";
            Rows = [];
            LiveAnnouncement = StatusMessage;
            return;
        }

        try
        {
            Rows = [.. query.GetMessages().Select(WatcherBoardRow.From)];
            if (Rows.Count == 0)
            {
                State = PaneState.Empty;
                StatusMessage = "No board posts yet.";
            }
            else
            {
                State = PaneState.Ready;
                var repos = Rows.Select(r => r.Repository).Distinct(StringComparer.Ordinal).Count();
                var flagged = Rows.Count(r => r.InjectionFlagged);
                StatusMessage = flagged == 0
                    ? $"{Rows.Count} post(s) across {repos} repo(s)"
                    : $"{Rows.Count} post(s) across {repos} repo(s) · {flagged} flagged";
            }
        }
        catch (Exception ex) when (ex is not OperationCanceledException)
        {
            State = PaneState.Error;
            StatusMessage = "Board unavailable — the observation store could not be read.";
            Rows = [];
        }

        LiveAnnouncement = StatusMessage;
    }
}
