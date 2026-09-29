using System.Text.Json.Nodes;
using AiDe.Core.AgentPlane;
using AiDe.Core.Watcher;

namespace AiDe.Core.Sessions;

/// <summary>
/// The user-facing container Addendum A3 defines: named, workspace-bound, and carrying
/// session-scoped config (Ruling 105: which <b>accounts</b> this session may bill, and its default).
/// R14 b2: "session" in this namespace names only this container — never a Watcher/Dispatch/
/// Terminal-internal concept.
/// </summary>
/// <param name="SessionId">This session's id — see <see cref="Sessions.SessionId"/>.</param>
/// <param name="Name">Operator-facing name (A4.3: default is a date-slug, renameable later).</param>
/// <param name="WorkspaceId">The workspace this session is bound to. A session cannot exist unbound.</param>
/// <param name="CreatedAt">Stamped once, at <see cref="SessionConfigStore.Create"/>.</param>
/// <param name="Accounts">
/// The accounts selected for THIS session, by identity (provider, label) — Ruling 105 (1). The
/// engine is <b>derived</b> from the provider through <see cref="AgentPlane.EngineCatalog"/> and is
/// never stored here: two definitions of one mapping is a defect signature (DM7). Mutated only
/// through <see cref="SessionConfigStore.SetAccounts"/>, which applies to new turns only (clause 3)
/// — never in scope here: routing mode, autonomy, default policy, per-session MCP (Ruling 19).
/// </param>
/// <param name="DefaultAccount">
/// The account a turn bills when the operator picks none on the composer, or <c>null</c> — "no
/// default account — choose one" (a migrated session whose provider carried several; never a
/// guessed label). Changed only through <see cref="SessionConfigStore.SetDefaultAccount"/>, new
/// turns only: Type-2 by construction, no past turn's binding is rewritten (Ruling 105 condition 2).
/// </param>
public sealed record SessionConfig(
    string SessionId,
    string Name,
    string WorkspaceId,
    DateTimeOffset CreatedAt,
    IReadOnlyList<AccountRef> Accounts,
    AccountRef? DefaultAccount)
{
    /// <summary>
    /// The engine ids an old <c>session.json</c> carried as <c>EnabledBackends</c>, until
    /// <see cref="SessionConfigStore.MigrateLegacyBackends"/> maps them to accounts — empty on a
    /// migrated or new session. <b>Never serialized as a member of this record</b>: the store keeps
    /// the legacy key on disk verbatim until the migration succeeds (expand → migrate → contract), so
    /// a session read with no provider file loses nothing.
    /// </summary>
    [System.Text.Json.Serialization.JsonIgnore]
    public IReadOnlyList<string> LegacyEnabledBackends { get; init; } = [];

    /// <summary>
    /// Whether this session may attach files to a composed prompt (Security/Privacy <b>C21</b>).
    /// <b>Off by default</b>, confirmed by the human on 2026-09-10.
    /// </summary>
    /// <remarks>
    /// <para><b>It gates the attach path — not egress, not send, not paste.</b> Gating all model
    /// egress or the composer's send would disable the product's core function and be dishonest in a
    /// specific way: the agent CLI is a separate process the operator launches from a terminal
    /// anyway, so switching off this app's send does not stop the egress, it routes around it. Attach
    /// is the honest line because it is the only path that puts bytes into the prompt the operator
    /// did not type.</para>
    ///
    /// <para><b>An init-only property rather than a positional parameter</b> so a
    /// <c>session.json</c> written before this field existed still reads, and reads false — which is
    /// the safe state, not merely the convenient one.</para>
    ///
    /// <para><b>"Off" is distinguishable from "never asked" by the EXISTING event log, and no
    /// provenance field is added here.</b> False with no <c>session.config</c> event naming it is the
    /// shipped default; with one, an operator decided. The append-only log is already the record, and
    /// two definitions of one fact is a defect signature — so there is deliberately no
    /// <c>source</c> or <c>decidedAt</c> member on this type.</para>
    ///
    /// <para><b>Honest limit, stated here rather than discovered later.</b> This record is
    /// per-session and operator-writable, so this is <b>a default with a safe initial state, not an
    /// enforceable policy</b>. A deployment that must <i>prevent</i> attach needs a
    /// non-session-overridable layer, which is Phase 2 — named here as the upgrade trigger. Nothing
    /// may describe this field as restricting or preventing attach for a deployment.</para>
    /// </remarks>
    public bool AttachEnabled { get; init; }

    /// <summary>
    /// The most sub-agents any turn in this session may convene — <c>fan_out_ceiling</c> in
    /// ADR-0033 §3 / <c>docs/architecture.md</c>'s vocabulary (Ruling 56). The eventual
    /// <c>FanOutCap = min(cap(tier), ceiling)</c> the compile step computes reads this value; this
    /// record only carries it — nothing here derives or enforces a cap from it (that projection has
    /// no code home yet, per ADR-0033's own finding).
    /// </summary>
    /// <remarks>
    /// <para><b>Default is 2, and no workspace-default mechanism exists in code to source it from —
    /// checked, not assumed.</b> The architecture doc and the New Session sheet mockups both call
    /// this value a "workspace default" (<c>docs/architecture.md:786</c>;
    /// <c>docs/mockups/new-session-sheet.html</c>), but no <c>WorkspaceDefaults</c> type or
    /// workspace-level setting exists anywhere in <c>src/</c> today: this session-settings node is
    /// the first code home for the ceiling at all, and it has no workspace layer beneath it to read a
    /// default from. 2 is the nearest ruled number instead — CT19's own T1 fan-out cap
    /// (<c>communication-and-task-discipline.instructions.md</c>: "0 at T0, 2 at T1") — used here as
    /// a per-session default, not as evidence the workspace-default plumbing exists.</para>
    ///
    /// <para><b>An old <c>session.json</c> reads as 2, not as an error.</b> This field is additive,
    /// exactly like <see cref="AttachEnabled"/>: a file written before it existed has no key for it,
    /// and <see cref="SessionConfigStore.Load"/> must keep reading such a file.</para>
    /// </remarks>
    public int FanOutCeiling { get; init; } = DefaultFanOutCeiling;

    /// <summary>
    /// The ruled per-session default for <see cref="FanOutCeiling"/> — CT19's T1 cap, 2 — named
    /// once so the New Session sheet prefills what an unset file reads (derive, don't store; DM7).
    /// </summary>
    public const int DefaultFanOutCeiling = 2;

    /// <summary>
    /// An enforced request/token ceiling for this session, or <c>null</c> — the session is bounded by
    /// the subscription instead (Ruling 72; ADR-0033 §3's <c>budget_cap</c>).
    /// </summary>
    /// <remarks>
    /// <para><b>Absent by default, never a required number.</b> The operator's own words: "budgets
    /// should be max … by default and then optionally I can enforce a cap" (Ruling 72). <c>null</c>
    /// is the shipped default; a caller that needs an actual <see cref="RunBudget"/> for a spawn
    /// reads <see cref="RunBudget.SubscriptionBounded"/> when this is <c>null</c> — that substitution
    /// belongs to the projection that reads this setting, not to this record (derive, don't store;
    /// DM7), so it is not performed here.</para>
    ///
    /// <para><b>Reuses <see cref="RunBudget"/> rather than a second <c>(requests, tokens)</c>
    /// shape.</b> ADR-0033 §3 names the setting's shape as exactly <c>{requests, tokens} | none</c> —
    /// the same two fields <see cref="RunBudget"/> already carries — and two definitions of one
    /// quantity is a defect signature (DM7).</para>
    /// </remarks>
    public RunBudget? BudgetCap { get; init; }

    /// <summary>
    /// How much of the compile step's agentic stage this session admits (ADR-0033 §A10.1;
    /// Ruling 68) — one of <see cref="CompileModes"/>.
    /// </summary>
    /// <remarks>
    /// Default <see cref="CompileModes.MechanicalOnly"/> (Ruling 68): a session opens with only the
    /// free, in-memory, mechanical pre-compile; the two agentic rungs are opt-in as the eval gate
    /// admits them.
    /// </remarks>
    public string CompileMode { get; init; } = CompileModes.MechanicalOnly;

    /// <summary>
    /// The task class a prompt in this session carries when it declares none of its own (Ruling 70;
    /// Ruling 72; ADR-0033 §4) — <c>default_task_class</c> in the ADR's vocabulary.
    /// </summary>
    /// <remarks>
    /// <para><b>Which "TaskClass" this is, and which it is not.</b> <see cref="SessionConfig"/>
    /// carried no <c>TaskClass</c> member before this field — there is nothing here renamed or
    /// removed. Two other, unrelated members share the name and are untouched: <c>GovernedRunRequest
    /// .TaskClass</c> (F5's tree; the per-run, required, already-resolved value a governed run
    /// carries) and <see cref="ScoreSegment"/>'s <c>TaskClass</c> (what the Watcher reads back
    /// for scoring). This field is the session-level <b>default</b> that
    /// <c>ComposerSendContext.TaskClass</c> is populated from when a prompt names no class of its
    /// own (ADR-0033 §4: "the session config's <c>default_task_class</c> … never a second literal") —
    /// a different point in the pipeline from either.</para>
    ///
    /// <para>Default <see cref="TaskClasses.FreeForm"/> (Ruling 72): "the basic should be free-form
    /// upon open, and then I can change it" — an explicit, operator-visible value present from the
    /// moment a session opens, never a null a caller must special-case.</para>
    /// </remarks>
    public string DefaultTaskClass { get; init; } = TaskClasses.FreeForm;
}

