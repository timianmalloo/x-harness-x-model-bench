using System.Text.Json.Nodes;
using AiDe.Core.PromptCompilation;
using AiDe.Core.Sessions;

namespace AiDe.Core.Tests.PromptCompilation;

/// <summary>
/// ADR-0034 test 5 (US-D13): purge deletes <c>envelope-events.jsonl</c> and nothing else; a
/// traversal, a non-segment id and a junctioned session directory are refused before any file is
/// touched; the Session aggregate's own delete cascades to the envelope file by containment — first
/// acquiring it exclusively (refused whole while a writer holds it), deleting it under the held
/// handle, then removing the siblings.
/// </summary>
public sealed class PurgeAndTheSessionDeleteCascadeTests : IDisposable
{
    private readonly string _workspace = Path.Combine(Path.GetTempPath(), "aide-purge-" + Guid.NewGuid().ToString("n")[..8]);
    private readonly SessionConfigStore _sessions;
    private readonly SessionConfig _config;

    public PurgeAndTheSessionDeleteCascadeTests()
    {
        Directory.CreateDirectory(_workspace);
        _sessions = new SessionConfigStore(_workspace, SessionId.New(new DateTimeOffset(2026, 9, 12, 10, 0, 0, TimeSpan.Zero)));
        _config = _sessions.Create("payments", "w-1", [new AccountRef("anthropic", "max")], new AccountRef("anthropic", "max"), DateTimeOffset.UnixEpoch);
    }

    public void Dispose()
    {
        try
        {
            // A junction fixture is removed as a link (never recursed into): the target's files are
            // not the junction's to delete.
            foreach (var link in Directory.Exists(SessionPaths.SessionsRoot(_workspace))
                         ? Directory.EnumerateDirectories(SessionPaths.SessionsRoot(_workspace)).Where(d => new DirectoryInfo(d).Attributes.HasFlag(FileAttributes.ReparsePoint))
                         : [])
            {
                Directory.Delete(link, recursive: false);
            }

            Directory.Delete(_workspace, recursive: true);
        }
        catch (IOException)
        {
        }
        catch (UnauthorizedAccessException)
        {
        }

        GC.SuppressFinalize(this);
    }

    private string SessionDir => SessionPaths.SessionDirectory(_workspace, _config.SessionId);
    private string EnvelopeFile => Path.Combine(SessionDir, EnvelopeStore.FileName);

    private void WriteTwoEnvelopes()
    {
        using var store = EnvelopeStore.Open(SessionDir, new FixedTime(new DateTimeOffset(2026, 9, 12, 11, 0, 0, TimeSpan.Zero)));
        store.Append(new Opened("e1", "one", _config.SessionId, "claude-code", CompileModes.MechanicalOnly, null, PreCompile.ConstantsFor("1")));
        store.Append(new Opened("e2", "two", _config.SessionId, "claude-code", CompileModes.MechanicalOnly, null, PreCompile.ConstantsFor("1")));
    }

    [Fact]
    public void PurgeRemovesTheEnvelopeFileAndLeavesSessionJsonTheEventsFileAndEverySibling()
    {
        WriteTwoEnvelopes();
        File.WriteAllText(Path.Combine(SessionDir, "layout-host-a.json"), "{}");

        var plan = EnvelopePurge.Resolve(_workspace, _config.SessionId);

        // The confirmation names an identity, never a count alone (DC-120).
        Assert.Equal("payments", plan.Name);
        Assert.Equal(_config.SessionId, plan.SessionId);
        Assert.Equal(Path.GetFullPath(_workspace), plan.WorkspaceRoot);
        Assert.Equal(Path.GetFullPath(EnvelopeFile), plan.ResolvedFilePath);
        Assert.Equal(2, plan.EnvelopeCount);
        Assert.Equal(new DateTimeOffset(2026, 9, 12, 11, 0, 0, TimeSpan.Zero), plan.NewestAt);

        EnvelopePurge.Execute(plan);

        Assert.False(File.Exists(EnvelopeFile));
        Assert.True(File.Exists(SessionPaths.SessionFile(_workspace, _config.SessionId)));
        Assert.True(File.Exists(SessionPaths.EventsFile(_workspace, _config.SessionId)));
        Assert.True(File.Exists(Path.Combine(SessionDir, "layout-host-a.json")));
        Assert.True(Directory.Exists(SessionDir));
    }

