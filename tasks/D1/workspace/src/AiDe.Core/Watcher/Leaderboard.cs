namespace AiDe.Core.Watcher;

/// <summary>
/// The partition a Weave score is comparable within: one workspace, one task class, one score schema
/// version. A comparison never crosses any of the three (spec US-14, rule 10).
/// </summary>
/// <param name="Workspace">
/// The repository the work happened in - see <see cref="WorkspaceKey"/> for why it is the repository
/// and not the checkout. <c>null</c> for a score recorded before segmentation existed, or where the
/// repository could not be resolved; such an episode is excluded from every cell rather than pooled
/// with other unknowns into a cohort that does not exist.
/// </param>
/// <remarks>
/// <para><b>One type rather than three adjacent strings.</b> <c>TaskClass</c> and
/// <c>SchemaVersion</c> already sat side by side in this record, in <see cref="Leaderboard"/>, and in
/// the standing's trend filter; adding a third string of the same type would have made a reordered
/// triple compile and pass, in the values that reach a surface and are read as meaning something.
/// With one type the two filter predicates collapse into one equality, and the day a fourth axis
/// arrives every call site breaks at once instead of silently accepting the wrong order.</para>
///
/// <para><b>The schema version is not the caller's to supply.</b> It comes from the scorecard the
/// scorer produced, so <see cref="ScoringService"/> composes the segment rather than accepting one -
/// two definitions of one quantity is a defect signature (DM7).</para>
/// </remarks>
public sealed record ScoreSegment(WorkspaceKey? Workspace, string TaskClass, string SchemaVersion)
{
    /// <summary>
    /// The task class of an episode whose kind of work was never declared.
    /// </summary>
    /// <remarks>
    /// The coordination contract carries a goal and a done-condition but <b>no task class</b> - an
    /// agent declares what it is trying to do, not what kind of work it is. So the class is genuinely
    /// absent, and this names the absence rather than inventing a kind. It is not a category anyone
    /// can be ranked in: see <see cref="IsComparable"/>.
    /// </remarks>
    public const string Unclassified = "unclassified";

    /// <summary>
    /// Whether this segment is a cohort at all, and therefore whether a rank in it would mean anything.
    /// </summary>
    /// <remarks>
    /// <para>Two conditions, both absences rather than values. <b>No workspace</b> - the repository
    /// could not be resolved, or the row predates segmentation, so the directives the work happened
    /// under are unknown. <b>No task class</b> - pooling every undeclared episode would compare a
    /// spike against a refactor and read the difference as an agent improving, which is the exact
    /// error segmentation exists to prevent.</para>
    ///
    /// <para>An incomparable segment still gets <b>scored</b> and still yields a standing; what it
    /// does not get is a rank. That distinction is the whole point - Not Comparable is a statement
    /// about the cohort, and a low score would be a statement about the agent.</para>
    ///
    /// <para>The rule lives here rather than in the composer because two consumers already ask it
    /// (the board and the standing's trend), and a rule spelled twice is a rule that drifts.</para>
    /// </remarks>
    public bool IsComparable => IncomparableReason is null;

    /// <summary>
    /// Why this segment is not a cohort, or <c>null</c> when it is one.
    /// </summary>
    /// <remarks>
    /// The reason travels with the verdict because the agent reading its standing sees only that it
    /// has no rank. "No rank" with no cause is an empty state naming nothing (DC-087), and the two
    /// causes want opposite responses: an undeclared task class is something the agent can fix, an
    /// unresolvable repository is not.
    /// </remarks>
    public string? IncomparableReason
        => Workspace is null ? "the repository this work happened in could not be resolved"
            : string.Equals(TaskClass, Unclassified, StringComparison.Ordinal)
                ? "the kind of work was not declared, so there is no cohort to rank within"
                : null;
}

/// <summary>
/// The task-class vocabulary a session or a prompt may declare — as opposed to
/// <see cref="ScoreSegment.Unclassified"/>, which names the ABSENCE of a declaration.
/// </summary>
/// <remarks>
/// One home for the quoted literal (ADR-0033 §4): a census asserts <c>"free-form"</c> appears
/// exactly once in <c>src/</c>, here. <see cref="AiDe.Core.Sessions.SessionConfig.DefaultTaskClass"/>
/// and <c>ComposerSendContext.TaskClass</c> read this constant rather than re-quoting it — two
/// spellings of one string is the defect DM7 names.
/// </remarks>
public static class TaskClasses
{
    /// <summary>The provenance vocabulary of an episode's task class (ADR-0028's amendment) — the envelope's <c>task_class.source</c>, spelled once for the cohort column.</summary>
    public static class Sources
    {
        /// <summary>The session's declared default applied (Ruling 72).</summary>
        public const string SessionDefault = "session-default";

