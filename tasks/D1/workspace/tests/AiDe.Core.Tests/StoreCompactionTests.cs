using AiDe.Core.Store;

namespace AiDe.Core.Tests;

/// <summary>
/// The compaction policy for the defect P1-PERF measured: refresh p95 is 192 ms on a fresh store,
/// 567 ms after ten generations and 785 ms after twenty, against a 500 ms budget. Append-only growth
/// is the cause, and it is the design working as intended — so the fix prunes superseded generations
/// by rebuilding, never by deleting facts from the live store.
/// </summary>
public sealed class StoreCompactionTests
{
    private static void CommitGenerations(TestWorkspace workspace, string scope, int count)
    {
        for (var generation = 1; generation <= count; generation++)
        {
            using var writer = workspace.Store.BeginWrite();
            var revision = $"rev-{generation}";
            writer.DesireScopeGeneration(scope, generation, revision);
            writer.CommitSnapshot(scope, generation, revision,
                [
                    TestWorkspace.Assertion("Order", "depends_on", "OrderRepository", scope, revision),
                    TestWorkspace.Assertion("Order", "persisted_in", $"table_{generation}", scope, revision),
                ],
                complete: true);
            writer.Commit();
        }
    }

    [Fact]
    public void ScopesUnderTheThreshold_AreNotCompacted()
    {
        // ONE generation is the whole store: there is nothing superseded to reclaim. The threshold
        // used to be eight, from the latency curve, and this fixture used to hold three — under it.
        // It moved to one when measurement showed a real workspace sitting at TWO generations, well
        // under the old trigger and already half superseded (53.3 MB of which 27.9 MB was dead).
        using var workspace = TestWorkspace.Create();
        CommitGenerations(workspace, "fixture", 1);

        using (var reader = workspace.Store.BeginRead())
        {
            Assert.Empty(StoreCompactor.ScopesNeedingCompaction(reader));
        }

        workspace.Store.Dispose();
        var result = new StoreCompactor(workspace.DatabasePath).Compact();

        Assert.False(result.Ran);
        Assert.Contains("No scope", result.Summary, StringComparison.Ordinal);
    }

    [Fact]
    public void AScopeOverTheThreshold_IsFlaggedForCompaction()
    {
        using var workspace = TestWorkspace.Create();
        CommitGenerations(workspace, "fixture", 12);

        using var reader = workspace.Store.BeginRead();
        var needing = StoreCompactor.ScopesNeedingCompaction(reader);

        var (scope, generations) = Assert.Single(needing);
        Assert.Equal("fixture", scope);
        Assert.Equal(12, generations);
    }

    // The property that makes compaction safe: current evidence is untouched.
    [Fact]
    public void Compaction_LeavesCurrentEvidenceIdentical()
    {
        using var workspace = TestWorkspace.Create();
        CommitGenerations(workspace, "fixture", 12);

        List<string> before;
        using (var reader = workspace.Store.BeginRead())
        {
            before = [.. reader.CurrentAssertions("fixture")
                .Select(a => $"{a.Subject}|{a.Predicate}|{a.Object}|{a.ArtifactRevision}")];
        }

        workspace.Store.Dispose();
        var result = new StoreCompactor(workspace.DatabasePath).Compact();
        Assert.True(result.Ran);

        workspace.Reopen();
        using var after = workspace.Store.BeginRead();
        var now = after.CurrentAssertions("fixture")
            .Select(a => $"{a.Subject}|{a.Predicate}|{a.Object}|{a.ArtifactRevision}")
            .ToList();

        Assert.Equal(before, now);
    }

    [Fact]
    public void Compaction_DropsSupersededGenerationsAndReportsWhatItDid()
    {
        using var workspace = TestWorkspace.Create();
        CommitGenerations(workspace, "fixture", 12);
        workspace.Store.Dispose();

        var result = new StoreCompactor(workspace.DatabasePath).Compact(retain: 2);

        Assert.True(result.Ran);
        Assert.Equal(1, result.ScopesCompacted);
        Assert.Equal(10, result.GenerationsDropped);
        Assert.True(result.AssertionsDropped > 0);
        Assert.Contains("superseded generation", result.Summary, StringComparison.Ordinal);

        workspace.Reopen();
        using var reader = workspace.Store.BeginRead();
        Assert.Equal(2, StoreCompactor.ScopesNeedingCompaction(reader, threshold: 0).Single().Generations);
    }

    // The invariant must survive the rebuild: a compacted store is still append-only.
    [Fact]
    public void AfterCompaction_FactsAreStillImmutable()
    {
        using var workspace = TestWorkspace.Create();
        CommitGenerations(workspace, "fixture", 12);
        workspace.Store.Dispose();
        new StoreCompactor(workspace.DatabasePath).Compact();
        workspace.Reopen();

        using var writer = workspace.Store.BeginWrite();
        var ex = Assert.Throws<WorkspaceStoreException>(() =>
            writer.ExecuteRawInternal("UPDATE evidence_assertion_fact SET object = 'Tampered';"));

        Assert.Equal(StoreErrorCodes.ImmutableViolation, ex.ErrorCode);
    }

