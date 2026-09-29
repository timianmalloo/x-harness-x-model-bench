using System.Collections.Generic;
using System.Linq;
using AiDe.Core.AgentPlane;
using AiDe.Core.Presentation.Composer;
using AiDe.Core.Sessions;

namespace AiDe.Core.Tests.Sessions;

/// <summary>
/// FT clause 7, re-scoped by Rulings 56, 63 and 72 — the <c>goal-block</c> template's fields ARE
/// the per-prompt goal-block fields (the three content lines), and its hints do not read as
/// enforced.
/// </summary>
/// <remarks>
/// <para><b>Nothing renames on the wire.</b> R18 re-bases Addendum A's goal-block shape as this
/// template with zero behaviour change; a template that spelled a field differently would give the
/// send gate and <see cref="SpawnContract.Validate"/> two vocabularies for one thing.</para>
///
/// <para><b>Tier, fan-out cap and budget left the per-prompt set</b> (Rulings 56, 63, 72; CV-1).
/// The contract still names six fields (<see cref="GoalBlockFields.All"/>, unchanged); the three
/// the template does not declare are supplied by the compile step's projection and the session's
/// settings when the draft becomes a block. <b>Red observed before the change</b>
/// (<c>docs/proof/composer-as-conversation.md</c>): the template declared all six and
/// <c>TheTemplatesFieldsAreTheSameSetAsGoalBlockFields</c> held it to the contract's list.</para>
/// </remarks>
public sealed class GoalBlockTemplateTests
{
    private static PromptTemplate Template => TemplateCatalog.BuiltIn().Find("goal-block")!.Template!;

    [Fact]
    public void TheTemplatesFieldsAreTheSameSetAsGoalBlockFields()
    {
        Assert.Equal(
            ComposerDraft.PerPromptGoalFields.Order(StringComparer.Ordinal),
            Template.Fields.Select(f => f.Name).Order(StringComparer.Ordinal));
    }

    [Fact]
    public void TheTemplatesFieldsAreInTheOrderSpec143ListsThem()
    {
        Assert.Equal(ComposerDraft.PerPromptGoalFields, Template.Fields.Select(f => f.Name));
    }

    /// <summary>The control for a per-prompt tier, cap or budget field (DESIGN.md's anti-goal): none is declared, none is rendered.</summary>
    [Fact]
    public void TheTemplateDeclaresNoTierFanOutCapOrBudgetField()
    {
        Assert.Equal(3, ComposerDraft.PerPromptGoalFields.Count);
        Assert.Equal(6, GoalBlockFields.All.Count);

        foreach (var name in ComposerDraft.SessionSuppliedGoalFields)
        {
            Assert.DoesNotContain(Template.Fields, f => f.Name == name);
            Assert.DoesNotContain("{{" + name + "}}", Template.Body, StringComparison.Ordinal);
        }
    }

    [Fact]
    public void NoFieldHintClaimsAnythingIsEnforced()
    {
        foreach (var field in Template.Fields.Where(f => f.Hint is not null))
        {
            Assert.DoesNotContain("enforces", field.Hint!, StringComparison.OrdinalIgnoreCase);
            Assert.DoesNotContain("enforced", field.Hint!.Replace("not enforced", string.Empty, StringComparison.Ordinal), StringComparison.OrdinalIgnoreCase);
        }
    }

    [Fact]
    public void CompilingTheTemplateProducesThePerPromptWireNamesTheValidatorUses()
    {
        var values = ComposerDraft.PerPromptGoalFields.ToDictionary(
            name => name,
            name => (IReadOnlyList<string>)[$"a {name}"],
            StringComparer.Ordinal);

        var text = TemplateCompiler.Compile(Template, values);

        Assert.All(ComposerDraft.PerPromptGoalFields, name => Assert.Contains($"{name}: a {name}", text, StringComparison.Ordinal));
        Assert.All(ComposerDraft.SessionSuppliedGoalFields, name => Assert.DoesNotContain(name + ":", text, StringComparison.Ordinal));
    }
}