        /// <summary>Chosen for that prompt (Ruling 70).</summary>
        public const string Operator = "operator";
    }

    /// <summary>
    /// The session's default task class (Ruling 70; Ruling 72): "the basic should be free-form upon
    /// open, and then I can change it" — an <b>explicit, declared</b> value, not an absence. Unlike
    /// <see cref="ScoreSegment.Unclassified"/>, a segment carrying this <b>is</b> a cohort: it
    /// partitions and ranks like any other task class (Ruling 72's reading of ADR-0028).
    /// </summary>
    public const string FreeForm = "free-form";
}

/// <summary>
/// A scored episode with its harness/model/operator attribution - the input to the leaderboard and
/// standing. <see cref="Weave"/> is the sum of the scored dimensions' earned points (there is no single
/// stored score; it is derived, DM7).
/// </summary>
public sealed record ScoredEpisode(
    string EpisodeId, string? Harness, string? Model, string OperatorId,
    ScoreSegment Segment, Scorecard Scorecard)
{
    /// <summary>The kind of work, from <see cref="Segment"/>.</summary>
    public string TaskClass => Segment.TaskClass;

    /// <summary>
    /// Where the class came from — <c>session-default</c> or <c>operator</c> (Ruling 70; ADR-0033
    /// rule 4) — or <c>null</c> for <b>not recorded</b>: a row written before the column existed,
    /// or an episode nothing stamped. A cohort attribute beside <see cref="Segment"/>, never inside
    /// it (ADR-0028's amendment): it changes no cell's membership, only what the board can say
    /// about the cell.
    /// </summary>
    public string? TaskClassSource { get; init; }

    /// <summary>The score schema version, from <see cref="Segment"/>.</summary>
    public string SchemaVersion => Segment.SchemaVersion;

    public double Weave => Scorecard.Assessments.Where(a => a.EarnedPoints is not null).Sum(a => a.EarnedPoints!.Value);

    public double? CoverageRatio => Scorecard.Coverage is { Required: > 0 } c ? (double)c.Observed / c.Required : null;

    public bool IsScoreable => Scorecard.Verdict is WeaveVerdict.Scored or WeaveVerdict.Partial;
}

/// <summary>The three leaderboard axes (spec US-14). There is deliberately no per-operator facet.</summary>
public enum LeaderboardFacet { Harness, Model, HarnessModel }

/// <summary>
/// One leaderboard cell. A cell below the cohort minimum or one that resolves to a single operator
/// renders Not Comparable, never a rank (spec US-14/US-10). Every comparable cell carries its cohort
/// size and Evidence Coverage.
/// </summary>
public sealed record LeaderboardCell(
    LeaderboardFacet Facet, string Label, int Cohort, double? MedianWeave, double? Coverage,
    int? Rank, bool Comparable, string? NotComparableReason)
{
    /// <summary>How many of the cohort ranked under the session's DEFAULT class (<c>task_class_source = session-default</c>) — so a defaulted <c>free-form</c> is told from a chosen one (ADR-0028's amendment).</summary>
    public int DefaultedClass { get; init; }

    /// <summary>How many of the cohort ranked under a class CHOSEN for the prompt (<c>operator</c>). The remainder is not recorded — never counted as either.</summary>
    public int ChosenClass { get; init; }
}

/// <summary>A leaderboard for one <see cref="ScoreSegment"/> (comparisons never cross it).</summary>
public sealed record Leaderboard(ScoreSegment Segment, IReadOnlyList<LeaderboardCell> Cells)
{
    /// <summary>The kind of work this board covers, from <see cref="Segment"/>.</summary>
    public string TaskClass => Segment.TaskClass;

    /// <summary>The score schema version this board covers, from <see cref="Segment"/>.</summary>
    public string SchemaVersion => Segment.SchemaVersion;

    public LeaderboardCell? Cell(LeaderboardFacet facet, string label)
        => Cells.FirstOrDefault(c => c.Facet == facet && string.Equals(c.Label, label, StringComparison.Ordinal));
}

