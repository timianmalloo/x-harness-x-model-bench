namespace AiDe.Core.AgentPlane;

/// <summary>The run lifecycle's stages — spec §5.3.</summary>
/// <remarks>
/// An enum rather than an open string, and for the opposite reason <see cref="RunEvent.Kind"/> is a
/// string: kinds arrive from an adapter that may invent one, whereas the stage list is <i>this</i>
/// product's own lifecycle. A stage nobody defined is a bug in the plane, not an additive protocol
/// change, so a compile break is the right answer.
/// </remarks>
public enum RunStage
{
    /// <summary>Stage 0 — triage (CT24). Always runs; it is what decides the rest.</summary>
    Triage,

    /// <summary>Stage 1 — graph-backed plan, emitted via <c>plan_submit</c>.</summary>
    Plan,

    /// <summary>Stage 2 — reviewer lanes from the persona roster, with their veto semantics.</summary>
    Council,

    /// <summary>Stage 3 — spawns per approved plan.</summary>
    Dispatch,

    /// <summary>Stage 4 — arbitrate seams and decisions.</summary>
    Steward,

    /// <summary>Stage 5 — converge and close.</summary>
    Converge,
}

/// <summary>
/// Stage-0 triage: whether this run skips plan and council on its way to dispatch — spec §5.3 and
/// R2's third bullet (line 362).
/// </summary>
/// <remarks>
/// <para><b>The decision is made from what the block declares, and nothing else.</b> §5.3 phrases
/// the skip as "a T0/T1 run (no fan-out, no loop, no gate)". <see cref="GoalBlockFields.All"/> is
/// the whole of a goal block, and it carries <b>no loop and no gate field</b> — so the two inputs
/// that exist are the tier and the fan-out cap. Guessing at a loop from a goal string would be
/// inventing a value that decides whether a run gets reviewed. <b>The trigger to revisit this is a
/// goal block that gains a field for either</b>; until then a run whose shape has a loop or a gate is
/// declared at a tier that does not skip, which is the discipline CT19 already asks for.</para>
///
/// <para><b>A missing tier or cap does not skip.</b> Absence degrades toward <i>more</i> ceremony,
/// never less: an unreadable block must not be the cheapest way to avoid a council. It is also
/// unreachable in practice — <see cref="SpawnContract"/> refuses such a block before any spawn — so
/// this is the second wall, not the first.</para>
///
/// <para><b>What "zero council lanes and zero plan artifacts" means here.</b> Phase 1 has no
/// conductor, so nothing produces either. The skip is therefore expressed as the stages the run
/// passes: on the skip path <see cref="RunStage.Plan"/> and <see cref="RunStage.Council"/> are
/// absent, so there is no stage that could produce one. A test that wants the counts measured rather
/// than implied reads them off the store after the run really dispatches.</para>
/// </remarks>
/// <param name="SkipsPlanAndCouncil">Whether Stage 0 short-circuits to dispatch.</param>
/// <param name="Stages">The stages this run passes, in lifecycle order. Always includes dispatch.</param>
/// <param name="Reason">Why — the half a log line needs, so a skip is a recorded decision.</param>
public sealed record RunTriage(bool SkipsPlanAndCouncil, IReadOnlyList<RunStage> Stages, string Reason)
{
    /// <summary>The tiers §5.3 names as eligible for the Stage-0 skip.</summary>
    public static readonly IReadOnlyList<string> SkipEligibleTiers = ["T0", "T1"];

    private static readonly RunStage[] SkipPath = [RunStage.Triage, RunStage.Dispatch, RunStage.Steward, RunStage.Converge];

    private static readonly RunStage[] FullPath =
        [RunStage.Triage, RunStage.Plan, RunStage.Council, RunStage.Dispatch, RunStage.Steward, RunStage.Converge];

    /// <summary>Triages one goal block.</summary>
    public static RunTriage For(GoalBlock block)
    {
        ArgumentNullException.ThrowIfNull(block);

        var tier = block.Tier?.Trim();

        if (string.IsNullOrEmpty(tier))
        {
            return Full("the goal block declares no tier, and an unreadable block is not a reason to skip review");
        }

        if (!SkipEligibleTiers.Contains(tier, StringComparer.OrdinalIgnoreCase))
        {
            return Full($"tier '{tier}' is not one of {string.Join('/', SkipEligibleTiers)}, so plan and council stand");
        }

        if (block.FanOutCap is not { } cap)
        {
            return Full("the goal block declares no fan-out cap, so how wide this run may go is unknown");
        }

        if (cap > 0)
        {
            return Full($"tier '{tier}' would skip, but the block declares a fan-out cap of {cap}; §5.3's skip is for a run that does not fan out");
        }

        return new RunTriage(
            true,
            SkipPath,
            $"tier '{tier}' with no fan-out: Stage 0 satisfies it with a single lane, so plan and council are skipped");
    }

    private static RunTriage Full(string reason) => new(false, FullPath, reason);
}
