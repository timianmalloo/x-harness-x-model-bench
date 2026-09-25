using System.ComponentModel;
using System.Runtime.InteropServices;
using System.Runtime.Versioning;
using Microsoft.Win32.SafeHandles;

namespace AiDe.Core.Terminal;

/// <summary>The Win32 surface the ConPTY runtime needs, and nothing else.</summary>
/// <remarks>
/// <para>Raw <c>DllImport</c> against <c>kernel32</c> rather than a Windows-targeted TFM, so
/// <c>AiDe.Core</c> stays <c>net10.0</c>. Retargeting the whole library to Windows in order to reach
/// four kernel functions would be the tail wagging the dog; the platform requirement is expressed
/// with <see cref="SupportedOSPlatformAttribute"/> instead.</para>
///
/// <para>Availability was established by <c>spikes/conpty-foundation</c> (create → resize → close,
/// HRESULT 0). This is the C# counterpart of that spike, and the same lifecycle.</para>
/// </remarks>
[SupportedOSPlatform("windows")]
internal static partial class ConPtyInterop
{
    internal const int STILL_ACTIVE = 259;

    private const uint EXTENDED_STARTUPINFO_PRESENT = 0x00080000;
    private const uint CREATE_UNICODE_ENVIRONMENT = 0x00000400;
    private const int STARTF_USESTDHANDLES = 0x00000100;

    /// <summary>Documented attribute id that binds a pseudo console to a new process.</summary>
    private static readonly IntPtr PROC_THREAD_ATTRIBUTE_PSEUDOCONSOLE = 0x00020016;

    [StructLayout(LayoutKind.Sequential)]
    internal struct Coord
    {
        public short X;
        public short Y;
    }

    [StructLayout(LayoutKind.Sequential)]
    internal struct StartupInfoEx
    {
        public StartupInfo StartupInfo;
        public IntPtr AttributeList;
    }

    [StructLayout(LayoutKind.Sequential, CharSet = CharSet.Unicode)]
    internal struct StartupInfo
    {
        public int cb;
        public IntPtr lpReserved;
        public IntPtr lpDesktop;
        public IntPtr lpTitle;
        public int dwX, dwY, dwXSize, dwYSize, dwXCountChars, dwYCountChars, dwFillAttribute, dwFlags;
        public short wShowWindow;
        public short cbReserved2;
        public IntPtr lpReserved2;
        public IntPtr hStdInput, hStdOutput, hStdError;
    }

    [StructLayout(LayoutKind.Sequential)]
    internal struct ProcessInformation
    {
        public IntPtr hProcess;
        public IntPtr hThread;
        public int dwProcessId;
        public int dwThreadId;
    }

    [StructLayout(LayoutKind.Sequential)]
    internal struct JobObjectBasicLimitInformation
    {
        public long PerProcessUserTimeLimit;
        public long PerJobUserTimeLimit;
        public uint LimitFlags;
        public UIntPtr MinimumWorkingSetSize;
        public UIntPtr MaximumWorkingSetSize;
        public uint ActiveProcessLimit;
        public UIntPtr Affinity;
        public uint PriorityClass;
        public uint SchedulingClass;
    }

    [StructLayout(LayoutKind.Sequential)]
    internal struct IoCounters
    {
        public ulong ReadOperationCount, WriteOperationCount, OtherOperationCount;
        public ulong ReadTransferCount, WriteTransferCount, OtherTransferCount;
    }

    [StructLayout(LayoutKind.Sequential)]
    internal struct JobObjectExtendedLimitInformation
    {
        public JobObjectBasicLimitInformation BasicLimitInformation;
        public IoCounters IoInfo;
        public UIntPtr ProcessMemoryLimit;
        public UIntPtr JobMemoryLimit;
        public UIntPtr PeakProcessMemoryUsed;
        public UIntPtr PeakJobMemoryUsed;
    }

    internal const uint JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x00002000;
    internal const int JobObjectExtendedLimitInformation_Class = 9;

    [LibraryImport("kernel32.dll", SetLastError = true)]
    internal static partial int CreatePseudoConsole(
        Coord size, SafeFileHandle input, SafeFileHandle output, uint flags, out IntPtr console);

    [LibraryImport("kernel32.dll", SetLastError = true)]
    internal static partial int ResizePseudoConsole(IntPtr console, Coord size);

    [LibraryImport("kernel32.dll", SetLastError = true)]
    internal static partial void ClosePseudoConsole(IntPtr console);

