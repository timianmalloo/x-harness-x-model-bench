namespace AiDe.Core.Tests.AgentPlane;

/// <summary>
/// The shipped <c>--self-test</c> flag, actually run.
/// </summary>
/// <remarks>
/// <para><b>DC-104: a new control's first run is evidence about the control, not about the code.</b>
/// A self-test that has never been executed is a claim; running it here makes each guard's firing a
/// standing assertion rather than a note in a report nobody re-reads. The guards mirror the ones
/// <c>src/AiDe.Mcp/Program.cs</c> covers, plus the three this client adds — the frame cap,
/// backpressure, and a measurement that degrades to "not recorded".</para>
///
/// <para><b>One process launch, not one per guard.</b> The probe costs about a second to start; a
/// theory over nine labels would pay that nine times for the same information (CE: the cheapest
/// minute is the one never billed). Attribution is kept by naming the missing guard in the failure.
/// </para>
/// </remarks>
public sealed class AcpProbeSelfTestTests
{
    /// <summary>
    /// Enumerated here so deleting a guard from the probe reddens a test, rather than quietly
    /// shrinking what "every guard fires" means.
    /// </summary>
    private static readonly string[] Guards =
    [
        "a notification is not answered",
        "an inbound request with id 0 is answered, not read as a notification",
        "an unknown method is answered, not ignored",
        "one malformed frame does not kill the loop",
        "an over-long line is refused and the splitter resynchronizes",
        "the handshake refuses a protocol version that is not the pinned one",
        "a relative session cwd never reaches the wire",
        "a full event queue applies backpressure and drops nothing",
        "an unmeasured latency reads",
    ];

    [Fact]
    public void EveryGuardTheAcpClientShipsFiresWhenTheSelfTestIsRun()
    {
        var (exitCode, stderr) = AcpProbeLauncher.Run("--self-test");

        Assert.DoesNotContain("FAIL", stderr, StringComparison.Ordinal);
        Assert.Equal(0, exitCode);
        Assert.Contains("every guard fires", stderr, StringComparison.Ordinal);

        Assert.All(Guards, guard => Assert.True(
            stderr.Contains("ok    " + guard, StringComparison.Ordinal),
            $"the self-test did not report the guard '{guard}'. It reported:\n{stderr}"));
    }
}
