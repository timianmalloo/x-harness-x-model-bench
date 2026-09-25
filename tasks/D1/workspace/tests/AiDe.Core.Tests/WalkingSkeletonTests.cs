using AiDe.Core;
using AiDe.Core.Facts;
using AiDe.Core.Health;
using AiDe.Core.Mcp;
using AiDe.Core.Presentation;
using AiDe.Core.Projections;

namespace AiDe.Core.Tests;

/// <summary>
/// The end-to-end slice, exercised through the real composition root (<see cref="WorkspaceCore"/>)
/// rather than against the units in isolation — E11: prove the rendered surface, not just the parts.
/// </summary>
public sealed class WalkingSkeletonTests : IDisposable
{
    private readonly FixtureRepository _fixture = FixtureRepository.Create();
    private readonly string _dataDirectory =
        Path.Combine(Path.GetTempPath(), "aide-core", Guid.NewGuid().ToString("N"));

    private WorkspaceCore OpenCore() => WorkspaceCore.Open("ws-1", _fixture.Root, _dataDirectory);

    // P1-EXT-01 — the pipeline: artifact -> assertions -> facts -> projection.
    [Fact]
    public async Task Refresh_ExtractsExactlyTheHandDerivedManifest()
    {
        using var core = OpenCore();

        var result = await core.RefreshScopeAsync("fixture", "rev-1");

        Assert.True(result.Complete);
        foreach (var (subject, predicate, @object) in FixtureRepository.ExpectedSourceEdges)
        {
            Assert.Contains(result.Assertions,
                a => a.Subject == subject && a.Predicate == predicate && a.Object == @object);
        }

        foreach (var (subject, predicate, @object) in FixtureRepository.ExpectedKnowledgeEdges)
        {
            Assert.Contains(result.Assertions,
                a => a.Subject == subject && a.Predicate == predicate && a.Object == @object);
        }
    }

    // Confidence must never be promoted by rendering: an [Inferred] relation stays Inferred.
    [Fact]
    public async Task InferredRelation_IsNeverPromotedToVerified()
    {
        using var core = OpenCore();
        await core.RefreshScopeAsync("fixture", "rev-1");

        var describe = core.Projections.Describe("Order", 50);
        var persisted = Assert.Single(describe.Neighbors, n => n.Predicate == "persisted_in");

        Assert.Equal(VerificationStatus.Inferred, persisted.Status);
    }

    // P1-EXT-02 — a malformed artifact marks the snapshot incomplete and raises an incident;
    // the previous snapshot still renders. An empty graph is never reported as a clean graph.
    [Fact]
    public async Task MalformedArtifact_KeepsLastGoodSnapshotAndRaisesAnIncident()
    {
        using var core = OpenCore();
        await core.RefreshScopeAsync("fixture", "rev-1");
        var before = core.Projections.Describe("Order", 50).Neighbors.Count;

        _fixture.WriteMalformed();
        var second = await core.RefreshScopeAsync("fixture", "rev-2");

        Assert.False(second.Complete);
        Assert.NotEmpty(core.Incidents.Unacknowledged());
        // Last successful evidence still stands.
        Assert.Equal(before, core.Projections.Describe("Order", 50).Neighbors.Count);
    }

    // P1-KNOW-01..03 — US-4, the story the council found had no verification path at all.
    [Fact]
    public async Task Knowledge_NavigatesTypesLinksBacklinksAndSurfacesHealthFindings()
    {
        using var core = OpenCore();
        await core.RefreshScopeAsync("fixture", "rev-1");

        var all = core.Projections.Knowledge(new KnowledgeQuery(null, null, 50));
        Assert.Equal(3, all.Nodes.Count);   // adr-0001, spec-orders, orphan-note

        var adr = Assert.Single(all.Nodes, n => n.NodeId == "adr-0001");
        Assert.Equal("adr", adr.Type);
        Assert.Equal("@alice", adr.Owner);
        Assert.Contains(adr.Links, l => l.Predicate == "implements" && l.Object == "spec-orders");

        // Backlink: the spec must know the ADR points at it.
        var spec = Assert.Single(all.Nodes, n => n.NodeId == "spec-orders");
        Assert.Contains(spec.Backlinks, b => b.Subject == "adr-0001");

        // Missing evidence is a visible health finding, not a clean-looking node.
        var orphan = Assert.Single(all.Nodes, n => n.NodeId == "orphan-note");
        Assert.Contains("owner not recorded", orphan.HealthFindings);
        Assert.Contains(orphan.HealthFindings, f => f.StartsWith("orphan", StringComparison.Ordinal));
    }

