using System.Text.Json.Nodes;
using AiDe.Core.AgentPlane;

namespace AiDe.Core.PromptCompilation;

/// <summary>
/// One event on one envelope — the stored fact of the Prompt Compilation bounded context
/// (spec Addendum D §A6; ADR-0034). Five kinds: <c>opened · decorated · called · submitted · consumed</c>.
/// </summary>
/// <remarks>
/// <para><b>The grain (DM8):</b> one row in <c>envelope-events.jsonl</c> is exactly one event on one
/// envelope, identified by <c>(envelope_id, seq)</c>, recorded when the event occurs. <see cref="Seq"/>
/// and <see cref="At"/> are assigned by the writer at <c>Append</c> (<see cref="EnvelopeStore"/>), or
/// by <see cref="Envelope.Pending"/> for the live, in-memory pre-compile that persists nothing; a
/// caller that supplies a <see cref="Seq"/> of its own is checked against the envelope's last, never
/// trusted.</para>
///
/// <para><b>Immutable by construction.</b> A record is never mutated or removed; a later event
/// supersedes an earlier one by <c>seq</c> (the fold's <see cref="Envelope.Current"/>). The pattern
/// is <i>Event Store</i> (the envelope is the fold), named as ADR-0034's LOA mapping names it.</para>
/// </remarks>
public abstract record EnvelopeEvent(string EnvelopeId)
{
    /// <summary>The event's kind — one of <see cref="EnvelopeEventKinds"/>.</summary>
    public abstract string Kind { get; }

    /// <summary>Per-envelope ordinal, strictly increasing; 0 until the writer assigns it.</summary>
    public int Seq { get; init; }

    /// <summary>When the event was recorded — the append is the moment; null until then.</summary>
    public DateTimeOffset? At { get; init; }
}

/// <summary>The five kinds, as the row's <c>kind</c> member spells them.</summary>
public static class EnvelopeEventKinds
{
    public const string Opened = "opened";
    public const string Decorated = "decorated";
    public const string Called = "called";
    public const string Submitted = "submitted";
    public const string Consumed = "consumed";
}

/// <summary>The rule's constants an <c>opened</c> row pins so a change never rewrites history (§A12.4, IO7).</summary>
/// <param name="K">How many prior submitted envelopes the history window admits.</param>
/// <param name="ByteBound">The window's total byte bound.</param>
/// <param name="BoundMs">The agentic compile's per-call bound.</param>
public sealed record CompileConstants(int K, int ByteBound, int BoundMs);

/// <summary>
/// The envelope opened — by the Send gesture, on a draft with no fresh envelope (§A10.1).
/// </summary>
/// <param name="EnvelopeId">The envelope this opens.</param>
/// <param name="SourceText">What the operator typed, verbatim — <b>the only text lease derivation ever reads</b> (Ruling 66).</param>
/// <param name="SessionId">The session; must equal the store's directory segment (ADR-0034 rule 1).</param>
/// <param name="EngineId">The bound engine.</param>
/// <param name="CompileMode">The session's <c>compile_mode</c> at open — a provenance fact, never a compile-line string (E5).</param>
/// <param name="Supersedes">The abandoned envelope this one re-prepares after a text edit, or null.</param>
/// <param name="Constants">The rule's constants, keyed by the projector version.</param>
public sealed record Opened(
    string EnvelopeId,
    string SourceText,
    string SessionId,
    string EngineId,
    string CompileMode,
    string? Supersedes,
    CompileConstants Constants) : EnvelopeEvent(EnvelopeId)
{
    public override string Kind => EnvelopeEventKinds.Opened;
}

/// <summary>Who wrote a mechanical decoration's value — named on the row, so no compile-time default hides behind it (F-6).</summary>
/// <param name="Writer">The writer: <c>session.config</c>, <c>template</c>, <c>draft-held-values</c>.</param>
/// <param name="Id">The writer's own identity when it has one (a template id).</param>
/// <param name="Version">Its version, when it has one.</param>
public sealed record DecorationInput(string Writer, string? Id = null, string? Version = null);

/// <summary>A span a derived decoration cites — offsets are UTF-16 indices into the raw <c>opened.source_text</c> (§A8.3 (iii)).</summary>
public sealed record GroundedSpan(string Input, int Start, int End);