    [LibraryImport("kernel32.dll", SetLastError = true)]
    [return: MarshalAs(UnmanagedType.Bool)]
    internal static partial bool CreatePipe(
        out SafeFileHandle readHandle, out SafeFileHandle writeHandle, IntPtr attributes, int size);

    [LibraryImport("kernel32.dll", SetLastError = true)]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static partial bool InitializeProcThreadAttributeList(
        IntPtr attributeList, int attributeCount, int flags, ref IntPtr size);

    [LibraryImport("kernel32.dll", SetLastError = true)]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static partial bool UpdateProcThreadAttribute(
        IntPtr attributeList, uint flags, IntPtr attribute, IntPtr value, IntPtr size,
        IntPtr previousValue, IntPtr returnSize);

    [LibraryImport("kernel32.dll", SetLastError = true)]
    internal static partial void DeleteProcThreadAttributeList(IntPtr attributeList);

    [LibraryImport("kernel32.dll", EntryPoint = "CreateProcessW", SetLastError = true,
        StringMarshalling = StringMarshalling.Utf16)]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static partial bool CreateProcess(
        string? applicationName, ref char commandLine, IntPtr processAttributes,
        IntPtr threadAttributes, [MarshalAs(UnmanagedType.Bool)] bool inheritHandles,
        uint creationFlags, IntPtr environment, string? currentDirectory,
        ref StartupInfoEx startupInfo, out ProcessInformation processInformation);

    [LibraryImport("kernel32.dll", SetLastError = true)]
    [return: MarshalAs(UnmanagedType.Bool)]
    internal static partial bool CloseHandle(IntPtr handle);

    [LibraryImport("kernel32.dll", SetLastError = true)]
    [return: MarshalAs(UnmanagedType.Bool)]
    internal static partial bool GetExitCodeProcess(IntPtr process, out int exitCode);

    [LibraryImport("kernel32.dll", SetLastError = true)]
    [return: MarshalAs(UnmanagedType.Bool)]
    internal static partial bool TerminateProcess(IntPtr process, uint exitCode);

    [LibraryImport("kernel32.dll", SetLastError = true, StringMarshalling = StringMarshalling.Utf16)]
    internal static partial IntPtr CreateJobObjectW(IntPtr attributes, string? name);

    [LibraryImport("kernel32.dll", SetLastError = true)]
    [return: MarshalAs(UnmanagedType.Bool)]
    internal static partial bool SetInformationJobObject(
        IntPtr job, int infoClass, ref JobObjectExtendedLimitInformation info, int length);

    [LibraryImport("kernel32.dll", SetLastError = true)]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static partial bool AssignProcessToJobObject(IntPtr job, IntPtr process);

    /// <summary>
    /// Puts <paramref name="process"/> into <paramref name="job"/>, and throws when that did not
    /// happen.
    /// </summary>
    /// <remarks>
    /// <para><b>The import above is <c>private</c> so this is the only way to reach it.</b> Both
    /// shipped call sites used to discard the boolean, and a discarded boolean is the whole defect:
    /// the job exists, the process is outside it, containment silently did not happen, and every
    /// test still passes. Measured on the pre-fix code against a job whose object had been closed —
    /// the call returned <c>false</c>, set <c>ERROR_INVALID_HANDLE</c> (6), raised nothing, and left
    /// the child running uncontained.</para>
    ///
    /// <para><b>Not a fourth spelling.</b> This is the check this repository had already written
    /// three times and used at neither shipped C# site:
    /// <c>spikes/extraction-containment/Sandbox.cs:86-87</c>,
    /// <c>docs/ai-forward-pack/scripts/bounded_process.py:125-127</c> and <c>:224-226</c>.</para>
    /// </remarks>
    /// <exception cref="Win32Exception">The assign failed, carrying the operating system's reason.</exception>
    internal static void AssignProcessToJob(IntPtr job, IntPtr process)
    {
        if (!AssignProcessToJobObject(job, process))
        {
            throw new Win32Exception(Marshal.GetLastWin32Error(), "AssignProcessToJobObject failed");
        }
    }

