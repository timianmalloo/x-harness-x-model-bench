using System.Runtime.Versioning;
using AiDe.Core.Ipc;
using AiDe.Core.Projections;

namespace AiDe.Core.Tests;

/// <summary>
/// The first <b>write</b> to cross the boundary: re-indexing a scope.
/// </summary>
/// <remarks>
/// <para><b>Reads could be answered and forgotten; a write cannot.</b> A refresh bumps a generation
/// and commits a snapshot, so a duplicate is not a wasted round trip — it is a second extraction
/// whose loser's work is discarded after costing a full 60-second budget. The command id carries the
/// architecture's idempotency semantics, and this is where they first matter across a process
/// boundary.</para>
///
/// <para><b>Started and polled, not awaited on the wire.</b> The lane serves one request at a time
/// per connection, so a refresh that answered only on completion would hold that connection for the
/// whole budget and the daemon's response-write timeout would abandon it first.</para>
/// </remarks>
[SupportedOSPlatform("windows")]
[Trait("Platform", "Windows")]
public sealed class ScopeRefreshTests
{
    private const string Workspace = "ws-refresh";
    private const long Epoch = 3;

    private static string FreshPipeName() => $"aide.test.{Guid.NewGuid():N}";

    /// <summary>A refresh that reports how often it actually ran.</summary>
    private sealed class CountingRefresh
    {
        private int _runs;
        private readonly TaskCompletionSource _release = new();

        public int Runs => Volatile.Read(ref _runs);

        public bool HoldUntilReleased { get; init; }

        public bool Throw { get; init; }

        public void Release() => _release.TrySetResult();

        public async Task<int> RunAsync(string scopeId, string revision, CancellationToken ct)
        {
            Interlocked.Increment(ref _runs);

            if (HoldUntilReleased)
            {
                await _release.Task;
            }

            return Throw ? throw new InvalidOperationException("extractor said no") : 7;
        }
    }

    // ---- the service's own rules --------------------------------------------

    [Fact]
    public async Task ARefresh_ReportsCompletionWithItsAssertionCount()
    {
        var work = new CountingRefresh();
        var service = new ScopeRefreshService(work.RunAsync);

        var started = service.Start("cmd-1", "fixture", "rev-1");
        Assert.Equal(ScopeRefreshState.Running, started.State);

        var final = await Settled(service, "cmd-1");

        Assert.Equal(ScopeRefreshState.Completed, final.State);
        Assert.Equal(7, final.AssertionCount);
        Assert.Equal(1, work.Runs);
    }

    [Fact]
    public void TheSameCommandId_DoesNotStartASecondExtraction()
    {
        // The case this exists for is a client that did not see the reply and retried. Two
        // extractions of one scope both bump the generation, and the loser's work is discarded after
        // costing a full budget.
        var work = new CountingRefresh { HoldUntilReleased = true };
        var service = new ScopeRefreshService(work.RunAsync);

        var first = service.Start("cmd-1", "fixture", "rev-1");
        var retry = service.Start("cmd-1", "fixture", "rev-1");

        Assert.Equal(first.CommandId, retry.CommandId);
        Assert.Equal(1, work.Runs);
        Assert.Equal(1, service.TrackedJobs);

        work.Release();
    }

    [Fact]
    public void ConcurrentRetriesOfOneCommandId_StartExactlyOneExtraction()
    {
        // The sequential case is caught by the fast path; THIS is what the TryAdd guard is for, and
        // nothing exercised it until a mutation run showed the guard could be disabled with no test
        // failing (DC-016).
        //
        // The race is real rather than theoretical: a client whose reply was lost retries, and a
        // shell reconnecting can retry while the original is still in flight. Two extractions of one
        // scope both bump the generation, and the loser's work is discarded after costing a budget.
        var work = new CountingRefresh { HoldUntilReleased = true };
        var service = new ScopeRefreshService(work.RunAsync);

        const int Racers = 32;
        using var start = new Barrier(Racers);
        var threads = new Thread[Racers];

        for (var i = 0; i < Racers; i++)
        {
            threads[i] = new Thread(() =>
            {
                start.SignalAndWait();
                service.Start("cmd-same", "fixture", "rev-1");
            });
            threads[i].Start();
        }

        foreach (var thread in threads)
        {
            Assert.True(thread.Join(TimeSpan.FromSeconds(20)), "a racer did not finish");
        }

        Assert.Equal(1, work.Runs);
        Assert.Equal(1, service.TrackedJobs);

        work.Release();
    }

