using System.Diagnostics;
using System.Runtime.Versioning;
using AiDe.Core.Ipc;
using AiDe.Core.Projections;

namespace AiDe.Core.Tests;

/// <summary>
/// The process split, as a real second process.
/// </summary>
/// <remarks>
/// <para><b>Everything else about this boundary has been proven in one process.</b> The
/// authorization decisions without a socket, the transport with a pipe between two objects in the
/// same test host. Neither can answer the question ADR-0009 actually deferred: does a shell reach a
/// <i>separate daemon process</i>, and does that process behave — take its lock, publish its pipe,
/// serve, and go away — as a process rather than as an object.</para>
///
/// <para><b>The lock case is the one that cannot be faked.</b> Two <see cref="WorkspaceLock"/>
/// instances in one process share a mutex the easy way; two daemon <i>processes</i> contending is
/// the actual scenario, and it is the only version that proves the store cannot get two writers.</para>
/// </remarks>
[SupportedOSPlatform("windows")]
[Trait("Platform", "Windows")]
public sealed class DaemonProcessTests
{
    private static string FreshWorkspace() =>
        Path.Combine(Path.GetTempPath(), $"aide-daemon-{Guid.NewGuid():N}");

    private static string LocateDaemon()
    {
        var root = Path.GetFullPath(Path.Combine(
            AppContext.BaseDirectory, "..", "..", "..", "..", "..", "src", "AiDe.Daemon", "bin"));

        // The configuration THESE TESTS were built in, read from their own output path — not
        // "Release if that folder happens to exist". The old rule preferred a Release daemon left
        // behind by an earlier publish, so a Debug test run drove a binary from a different commit
        // and reported on a product that was not the one under test (DC-023). It did exactly that
        // here: the daemon gained the full extractor composition and the test still failed, because
        // it was running yesterday's daemon.
        var configuration = AppContext.BaseDirectory.Contains(
            Path.DirectorySeparatorChar + "Release" + Path.DirectorySeparatorChar,
            StringComparison.OrdinalIgnoreCase)
            ? "Release"
            : "Debug";

        var candidate = Path.Combine(root, configuration, "net10.0-windows", "AiDe.Daemon.exe");

        Assert.True(
            File.Exists(candidate),
            $"the daemon was not built. Expected it at:\n  {candidate}\n"
            + "Build the solution rather than the test project alone.");

        return candidate;
    }

    /// <summary>Starts a daemon and waits until it says which pipe it is serving.</summary>
    /// <remarks>
    /// Waiting for the announcement rather than sleeping: a fixed delay is either too short (a flaky
    /// test) or too long (a slow one), and the daemon already reports readiness precisely so a
    /// supervisor need not guess.
    /// </remarks>
    private static async Task<(Process Process, string PipeName)> StartDaemonAsync(
        string workspace, params string[] extra)
    {
        var start = new ProcessStartInfo(LocateDaemon())
        {
            RedirectStandardOutput = true,
            RedirectStandardError = true,
            UseShellExecute = false,
            CreateNoWindow = true,
        };

        start.ArgumentList.Add(workspace);

        // Beside the workspace, so the state dies with it. Without this the daemon writes into the
        // user's real LocalAppData and the directory outlives the test by months.
        foreach (var argument in DaemonStateDirectory.ArgumentsFor(workspace))
        {
            start.ArgumentList.Add(argument);
        }

        foreach (var argument in extra)
        {
            start.ArgumentList.Add(argument);
        }

        var process = Process.Start(start);
        Assert.NotNull(process);

        var announcement = await process!.StandardOutput.ReadLineAsync().WaitAsync(TimeSpan.FromSeconds(30));

        Assert.NotNull(announcement);
        Assert.StartsWith("listening ", announcement, StringComparison.Ordinal);

        return (process, announcement!["listening ".Length..].Trim());
    }

    private static void Stop(Process process)
    {
        try
        {
            if (!process.HasExited)
            {
                process.Kill(entireProcessTree: true);
            }
        }
        catch (InvalidOperationException)
        {
        }

        process.Dispose();
    }

    // ---- a shell reaches a separate process ---------------------------------

