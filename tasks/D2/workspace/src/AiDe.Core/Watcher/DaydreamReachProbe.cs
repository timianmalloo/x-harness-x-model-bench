namespace AiDe.Core.Watcher;

/// <summary>
/// What Daydream actually reached, over the episodes the product has scored.
/// </summary>
/// <remarks>
/// <para>Counts, and one finding derived from them. Nothing here is stored: every number folds from
/// the scorecards and the repository record on read, because two definitions of one quantity is a
/// defect signature (DM7).</para>
/// </remarks>
public sealed record DaydreamReach(
    int EpisodesScored,
    int WouldRecord,
    int NothingWentWrong,
    int NothingWasAssessed,
    int ObservationsInRecord,
    string? RecordUnavailable)
{
    /// <summary>Nothing has been scored, so there is nothing to say about what Daydream saw.</summary>
    /// <remarks>
    /// Distinct from every other state below. A repository nobody has scored in is not a repository
    /// with an instrumentation gap, and reporting it as one would make the gap meaningless on the
    /// day it is real.
    /// </remarks>
    public bool NothingScoredYet => EpisodesScored == 0;

    /// <summary>
    /// Every scored episode was declined for want of anything to assess.
    /// </summary>
    /// <remarks>
    /// <b>The finding this probe exists for.</b> Daydream is not quiet because the work is clean —
    /// it is quiet because nothing it can key on was ever observed, and it will stay quiet for every
    /// future episode of the same kind. Without this the surface reports "no patterns observed yet",
    /// which is true and reads as reassurance (DC-025).
    /// </remarks>
    public bool Deaf => EpisodesScored > 0 && WouldRecord == 0 && NothingWasAssessed > 0;

    /// <summary>
    /// Observations the classification expected that the record does not hold.
    /// </summary>
    /// <remarks>
    /// The independent half. Comparing what the writer <i>reported</i> doing against what it did
    /// would be self-referential — <c>FreshnessProber</c> was built because a staleness metric
    /// measured against the daemon's own last event, so a dead watcher read as perfectly fresh.
    /// This compares a classification of the store against the file on disk, which are two sources.
    /// </remarks>
    public int Missing => Math.Max(0, WouldRecord - ObservationsInRecord);

    /// <summary>
    /// Observations the record holds that this store cannot account for.
    /// </summary>
    /// <remarks>
    /// <para><b>Found because clamping <see cref="Missing"/> at zero was uncovered by mutation.</b>
    /// Removing the clamp reddened nothing, which said the negative case had never been thought
    /// about — and it is not an impossible state. It is the <i>normal</i> one for a fresh clone: the
    /// Daydream record is committed and travels with the repository, while the scorecards live in a
    /// per-workspace store that starts empty. Retention deletion produces it too.</para>
    ///
    /// <para><b>Deliberately not a finding.</b> It fires for every clone, and a warning that fires
    /// for everyone warns no one. It is exposed as a count because clamping it away was the same
    /// mistake this probe exists to correct — a state folded into "fine" because nobody named
    /// it.</para>
    /// </remarks>
    public int Unaccounted => Math.Max(0, ObservationsInRecord - WouldRecord);

    /// <summary>
    /// One sentence for an operator, or <c>null</c> when there is nothing to report.
    /// </summary>
    /// <remarks>
    /// Ordered by what a reader must act on first: a record it cannot write beats a gap in what it
    /// would write, which beats an absence of evidence. Each names only what was counted.
    /// </remarks>
    public string? Finding =>
        RecordUnavailable is { Length: > 0 } why ? why
        : Missing > 0
            ? $"{Missing} of {WouldRecord} pattern(s) are missing from the record — it was not written."
        : Deaf
            ? $"{EpisodesScored} episode(s) scored and none carried anything to assess — "
              + "Daydream cannot see this work, which is an instrumentation gap rather than a quiet repository."
        : NothingWasAssessed > 0 && EpisodesScored > 0
            ? $"{NothingWasAssessed} of {EpisodesScored} scored episode(s) carried nothing to assess."
        : null;
}

/// <summary>
/// Answers the operator question the Daydream design named: <i>is Daydream seeing anything?</i>
/// </summary>
/// <remarks>
/// <para><b>Why a probe and not a counter.</b> The obvious build is to tally
/// <see cref="DaydreamObservationOutcome"/> as <see cref="DaydreamRecorder.Observe"/> returns them.
/// That fails twice: the shell constructs a fresh recorder per scoring pass so nothing accumulates,
/// and — more importantly — a tally is the writer reporting on itself. <c>FreshnessProber</c> exists
/// because exactly that shape let a dead watcher read as perfectly fresh. This derives the expected
/// answer from the <b>store's scorecards</b> and compares it against the <b>file on disk</b>: two
/// sources, neither of them the writer.</para>
///
/// <para><b>It shares the writer's judgement rather than copying it.</b>
/// <see cref="DaydreamRecorder.DeclineReason"/> is the single definition of what gets declined and
/// why. A probe with its own copy would drift, and it would drift into reporting the wrong
/// silence.</para>
///
/// <para><b>A silence is not a finding on its own.</b> Nothing scored yet, everything clean, and
/// nothing assessable are three different states that all produce an empty Daydream, and only the
/// last is a gap. Collapsing them is DC-025 — which is the defect this whole vertical was corrected
/// for once already.</para>
/// </remarks>
public sealed class DaydreamReachProbe(
    IWatcherObservationStore store,
    DaydreamRepositoryRecord record,
    int lowRubricThreshold = 2)
{
    private readonly IWatcherObservationStore _store = store ?? throw new ArgumentNullException(nameof(store));
    private readonly DaydreamRepositoryRecord _record = record ?? throw new ArgumentNullException(nameof(record));

    /// <summary>Classifies every scored episode and compares the result with the record.</summary>
    public DaydreamReach Probe()
    {
        var scored = _store.AllScoredEpisodes();

        var wouldRecord = 0;
        var clean = 0;
        var unassessed = 0;

        foreach (var episode in scored)
        {
            var signature = DaydreamSignature.For(episode, lowRubricThreshold);
            switch (DaydreamRecorder.DeclineReason(episode, signature))
            {
                case null:
                    wouldRecord++;
                    break;
                case DaydreamObservationOutcome.NothingWentWrong:
                    clean++;
                    break;
                case DaydreamObservationOutcome.NothingWasAssessed:
                    unassessed++;
                    break;
            }
        }

        // Distinct episodes, not rows: a re-scored episode is one observation and a union merge can
        // legitimately hold it twice, so counting rows would manufacture a surplus and hide a
        // shortfall behind it.
        var observed = _record.Available
            ? _record.Read().Observations.Select(o => o.EpisodeId).Distinct(StringComparer.Ordinal).Count()
            : 0;

        return new DaydreamReach(
            scored.Count, wouldRecord, clean, unassessed, observed, _record.Unavailable);
    }
}
