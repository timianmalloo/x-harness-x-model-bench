using AiDe.Core.Presentation;
using AiDe.Core.Projections;
using AiDe.Testing;

namespace AiDe.Core.Tests;

/// <summary>
/// The evidence list states what it knows, and states the shape of what it could not read.
/// </summary>
/// <remarks>
/// <para><b>Two findings, one surface, one class between them.</b> The pane rendered
/// <c>ConfidenceBadge.For(VerificationStatus.Verified)</c> unconditionally for every row, and it
/// asked for fifty results using the <i>neighbour</i> ceiling and reported the answer as
/// <c>50 item(s)</c>. Both are the surface asserting something the read did not establish: one
/// invents a confidence, the other invents completeness.</para>
///
/// <para><b>The badge was never drawn.</b> This surface renders <c>EvidenceRow.ListLine</c>, which
/// does not include the confidence, so the hard-coded <i>Verified</i> survived only in
/// <c>AccessibleName</c> — a false provenance claim made exclusively to screen-reader users, in a
/// product whose design language names provenance laundering as a correctness defect.</para>
/// </remarks>
public sealed class TheEvidencePaneDoesNotInventConfidenceTests
{
    private const string Revision = "rev-7";

    /// <summary>A read surface that answers Find with exactly what the test wants to measure.</summary>
    private sealed class Finds(int matches, int omitted, bool byteCapped) : FakeWorkspaceQueries
    {
        /// <summary>What the pane asked for. The whole point of the ceiling case.</summary>
        public int RequestedMaxResults { get; private set; } = -1;

        public override Task<FindResult> FindAsync(string term, int maxResults, CancellationToken cancellationToken)
        {
            RequestedMaxResults = maxResults;

            var found = Enumerable.Range(0, matches)
                .Select(i => new FindMatch(
                    $"node-{i}", "class", $"Type{i}", AuthorshipOrigin.RepositoryArtifact))
                .ToList();

            return Task.FromResult(new FindResult(
                found,
                new ResultBounds(
                    MaxNodes: matches + omitted,
                    MaxEdges: 0,
                    MaxBytes: 65_536,
                    ReturnedNodes: matches,
                    OmittedNodes: omitted,
                    ReturnedEdges: 0,
                    OmittedEdges: 0,
                    ByteCapped: byteCapped,
                    NextCursor: null),
                Revision));
        }
    }

    [Fact]
    public async Task ARowWhoseProjectionCarriesNoStatus_ReadsNotRecorded_NeverVerified()
    {
        var pane = new EvidencePaneViewModel(new Finds(matches: 3, omitted: 0, byteCapped: false));

        await pane.LoadAsync();

        Assert.Equal(PaneState.Ready, pane.State);
        Assert.NotEmpty(pane.Rows);

        foreach (var row in pane.Rows)
        {
            Assert.Equal("Not recorded", row.Confidence.Text);
            Assert.Equal("?", row.Confidence.Glyph);

            // The accessible name is where the false claim lived, so it is where the assertion goes.
            Assert.DoesNotContain("Verified", row.AccessibleName, StringComparison.Ordinal);
            Assert.Contains("Not recorded", row.AccessibleName, StringComparison.Ordinal);
        }
    }

    [Fact]
    public async Task ThePaneAsksForTheSearchCeiling_NotTheNeighbourCeiling()
    {
        var queries = new Finds(matches: 1, omitted: 0, byteCapped: false);
        var pane = new EvidencePaneViewModel(queries);

        await pane.LoadAsync();

        Assert.Equal(ProjectionService.MaxSearchResultsCeiling, queries.RequestedMaxResults);

        // Named rather than implied: fifty is the neighbourhood bound, and a search that borrows it
        // stops at fifty rows and reports the number as if it were the answer. ProjectionService's
        // own remarks record this being found and fixed elsewhere; this pane was the unswept
        // instance.
        Assert.NotEqual(ProjectionService.MaxNeighborsCeiling, queries.RequestedMaxResults);
    }

    [Theory]
    [InlineData(4, 0, false, "4 item(s)")]
    [InlineData(4, 11, false, "≥ 4 item(s) (capped)")]
    [InlineData(4, 0, true, "≥ 4 item(s) (capped)")]
    public async Task ABoundedReadNeverLooksComplete(int matches, int omitted, bool byteCapped, string expected)
    {
        var pane = new EvidencePaneViewModel(new Finds(matches, omitted, byteCapped));

        await pane.LoadAsync();

        Assert.StartsWith(expected, pane.StatusMessage, StringComparison.Ordinal);
        Assert.Contains(Revision, pane.StatusMessage, StringComparison.Ordinal);
        Assert.Equal(pane.StatusMessage, pane.LiveAnnouncement);
    }
}
