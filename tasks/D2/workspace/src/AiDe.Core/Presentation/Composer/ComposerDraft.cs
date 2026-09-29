using AiDe.Core.AgentPlane;
using AiDe.Core.Sessions;

namespace AiDe.Core.Presentation.Composer;

/// <summary>The three shapes one composer block can take (R19 bullet 3).</summary>
public enum ComposerShape
{
    /// <summary>Prose. The default, and the shape that works with no template anywhere in the path.</summary>
    FreeForm,

    /// <summary>The six goal-block fields, validated by the one mechanism (Ruling 26b).</summary>
    GoalBlock,

    /// <summary>A catalog template, rendered as a validated form.</summary>
    Template,
}

/// <summary>
/// The compiled turn's shape — Ruling 75 and Addendum D §A9's <b>P</b>: a goal block exists only
/// when Goal and Done when are both non-blank; everything else compiles as a Message.
/// </summary>
/// <remarks>
/// <b>A projection over the draft, never a stored decoration</b> (ADR-0033). It is distinct from
/// <see cref="ComposerShape"/>, which is the <i>editor's</i> form: a goal-block form with a blank
/// Goal is a Message, and a free-form or template draft is a Message until the compile step reads
/// a template's structure (Addendum D's <c>structure_source: template</c>, CV-2). The turn's
/// <i>access</i> — read-only or write — is the second projection, <see cref="ComposerCompiler.IsReadOnly"/>,
/// which reads this shape and the derived lease patterns together (Ruling 73).
/// </remarks>
public enum TurnShape
{
    /// <summary>No goal block: the turn runs read-only whatever it mentions (§A9 R0 — lease ≠ tier).</summary>
    Message,

    /// <summary>Goal and Done when are both written: the six-field block is validated and sent.</summary>
    GoalBlock,
}

/// <summary>One attachment, as it will appear in the prompt and nowhere else.</summary>
/// <param name="DisplayPath">
/// What the fence header names: a repository-relative path for an inside-workspace file, the
/// absolute path for an outside-workspace one. The operator read this before affirming it.
/// </param>
/// <param name="ResolvedPath">The fully resolved real path, after symlinks and junctions (C14(e)(ii)).</param>
/// <param name="Bytes">The byte count. It is what makes the human's read informed (Ruling 43).</param>
/// <param name="Text">The decoded text, held literally — never a reference, never re-read at send.</param>
/// <param name="IsOutsideWorkspace">Computed from <paramref name="ResolvedPath"/>, never from the pick.</param>
/// <param name="Sha256">
/// The content hash. Channel B only — the committed channel may never carry it for an
/// outside-workspace file, because a hash of a cloned file is a confirmable fingerprint.
/// </param>
public sealed record ComposerAttachment(
    string DisplayPath,
    string ResolvedPath,
    int Bytes,
    string Text,
    bool IsOutsideWorkspace,
    string Sha256);

/// <summary>
/// One composer block's draft: its shape, the content of every shape it has held, and its
/// attachments.
/// </summary>
/// <remarks>
/// <para><b>Shape switching preserves content by per-shape draft retention, not by transformation</b>
/// (Ruling 26 cut iv). Each shape keeps its own state; switching moves a cursor. The transform is
/// R20 and is not built here, so no assist is reachable from this type — there is nothing to call.
/// </para>
///
/// <para><b>The one seeded direction, and why it is not a transform.</b> Going to free-form from a
/// goal block when free-form holds <i>nothing yet</i> seeds it with the goal block's compiled text
/// (R15 b2's non-assist residue). Going back returns the retained free-form draft byte-identical,
/// because retention outranks seeding: a seed is what an empty shape starts from, never what a
/// written one is overwritten with.</para>
/// </remarks>
public sealed class ComposerDraft
{
    private readonly Dictionary<string, string> _goalValues = new(StringComparer.Ordinal);
    private readonly Dictionary<string, IReadOnlyList<string>> _templateValues = new(StringComparer.Ordinal);
    private readonly List<ComposerAttachment> _attachments = [];

    private string _freeForm = string.Empty;
    private bool _freeFormWritten;

