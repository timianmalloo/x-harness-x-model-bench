using System.Text;
using System.Text.Json;
using AiDe.Core;
using AiDe.Core.Extraction;
using AiDe.Core.Facts;
using AiDe.Core.Ipc;
using AiDe.Core.Projections;

namespace AiDe.Core.Tests;

/// <summary>
/// Whatever the workspace holds, the graph that comes back fits in one message.
/// </summary>
/// <remarks>
/// <para><b>DC-047, made checkable.</b> The graph was shrunk to fit by one proportional correction
/// applied once and never re-checked. Nodes are kept in degree order, so the ones that survive a cut
/// are the most connected — and their edges are most of the payload. Cutting 15% of the nodes can
/// cut 2% of the bytes, so the single correction fell short and the response went out anyway:
/// 1,176,341 bytes against a 1,048,576 frame, reported to the user as "The graph could not be
/// loaded" on opening a workspace.</para>
///
/// <para><b>Measured against the real serialisation, not the estimator.</b> Asserting that the
/// estimate is under the estimate's own budget would be a control marking its own work — the
/// question is whether the bytes on the wire fit the frame, so the test serialises with the wire's
/// own options and counts.</para>
///
/// <para><b>The fixture is hub-shaped on purpose.</b> A uniform graph would shrink proportionally
/// and pass on the un-fixed code, which would make this a test of a fixture rather than of the
/// product (DC-028). Hub dominance IS the failure mode, and it is what real repositories look
/// like — the top nodes on TheTerrace carry hundreds of edges each.</para>
/// </remarks>
public sealed class TheGraphAlwaysFitsInAFrameTests : IDisposable
{
    private readonly string _dir = Path.Combine(
        Path.GetTempPath(), "aide-frame", Guid.NewGuid().ToString("N"));

    public TheGraphAlwaysFitsInAFrameTests() => Directory.CreateDirectory(_dir);

    public void Dispose()
    {
        try { Directory.Delete(_dir, recursive: true); } catch (IOException) { }
    }

    private static readonly JsonSerializerOptions Wire = new(JsonSerializerDefaults.Web);

    /// <summary>The bytes the TRANSPORT counts: the response, framed exactly as it is sent.</summary>
    /// <remarks>
    /// Measuring the payload alone is what let a 727,244-byte graph reach 1,137,104 bytes on the wire
    /// — the budget was checked on the inner bytes and enforced on the outer ones, and through
    /// version 2 those differed by 1.56-1.57x because the payload was a string holding JSON text.
    /// From version 3 the payload IS JSON and the two agree; <see cref="ThePayloadIsNotEncodedTwice"/>
    /// is what keeps them agreeing.
    /// </remarks>
    private static int OnTheWire(WorkspaceGraph graph) =>
        Encoding.UTF8.GetByteCount(JsonSerializer.Serialize(IpcResponse.Success(graph, Wire), Wire));

    /// <summary>A graph whose weight sits in a few hundred hubs, the way a real one does.</summary>
    private WorkspaceCore Fill(int nodes, int hubs, int edgesPerHub)
    {
        var core = WorkspaceCore.Open("ws", _dir, Path.Combine(_dir, "data"), new FixtureExtractor());
        var assertions = new List<EvidenceAssertion>();

        // Ids as long as real ones. Counting nodes tells you nothing about bytes, which is the whole
        // reason the budget is in bytes.
        string Id(int i) => $"TheTerrace.Features.Membership.Application.Handlers.Generated.Type{i:D5}";

        var provenance = new Provenance("p", null, "test", "1", DateTimeOffset.UtcNow);

        for (var i = 0; i < nodes; i++)
        {
            assertions.Add(new EvidenceAssertion(
                "scope", "rev-1", Id(i), "has_type", "class",
                EvidenceOrigin.Static, VerificationStatus.Verified, provenance));
        }

        for (var h = 0; h < hubs; h++)
        {
            for (var e = 1; e <= edgesPerHub; e++)
            {
                // Distinct per hub: the natural key rejects the same triple twice, and a generator
                // that repeats one produces a store error rather than the graph being tested.
                var target = (h * edgesPerHub + e) % nodes;

                if (target == h) continue;

                assertions.Add(new EvidenceAssertion(
                    "scope", "rev-1", Id(h), "depends_on", Id(target),
                    EvidenceOrigin.Static, VerificationStatus.Verified, provenance));
            }
        }

        using var writer = core.Store.BeginWrite();
        writer.DesireScopeGeneration("scope", 1, "rev-1");
        writer.CommitSnapshot("scope", 1, "rev-1", assertions, complete: true);
        writer.Commit();

        return core;
    }

    [Fact]
    public void AGraphTooBigForOneMessageComesBackSmallEnoughForOne()
    {
        using var core = Fill(nodes: 6_200, hubs: 60, edgesPerHub: 4);

        var graph = core.Projections.Graph(new GraphQuery(GraphProjection.DefaultMaxNodes));

        Assert.True(OnTheWire(graph) <= IpcFraming.MaxFrameBytes,
            $"the graph serialises to {OnTheWire(graph):N0} bytes and one message carries "
            + $"{IpcFraming.MaxFrameBytes:N0} — this is the response the transport refuses");
    }

    [Fact]
    public void TheDefaultCanvasRequestFitsToo()
    {
        // The exact query the canvas makes when a workspace opens, which is where the user met this.
        using var core = Fill(nodes: 6_200, hubs: 60, edgesPerHub: 4);

        var graph = core.Projections.Graph(new GraphQuery(1_500, IncludeExternal: false));

        Assert.True(OnTheWire(graph) <= IpcFraming.MaxFrameBytes,
            $"the canvas's opening request serialises to {OnTheWire(graph):N0} bytes");
    }

