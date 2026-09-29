using System.Runtime.Versioning;
using AiDe.Core;
using AiDe.Core.Ipc;
using AiDe.Core.Projections;

namespace AiDe.Core.Tests;

/// <summary>
/// The core's read surface, answered by a daemon over a pipe.
/// </summary>
/// <remarks>
/// <para><b>The property that matters is agreement.</b> A projection reached in process and the same
/// projection reached across the boundary must return the same answer — otherwise the split has
/// quietly changed what the product says, and the difference would surface as a UI that disagrees
/// with itself depending on how it was configured. So these tests run each query <i>both ways</i>
/// against one store and compare, rather than asserting a remote result looks plausible.</para>
///
/// <para><b>Serialisation is where that agreement is lost.</b> Not in the projection — in a record
/// field that does not round-trip, an enum that renumbers, a bound that is dropped because nothing
/// read it. Comparing whole results is what catches those; comparing a node id would not.</para>
/// </remarks>
[SupportedOSPlatform("windows")]
[Trait("Platform", "Windows")]
public sealed class DaemonOperationsTests : IDisposable
{
    private readonly TestWorkspace _workspace = TestWorkspace.Create();
    private readonly ProjectionService _projections;
    private readonly string _pipeName = $"aide.test.{Guid.NewGuid():N}";

    public DaemonOperationsTests()
    {
        // A small graph with real shape: a hub, its neighbours, and a second component that must NOT
        // appear in a bounded walk from the hub.
        _workspace.CommitSnapshot(
            "fixture", 1, "rev-1",
            TestWorkspace.Assertion("Service.Orders", "depends_on", "Service.Billing"),
            TestWorkspace.Assertion("Service.Orders", "depends_on", "Service.Catalog"),
            TestWorkspace.Assertion("Service.Billing", "depends_on", "Service.Ledger"),
            TestWorkspace.Assertion("Service.Unrelated", "depends_on", "Service.Isolated"),
            TestWorkspace.Assertion("Service.Orders", "has_type", "class"));

        var root = Path.GetDirectoryName(_workspace.DatabasePath)!;
        Directory.CreateDirectory(Path.Combine(root, "unindexed_probe"));
        _projections = new ProjectionService(_workspace.Store, root);
    }