    /// <summary>The active shape. Free-form is the default, and needs no template anywhere.</summary>
    public ComposerShape Shape { get; private set; } = ComposerShape.FreeForm;

    /// <summary>
    /// The editor's own held source text — what the operator typed, and nothing else (Ruling 66).
    /// </summary>
    /// <remarks>
    /// <para><b>Why this exists.</b> <see cref="ComposerCompiler.Compile"/>'s output additionally
    /// carries an attachment's file content and, for a template draft, the template's own fixed
    /// prose — neither of which the operator wrote. <see cref="LeaseDerivation"/> must read only what
    /// the operator authored, so it is derived from this, never from the compiled prompt.</para>
    ///
    /// <para><b>Shape-scoped, not shape-summed.</b> A draft retains every shape's content at once
    /// (see the class remarks), but only the <i>active</i> shape's content is what the operator is
    /// currently looking at and editing — a mention left behind in a shape the operator switched away
    /// from must not silently widen the lane's write scope.</para>
    /// </remarks>
    public string SourceText => Shape switch
    {
        // ONE EDITOR (DESIGN.md SC1; Ruling 66): the message is the editor's text in both the
        // free-form and the goal-block form. The goal-block form adds three structure lines
        // beneath the editor (Goal · Done when · Not in scope), which are decorations of the turn,
        // never a second source of mentions.
        ComposerShape.FreeForm or ComposerShape.GoalBlock => _freeForm,
        ComposerShape.Template => string.Join('\n', _templateValues.Values.SelectMany(values => values)),
        _ => throw new ArgumentOutOfRangeException(nameof(Shape), Shape, "unknown composer shape"),
    };

    /// <summary>
    /// The compiled turn's shape (Ruling 75; Addendum D §A9's <b>P</b>): a goal block only when the
    /// editor is on the goal-block form <i>and</i> Goal and Done when are both non-blank.
    /// </summary>
    /// <remarks>
    /// Blank is whitespace, exactly as <see cref="SpawnContract.Validate"/> reads a field — so the
    /// shape and the validator can never disagree about whether a line was written.
    /// </remarks>
    public TurnShape TurnShape =>
        Shape == ComposerShape.GoalBlock && Written(GoalBlockFields.GoalKey) && Written(GoalBlockFields.DoneWhenKey)
            ? TurnShape.GoalBlock
            : TurnShape.Message;

    /// <summary>The retained free-form text — the message, in every form but a template's.</summary>
    public string FreeFormText => _freeForm;

    /// <summary>
    /// The three goal-block fields the session and the compile step supply — never the operator,
    /// per prompt (Rulings 56, 63, 72): the tier is the compile step's projection
    /// (<see cref="ComposerCompiler.Tier"/>), the cap and the budget are the session's
    /// (<see cref="Ceilings"/>).
    /// </summary>
    public static IReadOnlyList<string> SessionSuppliedGoalFields { get; } =
        [GoalBlockFields.TierKey, GoalBlockFields.FanOutCapKey, GoalBlockFields.BudgetKey];

    /// <summary>The goal-block fields a prompt carries: the three content lines.</summary>
    /// <remarks>
    /// Derived by subtraction from <see cref="GoalBlockFields.All"/> rather than typed out, so a
    /// seventh contract field would appear here rather than silently miss the form, and so the
    /// contract's own list stays the one home of the wire names (DM7).
    /// </remarks>
    public static IReadOnlyList<string> PerPromptGoalFields { get; } =
        [.. GoalBlockFields.All.Except(SessionSuppliedGoalFields, StringComparer.Ordinal)];

    /// <summary>
    /// The session's ceilings the compiled block reads (Ruling 56; ADR-0033 §3's <c>ceilings</c>
    /// snapshot): the fan-out ceiling and the budget cap. Set by the shell from the session's
    /// config; an unbound draft carries the config's own defaults.
    /// </summary>
    public Ceilings Ceilings { get; private set; } = Composer.Ceilings.Default;

