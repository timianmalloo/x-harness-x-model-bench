namespace AiDe.Core.Watcher;

/// <summary>
/// The optional, explicit deterministic signals an instrumented AI-Forward turn may record on its audit
/// entry (a <c>signals</c> object - the watcher telemetry convention). Every field is nullable by design:
/// a harness emits only what it actually observed, and the watcher falls back to a conservative default for
/// anything absent - never a fabricated value (spec L127, NG1). This is the reader-side data shape; the
/// writer half (audit-log.py emitting a <c>signals</c> object) is a future AI-Forward enhancement, so a
/// current entry simply omits it and scores conservatively. See
/// <c>docs/design/watcher-signals-telemetry.md</c>.
/// </summary>
public sealed record AuditSignals(
    bool? VerificationPath = null,
    bool? VerificationExecuted = null,
    bool? AcceptanceMet = null,
    bool? Regression = null,
    int? GuidanceRequired = null,
    int? GuidanceSatisfied = null,
    int? CoordinationRequired = null,
    int? CoordinationObserved = null);

/// <summary>
/// The observable audit-entry evidence a signal derivation grounds on (conn-10). At minimum a committed
/// Proof Pack artifact (a <c>docs/proof/</c> path); optionally the explicit <see cref="AuditSignals"/> an
/// instrumented turn recorded. Absent signals never fabricate a value - the deriver falls back to the
/// conservative default (spec L127, NG1).
/// </summary>
public sealed record EpisodeEvidence(bool HasProofPack, AuditSignals? Signals = null);

/// <summary>An imported closed Work Episode paired with the audit evidence a signal derivation needs.</summary>
public sealed record ImportedEpisode(WorkEpisode Episode, EpisodeEvidence Evidence);

/// <summary>
/// Derives a <see cref="DeterministicEpisodeSignals"/> for an imported closed episode from what is
/// <b>honestly observable</b> - a committed Proof Pack (the only verification signal an audit entry
/// carries), the declared close outcome, and any spans recorded after the close. Everything not observable
/// is a conservative default that the scorer renders as Not-Recorded or Not-Scored, never a fabricated
/// value: acceptance stays null (unknown, not "met"), regression false (not "no regression exists"),
/// guidance/coordination requirements 0 (those dimensions render Not-Recorded), coverage uncalibrated.
/// Pure and deterministic. See <c>docs/design/watcher-signals-derivation.md</c>.
/// </summary>
public static class DeterministicSignalsDeriver
{
    public static DeterministicEpisodeSignals Derive(
        WorkEpisode episode, EpisodeEvidence evidence, IWatcherObservationStore store)
    {
        ArgumentNullException.ThrowIfNull(episode);
        ArgumentNullException.ThrowIfNull(evidence);
        ArgumentNullException.ThrowIfNull(store);

        var s = evidence.Signals;

        // Verification: an explicit signal wins; else the one honest fallback is a committed Proof Pack. No
        // proof pack and no signal -> HasVerificationPath false -> the scorer renders Not-Scored, which is
        // correct. Every field below is "explicit signal ?? conservative default" - absent never fabricates.
        var verified = s?.VerificationPath ?? evidence.HasProofPack;
        var verificationExecuted = s?.VerificationExecuted ?? evidence.HasProofPack;

        // Work observed after the done condition (PACK-O drift). Endpoints are inclusive; imported episodes
        // typically have no spans in this store, so this is 0 - honest, never a wrong count.
        var actionsAfterDone = episode.ClosedAt is { } closed
            ? store.SpanCountInInterval(episode.SessionId, closed, DateTimeOffset.MaxValue)
            : 0;

        var guidanceRequired = s?.GuidanceRequired ?? 0;
        var guidanceSatisfied = s?.GuidanceSatisfied ?? 0;
        var coordinationRequired = s?.CoordinationRequired ?? 0;
        var coordinationObserved = s?.CoordinationObserved ?? 0;

        // Coverage is calibrated only when a turn recorded explicit required-signal totals; then the
        // observed/required pair is real. Absent any signal -> uncalibrated -> coverage renders Not-Recorded
        // (never a fake 100%/0%). The totals are the guidance + coordination requirements the turn declared.
        var requiredTotal = guidanceRequired + coordinationRequired;
        var observedTotal = guidanceSatisfied + coordinationObserved;
        var coverageCalibrated = s is not null && requiredTotal > 0;

        return new DeterministicEpisodeSignals(
            HasVerificationPath: verified,
            AcceptanceCriteriaMet: s?.AcceptanceMet,     // explicit only; absent stays null (unknown != false)
            RequiredVerificationExecuted: verificationExecuted,
            RegressionPresent: s?.Regression ?? false,   // none observed (not a claim that none exists)
            UnresolvedFloorBlockers: new HashSet<FloorDomain>(),
            ActionsAfterDoneCondition: actionsAfterDone,
            PrematureCompletion: false,                  // not observable from an audit entry alone
            RequiredGuidanceTriggers: guidanceRequired,  // 0 when absent -> GuidanceAdherence Not-Recorded
            SatisfiedGuidanceTriggers: guidanceSatisfied,
            RequiredCoordinationSignals: coordinationRequired, // 0 when absent -> CoordinationAndLearning Not-Recorded
            ObservedCoordinationSignals: coordinationObserved,
            CoverageCalibrated: coverageCalibrated,
            RequiredSignalTotal: requiredTotal,
            ObservedSignalTotal: observedTotal);
    }
}
