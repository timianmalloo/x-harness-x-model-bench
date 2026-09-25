using System.Runtime.Versioning;
using AiDe.Core.Dispatch;
using AiDe.Core.Extraction;
using AiDe.Core;
using AiDe.Core.Ipc;
using AiDe.Core.Upgrade;

namespace AiDe.Daemon;

/// <summary>
/// The workspace daemon: one process, one workspace, one pipe.
/// </summary>
/// <remarks>
/// <para><b>This is the process split ADR-0009 deferred.</b> Phase 1 called the core in-process, so
/// <c>CallerPrincipal</c> was simply true. From here it is a claim arriving over a pipe, established
/// by the transport from the connection and never from anything a caller sends.</para>
///
/// <para><b>Order matters and is the startup contract.</b> The workspace lock is taken <i>first</i>,
/// before a pipe exists and before anything is opened. A daemon that started serving and then
/// discovered it was the second one would already have published an endpoint clients could reach,
/// and two daemons on one workspace are two writers to one store — each believing it owns the epoch,
/// both working perfectly, with the damage visible only later as a history with two authors.</para>
///
/// <para><b>It exits when nobody needs it.</b> Not a tidiness measure: a daemon outliving every shell
/// holds the workspace lock, so an orphan makes the workspace unopenable by anything else while
/// being invisible to the user.</para>
///
/// <para><b>Exit codes are the contract</b> with Shell Bootstrap: <b>0</b> served and went idle,
/// <b>2</b> another daemon already owns this workspace, <b>3</b> could not start, <b>64</b> the
/// arguments were wrong.</para>
/// </remarks>
[SupportedOSPlatform("windows")]
internal static class Program
{
    private const int ExitOk = 0;
    private const int ExitWorkspaceLocked = 2;
    private const int ExitStartupFailed = 3;
    private const int ExitBadUsage = 64;

    private static async Task<int> Main(string[] args)
    {
        if (args.Length < 1 || string.IsNullOrWhiteSpace(args[0]))
        {
            await Console.Error.WriteLineAsync(
                "usage: AiDe.Daemon <workspace-path> [--data <directory>] "
                + "[--idle-seconds N] [--startup-seconds N]");
            return ExitBadUsage;
        }

        var workspacePath = Path.GetFullPath(args[0]);
        var options = new IpcServerOptions(
            IdleGrace: Seconds(args, "--idle-seconds"),
            StartupGrace: Seconds(args, "--startup-seconds"));

        // FIRST. Before the pipe, before the store, before anything a client could reach.
        if (!WorkspaceLock.TryAcquire(workspacePath, out var workspaceLock))
        {
            await Console.Error.WriteLineAsync(
                $"{IpcErrorCodes.WorkspaceLocked}: another daemon already serves this workspace");
            return ExitWorkspaceLocked;
        }

        using (workspaceLock)
        {
            WorkspaceCore? core = null;

            try
            {
                var pipeName = IpcPipeName.ForWorkspace(workspacePath);

                // Opened AFTER the lock and before the pipe. A daemon that published an endpoint and
                // then failed to open its store would be reachable while unable to answer anything.
                // BEFORE the store is opened, because compaction rebuilds and swaps the file.
                //
                // This is the deliberate maintenance moment the design asks for: no session is in
                // progress, no pane is rendering, and a daemon that has just started is the one
                // moment an operator is watching. Reporting alone was the previous answer and it
                // was worse than useless — the check existed, was tested, and nothing called it, so
                // a workspace grew without limit while its diagnosis sat in an uninvoked method
                // (DC-042).
                //
                // MEASURED: 1.09s to halve a 53 MB store, 1-34ms to decide there is nothing to do.
                // Cheap enough to simply always ask.
                Compact(workspacePath, Option(args, "--data"));

                var (endpoint, opened) = OpenWorkspace(workspacePath, Option(args, "--data"));
                core = opened;

                var server = new IpcServer(pipeName, endpoint, options);

                // stdout, so a supervisor can confirm which pipe to reach without guessing. The
                // workspace PATH is not printed: the name is derived precisely so the path does not
                // have to travel with it.
                Console.WriteLine($"listening {pipeName}");
                await Console.Out.FlushAsync();

                using var lifetime = new CancellationTokenSource();
                Console.CancelKeyPress += (_, e) =>
                {
                    e.Cancel = true;
                    lifetime.Cancel();
                };

                await server.RunAsync(lifetime.Token);
                return ExitOk;
            }
            catch (Exception ex) when (ex is IOException or UnauthorizedAccessException)
            {
                await Console.Error.WriteLineAsync($"daemon could not start: {ex.Message}");
                return ExitStartupFailed;
            }
            finally
            {
                // Closed before the workspace lock is released, so the next daemon never finds the
                // store still held by a process that has already given up its claim to the workspace.
                core?.Dispose();
            }
        }
    }

