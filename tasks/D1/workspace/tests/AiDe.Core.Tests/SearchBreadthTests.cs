using AiDe.Core.Projections;
using AiDe.Core.Store;

namespace AiDe.Core.Tests;

/// <summary>
/// Search reaches a node through its attribute values, and says why each row is there.
/// </summary>
/// <remarks>
/// <para><b>The question identity search cannot answer.</b> Asked for by the design session (§4i):
/// the canvas search box filtered loaded node labels client-side, and the user wanted to search by
/// content and keyword. MEASURED on TheTerrace before building: matching attribute values reaches
/// 1–14 nodes per term that identity search cannot reach at all. <c>addEventListener</c> matched ONE
/// node by identity and could not find the class that has that member; a Bicep resource's deployed
/// name matched the name and not the resource.</para>
///
/// <para><b>An attribute match returns the OWNER, never the value.</b> The original query excluded
/// attribute objects deliberately — a value is not a node, and offering <c>api_version = 2023-01-01</c>
/// as something to navigate to is how dates got into the graph. The exclusion was right about the
/// object and wrong about the subject: the owner is a real node and it is the answer.</para>
///
/// <para><b>Why a row must carry its reason.</b> Searching <c>addEventListener</c> and being shown a
/// class called <c>Element</c> is correct, and indistinguishable from a defect until the row says
/// <c>has_member = addEventListener</c>. A result whose relevance is invisible is read as a wrong
/// result, and a search people distrust is a search people stop using.</para>
/// </remarks>
public sealed class SearchBreadthTests
{
    /// <summary>A tiny workspace: two classes with members, one Bicep resource with a folded name.</summary>
    private static TestWorkspace Seeded()
    {
        var ws = TestWorkspace.Create();

        ws.CommitSnapshot(
            "fixture", 1, "rev-1",
            TestWorkspace.Assertion("app.Element", "has_type", "typescript-class"),
            TestWorkspace.Assertion("app.Element", "has_member", "+ addEventListener()"),
            TestWorkspace.Assertion("app.Element", "has_member", "+ focus()"),
            TestWorkspace.Assertion("app.Widget", "has_type", "typescript-class"),
            TestWorkspace.Assertion("app.Widget", "has_member", "+ render()"),
            TestWorkspace.Assertion("infra.storage", "has_type", "bicep-resource"),
            TestWorkspace.Assertion("infra.storage", "resource_name", "theterraces00dp"),
            TestWorkspace.Assertion("app.Element", "depends_on", "app.Widget"));

        return ws;
    }

    private static FindResult Find(TestWorkspace ws, string term) =>
        new ProjectionService(ws.Store).Find(term, 50);

    [Fact]
    public void AMemberNameFindsTheTypeThatDeclaresIt()
    {
        // The measured motivating case. `addEventListener` is a member VALUE; the thing a person
        // wants is the class that has it, and identity search cannot reach it at all.
        using var ws = Seeded();

        var match = Assert.Single(Find(ws, "addEventListener").Matches);

        Assert.Equal("app.Element", match.NodeId);
    }

    [Fact]
    public void AnAttributeMatchSaysWhichAttributeMatched()
    {
        using var ws = Seeded();

        var match = Assert.Single(Find(ws, "addEventListener").Matches);

        Assert.Equal(NodeMatchKind.Attribute, match.MatchedOn);
        Assert.NotNull(match.Evidence);
        Assert.Contains("has_member", match.Evidence);
        Assert.Contains("addEventListener", match.Evidence);
    }

    [Fact]
    public void AnIdentityMatchIsStillAnIdentityMatchAndCarriesNoEvidence()
    {
        // The id is its own evidence; repeating it in a second field is noise on a budgeted response.
        using var ws = Seeded();

        var match = Assert.Single(Find(ws, "app.Widget").Matches, m => m.NodeId == "app.Widget");

        Assert.Equal(NodeMatchKind.Identity, match.MatchedOn);
        Assert.Null(match.Evidence);
    }

    [Fact]
    public void AValueIsNeverReturnedAsThoughItWereANode()
    {
        // The reason the original query excluded attribute objects, and it still holds. The owner
        // comes back; the value does not become a row you can navigate to.
        using var ws = Seeded();

        var ids = Find(ws, "theterraces00dp").Matches.Select(m => m.NodeId).ToList();

        Assert.Contains("infra.storage", ids);
        Assert.DoesNotContain("theterraces00dp", ids);
    }

    [Fact]
    public void ANodeMatchingBothWaysIsReportedOnceAsAnIdentityMatch()
    {
        // Identity is the stronger reason and needs no explaining. Reporting the node twice, or
        // reporting the weaker reason, would both be worse than picking one.
        using var ws = Seeded();

        var element = Assert.Single(Find(ws, "Element").Matches, m => m.NodeId == "app.Element");

        Assert.Equal(NodeMatchKind.Identity, element.MatchedOn);
    }

    [Fact]
    public void ARelationObjectIsStillFoundAsANodeNotAsAnAttribute()
    {
        // `depends_on` is a RELATION: its object is a node, and it must keep being found as one.
        // Widening the attribute path must not quietly reclassify the relation path.
        using var ws = Seeded();

        var widget = Assert.Single(Find(ws, "app.Widget").Matches, m => m.NodeId == "app.Widget");

        Assert.Equal(NodeMatchKind.Identity, widget.MatchedOn);
    }

    [Fact]
    public void TheEvidenceIsBounded()
    {
        // A summary or a long expression would otherwise put unbounded text on a response whose
        // budget is the binding constraint on this product (INV-0003).
        using var ws = TestWorkspace.Create();
        ws.CommitSnapshot(
            "fixture", 1, "rev-1",
            TestWorkspace.Assertion("app.Thing", "has_type", "csharp-class"),
            TestWorkspace.Assertion("app.Thing", "has_member", "+ " + new string('x', 4_000) + "()"));

        var match = Assert.Single(Find(ws, "xxxxxxxxxx").Matches);

        Assert.NotNull(match.Evidence);
        Assert.True(match.Evidence.Length < 200,
            $"the evidence field carried {match.Evidence.Length} characters onto a budgeted response");
    }

    [Fact]
    public void AMissingTermFindsNothingRatherThanEverything()
    {
        // A widened query that matches too much is worse than one that matches too little: the
        // first is indistinguishable from a broken filter.
        using var ws = Seeded();

        Assert.Empty(Find(ws, "nothing-in-this-workspace").Matches);
    }
}
