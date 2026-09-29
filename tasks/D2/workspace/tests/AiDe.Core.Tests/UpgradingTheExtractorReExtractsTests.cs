using AiDe.Core;
using AiDe.Core.Extraction;
using AiDe.Core.Facts;

namespace AiDe.Core.Tests;

/// <summary>
/// A better extractor reaches a workspace that has already been indexed.
/// </summary>
/// <remarks>
/// <para><b>DC-044, made checkable.</b> The knowledge reader shipped, the generation was bumped, the
/// sidecar was invalidated — and a re-index of a real repository reported <i>"Indexed 66 of 66
/// scope(s): 0 assertion(s)"</i> while the Knowledge chip stayed at 0. Two independent guards
/// answered one question and only one of them had been taught about the new input.</para>
///
/// <para>These assert the OUTCOME an upgrade is for — new facts in the store — rather than the
/// mechanism that delivers it, so they survive the fix being implemented some other way.</para>
/// </remarks>
public sealed class UpgradingTheExtractorReExtractsTests : IDisposable
{
    private readonly string _dir = Path.Combine(
        Path.GetTempPath(), "aide-upgrade", Guid.NewGuid().ToString("N"));

    public UpgradingTheExtractorReExtractsTests() => Directory.CreateDirectory(_dir);

    public void Dispose()
    {
        try { Directory.Delete(_dir, recursive: true); } catch (IOException) { }
    }

    /// <summary>An extractor whose output grows between "releases", with nothing else changing.</summary>
    private sealed class UpgradeableExtractor : IExtractor
    {
        public int Facts { get; set; } = 1;

        public string ScopeKind => "fixture";

        public Task<ExtractionResult> ExtractAsync(ExtractionRequest request, CancellationToken cancellationToken)
        {
            var assertions = Enumerable.Range(0, Facts).Select(i => new EvidenceAssertion(
                request.ScopeId, request.ArtifactRevision,
                "node", "declares", $"thing{i}",
                EvidenceOrigin.Static, VerificationStatus.Verified,
                new Provenance("p", null, "test", "1", DateTimeOffset.UtcNow)));

            return Task.FromResult(new ExtractionResult([.. assertions], true, []));
        }
    }

    private WorkspaceCore Open(IExtractor extractor) =>
        WorkspaceCore.Open("ws", _dir, Path.Combine(_dir, "data"), extractor);

    [Fact]
    public async Task AnImprovedExtractorReachesAStoreAnOlderBuildWrote()
    {
        var extractor = new UpgradeableExtractor { Facts = 3 };
        using var core = Open(extractor);

        // What a previous release left behind: facts committed under the caller's own revision, with
        // nothing recording which reader produced them. This is the state on every machine that
        // indexed a workspace before the extractor improved.
        WriteAsAnOlderBuild(core, "scope", "rev-1");
        Assert.Equal(1, Count(core));

        // Same files, same revision, better extractor. Before the fix this returned an empty result
        // without calling the extractor at all — the shape the user saw as "Indexed 66 of 66
        // scope(s): 0 assertion(s)" with the Knowledge chip still reading 0.
        var again = await core.RefreshScopeAsync("scope", "rev-1");

        Assert.Equal(3, again.Assertions.Count);
        Assert.Equal(3, Count(core));
    }

    [Fact]
    public void TheStoredRevisionCarriesTheReaderThatProducedIt()
    {
        // The mechanism, asserted once: the natural key is
        // (scope, revision, subject, predicate, object, extractor) with no generation in it, so
        // without this the same fact re-read by a better extractor cannot be written at all.
        var stamped = SourceRevision.Stamp("rev-1");

        Assert.NotEqual("rev-1", stamped);
        Assert.Contains(ScopeFingerprints.ExtractorGeneration, stamped, StringComparison.Ordinal);
        Assert.Equal("rev-1", SourceRevision.Base(stamped));
        Assert.Equal(stamped, SourceRevision.Stamp(stamped));
    }

    [Fact]
    public async Task ReIndexingWithNothingChangedStillWritesNothing()
    {
        // The guard being fixed is load-bearing: re-indexing an unchanged workspace must stay a
        // no-op. A fix that got the upgrade case right by re-extracting everything every time would
        // pass the test above and be a different defect.
        var extractor = new UpgradeableExtractor { Facts = 2 };
        using var core = Open(extractor);

        await core.RefreshScopeAsync("scope", "rev-1");
        var again = await core.RefreshScopeAsync("scope", "rev-1");

        Assert.Empty(again.Assertions);
        Assert.Equal(2, Count(core));
    }

    [Fact]
    public void ASurfaceNeverShowsTheStamp()
    {
        // The stamp is an identity, not a thing to render. The user's status bar says "rev-1".
        Assert.Equal("rev-1", SourceRevision.Base(SourceRevision.Stamp("rev-1")));

        // Including one written by an older build, which is exactly what a stale scope renders.
        Assert.Equal("rev-1", SourceRevision.Base("rev-1+x2020-01-01.9"));

        // And a revision that never carried one is returned untouched.
        Assert.Equal("rev-1", SourceRevision.Base("rev-1"));
    }

    [Fact]
    public async Task ChangingTheExtractorWithoutBumpingTheGenerationWritesNothing()
    {
        // THE TRAP P3 WALKED UP TO. A reader's output changes; the generation is not bumped; every
        // guard downstream is still correct and the store keeps the old answer, because the stamped
        // revision is unchanged and the natural key has no room for "a different reader said it".
        //
        // It matters because the obvious alternative to a generation bump is to re-index harder —
        // and that does not work: `force` skips the fingerprint sidecar but not this guard, so a
        // forced full re-index on an unbumped generation prints "Indexed 66 of 66 scope(s): 0
        // assertion(s)" and writes nothing. That sentence is DC-044 verbatim.
        //
        // Asserted here as a red test rather than left as a live surprise, so the next person who
        // proposes "just force a re-index" finds out in CI (Ruling 133, the Data & Persistence
        // Architect's condition on P3).
        var extractor = new UpgradeableExtractor { Facts = 2 };
        using var core = Open(extractor);

        await core.RefreshScopeAsync("scope", "rev-1");
        Assert.Equal(2, Count(core));

        // The reader improves — the exact shape of P2, where two extractors began citing the file
        // instead of the scope id. Nothing else changes.
        extractor.Facts = 5;
        var again = await core.RefreshScopeAsync("scope", "rev-1");

        Assert.Empty(again.Assertions);
        Assert.Equal(2, Count(core));
    }

    /// <summary>Commits a snapshot the way a build with no revision stamp did.</summary>
    private static void WriteAsAnOlderBuild(WorkspaceCore core, string scopeId, string revision)
    {
        // Generation 0, so the core's own allocator (which starts at 1) still wins the desired-pair
        // check on the next commit rather than finding a newer generation already recorded.
        using var writer = core.Store.BeginWrite();
        writer.DesireScopeGeneration(scopeId, 0, revision);
        writer.CommitSnapshot(scopeId, 0, revision, [
            new EvidenceAssertion(
                scopeId, revision, "node", "declares", "thing0",
                EvidenceOrigin.Static, VerificationStatus.Verified,
                new Provenance("p", null, "test", "1", DateTimeOffset.UtcNow)),
        ], complete: true);
        writer.Commit();
    }

    private static int Count(WorkspaceCore core)
    {
        using var reader = core.Store.BeginRead();
        return reader.LatestCommittedSnapshot("scope")?.AssertionCount ?? 0;
    }
}
