using System.Runtime.InteropServices;
using System.Runtime.Versioning;
using AiDe.Core.Terminal;

namespace AiDe.Core.Tests;

/// <summary>
/// Launches <c>AiDe.Core.TerminalHost</c> in a console of its own and returns its verdict.
/// </summary>
/// <remarks>
/// <para>The helper exists so the containment and exit-path claims are made from a process that is
/// not the test host — an owner that can be killed, that can exit without disposing, whose job can
/// be watched from outside. It was first written on DC-014's premise that ConPTY needs the launcher
/// to own a <b>real console</b>; that premise was DC-164's mechanism (the child inherited the host's
/// redirected standard handles), and the runtime's channel works from a host with no console window
/// at all. <c>Process.Start</c> cannot set creation flags, so this is the one place a test needs
/// interop of its own.</para>
///
/// <para><b><c>CREATE_NO_WINDOW</c>, never <c>CREATE_NEW_CONSOLE</c> (DC-170).</b> A new console on
/// a machine whose default terminal is Windows Terminal is a Windows Terminal tab, and its agent
/// host attaches an agent session — a <c>copilot.exe</c> child and one <c>node.exe</c> MCP server —
/// to every tab and keeps them after the tab closes. Measured 2026-09-12: two helper launches, two
/// <c>node.exe</c> born, with or without <c>WT_SESSION</c> in the host; twenty-one tests headless,
/// none. <c>docs/ai-forward-pack/scripts/verify-no-new-console-launches.py</c> keeps it that way.</para>
///
/// <para>Shared rather than duplicated: two suites now need it, and a second hand-rolled copy of
/// <c>CreateProcessW</c> is the kind of thing that drifts silently.</para>
/// </remarks>
[SupportedOSPlatform("windows")]
internal static class TerminalHostLauncher
{
    /// <summary>The helper executable, built alongside the tests and found relative to them.</summary>
    /// <remarks>
    /// <b>The tests' own configuration, never "Release if it exists".</b> The helper is a project
    /// reference, so the test step builds it in the tests' configuration; an older rule preferred
    /// a Release helper whenever one was on disk, and on 2026-09-12 a Release helper built before
    /// DC-170's change sat beside a fresh Debug one — ten tests ran the stale binary and failed on
    /// an exit code the source no longer had. The helper that matches the assembly running the
    /// test is the one the test step just built; any other is a different program.
    /// </remarks>
    internal static string LocateHelper()
    {
        var root = Path.GetFullPath(Path.Combine(
            AppContext.BaseDirectory, "..", "..", "..", "..", "AiDe.Core.TerminalHost", "bin"));
        var configuration = ConfigurationOf(AppContext.BaseDirectory);
        var candidate = Path.Combine(root, configuration, "net10.0", "AiDe.Core.TerminalHost.exe");

        Assert.True(
            File.Exists(candidate),
            $"the terminal host helper was not built. Expected it at:\n  {candidate}\n"
            + "Build the solution rather than the test project alone.");

        return candidate;
    }

    /// <summary>The build configuration a test assembly's output directory names (<c>bin\Debug\…</c>).</summary>
    internal static string ConfigurationOf(string baseDirectory)
    {
        var parts = baseDirectory.Split(Path.DirectorySeparatorChar, Path.AltDirectorySeparatorChar);
        var bin = Array.LastIndexOf(parts, "bin");
        Assert.True(bin >= 0 && bin + 1 < parts.Length,
            $"the test assembly's directory carries no bin/<configuration> segment: {baseDirectory}");
        return parts[bin + 1];
    }

