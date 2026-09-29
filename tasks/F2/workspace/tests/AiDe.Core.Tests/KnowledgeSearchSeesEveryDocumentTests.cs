using AiDe.Core;
using AiDe.Core.Extraction;
using AiDe.Core.Facts;
using AiDe.Core.Projections;

namespace AiDe.Core.Tests;

/// <summary>
/// A knowledge search looks at every knowledge document, not at the first page of them.
/// </summary>
/// <remarks>
/// <para><b>DC-035's third instance, made checkable.</b> The knowledge projection has had a cap
/// applied before a filter three times. First it read the first 200 <c>has_type</c> assertions and
/// filtered THOSE to knowledge — the 200 were C# types in alphabetical order, so a workspace holding
/// 468 knowledge nodes returned nothing. Then the knowledge read moved into the query but stayed
/// capped at 200 ids while the TERM was still matched in memory afterwards, so a search saw the
/// alphabetically first 200 of 1,255 and a document sorting later was reported as not existing.</para>
///
/// <para>Both fixes were real and both left the defect in place one step along. What was missing was
/// a test that asks for something the cap would have hidden, which is why this fixture puts the
/// match deliberately past it.</para>
/// </remarks>
public sealed class KnowledgeSearchSeesEveryDocumentTests : IDisposable
{
    private readonly string _dir = Path.Combine(
        Path.GetTempPath(), "aide-knowledge-search", Guid.NewGuid().ToString("N"));

    public KnowledgeSearchSeesEveryDocumentTests() => Directory.CreateDirectory(_dir);

    public void Dispose()
    {
        try { Directory.Delete(_dir, recursive: true); } catch (IOException) { }
    }

    /// <summary>
    /// A workspace whose only interesting document sorts well past any plausible id cap.
    /// </summary>
    /// <remarks>
    /// The filler ids start with "aaa" and the target with "zzz", so ordering by id puts the target
    /// last. `MaxNodesCeiling` is 200 and there are 400 fillers: a read that caps before filtering
    /// cannot reach the target however the cap is spelled.
    /// </remarks>
    private WorkspaceCore Fill(int fillers = 400)
    {
        var core = WorkspaceCore.Open("ws", _dir, Path.Combine(_dir, "data"), new FixtureExtractor());
        var assertions = new List<EvidenceAssertion>();
        var provenance = new Provenance("docs/x.md", "1", "knowledge", "1", DateTimeOffset.UtcNow);

        void Document(string id, string type)
        {
            assertions.Add(new EvidenceAssertion(
                "knowledge:docs", "rev-1", id, "has_type", type,
                EvidenceOrigin.Static, VerificationStatus.Verified, provenance));
            assertions.Add(new EvidenceAssertion(
                "knowledge:docs", "rev-1", id, "node_class", "knowledge",
                EvidenceOrigin.Static, VerificationStatus.Verified, provenance));
        }

        for (var i = 0; i < fillers; i++)
        {
            Document($"aaa-filler-{i:D4}", "note");
        }

        Document("zzz-the-one-being-searched-for", "adr");

        using var writer = core.Store.BeginWrite();
        writer.DesireScopeGeneration("knowledge:docs", 1, "rev-1");
        writer.CommitSnapshot("knowledge:docs", 1, "rev-1", assertions, complete: true);

        foreach (var id in assertions.Select(a => a.Subject).Distinct(StringComparer.Ordinal))
        {
            writer.UpsertNode(id, "knowledge", id);
        }

        writer.Commit();
        return core;
    }

    [Fact]
    public void ATermMatchingOnlyALateDocumentStillFindsIt()
    {
        using var core = Fill();

        var result = core.Projections.Knowledge(new KnowledgeQuery("searched-for", null, 20));

        Assert.True(result.Nodes.Count == 1,
            $"the search returned {result.Nodes.Count} document(s); the one that matches sorts past "
            + "the id cap, so a filter applied after the read cannot see it");

        Assert.Equal("zzz-the-one-being-searched-for", result.Nodes[0].NodeId);
    }

    [Fact]
    public void ATypeMatchingOnlyALateDocumentStillFindsIt()
    {
        // The type filter had the same shape as the term filter and would have failed the same way.
        using var core = Fill();

        var result = core.Projections.Knowledge(new KnowledgeQuery(null, "adr", 20));

        Assert.Single(result.Nodes);
        Assert.Equal("zzz-the-one-being-searched-for", result.Nodes[0].NodeId);
    }

    [Fact]
    public void WhatWasLeftOutIsCountedAgainstWhatMatched()
    {
        // Omitted used to be counted against what was READ, which equalled what matched only while
        // the filter ran after the cap. A number that is right for the wrong reason stops being
        // right the moment the reason changes.
        using var core = Fill();

        var result = core.Projections.Knowledge(new KnowledgeQuery("filler", null, 10));

        Assert.Equal(10, result.Nodes.Count);
        Assert.Equal(390, result.Bounds.OmittedNodes);
    }

    [Fact]
    public void AnUnmatchedTermReturnsNothingRatherThanTheFirstPage()
    {
        // The opposite failure, and the one a user reads as "the search is broken": a filter that is
        // dropped somewhere returns the unfiltered head of the list, which looks like results.
        using var core = Fill();

        var result = core.Projections.Knowledge(new KnowledgeQuery("nothing-matches-this", null, 20));

        Assert.Empty(result.Nodes);
        Assert.Equal(0, result.Bounds.OmittedNodes);
    }
}
