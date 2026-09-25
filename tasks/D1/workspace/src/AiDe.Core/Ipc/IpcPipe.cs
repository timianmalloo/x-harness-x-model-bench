using System.IO.Pipes;
using System.Runtime.InteropServices;
using System.Runtime.Versioning;
using System.Security.AccessControl;
using System.Security.Principal;
using System.Security.Cryptography;
using System.Text;

namespace AiDe.Core.Ipc;

/// <summary>
/// The pipe name for a workspace, derived rather than configured.
/// </summary>
/// <remarks>
/// <para>Both ends must agree without talking first, so the name is a pure function of the workspace
/// path. Deriving it also keeps the path <b>out of the name</b>: pipe names are enumerable by any
/// process on the machine, and a name like <c>aide.C__Users_someone_clients_acme</c> would disclose
/// what a user is working on to anything that can list a directory.</para>
///
/// <para>Hashed lowercase-invariant because Windows paths are case-insensitive: the same workspace
/// reached as <c>C:\Work</c> and <c>c:\work</c> must be one daemon, not two racing for one store.</para>
/// </remarks>
public static class IpcPipeName
{
    /// <summary>The pipe name serving <paramref name="workspacePath"/>.</summary>
    public static string ForWorkspace(string workspacePath)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(workspacePath);

        var normalized = workspacePath
            .Replace('/', '\\')
            .TrimEnd('\\')
            .ToLowerInvariant();

        var digest = SHA256.HashData(Encoding.UTF8.GetBytes(normalized));

        // Half the digest: 128 bits is far beyond collision risk for the handful of workspaces one
        // machine holds, and a shorter name keeps diagnostics readable.
        return "aide." + Convert.ToHexString(digest, 0, 16).ToLowerInvariant();
    }
}

/// <summary>
/// One daemon per workspace, enforced by the operating system rather than by convention.
/// </summary>
/// <remarks>
/// <para>Two daemons on one workspace would be two writers to one store, each believing it owns the
/// epoch. Nothing above this notices — both would work perfectly, and the damage would appear later
/// as a fact store whose history has two authors. So the lock is taken <b>before</b> anything is
/// opened, and a daemon that cannot take it exits rather than degrading.</para>
///
/// <para>A named mutex rather than a lock file, because the kernel releases it when the holder dies
/// however it dies. A lock file outlives a killed process and needs staleness heuristics — which are
/// guesses about whether another process is alive, and wrong guesses here mean either a permanently
/// unopenable workspace or two writers.</para>
///
/// <para><b>Local, not Global.</b> The scope of the invariant is one user's session; a machine-wide
/// name would let one user's daemon block another's, which is a denial of service reachable by
/// opening a folder.</para>
/// </remarks>
[SupportedOSPlatform("windows")]
public sealed class WorkspaceLock : IDisposable
{
    /// <summary>Workspaces held by THIS process.</summary>
    /// <remarks>
    /// A Windows mutex is owned by a thread and is re-entrant: the same thread calling
    /// <c>WaitOne</c> twice succeeds both times. The kernel object therefore excludes a second
    /// <i>process</i> and silently permits a second holder inside this one — which matters directly,
    /// because ADR-0009 keeps an in-process daemon as a supported hosting mode. A lock that passes
    /// while providing nothing is worse than no lock: it reads as protection.
    /// </remarks>
    private static readonly HashSet<string> HeldHere = new(StringComparer.Ordinal);

    private readonly Mutex _mutex;
    private readonly string _key;
    private bool _released;

    private WorkspaceLock(Mutex mutex, string key)
    {
        _mutex = mutex;
        _key = key;
    }

    /// <summary>Takes the lock, or reports that another daemon already holds it.</summary>
    public static bool TryAcquire(string workspacePath, out WorkspaceLock? held)
    {
        var key = IpcPipeName.ForWorkspace(workspacePath);

        // In-process first, because the kernel mutex cannot answer this question.
        lock (HeldHere)
        {
            if (!HeldHere.Add(key))
            {
                held = null;
                return false;
            }
        }

        var mutex = new Mutex(initiallyOwned: false, $"Local\\{IpcPipeName.ForWorkspace(workspacePath)}.lock");

        try
        {
            // Zero timeout: this is a question, not a wait. A daemon that queued for the lock would
            // sit invisible until the other one exited, which looks exactly like a hang.
            if (!mutex.WaitOne(TimeSpan.Zero))
            {
                mutex.Dispose();
                lock (HeldHere)
                {
                    HeldHere.Remove(key);
                }

                held = null;
                return false;
            }
        }
        catch (AbandonedMutexException)
        {
            // The previous holder died without releasing. We now own it, and the workspace is ours:
            // an abandoned mutex means there is no other daemon, which is precisely the condition
            // the lock exists to establish.
            held = new WorkspaceLock(mutex, key);
            return true;
        }

        held = new WorkspaceLock(mutex, key);
        return true;
    }