    [Fact]
    public async Task Knowledge_FiltersByType()
    {
        using var core = OpenCore();
        await core.RefreshScopeAsync("fixture", "rev-1");

        var adrs = core.Projections.Knowledge(new KnowledgeQuery(null, "adr", 50));

        Assert.Single(adrs.Nodes);
        Assert.Equal("adr-0001", adrs.Nodes[0].NodeId);
    }

    // P1-MCP-03 — a bounded result must publish what it omitted, or it is indistinguishable
    // from a complete one.
    [Fact]
    public async Task Impact_IsBoundedAndPublishesItsOmissions()
    {
        using var core = OpenCore();
        await core.RefreshScopeAsync("fixture", "rev-1");

        var full = core.Projections.Impact("OrderService", 50, 50);
        var capped = core.Projections.Impact("OrderService", 2, 50);

        Assert.True(full.Nodes.Count > capped.Nodes.Count);
        Assert.Equal(2, capped.Nodes.Count);
        Assert.True(capped.Bounds.OmittedNodes > 0);
        Assert.Equal(2, capped.Bounds.MaxNodes);
    }

    [Fact]
    public async Task Impact_ClampsAnOverLargeRequestToTheCeiling()
    {
        using var core = OpenCore();
        await core.RefreshScopeAsync("fixture", "rev-1");

        var result = core.Projections.Impact("OrderService", int.MaxValue, int.MaxValue);

        Assert.Equal(ProjectionService.MaxNodesCeiling, result.Bounds.MaxNodes);
        Assert.Equal(ProjectionService.MaxEdgesCeiling, result.Bounds.MaxEdges);
    }

    // P1-MCP-EGRESS RETIRED by ADR-0022, and REPLACED rather than deleted: a security test that
    // vanishes with no explanation reads as an oversight to whoever finds the gap next.
    //
    // It asserted that a non-LocalOnly session got MinimumMetadataOnly on reads and Deny on writes.
    // The threat model did not survive contact with the product's shape — an agent in AI-DE has a
    // terminal in the workspace and can read any file directly, so the gate constrained the polite
    // interface while the impolite one stood open. What replaces it asserts the gate is GONE, so
    // re-adding one is a deliberate act with a failing test in front of it.
    [Theory]
    [InlineData(SessionProcessingClass.LocalOnly)]
    [InlineData(SessionProcessingClass.ExternalProcessing)]
    [InlineData(SessionProcessingClass.UnknownProcessing)]
    public async Task McpRead_IsNotReducedByProcessingClass(SessionProcessingClass processingClass)
    {
        using var core = OpenCore();
        await core.RefreshScopeAsync("fixture", "rev-1");

        var caller = new McpCallerContext("ws-1", "session-x", processingClass,
            new CallerPrincipal("agent-1", CallerKind.McpClient));

        var result = core.Mcp.Describe(caller, "Order", 50);

        Assert.Equal(ToolAuthorization.Allow, result.Authorization);
        Assert.IsNotType<MinimumMetadata>(result.Payload);
    }

    [Fact]
    public async Task McpWrite_IsNotDeniedByProcessingClass()
    {
        using var core = OpenCore();
        await core.RefreshScopeAsync("fixture", "rev-1");

        var caller = new McpCallerContext("ws-1", "session-x", SessionProcessingClass.ExternalProcessing,
            new CallerPrincipal("agent-1", CallerKind.McpClient));

        Assert.Equal(ToolAuthorization.Allow, McpToolGateway.Authorize(caller, "record_note"));
    }

    // P1-SEC-05
    [Fact]
    public async Task McpRead_ForAnotherWorkspace_IsRejected()
    {
        using var core = OpenCore();
        await core.RefreshScopeAsync("fixture", "rev-1");

        var caller = new McpCallerContext("ws-OTHER", "session-1", SessionProcessingClass.LocalOnly,
            new CallerPrincipal("agent-1", CallerKind.McpClient));

        var result = core.Mcp.Describe(caller, "Order", 50);

        Assert.True(result.IsError);
        Assert.Equal(McpErrorCodes.CrossWorkspace, result.ErrorCode);
        Assert.Null(result.Payload);
    }

