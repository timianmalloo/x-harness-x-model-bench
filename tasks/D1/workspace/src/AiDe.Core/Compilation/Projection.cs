using System.Text.Json.Nodes;
using AiDe.Core.AgentPlane;
using AiDe.Core.Presentation.Composer;
using AiDe.Core.Sessions;

namespace AiDe.Core.PromptCompilation;

/// <summary>
/// <c>Project(Fold(events))</c>: the shape, the tier with its rationale, the effective fan-out, the
/// CT19 block, the lease, the prompt, the task class and the rebuild's witness — computed at every
/// render and at Submit, stored nowhere (§A6; §A12.2).
/// </summary>
/// <param name="Shape">The turn's shape word: <c>message</c> or <c>goal block</c>.</param>
/// <param name="Tier">T0 · T1 · T2 — the rule's, or the operator's override.</param>
/// <param name="Rationale">The sentence the decoration line shows: <i>goal block filled by you, one lease</i> · <i>operator (rule said T1)</i>.</param>
/// <param name="Rule">R0 · R1 · R2 · R3 · R4.</param>
/// <param name="StructureSource">Who filled Goal and Done when: <c>operator</c> · <c>derived</c> · <c>template</c>; empty for a Message.</param>
/// <param name="FanOutCap"><c>min(cap(tier), ceiling)</c> — computed here, never stored.</param>
/// <param name="FanOutCeiling">The session's ceiling, from the <c>ceilings</c> snapshot.</param>
/// <param name="Budget">The cap, or <see cref="RunBudget.SubscriptionBounded"/> when the snapshot's budget is null.</param>
/// <param name="GoalBlock">The six-field block for a goal-block turn; null for a Message (Ruling 75).</param>
/// <param name="Lease">The derived lease for a write-shaped turn; null for a read-only one (Ruling 73).</param>
/// <param name="Patterns"><c>LeaseDerivation.Patterns</c> over <c>opened.source_text</c> — what the write-scope line displays.</param>
/// <param name="TaskClass"><c>Current(task_class).value</c>.</param>
/// <param name="TaskClassSource"><c>Current(task_class).source</c>: <c>session-default</c> or <c>operator</c>.</param>
/// <param name="ProjectionSha">sha256 over the canonical rebuildable domain — <c>submitted.projection_sha</c>'s value.</param>
/// <param name="Compiled">The render — the sent bytes and the attachment totals — when the held bodies were supplied; null for an offline rebuild.</param>
/// <param name="TextSha256">sha256 of the sent bytes, when rendered.</param>
public sealed record CompiledProjection(
    string Shape,
    string Tier,
    string Rationale,
    string Rule,
    string StructureSource,
    int FanOutCap,
    int FanOutCeiling,
    RunBudget Budget,
    GoalBlock? GoalBlock,
    Lease? Lease,
    IReadOnlyList<string> Patterns,
    string TaskClass,
    string TaskClassSource,
    string ProjectionSha,
    CompiledPrompt? Compiled,
    string? TextSha256)
{
    /// <summary>Ruling 73's access projection: read-only when no lease was derived.</summary>
    public bool IsReadOnly => Lease is null;

    /// <summary>
    /// The account label the operator chose for this turn (<c>Current(account)</c> with
    /// <c>source: operator</c>, Ruling 105 (2)), or null — the session's default account binds.
    /// Carried beside the projection's facts, outside <see cref="ProjectionSha"/>: the sha is the
    /// compiled prompt's identity and the account is the run-side binding the request carries.
    /// </summary>
    public string? AccountOverride { get; init; }

    /// <summary>The sent bytes, when rendered.</summary>
    public string? Prompt => Compiled?.Text;
}

/// <summary>
/// The one projection of the Prompt Compilation context — <b>the sole function that assembles what
/// <c>ComposerSendGate.Send</c> puts into <c>GovernedRunRequest</c></b>, serving every render and
/// the eval's <c>aide compile fold</c> alike (ADR-0033 rule 2; DM11 b).
/// </summary>
/// <remarks>
/// <para><b>Exactly three call sites by path</b>, asserted by a census: the composer's render
/// (<c>Presentation/Composer/ComposerCompiler.cs</c>), the send gate
/// (<c>Workbench/Composer/ComposerSendGate.cs</c>) and the eval's verb (<c>Cli/CompileFold.cs</c>).
/// A fourth producer of the sent bytes is the failure this shape exists to make visible.</para>
///
/// <para><b>The lease is derived here, from <c>opened.source_text</c>, and nowhere else in the
/// product</b> — the one <c>LeaseDerivation.Derive</c> call (Ruling 66; §A13.3 d′). A stored lease
/// would be one quantity with two homes (DM-A).</para>
///
/// <para><b>It never reads a live setting</b> (ADR-0033 rule 3): the ceilings come from the
/// <c>ceilings</c> row the pre-compile snapshotted, so the rebuild is possible offline with no
/// session open. A fold with no <c>opened</c> row or no well-formed <c>ceilings</c> row is
/// <i>incomplete</i> and refused with <see cref="EnvelopeStoreErrorCodes.ProjectionIncomplete"/>.</para>
///
/// <para>Patterns: <b>Projection / CQRS read model</b>; the mapping onto <c>GovernedRunRequest</c> in
/// the send gate is an <b>Anti-Corruption Layer</b> to the agent plane's Published Language.</para>
/// </remarks>
public static class Projection
{
    /// <summary>The projector's version — <c>submitted.projector_version</c>.</summary>
    public const string Version = PreCompile.ProjectorVersion;

