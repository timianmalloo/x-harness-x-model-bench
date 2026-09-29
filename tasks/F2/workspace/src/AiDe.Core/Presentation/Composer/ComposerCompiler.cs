using System.Text;
using AiDe.Core.AgentPlane;
using AiDe.Core.Sessions;

namespace AiDe.Core.Presentation.Composer;

/// <summary>The text the conductor will receive, and the attachment totals that ride with it.</summary>
/// <param name="Text">Exactly the bytes the run host is handed. The view renders this, not a summary.</param>
/// <param name="AttachmentCount">How many attachments are inside <paramref name="Text"/>.</param>
/// <param name="AttachmentBytes">Their total source byte count.</param>
/// <param name="OutsideWorkspaceCount">How many came from outside the workspace root.</param>
public sealed record CompiledPrompt(
    string Text, int AttachmentCount, int AttachmentBytes, int OutsideWorkspaceCount)
{
    /// <summary>How many came from inside the workspace root.</summary>
    public int InsideWorkspaceCount => AttachmentCount - OutsideWorkspaceCount;
}

/// <summary>
/// Compiles a draft to the prompt text — and nothing else happens between here and the send.
/// </summary>
/// <remarks>
/// <para><b>This type is where Security C15 is enforceable, because it is total and pure.</b> It
/// reads the draft and the template it is given. It opens no file, queries no graph, expands no
/// mention, and makes no network call — so "the compiled view and the sent text differ by a byte"
/// says what it appears to say. Without that, the human approves a mention and the agent receives a
/// file, while the byte check stays green because both sides hold the unresolved text.</para>
///
/// <para><b>Mentions stay literal on purpose.</b> A mention is characters in the draft. It is never
/// resolved to a path or to a file's contents anywhere in this slice; expansion is R20, and
/// Ruling 44's acceptance is void the moment it exists.</para>
///
/// <para><b>Deterministic.</b> The goal block renders its six fields in the order §14.3 lists them,
/// a template renders through <see cref="TemplateCompiler"/>, attachments render in affirmation
/// order, and nothing reads a clock, a culture or the environment.</para>
/// </remarks>
public static class ComposerCompiler
{
    /// <summary>The fence info word an attachment block carries, so a reader can see what it is.</summary>
    public const string AttachmentFenceTag = "aide-attachment";

    /// <summary>
    /// The lease line's read-only state — Ruling 73's one decoration-line state, in the words the
    /// specs fix (Addendum C US-C13 as amended; Addendum D's errata after Ruling 73).
    /// </summary>
    /// <remarks>
    /// The <i>value</i>, without the <c>Lease:</c> label: the WPF surface prefixes the label
    /// (<see cref="LeaseLine"/>); the thread's decoration line (DS-1; CV-1) renders the value as
    /// its lease segment.
    /// </remarks>
    public const string ReadOnlyScope = "read-only — nothing will be written";

    /// <summary>
    /// The one content-gap refusal (Ruling 75): tier-blind, and the only sentence a blank line on a
    /// goal block can refuse with. A blank Goal or Done when is never refused — it makes a Message.
    /// </summary>
    public const string GoalBlockNeedsNotInScope = "This prompt is a goal block and needs Not in scope.";

    /// <summary>
    /// Ruling 73's access projection: a turn is read-only when it is a Message (whatever it
    /// mentions — lease ≠ tier, §A9 R0) or a goal block whose source text derives no write scope
    /// (§A9 R1). Only a goal block with a derived scope is a write.
    /// </summary>
    /// <param name="shape">The turn's shape, <see cref="ComposerDraft.TurnShape"/>.</param>
    /// <param name="patterns">
    /// <see cref="LeaseDerivation.Patterns"/> over the draft's <c>SourceText</c> — the caller derives
    /// it from the editor's source text (Ruling 66) so this projection reads what the send will send.
    /// </param>
    public static bool IsReadOnly(TurnShape shape, IReadOnlyList<string> patterns)
    {
        ArgumentNullException.ThrowIfNull(patterns);
        return shape == TurnShape.Message || patterns.Count == 0;
    }