    /// <summary>
    /// Starts a process attached to <paramref name="console"/>.
    /// </summary>
    /// <remarks>
    /// The attribute list is the fiddly part and the reason this is a helper rather than a call
    /// site: <c>InitializeProcThreadAttributeList</c> is invoked twice by design — once with a null
    /// buffer purely to learn the size it wants, then again to fill it. Its first call FAILS and
    /// sets <c>ERROR_INSUFFICIENT_BUFFER</c>, which is success for that call.
    /// </remarks>
    /// <summary>
    /// Builds the child's environment block: this process's, minus Windows Terminal's own
    /// variables, plus <paramref name="extra"/>.
    /// </summary>
    /// <remarks>
    /// <para>Sorted case-insensitively by name, which is the documented block convention, and
    /// terminated by a second null. Returns null when there is nothing extra to add AND nothing to
    /// strip, so that child inherits exactly as before and the common path is untouched.</para>
    ///
    /// <para><b><c>WT_*</c> never reaches a child (INV-0010, slice 0 — measured, not reasoned).</b>
    /// A process started from a Windows Terminal tab inherits <c>WT_SESSION</c>, <c>WT_PROFILE_ID</c>
    /// (and <c>WT_COM_CLSID</c>); a ConPTY session whose parent carries them is treated by Windows
    /// Terminal's agent host (<c>wta.exe → copilot.exe --acp --stdio</c>) as one of its own, and it
    /// attaches an agent session per shell — one <c>node higgsfield-mcp</c> + one console host,
    /// kept for Windows Terminal's lifetime. Four product-shaped sessions with the variables: four
    /// births in 40 s; the same four without: zero (2026-09-12, this repository's fifth straggler
    /// report — 111 → 291 such processes in a day, all counted as someone else's). A ConPTY child
    /// of ours is not a Windows Terminal tab, and this is the one place every such child is
    /// started, so the variables leave here. Everything else passes through (INV-0001).</para>
    ///
    /// <para><b>There is deliberately no total-size guard here, and the reason is measured.</b> An
    /// earlier version of this method refused past 32,647 characters, from a bisection that had
    /// measured <c>PATH</c> length and been written down as a block size — two different quantities,
    /// one named with the other's units. Re-measured properly: a <b>60,000-character non-PATH
    /// variable passes through a PowerShell-hosted launch intact</b>, while a <b>33,000-character
    /// PATH breaks it</b>. So the limit is not on the block at all; it is on <c>PATH</c>
    /// specifically, because PowerShell uses <c>PATH</c> to resolve the command it was asked to run.
    /// </para>
    ///
    /// <para><b>A guard here would refuse launches that work.</b> That is worse than no guard: a
    /// check that fires on correct behaviour gets switched off, and takes the real check with it.
    /// Oversized <c>PATH</c> is already reported by <c>EnvironmentHealth</c>, at a threshold far
    /// below the one that breaks PowerShell.</para>
    /// </remarks>
    internal static char[]? BuildEnvironmentBlock(IReadOnlyDictionary<string, string>? extra)
    {
        var merged = new SortedDictionary<string, string>(StringComparer.OrdinalIgnoreCase);
        var stripped = false;
        foreach (System.Collections.DictionaryEntry e in Environment.GetEnvironmentVariables())
        {
            var name = e.Key?.ToString();
            if (string.IsNullOrEmpty(name)) { continue; }
            if (IsWindowsTerminalVariable(name)) { stripped = true; continue; }
            merged[name] = e.Value?.ToString() ?? string.Empty;
        }

        if ((extra is null || extra.Count == 0) && !stripped) { return null; }

        foreach (var (name, value) in extra ?? new Dictionary<string, string>())
        {
            if (!string.IsNullOrEmpty(name) && !IsWindowsTerminalVariable(name)) { merged[name] = value ?? string.Empty; }
        }

        var builder = new System.Text.StringBuilder();
        foreach (var (name, value) in merged)
        {
            builder.Append(name).Append('=').Append(value).Append('\0');
        }

        builder.Append('\0');

        var block = new char[builder.Length];
        builder.CopyTo(0, block, 0, builder.Length);
        return block;
    }

    /// <summary>Windows Terminal's per-tab variables: <c>WT_SESSION</c>, <c>WT_PROFILE_ID</c>, <c>WT_COM_CLSID</c>, and any other <c>WT_</c> prefix.</summary>
    internal static bool IsWindowsTerminalVariable(string name) =>
        name.StartsWith("WT_", StringComparison.OrdinalIgnoreCase);

