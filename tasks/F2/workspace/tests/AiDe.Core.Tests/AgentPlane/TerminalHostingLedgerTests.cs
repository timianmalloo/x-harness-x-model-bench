using System.Runtime.Versioning;
using AiDe.Core.AgentPlane;
using AiDe.Core.Dispatch;
using AiDe.Core.Facts;
using AiDe.Core.Terminal;

namespace AiDe.Core.Tests.AgentPlane;

/// <summary>
/// The falsification half of N7's "zero terminal hosting" claim: the counter that reads 0 after a
/// governed run is shown reading <b>1</b> when a terminal really is hosted.
/// </summary>
/// <remarks>
/// <para><b>Why this test is the evidence and the run is not.</b> A run reporting
/// <c>TerminalHostConstructions == 0</c> proves nothing on its own — a counter that can never
/// increment reports zero forever, and reads exactly like a correct absence. The claim only becomes
/// falsifiable once the same counter is observed going up for the case it exists to catch.</para>
///
/// <para><b>A real ConPTY session, not a fake.</b> The whole point is that the ledger sees the
/// production construction path. A double would prove the ledger can count something.</para>
/// </remarks>
[SupportedOSPlatform("windows")]
[Trait("Platform", "Windows")]
public sealed class TerminalHostingLedgerTests
{
    [Fact]
    public async Task AnOpenLedgerCountsARealTerminalHostConstruction()
    {
        using var ledger = TerminalHostingLedger.Open();

        Assert.Equal(0, ledger.Constructions);

        using var deadline = new CancellationTokenSource(TimeSpan.FromSeconds(60));
        var session = await ConPtyTerminalSession.StartAsync(
            new TerminalSessionRequest(
                SessionId: "ledger-falsification",
                Generation: 1,
                CommandLine: "cmd.exe",
                WorkingDirectory: Path.GetTempPath(),
                Columns: 80,
                Rows: 25,
                ProcessingClass: SessionProcessingClass.LocalOnly),
            deadline.Token);

        await using (session)
        {
            // THE OBSERVATION. Had the governed run hosted a terminal, its ledger would have read
            // this, not 0.
            Assert.Equal(1, ledger.Constructions);
        }
    }

    /// <summary>
    /// The other half of the pair (INV-0010): a session that ends is a completion, so
    /// <i>starts − completions</i> is the number of hosts still held — and it can be shown going
    /// 1 → 0 on the two end paths the runtime has.
    /// </summary>
    /// <remarks>
    /// <para><b>Why a counter and not a process list.</b> The census reads a host under a live App
    /// as <c>ours-live</c> whether the pane is working or ended (DC-156); the log carried 4,115
    /// starts and no ends. A ledger that counts both makes "still hosted" a subtraction a gate can
    /// read, from the product's own emissions.</para>
    /// <para><b>Exactly one completion per session.</b> A session whose child exits is then
    /// disposed — the App's tab-close path — and must complete <i>once</i>, or the subtraction
    /// undercounts what is held.</para>
    /// </remarks>
    [Fact]
    public async Task ALedgerCountsOneCompletionPerSession_OnDisposeAndOnChildExit()
    {
        using var ledger = TerminalHostingLedger.Open();
        using var deadline = new CancellationTokenSource(TimeSpan.FromSeconds(60));

        var disposed = await ConPtyTerminalSession.StartAsync(
            new TerminalSessionRequest(
                SessionId: "ledger-completion-disposed",
                Generation: 1,
                CommandLine: "cmd.exe",
                WorkingDirectory: Path.GetTempPath(),
                Columns: 80,
                Rows: 25,
                ProcessingClass: SessionProcessingClass.LocalOnly),
            deadline.Token);
        await disposed.DisposeAsync();

        Assert.Equal(1, ledger.Constructions);
        Assert.Equal(1, ledger.Completions);

        var exited = await ConPtyTerminalSession.StartAsync(
            new TerminalSessionRequest(
                SessionId: "ledger-completion-exited",
                Generation: 1,
                CommandLine: "cmd.exe /c exit 0",
                WorkingDirectory: Path.GetTempPath(),
                Columns: 80,
                Rows: 25,
                ProcessingClass: SessionProcessingClass.LocalOnly),
            deadline.Token);
        await using (exited)
        {
            await exited.WaitForExitAsync(deadline.Token);
            Assert.Equal(2, ledger.Completions);
        }

        // Disposing the exited session is the App's tab-close after an `exit`: no second completion.
        Assert.Equal(2, ledger.Constructions);
        Assert.Equal(2, ledger.Completions);
        Assert.Equal(0, ledger.Constructions - ledger.Completions);
    }

    /// <summary>
    /// A closed ledger stops counting, so "none happened while this ran" is bounded to the run.
    /// </summary>
    /// <remarks>
    /// An <see cref="System.Diagnostics.ActivityListener"/> is process-global. Without disposal the
    /// window would never close, and a later terminal in the same process would retroactively
    /// contradict a run that really did host none.
    /// </remarks>
    [Fact]
    public async Task AClosedLedgerNoLongerCounts()
    {
        var ledger = TerminalHostingLedger.Open();
        ledger.Dispose();

        using var deadline = new CancellationTokenSource(TimeSpan.FromSeconds(60));
        var session = await ConPtyTerminalSession.StartAsync(
            new TerminalSessionRequest(
                SessionId: "ledger-closed",
                Generation: 1,
                CommandLine: "cmd.exe",
                WorkingDirectory: Path.GetTempPath(),
                Columns: 80,
                Rows: 25,
                ProcessingClass: SessionProcessingClass.LocalOnly),
            deadline.Token);

        await using (session)
        {
            Assert.Equal(0, ledger.Constructions);
        }
    }
}