    /// <summary>Binds the session's ceilings (Ruling 56: one home, never a per-prompt override).</summary>
    public void UseSessionSettings(SessionConfig config)
    {
        ArgumentNullException.ThrowIfNull(config);
        Ceilings = new Ceilings(config.FanOutCeiling, config.BudgetCap);
    }

    /// <summary>The template this draft is bound to, when its shape is a template.</summary>
    public string? TemplateId { get; private set; }

    /// <summary>
    /// The operator's tier override for this prompt (Addendum D §A9 R4; §A11: the tier is the one
    /// decoration Prepare may override), or null — the rule's value stands. The only stored tier:
    /// it becomes a <c>tier</c> row with <c>source: operator</c> at Send.
    /// </summary>
    public string? TierOverride { get; private set; }

    /// <summary>
    /// The task class this prompt chose (Ruling 70: changeable per prompt; the session's default is
    /// untouched), or null — the session's default applies with <c>source: session-default</c>.
    /// </summary>
    public string? TaskClassChoice { get; private set; }

    /// <summary>Overrides the tier (T0 / T1 / T2), or clears the override with null. Anything else is refused and the prior value stands (§A9 input 14).</summary>
    /// <exception cref="ArgumentOutOfRangeException">The value is not one of the three tiers.</exception>
    public void OverrideTier(string? tier)
    {
        if (tier is not null && !ComposerCompiler.IsTier(tier))
        {
            throw new ArgumentOutOfRangeException(nameof(tier), tier, "an override is one of T0, T1, T2; the rule's value stands");
        }

        TierOverride = tier;
    }

    /// <summary>Chooses this prompt's task class, or returns to the session's default with null or blank.</summary>
    public void ChooseTaskClass(string? taskClass) =>
        TaskClassChoice = string.IsNullOrWhiteSpace(taskClass) ? null : taskClass.Trim();

    /// <summary>
    /// The account label this turn chose on the composer's picker (Ruling 105 (2)), or null — the
    /// session's <c>DefaultAccount</c> applies. A choice becomes an <c>account</c> row with
    /// <c>source: operator</c> at Send; it never changes the session's default.
    /// </summary>
    public string? AccountChoice { get; private set; }

    /// <summary>Chooses this turn's account by label, or returns to the session's default with null or blank.</summary>
    public void ChooseAccount(string? accountLabel) =>
        AccountChoice = string.IsNullOrWhiteSpace(accountLabel) ? null : accountLabel.Trim();

    /// <summary>The goal-block field values, by wire name.</summary>
    public IReadOnlyDictionary<string, string> GoalValues => _goalValues;

    /// <summary>The template field values, by field name.</summary>
    public IReadOnlyDictionary<string, IReadOnlyList<string>> TemplateValues => _templateValues;

    /// <summary>Everything attached to this send, in the order it was affirmed.</summary>
    public IReadOnlyList<ComposerAttachment> Attachments => _attachments;

    /// <summary>Replaces the free-form text.</summary>
    public void SetFreeFormText(string text)
    {
        ArgumentNullException.ThrowIfNull(text);
        _freeForm = text;
        _freeFormWritten = true;
    }

    /// <summary>Sets one goal-block field by its wire name.</summary>
    public void SetGoalValue(string fieldName, string value)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(fieldName);
        ArgumentNullException.ThrowIfNull(value);

        if (!GoalBlockFields.All.Contains(fieldName, StringComparer.Ordinal))
        {
            throw new ArgumentOutOfRangeException(
                nameof(fieldName), fieldName, "the goal block names no such field");
        }

        // THE CONTROL FOR "A PER-PROMPT TIER, CAP OR BUDGET FIELD" (DESIGN.md's anti-goal; the
        // plan's fail condition): a form that tried to write one here fails loudly rather than
        // rendering a box the rulings retired.
        if (SessionSuppliedGoalFields.Contains(fieldName, StringComparer.Ordinal))
        {
            throw new ArgumentOutOfRangeException(
                nameof(fieldName), fieldName,
                "not a per-prompt field: the tier is the compile step's projection and the fan-out cap "
                + "and budget are session settings (Rulings 56, 63, 72)");
        }