    /// <summary>
    /// Starts the helper in a headless console and waits for its verdict.
    /// </summary>
    /// <remarks>
    /// <c>Process.Start</c> cannot set creation flags, so this is the one place a test needs
    /// interop of its own.
    /// </remarks>
    internal static async Task<int> RunInNewConsoleAsync(
        string exe, string report, TimeSpan limit, string? mode = null,
        Func<int, Task>? afterExit = null)
    {
        const uint CREATE_NO_WINDOW = 0x08000000;
        const uint CREATE_UNICODE_ENVIRONMENT = 0x00000400;

        var startup = new NativeStartupInfo { cb = Marshal.SizeOf<NativeStartupInfo>() };
        // The mode is the second argument, so the existing one-argument call keeps its
        // meaning and the capture probe stays working unchanged.
        var arguments = mode is null ? $"\"{report}\"" : $"\"{report}\" \"{mode}\"";
        var commandLine = $"\"{exe}\" {arguments}\0".ToCharArray();

        // EVERYTHING THAT ALLOCATES IS INSIDE THE TRY, so the `finally` covers it.
        //
        // The job used to be created above this line, which left two throwing statements — the
        // `Assert.Fail` on a failed CreateProcessW, and now the checked assign — between the
        // creation of a handle and the only code that closes it. On those paths the job handle
        // leaked, and a leaked KILL_ON_JOB_CLOSE handle is worse than an ordinary one: the job
        // outlives the run, so the reaping it exists to do never happens.
        var job = IntPtr.Zero;
        var environment = IntPtr.Zero;
        NativeProcessInformation info = default;

        try
        {
            job = ConPtyInterop.CreateKillOnCloseJob();

            // The helper's own block is the runtime's (WT_* stripped, INV-0010 slice 0), so a
            // helper started from a Windows Terminal tab has the shape it has on a CI runner. Null
            // when there is nothing to strip: inherit, as before. The helper's ConPTY children are
            // scrubbed by the runtime itself; measured, that alone stops the births (4/4 → 0/4).
            var block = ConPtyInterop.BuildEnvironmentBlock(null);
            if (block is not null)
            {
                environment = Marshal.AllocHGlobal(block.Length * sizeof(char));
                Marshal.Copy(block, 0, environment, block.Length);
            }

            if (!CreateProcessW(
                    null, ref commandLine[0], IntPtr.Zero, IntPtr.Zero, false,
                    CREATE_NO_WINDOW | CREATE_UNICODE_ENVIRONMENT,
                    environment, Path.GetDirectoryName(exe), ref startup, out info))
            {
                Assert.Fail($"could not start the helper: Win32 error {Marshal.GetLastWin32Error()}");
            }

            // CHECKED. Discarding this answer is how containment silently does not happen: the job
            // exists, the helper is outside it, and the suite still reports green.
            ConPtyInterop.AssignProcessToJob(job, info.hProcess);

            using var process = System.Diagnostics.Process.GetProcessById(info.dwProcessId);
            using var deadline = new CancellationTokenSource(limit);
            await process.WaitForExitAsync(deadline.Token);

            // BEFORE the job is released. The helper's console hosts are in its job, so a count
            // taken after `finally` would find them killed by THIS launcher's containment and
            // report the product's exit path as clean for a reason that does not exist in the
            // product (INV-0010). The hook runs with the helper dead and the job still open.
            if (afterExit is not null)
            {
                await afterExit(info.dwProcessId);
            }

            return process.ExitCode;
        }
        catch (OperationCanceledException)
        {
            Assert.Fail("the terminal host helper did not exit within its deadline");
            return -1; // unreachable at runtime (Assert.Fail throws) but required: xunit 2.9's
                       // Assert.Fail is not [DoesNotReturn], so the compiler needs a value here (CS0161).
        }
        finally
        {
            // Zero-guarded because the throw can now arrive before any of these exists.
            if (info.hThread != IntPtr.Zero)
            {
                CloseHandle(info.hThread);
            }

            if (info.hProcess != IntPtr.Zero)
            {
                CloseHandle(info.hProcess);
            }

            if (job != IntPtr.Zero)
            {
                ConPtyInterop.CloseHandle(job);
            }

            if (environment != IntPtr.Zero)
            {
                Marshal.FreeHGlobal(environment);
            }
        }
    }

    [StructLayout(LayoutKind.Sequential)]
    private struct NativeStartupInfo
    {
        public int cb;
        public IntPtr lpReserved, lpDesktop, lpTitle;
        public int dwX, dwY, dwXSize, dwYSize, dwXCountChars, dwYCountChars, dwFillAttribute, dwFlags;
        public short wShowWindow, cbReserved2;
        public IntPtr lpReserved2, hStdInput, hStdOutput, hStdError;
    }

    [StructLayout(LayoutKind.Sequential)]
    private struct NativeProcessInformation
    {
        public IntPtr hProcess, hThread;
        public int dwProcessId, dwThreadId;
    }

    [DllImport("kernel32.dll", EntryPoint = "CreateProcessW", SetLastError = true, CharSet = CharSet.Unicode)]
    private static extern bool CreateProcessW(
        string? applicationName, ref char commandLine, IntPtr processAttributes,
        IntPtr threadAttributes, bool inheritHandles, uint creationFlags, IntPtr environment,
        string? currentDirectory, ref NativeStartupInfo startupInfo,
        out NativeProcessInformation information);

    [DllImport("kernel32.dll", SetLastError = true)]
    private static extern bool CloseHandle(IntPtr handle);
}
