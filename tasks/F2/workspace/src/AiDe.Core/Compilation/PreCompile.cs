using System.Text.Json.Nodes;
using AiDe.Core.AgentPlane;
using AiDe.Core.Presentation.Composer;
using AiDe.Core.Sessions;

namespace AiDe.Core.PromptCompilation;

/// <summary>Everything the mechanical pre-compile reads — the draft, the binding and the session's settings, with no live setting read later (ADR-0033 rule 3).</summary>
/// <param name="Draft">The draft: the source text, the structure lines, the attachments (refs only leave here), the ceilings, the per-prompt choices.</param>
/// <param name="Template">The bound template, for a template draft.</param>
/// <param name="SessionId">The session — the <c>opened</c> row's, which must equal the store's directory segment.</param>
/// <param name="EngineId">The bound engine; its provider is the family.</param>
/// <param name="CompileMode">The session's <c>compile_mode</c> — a provenance fact on <c>opened</c>.</param>
/// <param name="DefaultTaskClass">The session's <c>default_task_class</c> (<c>ComposerSendContext.TaskClass</c>) — the <c>task_class</c> row's value with <c>source: session-default</c> unless the prompt chose one (Ruling 70).</param>
public sealed record PreCompileInput(
    ComposerDraft Draft,
    PromptTemplate? Template,
    string SessionId,
    string EngineId,
    string CompileMode,
    string DefaultTaskClass);

/// <summary>
/// The mechanical rung of the compile step (§A8.1, T0): a pure, total, deterministic function of
/// the draft and the settings that yields the envelope's mechanical rows — never a model call,
/// never a clock in a value, never a file read (US-D2).
/// </summary>
/// <remarks>
/// <para><b>Runs in memory, persists nothing</b> (§A10.1): the live pre-compile on the debounced
/// draft yields <see cref="Live"/>, a pending envelope Prepare renders from; the Send gesture yields
/// <see cref="Open"/>, the same rows for the store to append. One function, two callers, so what
/// Prepare showed and what the store holds cannot differ.</para>
///
/// <para><b>What it writes, and what it never writes.</b> The <c>ceilings</c> snapshot with its
/// writer named on <c>inputs</c>; the <c>task_class</c> row (<c>session-default</c> or
/// <c>operator</c>); the family-profile selection (<c>none</c> until the pack ships one — ADR-0037's
/// dimension is read, not populated, here); the template applied; the attachments by reference;
/// the operator's structure lines as <c>operator</c> rows; the operator's tier override. It never
/// writes a lease, a shape, a rule-computed tier, an effective fan-out or a count — those are
/// <see cref="Projection.Project"/>'s (DM7; US-D1).</para>
/// </remarks>
public static class PreCompile
{
    /// <summary>The projector version <c>submitted.projector_version</c> records and <see cref="ConstantsFor"/> is keyed by.</summary>
    public const string ProjectorVersion = "1";

    /// <summary>The writer the <c>ceilings</c> snapshot names: the session's settings (S2's home, Ruling 56).</summary>
    public const string CeilingsWriter = "session.config";

    /// <summary>The writer a template-supplied structure line names.</summary>
    public const string TemplateWriter = "template";

    /// <summary>The envelope id the live, in-memory pre-compile carries — never persisted.</summary>
    public const string LiveEnvelopeId = "live";

    /// <summary>
    /// The rule's constants for a projector version — a host-compiled table, never read from the
    /// workspace (§A12.4: K and the byte bound are initial values labelled Inferred; a change is a
    /// new version, so history never rewrites).
    /// </summary>
    public static CompileConstants ConstantsFor(string projectorVersion) => projectorVersion switch
    {
        "1" => new CompileConstants(K: 5, ByteBound: 32768, BoundMs: 60000),
        _ => throw new ArgumentOutOfRangeException(nameof(projectorVersion), projectorVersion, "no constants table for this projector version"),
    };

    /// <summary>The live envelope Prepare renders from — the same rows <see cref="Open"/> yields, numbered, persisted nowhere.</summary>
    public static Envelope Live(PreCompileInput input) => Envelope.Pending(Open(input, LiveEnvelopeId));

