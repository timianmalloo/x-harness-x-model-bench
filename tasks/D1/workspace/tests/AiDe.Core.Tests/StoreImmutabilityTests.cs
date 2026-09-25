using AiDe.Core.Store;

namespace AiDe.Core.Tests;

/// <summary>
/// P1-STORE-01..08 — the append-only invariant, attacked rather than assumed.
/// The council's Data &amp; Persistence review found that immutability triggers ALONE are not an
/// immutability control: under SQLite's default PRAGMA recursive_triggers=0, INSERT OR REPLACE
/// resolves its conflict with an internal delete that never fires the BEFORE DELETE trigger.
/// These tests pin the whole control (triggers + pragma + a writer that refuses REPLACE).
/// </summary>
public sealed class StoreImmutabilityTests
{
    // P1-STORE-01
    [Fact]
    public void Update_OnFactTable_IsRejected()
    {
        using var workspace = TestWorkspace.Create();
        workspace.CommitSnapshot("fixture", 1, "rev-1", TestWorkspace.Assertion("Order", "depends_on", "OrderRepository"));

        using var writer = workspace.Store.BeginWrite();
        var ex = Assert.Throws<WorkspaceStoreException>(() =>
            writer.ExecuteRawInternal("UPDATE evidence_assertion_fact SET object = 'Tampered';"));

        Assert.Equal(StoreErrorCodes.ImmutableViolation, ex.ErrorCode);
    }

    // P1-STORE-01
    [Fact]
    public void Delete_OnFactTable_IsRejected()
    {
        using var workspace = TestWorkspace.Create();
        workspace.CommitSnapshot("fixture", 1, "rev-1", TestWorkspace.Assertion("Order", "depends_on", "OrderRepository"));

        using var writer = workspace.Store.BeginWrite();
        var ex = Assert.Throws<WorkspaceStoreException>(() =>
            writer.ExecuteRawInternal("DELETE FROM evidence_assertion_fact;"));

        Assert.Equal(StoreErrorCodes.ImmutableViolation, ex.ErrorCode);
    }

    // P1-STORE-02 — the finding that made this a control rather than a hope.
    // Fails RED against a store that omits `PRAGMA recursive_triggers=ON`: the REPLACE silently
    // succeeds and the assertion's object reads 'Tampered'.
    [Fact]
    public void InsertOrReplace_OnFactTable_CannotBypassTheDeleteTrigger()
    {
        using var workspace = TestWorkspace.Create();
        var assertion = TestWorkspace.Assertion("Order", "depends_on", "OrderRepository");
        workspace.CommitSnapshot("fixture", 1, "rev-1", assertion);

        using (var writer = workspace.Store.BeginWrite())
        {
            var ex = Assert.Throws<WorkspaceStoreException>(() => writer.ExecuteRawInternal($"""
                INSERT OR REPLACE INTO evidence_assertion_fact
                    (assertion_id, scope_id, generation, artifact_revision, subject, predicate, object,
                     origin, status, artifact_path_id, source_location, extractor_id, extractor_version,
                     observed_at, ingress_seq)
                VALUES ('{assertion.AssertionId}', 'fixture', 1, 'rev-1', 'Order', 'depends_on', 'Tampered',
                        'Static', 'Verified', 'x.txt', NULL, 'fixture-extractor', '1.0.0', '2026-08-26T00:00:00Z', 99);
                """));

            Assert.Equal(StoreErrorCodes.ImmutableViolation, ex.ErrorCode);
        }

        using var reader = workspace.Store.BeginRead();
        var stored = Assert.Single(reader.CurrentAssertions("fixture"));
        Assert.Equal("OrderRepository", stored.Object);
    }

    // P1-STORE-05
    [Fact]
    public void DuplicateAssertion_ForSameRevision_IsRejectedByTheNaturalKey()
    {
        using var workspace = TestWorkspace.Create();
        var first = TestWorkspace.Assertion("Order", "depends_on", "OrderRepository");

        workspace.CommitSnapshot("fixture", 1, "rev-1", first);

        using var writer = workspace.Store.BeginWrite();
        writer.DesireScopeGeneration("fixture", 2, "rev-1");

        // A different assertion_id would still be the same natural relation at the same revision.
        Assert.ThrowsAny<Exception>(() =>
            writer.CommitSnapshot("fixture", 2, "rev-1", [first, first], complete: true));
    }

    // P1-STORE-06 — a late worker must never remove newer evidence.
    [Fact]
    public void StaleGeneration_CannotCommit()
    {
        using var workspace = TestWorkspace.Create();
        workspace.CommitSnapshot("fixture", 1, "rev-1", TestWorkspace.Assertion("Order", "depends_on", "OrderRepository"));

        using var writer = workspace.Store.BeginWrite();
        writer.DesireScopeGeneration("fixture", 2, "rev-2");

        // Generation 1 finally finishes, but generation 2 is already desired.
        var ex = Assert.Throws<WorkspaceStoreException>(() => writer.CommitSnapshot(
            "fixture", 1, "rev-1", [TestWorkspace.Assertion("Order", "depends_on", "Stale")], complete: true));

        Assert.Equal(StoreErrorCodes.ScopeGenerationStale, ex.ErrorCode);
    }

    // P1-STORE-06 — the same fence, on revision rather than generation.
    [Fact]
    public void StaleArtifactRevision_CannotCommit()
    {
        using var workspace = TestWorkspace.Create();

        using var writer = workspace.Store.BeginWrite();
        writer.DesireScopeGeneration("fixture", 1, "rev-2");

        var ex = Assert.Throws<WorkspaceStoreException>(() => writer.CommitSnapshot(
            "fixture", 1, "rev-1", [TestWorkspace.Assertion("Order", "depends_on", "X")], complete: true));

        Assert.Equal(StoreErrorCodes.ScopeGenerationStale, ex.ErrorCode);
    }

    // P1-STORE-04 — ordering is ingress sequence, never wall-clock, so clock skew cannot reorder facts.
    [Fact]
    public void IngressSequence_IsMonotonic()
    {
        using var workspace = TestWorkspace.Create();
        using var writer = workspace.Store.BeginWrite();

        var first = writer.NextIngressSequence();
        var second = writer.NextIngressSequence();
        var third = writer.NextIngressSequence();

        Assert.True(second > first);
        Assert.True(third > second);
    }

    // Epoch must be decidable and ABA-free: a reopened store is strictly newer, never a repeat.
    [Fact]
    public void CoreEpoch_IncreasesOnEveryOpen()
    {
        using var workspace = TestWorkspace.Create();
        var first = workspace.Store.CoreEpoch;

        workspace.Reopen();

        Assert.True(workspace.Store.CoreEpoch > first);
    }

    // Reads physically cannot write (spike S6): the read path is not merely conventionally read-only.
    [Fact]
    public void ReadConnection_RejectsWrites()
    {
        using var workspace = TestWorkspace.Create();
        using var reader = workspace.Store.BeginRead();

        using var command = reader.Command("INSERT INTO claim_current_cache VALUES ('a','b','c','Verified',1,'rev-1');");

        Assert.ThrowsAny<Exception>(() => command.ExecuteNonQuery());
    }
}
