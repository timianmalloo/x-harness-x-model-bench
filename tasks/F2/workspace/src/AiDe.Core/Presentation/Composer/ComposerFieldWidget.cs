using AiDe.Core.AgentPlane;
using AiDe.Core.Sessions;

namespace AiDe.Core.Presentation.Composer;

/// <summary>The widget one composer field renders as — the inventory Ruling 33 fixed.</summary>
public enum ComposerFieldWidget
{
    /// <summary>A single-line native input. No editor instance.</summary>
    Text,

    /// <summary>Multi-line prose, in the composer's editor with its extension set.</summary>
    LongText,

    /// <summary>An ordered list of values, as native rows. No editor instance.</summary>
    List,

    /// <summary>A closed choice, as a native select. No editor instance.</summary>
    Enum,

    /// <summary>A request/token pair, as two native number inputs. No editor instance.</summary>
    Budget,

    /// <summary>Mention chips, in the composer's editor with its completion source.</summary>
    Mentions,
}

/// <summary>
/// Which widget a field renders as, and which of them get an editor instance (Ruling 33).
/// </summary>
/// <remarks>
/// <para><b>Ruling 33 is the whole content of this type.</b> <see cref="ComposerFieldWidget.Mentions"/>
/// and <see cref="ComposerFieldWidget.LongText"/> render in the composer's editor with the
/// composer's extension set; <see cref="ComposerFieldWidget.Text"/>,
/// <see cref="ComposerFieldWidget.List"/>, <see cref="ComposerFieldWidget.Enum"/> and
/// <see cref="ComposerFieldWidget.Budget"/> are native controls with <b>no editor instance at
/// all</b>. That narrowed the vendored bundle, and it is why a per-field editor for the four native
/// types is a defect rather than a preference.</para>
///
/// <para><b>The inventory spans two field vocabularies, and that is not an inconsistency.</b>
/// <c>template-schema/1</c> declares three field types (<see cref="TemplateFieldType"/>); the goal
/// block declares six named fields (<see cref="GoalBlockFields"/>). The widget set is the union of
/// what those two need — which is where <c>long-text</c>, <c>enum</c> and <c>budget</c> come from:
/// they are goal-block shapes, not template-schema types. Reading Ruling 33's list as a list of
/// template field types is the misreading this paragraph exists to prevent.</para>
/// </remarks>
public static class ComposerFieldWidgets
{
    /// <summary>Whether this widget is one of the two that gets an editor instance.</summary>
    public static bool RendersInEditorView(ComposerFieldWidget widget) =>
        widget is ComposerFieldWidget.Mentions or ComposerFieldWidget.LongText;

    /// <summary>The widget a declared template field renders as.</summary>
    public static ComposerFieldWidget ForTemplateField(TemplateField field)
    {
        ArgumentNullException.ThrowIfNull(field);

        return field.Type switch
        {
            TemplateFieldType.Mentions => ComposerFieldWidget.Mentions,
            TemplateFieldType.List => ComposerFieldWidget.List,
            TemplateFieldType.Text => ComposerFieldWidget.Text,
            _ => throw new ArgumentOutOfRangeException(
                nameof(field), field.Type, "template-schema/1 declares no such field type"),
        };
    }

    /// <summary>The widget a goal-block field renders as, by its wire name.</summary>
    /// <remarks>
    /// <c>goal</c>, <c>done_when</c> and <c>not_in_scope</c> are prose a person writes in sentences,
    /// so they take the editor; <c>tier</c> is a closed set; <c>fan_out_cap</c> is one integer; and
    /// <c>budget</c> is the request/token pair. Nothing here is a limit being enforced — Ruling 26c
    /// holds, and Phase 1 validates <c>fan_out_cap</c> and <c>budget</c> without enforcing them.
    /// </remarks>
    public static ComposerFieldWidget ForGoalBlockField(string fieldName)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(fieldName);

        return fieldName switch
        {
            GoalBlockFields.GoalKey or GoalBlockFields.DoneWhenKey or GoalBlockFields.NotInScopeKey
                => ComposerFieldWidget.LongText,
            GoalBlockFields.TierKey => ComposerFieldWidget.Enum,
            GoalBlockFields.FanOutCapKey => ComposerFieldWidget.Text,
            GoalBlockFields.BudgetKey => ComposerFieldWidget.Budget,
            _ => throw new ArgumentOutOfRangeException(
                nameof(fieldName), fieldName, "the goal block names no such field"),
        };
    }
}