    /// <summary>The rows the Send gesture appends: <c>opened</c>, then the mechanical decorations, then the operator's rows.</summary>
    /// <param name="input">The inputs.</param>
    /// <param name="envelopeId">The envelope being opened.</param>
    /// <param name="supersedes">The abandoned envelope this one re-prepares, or null.</param>
    public static IReadOnlyList<EnvelopeEvent> Open(PreCompileInput input, string envelopeId, string? supersedes = null)
    {
        ArgumentNullException.ThrowIfNull(input);
        ArgumentException.ThrowIfNullOrWhiteSpace(envelopeId);
        ArgumentException.ThrowIfNullOrWhiteSpace(input.DefaultTaskClass);

        var draft = input.Draft;
        var rows = new List<EnvelopeEvent>
        {
            new Opened(envelopeId, draft.SourceText, input.SessionId, input.EngineId, input.CompileMode, supersedes, ConstantsFor(ProjectorVersion)),

            // THE CEILINGS, A SNAPSHOT WITH ITS WRITER NAMED (Ruling 56; ADR-0033 rule 3): the fan-out
            // ceiling and the budget cap (null = bounded by the subscription) — never a compile-time default.
            new Decorated(envelopeId, DecorationNames.Ceilings, CeilingsValue(draft.Ceilings), DecorationSources.Mechanical)
            {
                Inputs = [new DecorationInput(CeilingsWriter, input.SessionId)],
            },

            // THE TASK CLASS (Ruling 70; Ruling 72): the session's default, or the class this prompt chose.
            draft.TaskClassChoice is { } chosen
                ? new Decorated(envelopeId, DecorationNames.TaskClass, JsonValue.Create(chosen), DecorationSources.Operator)
                : new Decorated(envelopeId, DecorationNames.TaskClass, JsonValue.Create(input.DefaultTaskClass), DecorationSources.SessionDefault),

            // FAMILY-PROFILE SELECTION (§A12.5): the family is the catalog's provider; the profile is
            // `none` until the pack ships one — recorded as null version and sha, never as the current one.
            new Decorated(envelopeId, DecorationNames.FamilyProfile, FamilyProfileValue(input.EngineId), DecorationSources.Mechanical),

            input.Template is { } template
                ? new Decorated(envelopeId, DecorationNames.TemplateApplied, new JsonObject { ["id"] = template.Id, ["version"] = template.Version }, DecorationSources.Mechanical)
                {
                    Inputs = [new DecorationInput(TemplateWriter, template.Id, template.Version.ToString(System.Globalization.CultureInfo.InvariantCulture))],
                }
                : new Decorated(envelopeId, DecorationNames.TemplateApplied, null, DecorationSources.Mechanical),

            // ATTACHMENTS BY REFERENCE — the body is held in memory since the affirmation and enters
            // only at Send, in the rendered prompt (§A13.2); the store refuses a body member.
            new Decorated(envelopeId, DecorationNames.Attachments, AttachmentsValue(draft.Attachments), DecorationSources.Mechanical),
        };

        // THE STRUCTURE LINES, AS THE OPERATOR TYPED THEM (mechanical-only: every line is the
        // operator's; a template's are `mechanical` with the template named on inputs; the model's
        // are `derived`, CV-3's rung). Only the goal-block form's lines are structure — a value
        // retained behind a switched-away shape is not part of this turn (ComposerDraft.TurnShape).
        if (draft.Shape == ComposerShape.GoalBlock)
        {
            foreach (var name in DecorationNames.StructureLines)
            {
                if (draft.GoalValues.TryGetValue(name, out var value) && !string.IsNullOrWhiteSpace(value))
                {
                    rows.Add(new Decorated(envelopeId, name, JsonValue.Create(value), DecorationSources.Operator));
                }
            }
        }

        // THE OPERATOR'S TIER OVERRIDE (§A9 R4; §A11): the only stored tier.
        if (draft.TierOverride is { } tier)
        {
            rows.Add(new Decorated(envelopeId, DecorationNames.Tier, JsonValue.Create(tier), DecorationSources.Operator));
        }

        // THE OPERATOR'S ACCOUNT CHOICE (Ruling 105 (2)): the Ruling 63/72 shape — an operator row at
        // Send; the session's default is never written here, it is the binding the request carries.
        if (draft.AccountChoice is { } account)
        {
            rows.Add(new Decorated(envelopeId, DecorationNames.Account, JsonValue.Create(account), DecorationSources.Operator));
        }

        return rows;
    }

    private static JsonObject CeilingsValue(Ceilings ceilings) => new()
    {
        ["fan_out"] = ceilings.FanOutCeiling,
        // THE SENTINEL NEVER REACHES A ROW AS A NUMBER (Ruling 72; the named-member cap): an absent
        // cap is null on the snapshot, whether the setting was null or the declared maximal value.
        ["budget"] = ceilings.BudgetCap is { IsSubscriptionBounded: false } cap
            ? new JsonObject { ["requests"] = cap.Requests, ["tokens"] = cap.Tokens }
            : null,
    };

    private static JsonObject FamilyProfileValue(string engineId)
    {
        string family;
        try
        {
            family = EngineCatalog.Find(engineId).Provider;
        }
        catch (AgentPlaneException)
        {
            family = Envelope.NotRecorded;
        }

        return new JsonObject { ["family"] = family, ["version"] = null, ["sha"] = null };
    }

    private static JsonArray AttachmentsValue(IReadOnlyList<ComposerAttachment> attachments) =>
        new([.. attachments.Select(a => (JsonNode)new JsonObject
        {
            ["path"] = a.DisplayPath,
            ["sha256"] = a.Sha256,
            ["bytes"] = a.Bytes,
            ["outside_workspace"] = a.IsOutsideWorkspace,
        })]);
}