    /// <summary>
    /// Opens the workspace and puts its read surface behind the endpoint.
    /// </summary>
    /// <remarks>
    /// <para><b>Read projections and the daemon's own two operations.</b> Dispatch — writing to a
    /// terminal, staging a prompt — carries the two-phase receipt semantics of ADR-0010 and moves
    /// across as its own piece of work; registering a handler that half-implemented it would leave
    /// the boundary partly crossed, which is worse than one honestly not yet.</para>
    ///
    /// <para><b>The workspace id is the derived pipe name, not the path.</b> It travels in every
    /// request and appears in operator output, and the pipe name was already computed precisely so
    /// the path does not have to.</para>
    /// </remarks>
    /// <param name="dataDirectoryOverride">
    /// Where to keep this workspace's state. Absent means the machine-wide default.
    /// </param>
    /// <remarks>
    /// <para><b>Why an override exists at all.</b> Without one the daemon decides for itself, from a
    /// machine-wide folder, and a caller cannot say otherwise — so anything that launches a daemon
    /// writes into the user's real profile whether it meant to or not. MEASURED: one run of the Core
    /// test suite left <b>12</b> workspace directories under LocalAppData, and 2,674 had accumulated
    /// there over four days, all but one of them an empty store from a test.</para>
    ///
    /// <para>It also removes a second derivation of the same value: the shell already computes this
    /// path and can now pass the one it computed, rather than the two of them agreeing by
    /// coincidence for as long as both copies of the expression stay identical (DC-022).</para>
    /// </remarks>
    private static (DaemonEndpoint Endpoint, WorkspaceCore Core) OpenWorkspace(
        string workspacePath, string? dataDirectoryOverride)
    {
        var workspaceId = IpcPipeName.ForWorkspace(workspacePath);

        var dataDirectory = DataDirectoryFor(workspacePath, dataDirectoryOverride);

        // BEFORE the store is opened. A migration interrupted by a power loss leaves a store that
        // may be anything, and the only thing known to be good is its snapshot — so the next start
        // is where that gets undone, because nothing at the moment of the crash got to run.
        var recovery = UpgradeCoordinator.RecoverIfIncomplete(
            Path.Combine(dataDirectory, "workspace.db"), dataDirectory);

        if (recovery.Recovered)
        {
            Console.WriteLine("recovered an interrupted migration; the pre-migration store was restored");
        }
        else if (recovery.Failure is not null)
        {
            // Announced, never swallowed. A store left half-migrated with no snapshot is a state the
            // operator has to know about; opening it anyway and hoping is how corruption becomes
            // permanent.
            Console.Error.WriteLine(recovery.Failure);
        }

        // ONE composition, shared with every other entry point. The daemon previously composed only
        // C# and the fixture adapter, so the running application could not see infrastructure or
        // schema at all — while a spike composed all four and reported joins the product had no way
        // to show. Two answers to "what does this tool read", depending which door you came in.
        var core = WorkspaceCore.Open(
            workspaceId, workspacePath, dataDirectory, WorkspaceExtractors.Default());

        var endpoint = new DaemonEndpoint(
            workspaceId, new CapabilityRegistry(), _ => core.Store.CoreEpoch);

        DaemonOperations.Register(endpoint, () => core.Store.CoreEpoch);
        WorkspaceOperations.Register(endpoint, core.Projections);
        WorkspaceOperations.RegisterDispatch(endpoint, new BoundaryDispatcher(core.Store));
        WorkspaceOperations.RegisterIndex(endpoint, async (revision, force, ct) =>
        {
            var result = await core.IndexCSharpAsync(revision, ct, force: force);
            return new IndexSummary(
                result.ScopesFound, result.ScopesIndexed, result.Assertions,
                result.Failed, result.Disclosures, result.Contexts, result.ScopesReused);
        });

        // Ingestion, which is a WRITE and the first one to cross. Started and polled rather than
        // awaited on the wire: a scope has a 60-second budget and the lane serves one request at a
        // time per connection.
        new ScopeRefreshService(async (scopeId, revision, ct) =>
        {
            var result = await core.RefreshScopeAsync(scopeId, revision, ct);

            if (!result.Complete)
            {
                // Surfaced as a failure rather than a count of zero. An incomplete extraction leaves
                // the previous snapshot rendering, and reporting it as a successful refresh of
                // nothing is precisely the clean-empty-success over rotting evidence the product
                // exists to avoid.
                throw new InvalidOperationException(
                    string.Join("; ", result.Diagnostics.Select(d => $"{d.ErrorCode}: {d.Message}")));
            }

            return result.Assertions.Count;
        }).Register(endpoint);

        return (endpoint, core);
    }

