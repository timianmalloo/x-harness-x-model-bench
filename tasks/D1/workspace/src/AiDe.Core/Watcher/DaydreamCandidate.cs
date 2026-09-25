namespace AiDe.Core.Watcher;

/// <summary>
/// Where a Daydream item stands on the promotion staircase (spec §"Daydream item" state vocabulary).
/// </summary>
/// <remarks>
/// Every landing has something that can stop the climb, and each is an acceptance criterion of US-9
/// rather than a design preference:
/// <code>
/// Observation ──(recurrence)──> NeedsDisconfirm ──(check survived)──> Promotable
///                                     │                                    │
///                            (check refuted)                        (a human decides)
///                                     ▼                                    ▼
///                                Disconfirmed              Promoted · Deferred · Rejected
///                                                                          │
///                                                       (source corrected/deleted/contradicted)
///                                                                          ▼
///                                                                      Retracted
/// </code>
/// </remarks>
public enum DaydreamState
{
    /// <summary>Seen, not generalised. One occurrence never leaves here (US-9, first criterion).</summary>
    Observation,

    /// <summary>Recurs, and promotion is <b>disabled</b> until a disconfirming check is attached.</summary>
    NeedsDisconfirm,

    /// <summary>A completed check refuted it. Promotion stays blocked (US-9, fourth criterion).</summary>
    Disconfirmed,

    /// <summary>A check survived. Everything is in place except the human decision.</summary>
    Promotable,

    /// <summary>A human promoted it.</summary>
    Promoted,

    /// <summary>A human chose not to decide yet. Still a candidate.</summary>
    Deferred,

    /// <summary>A human rejected it, with a reason.</summary>
    Rejected,

    /// <summary>Its source was corrected, deleted or later contradicted (US-9, fifth criterion).</summary>
    Retracted,
}

/// <summary>What a completed disconfirming check found.</summary>
public enum DisconfirmingOutcome
{
    /// <summary>The check ran and the candidate survived it.</summary>
    Survived,

    /// <summary>The check reproduced counter-evidence or refuted the candidate.</summary>
    Refuted,
}

/// <summary>
/// The evidence a Candidate Lesson must carry before anyone may act on it (US-9, second criterion:
/// source episodes, confidence, counter-evidence, expected effect, and the disconfirming check).
/// </summary>
/// <remarks>
/// <para><b>Split into derived and authored, deliberately.</b> Source episodes and confidence are
/// computed from observations — the system knows them. Counter-evidence, expected effect and the
/// check are <b>authored</b>, and are null until someone supplies them. Nothing derives them,
/// because a generated "expected effect" is a guess wearing the costume of evidence.</para>
///
/// <para>A candidate missing any authored part is <see cref="DaydreamState.NeedsDisconfirm"/>, which
/// is a state and not a warning: promotion is unreachable from it rather than discouraged.</para>
/// </remarks>
public sealed record CandidateEvidence(
    IReadOnlyList<string> SourceEpisodes,
    string Confidence,
    string? CounterEvidence = null,
    string? ExpectedEffect = null,
    string? DisconfirmingCheck = null,
    DisconfirmingOutcome? CheckOutcome = null)
{
    /// <summary>True only when every authored part is present and the check has been run.</summary>
    public bool IsComplete =>
        !string.IsNullOrWhiteSpace(CounterEvidence)
        && !string.IsNullOrWhiteSpace(ExpectedEffect)
        && !string.IsNullOrWhiteSpace(DisconfirmingCheck)
        && CheckOutcome is not null;
}

/// <summary>
/// One append-only event in a candidate's life. The state is folded from these, never stored.
/// </summary>
/// <remarks>
/// <para>The same discipline as every other fact in this store: a correction is a superseding event,
/// so the history of what was believed — and when, and by whom — survives the correction. A stored
/// state would be a second definition of a quantity the events already determine (DM7).</para>
///
/// <para><see cref="Actor"/> is who caused it: the system for an observation or a threshold
/// crossing, and a named operator for anything requiring the human gate. It is recorded because
/// "who promoted this" is the first question anyone asks about a lesson they disagree with.</para>
/// </remarks>
public sealed record DaydreamEvent(
    string EventId,
    DaydreamSignature Signature,
    DaydreamEventKind Kind,
    string Actor,
    string? Detail,
    DisconfirmingOutcome? Outcome,
    DateTimeOffset At,
    long Sequence);

/// <summary>The kinds of thing that happen to a candidate.</summary>
public enum DaydreamEventKind
{
    /// <summary>Recurrence crossed the threshold; the pattern is now a candidate.</summary>
    Proposed,

