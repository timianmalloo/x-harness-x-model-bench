using AiDe.Core.Watcher;
using AiDe.Mcp;

namespace AiDe.Core.Tests.Watcher;

/// <summary>
/// THE EQUIVALENCE GATE: the same board post, made through MCP and by hand, must land identically.
/// </summary>
/// <remarks>
/// <para><b>This is the control that makes the owner's principle a property rather than a promise.</b>
/// MCP is the enlightened path and JSONL is the participation floor, which only means anything if
/// the two agree — and two paths can only be <i>guaranteed</i> to agree when one is a translation of
/// the other. This asserts the translation.</para>
///
/// <para>Without it, "MCP is a thin wrapper" is a claim about intent. The way it fails is not
/// dramatic: someone adds a convenience to the tool — a default kind, a trimmed string, an inferred
/// parent — and the paths diverge in exactly the direction nobody tests, because each path's own
/// tests still pass.</para>
///
/// <para>Compared through the INGEST rather than at the file, deliberately. Identical bytes on disk
/// would be a stronger claim than needed and a weaker one than wanted: what matters is that the
/// board ends up in the same state, which is what an agent and an operator both actually see.</para>
/// </remarks>
public sealed class McpMatchesTheJsonlPathTests : IDisposable
{
    private readonly string _root = Path.Combine(
        Path.GetTempPath(), "aide-mcp-equiv-" + Guid.NewGuid().ToString("n")[..8]);

    public McpMatchesTheJsonlPathTests() => Directory.CreateDirectory(_root);

    public void Dispose()
    {
        try { Directory.Delete(_root, recursive: true); } catch (IOException) { /* best effort */ }
    }

    private const double At = 1_700_000_000d;
    private const string Terminal = "agent:claude#equiv";

    private static Dictionary<string, string?> RegisterAttrs() => new(StringComparer.Ordinal)
    {
        [OtelAttributes.RepoPath] = "C:/repos/app",
        [OtelAttributes.RepoDisplay] = "app",
        [OtelAttributes.WorktreeBranch] = "main",
        [OtelAttributes.WorktreePath] = "C:/repos/app",
        [OtelAttributes.TerminalId] = Terminal,
        [OtelAttributes.AgentName] = "claude-code",
    };

    /// <summary>Runs one coordination log through the ingest and returns the resulting board.</summary>
    private static IReadOnlyList<BoardMessage> Ingest(string logDir) => Pump(logDir).AllBoardMessages();

    /// <summary>Runs one coordination log through the ingest and returns the store it produced.</summary>
    private static InMemoryWatcherObservationStore Pump(string logDir)
    {
        var store = new InMemoryWatcherObservationStore();
        var registrar = new TrustedRegistrar(
            store, new SequentialCapabilityFactory(), new FakeMonotonicClock(), () => "session-1");
        var host = new IngestHost(store, registrar, new FixedTimeProvider(DateTimeOffset.UnixEpoch.AddSeconds(At)));
        new CoordContractLogPump(logDir, new InjectedContractIngest(host)).PumpOnce();
        return store;
    }

    private static SessionRecord SessionFor(string logDir)
    {
        var store = new InMemoryWatcherObservationStore();
        var registrar = new TrustedRegistrar(
            store, new SequentialCapabilityFactory(), new FakeMonotonicClock(), () => "session-1");
        var host = new IngestHost(store, registrar, new FixedTimeProvider(DateTimeOffset.UnixEpoch.AddSeconds(At)));
        new CoordContractLogPump(logDir, new InjectedContractIngest(host)).PumpOnce();
        return store.AllSessions().Single();
    }

    private string NewLog(string name)
    {
        var dir = Path.Combine(_root, name);
        Directory.CreateDirectory(dir);
        var writer = new CoordContractWriter(dir, new FixedTimeProvider(DateTimeOffset.UnixEpoch.AddSeconds(At)));
        writer.WriteRegister(Terminal, RegisterAttrs());
        return dir;
    }

    // ------------------------------------------------------------------ the gate

