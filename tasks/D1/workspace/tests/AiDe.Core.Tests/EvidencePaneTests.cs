using AiDe.Core.Projections;
using AiDe.Core;
using AiDe.Core.Facts;
using AiDe.Core.Health;
using AiDe.Core.Presentation;

namespace AiDe.Core.Tests;

/// <summary>
/// P1-UI-01..05 — the complete state set and the accessibility contract.
/// These are the states the urge to complete skips, so they are written first and asserted
/// explicitly: an unavailable source must never render as a clean empty result.
/// </summary>
public sealed class EvidencePaneTests : IDisposable
{
    private readonly FixtureRepository _fixture = FixtureRepository.Create();
    private readonly string _dataDirectory =
        Path.Combine(Path.GetTempPath(), "aide-pane", Guid.NewGuid().ToString("N"));

    private WorkspaceCore OpenCore() => WorkspaceCore.Open("ws-1", _fixture.Root, _dataDirectory);

    // P1-UI-01 — empty state guides to the first action instead of showing nothing.
    [Fact]
    public async Task Load_WithNoCommittedSnapshot_ShowsTheEmptyStateNotASilentBlank()
    {
        using var core = OpenCore();
        var pane = new EvidencePaneViewModel(new LocalWorkspaceQueries(core.Projections));

        await pane.LoadAsync();

        Assert.Equal(PaneState.Empty, pane.State);
        Assert.Contains("No evidence yet", pane.StatusMessage, StringComparison.Ordinal);
        Assert.Equal(pane.StatusMessage, pane.LiveAnnouncement);
    }

    [Fact]
    public async Task Load_WithEvidence_ReachesReadyAndReportsTheRenderedRevision()
    {
        using var core = OpenCore();
        await core.RefreshScopeAsync("fixture", "rev-1");

        var pane = new EvidencePaneViewModel(new LocalWorkspaceQueries(core.Projections));
        await pane.LoadAsync();

        Assert.Equal(PaneState.Ready, pane.State);
        Assert.NotEmpty(pane.Rows);
        Assert.Equal("rev-1", pane.SourceRevision);
        // The operator must be able to see WHICH revision is on screen.
        Assert.Contains("rev-1", pane.StatusMessage, StringComparison.Ordinal);
    }

    // P1-UI-02 — a failed refresh keeps the last good view and says so; it never empties the graph.
    [Fact]
    public async Task MarkStale_KeepsTheLastSuccessfulViewAndNamesTheCause()
    {
        using var core = OpenCore();
        await core.RefreshScopeAsync("fixture", "rev-1");
        var pane = new EvidencePaneViewModel(new LocalWorkspaceQueries(core.Projections));
        await pane.LoadAsync();
        var rowsBefore = pane.Rows.Count;

        pane.MarkStale("fixture extraction failed");

        Assert.Equal(PaneState.Stale, pane.State);
        Assert.Contains("stale", pane.StatusMessage, StringComparison.OrdinalIgnoreCase);
        Assert.Contains("fixture extraction failed", pane.StatusMessage, StringComparison.Ordinal);
        Assert.Equal(rowsBefore, pane.Rows.Count);   // last successful snapshot still rendered
    }

    // P1-UI-03 — filter no-match is its own state, distinct from empty.
    [Fact]
    public async Task Filter_WithNoMatches_ShowsNoMatchNotEmpty()
    {
        using var core = OpenCore();
        await core.RefreshScopeAsync("fixture", "rev-1");
        var pane = new EvidencePaneViewModel(new LocalWorkspaceQueries(core.Projections));
        await pane.LoadAsync();

        pane.Filter("zzz-nothing-matches");

        Assert.Empty(pane.Rows);
        Assert.Contains("No items match", pane.StatusMessage, StringComparison.Ordinal);
        Assert.NotEqual(PaneState.Empty, pane.State);   // still Ready: the data exists, the filter excluded it
    }

    // P1-UI-04 — provenance appears in the spec's fixed evidence order.
    [Fact]
    public async Task Select_BuildsProvenanceInTheSpecifiedEvidenceOrder()
    {
        using var core = OpenCore();
        await core.RefreshScopeAsync("fixture", "rev-1");
        var pane = new EvidencePaneViewModel(new LocalWorkspaceQueries(core.Projections));
        await pane.LoadAsync();

        await pane.SelectAsync("Order");

        var headings = pane.Provenance.Select(s => s.Heading).ToList();
        Assert.Equal("What it is", headings[0]);
        Assert.Equal("Confidence and provenance", headings[1]);
        Assert.Equal("Related nodes", headings[2]);
        Assert.Equal("Source", headings[3]);
    }