    private const string GoalBlockShape = "goal block";
    private const string MessageShape = "message";

    /// <summary>
    /// Projects one envelope. With a <paramref name="draft"/> the prompt is rendered from the held
    /// bodies; without one (the offline rebuild) the prompt is null and only the rebuildable
    /// domain is computed.
    /// </summary>
    /// <exception cref="EnvelopeStoreException"><see cref="EnvelopeStoreErrorCodes.ProjectionIncomplete"/>.</exception>
    public static CompiledProjection Project(Envelope envelope, ComposerDraft? draft = null, PromptTemplate? template = null)
    {
        ArgumentNullException.ThrowIfNull(envelope);

        var opened = envelope.Opened
            ?? throw new EnvelopeStoreException(EnvelopeStoreErrorCodes.ProjectionIncomplete, $"envelope '{envelope.EnvelopeId}' has no opened row; nothing projects from it");

        // THE CEILINGS FROM THE SNAPSHOT, never a live setting: a fold without a well-formed row is
        // incomplete — Prepare goes stale and the pre-compile appends a fresh one before Project runs.
        var (ceiling, budget) = ReadCeilings(envelope);

        // THE STRUCTURE — Confirmed(), the one function the shape, P and the CT19 block read.
        var goal = Line(envelope, DecorationNames.Goal);
        var doneWhen = Line(envelope, DecorationNames.DoneWhen);
        var notInScope = Line(envelope, DecorationNames.NotInScope);
        var hasBlock = goal is not null && doneWhen is not null;
        var shape = hasBlock ? TurnShape.GoalBlock : TurnShape.Message;
        var structureSource = hasBlock ? StructureSourceOf(envelope.Confirmed(DecorationNames.Goal)!) : string.Empty;

        // L — the distinct patterns the SOURCE TEXT derives (Ruling 66): the write-scope line's display.
        var patterns = LeaseDerivation.Patterns(opened.SourceText);

        // THE TIER: the rule (§A9 R0–R3) or the operator's override (R4).
        var rule = ComposerCompiler.Tier(shape, patterns, StructureWord(structureSource));
        var tier = envelope.Current(DecorationNames.Tier) is { Source: DecorationSources.Operator } overridden
            && overridden.ValueAsString is { } chosen
            && ComposerCompiler.IsTier(chosen)
                ? new TierProjection(chosen, $"operator (rule said {rule.Tier})", "R4")
                : rule;

        var fanOutCap = ComposerCompiler.EffectiveFanOut(tier.Tier, ceiling);

        var block = hasBlock ? new GoalBlock(goal, doneWhen, notInScope, tier.Tier, fanOutCap, budget) : null;

        // THE LEASE — derived here, from the editor's own text, only for a write-shaped turn (Ruling 73).
        var readOnly = ComposerCompiler.IsReadOnly(shape, patterns);
        var lease = readOnly ? null : LeaseDerivation.Derive(opened.SourceText);

        var taskClass = envelope.Current(DecorationNames.TaskClass)
            ?? throw new EnvelopeStoreException(EnvelopeStoreErrorCodes.ProjectionIncomplete, $"envelope '{envelope.EnvelopeId}' has no task_class row; the pre-compile always writes one");
        var taskClassValue = taskClass.ValueAsString
            ?? throw new EnvelopeStoreException(EnvelopeStoreErrorCodes.ProjectionIncomplete, $"envelope '{envelope.EnvelopeId}' has a task_class row with no string value");

        var sha = ProjectionSha(
            goal, doneWhen, notInScope, tier.Tier, fanOutCap, budget,
            lease?.Exclusive ?? [], opened.SourceText,
            envelope.Current(DecorationNames.FamilyProfile)?.Value,
            envelope.Current(DecorationNames.Attachments)?.Value,
            taskClassValue, taskClass.Source);

        CompiledPrompt? compiled = null;
        string? textSha = null;
        if (draft is not null)
        {
            // THE RENDER, FROM THIS PROJECTION'S OWN BLOCK: the tier the operator sees in the block is
            // the tier this projection computed, override included — the one producer of the sent
            // bytes, which the send gate's RenderView and Send both call.
            compiled = ComposerCompiler.Compile(draft, template, block);
            textSha = EnvelopeHash.Sha256Hex(compiled.Text);
        }

        return new CompiledProjection(
            hasBlock ? GoalBlockShape : MessageShape,
            tier.Tier, tier.Rationale, tier.Rule, structureSource,
            fanOutCap, ceiling, budget,
            block, lease, patterns,
            taskClassValue, taskClass.Source,
            sha, compiled, textSha)
        {
            AccountOverride = envelope.Current(DecorationNames.Account) is { Source: DecorationSources.Operator } chosenAccount
                ? chosenAccount.ValueAsString
                : null,
        };
    }