    /// <summary>
    /// The lease line as the surface shows it: the read-only state for <c>null</c>, else the
    /// patterns that are (or will be) the lane's lease. The caller passes <c>null</c> exactly when
    /// <see cref="IsReadOnly"/> says so before Send, and the request's own absent lease after it —
    /// so what the operator read and what was sent can never disagree (Ruling 66 condition (2)).
    /// </summary>
    public static string LeaseLine(IReadOnlyList<string>? lease) =>
        lease is null ? "Lease: " + ReadOnlyScope : "Lease: " + string.Join(", ", lease);

    /// <summary>The lease segment's empty state on the decoration line (SC2's words).</summary>
    public const string LeaseNoneYet = "none yet — mention the files this run may write as @path";

    /// <summary>
    /// Addendum D §A9's mechanical tier rule — a deterministic, <b>total</b> function of two inputs:
    /// <b>P</b>, whether a goal block exists (<see cref="ComposerDraft.TurnShape"/>), and <b>L</b>,
    /// the count of distinct lease patterns the source text derives. Nothing else.
    /// </summary>
    /// <remarks>
    /// <para>R0: no goal block → T0. R1: a goal block with no write scope → T1 (it runs read-only,
    /// Ruling 73). R2: one lease → T1. R3: two or more → T2. R4, the operator override, is Prepare's
    /// (CV-2) and is not here. The same two inputs <see cref="IsReadOnly"/> reads, so the shape,
    /// the access and the tier can never disagree about whether a goal block exists.</para>
    ///
    /// <para><b>The rationale names who filled the structure</b> — <paramref name="structureSource"/>
    /// is read from the fold by <c>Projection.Project</c> (<c>operator</c> · <c>template</c> · the
    /// model), which is the one caller that passes anything but the default.</para>
    /// </remarks>
    /// <param name="shape">The turn's shape — P.</param>
    /// <param name="patterns"><see cref="LeaseDerivation.Patterns"/> over the source text — L is its count.</param>
    /// <param name="structureSource">Who filled Goal and Done when: <c>you</c>, <c>the model</c> or <c>the template</c>.</param>
    public static TierProjection Tier(TurnShape shape, IReadOnlyList<string> patterns, string structureSource = "you")
    {
        ArgumentNullException.ThrowIfNull(patterns);

        if (shape == TurnShape.Message)
        {
            return new TierProjection("T0", "no goal block", "R0");
        }

        return patterns.Count switch
        {
            0 => new TierProjection("T1", $"goal block filled by {structureSource}, no write scope", "R1"),
            1 => new TierProjection("T1", $"goal block filled by {structureSource}, one lease", "R2"),
            var n => new TierProjection("T2", string.Create(System.Globalization.CultureInfo.InvariantCulture, $"goal block filled by {structureSource}, {n} leases"), "R3"),
        };
    }

    /// <summary>The three tiers a turn may carry — an override outside them is refused (§A9 R4's falsifier: <c>T9</c>).</summary>
    public static bool IsTier(string? tier) => tier is "T0" or "T1" or "T2";

    /// <summary>The cap function (CT19; GO7): <c>cap(T0) = 0</c>, <c>cap(T1) = 2</c>, <c>cap(T2) = 4</c>.</summary>
    public static int CapOf(string tier) => tier switch
    {
        "T0" => 0,
        "T1" => 2,
        "T2" => 4,
        _ => throw new ArgumentOutOfRangeException(nameof(tier), tier, "the tier is one of T0, T1, T2"),
    };

    /// <summary>
    /// Effective fan-out = <c>min(cap(tier), ceiling)</c> (Ruling 64) — a projection, never stored,
    /// never raised from a prompt. A negative ceiling is NOT clamped to 0: it is a broken session
    /// setting, and the contract refuses the block at the send naming <c>fan_out_cap</c> — a silent
    /// 0 would be a plausible wrong number (IO7).
    /// </summary>
    public static int EffectiveFanOut(string tier, int ceiling) => Math.Min(CapOf(tier), ceiling);