    [Fact]
    public void DifferentCommandIds_AreDifferentJobs()
    {
        var work = new CountingRefresh { HoldUntilReleased = true };
        var service = new ScopeRefreshService(work.RunAsync);

        service.Start("cmd-1", "fixture", "rev-1");
        service.Start("cmd-2", "fixture", "rev-1");

        Assert.Equal(2, work.Runs);

        work.Release();
    }

    [Fact]
    public async Task AFailedExtraction_IsReportedAsFailed_WithItsReason()
    {
        // Never as a successful refresh of zero assertions: an incomplete extraction leaves the
        // previous snapshot rendering, and reporting success would present rotting evidence as
        // freshly confirmed.
        var service = new ScopeRefreshService(new CountingRefresh { Throw = true }.RunAsync);

        service.Start("cmd-1", "fixture", "rev-1");
        var final = await Settled(service, "cmd-1");

        Assert.Equal(ScopeRefreshState.Failed, final.State);
        Assert.Equal(0, final.AssertionCount);
        Assert.Contains("extractor said no", final.Failure!, StringComparison.Ordinal);
    }

    [Fact]
    public async Task AFailingRefresh_DoesNotTakeTheDaemonDown()
    {
        // It runs detached from the request that started it, so an escaping exception would end the
        // process on behalf of a caller who is no longer listening.
        var service = new ScopeRefreshService(new CountingRefresh { Throw = true }.RunAsync);

        service.Start("cmd-1", "fixture", "rev-1");
        await Settled(service, "cmd-1");

        // Still serving: a second job starts and completes normally.
        var healthy = new ScopeRefreshService(new CountingRefresh().RunAsync);
        healthy.Start("cmd-2", "fixture", "rev-1");

        Assert.Equal(ScopeRefreshState.Completed, (await Settled(healthy, "cmd-2")).State);
    }

    [Fact]
    public void AnUnknownCommandId_HasNoStatus()
    {
        // Null rather than a synthesised "unknown" state: a job this daemon never started and one it
        // has evicted are both "I cannot tell you", and inventing a status would let a caller wait
        // for a result that is never coming.
        Assert.Null(new ScopeRefreshService(new CountingRefresh().RunAsync).Status("never-started"));
    }

    [Fact]
    public async Task FinishedJobs_AreBoundedSoAClientCannotGrowTheDaemon()
    {
        // Job records are keyed by a CALLER-CHOSEN id, so an unbounded map is a memory leak any
        // client can drive by refreshing in a loop.
        var service = new ScopeRefreshService(new CountingRefresh().RunAsync);

        for (var i = 0; i < 400; i++)
        {
            service.Start($"cmd-{i}", "fixture", "rev-1");
            await Settled(service, $"cmd-{i}");
        }

        Assert.True(
            service.TrackedJobs <= 300,
            $"the daemon retained {service.TrackedJobs} job records");
    }

    [Fact]
    public void ARunningJob_IsNeverEvicted()
    {
        // Its status is the only record that the extraction is happening; dropping it would report
        // an in-flight refresh as one this daemon never heard of.
        var held = new CountingRefresh { HoldUntilReleased = true };
        var service = new ScopeRefreshService(held.RunAsync);
        service.Start("held", "fixture", "rev-1");

        var finished = new ScopeRefreshService(new CountingRefresh().RunAsync);
        for (var i = 0; i < 400; i++)
        {
            service.Start($"cmd-{i}", "fixture", "rev-1");
        }

        Assert.NotNull(service.Status("held"));
        Assert.Equal(ScopeRefreshState.Running, service.Status("held")!.State);

        held.Release();
        GC.KeepAlive(finished);
    }

    // ---- across a real pipe --------------------------------------------------