    [Fact]
    public void PurgeOfASessionWithNoHistoryResolvesToZeroEnvelopesAndNoNewestAt()
    {
        var plan = EnvelopePurge.Resolve(_workspace, _config.SessionId);
        Assert.Equal(0, plan.EnvelopeCount);
        Assert.Null(plan.NewestAt);
        Assert.False(plan.HasHistory);
        EnvelopePurge.Execute(plan);   // nothing to remove is not an error
        Assert.True(File.Exists(SessionPaths.SessionFile(_workspace, _config.SessionId)));
    }

    [Theory]
    [InlineData("..\\..")]
    [InlineData("../..")]
    [InlineData("not-a-session-id")]
    [InlineData("20260912T100000Z-0000aaaa/../20260912T100000Z-0000bbbb")]
    [InlineData("")]
    public void PurgeOfATraversalOrANonSegmentIdIsRefusedBeforeAnyFileIsTouched(string id)
    {
        WriteTwoEnvelopes();
        var before = Directory.EnumerateFileSystemEntries(_workspace, "*", SearchOption.AllDirectories).Order(StringComparer.Ordinal).ToList();

        var refused = Assert.Throws<EnvelopeStoreException>(() => EnvelopePurge.Resolve(_workspace, id));
        Assert.Equal(EnvelopeStoreErrorCodes.PurgeRefused, refused.Code);

        Assert.Equal(before, Directory.EnumerateFileSystemEntries(_workspace, "*", SearchOption.AllDirectories).Order(StringComparer.Ordinal));
    }

    /// <summary>A junctioned session directory is refused — junctions and symlinks are not followed (a junction fixture).</summary>
    [Fact]
    public void PurgeOfAJunctionedSessionDirectoryIsRefusedBeforeAnyFileIsTouched()
    {
        var elsewhere = Path.Combine(_workspace, "elsewhere");
        Directory.CreateDirectory(elsewhere);
        File.WriteAllText(Path.Combine(elsewhere, EnvelopeStore.FileName), "{}\n");
        var junctionId = SessionId.New(new DateTimeOffset(2026, 9, 12, 12, 0, 0, TimeSpan.Zero));
        var junction = SessionPaths.SessionDirectory(_workspace, junctionId);
        Directory.CreateDirectory(SessionPaths.SessionsRoot(_workspace));

        CreateJunction(junction, elsewhere);
        Assert.True(new DirectoryInfo(junction).Attributes.HasFlag(FileAttributes.ReparsePoint), "the fixture is a reparse point");

        var refused = Assert.Throws<EnvelopeStoreException>(() => EnvelopePurge.Resolve(_workspace, junctionId));
        Assert.Equal(EnvelopeStoreErrorCodes.PurgeRefused, refused.Code);
        Assert.Contains("junction", refused.Message, StringComparison.OrdinalIgnoreCase);
        Assert.True(File.Exists(Path.Combine(elsewhere, EnvelopeStore.FileName)));
    }

    [Fact]
    public void PurgeWhileAWriterHoldsTheFileIsRefusedVisibly()
    {
        using var writer = EnvelopeStore.Open(SessionDir);
        var refused = Assert.Throws<EnvelopeStoreException>(() => EnvelopePurge.Resolve(_workspace, _config.SessionId));
        Assert.Equal(EnvelopeStoreErrorCodes.HeldByAnotherWriter, refused.Code);
        Assert.True(File.Exists(EnvelopeFile));
    }

    // ── the Session aggregate's own delete: containment ──