    /// <summary>
    /// The composer's settings line (<c>DESIGN.md</c> copy): <i>fan-out cap 2 (ceiling 3) · budget:
    /// bounded by your subscription · from session settings</i>; at T0, <i>T0 — the ceiling of 3
    /// does not apply to this turn</i>. Never a numeral for an absent cap (Ruling 72).
    /// </summary>
    public static string SettingsLine(string tier, int ceiling, RunBudget? budgetCap)
    {
        var culture = System.Globalization.CultureInfo.InvariantCulture;
        var fanOut = tier == "T0"
            ? string.Create(culture, $"T0 — the ceiling of {ceiling} does not apply to this turn")
            : string.Create(culture, $"fan-out cap {EffectiveFanOut(tier, ceiling)} (ceiling {ceiling})");
        var budget = budgetCap is null || budgetCap.IsSubscriptionBounded
            ? "budget: bounded by your subscription"
            : string.Create(culture, $"budget: {budgetCap.Tokens:N0} tokens, {budgetCap.Requests:N0} requests · cap enforced");
        return fanOut + " · " + budget + " · from session settings";
    }

    /// <summary>
    /// The current turn's decoration rows in SC2's one grammar — <c>class · tier · lease · shape
    /// [· template]</c>, each with its source and reason — <b>read from <see cref="PromptCompilation.Projection.Project"/>
    /// over the live pre-compile</b> (ADR-0033 rule 2: the render site calls <c>Project()</c>), so the
    /// line the operator confirms at Send is the projection the send gate puts on the wire.
    /// </summary>
    /// <param name="draft">The draft.</param>
    /// <param name="taskClass">The session's default class — the prompt's own choice on the draft supersedes it (Ruling 70).</param>
    /// <param name="template">The bound template, for a template draft.</param>
    /// <param name="engineId">The bound engine, or null before the composer is bound.</param>
    /// <param name="sessionId">The session, or null before the composer is bound.</param>
    /// <param name="compileMode">The session's compile mode.</param>
    /// <param name="defaultAccountLabel">The session's default account label (Ruling 105), or null before the composer is bound.</param>
    public static IReadOnlyList<Sessions.DecorationRow> Decorations(
        ComposerDraft draft,
        string taskClass,
        PromptTemplate? template = null,
        string? engineId = null,
        string? sessionId = null,
        string compileMode = CompileModes.MechanicalOnly,
        string? defaultAccountLabel = null)
    {
        ArgumentNullException.ThrowIfNull(draft);
        ArgumentException.ThrowIfNullOrWhiteSpace(taskClass);

        var input = new PromptCompilation.PreCompileInput(
            draft, template,
            sessionId ?? PromptCompilation.Envelope.NotRecorded,
            engineId ?? PromptCompilation.Envelope.NotRecorded,
            compileMode,
            taskClass);
        return Decorations(PromptCompilation.Projection.Project(PromptCompilation.PreCompile.Live(input)), draft, defaultAccountLabel);
    }

    /// <summary>The decoration rows of one projection — the one row builder the live line and a persisted envelope share (DM7).</summary>
    /// <param name="projection">The projection.</param>
    /// <param name="draft">The draft.</param>
    /// <param name="defaultAccountLabel">The session's default account label, or null — the <c>account</c> row then reads the override or <i>not recorded</i>.</param>
    public static IReadOnlyList<Sessions.DecorationRow> Decorations(PromptCompilation.CompiledProjection projection, ComposerDraft draft, string? defaultAccountLabel = null)
    {
        ArgumentNullException.ThrowIfNull(projection);
        ArgumentNullException.ThrowIfNull(draft);

        var rows = new List<Sessions.DecorationRow>
        {
            new("class", projection.TaskClass, projection.TaskClassSource,
                projection.TaskClassSource == PromptCompilation.DecorationSources.Operator
                    ? "chosen for this prompt"
                    : string.Equals(projection.TaskClass, Watcher.TaskClasses.FreeForm, StringComparison.Ordinal)
                        ? "no class ranks this turn"
                        : "the session's default task class"),
            new("tier", projection.Tier, projection.Rule == "R4" ? PromptCompilation.DecorationSources.Operator : "rule", projection.Rationale),
            new("lease",
                projection.IsReadOnly ? ReadOnlyScope : string.Join(" · ", projection.Patterns),
                "derived",
                projection.Patterns.Count switch
                {
                    0 => LeaseNoneYet,
                    1 => "from your mention",
                    _ => "from your mentions",
                }),
            new("shape",
                projection.Shape,
                "projection",
                projection.GoalBlock is not null
                    ? "Goal and Done when are both written"
                    : "a blank Goal or Done when makes a message"),   // Ruling 75 — the id stays here, never on the screen (U11)
        };

        if (draft.TemplateId is { } template)
        {
            rows.Add(new("template", template, "operator", "picked from the template control"));
        }

        // THE ACCOUNT (Ruling 105 (2)): this turn's binding — the operator's choice, else the session's default.
        rows.Add(projection.AccountOverride is { } chosenAccount
            ? new("account", chosenAccount, PromptCompilation.DecorationSources.Operator, "chosen for this turn")
            : new("account", defaultAccountLabel ?? PromptCompilation.Envelope.NotRecorded, PromptCompilation.DecorationSources.SessionDefault, "session default"));

        return rows;
    }

