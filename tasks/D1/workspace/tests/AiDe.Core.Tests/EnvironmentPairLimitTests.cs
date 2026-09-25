using AiDe.Core.Terminal;

namespace AiDe.Core.Tests;

/// <summary>
/// The environment limit is on <c>NAME=VALUE</c>, and the check compares the pair.
/// </summary>
/// <remarks>
/// <para><b>Bisected rather than looked up (2026-09-01).</b> A child was handed a controlled
/// environment and asked what it received — the parent's copy is not evidence, which is DC-027's own
/// generalisation. cmd.exe's boundary is identical at four name lengths:</para>
/// <code>
/// name len   max value   name + 1 + value
///        3       8,186              8,190
///       13       8,176              8,190
///       40       8,149              8,190
///      120       8,069              8,190
/// </code>
///
/// <para><b>Which makes a value-only comparison wrong above a 39-character name.</b> The scan used
/// <c>value.Length &gt; 8151</c>, so an 8,150-character value under a 40-character name passed the
/// check and was dropped by cmd.exe — a false clean from the control that exists to catch exactly
/// this class. Latent on the measured machine, whose longest name is 34 characters, and it stops
/// being latent as soon as something adds longer names.</para>
///
/// <para><b>The other half of the bisection is what did NOT turn up.</b> No total-block limit exists
/// below 13,010,087 wide characters on either delivery path — direct <c>CreateProcess</c> or a
/// <c>cmd.exe</c> shim. Both sessions had reasoned that adding nine variables risked a total-size
/// limit that spends one variable's budget on another; measurement says that limit does not bind at
/// any realistic scale, and the risk is per-pair only. Recorded here because a hazard that was
/// argued for and then measured away is worth as much as one that was found.</para>
/// </remarks>
public sealed class EnvironmentPairLimitTests
{
    /// <summary>Runs the whole-environment inspection against a controlled set of variables.</summary>
    /// <remarks>
    /// <c>Inspect</c> reads the process environment for its non-PATH scan, so the variables are set
    /// on this process and removed afterwards. Restoring in a <c>finally</c> matters: a leaked
    /// oversized variable would make every later test in the run see a dirty environment.
    /// </remarks>
    private static IReadOnlyList<string> InspectWith(params (string Name, string Value)[] variables)
    {
        foreach (var (name, value) in variables) Environment.SetEnvironmentVariable(name, value);

        try
        {
            return EnvironmentHealth.Inspect();
        }
        finally
        {
            foreach (var (name, _) in variables) Environment.SetEnvironmentVariable(name, null);
        }
    }

    [Fact]
    public void ALongNamedVariableOverThePairLimitIsReported()
    {
        // THE FALSE CLEAN. Value length 8,150 is under the old 8,151 threshold, so a value-only
        // comparison says healthy — and 40 + 1 + 8,150 = 8,191 is one past the measured cut-off, so
        // cmd.exe drops it. This is the case the previous check could not see.
        var name = new string('A', 40);

        var findings = InspectWith((name, new string('x', 8_150)));

        Assert.Contains(findings, f => f.Contains(name, StringComparison.Ordinal));
    }

    [Fact]
    public void AVariableExactlyAtThePairLimitIsNotReported()
    {
        // The boundary from the other side, so the check cannot pass by reporting everything. 40 + 1
        // + 8,149 = 8,190, which the measurement showed surviving intact.
        var name = new string('B', 40);

        var findings = InspectWith((name, new string('x', 8_149)));

        Assert.DoesNotContain(findings, f => f.Contains(name, StringComparison.Ordinal));
    }

    [Fact]
    public void AShortNamedVariableStillUsesTheSameRule()
    {
        // The case the old value-only check got right, kept so the fix cannot regress it while
        // fixing the long-name case.
        var name = new string('C', 3);

        var over = InspectWith((name, new string('x', 8_187)));   // 3 + 1 + 8,187 = 8,191
        var under = InspectWith((name, new string('x', 8_186)));  // 3 + 1 + 8,186 = 8,190

        Assert.Contains(over, f => f.Contains(name, StringComparison.Ordinal));
        Assert.DoesNotContain(under, f => f.Contains(name, StringComparison.Ordinal));
    }

    [Fact]
    public void TheConstantMatchesWhatWasMeasured()
    {
        // The four bisected points, as DATA. The first version of this test asserted
        // `CmdPairLimit - n - 1` against a helper that computed `CmdPairLimit - n - 1` — an
        // expression compared with itself, which passes for any constant whatsoever. That is DC-016
        // in a file whose whole subject is measuring rather than assuming.
        //
        // These four pairs came from a child process reporting what it received. If someone changes
        // CmdPairLimit, this fails and names the measurement it contradicts.
        (int Name, int MaxValue)[] measured = [(3, 8_186), (13, 8_176), (40, 8_149), (120, 8_069)];

        foreach (var (nameLength, maxValue) in measured)
        {
            Assert.Equal(
                EnvironmentHealth.CmdPairLimit,
                nameLength + 1 + maxValue);
        }
    }
}
