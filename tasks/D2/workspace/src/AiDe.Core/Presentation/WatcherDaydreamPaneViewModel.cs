using AiDe.Core.Watcher;

namespace AiDe.Core.Presentation;

/// <summary>
/// One row of the Daydreams surface (US-9): a pattern, where it stands, and what is stopping it.
/// </summary>
/// <remarks>
/// <para><b>The block reason is part of the row, not a tooltip.</b> A candidate that cannot be
/// promoted has to say <i>which</i> prerequisite is missing where it is read. "Promotion disabled"
/// with the reason a click away is the empty state DC-087 registered — a surface stating a
/// condition it never explains.</para>
///
/// <para><b>No content from an agent appears here.</b> A signature is built from typed values only,
/// so unlike the Message Board there is no quarantined prose to render and no injection flag to
/// show. The rows are describable entirely from the store's own vocabulary.</para>
/// </remarks>
public sealed record WatcherDaydreamRow(
    string Pattern,
    string Stage,
    string State,
    string Confidence,
    int Episodes,
    string? BlockedBecause,
    bool CanPromote)
{
    /// <summary>The dense one-line label (G6 density).</summary>
    public string DisplayLabel =>
        $"{Pattern} · {State} · {Episodes} episode(s) · {Confidence}"
        + (BlockedBecause is null ? string.Empty : $" · {BlockedBecause}");

    /// <summary>The full row a screen reader announces (WCAG 2.2 AA).</summary>
    public string AccessibleName =>
        $"{Pattern}, {State}, {Episodes} source episodes, confidence {Confidence}"
        + (CanPromote ? ", ready to promote" : BlockedBecause is null ? string.Empty : $", blocked: {BlockedBecause}");

    /// <summary>Builds a row, naming the pattern from its typed parts rather than any prose.</summary>
    public static WatcherDaydreamRow From(DaydreamCandidate candidate)
    {
        ArgumentNullException.ThrowIfNull(candidate);
        var s = candidate.Signature;

        var pattern = string.Join(" · ", new[]
        {
            s.TaskClass,
            s.Verdict.ToString(),
            s.Floors.Length == 0 ? null : "floors " + s.Floors.Replace("+", ", "),
            s.Shortfalls.Length == 0 ? null : "short " + s.Shortfalls.Replace("+", ", "),
        }.Where(p => p is not null));

        return new WatcherDaydreamRow(
            pattern,
            StageOf(candidate.State),
            candidate.State.ToString(),
            candidate.Evidence.Confidence,
            candidate.Evidence.SourceEpisodes.Count,
            candidate.BlockedBecause,
            candidate.CanPromote);
    }

    /// <summary>
    /// The three stages the spec's Daydreams tab shows: Observations, Candidates, Promoted.
    /// </summary>
    /// <remarks>
    /// Disconfirmed, Deferred and Rejected stay under <b>Candidates</b> rather than being hidden or
    /// given a fourth stage. A refuted candidate is the most informative thing on this surface —
    /// it is the system having done the disconfirming work and reported the answer nobody wanted —
    /// and moving it out of sight would leave a reader looking at only the proposals that survived.
    /// </remarks>
    public static string StageOf(DaydreamState state) => state switch
    {
        DaydreamState.Observation => "Observations",
        DaydreamState.Promoted => "Promoted",
        DaydreamState.Retracted => "Promoted",
        _ => "Candidates",
    };
}

/// <summary>The read seam the Daydreams pane consumes. A null query means no watcher store is wired.</summary>
public interface IWatcherDaydreamQuery
{
    IReadOnlyList<DaydreamCandidate> GetCandidates();

    /// <summary>
    /// Why there is no record to read, or <c>null</c> when there is one.
    /// </summary>
    /// <remarks>
    /// A separate channel from an empty list, because "no repository is open" and "this repository
    /// has observed nothing yet" are different facts and only one of them is about the repository.
    /// Collapsing them would let the pane report an absence as a result (DC-025).
    /// </remarks>
    string? Unavailable { get; }

    /// <summary>Lines the record held that this version could not parse. Reported, never swallowed.</summary>
    int UnreadableLines { get; }

    /// <summary>
    /// Why an empty Daydream is empty, when the reason is not "nothing has happened yet".
    /// </summary>
    /// <remarks>
    /// <see cref="DaydreamReach.Finding"/>, or <c>null</c> when there is nothing to report. This is
    /// the surface half of the design's §8 question — <i>is Daydream seeing anything?</i> — and it
    /// exists because "No patterns observed yet" is true of a healthy repository and of one where
    /// nothing observable was ever recorded, and only the second needs an operator (DC-025).
    /// </remarks>
    string? ReachFinding { get; }
}