    /// <summary>Compiles the draft. <paramref name="template"/> is required only for a template draft.</summary>
    public static CompiledPrompt Compile(ComposerDraft draft, PromptTemplate? template = null)
    {
        ArgumentNullException.ThrowIfNull(draft);
        return Compile(draft, template, draft.TurnShape == TurnShape.GoalBlock ? draft.ToGoalBlock() : null);
    }

    /// <summary>
    /// Compiles the draft around a projected block: <see cref="PromptCompilation.Projection.Project"/>
    /// renders the sent bytes through this overload with <i>its</i> block, so the tier in the block
    /// is the tier the projection computed (an override included) — one producer of the bytes.
    /// </summary>
    /// <param name="block">The six-field block for a goal-block turn, or null for a Message (Ruling 75).</param>
    public static CompiledPrompt Compile(ComposerDraft draft, PromptTemplate? template, GoalBlock? block)
    {
        ArgumentNullException.ThrowIfNull(draft);

        var body = draft.Shape switch
        {
            // A free-form draft whose fold confirmed a structure — the model's lines kept, under an
            // agentic rung — renders the block it projected; with none, the text alone (byte-identical
            // to before the compile step existed).
            ComposerShape.FreeForm => block is not null
                ? RenderGoalBlock(block) + RenderMessage(draft.FreeFormText)
                : draft.FreeFormText,

            // A goal-block form compiles as its shape says (Ruling 75): a goal block renders the
            // six sections and then the message; a blank Goal or Done when makes a Message, whose
            // bytes are the message alone — exactly the free-form form's, so a demotion never
            // changes what the lane receives except by the block's absence.
            ComposerShape.GoalBlock => block is not null
                ? RenderGoalBlock(block) + RenderMessage(draft.FreeFormText)
                : draft.FreeFormText,
            ComposerShape.Template => RenderTemplate(draft, template),
            _ => throw new ArgumentOutOfRangeException(nameof(draft), draft.Shape, "unknown composer shape"),
        };

        var text = new StringBuilder(body);
        foreach (var attachment in draft.Attachments)
        {
            if (text.Length > 0 && text[^1] != '\n')
            {
                text.Append('\n');
            }

            text.Append('\n').Append(RenderAttachment(attachment));
        }

        return new CompiledPrompt(
            text.ToString(),
            draft.Attachments.Count,
            draft.Attachments.Sum(a => a.Bytes),
            draft.Attachments.Count(a => a.IsOutsideWorkspace));
    }