    [Fact]
    public void ShrinkingStillReturnsAUsableGraphAndSaysWhatItLeftOut()
    {
        // Fitting by returning nothing would pass the assertion above and be a worse product.
        using var core = Fill(nodes: 6_200, hubs: 60, edgesPerHub: 4);

        var graph = core.Projections.Graph(new GraphQuery(GraphProjection.DefaultMaxNodes));

        Assert.True(graph.Nodes.Count > 100, $"only {graph.Nodes.Count} node(s) survived the shrink");
        Assert.True(graph.Omitted > 0, "nodes were dropped and Omitted does not say so");
    }

    [Fact]
    public void ThePayloadIsNotEncodedTwice()
    {
        // THE control for DC-047, and the reason the budget can sit near the frame again.
        //
        // Through version 2 a payload was serialised and the resulting TEXT was put in a string
        // field, so the envelope escaped every quote in it a second time — 1.56-1.57x, measured on
        // every real payload. Nothing said so, and nothing would say so if it came back: the budget
        // and its tests both counted the inner bytes, and agreed with each other while the transport
        // disagreed with both.
        //
        // Reintroducing string-carried JSON — here, or in any handler that hands Success something
        // already serialised — makes this ratio jump and fails HERE, at the seam, rather than at a
        // user opening a workspace.
        using var core = Fill(nodes: 6_200, hubs: 60, edgesPerHub: 4);

        var graph = core.Projections.Graph(new GraphQuery(1_500, IncludeExternal: false));

        var payload = Encoding.UTF8.GetByteCount(JsonSerializer.Serialize(graph, Wire));
        var framed = OnTheWire(graph);

        Assert.True(framed <= payload * 1.05 + 256,
            $"the payload is {payload:N0} bytes and the framed response is {framed:N0} — "
            + $"{(double)framed / payload:F2}x. A framed response should be its payload plus an "
            + "envelope; anything more means the payload is being encoded twice again (DC-047)");
    }

    [Fact]
    public void TheBudgetCannotDriftPastWhatAFrameHolds()
    {
        // The row-wise bounds (evidence, find) cannot afford to serialise per row, so they trust the
        // payload and the frame to be roughly the same size — true only while the payload is carried
        // as JSON rather than as text about JSON. ThePayloadIsNotEncodedTwice holds that premise up;
        // this holds up the arithmetic resting on it.
        Assert.True(ProjectionService.MaxResponseBytes < ProjectionService.FrameBytes,
            $"a {ProjectionService.MaxResponseBytes:N0}-byte payload does not fit a "
            + $"{ProjectionService.FrameBytes:N0}-byte frame at all");

        Assert.True(
            ProjectionService.FrameBytes - ProjectionService.MaxResponseBytes >= 64 * 1024,
            "the budget leaves no room for the envelope, and a response is its payload plus one");

        Assert.True(ProjectionService.MaxFramedGraphBytes < ProjectionService.FrameBytes,
            "a graph shrunk to exactly the frame has no headroom, and shrinking stops at the first "
            + "size that fits");
    }

    [Fact]
    public void AskingForMoreNeverReturnsFewer()
    {
        // Shrinking cuts by at least a third each round, which is what makes it terminate — and it
        // meant the first size that fits could sit far below the largest that would have. MEASURED
        // on a real workspace: asking for 5,000 nodes returned 706 while asking for 1,500 returned
        // 1,000. A caller who asked for MORE was served LESS.
        //
        // That is worse than a shortfall in fidelity: it is a surface whose answer moves in a
        // direction nobody can predict from the request, and the smaller number looks exactly like a
        // smaller workspace.
        //
        // Denser than the other fixtures here, and calibrated rather than chosen: shapes were
        // MEASURED against the un-recovered code until one inverted. At 9,000 nodes over 1,000 hubs
        // it returned 1,000 for a 1,500 request and 868 for a 5,000 one. Lighter shapes never shrink
        // far enough to invert, and a fixture that cannot invert cannot catch this (DC-016).
        using var core = Fill(nodes: 9_000, hubs: 1_000, edgesPerHub: 20);

        var small = core.Projections.Graph(new GraphQuery(1_500, IncludeExternal: false));
        var large = core.Projections.Graph(new GraphQuery(5_000, IncludeExternal: false));

        // Within the recovery gap, which is the precision this offers and not a fudge factor:
        // recovery APPROXIMATES the largest fitting size, and MinRecoveryGap is where it stops
        // looking. Measured here: 1,274 against 1,281. Without recovery it is 868 against 1,281 —
        // eight times the gap — so this still catches the defect it was written for.
        Assert.True(large.Nodes.Count >= small.Nodes.Count - ProjectionService.MinRecoveryGap,
            $"asking for 5,000 nodes returned {large.Nodes.Count} and asking for 1,500 returned "
            + $"{small.Nodes.Count} — a caller who asked for more was served materially less");

        // And the larger answer still fits, which is the constraint recovery must never trade away.
        Assert.True(OnTheWire(large) <= IpcFraming.MaxFrameBytes,
            $"the recovered graph serialises to {OnTheWire(large):N0} bytes");
    }

    [Fact]
    public void AGraphThatAlreadyFitsIsNotShrunk()
    {
        // The loop must be a response to a real overflow, not a cost paid by every workspace.
        using var core = Fill(nodes: 40, hubs: 5, edgesPerHub: 3);

        var graph = core.Projections.Graph(new GraphQuery(GraphProjection.DefaultMaxNodes));

        Assert.Equal(40, graph.Nodes.Count);
        Assert.Equal(0, graph.Omitted);
    }
}
