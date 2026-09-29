using AiDe.Core.Watcher;

namespace AiDe.Core.Tests.Watcher;

/// <summary>
/// A coordination log is written to a file the pump can find, whatever the session id contains.
/// </summary>
/// <remarks>
/// <para><b>The defect.</b> The writer used the session id verbatim as a file name. An agent pane's
/// id is <c>agent:claude#fb96e3</c>, and on Windows
/// <c>Path.Combine(dir, "agent:claude#fb96e3.jsonl")</c> is not a file with that name — NTFS reads
/// it as the file <c>agent</c> with the alternate data stream <c>claude#fb96e3.jsonl</c>.</para>
///
/// <para><b>Every part of it succeeded.</b> The directory was created, the write returned, the bytes
/// were on disk. <c>Directory.EnumerateFiles(dir, "*.jsonl")</c> cannot enumerate a stream, so the
/// pump found nothing and <b>no agent session was ever registered</b> — no liveness, no model
/// <c>update</c>, no <c>episode-open</c>. Not one of those paths reported a failure, because from
/// each one's point of view there was simply nothing to read.</para>
///
/// <para><b>Observed on the owner's machine:</b> a zero-byte file named <c>agent</c> carrying seven
/// streams and 41 KB of events, beside <c>terminal-1.jsonl</c> as a real 442 KB file. Plain
/// terminals worked throughout; only the ids containing a colon vanished, which is why it survived
/// every test — a fixture session id is a plain word.</para>
/// </remarks>
public sealed class CoordLogSurvivesASessionIdWithAColonTests : IDisposable
{
    private readonly string _dir = Path.Combine(
        Path.GetTempPath(), "aide-coord-" + Guid.NewGuid().ToString("n")[..8]);

    public void Dispose()
    {
        try { Directory.Delete(_dir, recursive: true); } catch (IOException) { /* best effort */ }
    }

    private CoordContractWriter Writer() =>
        new(_dir, new FixedTimeProvider(DateTimeOffset.UnixEpoch));

    private static Dictionary<string, string?> Attrs() => new(StringComparer.Ordinal)
    {
        [OtelAttributes.RepoPath] = "C:/repos/app",
        [OtelAttributes.RepoDisplay] = "app",
        [OtelAttributes.WorktreeBranch] = "main",
        [OtelAttributes.WorktreePath] = "C:/repos/app",
        [OtelAttributes.TerminalId] = "agent:claude#fb96e3",
        [OtelAttributes.AgentName] = "claude",
    };

    /// <summary>
    /// The exact id the workbench generates for an agent pane produces a file the pump enumerates.
    /// </summary>
    /// <remarks>
    /// Asserted through <c>EnumerateFiles(*.jsonl)</c> rather than by checking the file exists:
    /// enumeration is what the pump actually does, and it is the step a stream defeats. Reading the
    /// path back directly would have passed on the broken code.
    /// </remarks>
    [Fact]
    public void AnAgentSessionIdProducesAFileThePumpCanEnumerate()
    {
        Writer().WriteRegister("agent:claude#fb96e3", Attrs());

        var found = Directory.EnumerateFiles(_dir, "*.jsonl").ToList();

        Assert.Single(found);
        Assert.Contains("register", File.ReadAllText(found[0]));
    }

    /// <summary>Every event kind for one session lands in the one file, in order.</summary>
    [Fact]
    public void AllOfASessionsEventsLandInTheSameFile()
    {
        var writer = Writer();
        writer.WriteRegister("agent:copilot#1f12c8", Attrs());
        writer.WriteHeartbeat("agent:copilot#1f12c8");
        writer.WriteSessionEnd("agent:copilot#1f12c8");

        var file = Assert.Single(Directory.EnumerateFiles(_dir, "*.jsonl"));
        var lines = File.ReadAllLines(file).Where(l => l.Trim().Length > 0).ToList();

        Assert.Equal(3, lines.Count);
        Assert.Contains("\"kind\":\"register\"", lines[0]);
        Assert.Contains("\"kind\":\"heartbeat\"", lines[1]);
        Assert.Contains("\"kind\":\"session-end\"", lines[2]);
    }

    /// <summary>
    /// Two ids that differ only in an invalid character stay two sessions.
    /// </summary>
    /// <remarks>
    /// The obvious fix — replace invalid characters and stop — maps <c>agent:claude</c> and
    /// <c>agent-claude</c> onto one file. Their events would interleave in a single log and fold
    /// into one identity, which is a quieter defect than the one being fixed and harder to see. The
    /// name carries a digest of the original id so distinct sessions stay distinct.
    /// </remarks>
    [Fact]
    public void TwoIdsThatSanitiseAlikeDoNotShareAFile()
    {
        var writer = Writer();
        writer.WriteRegister("agent:claude", Attrs());
        writer.WriteRegister("agent-claude", Attrs());

        Assert.Equal(2, Directory.EnumerateFiles(_dir, "*.jsonl").Count());
    }

    /// <summary>The same id always resolves to the same file, so a session appends rather than forks.</summary>
    [Fact]
    public void TheSameIdAlwaysResolvesToTheSameFile()
    {
        Assert.Equal(
            CoordContractWriter.FileNameFor("agent:claude#fb96e3"),
            CoordContractWriter.FileNameFor("agent:claude#fb96e3"));

        Assert.NotEqual(
            CoordContractWriter.FileNameFor("agent:claude#fb96e3"),
            CoordContractWriter.FileNameFor("agent:claude#aa8dcb"));
    }

    /// <summary>
    /// An id the filesystem accepts is left exactly as it was.
    /// </summary>
    /// <remarks>
    /// The first version of the fix rewrote every name, which orphaned every log already on disk and
    /// changed the one case that was never broken. Two existing tests failed on it — the suite
    /// caught what the change had not thought about. Kept as an assertion so the narrowing is not
    /// undone by someone tidying the branch away.
    /// </remarks>
    [Fact]
    public void AnAlreadyValidIdIsNotRewritten()
    {
        Assert.Equal("terminal-1.jsonl", CoordContractWriter.FileNameFor("terminal-1"));
        Assert.Equal("s-terminal.jsonl", CoordContractWriter.FileNameFor("s-terminal"));
    }

    /// <summary>
    /// The written events round-trip through the parser, which is what the pump feeds.
    /// </summary>
    /// <remarks>
    /// A file the pump can find is only half of it; the contents still have to parse. Asserted
    /// end-to-end so a future change to the name cannot quietly corrupt what is inside it.
    /// </remarks>
    [Fact]
    public void WhatIsWrittenParsesBackAsTheEventsThatWereWritten()
    {
        var writer = Writer();
        writer.WriteRegister("agent:claude#fb96e3", Attrs());
        writer.WriteHeartbeat("agent:claude#fb96e3");

        var file = Assert.Single(Directory.EnumerateFiles(_dir, "*.jsonl"));
        var events = CoordContractParser.Parse(File.ReadAllText(file));

        Assert.Equal(2, events.Count);
        var register = Assert.IsType<ContractRegister>(events[0]);
        Assert.Equal("agent:claude#fb96e3", register.ExternalSessionId);
        Assert.IsType<ContractHeartbeat>(events[1]);
    }
}