    /// <summary>
    /// A post via the MCP tool and a post written by hand produce the same board message.
    /// </summary>
    /// <remarks>
    /// Everything but the identity and the clock: the message id is minted per ingest and the
    /// timestamp is the moment of ingest, so comparing those would be comparing the test harness to
    /// itself. Kind, author, trust, parent, content and the flags are the message.
    /// </remarks>
    [Theory]
    [InlineData("question", "why does the pump re-read the whole log?", null)]
    [InlineData("decision", "we key the segment on the repository, not the checkout", null)]
    [InlineData("breadcrumb", "the daemon path is BaseDirectory/daemon, not the publish root", null)]
    [InlineData("knowledge-candidate", "a fixture whose two paths are equal cannot fail", null)]
    public void APostViaTheToolAndAPostByHandAreTheSameMessage(string kind, string content, string? parent)
    {
        var viaTool = NewLog("tool");
        var byHand = NewLog("hand");

        // The enlightened path.
        BoardTools.Post(
            new CoordContractWriter(viaTool, new FixedTimeProvider(DateTimeOffset.UnixEpoch.AddSeconds(At))),
            SessionFor(viaTool), Terminal, kind, content, parent);

        // The participation floor: the line an agent writes with no tooling at all.
        //
        // Composed with a serializer rather than a hand-spelled string. The wire format is full of
        // braces, which fights raw-string interpolation — but the real reason is that a test proving
        // two spellings agree must not introduce a third one by hand.
        var handLine = System.Text.Json.JsonSerializer.Serialize(new Dictionary<string, object?>
        {
            ["kind"] = "board-post",
            ["contract"] = CoordContract.Version,
            ["session"] = Terminal,
            ["at"] = At + 1,
            ["seq"] = 2,
            ["attrs"] = new Dictionary<string, string?>
            {
                ["board.kind"] = kind,
                ["board.content"] = content,
            },
        });

        File.AppendAllText(
            Path.Combine(byHand, Path.GetFileName(Directory.GetFiles(byHand, "*.jsonl").Single())),
            handLine + "\n");

        var fromTool = Assert.Single(Ingest(viaTool));
        var fromHand = Assert.Single(Ingest(byHand));

        Assert.Equal(fromHand.Kind, fromTool.Kind);
        Assert.Equal(fromHand.Content, fromTool.Content);
        Assert.Equal(fromHand.AuthorSessionId, fromTool.AuthorSessionId);
        Assert.Equal(fromHand.AuthorTrust, fromTool.AuthorTrust);
        Assert.Equal(fromHand.ParentMessageId, fromTool.ParentMessageId);
        Assert.Equal(fromHand.Quarantined, fromTool.Quarantined);
        Assert.Equal(fromHand.InjectionFlagged, fromTool.InjectionFlagged);
        Assert.Equal(fromHand.RepositoryKey, fromTool.RepositoryKey);
    }

    /// <summary>
    /// The tool cannot post anything the hand-written path could not.
    /// </summary>
    /// <remarks>
    /// The direction that matters for the floor's meaning. If the tool could express something the
    /// contract cannot, an agent without MCP would be excluded from it — which is precisely what
    /// "participation, not parity" forbids, pointed the other way.
    /// </remarks>
    [Fact]
    public void TheToolExpressesNothingTheContractCannot()
    {
        var log = NewLog("expressive");
        BoardTools.Post(
            new CoordContractWriter(log, new FixedTimeProvider(DateTimeOffset.UnixEpoch.AddSeconds(At))),
            SessionFor(log), Terminal, "question", "anything at all");

        var written = File.ReadAllLines(Directory.GetFiles(log, "*.jsonl").Single())
            .Last(l => l.Contains("board-post"));

        // Only the keys the contract declares. A key the parser does not read is a key an agent
        // writing by hand would never know to send.
        Assert.Contains("\"board.kind\"", written);
        Assert.Contains("\"board.content\"", written);
        Assert.Contains($"\"contract\":\"{CoordContract.Version}\"", written);
    }

    // ------------------------------------------------------- the refusals are reported, not enforced

    /// <summary>
    /// The tool reports the ingest's refusals rather than applying its own.
    /// </summary>
    /// <remarks>
    /// It says what will happen and lets the ingest decide, so the two paths cannot disagree about
    /// what is acceptable. A tool that refused something the ingest would have accepted is a
    /// divergence the equivalence gate above could not see, because the message would never reach
    /// the board to be compared.
    /// </remarks>
    [Theory]
    [InlineData("not-a-kind", "x", null, "not a board kind")]
    [InlineData("question", "", null, "no content")]
    [InlineData("reply", "x", null, "parent_message_id")]
    public void ARefusalIsExplainedAtCallTime(string kind, string content, string? parent, string expected)
    {
        var log = NewLog("refusal");

        var answer = BoardTools.Post(
            new CoordContractWriter(log, new FixedTimeProvider(DateTimeOffset.UnixEpoch.AddSeconds(At))),
            SessionFor(log), Terminal, kind, content, parent);

        Assert.Contains(expected, answer);
        Assert.Empty(Ingest(log));
    }