    [Fact]
    public async Task AShell_RefreshesAScopeAcrossTheBoundary()
    {
        var pipeName = FreshPipeName();
        var work = new CountingRefresh();

        var endpoint = new DaemonEndpoint(pipeName, new CapabilityRegistry(), _ => Epoch);
        DaemonOperations.Register(endpoint, () => Epoch);
        new ScopeRefreshService(work.RunAsync).Register(endpoint);

        var server = new IpcServer(
            pipeName, endpoint, new IpcServerOptions(StartupGrace: TimeSpan.FromSeconds(45)));

        using var life = new CancellationTokenSource(TimeSpan.FromSeconds(60));
        var running = server.RunAsync(life.Token);

        try
        {
            await using var client = await WorkspaceClient.ConnectAsync(
                pipeName, TimeSpan.FromSeconds(20), CancellationToken.None);

            var status = await client.RefreshScopeAsync("fixture", "rev-1", CancellationToken.None);

            Assert.Equal(ScopeRefreshState.Completed, status.State);
            Assert.Equal(7, status.AssertionCount);
            Assert.Equal(1, work.Runs);
        }
        finally
        {
            await life.CancelAsync();
            try
            {
                await running;
            }
            catch (OperationCanceledException)
            {
            }
        }
    }

    [Fact]
    public async Task ARefreshThatOutlivesASingleRoundTrip_StillCompletes()
    {
        // The reason for start-then-poll. A refresh held open past any plausible response timeout
        // must still be reachable, which an await-on-the-wire design could not manage.
        var pipeName = FreshPipeName();
        var work = new CountingRefresh { HoldUntilReleased = true };

        var endpoint = new DaemonEndpoint(pipeName, new CapabilityRegistry(), _ => Epoch);
        DaemonOperations.Register(endpoint, () => Epoch);
        new ScopeRefreshService(work.RunAsync).Register(endpoint);

        var server = new IpcServer(
            pipeName, endpoint,
            new IpcServerOptions(
                StartupGrace: TimeSpan.FromSeconds(60),
                ResponseTimeout: TimeSpan.FromMilliseconds(500)));

        using var life = new CancellationTokenSource(TimeSpan.FromSeconds(90));
        var running = server.RunAsync(life.Token);

        try
        {
            await using var client = await WorkspaceClient.ConnectAsync(
                pipeName, TimeSpan.FromSeconds(20), CancellationToken.None);

            var refreshing = client.RefreshScopeAsync("fixture", "rev-1", CancellationToken.None);

            // Far longer than the response timeout, and the connection is fine because no single
            // request is waiting on the work.
            await Task.Delay(TimeSpan.FromSeconds(2));
            work.Release();

            var status = await refreshing;
            Assert.Equal(ScopeRefreshState.Completed, status.State);
        }
        finally
        {
            await life.CancelAsync();
            try
            {
                await running;
            }
            catch (OperationCanceledException)
            {
            }
        }
    }

    [Fact]
    public async Task AStatusQueryForAnUnknownCommand_IsRejectedWithAStableCode()
    {
        var pipeName = FreshPipeName();

        var endpoint = new DaemonEndpoint(pipeName, new CapabilityRegistry(), _ => Epoch);
        DaemonOperations.Register(endpoint, () => Epoch);
        new ScopeRefreshService(new CountingRefresh().RunAsync).Register(endpoint);

        var server = new IpcServer(
            pipeName, endpoint, new IpcServerOptions(StartupGrace: TimeSpan.FromSeconds(45)));

        using var life = new CancellationTokenSource(TimeSpan.FromSeconds(60));
        var running = server.RunAsync(life.Token);

        try
        {
            await using var client = await IpcClient.ConnectAsync(
                pipeName, TimeSpan.FromSeconds(20), CancellationToken.None);

            Assert.True((await client.OpenWorkspaceAsync(pipeName, 0, CancellationToken.None)).Ok);

            var response = await client.InvokeAsync(
                ScopeRefreshService.Operations.RefreshStatus, "cmd-x", pipeName, Epoch,
                IpcPayloadTestExtensions.Json("{\"commandId\":\"never-started\"}"),
                CancellationToken.None);

            Assert.False(response.Ok);
            Assert.Equal(IpcErrorCodes.CommandUnknown, response.ErrorCode);
        }
        finally
        {
            await life.CancelAsync();
            try
            {
                await running;
            }
            catch (OperationCanceledException)
            {
            }
        }
    }

    private static async Task<ScopeRefreshStatus> Settled(ScopeRefreshService service, string commandId)
    {
        var deadline = DateTimeOffset.UtcNow + TimeSpan.FromSeconds(20);

        while (DateTimeOffset.UtcNow < deadline)
        {
            var status = service.Status(commandId);
            if (status is not null && status.State != ScopeRefreshState.Running)
            {
                return status;
            }

            await Task.Delay(10);
        }

        throw new TimeoutException($"'{commandId}' never settled");
    }
}
