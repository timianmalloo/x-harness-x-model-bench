using AiDe.Core.Facts;
using AiDe.Core.Ipc;
using AiDe.Core.Projections;
using AiDe.Core.Store;

namespace AiDe.Core.Tests;

/// <summary>
/// No response can be built that the transport will refuse.
/// </summary>
/// <remarks>
/// <para><b>The audit that produced these, run after INV-0003.</b> The graph was found by a user
/// opening a repository, not by us, so every other read operation was measured at its own ceiling
/// against the 1 MiB frame. Two more were one repository away from the same failure:</para>
///
/// <list type="bullet">
/// <item><b>evidence</b> — 1,004,397 bytes for one 2,000-assertion page, <b>95.8% of the frame</b>,
/// while its own documentation claimed a page stayed "comfortably inside" a 64 KiB cap.</item>
/// <item><b>find</b> — 461,750 bytes returned while REPORTING <c>MaxBytes: 65,536</c> beside it. The
/// cap was declared and never applied, on an operation whose ceiling permits 20,000 results
/// (DC-016: a control that cannot fire).</item>
/// </list>
///
/// <para><b>The class, stated so the next one is caught by design:</b> every ceiling in the read
/// surface counts ITEMS and the transport limit is in BYTES, and every item's size comes from
/// repository content. A count-only cap therefore admits an unbounded payload — which is not a
/// hypothesis, it is three operations.</para>
/// </remarks>
public sealed class ResponseByteBoundTests : IDisposable
{
    private readonly string _dir = Path.Combine(
        Path.GetTempPath(), "aide-bytes", Guid.NewGuid().ToString("N"));

    public ResponseByteBoundTests() => Directory.CreateDirectory(_dir);

    public void Dispose()
    {
        try { Directory.Delete(_dir, recursive: true); } catch (IOException) { }
    }

    /// <summary>A workspace whose content is deliberately long, the way real type names are.</summary>
    private ProjectionService Fat(int assertions, int nameLength)
    {
        var store = WorkspaceStore.Open(Path.Combine(_dir, $"facts-{Guid.NewGuid():N}.db"));

        var padding = new string('N', nameLength);
        var facts = new List<EvidenceAssertion>();

        for (var i = 0; i < assertions; i++)
        {
            facts.Add(new EvidenceAssertion(
                "scope", "rev-1", $"Very.Long.Namespace.{padding}.Type{i}", "has_type", "class",
                EvidenceOrigin.Static, VerificationStatus.Verified,
                new Provenance($"src/{padding}/File{i}.cs", "1:1", "test", "1.0.0", DateTimeOffset.UnixEpoch)));
        }

        using (var writer = store.BeginWrite())
        {
            writer.DesireScopeGeneration("scope", 1, "rev-1");
            writer.CommitSnapshot("scope", 1, "rev-1", facts, complete: true);
            writer.Commit();
        }

        return new ProjectionService(store);
    }

    private static int WireBytes<T>(T payload) =>
        System.Text.Encoding.UTF8.GetByteCount(
            System.Text.Json.JsonSerializer.Serialize(
                payload, new System.Text.Json.JsonSerializerOptions(
                    System.Text.Json.JsonSerializerDefaults.Web)));

    [Fact]
    public void KnowledgeIsSelectedBeforeTheCap_NotFilteredAfterIt()
    {
        // MEASURED at 0 items on a workspace holding 468 knowledge nodes. The projection read the
        // first 200 `has_type` assertions and filtered THOSE to knowledge — so on any real
        // repository the 200 were code types in alphabetical order and the filter left nothing.
        // DC-035's shape one projection along: a cap before a filter returns the wrong slice
        // trimmed to the right shape, and nothing in the result says so.
        var store = WorkspaceStore.Open(Path.Combine(_dir, $"kb-{Guid.NewGuid():N}.db"));
        var facts = new List<EvidenceAssertion>();

        // Code that sorts BEFORE the knowledge, in bulk — the condition that hid the defect.
        for (var i = 0; i < 400; i++)
        {
            facts.Add(new EvidenceAssertion(
                "scope", "rev-1", $"AAA.Code.Type{i:D4}", "has_type", "class",
                EvidenceOrigin.Static, VerificationStatus.Verified,
                new Provenance("src/x.cs", "1:1", "test", "1.0.0", DateTimeOffset.UnixEpoch)));
        }

        facts.Add(new EvidenceAssertion(
            "scope", "rev-1", "zzz-adr-1", "has_type", "adr",
            EvidenceOrigin.Static, VerificationStatus.Verified,
            new Provenance("docs/adr.md", "2:1", "test", "1.0.0", DateTimeOffset.UnixEpoch)));

        facts.Add(new EvidenceAssertion(
            "scope", "rev-1", "zzz-adr-1", "node_class", "knowledge",
            EvidenceOrigin.Static, VerificationStatus.Verified,
            new Provenance("docs/adr.md", "2:1", "test", "1.0.0", DateTimeOffset.UnixEpoch)));

        using (var writer = store.BeginWrite())
        {
            writer.DesireScopeGeneration("scope", 1, "rev-1");
            writer.CommitSnapshot("scope", 1, "rev-1", facts, complete: true);

            foreach (var id in facts.Select(f => f.Subject).Distinct(StringComparer.Ordinal))
            {
                writer.UpsertNode(id, id.StartsWith("zzz", StringComparison.Ordinal) ? "knowledge" : "source", id);
            }

            writer.Commit();
        }

        var result = new ProjectionService(store).Knowledge(new KnowledgeQuery(null, null, 50));

        var node = Assert.Single(result.Nodes);
        Assert.Equal("zzz-adr-1", node.NodeId);
        Assert.Equal("adr", node.Type);
    }