    /// <summary>
    /// A successful post says "accepted", never "posted".
    /// </summary>
    /// <remarks>
    /// The line is on disk; the row appears when AI-DE's pump next runs. "Posted" would be true of
    /// the file and false of the board, and the gap between them is exactly where an agent would
    /// stop looking for its own message.
    /// </remarks>
    [Fact]
    public void AnAcceptedPostDoesNotClaimToBeOnTheBoardYet()
    {
        var log = NewLog("accepted");

        var answer = BoardTools.Post(
            new CoordContractWriter(log, new FixedTimeProvider(DateTimeOffset.UnixEpoch.AddSeconds(At))),
            SessionFor(log), Terminal, "breadcrumb", "the pump reads the whole log every tick");

        Assert.Contains("Accepted", answer);
        Assert.DoesNotContain("Posted", answer, StringComparison.OrdinalIgnoreCase);
    }

    // ------------------------------------------------------------- the gate, for episodes

    /// <summary>
    /// An episode opened and closed through MCP is the same episode opened and closed by hand.
    /// </summary>
    /// <remarks>
    /// <para>The same control as the board's, applied to the surface where divergence would cost
    /// more. A board message is read by a person who can tell something looks wrong; an episode is
    /// read by the SCORER, so a tool that quietly normalised an outcome or trimmed an artifact path
    /// would move a score with nothing to notice it.</para>
    ///
    /// <para>Both halves are asserted in one test because an episode is not observable until it is
    /// closed — opening alone leaves nothing with an outcome to compare.</para>
    /// </remarks>
    [Fact]
    public void AnEpisodeViaTheToolsAndAnEpisodeByHandAreTheSameEpisode()
    {
        var viaTool = NewLog("episode-tool");
        var byHand = NewLog("episode-hand");

        const string Goal = "make the board reachable from an agent that never reads a file";
        const string DoneWhen = "aide_board_post lands a row the operator can see";
        const string NotInScope = "the leaderboard";
        const string Artifact = "docs/design/mcp-enlightened-path.md";

        // The enlightened path.
        var writer = new CoordContractWriter(viaTool, new FixedTimeProvider(DateTimeOffset.UnixEpoch.AddSeconds(At)));
        EpisodeTools.Open(writer, Terminal, Goal, DoneWhen, NotInScope);
        EpisodeTools.Close(writer, Terminal, "completed", [Artifact]);

        // The participation floor. Serialized rather than hand-spelled, for the reason above: a test
        // proving two spellings agree must not introduce a third.
        var handFile = Directory.GetFiles(byHand, "*.jsonl").Single();
        File.AppendAllText(handFile, Line(2, "episode-open", new Dictionary<string, string?>
        {
            ["episode.goal"] = Goal,
            ["episode.done_when"] = DoneWhen,
            ["episode.not_in_scope"] = NotInScope,
        }) + "\n");
        File.AppendAllText(handFile, Line(3, "episode-close", new Dictionary<string, string?>
        {
            ["episode.outcome"] = "completed",
            ["episode.artifacts"] = Artifact,
        }) + "\n");

        var toolStore = Pump(viaTool);
        var handStore = Pump(byHand);

        var fromTool = Assert.Single(toolStore.AllEpisodes());
        var fromHand = Assert.Single(handStore.AllEpisodes());

        Assert.Equal(fromHand.Goal.Statement, fromTool.Goal.Statement);
        Assert.Equal(fromHand.DoneWhen.Statement, fromTool.DoneWhen.Statement);
        Assert.Equal(fromHand.NotInScope, fromTool.NotInScope);
        Assert.Equal(fromHand.Outcome, fromTool.Outcome);
        Assert.Equal(fromHand.Generation.Value, fromTool.Generation.Value);

        Assert.Equal(
            handStore.DeclaredArtifactsFor(fromHand.EpisodeId).Select(a => a.Path),
            toolStore.DeclaredArtifactsFor(fromTool.EpisodeId).Select(a => a.Path));
    }

