using System.Diagnostics;
using System.Runtime.Versioning;
using AiDe.Core.AgentPlane;

namespace AiDe.Core.Tests.AgentPlane;

/// <summary>
/// The runner's bound is on the <i>call</i>, not on the child's exit: a pipe held open by someone
/// other than the child cannot hold the caller.
/// </summary>
/// <remarks>
/// <para><b>Red-first.</b> Observed on <c>lane/conversation-cv1</c>, 2026-09-12: the App test host
/// hung for 30 minutes in <c>WorkbenchShell.Git</c> → <c>StreamReader.ReadToEnd()</c> during
/// <c>SessionIdentityReportsTheRealWorktreeTests.ANonRepository_ReportsAnUnknownBranch_NeverAGuess</c>
/// (managed stacks read with <c>dotnet-stack</c>). <c>git</c> had exited; its <c>WaitForExit(3000)</c>
/// bound sat <i>after</i> the read and never ran. End-of-stream on a pipe arrives when the <b>last
/// writer handle</b> closes, and that handle is not necessarily the child's — any process that
/// inherited it keeps the reader waiting for as long as it lives. The same shape sat in
/// <see cref="ProcessRunner.Run"/>: the exit was bounded, the <c>GetResult()</c> on the read was not.</para>
///
/// <para><b>The oracle.</b> A child that hands its standard output to a background process and
/// exits at once — <c>cmd /c start /b ping</c>, which keeps the pipe for seven seconds — must not
/// hold a runner whose bound is two seconds. The holder ends on its own, so the test leaves nothing
/// behind. The elapsed time is the assertion; the reason is on the result.</para>
/// </remarks>
[Trait("Platform", "Windows")]
[SupportedOSPlatform("windows")]
public sealed class ProcessRunnerBoundsTheReadTests
{
    [Fact]
    public void AStrangerHoldingTheOutputPipeCannotHoldTheCaller()
    {
        var runner = new ProcessRunner(TimeSpan.FromSeconds(2));
        var clock = Stopwatch.StartNew();

        var result = runner.Run(
            "cmd.exe",
            ["/c", "start /b ping -n 8 127.0.0.1 & echo the child said this"],
            Path.GetTempPath());

        clock.Stop();

        // The child exited immediately (exit 0); what it printed before handing the pipe on may or
        // may not have been read before the holder took over — the contract is the bound.
        Assert.True(clock.Elapsed < TimeSpan.FromSeconds(5),
            $"the call took {clock.Elapsed.TotalSeconds:F1} s against a 2 s bound: the read waited for the pipe's last holder, not the child");
        Assert.Equal(0, result.ExitCode);
        Assert.Contains("held open", result.StandardError, StringComparison.Ordinal);
    }
}