    [Fact]
    public async Task AShell_ReachesADaemonInAnotherProcess()
    {
        var workspace = FreshWorkspace();
        var (daemon, pipeName) = await StartDaemonAsync(workspace, "--startup-seconds", "40");

        try
        {
            Assert.Equal(IpcPipeName.ForWorkspace(workspace), pipeName);

            await using var client = await IpcClient.ConnectAsync(
                pipeName, TimeSpan.FromSeconds(20), CancellationToken.None);

            var opened = await client.OpenWorkspaceAsync(pipeName, 1, CancellationToken.None);
            Assert.True(opened.Ok, opened.Reason);

            var pong = await client.InvokeAsync(
                "ping", "cmd-1", pipeName, 1, null, CancellationToken.None);

            Assert.True(pong.Ok, pong.Reason);
            Assert.Equal("pong", pong.Payload.AsText());

            // The peer really is another process — the whole point of the phase.
            Assert.NotEqual(Environment.ProcessId, daemon.Id);
        }
        finally
        {
            Stop(daemon);
        }
    }

    // ---- the daemon extracts what the product claims to extract --------------

    [Fact]
    public async Task TheDaemon_ReturnsInfrastructureEvidence_AcrossThePipe()
    {
        // The daemon composed only the C# extractor and the fixture adapter, so a workspace's
        // infrastructure was invisible to the running application while a spike — which composed all
        // four in process — reported joins the product had no way to show. The composition is shared
        // now; this is the assertion that the SHIPPED PROCESS actually uses it.
        //
        // Across the pipe on purpose. Everything else about this is unit-tested in process, and the
        // in-process answer was right the whole time the product's was wrong.
        var workspace = FreshWorkspace();
        Directory.CreateDirectory(Path.Combine(workspace, "infra"));

        await File.WriteAllTextAsync(Path.Combine(workspace, "infra", "main.bicep"),
            """
            param siteName string = 'aide-probe'

            resource site 'Microsoft.Web/sites@2023-01-01' = {
              name: siteName
              location: resourceGroup().location
            }
            """);

        var (daemon, pipeName) = await StartDaemonAsync(workspace, "--startup-seconds", "60");

        try
        {
            await using var client = await WorkspaceClient.ConnectAsync(
                pipeName, TimeSpan.FromSeconds(20), CancellationToken.None);

            var summary = await client.IndexSolutionAsync("probe-1", CancellationToken.None);

            Assert.True(summary.ScopesIndexed > 0,
                $"nothing was indexed; {summary.Failed.Count} scope(s) failed");
            Assert.Empty(summary.Failed);

            // The resource itself, by name, read back through the daemon's own read surface. A count
            // would pass on any evidence at all, which is exactly what the C#-only composition
            // produced.
            var found = await client.FindAsync("site", 200, CancellationToken.None);
            Assert.NotEmpty(found.Matches);

            // Asked of every match rather than of the first. "site" matches the PARAMETER
            // (bicep:main#siteName) before the resource, and a test that described only the first
            // hit failed while the daemon was returning exactly the evidence it was asked for — a
            // wrong assertion about a working fix, which is the most expensive kind to debug.
            var predicates = new List<string>();

            foreach (var match in found.Matches)
            {
                var described = await client.DescribeAsync(match.NodeId, 60, CancellationToken.None);
                predicates.AddRange(described.Neighbors.Select(e => e.Predicate));
            }

            Assert.Contains("resource_type", predicates);
            Assert.Contains("api_version", predicates);

            // And the extractor that produced it, so "infrastructure evidence" is not being read
            // from a C# assertion that happens to share a predicate name (DC-022).
            var resource = await client.DescribeAsync(
                found.Matches.First(m => !m.NodeId.Contains('#', StringComparison.Ordinal)).NodeId,
                60, CancellationToken.None);

            Assert.All(resource.Neighbors, e =>
                Assert.Equal("bicep-extractor", e.Provenance.ExtractorId));
        }
        finally
        {
            Stop(daemon);
        }
    }