/// <summary>
/// Composes the harness / model / harness-model leaderboard within one task class and score schema
/// version (spec US-14, rules 10-11). A facet cell is Comparable only with a cohort of at least the
/// minimum (default 5) AND more than one distinct operator (a single-operator cell is a privacy proxy
/// for one human - US-10); comparable cells rank by median Weave. Deterministic and non-identifying.
/// </summary>
public sealed class LeaderboardComposer
{
    public Leaderboard Compose(IReadOnlyList<ScoredEpisode> episodes, ScoreSegment segment, int cohortMinimum = 5)
    {
        ArgumentNullException.ThrowIfNull(episodes);
        ArgumentNullException.ThrowIfNull(segment);

        // A board for an incomparable segment is a board of a cohort that does not exist. Returning
        // it empty is the honest answer: no cell, therefore no rank, rather than a rank derived from
        // episodes that were never alike (see ScoreSegment.IsComparable).
        if (!segment.IsComparable)
        {
            return new Leaderboard(segment, []);
        }

        // Segmentation (rule 10): never compare across workspace, task class, or score schema version.
        // One value equality, because the segment is one value.
        var scoped = episodes.Where(e => e.IsScoreable && e.Segment == segment).ToList();

        var cells = new List<LeaderboardCell>();
        cells.AddRange(FacetCells(scoped, LeaderboardFacet.Harness, e => e.Harness, cohortMinimum));
        cells.AddRange(FacetCells(scoped, LeaderboardFacet.Model, e => e.Model, cohortMinimum));
        cells.AddRange(FacetCells(scoped, LeaderboardFacet.HarnessModel,
            e => e.Harness is null || e.Model is null ? null : $"{e.Harness} / {e.Model}", cohortMinimum));

        return new Leaderboard(segment, cells);
    }

    private static IEnumerable<LeaderboardCell> FacetCells(
        IReadOnlyList<ScoredEpisode> episodes, LeaderboardFacet facet, Func<ScoredEpisode, string?> label, int cohortMinimum)
    {
        var groups = episodes
            .Select(e => (Label: label(e), Episode: e))
            .Where(x => x.Label is not null)
            .GroupBy(x => x.Label!, x => x.Episode, StringComparer.Ordinal)
            .Select(g =>
            {
                var members = g.ToList();
                var cohort = members.Count;
                var operators = members.Select(m => m.OperatorId).Distinct(StringComparer.Ordinal).Count();

                string? reason = null;
                if (cohort < cohortMinimum)
                {
                    reason = $"cohort {cohort} < {cohortMinimum}";
                }
                else if (operators < 2)
                {
                    reason = "single operator (privacy-protected small cohort)";
                }

                var comparable = reason is null;
                return new LeaderboardCell(
                    facet, g.Key, cohort,
                    comparable ? Median(members.Select(m => m.Weave)) : null,
                    comparable ? Median(members.Where(m => m.CoverageRatio is not null).Select(m => m.CoverageRatio!.Value)) : null,
                    Rank: null,
                    comparable,
                    reason)
                {
                    DefaultedClass = members.Count(m => string.Equals(m.TaskClassSource, TaskClasses.Sources.SessionDefault, StringComparison.Ordinal)),
                    ChosenClass = members.Count(m => string.Equals(m.TaskClassSource, TaskClasses.Sources.Operator, StringComparison.Ordinal)),
                };
            })
            .ToList();

        // Rank the comparable cells within this facet by median Weave, best first.
        var ranked = groups.Where(c => c.Comparable)
            .OrderByDescending(c => c.MedianWeave)
            .ThenBy(c => c.Label, StringComparer.Ordinal)
            .Select((c, i) => c with { Rank = i + 1 });

        var notComparable = groups.Where(c => !c.Comparable);
        return ranked.Concat(notComparable);
    }

    private static double? Median(IEnumerable<double> values)
    {
        var sorted = values.OrderBy(v => v).ToList();
        if (sorted.Count == 0)
        {
            return null;
        }

        var mid = sorted.Count / 2;
        return sorted.Count % 2 == 1 ? sorted[mid] : (sorted[mid - 1] + sorted[mid]) / 2.0;
    }
}

/// <summary>One evidence-backed reason for one dimension (spec US-16 - one reason per dimension).</summary>
public sealed record DimensionReason(ScoreDimension Dimension, string Reason);

/// <summary>
/// An agent's per-turn standing (spec US-16). It carries the harness-model rank, the recent trend, and
/// one evidence-backed reason per dimension - and <b>deliberately no single aggregate scalar</b> to
/// optimize (the anti-Goodhart stance: there is no <c>Score</c> field, only a relative rank, a trend
/// direction, and per-dimension evidence).
/// </summary>
/// <param name="Trend">
/// Signed movement in Weave points against the previous episode in the same cohort, or
/// <c>null</c> when there is no previous episode to move against.
/// </param>
/// <remarks>
/// <b>Trend is nullable, and that is the point.</b> It was <c>int</c>, so an agent's first scored
/// episode reported <b>0</b> — the same value as "you did not move" — in the one feature whose
/// purpose is telling an agent whether it is improving or regressing. The spec is explicit that
/// "every displayed evaluation or learning claim has evidence/confidence, or renders Not Recorded",
/// and no-history is exactly that case.
/// </remarks>
/// <param name="NotComparableReason">
/// Why no rank is shown, or <c>null</c> when one is. Present whenever <c>RankComparable</c> is false,
/// so the agent is never told only that it has no rank (DC-087).
/// </param>
public sealed record AgentStanding(
    string EpisodeId, string? Harness, string? Model,
    int? Rank, int? Cohort, int? Trend, bool RankComparable,
    IReadOnlyList<DimensionReason> Reasons,
    string? NotComparableReason = null);

