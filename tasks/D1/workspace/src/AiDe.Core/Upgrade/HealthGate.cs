using System.Diagnostics;

namespace AiDe.Core.Upgrade;

/// <summary>One named check and what it found.</summary>
/// <remarks>
/// The detail is not decoration. "The upgrade failed" is not actionable; "expected schema v4, found
/// v3" is, and it is the difference between a rollback someone can explain and one they can only
/// observe.
/// </remarks>
public sealed record HealthCheck(string Name, bool Passed, string Detail)
{
    public static HealthCheck Pass(string name, string detail) => new(name, true, detail);

    public static HealthCheck Fail(string name, string detail) => new(name, false, detail);
}

/// <summary>A gate run: whether it passed, what it ran, and how long it took.</summary>
public sealed record HealthGateResult(bool Passed, IReadOnlyList<HealthCheck> Checks, TimeSpan Duration);

/// <summary>One check the gate will run.</summary>
public sealed record GateStep(string Name, Func<HealthCheck> Run);

/// <summary>
/// The fast subset that decides whether a freshly migrated store may be kept.
/// </summary>
/// <remarks>
/// <para><b>Fast is the specification, not an aspiration.</b> Full restore/replay equality is
/// asynchronous verification — P1-PERF measured a 50k-edge replay against a 15-minute RTO while this
/// gate has a 60-second budget. Putting the slow check inside the fast gate is the contradiction the
/// council review caught in the v1 architecture, so the budget is <b>enforced</b>: a gate that
/// merely documented one would pass a fifteen-minute replay and the contradiction would be back.</para>
///
/// <para><b>It stops at the first failure.</b> Later checks assume earlier ones held — an integrity
/// sample over a store whose schema check just failed reports nonsense — so continuing produces a
/// cascade whose first entry is the only real one.</para>
///
/// <para><b>It reports what it ran.</b> A gate's green result is evidence that the gate passed, not
/// that its contents passed. Naming every check is what makes the difference inspectable rather than
/// a matter of trust.</para>
/// </remarks>
public sealed class HealthGate(TimeSpan budget)
{
    public HealthGateResult Run(IReadOnlyList<GateStep> steps)
    {
        ArgumentNullException.ThrowIfNull(steps);

        var watch = Stopwatch.StartNew();
        var results = new List<HealthCheck>(steps.Count);

        foreach (var step in steps)
        {
            // Checked before each step rather than only after: the budget is about how long the
            // whole gate may take, and a check started at 59 seconds can still overrun it.
            if (watch.Elapsed >= budget)
            {
                results.Add(HealthCheck.Fail(
                    "budget", $"the gate exceeded its {budget.TotalSeconds:0.###}s budget"));
                return new HealthGateResult(false, results, watch.Elapsed);
            }

            var check = step.Run();
            results.Add(check);

            if (!check.Passed)
            {
                return new HealthGateResult(false, results, watch.Elapsed);
            }
        }

        // Checked once more at the end, so a single long-running step cannot pass by finishing the
        // list before anyone looked at the clock.
        if (watch.Elapsed >= budget)
        {
            results.Add(HealthCheck.Fail(
                "budget", $"the gate exceeded its {budget.TotalSeconds:0.###}s budget"));
            return new HealthGateResult(false, results, watch.Elapsed);
        }

        return new HealthGateResult(true, results, watch.Elapsed);
    }
}
