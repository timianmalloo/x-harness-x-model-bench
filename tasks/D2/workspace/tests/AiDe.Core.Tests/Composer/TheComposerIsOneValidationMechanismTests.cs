using AiDe.Core.AgentPlane;
using AiDe.Core.Presentation.Composer;
using AiDe.Core.Sessions;

namespace AiDe.Core.Tests.Composer;

/// <summary>
/// R15 and R19's composition clauses: one goal-block validation mechanism (Ruling 26b), the field
/// widget inventory (Ruling 33), per-shape draft retention (Ruling 26 cut iv), R15 b2's re-based
/// round trip (Ruling 34), the S1 free-form guard, and the deterministic compile.
/// </summary>
public sealed class TheComposerIsOneValidationMechanismTests
{
    private static GoalBlock Block(
        string? goal = "g", string? doneWhen = "d", string? notInScope = "n", string? tier = "T1",
        int? cap = 0, RunBudget? budget = null) =>
        new(goal, doneWhen, notInScope, tier, cap, budget ?? new RunBudget(10, 1000));

    /// <summary>A goal-block draft carrying the block's three content lines — the per-prompt set (Rulings 56, 63, 72).</summary>
    private static ComposerDraft GoalDraft(GoalBlock block)
    {
        var draft = new ComposerDraft();
        draft.SwitchTo(ComposerShape.GoalBlock);

        Set(GoalBlockFields.GoalKey, block.Goal);
        Set(GoalBlockFields.DoneWhenKey, block.DoneWhen);
        Set(GoalBlockFields.NotInScopeKey, block.NotInScope);

        return draft;

        void Set(string field, string? value)
        {
            if (value is not null)
            {
                draft.SetGoalValue(field, value);
            }
        }
    }

    /// <summary>
    /// Ruling 26b, re-scoped by Rulings 56, 63 and 72: the form still <i>calls</i> the contract, so
    /// the two name one field set for every per-prompt input — and the contract never names a
    /// field the operator cannot type, because the draft supplies the tier, the cap and the budget
    /// itself. <b>Red observed before the change</b>: a draft with nothing typed for <c>tier</c>
    /// reported <i>the goal block field 'tier' is required</i> (recorded in the Proof Pack).
    /// </summary>
    [Fact]
    public void Ruling26b_TheFormEngineAndTheSpawnContractNameOneFieldSetForEveryInput()
    {
        // Every combination of present/absent across the three per-prompt fields. If a second
        // definition of goal-block validity existed anywhere, it would disagree on one of these
        // eight inputs and nothing else would notice.
        for (var mask = 0; mask < 8; mask++)
        {
            var draft = GoalDraft(new GoalBlock(
                (mask & 1) != 0 ? "g" : null,
                (mask & 2) != 0 ? "d" : null,
                (mask & 4) != 0 ? "n" : null,
                Tier: null, FanOutCap: null, Budget: null));

            var contract = SpawnContract.Validate(draft.ToGoalBlock()).Select(e => e.Field).Order(StringComparer.Ordinal).ToList();
            var form = ComposerFormEngine.Validate(draft).Select(e => e.Field).Order(StringComparer.Ordinal).ToList();

            Assert.Equal(contract, form);

            // THE SESSION SUPPLIES WHAT THE OPERATOR NO LONGER TYPES: no input can be refused on
            // tier, fan_out_cap or budget, whatever is or is not written.
            Assert.DoesNotContain(contract, field => ComposerDraft.SessionSuppliedGoalFields.Contains(field, StringComparer.Ordinal));
        }
    }

    /// <summary>The control behind the anti-goal: a per-prompt tier, cap or budget cannot be written into a draft at all.</summary>
    [Theory]
    [InlineData("tier")]
    [InlineData("fan_out_cap")]
    [InlineData("budget")]
    public void Rulings56_63_72_ASessionSuppliedFieldIsRefusedOnTheDraft(string field)
    {
        var draft = new ComposerDraft();
        draft.SwitchTo(ComposerShape.GoalBlock);

        var refused = Assert.Throws<ArgumentOutOfRangeException>(() => draft.SetGoalValue(field, "x"));
        Assert.Contains("not a per-prompt field", refused.Message, StringComparison.Ordinal);
    }