    // P1-MCP-INERT-01 — AI-DE is an OUTBOUND injection conduit too. A hostile repo label must arrive
    // as inert typed data, never blended into free text that a downstream agent could act on.
    [Fact]
    public async Task HostileLabel_ArrivesAsInertTypedData()
    {
        using var core = OpenCore();
        _fixture.WriteHostileLabel();
        await core.RefreshScopeAsync("fixture", "rev-1");

        var caller = new McpCallerContext("ws-1", "session-1", SessionProcessingClass.LocalOnly,
            new CallerPrincipal("agent-1", CallerKind.McpClient));
        var describe = Assert.IsType<DescribeResult>(core.Mcp.Describe(caller, "Order", 50).Payload);

        var hostile = Assert.Single(describe.Neighbors, n => n.Object == FixtureRepository.HostileLabel);
        // It is carried in the Object FIELD, verbatim, with its provenance — a structured datum,
        // not an instruction spliced into a narrative string.
        Assert.Equal(FixtureRepository.HostileLabel, hostile.Object);
        Assert.Equal("fixture-extractor", hostile.Provenance.ExtractorId);
    }

    // P1-STORE-08 — the labelled cache must equal its derivation, or it is a second source of truth.
    [Fact]
    public async Task ClaimCache_EqualsItsDerivationFromFacts()
    {
        using var core = OpenCore();
        await core.RefreshScopeAsync("fixture", "rev-1");

        var derivedOnce = core.Projections.DeriveClaimCurrent();
        var derivedAgain = core.Projections.DeriveClaimCurrent();

        Assert.Equal(derivedOnce, derivedAgain);
        Assert.NotEmpty(derivedOnce);
        // A relation supported only by an Inferred assertion must not read Verified in the cache.
        var persisted = Assert.Single(derivedOnce, r => r.Predicate == "persisted_in");
        Assert.Equal(nameof(VerificationStatus.Inferred), persisted.Status);
    }

    // P1-FRESH-01 — silent watcher loss. Fails RED against staleness measured from the daemon's own
    // last event, which reads perfectly fresh while the graph rots.
    [Fact]
    public async Task FreshnessProber_DetectsDriftAgainstTheRepositoryNotTheDaemon()
    {
        using var core = OpenCore();
        await core.RefreshScopeAsync("fixture", "rev-1");

        // The repository moved on; no watcher event ever arrived.
        var probe = new StubRevisionProbe("rev-2");
        var prober = new FreshnessProber(core.Store, probe, core.Incidents);

        var drifts = prober.Probe(["fixture"], DateTimeOffset.UtcNow);

        var drift = Assert.Single(drifts);
        Assert.Equal("rev-2", drift.ObservedRevision);
        Assert.Equal("rev-1", drift.IndexedRevision);
        Assert.Contains(core.Incidents.Unacknowledged(), i => i.IncidentClass == FreshnessProber.DriftIncidentClass);
    }

    [Fact]
    public async Task FreshnessProber_WhenRevisionsAgree_RaisesNothing()
    {
        using var core = OpenCore();
        await core.RefreshScopeAsync("fixture", "rev-1");

        var prober = new FreshnessProber(core.Store, new StubRevisionProbe("rev-1"), core.Incidents);

        Assert.Empty(prober.Probe(["fixture"], DateTimeOffset.UtcNow));
    }

    // E11/E12 — the rendered surface, and consistency across surfaces: the pane and the MCP tool
    // must agree about the same node, because a quantity with two homes eventually disagrees.
    [Fact]
    public async Task PaneAndMcpTool_AgreeOnTheSameNodesEvidence()
    {
        using var core = OpenCore();
        await core.RefreshScopeAsync("fixture", "rev-1");

        var pane = new EvidencePaneViewModel(new LocalWorkspaceQueries(core.Projections));
        await pane.LoadAsync();
        await pane.SelectAsync("Order");

        var caller = new McpCallerContext("ws-1", "session-1", SessionProcessingClass.LocalOnly,
            new CallerPrincipal("agent-1", CallerKind.McpClient));
        var describe = Assert.IsType<DescribeResult>(core.Mcp.Describe(caller, "Order", 50).Payload);

        var relatedSection = Assert.Single(pane.Provenance, s => s.Heading == "Related nodes");
        Assert.Equal(describe.Neighbors.Count, relatedSection.Lines.Count);
    }

    public void Dispose()
    {
        _fixture.Dispose();
        try
        {
            Directory.Delete(_dataDirectory, recursive: true);
        }
        catch (IOException)
        {
            // Leaked temp state must never fail a run.
        }
    }

    private sealed class StubRevisionProbe(string revision) : IRevisionProbe
    {
        public string? ObservedRevision(string scopeId) => revision;
    }
}
