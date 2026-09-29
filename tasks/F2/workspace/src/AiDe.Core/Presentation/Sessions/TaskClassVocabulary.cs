namespace AiDe.Core.Presentation.Sessions;

/// <summary>One offered task class, and what choosing it decides for the operator.</summary>
/// <param name="Id">The cohort key, exactly as it is stored and compared.</param>
/// <param name="WhatItIs">
/// One line saying what work this class covers. <b>A consequence, not a mechanism</b> (RQ2): the
/// operator is choosing what their session will be compared against, and "a defaulted class ranks
/// in the wrong cohort" names a subsystem rather than an outcome.
/// </param>
public sealed record TaskClassOption(string Id, string WhatItIs);

/// <summary>
/// The task classes the New Session sheet offers.
/// </summary>
/// <remarks>
/// <para><b>Why a set at all (RQ1).</b> A task class's only use is exact string equality against a
/// cohort key, and it was collected through a free text box with no options, no placeholder and no
/// autocomplete. A typo there is worse than a default: <c>Leaderboard</c> scopes by record
/// equality, so one mistyped character forms a cohort of one, every facet fails its
/// <c>cohort &lt; 5</c> minimum and renders <i>Not Comparable</i>, the real cohort silently loses
/// the episode from its median, and the standing composer finds no predecessor so the trend renders
/// absent — on the one surface whose job is telling an agent whether it is improving. The shipped
/// helper text warned only about <i>defaulting</i>.</para>
///
/// <para><b>PROVISIONAL, and said so rather than implied.</b> A controlled vocabulary is already
/// owed to Phase 3 (<c>conductor-programme</c>, <c>LaneCohort</c>, ADR-0028) and the specification
/// section that would define it does not exist yet. These six are the set the reviewed design
/// artifact renders (<c>docs/mockups/session-front-door.html</c>), drawn from values observed in
/// this repository's own fixtures and specs — <c>feature</c> and <c>refactor</c> are the two that
/// appear in committed code. <b>This list is a rendering of a decision that has not been ratified,
/// not the decision.</b> When §8.4 lands, this type is where it lands, and the sheet does not
/// change.</para>
///
/// <para><b>Why the sheet still accepts a value from outside the list.</b>
/// <see cref="NewSessionSheetViewModel.TaskClass"/> stays a plain nullable string: a reopened
/// session, a test, and a future vocabulary all set it directly. The <i>sheet</i> offers only the
/// set, which is where the typo was being made. Narrowing the type would make today's provisional
/// list a contract, which is precisely the decision this list is not allowed to make.</para>
/// </remarks>
public static class TaskClassVocabulary
{
    /// <summary>What a wrong answer costs, in the operator's terms (RQ2).</summary>
    public const string Explanation =
        "A session's score is only ever compared against sessions of the same class. "
        + "Pick the one that matches the work.";

    /// <summary>The label for the unanswered state (RQ4). Never a bare asterisk, never colour alone.</summary>
    public const string RequiredLabel = "Required, no default";

    /// <summary>The label once a class is chosen (RQ4).</summary>
    public const string AnsweredLabel = "Answered";

    /// <summary>The reason a disabled Create carries beside itself (RQ5).</summary>
    public const string ChooseOneToCreate = "Choose a task class to create the session.";

    /// <summary>
    /// The rule itself, for a caller that ignored <c>CanCreate</c> and called <c>Create</c> anyway.
    /// </summary>
    /// <remarks>
    /// <b>A different audience from <see cref="ChooseOneToCreate"/>, which is why it is a different
    /// sentence.</b> RQ5's copy is what an operator reads beside a disabled button: short, and
    /// naming the field. An exception message is read by whoever wrote the call that should have
    /// checked first, and there the useful content is the contract (Ruling 19) rather than the next
    /// click. Collapsing the two would make one of them worse.
    /// </remarks>
    public const string NoDefaultRule =
        "It is required and has no default: a guessed class is indistinguishable from a chosen one "
        + "afterwards.";

    /// <summary>The offered set. Nothing here is a default; see the type's remarks.</summary>
    public static IReadOnlyList<TaskClassOption> Offered { get; } =
    [
        new("extraction", "Pull an existing behaviour out into its own shape."),
        new("feature", "Add a capability that did not exist."),
        new("defect", "Find a cause and repair its class."),
        new("migration", "Move a dependency, framework or schema forward."),
        new("review", "Read and judge without changing."),
        new("ui-feedback", "Elevate a surface against operator feedback."),
    ];
}
