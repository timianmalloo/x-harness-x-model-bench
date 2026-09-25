namespace AiDe.Core.PromptCompilation;

/// <summary>Stable error codes for the envelope store and the projections over it (the <c>CE-</c> family; O-standard: every failure carries one).</summary>
public static class EnvelopeStoreErrorCodes
{
    /// <summary>The session directory does not exist — the store never creates the Session aggregate's directory.</summary>
    public const string NoSessionDirectory = "CE-0001";

    /// <summary>Another writer holds the file (<c>FileShare.None</c>): a second AI-DE, or a composer while a reader asks.</summary>
    public const string HeldByAnotherWriter = "CE-0002";

    /// <summary>The chain is broken at line N; <c>Append</c> is refused for the life of this open.</summary>
    public const string StoreBroken = "CE-0003";

    /// <summary>An <c>opened</c> row's <c>session_id</c> differs from the directory segment.</summary>
    public const string SessionIdMismatch = "CE-0004";

    /// <summary>A supplied <c>seq</c> is not the envelope's next.</summary>
    public const string SeqNotIncreasing = "CE-0005";

    /// <summary>A <c>decorated</c> after an accepted <c>submitted</c>.</summary>
    public const string DecoratedAfterSubmitted = "CE-0006";

    /// <summary>A second accepted <c>submitted</c> on one envelope.</summary>
    public const string SubmittedTwice = "CE-0007";

    /// <summary>A second <c>consumed</c> on one envelope.</summary>
    public const string ConsumedTwice = "CE-0008";

    /// <summary>An attachment value carrying a <c>body</c> member — bodies are never persisted (§A13.5).</summary>
    public const string AttachmentBodyRefused = "CE-0009";

    /// <summary>A decoration named <c>lease</c> (DM-A), an <c>operator</c> row named a setting, or an unknown source.</summary>
    public const string DecorationNameRefused = "CE-0010";

    /// <summary>A <c>tier</c> row outside {T0, T1, T2} (§A9 R4's falsifier).</summary>
    public const string TierRefused = "CE-0011";

    /// <summary>An event on an envelope with no <c>opened</c> row, or a second <c>opened</c>.</summary>
    public const string NotOpened = "CE-0012";

    /// <summary>The append's write failed after a good open (disk full, an IO error) — the send proceeds degraded.</summary>
    public const string AppendFailed = "CE-0013";

    /// <summary>A purge was refused before any file was touched: a traversal, a non-segment id, a junction.</summary>
    public const string PurgeRefused = "CE-0014";

    /// <summary>A fold is incomplete for projection: no <c>opened</c> row, or no well-formed <c>ceilings</c> row.</summary>
    public const string ProjectionIncomplete = "CE-0015";

    /// <summary>Gate 1: the compile-pin-spike artifact is absent (or unreadable) — no agentic rung is selectable (ADR-0036; US-D11 b1).</summary>
    public const string PinArtifactMissing = "CE-0016";

    /// <summary>Gate 1: the artifact's recorded adapter/SDK/CLI triple is not the installed one — an adapter bump under a stale artifact.</summary>
    public const string PinTripleMismatch = "CE-0017";

    /// <summary>Gate 1: the artifact names no frame log, or the frame log is missing or does not hash to the recorded sha — the count cannot be recounted.</summary>
    public const string PinFrameLogUnverifiable = "CE-0018";

    /// <summary>Gate 1: the recount over the frame log is not zero — the pin did not hold on the recorded run.</summary>
    public const string PinRecountNotZero = "CE-0019";

    /// <summary>Gate 2: no admission report has been read — <c>agentic</c> is refused by name until CV-4's reader admits it.</summary>
    public const string AdmissionReportOutstanding = "CE-0020";

    /// <summary>A <c>compile_mode</c> word outside the three the ladder names.</summary>
    public const string CompileModeUnknown = "CE-0021";

    /// <summary>Gate 1: the artifact records a run that did not end (<c>mode</c> not <c>full</c>, or a prompt with no result) — an aborted or timed-out spike admits nothing.</summary>
    public const string PinRunNotEnded = "CE-0022";

    /// <summary>Gate 1: the artifact's <c>sent_meta_triple</c> is not the pin this build sends — a pin change re-runs PD-5 by construction.</summary>
    public const string PinIdentityMismatch = "CE-0023";

    /// <summary>Gate 2: the admission report exists but is not readable as the <c>compile-eval-admission/1</c> contract (bad JSON, wrong contract string, or a required shape missing) — CV-4's reader.</summary>
    public const string AdmissionReportUnreadable = "CE-0024";

    /// <summary>Gate 2: the split witness fails — fewer than 50 holdout envelopes, an id shared with the sample, or the holdout preceding the sample. The holdout is judged, never the sample.</summary>
    public const string AdmissionSplitInvalid = "CE-0025";

    /// <summary>Gate 2: the recomputed <c>schema_fail</c> rate over the holdout exceeds the fixed floor (2 %, §A14.4).</summary>
    public const string AdmissionFloorSchemaFail = "CE-0026";

    /// <summary>Gate 2: the recomputed <c>applied_denied</c> invariant is non-zero over every <c>called</c> row (§A14.4; unfiltered by <c>EffectiveMode</c>).</summary>
    public const string AdmissionFloorAppliedDenied = "CE-0027";

    /// <summary>Gate 2: the recomputed <c>tool_calls</c> invariant is non-zero over every <c>called</c> row (§A14.4; unfiltered by <c>EffectiveMode</c>).</summary>
    public const string AdmissionFloorToolCalls = "CE-0028";

    /// <summary>Gate 2: the recomputed degraded rate over every model call exceeds Ruling 76's floor (X = 5 %).</summary>
    public const string AdmissionFloorDegraded = "CE-0029";
}

/// <summary>A refusal by the envelope store, with its stable code (<see cref="EnvelopeStoreErrorCodes"/>).</summary>
public sealed class EnvelopeStoreException : Exception
{
    public EnvelopeStoreException(string code, string message, Exception? inner = null)
        : base($"[{code}] {message}", inner)
    {
        Code = code;
    }

    /// <summary>The stable code.</summary>
    public string Code { get; }
}