/// <summary>
/// Turns a scored episode + the leaderboard into per-turn standing (spec US-16). The rank is shown only
/// when the harness-model cell is comparable (else RankComparable is false and only trend + reasons
/// render); the reasons are one per dimension from the scorecard; no single optimizable number is exposed.
/// </summary>
public sealed class StandingComposer
{
    /// <summary>
    /// Composes one episode's standing, deriving the trend from <paramref name="history"/>.
    /// </summary>
    /// <remarks>
    /// <b>The history is a parameter, not the trend.</b> This took <c>int trend</c> and nothing in
    /// src/ produced one — the caller was expected to compute it and there was no caller at all. A
    /// value someone must remember to supply is a value that will eventually be supplied wrongly or
    /// not at all; a history the method derives from cannot be forgotten, because the method cannot
    /// be called without it.
    /// </remarks>
    public AgentStanding Compose(
        ScoredEpisode subject, Leaderboard board, IReadOnlyList<ScoredEpisode> history)
    {
        ArgumentNullException.ThrowIfNull(subject);
        ArgumentNullException.ThrowIfNull(board);
        ArgumentNullException.ThrowIfNull(history);

        // No trend within an incomparable segment: two episodes that merely both lack a workspace or
        // a task class are not the same cohort, and a movement derived from them would read as
        // improvement. Null here means "nothing to compare against", which is what is true.
        var trend = subject.Segment.IsComparable ? TrendFor(subject, history) : null;

        LeaderboardCell? cell = subject.Harness is not null && subject.Model is not null
            ? board.Cell(LeaderboardFacet.HarnessModel, $"{subject.Harness} / {subject.Model}")
            : null;

        var comparable = cell is { Comparable: true };
        var reasons = subject.Scorecard.Assessments
            .Select(a => new DimensionReason(a.Dimension, a.Rationale))
            .ToList();

        // The cause, in the order it becomes decidable: the segment is not a cohort at all; or it is,
        // but this episode has no harness/model to place in a facet; or it has one and the cell itself
        // is protected (too small, or a single operator).
        var notComparable = comparable
            ? null
            : subject.Segment.IncomparableReason
                ?? (cell is null
                    ? "no harness and model were recorded for this session, so there is no facet to rank in"
                    : cell.NotComparableReason);

        return new AgentStanding(
            subject.EpisodeId, subject.Harness, subject.Model,
            comparable ? cell!.Rank : null,
            comparable ? cell!.Cohort : null,
            trend,
            comparable,
            reasons,
            notComparable);
    }

    /// <summary>
    /// Movement in Weave points against the previous episode of the same cohort, or null.
    /// </summary>
    /// <remarks>
    /// <para><b>The cohort is harness + model + the score segment</b> - the same partition the
    /// leaderboard compares within (rule 11). A trend across task classes would compare a refactor
    /// against a spike and call the difference improvement.</para>
    ///
    /// <para><b>Null when there is no previous episode</b>, never zero. Zero means "scored the same";
    /// absent means "there is nothing to compare against yet", and an agent reading its first
    /// standing must be able to tell those apart.</para>
    ///
    /// <para>Ordered by <c>EvaluatedAt</c> and filtered to episodes strictly before the subject's,
    /// so a re-scored or backfilled episode does not become its own predecessor.</para>
    /// </remarks>
    private static int? TrendFor(ScoredEpisode subject, IReadOnlyList<ScoredEpisode> history)
    {
        var previous = history
            .Where(e => !string.Equals(e.EpisodeId, subject.EpisodeId, StringComparison.Ordinal))
            .Where(e => string.Equals(e.Harness, subject.Harness, StringComparison.Ordinal)
                && string.Equals(e.Model, subject.Model, StringComparison.Ordinal)
                && e.Segment == subject.Segment)
            .Where(e => e.Scorecard.EvaluatedAt <= subject.Scorecard.EvaluatedAt)
            .OrderByDescending(e => e.Scorecard.EvaluatedAt)
            .ThenByDescending(e => e.EpisodeId, StringComparer.Ordinal)
            .FirstOrDefault();

        return previous is null ? null : (int)Math.Round(subject.Weave - previous.Weave);
    }
}
