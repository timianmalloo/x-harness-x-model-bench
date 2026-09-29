using AiDe.Core.Watcher;

namespace AiDe.Core.Presentation;

/// <summary>
/// A liveness badge that never relies on colour. Glyph and text carry the meaning; colour is the third
/// signal (token), so the badge reads correctly in high-contrast and for a colour-blind operator
/// (WCAG 2.2 AA, "not colour alone" - mirrors <see cref="ConfidenceBadge"/>).
/// </summary>
public sealed record LivenessBadge(string Glyph, string Text, string TokenName)
{
    public static LivenessBadge For(LivenessState state) => state switch
    {
        LivenessState.Alive => new LivenessBadge("✓", "Alive", "colors.verified"),
        LivenessState.Stale => new LivenessBadge("~", "Stale", "colors.inferred"),
        _ => new LivenessBadge("×", "Ended", "colors.unverified"),
    };

    /// <summary>What a screen reader announces. Never just the colour name.</summary>
    public string AccessibleName => Text;
}

/// <summary>The literal shown when a dimension was never observed - honest, never blank (spec US-13).</summary>
public static class WatcherSessionText
{
    public const string NotRecorded = "Not Recorded";
}

/// <summary>
/// One session row of the Sessions surface - a dense, scannable, screen-reader-complete line. An
/// absent harness or model renders <see cref="WatcherSessionText.NotRecorded"/>, never blank and never
/// a guess.
/// </summary>
public sealed record WatcherSessionRow(
    string SessionId,
    string Repository,
    string Worktree,
    string Agent,
    string Harness,
    string Model,
    LivenessBadge Liveness,
    string Trust,
    int SpanCount,
    bool Disputed = false,
    string WorktreePath = "",
    string TerminalId = "")
{
    /// <summary>
    /// A short, stable handle for one session — the thing that tells two otherwise identical rows
    /// apart.
    /// </summary>
    /// <remarks>
    /// <para>Reported from the running product: three live sessions rendered as three IDENTICAL
    /// strings, because every visible field (agent, repository, branch) was the same for all of
    /// them. Nothing on the surface said WHICH session a row was, and the session id was on the
    /// record the whole time without being shown.</para>
    ///
    /// <para>Eight characters, not the whole id. A full <c>Guid.ToString("n")</c> is 32 characters of
    /// noise that pushes the readable part off the line — and the job here is discrimination between
    /// the handful of sessions on screen, not global uniqueness, which the id itself still carries.
    /// </para>
    /// </remarks>
    public string ShortId => SessionId.Length <= 8 ? SessionId : SessionId[..8];

    /// <summary>
    /// Repository and branch, separated so a branch name cannot be mistaken for a path.
    /// </summary>
    /// <remarks>
    /// <para>This used to be <c>{Repository}/{Worktree}</c>, which rendered
    /// <c>TheTerrace/docs/fix-broken-design-links</c> — read, reasonably, as a directory path, and
    /// the reporter asked why sessions were not at the repository root. They were: that is the repo
    /// <c>TheTerrace</c> on branch <c>docs/fix-broken-design-links</c>.</para>
    ///
    /// <para>A <c>/</c> separator collides with the dominant branch-naming convention — <c>docs/</c>,
    /// <c>feature/</c>, <c>fix/</c> — so the ambiguity was not an edge case but the common case.
    /// <c>@</c> cannot appear alone in a git ref, so it can never be confused for part of either
    /// side.</para>
    /// </remarks>
    public string Location => $"{Repository}@{Worktree}";

    /// <summary>The prefix a session with a disputed episode carries (US-16 discoverability, no colour-alone).</summary>
    public const string DisputedText = "⚠ Disputed";

    /// <summary>The dense one-line label (G6 Multi-Panel Data Terminal density).</summary>
    public string DisplayLabel =>
        $"{Agent} · {Location} · {ShortId} · {Harness} · {Model} · " +
        $"{Liveness.Glyph} {Liveness.Text} · {SpanCount} span(s) · {Trust}" +
        (Disputed ? $" · {DisputedText}" : string.Empty);

    /// <summary>The full row a screen reader announces (WCAG 2.2 AA).</summary>
    /// <remarks>
    /// Spoken as "on branch" rather than read as <c>@</c>: the symbol removes a VISUAL ambiguity and
    /// would introduce an audible one, since a screen reader says "at" and a listener has no way to
    /// know it separates two fields.
    /// </remarks>
    public string AccessibleName =>
        $"Agent {Agent}, session {ShortId}, in {Repository} on branch {Worktree}, " +
        $"harness {Harness}, model {Model}, " +
        $"{Liveness.Text}, {SpanCount} span(s), trust {Trust}" +
        (Disputed ? ", has a disputed score." : ".");

    /// <summary>Builds an honest row from a snapshot: null harness/model become Not Recorded.</summary>
    public static WatcherSessionRow From(WatcherSessionSnapshot snapshot)
    {
        var b = snapshot.Binding;
        return new WatcherSessionRow(
            snapshot.SessionId,
            b.Repository.DisplayName,
            b.Worktree.Branch,
            b.Agent.AgentName,
            b.Harness?.Name ?? WatcherSessionText.NotRecorded,
            b.Model?.Name ?? WatcherSessionText.NotRecorded,
            LivenessBadge.For(snapshot.Liveness),
            b.Trust.ToString(),
            snapshot.SpanCount,
            snapshot.Disputed,
            b.Worktree.Path,
            b.Terminal.TerminalId);
    }
}