    /// <summary>
    /// The episode tools express nothing the contract cannot.
    /// </summary>
    /// <remarks>
    /// "Participation, not parity" pointed the other way: a key only the tool knows how to send is a
    /// capability an agent on the floor is excluded from.
    /// </remarks>
    [Fact]
    public void TheEpisodeToolsExpressNothingTheContractCannot()
    {
        var log = NewLog("episode-expressive");
        var writer = new CoordContractWriter(log, new FixedTimeProvider(DateTimeOffset.UnixEpoch.AddSeconds(At)));
        EpisodeTools.Open(writer, Terminal, "g", "d", "n");
        EpisodeTools.Close(writer, Terminal, "blocked", ["a/b.md", "c/d.md"]);

        var lines = File.ReadAllLines(Directory.GetFiles(log, "*.jsonl").Single());
        var open = lines.Last(l => l.Contains("episode-open"));
        var close = lines.Last(l => l.Contains("episode-close"));

        Assert.Contains("\"episode.goal\"", open);
        Assert.Contains("\"episode.done_when\"", open);
        Assert.Contains("\"episode.not_in_scope\"", open);
        Assert.Contains("\"episode.outcome\"", close);
        // Newline-separated, because that is the only separator a real path cannot contain.
        Assert.Contains(@"a/b.md\nc/d.md", close);
    }

    /// <summary>
    /// The episode tools report the ingest's refusals rather than inventing their own answers.
    /// </summary>
    /// <remarks>
    /// The outcome case is the one that matters: defaulting a missing outcome to <c>Completed</c>
    /// would hand the scorer a verdict no agent declared, which is the single value ADR-0019 advisory-evaluator-calibration says
    /// must never be guessed.
    /// </remarks>
    [Fact]
    public void AnEpisodeRefusalIsExplainedAtCallTime()
    {
        var log = NewLog("episode-refusal");
        var writer = new CoordContractWriter(log, new FixedTimeProvider(DateTimeOffset.UnixEpoch.AddSeconds(At)));

        Assert.Contains("done condition", EpisodeTools.Open(writer, Terminal, "a goal", null, null));
        Assert.Contains("goal", EpisodeTools.Open(writer, Terminal, null, "a condition", null));
        Assert.Contains("not an outcome", EpisodeTools.Close(writer, Terminal, "finished", null));
        Assert.Contains("never defaulted", EpisodeTools.Close(writer, Terminal, null, null));

        // Nothing reached the log: a refusal at call time is a refusal to write, not a warning.
        Assert.Empty(Pump(log).AllEpisodes());
    }

    /// <summary>
    /// Closing with no evidence says so, and says what it costs.
    /// </summary>
    /// <remarks>
    /// It is accepted — an agent that declares nothing loses nothing it had — but the answer names
    /// the consequence, because "closed" alone reads as success to something optimising for it.
    /// </remarks>
    [Fact]
    public void ClosingWithNoEvidenceNamesTheCost()
    {
        var log = NewLog("episode-no-evidence");
        var writer = new CoordContractWriter(log, new FixedTimeProvider(DateTimeOffset.UnixEpoch.AddSeconds(At)));
        EpisodeTools.Open(writer, Terminal, "g", "d", null);

        var answer = EpisodeTools.Close(writer, Terminal, "completed", null);

        Assert.Contains("Not Scored", answer);
        var episode = Assert.Single(Pump(log).AllEpisodes());
        Assert.Equal(EpisodeOutcome.Completed, episode.Outcome);
    }

    /// <summary>
    /// Too many paths refuses the WHOLE close rather than truncating it.
    /// </summary>
    /// <remarks>
    /// A truncated evidence list reads as a complete one — the agent believes it declared its proof
    /// pack, the scorer sees a shorter list, and nothing tells either of them. Loud beats lossy.
    /// </remarks>
    [Fact]
    public void TooManyPathsRefusesTheWholeClose()
    {
        var log = NewLog("episode-too-many");
        var writer = new CoordContractWriter(log, new FixedTimeProvider(DateTimeOffset.UnixEpoch.AddSeconds(At)));
        EpisodeTools.Open(writer, Terminal, "g", "d", null);

        var tooMany = Enumerable.Range(0, DeclaredArtifactBounds.MaxPaths + 1).Select(i => $"docs/{i}.md").ToList();
        var answer = EpisodeTools.Close(writer, Terminal, "completed", tooMany);

        Assert.Contains("rather than truncated", answer);
        Assert.Equal(EpisodeState.Active, Assert.Single(Pump(log).AllEpisodes()).State);
    }

    /// <summary>The exact line an agent writes by hand, composed once.</summary>
    private static string Line(int seq, string kind, Dictionary<string, string?> attributes) =>
        System.Text.Json.JsonSerializer.Serialize(new Dictionary<string, object?>
        {
            ["kind"] = kind,
            ["contract"] = CoordContract.Version,
            ["session"] = Terminal,
            ["at"] = At + seq,
            ["seq"] = seq,
            ["attrs"] = attributes,
        });
}