        _goalValues[fieldName] = value;
    }

    /// <summary>Binds this draft to a catalog template and switches to the template shape.</summary>
    public void UseTemplate(string templateId)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(templateId);
        TemplateId = templateId;
        Shape = ComposerShape.Template;
    }

    /// <summary>Sets one template field's values, in the caller's order — the order is the content.</summary>
    public void SetTemplateValue(string fieldName, IReadOnlyList<string> values)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(fieldName);
        ArgumentNullException.ThrowIfNull(values);
        _templateValues[fieldName] = [.. values];
    }

    /// <summary>Adds an affirmed attachment.</summary>
    public void Add(ComposerAttachment attachment)
    {
        ArgumentNullException.ThrowIfNull(attachment);
        _attachments.Add(attachment);
    }

    /// <summary>Switches shape, retaining every shape's own content.</summary>
    /// <param name="shape">The shape to move to.</param>
    /// <param name="goalBlockText">
    /// The compiled goal-block text, supplied by the caller so this type never compiles anything
    /// itself. Used only to seed an <i>empty</i> free-form draft on the goal-block to free-form
    /// direction; ignored otherwise.
    /// </param>
    public void SwitchTo(ComposerShape shape, string? goalBlockText = null)
    {
        if (shape == ComposerShape.FreeForm
            && Shape == ComposerShape.GoalBlock
            && !_freeFormWritten
            && goalBlockText is not null)
        {
            _freeForm = goalBlockText;
            _freeFormWritten = true;
        }

        Shape = shape;
    }

    /// <summary>
    /// The goal block this draft declares, as a value the one validation mechanism can read.
    /// </summary>
    /// <remarks>
    /// <para>The three content lines are nullable, exactly as <see cref="GoalBlock"/> is: a blank
    /// field must be expressible so the form engine can name it, rather than being defaulted into
    /// something that validates.</para>
    ///
    /// <para><b>The other three are supplied, never typed (Rulings 56, 63, 72).</b> The tier is
    /// <see cref="ComposerCompiler.Tier"/>'s projection over the same two inputs the shape and the
    /// lease read (Addendum D §A9); the cap is <c>min(cap(tier), ceiling)</c> (Ruling 64); the budget
    /// is the session's cap or <see cref="RunBudget.SubscriptionBounded"/>. So a send with nothing
    /// typed for them is complete, and <see cref="SpawnContract.Validate"/> stays byte-identical.</para>
    /// </remarks>
    public GoalBlock ToGoalBlock()
    {
        // THE RULE, OR THE OPERATOR'S OVERRIDE (§A9 R4) — the same answer Projection.Project gives
        // for this draft's envelope, so the block a render shows and the block the send projects agree.
        var tier = TierOverride ?? ComposerCompiler.Tier(TurnShape, LeaseDerivation.Patterns(this.SourceText)).Tier;

        return new GoalBlock(
            Text(GoalBlockFields.GoalKey),
            Text(GoalBlockFields.DoneWhenKey),
            Text(GoalBlockFields.NotInScopeKey),
            tier,
            ComposerCompiler.EffectiveFanOut(tier, Ceilings.FanOutCeiling),
            Ceilings.BudgetCap ?? RunBudget.SubscriptionBounded);

        string? Text(string field) => Written(field) ? _goalValues[field] : null;
    }

    /// <summary>Whether a goal-block field holds anything but whitespace — the validator's own reading of "written".</summary>
    private bool Written(string field) =>
        _goalValues.TryGetValue(field, out var value) && !string.IsNullOrWhiteSpace(value);
}

/// <summary>
/// The session's two ceilings as the compiled block reads them (Ruling 56): the fan-out ceiling and
/// the budget cap, <c>null</c> for <i>bounded by the subscription</i> (Ruling 72).
/// </summary>
public sealed record Ceilings(int FanOutCeiling, RunBudget? BudgetCap)
{
    /// <summary>What an unbound draft carries: the config's own defaults, never a compile-time invention.</summary>
    public static readonly Ceilings Default = new(SessionConfig.DefaultFanOutCeiling, null);
}