/// <summary>
/// One account by identity — (provider, label) — as a session refers to it (Ruling 105 (1)). A
/// <b>reference</b>, never a copy: health, the observed auth label and the host live on the registry's
/// <see cref="AgentPlane.ProviderAccount"/>, read at bind time, so a session never carries a stale
/// health beside a label.
/// </summary>
/// <param name="Provider">The provider key in <c>~/.aide/providers.json</c> — <c>anthropic</c>, <c>openai</c>, <c>github</c>, <c>google</c>, <c>xai</c>.</param>
/// <param name="Label">The account label the operator configured.</param>
public sealed record AccountRef(string Provider, string Label)
{
    /// <summary>How the operator reads it: <c>provider · label</c>.</summary>
    public override string ToString() => $"{Provider} · {Label}";
}

/// <summary>
/// The <c>compile_mode</c> vocabulary a <see cref="SessionConfig"/> declares (ADR-0033 §A10.1;
/// Ruling 68) — mechanical always runs; the two agentic rungs are opt-in behind an eval gate.
/// </summary>
public static class CompileModes
{
    /// <summary>The default (Ruling 68): only the free, in-memory mechanical pre-compile runs.</summary>
    public const string MechanicalOnly = "mechanical-only";

    /// <summary>The agentic compile runs, but a `derived` decoration needs confirmation before Send.</summary>
    public const string AgenticAdvisory = "agentic-advisory";