    internal static ProcessInformation StartAttachedProcess(
        IntPtr console, string commandLine, string? workingDirectory,
        IReadOnlyDictionary<string, string>? extraEnvironment = null)
    {
        var size = IntPtr.Zero;
        InitializeProcThreadAttributeList(IntPtr.Zero, 1, 0, ref size);

        var attributeList = Marshal.AllocHGlobal(size);
        try
        {
            if (!InitializeProcThreadAttributeList(attributeList, 1, 0, ref size))
            {
                throw new Win32Exception(Marshal.GetLastWin32Error(),
                    "InitializeProcThreadAttributeList failed");
            }

            if (!UpdateProcThreadAttribute(
                    attributeList, 0, PROC_THREAD_ATTRIBUTE_PSEUDOCONSOLE, console,
                    IntPtr.Size, IntPtr.Zero, IntPtr.Zero))
            {
                throw new Win32Exception(Marshal.GetLastWin32Error(),
                    "UpdateProcThreadAttribute(PSEUDOCONSOLE) failed");
            }

            // STARTF_USESTDHANDLES with all three handles left null, which is how Windows Terminal
            // starts its own clients (ConptyConnection.cpp, _LaunchAttachedClient). Without the
            // flag, CreateProcess hands a console-subsystem child DUPLICATES of this process's
            // standard handles whenever they are not console handles — bInheritHandles=false does
            // not stop it — so a child started from a process whose stdout is a pipe (every test
            // host; any launch under a redirected parent) writes its stdout into that pipe, not the
            // pseudo console it was attached to. Observed 2026-09-12: PowerShell's prompt bytes
            // inside the session-render probe's stdout, on the same line as a measurement
            // (ConPtyChildStandardHandlesTests). With the flag and null handles the child inherits
            // nothing and takes its standard handles from the pseudo console, as the App's own
            // window-subsystem process — which has no standard handles to duplicate — always did.
            var startup = new StartupInfoEx
            {
                StartupInfo = new StartupInfo { cb = Marshal.SizeOf<StartupInfoEx>(), dwFlags = STARTF_USESTDHANDLES },
                AttributeList = attributeList,
            };

            // CreateProcessW may WRITE to its command-line buffer, so it must be a mutable copy.
            // Passing a literal is a documented way to corrupt memory that usually appears to work.
            var mutable = $"{commandLine}\0".ToCharArray();

            // Null means inherit, which is what every caller did before an environment could be
            // supplied — so a session that adds nothing behaves exactly as it always has.
            var block = BuildEnvironmentBlock(extraEnvironment);
            var environment = IntPtr.Zero;
            if (block is not null)
            {
                environment = Marshal.AllocHGlobal(block.Length * sizeof(char));
                Marshal.Copy(block, 0, environment, block.Length);
            }

            try
            {
                if (!CreateProcess(
                        null, ref mutable[0], IntPtr.Zero, IntPtr.Zero, false,
                        EXTENDED_STARTUPINFO_PRESENT | CREATE_UNICODE_ENVIRONMENT,
                        environment, workingDirectory, ref startup, out var process))
                {
                    throw new Win32Exception(Marshal.GetLastWin32Error(),
                        $"CreateProcess('{commandLine}') failed");
                }

                return process;
            }
            finally
            {
                if (environment != IntPtr.Zero) { Marshal.FreeHGlobal(environment); }
            }
        }
        finally
        {
            DeleteProcThreadAttributeList(attributeList);
            Marshal.FreeHGlobal(attributeList);
        }
    }

    /// <summary>A job that kills everything in it when the last handle closes — the orphan reaper.</summary>
    /// <remarks>
    /// <c>JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE</c> is what makes orphan reaping survive AI-DE itself
    /// being killed: the handle closes when the process dies, however it dies, and Windows takes the
    /// children with it. A shutdown-path <c>TerminateProcess</c> would not run at all in that case.
    /// </remarks>
    internal static IntPtr CreateKillOnCloseJob()
    {
        var job = CreateJobObjectW(IntPtr.Zero, null);
        if (job == IntPtr.Zero)
        {
            throw new Win32Exception(Marshal.GetLastWin32Error(), "CreateJobObject failed");
        }

        var info = new JobObjectExtendedLimitInformation
        {
            BasicLimitInformation = new JobObjectBasicLimitInformation
            {
                LimitFlags = JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE,
            },
        };

        if (!SetInformationJobObject(
                job, JobObjectExtendedLimitInformation_Class, ref info,
                Marshal.SizeOf<JobObjectExtendedLimitInformation>()))
        {
            var error = Marshal.GetLastWin32Error();
            CloseHandle(job);
            throw new Win32Exception(error, "SetInformationJobObject(KILL_ON_JOB_CLOSE) failed");
        }

        return job;
    }

    internal static void ThrowIfFailed(int hresult, string what)
    {
        if (hresult != 0)
        {
            throw new Win32Exception(hresult, $"{what} failed with HRESULT 0x{hresult:X8}");
        }
    }
}