    /// <summary>The positive send with nothing typed for tier, fan-out cap or budget: the block is complete from the session's values.</summary>
    [Fact]
    public void Rulings56_63_72_AGoalBlockWithNothingTypedForTierCapOrBudgetIsCompleteFromTheSession()
    {
        var draft = GoalDraft(Block());
        draft.SetFreeFormText("Rename the helper in @src/Payments/Money.cs.\n");

        Assert.Empty(ComposerFormEngine.Validate(draft));

        var block = draft.ToGoalBlock();
        Assert.Equal("T1", block.Tier);
        Assert.Equal(2, block.FanOutCap);
        Assert.True(block.Budget!.IsSubscriptionBounded);
        Assert.Empty(SpawnContract.Validate(block));
    }

    /// <summary>
    /// The two invalid-value rows the per-prompt form used to carry (a cap of −1, a budget of 0/0)
    /// moved with the values: they are the SESSION's now, and the contract refuses them at the
    /// send — the one validation mechanism still names the field (Ruling 26b), the composer never
    /// invents a second check.
    /// </summary>
    [Fact]
    public void Rulings56_63_72_ASessionCeilingOutOfRangeIsRefusedByTheContractAtTheSend()
    {
        var draft = GoalDraft(Block());
        draft.SetFreeFormText("Rename the helper in @src/Payments/Money.cs.\n");
        draft.UseSessionSettings(new SessionConfig("s", "n", "w", DateTimeOffset.UnixEpoch, [new AccountRef("anthropic", "max")], new AccountRef("anthropic", "max"))
        {
            FanOutCeiling = -1,
            BudgetCap = new RunBudget(0, 0),
        });

        // ONE MECHANISM: the form engine IS the contract for a goal block — it names the two
        // session values by their wire names, the same two the contract names, in the same order.
        var errors = SpawnContract.Validate(draft.ToGoalBlock());
        Assert.Equal(["fan_out_cap", "budget"], errors.Select(e => e.Field).ToList());
        Assert.Contains("a negative bound is not one", errors[0].Message, StringComparison.Ordinal);
        Assert.Contains("a spawn that can do nothing is a typo", errors[1].Message, StringComparison.Ordinal);
        Assert.Equal(errors.Select(e => (e.Field, e.Message)), ComposerFormEngine.Validate(draft).Select(e => (e.Field, e.Message)));

        // And the -1 was never clamped to a plausible 0 on the way (the mutation: Math.Max(0, ceiling)).
        Assert.Equal(-1, draft.ToGoalBlock().FanOutCap);
    }

    [Fact]
    public void Ruling26b_TheSpawnContractsOwnFourTestsAreUntouchedAndTheSixNamesStillHold()
    {
        // The composer re-bases onto the contract; it does not renegotiate it. The six names and the
        // absence of a lease among them are what the lease clause turns on.
        Assert.Equal(6, GoalBlockFields.All.Count);
        Assert.Equal(
            ["goal", "done_when", "not_in_scope", "tier", "fan_out_cap", "budget"],
            GoalBlockFields.All);
        Assert.DoesNotContain(GoalBlockFields.All, f => f.Contains("lease", StringComparison.OrdinalIgnoreCase));
    }

    [Fact]
    public void Ruling26c_TheGoalBlocksHintsRenderAsDeclaredRatherThanEnforced()
    {
        var text = ComposerCompiler.RenderGoalBlock(Block());

        Assert.Contains("declared, not enforced in Phase 1", text, StringComparison.Ordinal);
    }

    [Theory]
    [InlineData("goal", ComposerFieldWidget.LongText)]
    [InlineData("done_when", ComposerFieldWidget.LongText)]
    [InlineData("not_in_scope", ComposerFieldWidget.LongText)]
    [InlineData("tier", ComposerFieldWidget.Enum)]
    [InlineData("fan_out_cap", ComposerFieldWidget.Text)]
    [InlineData("budget", ComposerFieldWidget.Budget)]
    public void Ruling33_TheGoalBlockFieldsTakeTheWidgetsTheInventoryNames(string field, ComposerFieldWidget expected)
    {
        Assert.Equal(expected, ComposerFieldWidgets.ForGoalBlockField(field));
    }

    [Fact]
    public void Ruling33_OnlyMentionsAndLongTextGetAnEditorInstance()
    {
        Assert.True(ComposerFieldWidgets.RendersInEditorView(ComposerFieldWidget.Mentions));
        Assert.True(ComposerFieldWidgets.RendersInEditorView(ComposerFieldWidget.LongText));

        foreach (var native in new[]
                 {
                     ComposerFieldWidget.Text, ComposerFieldWidget.List,
                     ComposerFieldWidget.Enum, ComposerFieldWidget.Budget,
                 })
        {
            Assert.False(
                ComposerFieldWidgets.RendersInEditorView(native),
                $"a per-field editor was created for the native widget {native}");
        }
    }

