using AiDe.Core.AgentPlane;
using AiDe.Core.Presentation.Composer;

namespace AiDe.Core.Tests.Composer;

/// <summary>
/// Rulings 72, 73 and 75 at the render site: the compiled block declares a subscription-bounded
/// budget as a state rather than as two maximal numerals, and the turn's shape — Message or
/// Goal-block, read-only or write — is one projection over the draft that the send gate and the
/// lease line both read.
/// </summary>
/// <remarks>
/// <para><b>Red observed before the change</b> (recorded in <c>docs/proof/read-only-turn.md</c>):
/// <see cref="RenderGoalBlock"/> rendered <see cref="RunBudget.SubscriptionBounded"/> as
/// <c>requests: 2147483647, tokens: 9223372036854775807</c>, and no shape projection existed.</para>
/// </remarks>
public sealed class TheCompiledBlockRendersItsShapeTests
{
    private static GoalBlock Block(RunBudget budget) => new("g", "d", "n", "T1", 0, budget);

    /// <summary>Ruling 72 condition (1): the absent cap reads as a state, never as a plausible number.</summary>
    [Fact]
    public void ASubscriptionBoundedBudgetRendersAsTheDeclaredStateWithNoNumeral()
    {
        var text = ComposerCompiler.RenderGoalBlock(Block(RunBudget.SubscriptionBounded));

        var budgetSection = text[text.IndexOf("## " + GoalBlockFields.BudgetKey, StringComparison.Ordinal)..];

        Assert.Contains(RunBudget.SubscriptionBoundedDisplay, budgetSection, StringComparison.Ordinal);
        Assert.Equal("bounded by your subscription — not measured here", RunBudget.SubscriptionBoundedDisplay);
        Assert.DoesNotContain(int.MaxValue.ToString(System.Globalization.CultureInfo.InvariantCulture), budgetSection, StringComparison.Ordinal);
        Assert.DoesNotContain(long.MaxValue.ToString(System.Globalization.CultureInfo.InvariantCulture), budgetSection, StringComparison.Ordinal);
        Assert.DoesNotContain("requests:", budgetSection, StringComparison.Ordinal);
    }

    /// <summary>The control against over-narrowing: an enforced cap still renders its numbers.</summary>
    [Fact]
    public void AnEnforcedCapStillRendersItsTwoNumbers()
    {
        var text = ComposerCompiler.RenderGoalBlock(Block(new RunBudget(10, 1000)));

        Assert.Contains("requests: 10, tokens: 1000 (declared, not enforced in Phase 1)", text, StringComparison.Ordinal);
        Assert.DoesNotContain(RunBudget.SubscriptionBoundedDisplay, text, StringComparison.Ordinal);
    }

    /// <summary>
    /// Addendum D §A9's <b>P</b>: a goal block exists only when Goal and Done when are both non-blank
    /// (Ruling 75). Every other draft compiles as a Message — the free-form and template shapes
    /// included, until the compile step reads a template's structure (CV-2).
    /// </summary>
    [Theory]
    [InlineData("goal", "done", TurnShape.GoalBlock)]
    [InlineData("goal", null, TurnShape.Message)]
    [InlineData(null, "done", TurnShape.Message)]
    [InlineData("   ", "done", TurnShape.Message)]
    [InlineData("goal", "\t", TurnShape.Message)]
    [InlineData(null, null, TurnShape.Message)]
    public void AGoalBlockExistsOnlyWhenGoalAndDoneWhenAreBothNonBlank(string? goal, string? doneWhen, TurnShape expected)
    {
        var draft = new ComposerDraft();
        draft.SwitchTo(ComposerShape.GoalBlock);
        if (goal is not null)
        {
            draft.SetGoalValue(GoalBlockFields.GoalKey, goal);
        }

        if (doneWhen is not null)
        {
            draft.SetGoalValue(GoalBlockFields.DoneWhenKey, doneWhen);
        }

        Assert.Equal(expected, draft.TurnShape);
    }

    [Fact]
    public void AFreeFormDraftIsAMessageHoweverManyMentionsItCarries()
    {
        var draft = new ComposerDraft();
        draft.SetFreeFormText("look at @src/A/ and @src/B/ and @src/c.cs");

        Assert.Equal(TurnShape.Message, draft.TurnShape);
    }

    [Fact]
    public void ATemplateDraftIsAMessageUntilTheCompileStepReadsItsStructure()
    {
        var draft = new ComposerDraft();
        draft.UseTemplate("t1");
        draft.SetTemplateValue("notes", ["@src/A/"]);

        Assert.Equal(TurnShape.Message, draft.TurnShape);
    }

    /// <summary>
    /// Ruling 73: a Message is read-only whatever it mentions (lease ≠ tier, §A9 R0); a goal block
    /// with no derivable scope is read-only (R1); a goal block with a scope is a write (R2/R3).
    /// </summary>
    [Theory]
    [InlineData(TurnShape.Message, 0, true)]
    [InlineData(TurnShape.Message, 3, true)]
    [InlineData(TurnShape.GoalBlock, 0, true)]
    [InlineData(TurnShape.GoalBlock, 1, false)]
    [InlineData(TurnShape.GoalBlock, 2, false)]
    public void ReadOnlyIsAMessageOrAScopelessGoalBlock(TurnShape shape, int patterns, bool readOnly)
    {
        var derived = Enumerable.Range(0, patterns).Select(i => $"src/p{i}/**").ToList();

        Assert.Equal(readOnly, ComposerCompiler.IsReadOnly(shape, derived));
    }

    /// <summary>The lease line's two states: the read-only copy the spec names for no lease, or the patterns.</summary>
    [Fact]
    public void TheLeaseLineReadsReadOnlyOrThePatterns()
    {
        Assert.Equal("Lease: read-only — nothing will be written", ComposerCompiler.LeaseLine(null));
        Assert.Equal("Lease: src/A/**, src/b.cs", ComposerCompiler.LeaseLine(["src/A/**", "src/b.cs"]));
        Assert.Equal("Lease: " + ComposerCompiler.ReadOnlyScope, ComposerCompiler.LeaseLine(null));
    }
}