    [Fact]
    public void TheBudgetLeavesRealHeadroomUnderTheFrame()
    {
        // A projection that fills the frame exactly is one repository away from INV-0003.
        Assert.True(ProjectionService.MaxResponseBytes < IpcFraming.MaxFrameBytes);

        var headroom = IpcFraming.MaxFrameBytes - ProjectionService.MaxResponseBytes;
        Assert.True(headroom >= 128 * 1024,
            $"only {headroom:N0} bytes of headroom for the envelope and for estimate error");
    }

    [Fact]
    public void AnEvidencePageStopsAtTheByteBudget_AndTheCursorSaysThereIsMore()
    {
        // Truncating early is LOSSLESS because the page is cursor-driven — which is exactly why the
        // bound belongs here rather than in the transport.
        var projections = Fat(assertions: 2_000, nameLength: 400);

        var page = projections.Evidence(null, ProjectionService.MaxEvidencePageCeiling);

        Assert.True(WireBytes(page) <= IpcFraming.MaxFrameBytes,
            $"a single page serialised to {WireBytes(page):N0} bytes");

        Assert.True(page.Assertions.Count < ProjectionService.MaxEvidencePageCeiling,
            "the byte bound never fired, so this fixture is not exercising it");

        // The count came back SHORT, which used to mean "last page". It must not now.
        Assert.NotNull(page.NextCursor);
    }

    [Fact]
    public void PagingStillReturnsEveryAssertionWhenPagesAreCutShortByBytes()
    {
        // The bound must cost a round trip, never a row.
        var projections = Fat(assertions: 1_200, nameLength: 400);

        var seen = new HashSet<string>(StringComparer.Ordinal);
        string? cursor = null;

        for (var page = 0; page < 50; page++)
        {
            var result = projections.Evidence(cursor, ProjectionService.MaxEvidencePageCeiling);

            foreach (var assertion in result.Assertions)
            {
                Assert.True(seen.Add(assertion.Subject), $"'{assertion.Subject}' came back twice");
            }

            cursor = result.NextCursor;
            if (cursor is null) break;
        }

        Assert.Null(cursor);
        Assert.Equal(1_200, seen.Count);
    }

    [Fact]
    public void AGraphAtItsCountCeilingIsShrunkToFitRatherThanRefused()
    {
        // MEASURED before this: 1,522,915 bytes for the 5,000-node ceiling on a real repository. An
        // operation that can never succeed is a defect whoever calls it.
        var projections = Fat(assertions: 4_000, nameLength: 300);

        var graph = projections.Graph(new GraphQuery(GraphProjection.DefaultMaxNodes));

        Assert.True(WireBytes(graph) <= IpcFraming.MaxFrameBytes,
            $"the graph serialised to {WireBytes(graph):N0} bytes");

        // And it says what it dropped rather than pretending it is whole.
        Assert.True(graph.Omitted > 0);
    }

    [Fact]
    public void FindEnforcesTheByteCapItReports()
    {
        // It reported MaxBytes: 65,536 while returning 461,750. A caller reading the bounds was told
        // a limit that could not fire.
        var projections = Fat(assertions: 3_000, nameLength: 400);

        var result = projections.Find("Type", ProjectionService.MaxSearchResultsCeiling);

        Assert.True(WireBytes(result) <= IpcFraming.MaxFrameBytes,
            $"find serialised to {WireBytes(result):N0} bytes");

        Assert.True(result.Bounds.ByteCapped, "the byte cap never fired on a fixture built to trip it");
        Assert.True(result.Bounds.OmittedNodes > 0, "truncation was not reported to the caller");
        Assert.Equal(ProjectionService.MaxResponseBytes, result.Bounds.MaxBytes);
    }

    [Fact]
    public void AResponseAlwaysCarriesAtLeastOneItem()
    {
        // A caller that receives nothing because its first row is enormous can never make progress,
        // which is worse than one frame slightly over an internal budget.
        var projections = Fat(assertions: 3, nameLength: 900_000);

        var page = projections.Evidence(null, ProjectionService.MaxEvidencePageCeiling);

        Assert.NotEmpty(page.Assertions);
    }
}