    [Fact]
    public void TheSessionDeleteRemovesTheDirectoryIncludingTheEnvelopeFileAndNothingOutsideIt()
    {
        WriteTwoEnvelopes();
        var sibling = new SessionConfigStore(_workspace, SessionId.New(new DateTimeOffset(2026, 9, 12, 13, 0, 0, TimeSpan.Zero)));
        var other = sibling.Create("other", "w-1", [new AccountRef("anthropic", "max")], new AccountRef("anthropic", "max"), DateTimeOffset.UnixEpoch);
        var outside = Path.Combine(_workspace, "README.md");
        File.WriteAllText(outside, "unchanged");
        var otherFile = SessionPaths.SessionFile(_workspace, other.SessionId);
        var otherBytes = File.ReadAllBytes(otherFile);

        _sessions.Delete();

        Assert.False(File.Exists(EnvelopeFile));
        Assert.False(Directory.Exists(SessionDir));
        Assert.Equal("unchanged", File.ReadAllText(outside));
        Assert.Equal(otherBytes, File.ReadAllBytes(otherFile));
    }

    [Fact]
    public void TheSessionDeleteWhileAWriterHoldsTheEnvelopeFileIsRefusedWholeAndNothingIsRemoved()
    {
        WriteTwoEnvelopes();
        using var writer = EnvelopeStore.Open(SessionDir);

        var refused = Assert.Throws<EnvelopeStoreException>(() => _sessions.Delete());
        Assert.Equal(EnvelopeStoreErrorCodes.HeldByAnotherWriter, refused.Code);

        Assert.True(File.Exists(EnvelopeFile));
        Assert.True(File.Exists(SessionPaths.SessionFile(_workspace, _config.SessionId)));
        Assert.True(File.Exists(SessionPaths.EventsFile(_workspace, _config.SessionId)));
    }

    /// <summary>
    /// The delete's ordering, as the D&amp;P lens re-shaped it: acquire the envelope file (refuse if
    /// held) → move the whole directory to a tombstone (a directory move fails while ANY file inside
    /// is open, so the window between the handle's release and the recursive delete is closed) →
    /// delete the tombstone. A sibling held open therefore refuses the delete WHOLE — nothing is
    /// removed, nothing is orphaned — rather than leaving session.json gone and the envelope file behind.
    /// </summary>
    [Fact]
    [Trait("Platform", "Windows")]   // Ruling 117: the refusal rests on a Windows directory-move refusing while a file inside is open; Linux unlinks under the open reader (INV-0012 4.2, residual per Ruling 118)
    public void ASiblingHeldOpenRefusesTheDeleteWholeAndNothingIsOrphaned()
    {
        WriteTwoEnvelopes();
        using var held = new FileStream(SessionPaths.EventsFile(_workspace, _config.SessionId), FileMode.Open, FileAccess.Read, FileShare.None);

        var refused = Assert.Throws<EnvelopeStoreException>(() => _sessions.Delete());
        Assert.Equal(EnvelopeStoreErrorCodes.HeldByAnotherWriter, refused.Code);

        Assert.True(File.Exists(EnvelopeFile));
        Assert.True(File.Exists(SessionPaths.SessionFile(_workspace, _config.SessionId)));
        Assert.True(File.Exists(SessionPaths.EventsFile(_workspace, _config.SessionId)));
        Assert.True(Directory.Exists(SessionDir));
        Assert.Empty(Directory.EnumerateDirectories(SessionPaths.SessionsRoot(_workspace), "*.deleting-*"));
    }

    /// <summary>A writer that opens in the window after the acquire cannot orphan anything: the session path is gone (moved), so its open refuses NoSessionDirectory.</summary>
    [Fact]
    public void AfterTheDeleteAWriterAtTheSessionPathIsRefusedNotCreated()
    {
        WriteTwoEnvelopes();
        _sessions.Delete();
        var refused = Assert.Throws<EnvelopeStoreException>(() => EnvelopeStore.Open(SessionDir));
        Assert.Equal(EnvelopeStoreErrorCodes.NoSessionDirectory, refused.Code);
        Assert.False(Directory.Exists(SessionDir));
    }