/// <summary>
/// Folds the repository's Daydream record into the pane's read (US-9).
/// </summary>
/// <remarks>
/// <para>The fold runs here rather than in the view model, so the pane renders a decision it did not
/// make. Every state — including whether promotion is possible — comes from
/// <see cref="DaydreamFold"/>, which is where the acceptance criteria are tested.</para>
///
/// <para><b>The repository is the record, not the store.</b> This read used to fold
/// <c>IWatcherObservationStore</c>'s <c>daydream_*_fact</c> tables. Those tables still exist —
/// deleting a shipped migration is worse than leaving one unused — but they are no longer
/// authoritative, and nothing reads them. Two definitions of one quantity is a defect signature
/// (DM7), so there is deliberately no parallel copy to fall back to.
/// (<c>design-watcher-daydream-dream-seam</c> §4a.)</para>
/// </remarks>
public sealed class WatcherDaydreamQuery(
    DaydreamRepositoryRecord record,
    DaydreamReachProbe? reach = null) : IWatcherDaydreamQuery
{
    private readonly DaydreamRepositoryRecord _record = record ?? throw new ArgumentNullException(nameof(record));
    private readonly DaydreamFold _fold = new();

    private int _unreadable;

    public string? Unavailable => _record.Unavailable;

    public int UnreadableLines => _unreadable;

    /// <summary>
    /// The probe's finding, or <c>null</c> when no probe is wired.
    /// </summary>
    /// <remarks>
    /// Optional so a host with no scored episodes to compare against gets no finding rather than a
    /// fabricated one — an absent probe must never render as "nothing to report", which is the
    /// distinction the probe exists to make in the first place.
    /// </remarks>
    public string? ReachFinding => reach?.Probe().Finding;

    public IReadOnlyList<DaydreamCandidate> GetCandidates()
    {
        var read = _record.Read();
        _unreadable = read.UnreadableLines;
        return _fold.Fold(read.Observations, read.Events);
    }
}

/// <summary>
/// The Loomkeeper Daydreams surface view model (US-9) — three stages, each with an honest empty
/// state, and promotion visible only where it is actually possible.
/// </summary>
/// <remarks>
/// Synchronous load (a local store fold), so it degrades to an explicit state and never strands on
/// "Loading…" (DC-011).
/// </remarks>
public sealed class WatcherDaydreamPaneViewModel(IWatcherDaydreamQuery? query)
{
    /// <summary>The stages in reading order, so an empty one is still shown and named.</summary>
    public static IReadOnlyList<string> Stages { get; } = ["Observations", "Candidates", "Promoted"];

    public PaneState State { get; private set; } = PaneState.Loading;

    public IReadOnlyList<WatcherDaydreamRow> Rows { get; private set; } = [];

    public string StatusMessage { get; private set; } = "Loading daydreams…";

    public string LiveAnnouncement { get; private set; } = string.Empty;

    /// <summary>Rows for one stage, in reading order. An empty stage returns an empty list.</summary>
    public IReadOnlyList<WatcherDaydreamRow> RowsFor(string stage) =>
        [.. Rows.Where(r => string.Equals(r.Stage, stage, StringComparison.Ordinal))];

    /// <summary>
    /// What to show under a stage with nothing in it.
    /// </summary>
    /// <remarks>
    /// Each names only what it has looked at. "Nothing to show" is complete; "nothing to show
    /// because X" is a claim, and a surface that has not checked X is not entitled to make it
    /// (DC-087). None of these mentions the extractor, the scorer, or any subsystem this pane does
    /// not read.
    /// </remarks>
    public static string EmptyStateFor(string stage) => stage switch
    {
        "Observations" => "No patterns observed yet.",
        "Candidates" => "Nothing has recurred often enough to propose.",
        "Promoted" => "Nothing has been promoted.",
        _ => "Nothing to show.",
    };

    public void Load()
    {
        if (query is null)
        {
            State = PaneState.Empty;
            StatusMessage = "Daydreams are not available — no watcher store is attached.";
            Rows = [];
            LiveAnnouncement = StatusMessage;
            return;
        }

        // Asked before the read, not after: an unavailable record reads as empty, and reporting
        // that as "no patterns observed yet" would be a claim about the repository made by a pane
        // that never opened one.
        if (query.Unavailable is { Length: > 0 } reason)
        {
            State = PaneState.Empty;
            StatusMessage = reason;
            Rows = [];
            LiveAnnouncement = StatusMessage;
            return;
        }

        try
        {
            Rows = [.. query.GetCandidates().Select(WatcherDaydreamRow.From)];

            // A record that is partly unreadable is never rendered as a whole one, whatever it
            // otherwise contains (DC-025). The count comes last so it reads as a caveat on the
            // number rather than replacing it.
            var caveat = query.UnreadableLines > 0
                ? $" · {query.UnreadableLines} line(s) could not be read"
                : string.Empty;

            if (Rows.Count == 0)
            {
                State = PaneState.Empty;

                // The finding REPLACES the empty message rather than appending to it. "No patterns
                // observed yet" is true of a healthy repository and of one Daydream cannot see, and
                // leading with it would let the reassurance arrive first and the cause second —
                // which is the reading this whole probe exists to displace (DC-025).
                StatusMessage = (query.ReachFinding is { Length: > 0 } finding
                    ? finding
                    : "No patterns observed yet.") + caveat;
            }
            else
            {
                State = PaneState.Ready;
                var promotable = Rows.Count(r => r.CanPromote);
                var candidates = RowsFor("Candidates").Count;
                StatusMessage = (promotable == 0
                    ? $"{Rows.Count} pattern(s) · {candidates} candidate(s) · none ready to promote"
                    : $"{Rows.Count} pattern(s) · {candidates} candidate(s) · {promotable} ready to promote")
                    + caveat;
            }
        }
        catch (Exception ex) when (ex is not OperationCanceledException)
        {
            State = PaneState.Error;
            StatusMessage = "Daydreams unavailable — the repository's Daydream record could not be read.";
            Rows = [];
        }

        LiveAnnouncement = StatusMessage;
    }
}