/// <summary>A point-in-time read of one session: its binding, computed liveness, span count, and Disputed state.</summary>
public sealed record WatcherSessionSnapshot(
    string SessionId, SessionBinding Binding, LivenessState Liveness, int SpanCount, bool Disputed = false);

/// <summary>The read seam the Sessions pane consumes. A null pane query means no watcher store is wired.</summary>
public interface IWatcherSessionsQuery
{
    IReadOnlyList<WatcherSessionSnapshot> GetSessions();
}

/// <summary>
/// Folds the observation store + liveness into session snapshots - the deterministic compute reader
/// (DM7: liveness is computed here, never stored). Ordered by the store's own enumeration
/// (repo, worktree, session), which the pane preserves.
/// </summary>
public sealed class WatcherSessionsQuery(IWatcherObservationStore store, LivenessProjection liveness)
    : IWatcherSessionsQuery
{
    private readonly IWatcherObservationStore _store = store ?? throw new ArgumentNullException(nameof(store));
    private readonly LivenessProjection _liveness = liveness ?? throw new ArgumentNullException(nameof(liveness));
    private readonly DisputeProjection _disputes = new(store ?? throw new ArgumentNullException(nameof(store)));

    public IReadOnlyList<WatcherSessionSnapshot> GetSessions() =>
        [.. _store.AllSessions().Select(s => new WatcherSessionSnapshot(
            s.SessionId, s.Binding, _liveness.Evaluate(s.SessionId), _store.SpanCount(s.SessionId),
            _disputes.IsSessionDisputed(s.SessionId)))];
}

/// <summary>
/// The Loomkeeper Sessions surface view model - the compute reader that closes the Phase-1
/// change-surface. It renders observed sessions honestly: Not Recorded for an unproven harness/model,
/// a no-colour-alone liveness badge, and the full state set. Mirrors <see cref="EvidencePaneViewModel"/>,
/// but its load is <b>synchronous</b> (a local store fold, no I/O) - so it can never strand on a
/// "Loading…" message the way an async construction-time binding did (DC-011).
/// </summary>
public sealed class WatcherSessionsPaneViewModel(IWatcherSessionsQuery? query)
{
    public PaneState State { get; private set; } = PaneState.Loading;

    public IReadOnlyList<WatcherSessionRow> Rows { get; private set; } = [];

    /// <summary>The one string the operator reads - always evidence, never reassurance.</summary>
    public string StatusMessage { get; private set; } = "Loading sessions…";

    /// <summary>Announced through a live region so a state change reaches a screen reader without motion.</summary>
    public string LiveAnnouncement { get; private set; } = string.Empty;

    /// <summary>Loads the sessions synchronously. Degrades to an explicit state, never a blank success.</summary>
    public void Load()
    {
        if (query is null)
        {
            // No watcher store is wired (the walking-skeleton default). Say what is unavailable -
            // an unavailable result rendered as a clean empty one is the dishonesty to avoid.
            State = PaneState.Empty;
            StatusMessage = "Session observation is not available — no watcher store is attached.";
            Rows = [];
            LiveAnnouncement = StatusMessage;
            return;
        }

        try
        {
            Rows = [.. query.GetSessions().Select(WatcherSessionRow.From)];
            if (Rows.Count == 0)
            {
                State = PaneState.Empty;
                StatusMessage = "No sessions observed yet.";
            }
            else
            {
                State = PaneState.Ready;
                var alive = Rows.Count(r => r.Liveness.Text == "Alive");
                StatusMessage = $"{Rows.Count} session(s) · {alive} alive";
            }
        }
        catch (Exception ex) when (ex is not OperationCanceledException)
        {
            // DC-011: a store that cannot be read is an explicit failed state, never Loading-forever
            // and never a blank success.
            State = PaneState.Error;
            StatusMessage = "Sessions unavailable — the observation store could not be read.";
            Rows = [];
        }

        LiveAnnouncement = StatusMessage;
    }
}
