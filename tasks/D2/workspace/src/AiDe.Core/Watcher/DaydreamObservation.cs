namespace AiDe.Core.Watcher;

/// <summary>
/// What makes two episodes "the same thing happening again" (spec US-9).
/// </summary>
/// <remarks>
/// <para><b>Derived from the recorded scorecard, not from the scorer's inputs.</b>
/// <see cref="DeterministicEpisodeSignals"/> is never persisted — only <see cref="ScoredEpisode"/>
/// is (<c>RecordScorecard</c>). So a signature computed from the raw signals could be produced once,
/// live, and never again from the store. Daydream observes what was <i>recorded</i>.</para>
///
/// <para><b>Typed values only, never prose.</b> The verdict, the tripped floors, and each
/// dimension's 0–4 rubric. Deliberately <b>not</b> <c>Rationale</c> or <c>Headline</c>, which are
/// generated sentences: keying on them would make a wording change look like a new pattern, and it
/// would put the scorer's phrasing on the path between an agent and a proposed lesson. The scorer's
/// injection invariance is inherited here rather than re-earned — board text cannot reach a
/// signature because no text can.</para>
///
/// <para><b>Attribution is excluded on purpose.</b> Harness, model and operator are not part of the
/// signature. A pattern is a property of the <i>work</i>, and including them would produce claims of
/// the form "this harness tends to…" — a comparison the leaderboard already makes under cohort and
/// single-operator protections that a Daydream candidate would bypass entirely (US-10).</para>
///
/// <para><b>Task class segments.</b> Two episodes in different task classes are not the same
/// pattern, for the same reason the leaderboard never ranks across one.</para>
/// </remarks>
public sealed record DaydreamSignature(
    string TaskClass,
    string SchemaVersion,
    WeaveVerdict Verdict,
    string Floors,
    string Shortfalls)
{
    /// <summary>
    /// Derives the signature of one scored episode.
    /// </summary>
    /// <remarks>
    /// <paramref name="lowRubricThreshold"/> is what counts as a shortfall. A dimension scoring at
    /// or below it is part of what makes this episode recognisable; one scoring above it is the
    /// system working and is not a pattern worth proposing a lesson about.
    /// </remarks>
    public static DaydreamSignature For(ScoredEpisode episode, int lowRubricThreshold = 2)
    {
        ArgumentNullException.ThrowIfNull(episode);

        var card = episode.Scorecard;

        // Ordered, so two episodes with the same floors in a different order are one pattern.
        var floors = string.Join("+", card.TrippedFloors.Select(f => f.ToString()).Order(StringComparer.Ordinal));

        // Only the dimensions that fell short, and only their rubric — never the rationale.
        // A NotRecorded dimension (advisory, or no signal) is absent rather than counted as zero,
        // for the same reason the scorecard reports it that way.
        var shortfalls = string.Join("+", card.Assessments
            .Where(a => a.Rubric0to4 is not null && a.Rubric0to4 <= lowRubricThreshold)
            .Select(a => a.Dimension + ":" + a.Rubric0to4)
            .Order(StringComparer.Ordinal));

        return new DaydreamSignature(
            episode.TaskClass, episode.SchemaVersion, card.Verdict, floors, shortfalls);
    }

    /// <summary>True when nothing fell short and no floor tripped — a clean episode.</summary>
    /// <remarks>
    /// A clean episode is not a pattern to learn from. Observing them would fill the register with
    /// "work went well", which is true, recurrent, and useless as a lesson.
    /// </remarks>
    public bool IsUnremarkable => Floors.Length == 0 && Shortfalls.Length == 0;
}

/// <summary>
/// One observed occurrence of one candidate pattern in one Work Episode at one observation time
/// (the spec's grain table, <c>Daydream Observation</c> row — the declared grain).
/// </summary>
/// <remarks>
/// Append-only. An observation is never edited; a re-observation of the same episode is a new row
/// and the fold deduplicates by episode, so replay is deterministic and a correction is a
/// superseding fact rather than a rewrite.
/// </remarks>
public sealed record DaydreamObservation(
    string ObservationId,
    DaydreamSignature Signature,
    string EpisodeId,
    DateTimeOffset ObservedAt);

/// <summary>
/// A pattern seen more than once, with the episodes that evidence it.
/// </summary>
/// <remarks>
/// <see cref="DistinctEpisodes"/> rather than a raw count: the same episode observed twice is one
/// occurrence. Without that, a re-scan of the store would manufacture recurrence out of nothing —
/// which is the cheapest possible way to produce a confident lesson from a single event.
/// </remarks>
public sealed record DaydreamRecurrence(
    DaydreamSignature Signature,
    IReadOnlyList<string> EpisodeIds)
{
    public int DistinctEpisodes => EpisodeIds.Count;
}

/// <summary>
/// Groups observations into recurrences. Pure: no store, no clock, no I/O.
/// </summary>
/// <remarks>
/// <para><b>The threshold is a declared safety floor, not a tuned number.</b> Two distinct episodes
/// is the minimum at which "again" is meaningful, and US-9's first acceptance criterion is that one
/// occurrence stays an Observation and is <b>not</b> generalised. Its statistical basis is
/// <b>not recorded</b>: no power analysis has been done, and this is stated rather than implied so
/// that raising it later is a decision with evidence rather than a correction of a guess. It may
/// tighten; it must never silently relax.</para>
/// </remarks>
public sealed class RecurrenceDetector(int minimumDistinctEpisodes = 2)
{
    private readonly int _minimum = minimumDistinctEpisodes >= 2
        ? minimumDistinctEpisodes
        : throw new ArgumentOutOfRangeException(
            nameof(minimumDistinctEpisodes),
            "A recurrence needs at least two distinct episodes; one occurrence is an Observation (US-9).");

    /// <summary>The patterns that recur, ordered deterministically for replay.</summary>
    public IReadOnlyList<DaydreamRecurrence> Recurring(IEnumerable<DaydreamObservation> observations)
    {
        ArgumentNullException.ThrowIfNull(observations);

        return [.. observations
            .Where(o => !o.Signature.IsUnremarkable)
            .GroupBy(o => o.Signature)
            .Select(g => new DaydreamRecurrence(
                g.Key,
                [.. g.Select(o => o.EpisodeId).Distinct(StringComparer.Ordinal).Order(StringComparer.Ordinal)]))
            .Where(r => r.DistinctEpisodes >= _minimum)
            .OrderByDescending(r => r.DistinctEpisodes)
            .ThenBy(r => r.Signature.ToString(), StringComparer.Ordinal)];
    }
}
