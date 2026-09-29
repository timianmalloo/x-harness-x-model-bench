using AiDe.Core.AgentPlane;
using AiDe.Core.Presentation.Composer;
using AiDe.Core.Sessions;

namespace AiDe.Core.Tests.Composer;

/// <summary>
/// Addendum D §A9 as CV-1 exposes it on the compiler: a total function of <b>P</b> (a goal block
/// exists) and <b>L</b> (the distinct lease patterns), the cap function, the effective fan-out, the
/// settings line that never carries a numeral for an absent cap (Ruling 72), and the decoration
/// rows in SC2's one grammar. P-D1's fourteen inputs against <c>Projection.Project</c> are CV-2's;
/// these rows are the falsifiers of the four rule rows and of what the composer renders from them.
/// </summary>
public sealed class TheTierIsTheMechanicalRulesProjectionTests
{
    [Theory]
    [InlineData(TurnShape.Message, 0, "T0", "R0")]
    [InlineData(TurnShape.Message, 3, "T0", "R0")]   // a Message with three mentions is still T0 — lease ≠ tier
    [InlineData(TurnShape.GoalBlock, 0, "T1", "R1")]
    [InlineData(TurnShape.GoalBlock, 1, "T1", "R2")]
    [InlineData(TurnShape.GoalBlock, 2, "T2", "R3")]
    [InlineData(TurnShape.GoalBlock, 5, "T2", "R3")]
    public void TheRuleIsTotalOverPAndL(TurnShape shape, int leases, string tier, string rule)
    {
        var patterns = Enumerable.Range(0, leases).Select(i => $"src/{i}/**").ToList();

        var projection = ComposerCompiler.Tier(shape, patterns);

        Assert.Equal(tier, projection.Tier);
        Assert.Equal(rule, projection.Rule);
    }

    [Fact]
    public void TheRationaleNamesWhoFilledTheStructureAndHowManyLeases()
    {
        Assert.Equal("no goal block", ComposerCompiler.Tier(TurnShape.Message, []).Rationale);
        Assert.Equal("goal block filled by you, no write scope", ComposerCompiler.Tier(TurnShape.GoalBlock, []).Rationale);
        Assert.Equal("goal block filled by you, one lease", ComposerCompiler.Tier(TurnShape.GoalBlock, ["a/**"]).Rationale);
        Assert.Equal("goal block filled by you, 2 leases", ComposerCompiler.Tier(TurnShape.GoalBlock, ["a/**", "b/**"]).Rationale);
        Assert.Equal("goal block filled by the model, one lease", ComposerCompiler.Tier(TurnShape.GoalBlock, ["a/**"], "the model").Rationale);
    }

    [Fact]
    public void TheCapFunctionIsCt19sAndTheEffectiveFanOutNeverExceedsTheCeiling()
    {
        Assert.Equal(0, ComposerCompiler.CapOf("T0"));
        Assert.Equal(2, ComposerCompiler.CapOf("T1"));
        Assert.Equal(4, ComposerCompiler.CapOf("T2"));
        Assert.Throws<ArgumentOutOfRangeException>(() => ComposerCompiler.CapOf("T9"));

        Assert.Equal(2, ComposerCompiler.EffectiveFanOut("T1", 3));
        Assert.Equal(3, ComposerCompiler.EffectiveFanOut("T2", 3));
        Assert.Equal(0, ComposerCompiler.EffectiveFanOut("T2", 0));
        Assert.Equal(0, ComposerCompiler.EffectiveFanOut("T0", 3));

        // A negative ceiling is carried, never clamped: the contract refuses it at the send.
        Assert.Equal(-1, ComposerCompiler.EffectiveFanOut("T2", -1));
    }

    /// <summary>Ruling 72 condition (1): the absent cap reads as a state; the numerals int.MaxValue / long.MaxValue never appear.</summary>
    [Fact]
    public void TheSettingsLineReadsBoundedByYourSubscriptionWithNoNumeralForAnAbsentCap()
    {
        var line = ComposerCompiler.SettingsLine("T1", 3, null);

        Assert.Equal("fan-out cap 2 (ceiling 3) · budget: bounded by your subscription · from session settings", line);
        Assert.Equal(line, ComposerCompiler.SettingsLine("T1", 3, RunBudget.SubscriptionBounded));
        Assert.DoesNotContain(int.MaxValue.ToString(System.Globalization.CultureInfo.InvariantCulture), line, StringComparison.Ordinal);
        Assert.DoesNotContain(long.MaxValue.ToString(System.Globalization.CultureInfo.InvariantCulture), line, StringComparison.Ordinal);

        Assert.Equal(
            "T0 — the ceiling of 3 does not apply to this turn · budget: bounded by your subscription · from session settings",
            ComposerCompiler.SettingsLine("T0", 3, null));

        Assert.Equal(
            "fan-out cap 3 (ceiling 3) · budget: 40,000 tokens, 10 requests · cap enforced · from session settings",
            ComposerCompiler.SettingsLine("T2", 3, new RunBudget(10, 40_000)));
    }