    [Fact]
    public async Task TheDaemon_PagesEveryAssertion_AcrossThePipe()
    {
        // The last three cross-boundary defects were all "right in process, wrong through the pipe":
        // an extractor composition the daemon did not have, a search ceiling the daemon applied
        // differently, and a request field the wire did not carry. Paging is the newest thing to
        // cross, and a cursor is exactly the sort of state that survives a unit test and not a
        // serialiser.
        var workspace = FreshWorkspace();
        Directory.CreateDirectory(Path.Combine(workspace, "infra"));

        await File.WriteAllTextAsync(Path.Combine(workspace, "infra", "main.bicep"),
            """
            param siteName string = 'aide-probe'
            param region string = 'westus'

            resource site 'Microsoft.Web/sites@2023-01-01' = {
              name: siteName
              location: region
            }

            resource plan 'Microsoft.Web/serverfarms@2023-01-01' = {
              name: 'aide-plan'
              location: region
            }
            """);

        var (daemon, pipeName) = await StartDaemonAsync(workspace, "--startup-seconds", "60");

        try
        {
            await using var client = await WorkspaceClient.ConnectAsync(
                pipeName, TimeSpan.FromSeconds(20), CancellationToken.None);

            var summary = await client.IndexSolutionAsync("probe-1", CancellationToken.None);
            Assert.True(summary.Assertions > 0, summary.Describe());

            // A page size of ONE, so the cursor is exercised at every boundary rather than the test
            // proving only that a single response deserialises.
            var seen = new List<string>();
            string? cursor = null;
            var pages = 0;

            do
            {
                var page = await client.EvidenceAsync(cursor, 1, CancellationToken.None);
                seen.AddRange(page.Assertions.Select(a => $"{a.Subject}|{a.Predicate}|{a.Object}"));
                cursor = page.NextCursor;
                pages++;
            }
            while (cursor is not null && pages < 500);

            Assert.Null(cursor);                                   // it ended, rather than hitting the cap
            Assert.Equal(summary.Assertions, seen.Count);           // every one, exactly once
            Assert.Equal(seen.Count, seen.Distinct(StringComparer.Ordinal).Count());

            // And the payload survived the wire intact, provenance included — the field a join's
            // basis is qualified by (DC-022).
            var single = await client.EvidenceAsync(null, 50, CancellationToken.None);
            Assert.All(single.Assertions, a =>
                Assert.False(string.IsNullOrWhiteSpace(a.Provenance.ExtractorId)));
        }
        finally
        {
            Stop(daemon);
        }
    }