    [Fact]
    public void Ruling33_ATemplatesDeclaredFieldsMapOntoTheSameInventory()
    {
        Assert.Equal(
            ComposerFieldWidget.Mentions,
            ComposerFieldWidgets.ForTemplateField(new TemplateField("who", TemplateFieldType.Mentions, true, null, null)));
        Assert.Equal(
            ComposerFieldWidget.List,
            ComposerFieldWidgets.ForTemplateField(new TemplateField("steps", TemplateFieldType.List, true, null, 2)));
        Assert.Equal(
            ComposerFieldWidget.Text,
            ComposerFieldWidgets.ForTemplateField(new TemplateField("title", TemplateFieldType.Text, true, null, null)));
    }

    [Fact]
    public void S1_FreeFormSendsWithNoTemplateCodeAnywhereInThePath()
    {
        var draft = new ComposerDraft();
        draft.SetFreeFormText("just a prompt\n");

        // No template is bound, none is passed, and validation does not consult one.
        Assert.Empty(ComposerFormEngine.Validate(draft));
        Assert.Null(draft.TemplateId);
        Assert.Equal("just a prompt\n", ComposerCompiler.Compile(draft).Text);
    }

    [Fact]
    public void Ruling26cutIV_SwitchingShapePreservesEachShapesOwnContent()
    {
        var draft = new ComposerDraft();
        draft.SetFreeFormText("the original free-form draft\n");

        draft.SwitchTo(ComposerShape.GoalBlock);
        draft.SetGoalValue(GoalBlockFields.GoalKey, "move the aggregate");

        draft.SwitchTo(ComposerShape.FreeForm, ComposerCompiler.RenderGoalBlock(draft.ToGoalBlock()));

        // BYTE-IDENTICAL. Retention outranks seeding: a seed is what an empty shape starts from,
        // never what a written one is overwritten with.
        Assert.Equal("the original free-form draft\n", draft.FreeFormText);

        draft.SwitchTo(ComposerShape.GoalBlock);
        Assert.Equal("move the aggregate", draft.GoalValues[GoalBlockFields.GoalKey]);
    }

    [Fact]
    public void Ruling34_GoalBlockToFreeFormSeedsTheCompiledTextWhenFreeFormHoldsNothingYet()
    {
        var draft = new ComposerDraft();
        draft.SwitchTo(ComposerShape.GoalBlock);
        draft.SetGoalValue(GoalBlockFields.GoalKey, "move the aggregate");

        var compiled = ComposerCompiler.RenderGoalBlock(draft.ToGoalBlock());
        draft.SwitchTo(ComposerShape.FreeForm, compiled);

        Assert.Equal(compiled, draft.FreeFormText);
        Assert.Contains("move the aggregate", draft.FreeFormText, StringComparison.Ordinal);
    }

    [Fact]
    public void Ruling34_ARoundTripLosesNoFieldAndCallsNoAssist()
    {
        var draft = new ComposerDraft();
        draft.SwitchTo(ComposerShape.GoalBlock);

        foreach (var field in ComposerDraft.PerPromptGoalFields)
        {
            draft.SetGoalValue(field, $"value of {field}");
        }

        var before = draft.GoalValues.ToDictionary(StringComparer.Ordinal);

        draft.SwitchTo(ComposerShape.FreeForm, ComposerCompiler.RenderGoalBlock(draft.ToGoalBlock()));
        draft.SwitchTo(ComposerShape.Template);
        draft.SwitchTo(ComposerShape.GoalBlock);

        Assert.Equal(before, draft.GoalValues);
    }

    [Fact]
    public void TheCompileIsDeterministicAcrossRepeatedRuns()
    {
        var draft = new ComposerDraft();
        draft.SwitchTo(ComposerShape.GoalBlock);

        // Set in one order; the renderer walks the TEMPLATE's declared order, not the caller's.
        foreach (var field in ComposerDraft.PerPromptGoalFields.Reverse())
        {
            draft.SetGoalValue(field, $"v-{field}");
        }

        draft.SetFreeFormText("the message, with @src/A/ mentioned\n");

        var first = ComposerCompiler.Compile(draft).Text;
        for (var i = 0; i < 20; i++)
        {
            Assert.Equal(first, ComposerCompiler.Compile(draft).Text);
        }

        Assert.StartsWith("## goal", first, StringComparison.Ordinal);

        // The six sections in §14.3's order, the three supplied ones from the session, then the message.
        var order = new[] { "## goal", "## done_when", "## not_in_scope", "## tier", "## fan_out_cap", "## budget", "## message" }
            .Select(h => first.IndexOf(h, StringComparison.Ordinal)).ToList();
        Assert.All(order, i => Assert.True(i >= 0));
        Assert.Equal(order.Order(), order);
        Assert.Contains("## tier\n\nT1\n", first, StringComparison.Ordinal);
        Assert.Contains(RunBudget.SubscriptionBoundedDisplay, first, StringComparison.Ordinal);
        Assert.EndsWith("## message\n\nthe message, with @src/A/ mentioned\n\n", first, StringComparison.Ordinal);
    }