/// <summary>
/// One immutable, named, sourced claim about this turn (§A6): <c>{name, value, source}</c>.
/// </summary>
/// <param name="EnvelopeId">The envelope.</param>
/// <param name="Name">The decoration's name — a structure line, a snapshot, a ref, or the operator's tier / task class.</param>
/// <param name="Value">Its value, as JSON: a string for a structure line, an object or array for a ref or snapshot, null for <i>none</i>.</param>
/// <param name="Source">One of <see cref="DecorationSources"/>.</param>
public sealed record Decorated(string EnvelopeId, string Name, JsonNode? Value, string Source) : EnvelopeEvent(EnvelopeId)
{
    public override string Kind => EnvelopeEventKinds.Decorated;

    /// <summary>The writer(s) of a mechanical snapshot or a template-supplied line; null otherwise.</summary>
    public IReadOnlyList<DecorationInput>? Inputs { get; init; }

    /// <summary>The <c>called</c> row a derived decoration came from; null unless <see cref="Source"/> is <c>derived</c>.</summary>
    public int? CallSeq { get; init; }

    /// <summary>The model's self-reported confidence in [0, 1]; derived only.</summary>
    public double? Confidence { get; init; }

    /// <summary>The spans a derived decoration cites; derived only.</summary>
    public IReadOnlyList<GroundedSpan>? GroundedIn { get; init; }

    /// <summary>The history window's byte size; <c>history_window</c> only.</summary>
    public int? Bytes { get; init; }

    /// <summary>The value as a string, or null when it is absent or not a string (a blank reads as absent, as <c>SpawnContract.Validate</c> reads a field).</summary>
    public string? ValueAsString => Value is JsonValue v && v.TryGetValue<string>(out var s) ? s : null;
}

/// <summary>The provenance of a decoration — <c>source</c> is provenance, never precedence (§A6 Supersession).</summary>
public static class DecorationSources
{
    /// <summary>The pre-compile wrote it, deterministically.</summary>
    public const string Mechanical = "mechanical";

    /// <summary>The bound model proposed it, through the typed boundary (CV-3's rung).</summary>
    public const string Derived = "derived";

    /// <summary>The operator wrote or overrode it in Prepare, or typed it as a structure line — one spelling with the cohort column's (<see cref="Watcher.TaskClasses.Sources"/>).</summary>
    public const string Operator = Watcher.TaskClasses.Sources.Operator;

    /// <summary>The session's default, snapshotted for this prompt (the <c>task_class</c> row, Ruling 70) — one spelling with the cohort column's.</summary>
    public const string SessionDefault = Watcher.TaskClasses.Sources.SessionDefault;
}

/// <summary>The decoration names this slice writes or reads — one spelling each (DM7).</summary>
public static class DecorationNames
{
    public const string Goal = GoalBlockFields.GoalKey;
    public const string DoneWhen = GoalBlockFields.DoneWhenKey;
    public const string NotInScope = GoalBlockFields.NotInScopeKey;
    public const string Tier = GoalBlockFields.TierKey;
    public const string TaskClass = "task_class";
    public const string Ceilings = "ceilings";
    public const string FamilyProfile = "family_profile";
    public const string TemplateApplied = "template_applied";
    public const string Attachments = "attachments";
    public const string HistoryWindow = "history_window";
    public const string Constitution = "constitution";

    /// <summary>The operator's per-turn account choice (Ruling 105 (2)) — an <c>operator</c> row at Send; absent means the session's default account.</summary>
    public const string Account = "account";

    /// <summary>The three structure lines, in §14.3 order.</summary>
    public static readonly IReadOnlyList<string> StructureLines = [Goal, DoneWhen, NotInScope];

    /// <summary>
    /// Names an <c>operator</c> row may never carry (US-D1): the settings have one home, and a
    /// projection is never stored. Checked at <see cref="EnvelopeStore.Append"/>.
    /// </summary>
    public static readonly IReadOnlyList<string> NeverOperator =
        [Ceilings, "fan_out_effective", "fan_out_cap", "fan_out_ceiling", GoalBlockFields.BudgetKey, "shape", "engine", "model", "account", "compile_mode", HistoryWindow, Constitution, FamilyProfile, TemplateApplied, Attachments];
}

/// <summary>What the typed boundary dropped from one model output, by reason (§A8.3).</summary>
public sealed record DroppedCounts(int UnknownName, int AlreadySupplied, int Ungrounded, int MentionBearing, int TypeFail)
{
    public static readonly DroppedCounts None = new(0, 0, 0, 0, 0);