    /// <summary>Counter-evidence, expected effect or a check was attached.</summary>
    EvidenceAttached,

    /// <summary>A disconfirming check completed, with an outcome.</summary>
    CheckCompleted,

    /// <summary>A human promoted it.</summary>
    Promoted,

    /// <summary>A human deferred it.</summary>
    Deferred,

    /// <summary>A human rejected it, with a reason.</summary>
    Rejected,

    /// <summary>Its source was corrected, deleted or contradicted.</summary>
    Retracted,
}

/// <summary>A candidate's current standing, folded from its events and its surviving evidence.</summary>
public sealed record DaydreamCandidate(
    DaydreamSignature Signature,
    DaydreamState State,
    CandidateEvidence Evidence,
    string? BlockedBecause)
{
    /// <summary>
    /// Whether a human may promote this now.
    /// </summary>
    /// <remarks>
    /// Read by the surface to decide whether a promote affordance exists <b>at all</b> — not whether
    /// it is enabled and shows an error on click. A control the user can press and be refused by
    /// teaches that the refusal is negotiable.
    /// </remarks>
    public bool CanPromote => State == DaydreamState.Promotable;
}

/// <summary>
/// Folds observations and candidate events into current standing. Pure: no store, no clock, no I/O.
/// </summary>
/// <remarks>
/// <para><b>Promotion is unreachable rather than refused.</b> There is no <c>Promote()</c> method
/// that validates and throws. A <c>Promoted</c> event on a candidate that was not
/// <see cref="DaydreamState.Promotable"/> does not move it — the guard is in the transition, so an
/// event written by any path, including a hand-edited store, cannot promote something unpromotable.
/// </para>
///
/// <para><b>Evidence can be withdrawn.</b> Fold order is observations first, then events: if
/// episodes disappear — retention, correction, a purged workspace — a candidate that no longer
/// recurs falls back to <see cref="DaydreamState.Observation"/> whatever its event history says.
/// A lesson outliving the evidence for it is the failure this ordering prevents.</para>
/// </remarks>
public sealed class DaydreamFold(int minimumDistinctEpisodes = 2)
{
    private readonly RecurrenceDetector _recurrence = new(minimumDistinctEpisodes);

    /// <summary>Every pattern currently known, with its standing.</summary>
    public IReadOnlyList<DaydreamCandidate> Fold(
        IEnumerable<DaydreamObservation> observations,
        IEnumerable<DaydreamEvent> events)
    {
        ArgumentNullException.ThrowIfNull(observations);
        ArgumentNullException.ThrowIfNull(events);

        var recurring = _recurrence.Recurring(observations)
            .ToDictionary(r => r.Signature, r => r.EpisodeIds);

        var bySignature = events
            .OrderBy(e => e.Sequence)
            .GroupBy(e => e.Signature);

        var results = new List<DaydreamCandidate>();
        var seen = new HashSet<DaydreamSignature>();

        foreach (var history in bySignature)
        {
            seen.Add(history.Key);
            results.Add(FoldOne(history.Key, recurring.GetValueOrDefault(history.Key), [.. history]));
        }

        // Patterns that recur but have no events yet: proposed by evidence alone.
        foreach (var (signature, episodes) in recurring.Where(r => !seen.Contains(r.Key)))
        {
            results.Add(FoldOne(signature, episodes, []));
        }

        return [.. results.OrderBy(c => c.Signature.ToString(), StringComparer.Ordinal)];
    }