    [Fact]
    public void AfterCompaction_TheStoreIsSmaller()
    {
        using var workspace = TestWorkspace.Create();
        CommitGenerations(workspace, "fixture", 30);
        workspace.Store.Dispose();

        var result = new StoreCompactor(workspace.DatabasePath).Compact();

        Assert.True(result.BytesAfter < result.BytesBefore,
            $"{result.BytesBefore} -> {result.BytesAfter} bytes");
    }

    [Fact]
    public void Compaction_LeavesNoTemporaryFilesBehind()
    {
        using var workspace = TestWorkspace.Create();
        CommitGenerations(workspace, "fixture", 12);
        workspace.Store.Dispose();

        new StoreCompactor(workspace.DatabasePath).Compact();

        Assert.False(File.Exists(workspace.DatabasePath + ".compacting"));
        Assert.False(File.Exists(workspace.DatabasePath + ".superseded"));
    }

    [Fact]
    public void WhatSurvivesCompactionIsExactlyWhatRenders()
    {
        // The safety argument for retaining ONE generation, made checkable: every committed snapshot
        // is complete (a failed extraction returns before committing), so the newest is always the
        // one the graph draws. If that ever stops being true, retaining one would delete the
        // rendering snapshot — so this asserts the property the default rests on.
        using var workspace = TestWorkspace.Create();
        CommitGenerations(workspace, "fixture", 5);

        IReadOnlyList<string> Rendered()
        {
            using var reader = workspace.Store.BeginRead();
            return [.. reader.AllCurrentAssertions().Select(a => $"{a.Subject}|{a.Predicate}|{a.Object}").Order(StringComparer.Ordinal)];
        }

        var before = Rendered();
        workspace.Store.Dispose();

        var result = new StoreCompactor(workspace.DatabasePath).Compact();
        Assert.True(result.Ran);

        workspace.Reopen();

        Assert.Equal(before, Rendered());
    }

    [Fact]
    public void Compaction_HandlesSeveralScopesIndependently()
    {
        using var workspace = TestWorkspace.Create();
        CommitGenerations(workspace, "busy", 12);
        CommitGenerations(workspace, "quiet", 2);
        CommitGenerations(workspace, "untouched", 1);
        workspace.Store.Dispose();

        var result = new StoreCompactor(workspace.DatabasePath).Compact();

        // Every scope holding something superseded is reclaimed; a scope at one generation holds
        // nothing superseded and is left alone. Under the old defaults "quiet" was spared because
        // two generations was under the threshold — which was precisely the case that let a real
        // workspace double in size without ever tripping.
        Assert.Equal(2, result.ScopesCompacted);

        workspace.Reopen();
        using var reader = workspace.Store.BeginRead();
        var counts = StoreCompactor.ScopesNeedingCompaction(reader, threshold: 0)
            .ToDictionary(x => x.ScopeId, x => x.Generations);

        Assert.Equal(1, counts["busy"]);
        Assert.Equal(1, counts["quiet"]);
        Assert.Equal(1, counts["untouched"]);
    }
}

/// <summary>
/// The policy half: the operator is told when a workspace has drifted past the point where refresh
/// is measurably slow, rather than the slowdown being absorbed silently.
/// </summary>
public sealed class CompactionPolicyTests : IDisposable
{
    private readonly FixtureRepository _fixture = FixtureRepository.Create();
    private readonly string _data =
        Path.Combine(Path.GetTempPath(), "aide-compact-policy", Guid.NewGuid().ToString("N"));

    [Fact]
    public async Task AQuietWorkspace_RaisesNoCompactionIncident()
    {
        using var core = WorkspaceCore.Open("ws-1", _fixture.Root, _data);
        await core.RefreshScopeAsync("fixture", "rev-1");

        var needing = core.CheckCompactionNeeded();

        Assert.Empty(needing);
        Assert.DoesNotContain(core.Incidents.Unacknowledged(),
            i => i.IncidentClass == "store.compaction_due");
    }

    [Fact]
    public async Task AWorkspacePastTheThreshold_RaisesAnIncidentNamingTheScope()
    {
        using var core = WorkspaceCore.Open("ws-1", _fixture.Root, _data);
        for (var i = 1; i <= 10; i++)
        {
            await core.RefreshScopeAsync("fixture", $"rev-{i}");
        }

        var needing = core.CheckCompactionNeeded();

        Assert.Single(needing);
        var incident = Assert.Single(core.Incidents.Unacknowledged(),
            i => i.IncidentClass == "store.compaction_due");
        // The message must say which scope and why, not merely that something is slow.
        Assert.Equal("fixture", incident.ScopeId);
        Assert.Contains("generations", incident.Message, StringComparison.Ordinal);
    }

    public void Dispose()
    {
        _fixture.Dispose();
        try { Directory.Delete(_data, recursive: true); } catch (IOException) { }
    }
}
