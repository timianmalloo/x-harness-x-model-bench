using AiDe.Testing;
using AiDe.Core.Ipc;
using AiDe.Core.Presentation;
using AiDe.Core.Projections;
using AiDe.Core.Facts;

namespace AiDe.Core.Tests;

/// <summary>
/// A response too big to send says so, and the default view does not produce one.
/// </summary>
/// <remarks>
/// <para><b>INV-0003, reported by the user through the design session.</b> Opening TheTerrace showed
/// <i>"The graph could not be loaded: ipc.transport_closed: the daemon closed the connection without
/// responding."</i> MEASURED: the whole-graph response is <b>1,522,284 bytes</b> against a 1 MiB
/// frame. The write threw, the serve loop caught IOException and OperationCanceledException but not
/// that, the exception escaped, and the connection closed with no reply — so "the answer is too big"
/// reached the user as "the daemon vanished".</para>
///
/// <para>Two separate failures, and both are pinned here: the transport must never close silently,
/// and the default view must not ask for something that cannot be delivered.</para>
/// </remarks>
public sealed class OversizedResponseTests
{
    private static EvidenceAssertion Say(string subject, string predicate, string obj) =>
        new("scope", "rev-1", subject, predicate, obj, EvidenceOrigin.Static, VerificationStatus.Verified,
            new Provenance("test", null, "test", "1", DateTimeOffset.UnixEpoch));

    [Fact]
    public void TheFrameCapIsSmallerThanARealRepositorysWholeGraph()
    {
        // The measurement that makes the rest of this file necessary, kept as an assertion so that
        // raising the cap without revisiting the default view fails here first.
        const int MeasuredWholeGraphBytes = 1_522_284;

        Assert.True(MeasuredWholeGraphBytes > IpcFraming.MaxFrameBytes,
            "the measurement this fix rests on no longer holds — re-measure before trusting it");
    }

    [Fact]
    public async Task AnOversizedFrameIsRefusedByTheWriter()
    {
        // The throw is correct and stays: a partially written frame leaves the peer reading a length
        // prefix whose body never arrives, which is a hang rather than an error. What was missing is
        // a caller that checks BEFORE writing — see IpcServer.Respond.
        using var stream = new MemoryStream();
        var tooBig = new string('x', IpcFraming.MaxFrameBytes + 1);

        await Assert.ThrowsAsync<ArgumentException>(
            () => IpcFraming.WriteAsync(stream, tooBig, CancellationToken.None));
    }

    [Fact]
    public void ThereIsACodeForTooBigToSend_DistinctFromTheDaemonGoingAway()
    {
        // "The daemon vanished" and "the answer is too big to send" need different things from a
        // user. Rendering the second as the first sends them to look at the daemon.
        Assert.NotEqual(IpcErrorCodes.TransportClosed, IpcErrorCodes.PayloadTooLarge);
        Assert.Contains("payload", IpcErrorCodes.PayloadTooLarge, StringComparison.Ordinal);
    }

    [Fact]
    public async Task TheDefaultViewIsBounded_AndSaysWhatItLeftOut()
    {
        // The default asked for the whole graph, which could not be delivered. The spec never wanted
        // one: knowledge-exploration.md US-K2 — "the whole graph is never rendered at once".
        var assertions = new List<EvidenceAssertion>();

        for (var i = 0; i < CanvasGraphViewModel.OverviewNodeCap + 200; i++)
        {
            assertions.Add(Say($"Shop.Type{i}", "has_type", "class"));
            assertions.Add(Say($"Shop.Type{i}", "depends_on", "Shop.Hub"));
        }

        assertions.Add(Say("Shop.Hub", "has_type", "class"));

        var graph = new GraphProjection(assertions, "rev-1");
        var queries = new StubGraphQueries(graph);

        var canvas = await new CanvasGraphViewModel(queries).LoadAsync(null, 40, CancellationToken.None);

        Assert.Equal(CanvasGraphViewModel.OverviewNodeCap, canvas.Nodes.Count);
        Assert.True(canvas.Omitted > 0);
        Assert.Contains("not drawn", canvas.Message);

        // And it asked for the bounded query, not the whole one.
        Assert.NotNull(queries.Asked);
        Assert.Equal(CanvasGraphViewModel.OverviewNodeCap, queries.Asked!.MaxNodes);
        Assert.False(queries.Asked.IncludeExternal);
    }

    [Fact]
    public async Task TheDefaultViewExcludesTheFrameworkFromTheCentre()
    {
        // Measured on a real repository: the six most-connected nodes were string, int, Task<T>,
        // DateTimeOffset, IReadOnlyList<T> and Guid. A first view centred on the BCL is not a
        // picture of anybody's domain.
        var assertions = new List<EvidenceAssertion>
        {
            Say("Shop.Order", "has_type", "class"),
            Say("Shop.Order", "depends_on", "string"),
            Say("Shop.Order", "depends_on", "int"),
        };

        var queries = new StubGraphQueries(new GraphProjection(assertions, "rev-1"));

        var canvas = await new CanvasGraphViewModel(queries).LoadAsync(null, 40, CancellationToken.None);

        Assert.Single(canvas.Nodes);
        Assert.Equal("Shop.Order", canvas.Nodes[0].Id);
    }

    private sealed class StubGraphQueries(GraphProjection projection) : FakeWorkspaceQueries
    {
        public GraphQuery? Asked { get; private set; }

        public override Task<WorkspaceGraph> GraphAsync(GraphQuery query, CancellationToken ct)
        {
            Asked = query;
            return Task.FromResult(projection.Compute(query));
        }






    }
}