    private async Task WithDaemon(Func<WorkspaceClient, Task> body)
    {
        var endpoint = new DaemonEndpoint(
            _pipeName, new CapabilityRegistry(), _ => _workspace.Store.CoreEpoch);

        DaemonOperations.Register(endpoint, () => _workspace.Store.CoreEpoch);
        WorkspaceOperations.Register(endpoint, _projections);

        var server = new IpcServer(
            _pipeName, endpoint, new IpcServerOptions(StartupGrace: TimeSpan.FromSeconds(45)));

        using var life = new CancellationTokenSource(TimeSpan.FromSeconds(60));
        var running = server.RunAsync(life.Token);

        try
        {
            await using var client = await WorkspaceClient.ConnectAsync(
                _pipeName, TimeSpan.FromSeconds(20), CancellationToken.None);

            await body(client);
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

    // ---- the same answer, both ways -----------------------------------------

    [Fact]
    public async Task Describe_AgreesWithTheInProcessProjection()
    {
        var expected = _projections.Describe("Service.Orders", 10);
        Assert.NotEmpty(expected.Neighbors); // Two empty results compare equal (DC-015).

        await WithDaemon(async client =>
        {
            var actual = await client.DescribeAsync("Service.Orders", 10, CancellationToken.None);

            Assert.Equal(expected.Node, actual.Node);
            Assert.Equal(expected.Bounds, actual.Bounds);
            Assert.Equal(expected.SourceRevision, actual.SourceRevision);
            Assert.Equal(expected.Neighbors, actual.Neighbors);
            Assert.Equal(expected.Members, actual.Members); // enriched fields survive the wire (class-diagram compartments)
            Assert.Equal(expected.MembersDeclared, actual.MembersDeclared);
        });
    }

    [Fact]
    public async Task Impact_AgreesWithTheInProcessProjection()
    {
        var expected = _projections.Impact("Service.Orders", 10, 20);
        Assert.NotEmpty(expected.Nodes);

        await WithDaemon(async client =>
        {
            var actual = await client.ImpactAsync("Service.Orders", 10, 20, CancellationToken.None);

            Assert.Equal(expected.RootNodeId, actual.RootNodeId);
            Assert.Equal(expected.Bounds, actual.Bounds);
            Assert.Equal(expected.Nodes, actual.Nodes);
            Assert.Equal(expected.Edges, actual.Edges);
        });
    }

    [Fact]
    public async Task Find_AgreesWithTheInProcessProjection()
    {
        var expected = _projections.Find("Service", 10);
        Assert.NotEmpty(expected.Matches);

        await WithDaemon(async client =>
        {
            var actual = await client.FindAsync("Service", 10, CancellationToken.None);

            Assert.Equal(expected.Bounds, actual.Bounds);
            Assert.Equal(expected.SourceRevision, actual.SourceRevision);
            Assert.Equal(expected.Matches, actual.Matches);
        });
    }

    [Fact]
    public async Task SolutionTree_AgreesWithTheInProcessProjection()
    {
        var expected = _projections.SolutionTree(new SolutionTreeQuery());
        Assert.Contains(expected.Nodes, n => n.Path == "unindexed_probe");

        await WithDaemon(async client =>
        {
            var actual = await client.SolutionTreeAsync(new SolutionTreeQuery(), CancellationToken.None);
            Assert.Equal(expected.SkipListedDirectoriesOmitted, actual.SkipListedDirectoriesOmitted);
            Assert.Equal(expected.OmittedByCap, actual.OmittedByCap);
            Assert.Equal(expected.SourceRevision, actual.SourceRevision);
            Assert.Equal(expected.Nodes, actual.Nodes);
            Assert.Equal(expected.Disclosures, actual.Disclosures);
        });
    }

    [Fact]
    public async Task EntryPoints_AgreesWithTheInProcessProjection()
    {
        var expected = _projections.EntryPoints(new EntryPointsQuery());
        Assert.NotEmpty(expected.Rows);

        await WithDaemon(async client =>
        {
            var actual = await client.EntryPointsAsync(new EntryPointsQuery(), CancellationToken.None);
            Assert.Equal(expected.OmittedByCap, actual.OmittedByCap);
            Assert.Equal(expected.SourceRevision, actual.SourceRevision);
            Assert.Equal(expected.Rows, actual.Rows);
            Assert.Equal(expected.Disclosures, actual.Disclosures);
        });
    }

    [Fact]
    public async Task Knowledge_AgreesWithTheInProcessProjection()
    {
        var expected = _projections.Knowledge(new KnowledgeQuery("Service", null, 10));

        await WithDaemon(async client =>
        {
            var actual = await client.KnowledgeAsync("Service", null, 10, CancellationToken.None);

            Assert.Equal(expected.Bounds, actual.Bounds);
            Assert.Equal(expected.Nodes, actual.Nodes);
        });
    }

    // ---- the bounds survive the wire ----------------------------------------

    [Fact]
    public async Task OmittedCounts_SurviveTheBoundary()
    {
        // The omission state is the product's whole answer to "is this result complete?". A bound
        // that arrived as zero would render as a complete answer that is not one — silence read as
        // "nothing there", which is the failure the omission channel exists to prevent.
        var expected = _projections.Describe("Service.Orders", 1);
        Assert.True(expected.Bounds.OmittedEdges > 0, "the fixture no longer produces an omission to test");

        await WithDaemon(async client =>
        {
            var actual = await client.DescribeAsync("Service.Orders", 1, CancellationToken.None);

            Assert.Equal(expected.Bounds.OmittedEdges, actual.Bounds.OmittedEdges);
            Assert.Equal(expected.Bounds.ReturnedEdges, actual.Bounds.ReturnedEdges);
        });
    }

    [Fact]
    public async Task AnEnumField_TravelsAsAName_SoAddingAMemberCannotRenumberIt()
    {
        // Asserted on the WIRE TEXT, not on the round-tripped value. An earlier version of this test
        // checked that the enum came back equal — which a NUMERIC enum also satisfies, so it passed
        // whether or not the converter was configured. Mutation proved it: removing the string
        // converter failed nothing.
        //
        // The property is that the payload carries a NAME. By number, inserting a member renumbers
        // every later one, and the dual-major handshake exists so an old shell may meet a new
        // daemon: that is a wire break with no error and no symptom except wrong answers.
        await WithDaemon(async client =>
        {
            var result = await client.FindAsync("Service", 5, CancellationToken.None);
            Assert.NotEmpty(result.Matches);
            Assert.All(result.Matches, m => Assert.Equal(AuthorshipOrigin.RepositoryArtifact, m.Authorship));
        });

        var wire = System.Text.Json.JsonSerializer.Serialize(
            _projections.Find("Service", 5), WorkspaceOperations.Wire);

        Assert.Contains("\"RepositoryArtifact\"", wire, StringComparison.Ordinal);
        Assert.DoesNotContain("\"authorship\":0", wire, StringComparison.OrdinalIgnoreCase);
    }

    // ---- the epoch fence still applies across the boundary --------------------

    [Fact]
    public async Task TheClient_BindsToTheDaemonsEpoch()
    {
        await WithDaemon(async client =>
        {
            Assert.Equal(_workspace.Store.CoreEpoch, client.Epoch);
            Assert.Equal(_workspace.Store.CoreEpoch, await client.RefreshEpochAsync(CancellationToken.None));
        });
    }

    [Fact]
    public async Task ARequestAuthoredAgainstAStaleEpoch_IsRefused()
    {
        // The fence is the reason the epoch travels at all: a command written while the caller
        // believed different state must not run against the state that replaced it.
        var endpoint = new DaemonEndpoint(_pipeName, new CapabilityRegistry(), _ => 999);
        DaemonOperations.Register(endpoint, () => 999);
        WorkspaceOperations.Register(endpoint, _projections);

        var server = new IpcServer(
            _pipeName, endpoint, new IpcServerOptions(StartupGrace: TimeSpan.FromSeconds(45)));

        using var life = new CancellationTokenSource(TimeSpan.FromSeconds(60));
        var running = server.RunAsync(life.Token);

        try
        {
            await using var client = await IpcClient.ConnectAsync(
                _pipeName, TimeSpan.FromSeconds(20), CancellationToken.None);

            Assert.True((await client.OpenWorkspaceAsync(_pipeName, 0, CancellationToken.None)).Ok);

            var response = await client.InvokeAsync(
                WorkspaceOperations.Find, "cmd-1", _pipeName, epoch: 1, payload: IpcPayloadTestExtensions.Json("{\"term\":\"Service\",\"maxResults\":5}"),
                CancellationToken.None);

            Assert.False(response.Ok);
            Assert.Equal(IpcErrorCodes.EpochStale, response.ErrorCode);
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

    // ---- hostile payloads ------------------------------------------------------

    [Fact]
    public async Task AMalformedPayload_IsRejectedWithoutTakingTheDaemonDown()
    {
        // The payload comes from another process. An unhandled JsonException here would end a daemon
        // serving every other shell attached to the workspace.
        await WithDaemon(async client =>
        {
            await using var raw = await IpcClient.ConnectAsync(
                _pipeName, TimeSpan.FromSeconds(20), CancellationToken.None);

            Assert.True((await raw.OpenWorkspaceAsync(_pipeName, 0, CancellationToken.None)).Ok);

            var rejected = await raw.InvokeAsync(
                WorkspaceOperations.Find, "cmd-1", _pipeName, _workspace.Store.CoreEpoch,
                IpcPayloadTestExtensions.Json("{ this is not json"), CancellationToken.None);

            Assert.False(rejected.Ok);
            Assert.Equal(IpcErrorCodes.MalformedEnvelope, rejected.ErrorCode);

            // And the daemon is still serving the client that behaved.
            var served = await client.FindAsync("Service", 5, CancellationToken.None);
            Assert.NotEmpty(served.Matches);
        });
    }

    [Fact]
    public async Task AMissingPayload_IsRejected()
    {
        await WithDaemon(async client =>
        {
            await using var raw = await IpcClient.ConnectAsync(
                _pipeName, TimeSpan.FromSeconds(20), CancellationToken.None);

            Assert.True((await raw.OpenWorkspaceAsync(_pipeName, 0, CancellationToken.None)).Ok);

            var rejected = await raw.InvokeAsync(
                WorkspaceOperations.Describe, "cmd-1", _pipeName, _workspace.Store.CoreEpoch,
                null, CancellationToken.None);

            Assert.False(rejected.Ok);
            Assert.Equal(IpcErrorCodes.MalformedEnvelope, rejected.ErrorCode);

            await Task.CompletedTask;
        });
    }

    [Fact]
    public async Task AnAbsurdLimit_IsClampedByTheProjection_NotByTheBoundary()
    {
        // Deliberately NOT re-validated at the boundary: the projection already clamps, and a second
        // definition of the bound is two things to keep in step. This asserts the clamp still holds
        // when the number arrives from another process.
        await WithDaemon(async client =>
        {
            var result = await client.DescribeAsync("Service.Orders", int.MaxValue, CancellationToken.None);

            Assert.True(result.Bounds.MaxEdges <= ProjectionService.MaxNeighborsCeiling);
        });
    }

    public void Dispose() => _workspace.Dispose();
}