    /// <summary>
    /// <c>sha256(canonical(goal ‖ done_when ‖ not_in_scope ‖ tier ‖ fan_out_cap ‖ budget ‖
    /// Derive(source_text).Exclusive ‖ sha256(source_text) ‖ family_profile {family, version, sha} ‖
    /// attachments[].{path, sha256} ‖ Current(task_class).value ‖ source))</c> (§A12.2; ADR-0033
    /// rule 2's domain: the task class by its current row AND its source, so an <c>operator</c> row
    /// whose value equals the session default still moves the witness). Bodies excluded — never
    /// stored; <c>text_sha256</c> witnesses them separately.
    /// </summary>
    internal static string ProjectionSha(
        string? goal, string? doneWhen, string? notInScope, string tier, int fanOutCap, RunBudget budget,
        IReadOnlyList<string> exclusive, string sourceText, JsonNode? familyProfile, JsonNode? attachments,
        string taskClass, string taskClassSource)
    {
        var domain = new JsonArray
        {
            goal,
            doneWhen,
            notInScope,
            tier,
            fanOutCap,

            // THE SENTINEL NEVER REACHES A RENDERED BYTE AS A NUMBER (Ruling 72); the hash domain is
            // not a render, and "none chosen" is null there too, so the two readings agree.
            budget.IsSubscriptionBounded ? null : new JsonObject { ["requests"] = budget.Requests, ["tokens"] = budget.Tokens },
            new JsonArray([.. exclusive.Select(e => JsonValue.Create(e))]),
            EnvelopeHash.Sha256Hex(sourceText),
            familyProfile is JsonObject fp
                ? new JsonObject { ["family"] = fp["family"]?.DeepClone(), ["version"] = fp["version"]?.DeepClone(), ["sha"] = fp["sha"]?.DeepClone() }
                : null,
            attachments is JsonArray refs
                ? new JsonArray([.. refs.OfType<JsonObject>().Select(r => (JsonNode)new JsonObject { ["path"] = r["path"]?.DeepClone(), ["sha256"] = r["sha256"]?.DeepClone() })])
                : new JsonArray(),
            taskClass,
            taskClassSource,
        };

        return EnvelopeHash.Sha256Hex(domain.ToJsonString());
    }

    private static (int Ceiling, RunBudget Budget) ReadCeilings(Envelope envelope)
    {
        var row = envelope.Current(DecorationNames.Ceilings);
        if (row?.Value is not JsonObject value
            || value["fan_out"] is not JsonValue fanOut || !fanOut.TryGetValue(out int ceiling)
            || !value.ContainsKey("budget"))
        {
            throw new EnvelopeStoreException(
                EnvelopeStoreErrorCodes.ProjectionIncomplete,
                $"envelope '{envelope.EnvelopeId}' has no well-formed ceilings row ({{fan_out, budget}}); the fold is incomplete — Prepare is stale until the pre-compile appends a fresh snapshot");
        }

        var budget = value["budget"] is JsonObject cap
            && cap["requests"] is JsonValue r && r.TryGetValue(out int requests)
            && cap["tokens"] is JsonValue t && t.TryGetValue(out long tokens)
                ? new RunBudget(requests, tokens)
                : RunBudget.SubscriptionBounded;

        return (ceiling, budget);
    }

    /// <summary>A structure line's confirmed value — blank reads as absent, exactly as <c>SpawnContract.Validate</c> reads a field.</summary>
    private static string? Line(Envelope envelope, string name)
    {
        var value = envelope.Confirmed(name)?.ValueAsString;
        return string.IsNullOrWhiteSpace(value) ? null : value;
    }

    /// <summary>
    /// Who filled the structure (§A9): an <c>operator</c> row is the operator's; a <c>derived</c> row
    /// the model's; a <c>mechanical</c> row is a template's <b>only when its inputs name the template
    /// writer</b> — a mechanical structure row with no named writer reads <i>not recorded</i>, never
    /// a plausible "template".
    /// </summary>
    private static string StructureSourceOf(Decorated confirmed) => confirmed.Source switch
    {
        DecorationSources.Derived => StructureSources.Derived,
        DecorationSources.Mechanical => confirmed.Inputs?.Any(i => string.Equals(i.Writer, PreCompile.TemplateWriter, StringComparison.Ordinal)) == true
            ? StructureSources.Template
            : Envelope.NotRecorded,
        _ => StructureSources.Operator,
    };

    private static string StructureWord(string structureSource) => structureSource switch
    {
        StructureSources.Derived => "the model",
        StructureSources.Template => "the template",
        StructureSources.Operator => "you",
        _ => "an unnamed writer",
    };
}

/// <summary>Who filled the structure — the rationale's <c>structure_source</c> (§A9).</summary>
public static class StructureSources
{
    public const string Operator = "operator";
    public const string Derived = "derived";
    public const string Template = "template";
}
