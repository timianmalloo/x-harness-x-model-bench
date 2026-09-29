using AiDe.Core.Watcher;

namespace AiDe.Core.Tests.Watcher;

/// <summary>
/// LK-EGRESS-01..04 — the default-deny egress gate (ADR-0024 credential-backed-grading-egress). The claim is that nothing egresses
/// unless an explicit per-path opt-in enabled exactly that path.
/// </summary>
public sealed class EgressGateTests
{
    [Fact]
    public void Decide_ByDefault_IsBlocked()
    {
        var gate = new EgressGate();

        Assert.Equal(EgressDecision.Blocked, gate.Decide("hosted-grader"));
    }

    [Fact]
    public void Decide_AfterOptIn_IsAllowedForThatPathOnly()
    {
        var gate = new EgressGate();

        gate.OptIn("hosted-grader");

        Assert.Equal(EgressDecision.Allowed, gate.Decide("hosted-grader"));
        Assert.Equal(EgressDecision.Blocked, gate.Decide("telemetry-export"));
    }

    [Fact]
    public void Decide_AfterRevoke_ReturnsToBlocked()
    {
        var gate = new EgressGate();
        gate.OptIn("hosted-grader");

        gate.Revoke("hosted-grader");

        Assert.Equal(EgressDecision.Blocked, gate.Decide("hosted-grader"));
    }

    [Fact]
    public void Decide_EmptyPath_Throws()
    {
        var gate = new EgressGate();

        Assert.Throws<ArgumentException>(() => gate.Decide(""));
    }
}