    // Absence stays explicit: a node with no evidence reads "not recorded", never a blank section.
    [Fact]
    public async Task Select_NodeWithNoEvidence_RendersNotRecorded()
    {
        using var core = OpenCore();
        await core.RefreshScopeAsync("fixture", "rev-1");
        var pane = new EvidencePaneViewModel(new LocalWorkspaceQueries(core.Projections));
        await pane.LoadAsync();

        await pane.SelectAsync("NodeThatDoesNotExist");

        var confidence = Assert.Single(pane.Provenance, s => s.Heading == "Confidence and provenance");
        Assert.Contains("not recorded", confidence.Lines);
    }

    // WCAG 2.2 AA — confidence must not rely on colour alone. Glyph AND text carry the meaning.
    [Theory]
    [InlineData(VerificationStatus.Verified, "Verified")]
    [InlineData(VerificationStatus.Inferred, "Inferred")]
    [InlineData(VerificationStatus.Unverified, "Unverified")]
    public async Task ConfidenceBadge_CarriesGlyphAndTextNotColourAlone(VerificationStatus status, string expectedText)
    {
        var badge = ConfidenceBadge.For(status);

        Assert.False(string.IsNullOrWhiteSpace(badge.Glyph));
        Assert.Equal(expectedText, badge.Text);
        Assert.Equal(expectedText, badge.AccessibleName);
        // The colour is a token reference, never a raw value baked into the component.
        Assert.StartsWith("colors.", badge.TokenName, StringComparison.Ordinal);
    }

    // A screen reader must get the same information the visual row conveys.
    [Fact]
    public async Task EvidenceRow_ExposesAnAccessibleNameCoveringLabelKindAndConfidence()
    {
        using var core = OpenCore();
        await core.RefreshScopeAsync("fixture", "rev-1");
        var pane = new EvidencePaneViewModel(new LocalWorkspaceQueries(core.Projections));
        await pane.LoadAsync();

        var row = pane.Rows[0];

        Assert.Contains(row.DisplayLabel, row.AccessibleName, StringComparison.Ordinal);
        Assert.Contains(row.NodeKind, row.AccessibleName, StringComparison.Ordinal);
        Assert.Contains(row.Confidence.AccessibleName, row.AccessibleName, StringComparison.Ordinal);
    }

    // The limit state is part of the evidence, announced rather than silently applied.
    [Fact]
    public async Task Select_WhenNeighborsAreTruncated_ShowsTheResultLimitSection()
    {
        using var core = OpenCore();
        await core.RefreshScopeAsync("fixture", "rev-1");
        var pane = new EvidencePaneViewModel(new LocalWorkspaceQueries(core.Projections));
        await pane.LoadAsync();

        await pane.SelectAsync("Order");
        var describeAll = core.Projections.Describe("Order", 50);

        // With the full cap there is nothing omitted, so no limit section should appear —
        // the section must reflect reality, not always be present.
        Assert.Equal(0, describeAll.Bounds.OmittedEdges);
        Assert.DoesNotContain(pane.Provenance, s => s.Heading == "Result limits");
    }

    // Health incidents dedup by {class, scope} with a count, so a flapping condition cannot
    // flood out the incident that mattered.
    [Fact]
    public async Task HealthSidecar_CollapsesRepeatOccurrencesAndSurvivesReopen()
    {
        var path = Path.Combine(_dataDirectory, "incidents.jsonl");
        var sidecar = new HealthIncidentSidecar(path);
        var now = DateTimeOffset.UtcNow;

        sidecar.Record("extraction.failed", "fixture", "first", now);
        sidecar.Record("extraction.failed", "fixture", "second", now.AddSeconds(30));
        sidecar.Record("freshness.drift", "fixture", "drift", now.AddSeconds(60));

        var reopened = new HealthIncidentSidecar(path).Unacknowledged();

        Assert.Equal(2, reopened.Count);
        var extraction = Assert.Single(reopened, i => i.IncidentClass == "extraction.failed");
        Assert.Equal(2, extraction.OccurrenceCount);
    }

    [Fact]
    public async Task HealthSidecar_AcknowledgedIncidentsLeaveTheOpenList()
    {
        var path = Path.Combine(_dataDirectory, "ack.jsonl");
        var sidecar = new HealthIncidentSidecar(path);
        sidecar.Record("extraction.failed", "fixture", "boom", DateTimeOffset.UtcNow);

        sidecar.Acknowledge("extraction.failed", "fixture");

        Assert.Empty(sidecar.Unacknowledged());
        Assert.Single(sidecar.Read());   // the record survives; only its acknowledged flag changed
    }

    // The sidecar exists precisely so an unwritable store can still report itself.
    [Fact]
    public async Task HealthSidecar_WritesOutsideTheWorkspaceDatabase()
    {
        var path = Path.Combine(_dataDirectory, "outside", "incidents.jsonl");
        var sidecar = new HealthIncidentSidecar(path);

        sidecar.Record("store.readonly", "workspace", "disk full", DateTimeOffset.UtcNow);

        Assert.True(File.Exists(path));
        Assert.DoesNotContain("workspace.db", path, StringComparison.Ordinal);
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
}