    /// <summary>
    /// The goal block as prompt text, in the order §14.3 lists the fields.
    /// </summary>
    /// <remarks>
    /// <para>The headings are the <b>wire names</b>, so the field-level error a person sees and the prompt
    /// the engine reads use one vocabulary. <c>fan_out_cap</c> and <c>budget</c> are rendered as what
    /// they are — declarations — because Ruling 26c holds: Phase 1 validates them and enforces
    /// neither, and a prompt that reads as though they were enforced would be the first place that
    /// claim was made.</para>
    ///
    /// <para><b>The subscription-bounded budget renders as its state, not its numerals</b> (Ruling 72;
    /// ADR-0033 §3). <see cref="RunBudget.SubscriptionBounded"/> keeps <see cref="SpawnContract.Validate"/>
    /// byte-identical by being a maximal positive value; the render is where that value is read
    /// back as what it means — a reader of the compiled block sees <i>bounded by your subscription</i>,
    /// never <c>2147483647</c> presented as a limit somebody chose.</para>
    /// </remarks>
    public static string RenderGoalBlock(GoalBlock block)
    {
        ArgumentNullException.ThrowIfNull(block);

        var text = new StringBuilder();
        Section(GoalBlockFields.GoalKey, block.Goal);
        Section(GoalBlockFields.DoneWhenKey, block.DoneWhen);
        Section(GoalBlockFields.NotInScopeKey, block.NotInScope);
        Section(GoalBlockFields.TierKey, block.Tier);
        Section(GoalBlockFields.FanOutCapKey, block.FanOutCap?.ToString(System.Globalization.CultureInfo.InvariantCulture));
        Section(
            GoalBlockFields.BudgetKey,
            block.Budget switch
            {
                { IsSubscriptionBounded: true } => RunBudget.SubscriptionBoundedDisplay,
                { } budget => string.Create(
                    System.Globalization.CultureInfo.InvariantCulture,
                    $"requests: {budget.Requests}, tokens: {budget.Tokens} (declared, not enforced in Phase 1)"),
                null => null,
            });

        return text.ToString();

        void Section(string name, string? value)
        {
            text.Append("## ").Append(name).Append('\n').Append('\n')
                .Append(value ?? string.Empty).Append('\n').Append('\n');
        }
    }

    /// <summary>The message section under a goal block: the operator's words, verbatim, under the one heading that is not a §14.3 field.</summary>
    public const string MessageKey = "message";

    private static string RenderMessage(string message) =>
        string.IsNullOrWhiteSpace(message) ? string.Empty : "## " + MessageKey + "\n\n" + message + "\n";

    private static string RenderTemplate(ComposerDraft draft, PromptTemplate? template)
    {
        if (template is null)
        {
            throw new ArgumentNullException(
                nameof(template),
                "a template draft cannot compile without the template it names; a compiler that "
                + "substituted a blank here would put an empty prompt on the wire");
        }

        return TemplateCompiler.Compile(template, draft.TemplateValues);
    }

    /// <summary>
    /// One attachment as a visible fenced block whose header names the source and its byte count.
    /// </summary>
    /// <remarks>
    /// <para><b>The fence is widened to clear the content</b> — a file containing a fence of its own
    /// would otherwise end the block early and leave the rest of the file rendering as prose, which
    /// is the same defect class as a truncation with a better disguise.</para>
    ///
    /// <para><b>The outside-workspace label is part of the header, and the header is the record of a
    /// decision already taken</b> — the control that bites is the affirmation at the pick
    /// (C14(e)(iii)). Both exist because the label alone is read only by the person who already
    /// decided.</para>
    /// </remarks>
    public static string RenderAttachment(ComposerAttachment attachment)
    {
        ArgumentNullException.ThrowIfNull(attachment);

        var fence = new string('`', LongestBacktickRun(attachment.Text) + 1);
        var location = attachment.IsOutsideWorkspace
            ? "OUTSIDE the workspace root"
            : "inside the workspace root";

        var header = string.Create(
            System.Globalization.CultureInfo.InvariantCulture,
            $"{fence}{AttachmentFenceTag} source={attachment.DisplayPath} bytes={attachment.Bytes} location={location}");

        var body = attachment.Text.EndsWith('\n') ? attachment.Text : attachment.Text + "\n";
        return header + "\n" + body + fence + "\n";
    }

    private static int LongestBacktickRun(string text)
    {
        var longest = 2;
        var run = 0;
        foreach (var c in text)
        {
            run = c == '`' ? run + 1 : 0;
            if (run > longest)
            {
                longest = run;
            }
        }

        return longest;
    }
}

/// <summary>The §A9 rule's answer: the tier, why, and which row decided it.</summary>
/// <param name="Tier">One of T0, T1, T2.</param>
/// <param name="Rationale">The sentence the decoration line's provenance shows (<i>goal block filled by you, one lease</i>).</param>
/// <param name="Rule">The row: R0 · R1 · R2 · R3.</param>
public sealed record TierProjection(string Tier, string Rationale, string Rule);
