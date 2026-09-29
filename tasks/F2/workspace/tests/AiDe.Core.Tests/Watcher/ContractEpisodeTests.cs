using AiDe.Core.Watcher;

namespace AiDe.Core.Tests.Watcher;

/// <summary>
/// The <c>episode-open</c> / <c>episode-close</c> event kinds: a live Work Episode declared by the
/// agent over the coordination log.
/// </summary>
/// <remarks>
/// <para><b>The gap they close.</b> Before them <c>AuditLogEpisodeSource</c> was the only producer of
/// episodes, so an episode existed only where the AI-Forward pack had written an audit entry. A
/// GitHub Copilot session or a plain shell produced none, and the leaderboard could not compare what
/// it was built to compare.</para>
///
/// <para><b>Why the agent declares and the shell cannot.</b> An episode needs a goal. The workbench
/// knows a terminal exists; it does not know what the agent inside it is trying to do. Opening one
/// per terminal with a placeholder would fabricate a goal (NG1), and the scorer already handles a
/// missing goal honestly — Not Scored with the reason, never a low mark.</para>
/// </remarks>
public sealed class ContractEpisodeTests
{
    private const double At = 1_700_000_000d;

    private static Dictionary<string, string?> RegisterAttrs() => new(StringComparer.Ordinal)
    {
        [OtelAttributes.RepoPath] = "C:/repos/app",
        [OtelAttributes.RepoDisplay] = "app",
        [OtelAttributes.WorktreeBranch] = "main",
        [OtelAttributes.WorktreePath] = "C:/repos/app",
        [OtelAttributes.TerminalId] = "term-1",
        [OtelAttributes.AgentName] = "copilot",
    };

    private static Dictionary<string, string?> OpenAttrs(
        string? goal = "Wire live episode capture", string? doneWhen = "an episode exists for a non-pack session",
        string? notInScope = null)
    {
        var attrs = new Dictionary<string, string?>(StringComparer.Ordinal);
        if (goal is not null)
        {
            attrs[CoordContract.EpisodeAttributes.Goal] = goal;
        }

        if (doneWhen is not null)
        {
            attrs[CoordContract.EpisodeAttributes.DoneWhen] = doneWhen;
        }

        if (notInScope is not null)
        {
            attrs[CoordContract.EpisodeAttributes.NotInScope] = notInScope;
        }

        return attrs;
    }

    private static Dictionary<string, string?> CloseAttrs(string? outcome) =>
        outcome is null
            ? new Dictionary<string, string?>(StringComparer.Ordinal)
            : new Dictionary<string, string?>(StringComparer.Ordinal)
            {
                [CoordContract.EpisodeAttributes.Outcome] = outcome,
            };

    private static (InjectedContractIngest adapter, InMemoryWatcherObservationStore store) NewAdapter()
    {
        var store = new InMemoryWatcherObservationStore();
        var clock = new FakeMonotonicClock();
        var n = 0;
        var registrar = new TrustedRegistrar(store, new SequentialCapabilityFactory(), clock, () => $"session-{++n}");
        var host = new IngestHost(store, registrar, new FixedTimeProvider(DateTimeOffset.UnixEpoch.AddSeconds(At)));
        return (new InjectedContractIngest(host), store);
    }

    private static InjectedContractIngest Registered(out InMemoryWatcherObservationStore store)
    {
        var (adapter, s) = NewAdapter();
        adapter.Apply(new ContractRegister("ext-1", RegisterAttrs(), At, 1));
        store = s;
        return adapter;
    }

    [Fact]
    public void AnEpisodeOpen_CreatesAnActiveEpisodeForARegisteredSession()
    {
        var adapter = Registered(out var store);

        adapter.Apply(new ContractEpisodeOpen("ext-1", OpenAttrs(notInScope: "the Daydream surface"), At + 1, 2));

        var episode = Assert.Single(store.EpisodesForSession("session-1"));
        Assert.Equal("Wire live episode capture", episode.Goal.Statement);
        Assert.Equal("an episode exists for a non-pack session", episode.DoneWhen.Statement);
        Assert.Equal("the Daydream surface", episode.NotInScope);
        Assert.Equal(EpisodeState.Active, episode.State);
        Assert.Equal(1, adapter.Stats.EpisodesOpened);
    }

    /// <summary>
    /// An episode never creates a session.
    /// </summary>
    /// <remarks>
    /// Registration is where trust is decided: a registration carrying a harness is
    /// <c>Verified</c>, one without is <c>Asserted</c>, and trust never rises afterwards. An
    /// episode-open that auto-registered would mint a session — and its trust — from an append-only
    /// file anything can write to. That is a trust-<i>creating</i> side door, which is worse than a
    /// trust-raising one.
    /// </remarks>
    [Fact]
    public void AnEpisodeOpen_ForAnUnregisteredSession_IsDroppedAndCounted()
    {
        var (adapter, store) = NewAdapter();

        adapter.Apply(new ContractEpisodeOpen("never-registered", OpenAttrs(), At, 1));

        Assert.Empty(store.AllEpisodes());
        Assert.Null(store.FindSession("session-1"));
        Assert.Equal(0, adapter.Stats.EpisodesOpened);
        Assert.Equal(1, adapter.Stats.Unknown);
    }