    [Fact]
    public async Task TheDaemon_ReturnsTheWholeGraph_AcrossThePipe()
    {
        // The user's report was about the graph SURFACE, which reads through the daemon. Proving the
        // projection in process would have proved the half that was never broken.
        var workspace = FreshWorkspace();
        Directory.CreateDirectory(Path.Combine(workspace, "infra"));
        Directory.CreateDirectory(Path.Combine(workspace, "docs"));

        // A knowledge artifact beside the code, so the graph this test reads holds BOTH halves —
        // which is the only way an assertion about the declared class can fail when it should.
        await File.WriteAllTextAsync(Path.Combine(workspace, "docs", "note.md"),
            """
            ---
            id: probe-note
            type: decision-note
            owner: "@probe"
            ---

            # A note the graph should carry as knowledge
            """);

        await File.WriteAllTextAsync(Path.Combine(workspace, "infra", "main.bicep"),
            """
            param region string = 'westus'

            resource site 'Microsoft.Web/sites@2023-01-01' = {
              name: 'aide-probe'
              location: region
            }

            resource plan 'Microsoft.Web/serverfarms@2023-01-01' = {
              name: 'aide-plan'
              location: region
              dependsOn: [ site ]
            }
            """);

        var (daemon, pipeName) = await StartDaemonAsync(workspace, "--startup-seconds", "60");

        try
        {
            await using var client = await WorkspaceClient.ConnectAsync(
                pipeName, TimeSpan.FromSeconds(20), CancellationToken.None);

            await client.IndexSolutionAsync("probe-1", CancellationToken.None);

            var graph = await client.GraphAsync(new GraphQuery(2_000), CancellationToken.None);

            // More than a node and its neighbour, which is what the surface used to draw.
            Assert.True(graph.Nodes.Count > 2, $"only {graph.Nodes.Count} node(s) came back");
            Assert.NotEmpty(graph.Edges);

            // The node's kind rode across intact — an attribute, not an edge.
            Assert.Contains(graph.Nodes, n => n.Kind != "external" && n.Kind.Length > 0);

            // And the declared/external split survived serialisation, which is what keeps the
            // framework out of the centre of the picture.
            Assert.Contains(graph.Nodes, n => !n.IsExternal);

            // ---- the FILTER crosses the pipe too --------------------------------------------
            // Proven here rather than only in process, because every cross-boundary defect in this
            // codebase so far has been right in process and wrong through the pipe. A filter that
            // silently arrives as its default returns a correct-looking whole graph, which is the
            // hardest kind of wrong to notice.
            var mine = await client.GraphAsync(
                new GraphQuery(2_000, IncludeExternal: false), CancellationToken.None);

            Assert.NotEmpty(mine.Nodes);
            Assert.All(mine.Nodes, n => Assert.False(n.IsExternal));

            // Only assert that it REMOVED something when there was something to remove. This
            // fixture's workspace is small enough to have no external nodes at all, and a test that
            // demands a reduction there would be measuring the fixture rather than the filter.
            if (graph.Nodes.Any(n => n.IsExternal))
            {
                Assert.True(mine.Nodes.Count < graph.Nodes.Count,
                    $"the filter changed nothing: {mine.Nodes.Count} of {graph.Nodes.Count}");
            }

            // A kind filter names the values `has_type` carries.
            var kind = graph.Nodes.First(n => !n.IsExternal && n.Kind != "external").Kind;

            var byKind = await client.GraphAsync(
                new GraphQuery(2_000, Kinds: [kind]), CancellationToken.None);

            Assert.NotEmpty(byKind.Nodes);
            Assert.All(byKind.Nodes, n => Assert.Equal(kind, n.Kind));

            // ---- the DECLARED class survives the pipe ----------------------------------------
            // The Knowledge chip reads this. It read 0 on a repository holding 2,343 knowledge
            // nodes, and one cause was that the graph carried only each node's FINE kind — which
            // there is a name that repository invented (`knowledge-epl-fan-platform`), so no fixed
            // list of type names could recognise it. A bool that arrives defaulted to false across
            // the pipe reproduces the same symptom with the fix in place, so it is asserted on a
            // node KNOWN to be knowledge and on one known not to be.
            Assert.Contains(graph.Nodes, n => n.IsKnowledge);
            Assert.Contains(graph.Nodes, n => !n.IsKnowledge);

            var document = Assert.Single(graph.Nodes, n => n.Id == "probe-note");
            Assert.True(document.IsKnowledge, "the document arrived across the pipe as source");
            Assert.Equal("decision-note", document.Kind);

            // ---- ExcludeKnowledge crosses the pipe too (Ruling 53; US-C8) --------------------
            // GraphRequest used to drop this field entirely — a filter set in process and silently
            // ignored over the wire is the "arrives defaulted to false" defect above, one field
            // over. Proven against the SAME running daemon: the knowledge document disappears, the
            // source node from the fixture's own code does not.
            var withoutKnowledge = await client.GraphAsync(
                new GraphQuery(2_000, ExcludeKnowledge: true), CancellationToken.None);

            Assert.DoesNotContain(withoutKnowledge.Nodes, n => n.Id == "probe-note");
            Assert.Contains(withoutKnowledge.Nodes, n => !n.IsKnowledge);

            // ---- and a ROUTE crosses the pipe ------------------------------------------------
            // A path is the one result whose shape is a list of lists, so it is the one most likely
            // to arrive flattened, empty, or with its edge direction lost — none of which would look
            // like a failure at the call site.
            var edge = graph.Edges[0];

            var route = await client.PathsAsync(
                new PathQuery(edge.From, edge.To), CancellationToken.None);

            var path = Assert.Single(route.Paths);
            Assert.NotEmpty(path.Edges);
            Assert.Equal(edge.From, path.Edges[0].From);
            Assert.Equal(edge.To, path.Edges[^1].To);

            // A missing endpoint must arrive as a REASON, not as an empty list that reads like
            // "these two are unconnected".
            var missing = await client.PathsAsync(
                new PathQuery(edge.From, "no.such.node.anywhere"), CancellationToken.None);

            Assert.Empty(missing.Paths);
            Assert.False(string.IsNullOrWhiteSpace(missing.Reason));

            // ---- the OVERVIEW, and the drill-down back out of it ------------------------------
            // The overview is nested — clusters and weighted links — so it is the response most
            // likely to arrive with an inner list flattened or a count defaulted to zero. And a
            // cluster's count is a CLAIM: if drilling in returns a different number, the two answers
            // disagree and a user who noticed would be right to stop believing both.
            var overview = await client.OverviewAsync(new OverviewQuery(Depth: 1), CancellationToken.None);

            Assert.NotEmpty(overview.Clusters);
            Assert.All(overview.Clusters, c => Assert.True(c.NodeCount > 0,
                $"cluster '{c.Id}' crossed the pipe claiming {c.NodeCount} nodes"));
            Assert.Equal(1, overview.Depth);

            var group = overview.Clusters.OrderByDescending(c => c.NodeCount).First();

            var inside = await client.GraphAsync(
                new GraphQuery(2_000, GroupId: group.Id), CancellationToken.None);

            Assert.Equal(group.NodeCount, inside.Nodes.Count);
        }
        finally
        {
            Stop(daemon);
        }
    }