    private static DaydreamCandidate FoldOne(
        DaydreamSignature signature,
        IReadOnlyList<string>? episodes,
        IReadOnlyList<DaydreamEvent> history)
    {
        var sources = episodes ?? [];

        // Evidence first. A candidate whose episodes are gone is not a candidate, whatever was
        // decided about it before — the decision was made about evidence that no longer exists.
        if (sources.Count == 0)
        {
            return new DaydreamCandidate(
                signature, DaydreamState.Observation,
                new CandidateEvidence([], ConfidenceFor(0)),
                "The evidence for this pattern is no longer present.");
        }

        var evidence = new CandidateEvidence(sources, ConfidenceFor(sources.Count));
        var state = DaydreamState.NeedsDisconfirm;
        string? blocked = "No disconfirming check has been attached.";

        foreach (var e in history)
        {
            switch (e.Kind)
            {
                case DaydreamEventKind.EvidenceAttached:
                    evidence = Attach(evidence, e.Detail);
                    break;

                case DaydreamEventKind.CheckCompleted:
                    evidence = evidence with { CheckOutcome = e.Outcome };
                    break;

                case DaydreamEventKind.Promoted when state == DaydreamState.Promotable:
                    state = DaydreamState.Promoted;
                    blocked = null;
                    break;

                case DaydreamEventKind.Deferred when state is DaydreamState.Promotable or DaydreamState.NeedsDisconfirm:
                    state = DaydreamState.Deferred;
                    break;

                case DaydreamEventKind.Rejected:
                    state = DaydreamState.Rejected;
                    blocked = e.Detail ?? "Rejected.";
                    break;

                case DaydreamEventKind.Retracted:
                    state = DaydreamState.Retracted;
                    blocked = e.Detail ?? "Retracted.";
                    break;
            }

            // Re-derive the gate after every event, so attaching a check moves the state and a
            // refuting one moves it back.
            //
            // A DEFERRAL is re-opened only by new evidence. "Defer" means "not deciding on this as
            // it stands" (spec review flow: defer → remain Candidate), so it must persist through
            // later events — otherwise the next unrelated event would silently undo a human's
            // choice. But it must NOT persist through a change to the thing they deferred on, or a
            // candidate could be parked once and never resurface however much evidence arrived.
            var evidenceChanged = e.Kind is DaydreamEventKind.EvidenceAttached or DaydreamEventKind.CheckCompleted;

            if (state is DaydreamState.NeedsDisconfirm or DaydreamState.Promotable or DaydreamState.Disconfirmed
                || (state == DaydreamState.Deferred && evidenceChanged))
            {
                (state, blocked) = Gate(evidence);
            }
        }

        if (history.Count == 0)
        {
            (state, blocked) = Gate(evidence);
        }

        return new DaydreamCandidate(signature, state, evidence, blocked);
    }

    /// <summary>
    /// The gate US-9's third and fourth criteria describe, in one place.
    /// </summary>
    /// <remarks>
    /// A refuted check is checked <b>before</b> completeness: a candidate the evidence refutes is
    /// Disconfirmed even if every other field is filled in, because the missing-field case and the
    /// refuted case are different answers and the refuted one is the more important.
    /// </remarks>
    private static (DaydreamState State, string? Blocked) Gate(CandidateEvidence evidence)
    {
        if (evidence.CheckOutcome == DisconfirmingOutcome.Refuted)
        {
            return (DaydreamState.Disconfirmed,
                "A completed disconfirming check refuted this candidate.");
        }

        if (!evidence.IsComplete)
        {
            return (DaydreamState.NeedsDisconfirm, MissingPart(evidence));
        }

        return (DaydreamState.Promotable, null);
    }

    private static string MissingPart(CandidateEvidence e) =>
        string.IsNullOrWhiteSpace(e.CounterEvidence) ? "No counter-evidence has been reviewed."
        : string.IsNullOrWhiteSpace(e.ExpectedEffect) ? "No expected effect has been stated."
        : string.IsNullOrWhiteSpace(e.DisconfirmingCheck) ? "No disconfirming check has been attached."
        : "The disconfirming check has not been run.";

    // "counter:…", "effect:…", "check:…" — a tagged detail rather than three event kinds, because
    // the three are the same act (a human supplying part of the evidence) at different times.
    private static CandidateEvidence Attach(CandidateEvidence evidence, string? detail) =>
        detail is null ? evidence
        : detail.StartsWith("counter:", StringComparison.Ordinal) ? evidence with { CounterEvidence = detail[8..] }
        : detail.StartsWith("effect:", StringComparison.Ordinal) ? evidence with { ExpectedEffect = detail[7..] }
        : detail.StartsWith("check:", StringComparison.Ordinal) ? evidence with { DisconfirmingCheck = detail[6..] }
        : evidence;

    /// <summary>
    /// A confidence label, from the pack's vocabulary rather than a number.
    /// </summary>
    /// <remarks>
    /// <b>Never "Verified".</b> A pattern seen many times is still an <i>observation</i> about
    /// outcomes, not a proven claim — only a surviving disconfirming check earns more than that, and
    /// that is expressed by the state rather than by relabelling the evidence. The thresholds are
    /// declared floors with no statistical basis recorded, exactly as the recurrence minimum is.
    /// </remarks>
    private static string ConfidenceFor(int distinctEpisodes) => distinctEpisodes switch
    {
        0 => "Not recorded",
        < 4 => "Inferred — few occurrences",
        _ => "Inferred — recurring",
    };
}