    [Fact]
    public void ATemplateFormBlocksSendWithAFieldLevelErrorWhenARequiredFieldIsEmpty()
    {
        var template = new PromptTemplate(
            "launch", 1, "intent", "audience", "when", "why", "T1",
            [
                new TemplateField("title", TemplateFieldType.Text, Required: true, null, null),
                new TemplateField("steps", TemplateFieldType.List, Required: true, null, Min: 2),
            ],
            "# {{title}}\n{{#steps}}- {{.}}{{/steps}}\n",
            new Dictionary<string, string>());

        var draft = new ComposerDraft();
        draft.UseTemplate("launch");

        var errors = ComposerFormEngine.Validate(draft, template);
        Assert.Equal(["title", "steps"], errors.Select(e => e.Field).Order(StringComparer.Ordinal).Reverse());

        draft.SetTemplateValue("title", ["Ship it"]);
        draft.SetTemplateValue("steps", ["one"]);

        var minError = Assert.Single(ComposerFormEngine.Validate(draft, template));
        Assert.Equal("steps", minError.Field);
        Assert.Contains("minimum of 2", minError.Message, StringComparison.Ordinal);

        draft.SetTemplateValue("steps", ["one", "two"]);
        Assert.Empty(ComposerFormEngine.Validate(draft, template));
        Assert.Equal("# Ship it\n- one\n- two\n", ComposerCompiler.Compile(draft, template).Text);
    }

    [Fact]
    public void TheDraftSurvivesARestartThroughTheStoreRatherThanAReInstantiatedModel()
    {
        var root = Path.Combine(Path.GetTempPath(), "aide-draft", Guid.NewGuid().ToString("N"));
        Directory.CreateDirectory(root);

        try
        {
            var draft = new ComposerDraft();
            draft.SetFreeFormText("a draft that must outlive the process\n");
            draft.SwitchTo(ComposerShape.GoalBlock);
            draft.SetGoalValue(GoalBlockFields.GoalKey, "survive a restart");

            new ComposerDraftStore(root).Save("s-0001", draft);

            // A NEW store instance over the same bytes, which is what a restart is.
            var restored = new ComposerDraftStore(root).Load("s-0001");

            Assert.NotNull(restored);
            Assert.Equal("a draft that must outlive the process\n", restored!.FreeFormText);
            Assert.Equal("survive a restart", restored.GoalValues[GoalBlockFields.GoalKey]);
            Assert.Equal(ComposerShape.GoalBlock, restored.Shape);

            // ONE-WAY. Mutating what came back does not reach the stored bytes, and nothing exposes a
            // reverse path: the store's Load returns a fresh instance every time.
            restored.SetFreeFormText("mutated downstream\n");
            var again = new ComposerDraftStore(root).Load("s-0001");
            Assert.Equal("a draft that must outlive the process\n", again!.FreeFormText);
            Assert.NotSame(restored, again);
        }
        finally
        {
            Directory.Delete(root, recursive: true);
        }
    }

    [Fact]
    public void TheDraftStoreWritesInsideTheIgnoredSidecarAndHoldsNoAttachmentContent()
    {
        using var fixture = new AttachmentFixture();
        var draft = new ComposerDraft();
        draft.SetFreeFormText("prompt\n");

        fixture.Gate().Offer(
            draft, [fixture.WriteInside("secret-note.md", "ATTACHMENT-BODY-MARKER\n")], attachEnabled: true);

        var store = new ComposerDraftStore(fixture.WorkspaceRoot);
        store.Save("s-0001", draft);

        Assert.Equal(
            Path.Combine(fixture.WorkspaceRoot, ".aide", "composer-drafts.json"),
            store.File);

        var persisted = File.ReadAllText(store.File);
        Assert.DoesNotContain("ATTACHMENT-BODY-MARKER", persisted, StringComparison.Ordinal);
    }
}