    [Fact]
    public void TheDecorationRowsCarryOneGrammarForEveryTurn()
    {
        var draft = new ComposerDraft();
        draft.SwitchTo(ComposerShape.GoalBlock);
        draft.SetFreeFormText("Refactor the chain; touch only @src/AiDe.Core/Workbench/.\n");

        // A message (no goal block yet): class · tier T0 · lease read-only · message.
        var message = ComposerCompiler.Decorations(draft, AiDe.Core.Watcher.TaskClasses.FreeForm);
        // Ruling 105 (2): the grammar gains `account` — this turn's binding — after the shape (and the template, when one is bound).
        Assert.Equal(["class", "tier", "lease", "shape", "account"], message.Select(d => d.Name));
        Assert.Equal("free-form", message[0].Value);
        Assert.Equal("session-default", message[0].Source);
        Assert.Equal("no class ranks this turn", message[0].Reason);
        Assert.Equal("T0", message[1].Value);
        Assert.Equal(ComposerCompiler.ReadOnlyScope, message[2].Value);
        Assert.Equal("message", message[3].Value);

        // The same draft with Goal and Done when written: tier T1 by R2, the lease in full, goal block.
        draft.SetGoalValue(GoalBlockFields.GoalKey, "Refuse a newer schema with a report");
        draft.SetGoalValue(GoalBlockFields.DoneWhenKey, "a v2 envelope is refused and reported");
        var block = ComposerCompiler.Decorations(draft, "defect");
        Assert.Equal("defect", block[0].Value);
        Assert.Equal("T1", block[1].Value);
        Assert.Equal("goal block filled by you, one lease", block[1].Reason);
        Assert.Equal("src/AiDe.Core/Workbench/**", block[2].Value);
        Assert.Equal("from your mention", block[2].Reason);
        Assert.Equal("goal block", block[3].Value);

        // A template adds its row; nothing else moves.
        draft.UseTemplate("change-order");
        var templated = ComposerCompiler.Decorations(draft, "defect");
        Assert.Equal("template", templated[^2].Name);   // the template row precedes the account row (Ruling 105)
        Assert.Equal("account", templated[^1].Name);
        Assert.Equal("change-order", templated[^2].Value);
    }

    [Fact]
    public void ACompiledGoalBlockCarriesTheSessionsValuesAndTheMessage()
    {
        var draft = new ComposerDraft();
        draft.SwitchTo(ComposerShape.GoalBlock);
        draft.UseSessionSettings(new SessionConfig("s", "n", "w", DateTimeOffset.UnixEpoch, [new AccountRef("anthropic", "max")], new AccountRef("anthropic", "max"))
        {
            FanOutCeiling = 1,
            BudgetCap = new RunBudget(10, 40_000),
        });
        draft.SwitchTo(ComposerShape.GoalBlock);
        draft.SetGoalValue(GoalBlockFields.GoalKey, "g");
        draft.SetGoalValue(GoalBlockFields.DoneWhenKey, "d");
        draft.SetGoalValue(GoalBlockFields.NotInScopeKey, "n");
        draft.SetFreeFormText("touch @src/A/ and @src/B/\n");

        var block = draft.ToGoalBlock();

        Assert.Equal("T2", block.Tier);
        Assert.Equal(1, block.FanOutCap);   // min(cap(T2) = 4, ceiling 1)
        Assert.Equal(new RunBudget(10, 40_000), block.Budget);

        var text = ComposerCompiler.Compile(draft).Text;
        Assert.Contains("## fan_out_cap\n\n1\n", text, StringComparison.Ordinal);
        Assert.Contains("## message\n\ntouch @src/A/ and @src/B/\n", text, StringComparison.Ordinal);
    }

    /// <summary>A goal-block form whose block is a Message compiles to the message alone — the free-form bytes (Ruling 75).</summary>
    [Fact]
    public void AGoalBlockFormWithABlankGoalCompilesAsTheMessageAlone()
    {
        var draft = new ComposerDraft();
        draft.SwitchTo(ComposerShape.GoalBlock);
        draft.SetGoalValue(GoalBlockFields.NotInScopeKey, "the ADR");
        draft.SetFreeFormText("Explain the store.\n");

        Assert.Equal(TurnShape.Message, draft.TurnShape);
        Assert.Equal("Explain the store.\n", ComposerCompiler.Compile(draft).Text);
    }
}