    /// <summary>Reads a duration flag, ignoring anything malformed rather than failing to start.</summary>
    /// <remarks>
    /// A daemon that refused to start over an unparseable tuning flag would turn a typo in a
    /// supervisor's command line into an unopenable workspace. The defaults are safe.
    /// </remarks>
    /// <summary>
    /// Where this workspace's state lives — one derivation, used by everything that needs it.
    /// </summary>
    /// <remarks>
    /// Extracted because compaction needs the same answer as opening does, and a second copy of this
    /// expression would agree with the first only until somebody edited one of them (DC-022).
    /// </remarks>
    private static string DataDirectoryFor(string workspacePath, string? dataDirectoryOverride) =>
        string.IsNullOrWhiteSpace(dataDirectoryOverride)
            ? Path.Combine(
                Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),
                "AiDe", "workspaces", IpcPipeName.ForWorkspace(workspacePath))
            : Path.GetFullPath(dataDirectoryOverride);

    /// <summary>Reclaims superseded generations, if there are any, before anything opens the store.</summary>
    private static void Compact(string workspacePath, string? dataDirectoryOverride)
    {
        var database = Path.Combine(DataDirectoryFor(workspacePath, dataDirectoryOverride), "workspace.db");

        if (!File.Exists(database)) return;

        try
        {
            var result = new AiDe.Core.Store.StoreCompactor(database).Compact();

            if (result.Ran)
            {
                Console.WriteLine(result.Summary);
            }
        }
        catch (Exception ex) when (ex is IOException or UnauthorizedAccessException or AiDe.Core.Store.WorkspaceStoreException)
        {
            // A workspace that cannot be compacted is a workspace that starts anyway, larger than it
            // needs to be. Refusing to serve because housekeeping failed would trade a disk cost for
            // an outage.
            Console.Error.WriteLine($"compaction skipped: {ex.Message}");
        }
    }

    /// <summary>The value after a flag, or null when the flag is absent or last.</summary>
    private static string? Option(string[] args, string flag)
    {
        var index = Array.IndexOf(args, flag);
        return index >= 0 && index + 1 < args.Length ? args[index + 1] : null;
    }

    private static TimeSpan? Seconds(string[] args, string flag)
    {
        var index = Array.IndexOf(args, flag);

        return index >= 0
            && index + 1 < args.Length
            && double.TryParse(args[index + 1], out var seconds)
            && seconds > 0
                ? TimeSpan.FromSeconds(seconds)
                : null;
    }
}
