using System.Diagnostics;
using System.Runtime.Versioning;

namespace AiDe.Core.Ipc;

/// <summary>Why a shell could not reach a daemon.</summary>
public sealed class DaemonUnavailableException(string message, Exception? inner = null)
    : Exception(message, inner);

/// <summary>
/// Gets the shell a daemon: reach the one that is running, or start one and wait for it.
/// </summary>
/// <remarks>
/// <para><b>Connect first, launch second, and that order is the whole design.</b> A workspace has at
/// most one daemon — enforced by <see cref="WorkspaceLock"/> — so launching first would mean the
/// second shell on a workspace starts a process whose only job is to discover it is redundant and
/// exit. Trying the pipe costs a few milliseconds and is right in the common case.</para>
///
/// <para><b>Launching is racy on purpose, and safe because of the lock.</b> Two shells opening the
/// same workspace at the same instant will both fail to connect and both launch; one takes the
/// workspace lock and serves, the other exits with a stable code. Serialising that with a lock of
/// our own would put a second mechanism in front of the one that already decides this correctly.</para>
///
/// <para><b>Failure is reported, never degraded into a silent fallback to in-process.</b> A shell
/// that quietly ran the core itself when the daemon would not start would work — and would have
/// abandoned the trust boundary, the workspace lock and the epoch fence without saying so. The
/// caller is told, and decides.</para>
/// </remarks>
[SupportedOSPlatform("windows")]
public static class ShellBootstrap
{
    /// <summary>How long to keep retrying the pipe after launching a daemon.</summary>
    /// <remarks>
    /// A cold daemon has to start a runtime, take a lock and open a store. Too short and an ordinary
    /// cold start looks like a failure; too long and a genuinely broken daemon looks like a hang.
    /// </remarks>
    private static readonly TimeSpan LaunchDeadline = TimeSpan.FromSeconds(30);

    /// <summary>How long to wait when we believe a daemon is already there.</summary>
    private static readonly TimeSpan ExistingDaemonTimeout = TimeSpan.FromSeconds(2);

    /// <summary>Connects to the workspace's daemon, starting one if none answers.</summary>
    /// <param name="workspacePath">The workspace root. Determines the pipe name and the lock.</param>
    /// <param name="daemonExecutable">The daemon build to launch if none is running.</param>
    /// <param name="dataDirectory">
    /// Where a launched daemon should keep this workspace's state. Null leaves it to the daemon's
    /// machine-wide default — which is right for the shell and wrong for anything that must not
    /// write into the user's profile, such as a test.
    /// </param>
    public static async Task<WorkspaceClient> ConnectOrLaunchAsync(
        string workspacePath, string daemonExecutable, CancellationToken cancellationToken,
        string? dataDirectory = null)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(workspacePath);
        ArgumentException.ThrowIfNullOrWhiteSpace(daemonExecutable);

        var pipeName = IpcPipeName.ForWorkspace(workspacePath);

        // The common case: a daemon is already serving this workspace, because another shell opened
        // it or this one was restarted inside the idle grace.
        var existing = await TryConnectAsync(pipeName, ExistingDaemonTimeout, cancellationToken)
            .ConfigureAwait(false);

        if (existing is not null)
        {
            return existing;
        }

        if (!File.Exists(daemonExecutable))
        {
            // Distinguished from "the daemon would not start": a missing build is an installation
            // problem, and reporting it as a startup failure sends the investigation elsewhere.
            throw new DaemonUnavailableException(
                $"no daemon is running for this workspace and none is installed at '{daemonExecutable}'");
        }

        Launch(daemonExecutable, workspacePath, dataDirectory);

        var deadline = DateTimeOffset.UtcNow + LaunchDeadline;

        while (DateTimeOffset.UtcNow < deadline)
        {
            cancellationToken.ThrowIfCancellationRequested();

            var client = await TryConnectAsync(pipeName, TimeSpan.FromMilliseconds(500), cancellationToken)
                .ConfigureAwait(false);

            if (client is not null)
            {
                return client;
            }

            await Task.Delay(TimeSpan.FromMilliseconds(100), cancellationToken).ConfigureAwait(false);
        }

        throw new DaemonUnavailableException(
            $"a daemon was launched for this workspace but did not answer within "
            + $"{LaunchDeadline.TotalSeconds:0}s");
    }

    /// <summary>Starts a daemon for the workspace, detached from this process's console.</summary>
    /// <remarks>
    /// <para><b>Not awaited, and its output is not redirected.</b> The daemon outlives the shell that
    /// started it by design — it holds warm state through a shell restart, which is what the idle
    /// grace exists for. Redirecting its streams would make the shell responsible for draining them
    /// forever, and a full pipe buffer would then block the daemon.</para>
    ///
    /// <para>The process handle is disposed immediately: we are not its supervisor, the workspace
    /// lock decides who serves, and the idle grace decides when it stops.</para>
    /// </remarks>
    private static void Launch(string daemonExecutable, string workspacePath, string? dataDirectory)
    {
        var start = new ProcessStartInfo(daemonExecutable)
        {
            UseShellExecute = false,
            CreateNoWindow = true,
            WorkingDirectory = Path.GetDirectoryName(daemonExecutable) ?? Environment.CurrentDirectory,
        };

        start.ArgumentList.Add(workspacePath);

        if (!string.IsNullOrWhiteSpace(dataDirectory))
        {
            start.ArgumentList.Add("--data");
            start.ArgumentList.Add(dataDirectory);
        }

        try
        {
            Process.Start(start)?.Dispose();
        }
        catch (Exception ex) when (ex is System.ComponentModel.Win32Exception or InvalidOperationException)
        {
            throw new DaemonUnavailableException(
                $"the daemon at '{daemonExecutable}' could not be started: {ex.Message}", ex);
        }
    }

    private static async Task<WorkspaceClient?> TryConnectAsync(
        string pipeName, TimeSpan timeout, CancellationToken cancellationToken)
    {
        try
        {
            return await WorkspaceClient
                .ConnectAsync(pipeName, timeout, cancellationToken)
                .ConfigureAwait(false);
        }
        catch (TimeoutException)
        {
            return null; // Nobody listening yet.
        }
        catch (IOException)
        {
            return null; // A daemon exiting as we arrived, or all its instances busy.
        }
        catch (UnauthorizedAccessException)
        {
            // The pipe exists but is not ours. Not retried and not swallowed: another user's process
            // holding this name is a security-relevant condition, not a slow start.
            throw new DaemonUnavailableException(
                "a pipe with this workspace's name exists but is owned by another user");
        }
        catch (IpcRequestException ex) when (ex.Code == IpcErrorCodes.UnsupportedVersion)
        {
            // A daemon from an EARLIER BUILD is still serving this workspace. It holds the pipe, and
            // one daemon per workspace is the store's single-writer invariant — so a second cannot
            // be started beside it.
            //
            // Version negotiation did its job here: the mismatch was refused at the boundary instead
            // of becoming a parse failure further in. What was missing was saying so in terms of the
            // thing a person can act on — "ipc.unsupported_version" names the protocol; this names
            // the process that has to go.
            throw new DaemonUnavailableException(
                "a daemon from an earlier build is still running for this workspace and speaks an "
                + "older protocol. It exits on its own once idle; to reopen immediately, end the "
                + $"AiDe.Daemon process serving this workspace ({ex.Message})");
        }
    }
}