    public int Total => UnknownName + AlreadySupplied + Ungrounded + MentionBearing + TypeFail;
}

/// <summary>
/// One invocation of the bound model by the compile stage — the grain at which cost exists (§A6).
/// Written by the agentic rung (<c>ComposerSendGate.PrepareAsync</c> from a <c>CompileResult</c>).
/// </summary>
public sealed record Called(
    string EnvelopeId,
    string EngineId,
    string ModelConfigured,
    string ModelObserved,
    int? LatencyMs,
    RunEventCost? Cost,
    string Outcome,
    string? Reason,
    string InputsSha,
    string PromptSha,
    string ContractVersion,
    int PermissionRequests,
    int ToolCalls,
    DroppedCounts Dropped) : EnvelopeEvent(EnvelopeId)
{
    public override string Kind => EnvelopeEventKinds.Called;
}

/// <summary>The <c>called.outcome</c> vocabulary (§A10.2).</summary>
public static class CallOutcomes
{
    public const string Succeeded = "succeeded";
    public const string SucceededNoStructure = "succeeded_no_structure";
    public const string Suspect = "suspect";
    public const string Unavailable = "unavailable";
    public const string Refused = "refused";
    public const string TimedOut = "timed_out";
    public const string Malformed = "malformed";
    public const string Cancelled = "cancelled";

    /// <summary>
    /// A re-prepare with an unchanged <c>inputs_sha</c> after a success reused the stored derived
    /// decorations and made no request — a <c>called</c> row with a known-zero cost and
    /// <c>reason</c> naming <c>reused_from</c> (ADR-0035 rule 1: C3/C10's receipt exists for every
    /// envelope, and the eval de-duplicates by the originating call).
    /// </summary>
    public const string Reused = "reused";

    /// <summary>The outcomes <see cref="Envelope.EffectiveMode"/> counts as agentic.</summary>
    public static readonly IReadOnlyList<string> Agentic = [Succeeded, SucceededNoStructure, Suspect, Reused];
}

/// <summary>
/// The Send gesture's confirmation: accepted, or refused with a code — at most one <b>accepted</b>
/// <c>submitted</c> per envelope (US-D6/US-D7).
/// </summary>
/// <param name="TextSha256">sha256 of the sent bytes — C15's witness.</param>
/// <param name="ProjectionSha">The rebuild's oracle over the projection's domain (§A12.2; ADR-0033 rule 2).</param>
/// <param name="ProjectorVersion">The version of <c>Project()</c> that computed the sha.</param>
public sealed record Submitted(
    string EnvelopeId,
    bool Accepted,
    string? Refusal,
    string TextSha256,
    string ProjectionSha,
    string ProjectorVersion) : EnvelopeEvent(EnvelopeId)
{
    public override string Kind => EnvelopeEventKinds.Submitted;
}

/// <summary>The run consumed the envelope: the pair <c>(outcome, reason)</c> (E6), by identity only.</summary>
/// <param name="Outcome">The episode's <c>EpisodeOutcome</c> word, or <see cref="Envelope.NotRecorded"/>.</param>
/// <param name="Reason">A stable code — <see cref="ConsumedReasons"/>.</param>
public sealed record Consumed(
    string EnvelopeId,
    string RunId,
    string? EpisodeId,
    string Outcome,
    string Reason) : EnvelopeEvent(EnvelopeId)
{
    public override string Kind => EnvelopeEventKinds.Consumed;
}

/// <summary>The <c>consumed.reason</c> codes (E6).</summary>
public static class ConsumedReasons
{
    public const string Completed = "completed";
    public const string StoppedByOperator = "stopped_by_operator";
    public const string DocumentClosed = "document_closed";

    /// <summary>A queued turn the operator cancelled before it was sent (Ruling 95): submitted, never run.</summary>
    public const string CancelledByOperator = "cancelled_by_operator";

    /// <summary><c>lane_exited{code}</c>, rendered with the exit code — or <c>lane_exited</c> alone when none was recorded.</summary>
    public static string LaneExited(int? code) => code is { } c
        ? string.Create(System.Globalization.CultureInfo.InvariantCulture, $"lane_exited{{{c}}}")
        : "lane_exited";
}