    /// <summary>The agentic compile's result is admitted without a confirmation step.</summary>
    public const string Agentic = "agentic";
}

/// <summary>
/// The <c>kind</c> strings this slice adds to the open, unenumerated vocabulary
/// <see cref="AgentPlane.RunEvent.Kind"/> already accepts (clause 4). Defined here, in the
/// container's own namespace, rather than in <c>AgentPlane</c> — these are session-level events, not
/// run events, and F0 does not touch <c>AgentPlane.RunEvent</c> at all: proving it needs no change
/// IS the clause.
/// </summary>
public static class SessionEventKinds
{
    /// <summary>A session was created (<see cref="SessionConfigStore.Create"/>).</summary>
    public const string Open = "session.open";

    /// <summary>A session's config changed — accounts, the default account, attach, compile mode.</summary>
    public const string Config = "session.config";
}

/// <summary>
/// One line of a session's append-only <c>session-events.jsonl</c> (clause 3's "emit a session
/// event"). Deliberately its own small type rather than <see cref="AgentPlane.RunEvent"/>: a session
/// event has no run id and no agent id, so forcing it into that shape would mean populating fields
/// that do not apply. Clause 4's obligation — that the future run-event stream accepts
/// <see cref="SessionEventKinds"/> with no schema change — is proven directly against
/// <see cref="AgentPlane.RunEvent"/> in <c>SessionEventEnvelopeTests</c>, not by round-tripping this
/// type through it.
/// </summary>
/// <param name="Seq">Per-session monotonic ordinal, 1-based, assigned at append.</param>
/// <param name="Ts">Append time.</param>
/// <param name="Kind">A <see cref="SessionEventKinds"/> value.</param>
/// <param name="Body">The event payload — the resulting accounts, default account and toggles.</param>
public sealed record SessionEvent(long Seq, DateTimeOffset Ts, string Kind, JsonObject Body);

/// <summary>
/// How a session came to exist, as the <c>session.open</c> body records it (F5 clause 1).
/// </summary>
/// <remarks>
/// <para><b>On the event, never on <see cref="SessionConfig"/>.</b> Origin is a fact about one
/// moment — the creation — not a property of the container, and the append-only log is already the
/// record of what happened. Putting it on the record too would be two definitions of one fact, which
/// is the defect signature DM's "derive don't store" names.</para>
///
/// <para><b><see cref="Direct"/> is the default because the claim is about the OTHER value.</b>
/// "Started from File → New Session" is only checkable if something that did not start there reads
/// differently. A field that is always <see cref="MainMenuNewSession"/> would satisfy the sentence
/// and prove nothing — the exact "asserted-about" shape N7 was blocked for. So
/// <see cref="SessionConfigStore.Create"/> defaults to <see cref="Direct"/> and exactly one caller
/// in <c>src/</c> passes <see cref="MainMenuNewSession"/>.</para>
/// </remarks>
public static class SessionOrigins
{
    /// <summary>
    /// The <c>File → New Session</c> command path — <c>Ctrl+N</c> and the <c>MainMenuBuilder</c>
    /// entry, both of which resolve to <c>WorkbenchCommandCatalog</c>'s <c>session.new</c>.
    /// </summary>
    /// <remarks>
    /// <b>Passed at exactly one site in <c>src/</c></b>, <c>NewSessionSheetViewModel.Create</c> —
    /// the sheet that command opens, and the only production caller of
    /// <see cref="SessionConfigStore.Create"/>. <c>TheSessionOriginIsSetOnlyOnTheCommandPathTests</c>
    /// is the scan that holds that to one site.
    /// </remarks>
    public const string MainMenuNewSession = "main-menu.new-session";

    /// <summary>Anything that created a session without going through that command.</summary>
    public const string Direct = "direct";
}
