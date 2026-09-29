using AiDe.Core.AgentPlane;
using AiDe.Core.Sessions;

namespace AiDe.Core.Presentation.Composer;

/// <summary>One field-level reason a draft cannot be sent. The field is a member, not prose.</summary>
/// <param name="Field">The field's own wire name.</param>
/// <param name="Message">Why the send is blocked on it.</param>
public sealed record ComposerFieldError(string Field, string Message);

/// <summary>
/// The generic form engine: which fields block a send, for any shape.
/// </summary>
/// <remarks>
/// <para><b>The goal-block re-base is one mechanism (Ruling 26b), and this is the whole of it.</b>
/// For a goal-block draft this method <i>calls</i> <see cref="SpawnContract.Validate"/> and maps its
/// result. It does not re-implement the rule, restate the field list, or hold a second opinion about
/// what a complete goal block is — so "the form engine and the spawn contract name the same field
/// set for every input" is true by construction rather than by agreement, and
/// <c>TheFormEngineAndTheSpawnContractNameOneFieldSet</c> is the observation of it.</para>
///
/// <para><b>A second definition of goal-block validity is the defect this shape exists to prevent.</b>
/// It would be invisible: both would pass the happy path, and they would disagree only on the input
/// nobody wrote a test for.</para>
/// </remarks>
public static class ComposerFormEngine
{
    /// <summary>Every reason this draft cannot be sent, at once. Empty means it can.</summary>
    /// <param name="draft">The draft to check.</param>
    /// <param name="template">The bound template, required only for a template draft.</param>
    public static IReadOnlyList<ComposerFieldError> Validate(ComposerDraft draft, PromptTemplate? template = null)
    {
        ArgumentNullException.ThrowIfNull(draft);

        return draft.Shape switch
        {
            // Free-form has no required field. A prompt is what the operator typed, and S1 says this
            // path works with no template anywhere in it.
            ComposerShape.FreeForm => [],

            ComposerShape.GoalBlock =>
                [.. SpawnContract.Validate(draft.ToGoalBlock())
                    .Select(error => new ComposerFieldError(error.Field, error.Message))],

            ComposerShape.Template => ValidateTemplate(draft, template),

            _ => throw new ArgumentOutOfRangeException(nameof(draft), draft.Shape, "unknown composer shape"),
        };
    }

    private static IReadOnlyList<ComposerFieldError> ValidateTemplate(ComposerDraft draft, PromptTemplate? template)
    {
        if (template is null)
        {
            throw new ArgumentNullException(
                nameof(template), "a template draft cannot be validated without the template it names");
        }

        var errors = new List<ComposerFieldError>();

        foreach (var field in template.Fields)
        {
            var values = draft.TemplateValues.TryGetValue(field.Name, out var declared)
                ? declared.Where(v => !string.IsNullOrWhiteSpace(v)).ToList()
                : [];

            if (field.Required && values.Count == 0)
            {
                errors.Add(new ComposerFieldError(
                    field.Name,
                    $"the template field '{field.Name}' is required and is empty"));
                continue;
            }

            // `min` is carried by template-schema/1 and compared HERE — the loader validated that it
            // is well-formed and deliberately did not count items against it (F4 gates it, not FT).
            if (field.Min is { } min && values.Count > 0 && values.Count < min)
            {
                errors.Add(new ComposerFieldError(
                    field.Name,
                    $"the template field '{field.Name}' declares a minimum of {min} items and has {values.Count}"));
            }
        }

        return errors;
    }
}