    /// <summary>
    /// A goal is never defaulted.
    /// </summary>
    /// <remarks>
    /// An episode opened with an empty goal would score <c>Not Scored</c> and read as "the agent
    /// declared nothing", when in fact the declaration was invented here — making one verdict mean
    /// two different things at the one surface whose job is telling them apart.
    /// </remarks>
    [Theory]
    [InlineData(null, "a done condition")]   // no goal
    [InlineData("a goal", null)]             // no done condition
    [InlineData("   ", "a done condition")]  // blank is not a declaration
    public void AnEpisodeOpen_WithoutBothHalvesOfTheDeclaration_IsQuarantined(string? goal, string? doneWhen)
    {
        var adapter = Registered(out var store);

        adapter.Apply(new ContractEpisodeOpen("ext-1", OpenAttrs(goal, doneWhen), At + 1, 2));

        Assert.Empty(store.AllEpisodes());
        Assert.Equal(0, adapter.Stats.EpisodesOpened);
        Assert.Equal(1, adapter.Stats.Quarantined);
    }

    /// <summary>
    /// A second open supersedes the first. It must not fork the session into two live episodes.
    /// </summary>
    /// <remarks>
    /// <para><b>This test exists because the obvious implementation is wrong.</b> Calling
    /// <c>Open</c> a second time does not close anything: it records a new episode with the next
    /// generation and returns, leaving two rows with <c>ClosedAt is null</c>, both reporting
    /// <c>Active</c>. Nothing errors, generations keep climbing, and a reader picks one of the two
    /// without knowing the other exists. The adapter therefore routes a second open through
    /// <c>Reframe</c>, which is where "changing the goal starts a new episode" is already
    /// defined (spec line 211) — the rule is not re-decided here.</para>
    ///
    /// <para>Found by a second party reading the service rather than the caller.</para>
    /// </remarks>
    [Fact]
    public void ASecondOpen_SupersedesTheFirst_ItDoesNotForkIntoTwoActiveEpisodes()
    {
        var adapter = Registered(out var store);

        adapter.Apply(new ContractEpisodeOpen("ext-1", OpenAttrs("first goal", "first done"), At + 1, 2));
        adapter.Apply(new ContractEpisodeOpen("ext-1", OpenAttrs("second goal", "second done"), At + 2, 3));

        var episodes = store.EpisodesForSession("session-1");
        Assert.Equal(2, episodes.Count);

        var active = episodes.Where(e => e.State == EpisodeState.Active).ToList();
        Assert.Single(active);
        Assert.Equal("second goal", active[0].Goal.Statement);

        var displaced = Assert.Single(episodes, e => e.State == EpisodeState.Closed);
        Assert.Equal(EpisodeOutcome.Superseded, displaced.Outcome);
        Assert.Equal("first goal", displaced.Goal.Statement);
    }

    [Fact]
    public void AnEpisodeClose_RecordsTheDeclaredOutcome()
    {
        var adapter = Registered(out var store);
        adapter.Apply(new ContractEpisodeOpen("ext-1", OpenAttrs(), At + 1, 2));

        adapter.Apply(new ContractEpisodeClose("ext-1", CloseAttrs("Abandoned"), At + 2, 3));

        var episode = Assert.Single(store.EpisodesForSession("session-1"));
        Assert.Equal(EpisodeState.Closed, episode.State);
        Assert.Equal(EpisodeOutcome.Abandoned, episode.Outcome);
        Assert.Equal(1, adapter.Stats.EpisodesClosed);
    }

    /// <summary>
    /// An outcome is never defaulted to <c>Completed</c>.
    /// </summary>
    /// <remarks>
    /// Outcome-integrity reads this field: a fabricated <c>Completed</c> would be scored as a met
    /// outcome for an episode whose author said nothing of the kind.
    /// </remarks>
    [Theory]
    [InlineData(null)]
    [InlineData("finished")]
    [InlineData("")]
    public void AnEpisodeClose_WithoutAParseableOutcome_IsQuarantined(string? declared)
    {
        var adapter = Registered(out var store);
        adapter.Apply(new ContractEpisodeOpen("ext-1", OpenAttrs(), At + 1, 2));

        adapter.Apply(new ContractEpisodeClose("ext-1", CloseAttrs(declared), At + 2, 3));

        var episode = Assert.Single(store.EpisodesForSession("session-1"));
        Assert.Equal(EpisodeState.Active, episode.State);
        Assert.Null(episode.Outcome);
        Assert.Equal(0, adapter.Stats.EpisodesClosed);
        Assert.Equal(1, adapter.Stats.Quarantined);
    }

