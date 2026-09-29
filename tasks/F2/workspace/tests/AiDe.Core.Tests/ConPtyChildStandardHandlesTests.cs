using System.Runtime.InteropServices;
using System.Runtime.Versioning;
using System.Text;
using AiDe.Core.Dispatch;
using AiDe.Core.Facts;
using AiDe.Core.Terminal;
using Microsoft.Win32.SafeHandles;

namespace AiDe.Core.Tests;

/// <summary>
/// A ConPTY child writes to its pseudo console, never to the standard handles of the process that
/// started it.
/// </summary>
/// <remarks>
/// <para><b>Red-first.</b> Observed on <c>lane/conversation-cv1</c> at <c>7007e4ac</c>, 2026-09-12:
/// the session-render probe, started by the App test host with its standard output redirected to a
/// pipe, restored the operator's arrangement — which holds a terminal — and PowerShell's shell
/// integration bytes (<c>ESC ]133;B BEL</c>, the prompt) landed in the <i>probe's</i> stdout, on the
/// same line as the next measurement, so <c>restore (22:33:53Z replay):</c> no longer began a line
/// and the test failed on a race it could not name. Run directly with <c>&gt; file</c> the probe's
/// stdout carried the shell's bytes twice and its stderr carried PowerShell's CLIXML stream.</para>
///
/// <para><b>The mechanism.</b> <c>CreateProcess</c> with <c>bInheritHandles = false</c> and no
/// <c>STARTF_USESTDHANDLES</c> still hands a console-subsystem child duplicates of the parent's
/// standard handles when those are not console handles — a redirected parent's pipes reach the
/// child, and the pseudo console the child was attached to is not where its stdout goes. Windows
/// Terminal starts its clients with <c>dwFlags = STARTF_USESTDHANDLES</c> and all three handles
/// null for exactly this reason (<c>ConptyConnection.cpp</c>, <c>_LaunchAttachedClient</c>).</para>
///
/// <para><b>Why the App never showed it.</b> A window-subsystem process started from Explorer has
/// no standard handles, so there was nothing to duplicate. Every test host does have them, and every
/// test-spawned terminal inherited them. This is the DC-014 finding of 2026-08-26 seen from the
/// other side: the reason a <c>dotnet test</c> host's ConPTY child seemed "not attached" was that
/// its stdout was the host's redirected pipe, not the pseudo console.</para>
///
/// <para><b>The oracle.</b> The test host's own standard output is pointed at a pipe for the
/// duration, a child is started through the product's <see cref="ConPtyTerminalSession"/> and told
/// to echo a token, and the pipe is read. The token on the pipe is the defect; the token on the
/// session's <c>Output</c> channel is the contract. The handle is restored in <c>finally</c>
/// whatever happens.</para>
/// </remarks>
[Trait("Platform", "Windows")]
[SupportedOSPlatform("windows")]
public sealed class ConPtyChildStandardHandlesTests
{
    private const int STD_OUTPUT_HANDLE = -11;

    [Fact]
    public async Task AChildsStdoutIsThePseudoConsoleNotTheHostsRedirectedPipe()
    {
        var token = $"AIDE-STDOUT-LEAK-{Guid.NewGuid():N}";
        var previous = GetStdHandle(STD_OUTPUT_HANDLE);

        // Inheritable on purpose: the defect is a duplication CreateProcess performs on the parent's
        // behalf, and a non-inheritable handle would hide it by failing the duplication, not by
        // fixing the child. The child must not receive it because the flag says so, not because
        // the handle could not travel.
        var attributes = new SECURITY_ATTRIBUTES { nLength = Marshal.SizeOf<SECURITY_ATTRIBUTES>(), bInheritHandle = true };
        Assert.True(CreateInheritablePipe(out var pipeRead, out var pipeWrite, ref attributes, 0), "could not create the observation pipe");

        using (pipeRead)
        using (pipeWrite)
        {
            Assert.True(SetStdHandle(STD_OUTPUT_HANDLE, pipeWrite.DangerousGetHandle()), "could not point the host's stdout at the pipe");
            try
            {
                using var timeout = new CancellationTokenSource(TimeSpan.FromSeconds(30));
                await using var session = await ConPtyTerminalSession.StartAsync(
                    new TerminalSessionRequest(
                        SessionId: "stdout-leak",
                        Generation: 1,
                        CommandLine: $"cmd.exe /c echo {token}",
                        WorkingDirectory: Path.GetTempPath(),
                        Columns: 120,
                        Rows: 25,
                        ProcessingClass: SessionProcessingClass.LocalOnly),
                    timeout.Token);

                var onTheChannel = new StringBuilder();
                try
                {
                    while (!onTheChannel.ToString().Contains(token, StringComparison.Ordinal)
                        && await session.Output.WaitToReadAsync(timeout.Token))
                    {
                        while (session.Output.TryRead(out var chunk))
                        {
                            onTheChannel.Append(Encoding.UTF8.GetString(chunk.Bytes.Span));
                        }
                    }
                }
                catch (OperationCanceledException)
                {
                    // The channel is judged below; a silent channel is a finding, not a crash.
                }

                await session.DisposeAsync();

                // Nothing else in this process writes to handle 1 while the pipe is installed, so
                // the pipe holds exactly what the child (or nothing) put there.
                SetStdHandle(STD_OUTPUT_HANDLE, previous);
                pipeWrite.Dispose();
                var onThePipe = ReadAll(pipeRead);

                Assert.DoesNotContain(token, onThePipe, StringComparison.Ordinal);
                Assert.Contains(token, onTheChannel.ToString(), StringComparison.Ordinal);
            }
            finally
            {
                SetStdHandle(STD_OUTPUT_HANDLE, previous);
            }
        }
    }

    private static string ReadAll(SafeFileHandle pipeRead)
    {
        using var stream = new FileStream(pipeRead, FileAccess.Read, 4096, isAsync: false);
        using var reader = new StreamReader(stream, Encoding.UTF8, detectEncodingFromByteOrderMarks: false, leaveOpen: true);
        return reader.ReadToEnd();
    }

    [StructLayout(LayoutKind.Sequential)]
    private struct SECURITY_ATTRIBUTES
    {
        public int nLength;
        public IntPtr lpSecurityDescriptor;
        [MarshalAs(UnmanagedType.Bool)] public bool bInheritHandle;
    }

    [DllImport("kernel32.dll", SetLastError = true)]
    private static extern IntPtr GetStdHandle(int which);

    [DllImport("kernel32.dll", SetLastError = true)]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static extern bool SetStdHandle(int which, IntPtr handle);

    [DllImport("kernel32.dll", EntryPoint = "CreatePipe", SetLastError = true)]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static extern bool CreateInheritablePipe(
        out SafeFileHandle readHandle, out SafeFileHandle writeHandle, ref SECURITY_ATTRIBUTES attributes, int size);
}
