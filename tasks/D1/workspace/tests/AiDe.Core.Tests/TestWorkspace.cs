using AiDe.Core.Facts;
using AiDe.Core.Store;

namespace AiDe.Core.Tests;

/// <summary>
/// A disposable workspace on a real SQLite file. Phase-1 store behaviour is only meaningful against
/// the real engine — an in-memory fake would not exhibit the trigger/pragma semantics these tests
/// exist to pin (D4: integration against the real dependency, not a substitute).
/// </summary>
internal sealed class TestWorkspace : IDisposable
{
    private readonly string _directory;

    private TestWorkspace(string directory, WorkspaceStore store)
    {
        _directory = directory;
        Store = store;
    }

    public WorkspaceStore Store { get; private set; }

    public string DatabasePath => Path.Combine(_directory, "workspace.db");

    public static TestWorkspace Create()
    {
        var directory = Path.Combine(Path.GetTempPath(), "aide-tests", Guid.NewGuid().ToString("N"));
        Directory.CreateDirectory(directory);
        var store = WorkspaceStore.Open(Path.Combine(directory, "workspace.db"));
        return new TestWorkspace(directory, store);
    }

    /// <summary>
    /// Closes and reopens the store, standing in for a process restart. Used to prove that recovery —
    /// not a lucky in-memory field — is what resolves a pending dispatch.
    /// </summary>
    public void Reopen()
    {
        Store.Dispose();
        Store = WorkspaceStore.Open(DatabasePath);
    }

    public static EvidenceAssertion Assertion(
        string subject, string predicate, string @object,
        string scopeId = "fixture", string revision = "rev-1",
        VerificationStatus status = VerificationStatus.Verified,
        string extractorId = "fixture-extractor")
        => new(scopeId, revision, subject, predicate, @object, EvidenceOrigin.Static, status,
            new Provenance($"{subject}.txt", "1:1", extractorId, "1.0.0",
                new DateTimeOffset(2026, 8, 26, 0, 0, 0, TimeSpan.Zero)));

    /// <summary>Commits one complete snapshot in the shape the ingestion path would.</summary>
    public void CommitSnapshot(string scopeId, long generation, string revision, params EvidenceAssertion[] assertions)
    {
        using var writer = Store.BeginWrite();
        writer.DesireScopeGeneration(scopeId, generation, revision);
        writer.CommitSnapshot(scopeId, generation, revision, assertions, complete: true);
        writer.Commit();
    }

    public void Dispose()
    {
        Store.Dispose();
        try
        {
            Directory.Delete(_directory, recursive: true);
        }
        catch (IOException)
        {
            // A WAL sidecar handle can linger briefly on Windows; a leaked temp dir must never
            // fail a test run, so this is swallowed deliberately rather than retried.
        }
    }
}