    // ---- P2-IPC-06: one daemon per workspace, across processes ---------------

    [Fact]
    public async Task ASecondDaemonForTheSameWorkspace_RefusesToStart()
    {
        // Two daemons on one workspace would both work, both write, and both believe they owned the
        // epoch. Nothing would fail at the time; the store would simply end up with a history that
        // has two authors.
        var workspace = FreshWorkspace();
        var (first, _) = await StartDaemonAsync(workspace, "--startup-seconds", "40");

        try
        {
            var start = new ProcessStartInfo(LocateDaemon())
            {
                RedirectStandardOutput = true,
                RedirectStandardError = true,
                UseShellExecute = false,
                CreateNoWindow = true,
            };
            start.ArgumentList.Add(workspace);

            // The same state directory as the first: this is the SAME workspace, and pointing the
            // second daemon elsewhere would test two workspaces refusing to share a lock, which
            // they never would.
            foreach (var argument in DaemonStateDirectory.ArgumentsFor(workspace))
            {
                start.ArgumentList.Add(argument);
            }

            using var second = Process.Start(start)!;
            var error = await second.StandardError.ReadToEndAsync();
            Assert.True(second.WaitForExit(30_000), "the second daemon did not exit");

            Assert.Equal(2, second.ExitCode);
            Assert.Contains(IpcErrorCodes.WorkspaceLocked, error, StringComparison.Ordinal);

            // And the first is unharmed: the loser exits, the incumbent keeps serving.
            Assert.False(first.HasExited, "the incumbent daemon died when a second one was attempted");
        }
        finally
        {
            Stop(first);
        }
    }

    [Fact]
    public async Task AfterTheFirstDaemonExits_AnotherCanTakeTheWorkspace()
    {
        // Otherwise a restart would need a reboot, and the lock protecting the store would be the
        // thing that made the workspace permanently unopenable.
        var workspace = FreshWorkspace();

        var (first, _) = await StartDaemonAsync(workspace, "--startup-seconds", "2");
        Assert.True(first.WaitForExit(40_000), "the first daemon did not exit on its startup grace");
        Assert.Equal(0, first.ExitCode);
        first.Dispose();

        var (second, _) = await StartDaemonAsync(workspace, "--startup-seconds", "40");
        Stop(second);
    }

    // ---- P2-IPC-05: an orphaned daemon does not linger ------------------------

    [Fact]
    public async Task ADaemonNobodyConnectsTo_ExitsOnItsOwn()
    {
        var workspace = FreshWorkspace();
        var (daemon, _) = await StartDaemonAsync(workspace, "--startup-seconds", "2");

        try
        {
            Assert.True(
                daemon.WaitForExit(40_000),
                "an orphaned daemon kept running, holding the workspace lock invisibly");
            Assert.Equal(0, daemon.ExitCode);
        }
        finally
        {
            Stop(daemon);
        }
    }

    [Fact]
    public async Task ADaemonWhoseClientLeaves_ExitsAfterTheIdleGrace()
    {
        var workspace = FreshWorkspace();
        var (daemon, pipeName) = await StartDaemonAsync(
            workspace, "--startup-seconds", "40", "--idle-seconds", "2");

        try
        {
            await using (var client = await IpcClient.ConnectAsync(
                pipeName, TimeSpan.FromSeconds(20), CancellationToken.None))
            {
                Assert.True((await client.OpenWorkspaceAsync(pipeName, 1, CancellationToken.None)).Ok);
            }

            Assert.True(
                daemon.WaitForExit(40_000),
                "the daemon kept running after its last client left");
            Assert.Equal(0, daemon.ExitCode);
        }
        finally
        {
            Stop(daemon);
        }
    }

    // ---- usage ---------------------------------------------------------------

    [Fact]
    public void WithNoWorkspace_TheDaemonRefusesToStart()
    {
        // A daemon that defaulted to some directory would take a lock on a workspace nobody asked
        // for and serve it under a pipe name nobody can predict.
        var start = new ProcessStartInfo(LocateDaemon())
        {
            RedirectStandardError = true,
            UseShellExecute = false,
            CreateNoWindow = true,
        };

        using var process = Process.Start(start)!;
        var error = process.StandardError.ReadToEnd();

        Assert.True(process.WaitForExit(20_000));
        Assert.Equal(64, process.ExitCode);
        Assert.Contains("usage", error, StringComparison.OrdinalIgnoreCase);
    }
}
