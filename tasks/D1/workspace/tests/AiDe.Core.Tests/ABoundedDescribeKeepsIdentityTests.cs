using AiDe.Core;
using AiDe.Core.Extraction;
using AiDe.Core.Facts;

namespace AiDe.Core.Tests;

/// <summary>
/// A node that has more facts than the cap still comes back knowing what it is.
/// </summary>
/// <remarks>
/// <para>`AssertionsTouching` caps at <see cref="Projections.ProjectionService.MaxNeighborsCeiling"/>
/// and ordered `subject, predicate, object` — alphabetical, which is deterministic and says nothing
/// about importance. So a node with more relations than the cap lost its own type, owner and class to
/// its own links, and lost them in alphabetical order: WHICH facts survived depended on how the node
/// happened to be named.</para>
///
/// <para>Not hypothetical. MEASURED on TheTerrace: 12 of 877 knowledge documents were already over
/// the ceiling before anything was added to them, and it is why headings were rejected from the
/// knowledge reader — simulating them pushed `adr-0015-erasure-ledger-durable-model` to returning 44
/// headings and none of its `has_type`, `node_class`, `owned_by`, `refines` or `review_by`.</para>
/// </remarks>
public sealed class ABoundedDescribeKeepsIdentityTests : IDisposable
{
    private readonly string _dir = Path.Combine(
        Path.GetTempPath(), "aide-describe", Guid.NewGuid().ToString("N"));

    public ABoundedDescribeKeepsIdentityTests() => Directory.CreateDirectory(_dir);

    public void Dispose()
    {
        try { Directory.Delete(_dir, recursive: true); } catch (IOException) { }
    }

    /// <summary>
    /// A node whose identity sorts LATE and whose links sort early — the arrangement that hid it.
    /// </summary>
    /// <remarks>
    /// The relations are named `aaa…` so they sort before `has_type`, `node_class` and `owned_by`
    /// under the old ordering; there are more of them than the cap. A fixture whose identity happened
    /// to sort first would pass against the unfixed reader and prove nothing (DC-016).
    /// </remarks>
    private WorkspaceCore Crowded(int relations)
    {
        var core = WorkspaceCore.Open("ws", _dir, Path.Combine(_dir, "data"), new FixtureExtractor());
        var provenance = new Provenance("docs/x.md", "1:1", "test", "1", DateTimeOffset.UtcNow);
        var assertions = new List<EvidenceAssertion>();

        void Fact(string subject, string predicate, string obj) =>
            assertions.Add(new EvidenceAssertion(
                "knowledge:docs", "rev-1", subject, predicate, obj,
                EvidenceOrigin.Static, VerificationStatus.Verified, provenance));

        Fact("the-node", "has_type", "adr");
        Fact("the-node", "node_class", "knowledge");
        Fact("the-node", "owned_by", "@someone");
        Fact("the-node", "review_by", "2027-01-01");
        Fact("the-node", "declared_in", "knowledge:docs");

        for (var i = 0; i < relations; i++)
        {
            Fact("the-node", "aaa-relates-to", $"other-{i:D4}");
        }

        using var writer = core.Store.BeginWrite();
        writer.DesireScopeGeneration("knowledge:docs", 1, "rev-1");
        writer.CommitSnapshot("knowledge:docs", 1, "rev-1", assertions, complete: true);
        writer.Commit();

        return core;
    }

    [Fact]
    public void ANodeWithMoreLinksThanTheCapStillReportsItsOwnIdentity()
    {
        var cap = Projections.ProjectionService.MaxNeighborsCeiling;
        using var core = Crowded(relations: cap * 2);

        using var reader = core.Store.BeginRead();

        // The fixture proves it can reproduce before asserting anything: more facts than the cap,
        // and the identity really does sort after the relations.
        Assert.True(reader.CountAssertionsTouching("the-node") > cap);
        Assert.True(string.CompareOrdinal("aaa-relates-to", "has_type") < 0);

        var window = reader.AssertionsTouching("the-node", cap);

        foreach (var identity in EvidencePredicates.Identity)
        {
            Assert.True(
                window.Any(a => a.Subject == "the-node" && a.Predicate == identity),
                $"'{identity}' fell outside a {cap}-row window on a node with "
                + $"{reader.CountAssertionsTouching("the-node")} facts — the caller cannot tell what "
                + "this node even is");
        }
    }

    [Fact]
    public void TheRestOfTheWindowIsStillFilledWithRelations()
    {
        // Identity must not crowd out everything else: five facts first, the remaining 45 are links.
        var cap = Projections.ProjectionService.MaxNeighborsCeiling;
        using var core = Crowded(relations: cap * 2);

        using var reader = core.Store.BeginRead();
        var window = reader.AssertionsTouching("the-node", cap);

        Assert.Equal(cap, window.Count);
        Assert.Equal(
            cap - EvidencePredicates.Identity.Count,
            window.Count(a => a.Predicate == "aaa-relates-to"));
    }

    [Fact]
    public void TheOrderIsStillDeterministicWithinEachBand()
    {
        // The omission count only means something if the same query returns the same rows. Bands are
        // coarse; inside them the old alphabetical order still holds.
        var cap = Projections.ProjectionService.MaxNeighborsCeiling;
        using var core = Crowded(relations: cap * 2);

        using var reader = core.Store.BeginRead();

        var first = reader.AssertionsTouching("the-node", cap).Select(a => a.Object).ToList();
        var second = reader.AssertionsTouching("the-node", cap).Select(a => a.Object).ToList();

        Assert.Equal(first, second);

        var links = first.Where(o => o.StartsWith("other-", StringComparison.Ordinal)).ToList();
        Assert.Equal(links.Order(StringComparer.Ordinal), links);
    }

    [Fact]
    public void ANodeThatFitsIsUnchanged()
    {
        // Ordering matters only at the boundary. A small node must return everything it did before.
        using var core = Crowded(relations: 3);

        using var reader = core.Store.BeginRead();
        var window = reader.AssertionsTouching(
            "the-node", Projections.ProjectionService.MaxNeighborsCeiling);

        Assert.Equal(8, window.Count);
    }

    [Fact]
    public void TheIdentitySetAndItsSqlListCannotDrift()
    {
        // The set is used from C# and the query uses a generated literal list. A hand-written copy in
        // the SQL is exactly how the two halves of a rule drift apart.
        foreach (var predicate in EvidencePredicates.Identity)
        {
            Assert.Contains($"'{predicate}'", EvidencePredicates.IdentitySqlList, StringComparison.Ordinal);
        }

        // And identity is a SMALL set — "all attributes" would put forty has_member rows ahead of a
        // type's relations and replace one flood with another.
        Assert.True(EvidencePredicates.Identity.Count < 10);
        Assert.DoesNotContain("has_member", EvidencePredicates.Identity);
    }
}