    [Fact]
    public void AnEpisodeClose_WithNoOpenEpisode_IsDroppedAndCounted()
    {
        var adapter = Registered(out var store);

        adapter.Apply(new ContractEpisodeClose("ext-1", CloseAttrs("Completed"), At + 1, 2));

        Assert.Empty(store.AllEpisodes());
        Assert.Equal(0, adapter.Stats.EpisodesClosed);
        Assert.Equal(1, adapter.Stats.Unknown);
    }

    /// <summary>
    /// A session ending leaves an open episode open.
    /// </summary>
    /// <remarks>
    /// <para><b>The line is observed versus inferred, not who writes it.</b> The system does write
    /// outcomes without the agent saying so — <c>Reframe</c> writes <c>Superseded</c> — and that is
    /// allowed because a new goal arriving is a <i>fact about the log</i>. <c>Abandoned</c> at
    /// session-end would be inferred: it asserts the agent gave up, when all that was observed is a
    /// session ending with an episode open, which is equally consistent with a crash, a closed
    /// terminal, or a harness that never emits <c>episode-close</c> at all.</para>
    ///
    /// <para><c>EpisodeOutcome</c> has no "unknown" member, and the scorer's Not-Scored gate
    /// already reports an episode that never closed with the reason
    /// (<c>WeaveScore.cs</c> — "the episode is not closed"). A fabricated <c>Abandoned</c> would
    /// replace that abstention with a scored judgement.</para>
    /// </remarks>
    [Fact]
    public void ASessionEnd_LeavesAnOpenEpisodeOpen_ItDoesNotInventAnOutcome()
    {
        var adapter = Registered(out var store);
        adapter.Apply(new ContractEpisodeOpen("ext-1", OpenAttrs(), At + 1, 2));

        adapter.Apply(new ContractSessionEnd("ext-1", At + 2, 3));

        var episode = Assert.Single(store.EpisodesForSession("session-1"));
        Assert.Equal(EpisodeState.Active, episode.State);
        Assert.Null(episode.Outcome);
    }

    [Fact]
    public void TheParserReadsEpisodeLines_WithoutABumpedVersion()
    {
        var open = "{\"kind\":\"episode-open\",\"contract\":\"" + CoordContract.Version
            + "\",\"session\":\"ext-1\",\"at\":1,\"seq\":2,"
            + "\"attrs\":{\"episode.goal\":\"g\",\"episode.done_when\":\"d\"}}";
        var close = "{\"kind\":\"episode-close\",\"contract\":\"" + CoordContract.Version
            + "\",\"session\":\"ext-1\",\"at\":2,\"seq\":3,"
            + "\"attrs\":{\"episode.outcome\":\"Completed\"}}";

        var events = CoordContractParser.Parse(open + "\n" + close);

        Assert.Equal(2, events.Count);
        var opened = Assert.IsType<ContractEpisodeOpen>(events[0]);
        Assert.Equal("g", opened.Attributes[CoordContract.EpisodeAttributes.Goal]);
        var closed = Assert.IsType<ContractEpisodeClose>(events[1]);
        Assert.Equal("Completed", closed.Attributes[CoordContract.EpisodeAttributes.Outcome]);
    }

    /// <summary>
    /// An older reader ignores an episode line rather than rejecting the whole log.
    /// </summary>
    /// <remarks>
    /// This is what makes the kind additive within <c>loomkeeper/1</c> rather than a version bump:
    /// the parser already returns null for a kind it does not handle. Asserted here so that
    /// removing that tolerance fails a test instead of silently making the contract breaking.
    /// </remarks>
    /// <remarks>
    /// <para><b>The example moved once already.</b> This was written with <c>board-post</c> as the
    /// unhandled kind, and <c>board-post</c> was then implemented — so the test failed, correctly,
    /// the moment its example stopped being an example. The fix is a different future kind, not a
    /// weaker assertion: <c>daydream-observation</c> is specified (US-9) and unbuilt, so it is
    /// genuinely unhandled today.</para>
    ///
    /// <para>If it too becomes real, this test will fail again and should be re-pointed again. That
    /// is the test working: the tolerance it pins is what lets every one of these kinds be added
    /// without a version bump, and it can only be demonstrated with a kind that is actually absent.
    /// </para>
    /// </remarks>
    [Fact]
    public void AnUnhandledKindIsSkipped_NotTreatedAsMalformed()
    {
        var unknown = "{\"kind\":\"daydream-observation\",\"contract\":\"" + CoordContract.Version
            + "\",\"session\":\"ext-1\",\"at\":1,\"seq\":2}";

        var events = CoordContractParser.Parse(unknown, out var stats);

        Assert.Empty(events);
        Assert.Equal(0, stats.Malformed);
        Assert.Equal(0, stats.VersionRejected);
    }
}