    public void Dispose()
    {
        if (_released)
        {
            return;
        }

        _released = true;

        lock (HeldHere)
        {
            HeldHere.Remove(_key);
        }

        try
        {
            _mutex.ReleaseMutex();
        }
        catch (ApplicationException)
        {
            // Not the owning thread, or already released. Disposing below is the part that matters.
        }

        _mutex.Dispose();
    }
}

/// <summary>Creates pipe endpoints that only the workspace owner can reach.</summary>
/// <remarks>
/// <para><b>The ACL is the first of two controls, not the only one.</b> It stops another user's
/// process from connecting at all. The server still derives the peer's SID after connecting and
/// checks it, because defence that exists only in an access-control list is defence that disappears
/// the moment someone constructs a pipe by a different route — and because a control nothing
/// verifies is a control nobody notices losing.</para>
/// </remarks>
[SupportedOSPlatform("windows")]
public static class IpcPipeFactory
{
    /// <summary>A server instance whose ACL admits only the current user.</summary>
    public static NamedPipeServerStream CreateServer(string pipeName, int maxInstances)
    {
        var owner = WindowsIdentity.GetCurrent().User
            ?? throw new InvalidOperationException("the current identity has no user SID");

        var security = new PipeSecurity();

        // Exactly one rule. Nothing for Everyone, nothing for Authenticated Users, nothing for
        // Administrators: an administrator can already take ownership of anything, so naming them
        // adds no protection and does add a second party who can reach the workspace by default.
        security.AddAccessRule(new PipeAccessRule(
            owner, PipeAccessRights.ReadWrite | PipeAccessRights.CreateNewInstance, AccessControlType.Allow));

        return NamedPipeServerStreamAcl.Create(
            pipeName,
            PipeDirection.InOut,
            maxInstances,
            PipeTransmissionMode.Byte,
            // NOT CurrentUserOnly here: the framework refuses to combine it with an explicit
            // pipeSecurity, because it applies its own. The two express the same intent, and the
            // explicit rule is chosen because it is AUDITABLE — GetAccessControl reads it back, so
            // a test can assert what the ACL actually is rather than trusting a flag's reputation.
            PipeOptions.Asynchronous,
            inBufferSize: 0,
            outBufferSize: 0,
            security);
    }

    /// <summary>A client end for <paramref name="pipeName"/>.</summary>
    /// <remarks>
    /// <c>CurrentUserOnly</c> is the client-side half, and it defends the opposite direction from
    /// the server's ACL: the ACL stops another user reaching our daemon, while this stops us
    /// reaching *theirs*. Without it another user could create a pipe of the expected name first and
    /// harvest whatever a shell sent to what it believed was its own daemon.
    ///
    /// It appears only on this end because the framework refuses to combine it with the explicit
    /// server ACL — they are two spellings of one intent, and the server's is the one a test can
    /// read back.
    /// </remarks>
    public static NamedPipeClientStream CreateClient(string pipeName) =>
        new(".", pipeName, PipeDirection.InOut, PipeOptions.Asynchronous | PipeOptions.CurrentUserOnly);

    /// <summary>The SID of the user this process runs as — the workspace owner.</summary>
    public static string OwnerSid() =>
        WindowsIdentity.GetCurrent().User?.Value
        ?? throw new InvalidOperationException("the current identity has no user SID");

    /// <summary>
    /// Who is on the other end, established from the connection itself.
    /// </summary>
    /// <remarks>
    /// Both values come from the kernel, never from anything the peer sent. A peer that could state
    /// its own identity could state someone else's, which is the entire reason a capability binds to
    /// the connection rather than to a claim.
    /// </remarks>
    public static IpcPeer PeerOf(NamedPipeServerStream pipe, string connectionId)
    {
        ArgumentNullException.ThrowIfNull(pipe);

        string sid = string.Empty;

        // Impersonation is the supported way to learn the client's identity: inside the callback the
        // thread IS the client, so its identity is theirs.
        pipe.RunAsClient(() =>
            sid = WindowsIdentity.GetCurrent().User?.Value ?? string.Empty);

        return new IpcPeer(sid, ClientProcessId(pipe), connectionId);
    }

    private static int ClientProcessId(NamedPipeServerStream pipe)
    {
        return GetNamedPipeClientProcessId(pipe.SafePipeHandle.DangerousGetHandle(), out var id)
            ? (int)id
            : 0;
    }

    [DllImport("kernel32.dll", SetLastError = true)]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static extern bool GetNamedPipeClientProcessId(nint pipe, out uint clientProcessId);
}
