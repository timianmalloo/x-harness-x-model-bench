using AiDe.Core.Watcher;

namespace AiDe.Core.Presentation;

/// <summary>
/// One row of the Leaderboard surface (US-14): a facet cell within one (task class, score schema)
/// segment. A cell below the cohort minimum or one that resolves to a single operator renders
/// <b>Not Comparable</b> with its reason, never a rank (US-14/US-10 - a single operator is not
/// de-anonymised off a public board). Comparable cells carry rank, cohort and median Weave. There is
/// deliberately no single optimisable scalar the operator can chase (US-16).
/// </summary>
public sealed record WatcherLeaderboardRow(
    string Segment,
    string Facet,
    string Label,
    int? Rank,
    int Cohort,
    double? MedianWeave,
    bool Comparable,
    string? NotComparableReason)
{
    /// <summary>The literal a non-comparable cell shows in place of a rank (US-10/US-14).</summary>
    public const string NotComparableText = "Not Comparable";

    public string RankText => Comparable && Rank is { } r ? $"#{r}" : NotComparableText;

    public string MedianText => Comparable && MedianWeave is { } m ? $"{m:0.#}" : "—";

    /// <summary>The dense one-line label (G6 density).</summary>
    public string DisplayLabel =>
        $"{Segment} · {Facet} · {Label} · {RankText} · median {MedianText} · cohort {Cohort}" +
        (Comparable ? string.Empty : $" · {NotComparableReason}");

    /// <summary>The full row a screen reader announces (WCAG 2.2 AA).</summary>
    public string AccessibleName =>
        Comparable
            ? $"{Label} ({Facet}) in {Segment}: rank {Rank}, median Weave {MedianText}, cohort {Cohort}."
            : $"{Label} ({Facet}) in {Segment}: not comparable, {NotComparableReason}.";

    public static WatcherLeaderboardRow From(Leaderboard board, LeaderboardCell cell)
    {
        var segment = $"{board.TaskClass}·{board.SchemaVersion}";
        return new WatcherLeaderboardRow(
            segment,
            cell.Facet.ToString(),
            cell.Label,
            cell.Rank,
            cell.Cohort,
            cell.MedianWeave,
            cell.Comparable,
            cell.NotComparableReason);
    }
}

/// <summary>The read seam the Leaderboard pane consumes. A null query means no watcher store is wired.</summary>
public interface IWatcherLeaderboardQuery
{
    IReadOnlyList<ScoredEpisode> GetScoredEpisodes();
}

/// <summary>Folds the store's materialised scored episodes into the leaderboard's read (US-14).</summary>
public sealed class WatcherLeaderboardQuery(IWatcherObservationStore store) : IWatcherLeaderboardQuery
{
    private readonly IWatcherObservationStore _store = store ?? throw new ArgumentNullException(nameof(store));

    public IReadOnlyList<ScoredEpisode> GetScoredEpisodes() => _store.AllScoredEpisodes();
}

/// <summary>The read seam for the derived Disputed state (US-16). A null query means disputes are not shown.</summary>
public interface IWatcherDisputeQuery
{
    IReadOnlySet<string> DisputedEpisodeIds();
}

/// <summary>Folds the store's append-only disputes into the disputed-episode set (US-16 / rule 12).</summary>
public sealed class WatcherDisputeQuery(IWatcherObservationStore store) : IWatcherDisputeQuery
{
    private readonly DisputeProjection _projection = new(store ?? throw new ArgumentNullException(nameof(store)));

    public IReadOnlySet<string> DisputedEpisodeIds() => _projection.DisputedEpisodeIds();
}

/// <summary>
/// The Loomkeeper Leaderboard surface view model - the comparative view of agent effectiveness
/// (US-14). It discovers the distinct (task class, score schema) segments present in the scored
/// episodes and composes one leaderboard per segment through <see cref="LeaderboardComposer"/> (never
/// comparing across segments - rule 11), flattening the cells into honest rows: a rank where
/// comparable, "Not Comparable" with a reason where the cohort is too small or single-operator
/// (US-10). Synchronous load; degrades to an explicit state (DC-011).
/// </summary>
public sealed class WatcherLeaderboardPaneViewModel(IWatcherLeaderboardQuery? query, IWatcherDisputeQuery? disputes = null)
{
    private readonly LeaderboardComposer _composer = new();

    public PaneState State { get; private set; } = PaneState.Loading;

    public IReadOnlyList<WatcherLeaderboardRow> Rows { get; private set; } = [];

    public string StatusMessage { get; private set; } = "Loading leaderboard…";

    public string LiveAnnouncement { get; private set; } = string.Empty;

    public void Load()
    {
        if (query is null)
        {
            State = PaneState.Empty;
            StatusMessage = "The leaderboard is not available — no watcher store is attached.";
            Rows = [];
            LiveAnnouncement = StatusMessage;
            return;
        }

        try
        {
            var episodes = query.GetScoredEpisodes();

            // Segment by (workspace, task class, score schema) - a comparison never crosses any of
            // the three (rule 11). Discovered from the episodes rather than enumerated, so a segment
            // that is not comparable simply contributes no cells instead of an empty row.
            var segments = episodes
                .Select(e => e.Segment)
                .Distinct()
                .OrderBy(s => s.Workspace?.Value ?? string.Empty, StringComparer.Ordinal)
                .ThenBy(s => s.TaskClass, StringComparer.Ordinal)
                .ThenBy(s => s.SchemaVersion, StringComparer.Ordinal);

            var rows = new List<WatcherLeaderboardRow>();
            foreach (var segment in segments)
            {
                var board = _composer.Compose(episodes, segment);
                rows.AddRange(board.Cells.Select(c => WatcherLeaderboardRow.From(board, c)));
            }

            Rows = rows;
            if (Rows.Count == 0)
            {
                State = PaneState.Empty;
                StatusMessage = "No scored episodes yet — nothing to rank.";
            }
            else
            {
                State = PaneState.Ready;
                var comparable = Rows.Count(r => r.Comparable);
                var disputed = CountDisputedScoredEpisodes(episodes);
                StatusMessage = disputed == 0
                    ? $"{Rows.Count} cell(s) · {comparable} comparable"
                    : $"{Rows.Count} cell(s) · {comparable} comparable · {disputed} disputed episode(s)";
            }
        }
        catch (Exception ex) when (ex is not OperationCanceledException)
        {
            State = PaneState.Error;
            StatusMessage = "Leaderboard unavailable — the observation store could not be read.";
            Rows = [];
        }

        LiveAnnouncement = StatusMessage;
    }

    /// <summary>
    /// How many of the scored episodes carry at least one dispute (US-16 - Disputed is discoverable
    /// from the surface). Derived from the append-only dispute facts, never a stored flag (DM7). Zero
    /// when no dispute query is wired.
    /// </summary>
    private int CountDisputedScoredEpisodes(IReadOnlyList<ScoredEpisode> episodes)
    {
        if (disputes is null)
        {
            return 0;
        }

        var disputed = disputes.DisputedEpisodeIds();
        return episodes.Count(e => disputed.Contains(e.EpisodeId));
    }
}