    /// <summary>
    /// A symbolic link where the envelope file should be is refused before any touch — the target is
    /// not this session's history. A FILE symbolic link has no junction fallback, so on a host
    /// without the privilege the test is <b>skipped with the reason</b> (visible in the count as
    /// skipped, never a vacuous pass) — <see cref="SymbolicLinkFactAttribute"/>.
    /// </summary>
    [SymbolicLinkFact]
    public void PurgeOfASymlinkedEnvelopeFileIsRefusedBeforeAnyFileIsTouched()
    {
        var target = Path.Combine(_workspace, "elsewhere.jsonl");
        File.WriteAllText(target, "{}" + Environment.NewLine);
        File.CreateSymbolicLink(EnvelopeFile, target);
        Assert.True(new FileInfo(EnvelopeFile).Attributes.HasFlag(FileAttributes.ReparsePoint));

        var refused = Assert.Throws<EnvelopeStoreException>(() => EnvelopePurge.Resolve(_workspace, _config.SessionId));
        Assert.Equal(EnvelopeStoreErrorCodes.PurgeRefused, refused.Code);
        Assert.Contains("symbolic link", refused.Message, StringComparison.OrdinalIgnoreCase);
        Assert.True(File.Exists(target));
        Assert.Equal("{}" + Environment.NewLine, File.ReadAllText(target));
    }

    /// <summary>Execute re-validates the path it deletes: a plan pointing outside the session's envelope file is refused, whatever its other fields say.</summary>
    [Fact]
    public void ExecuteRefusesAPlanWhosePathIsNotTheSessionsEnvelopeFile()
    {
        var outside = Path.Combine(_workspace, "README.md");
        File.WriteAllText(outside, "keep");
        var forged = new PurgePlan("payments", _config.SessionId, Path.GetFullPath(_workspace), Path.GetFullPath(outside), 1, 0, null);

        var refused = Assert.Throws<EnvelopeStoreException>(() => EnvelopePurge.Execute(forged));
        Assert.Equal(EnvelopeStoreErrorCodes.PurgeRefused, refused.Code);
        Assert.Equal("keep", File.ReadAllText(outside));
    }

    /// <summary>A directory junction (no privilege needed on Windows) or a symlink elsewhere — the fixture the refusal is proven against.</summary>
    private static void CreateJunction(string link, string target)
    {
        if (!OperatingSystem.IsWindows())
        {
            Directory.CreateSymbolicLink(link, target);
            return;
        }

        var mklink = System.Diagnostics.Process.Start(new System.Diagnostics.ProcessStartInfo("cmd.exe", $"/c mklink /J \"{link}\" \"{target}\"")
        {
            UseShellExecute = false,
            CreateNoWindow = true,
            RedirectStandardOutput = true,
            RedirectStandardError = true,
        })!;
        mklink.WaitForExit();
        Assert.True(mklink.ExitCode == 0, "mklink /J failed: " + mklink.StandardError.ReadToEnd());
    }

    /// <summary>A fact that runs only where the host can create a file symbolic link; elsewhere it is skipped with the reason.</summary>
    private sealed class SymbolicLinkFactAttribute : FactAttribute
    {
        private static readonly Lazy<string?> Reason = new(Probe);

        public SymbolicLinkFactAttribute()
        {
            if (Reason.Value is { } reason)
            {
                Skip = reason;
            }
        }

        private static string? Probe()
        {
            var dir = Path.Combine(Path.GetTempPath(), "aide-symlink-probe-" + Guid.NewGuid().ToString("n")[..8]);
            Directory.CreateDirectory(dir);
            try
            {
                var target = Path.Combine(dir, "target");
                File.WriteAllText(target, "x");
                File.CreateSymbolicLink(Path.Combine(dir, "link"), target);
                return null;
            }
            catch (Exception error) when (error is IOException or UnauthorizedAccessException)
            {
                return $"this host cannot create a file symbolic link ({error.GetType().Name}: enable Developer Mode or run elevated); the refusal is covered by the directory-junction fixture";
            }
            finally
            {
                try { Directory.Delete(dir, recursive: true); } catch (IOException) { }
            }
        }
    }

    private sealed class FixedTime(DateTimeOffset now) : TimeProvider
    {
        public override DateTimeOffset GetUtcNow() => now;
    }
}
