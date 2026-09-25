using System.Text.Json;
using AiDe.Core.AgentPlane;
using AiDe.Core.Sessions;
using AiDe.Core.Watcher;

namespace AiDe.Core.Tests.Sessions;

/// <summary>
/// F0 clauses 1-3 (docs/plans/conductor-front-door.md): <c>session.json</c> round-trips through
/// <see cref="System.Text.Json"/>, backend toggles apply to new runs only and never rewrite a
/// config already picked up, and nothing writes under the reserved <c>runs/</c> path.
/// </summary>
public sealed class SessionConfigStoreTests : IDisposable
{
    private readonly string _workspaceRoot;

    public SessionConfigStoreTests()
    {
        _workspaceRoot = Directory.CreateTempSubdirectory("aide-session-store-tests-").FullName;
    }

    public void Dispose() => Directory.Delete(_workspaceRoot, recursive: true);

    private static readonly AccountRef Max = new("anthropic", "max");
    private static readonly AccountRef Codex = new("openai", "chatgpt");

    [Fact]
    public void Create_WritesSessionJsonAtTheContractPath()
    {
        var sessionId = SessionId.New();
        var store = new SessionConfigStore(_workspaceRoot, sessionId);
        var now = DateTimeOffset.UtcNow;

        store.Create("payments extraction", "workspace-1", [Max], Max, now);

        var path = SessionPaths.SessionFile(_workspaceRoot, sessionId);
        Assert.True(File.Exists(path));
    }

    /// <summary>
    /// Ruling 99: session names are unique within a workspace by a counter suffix, and the rule is
    /// ONE function — the sheet's default name, an operator-typed duplicate at Create, and the later
    /// parallel-session slice (its parent's name) all call it. Counted over every session the store holds.
    /// </summary>
    [Fact]
    public void UniqueName_CountsUpFromTwo_OverEverySessionInTheStore_AndNeverRefuses()
    {
        var now = DateTimeOffset.UtcNow;
        new SessionConfigStore(_workspaceRoot, SessionId.New(now)).Create("2026-09-14 session", "ws", [], null, now);
        new SessionConfigStore(_workspaceRoot, SessionId.New(now)).Create("2026-09-14 session (2)", "ws", [], null, now);

        var existing = SessionConfigStore.ExistingNames(_workspaceRoot);
        Assert.Equal(["2026-09-14 session", "2026-09-14 session (2)"], existing.OrderBy(n => n, StringComparer.Ordinal));

        Assert.Equal("2026-09-14 session (3)", SessionConfigStore.UniqueName("2026-09-14 session", existing));
        // A counter the operator (or a parent session) already carries is not part of the base.
        Assert.Equal("2026-09-14 session (3)", SessionConfigStore.UniqueName("2026-09-14 session (2)", existing));
        Assert.Equal("other", SessionConfigStore.UniqueName("other", existing));
        Assert.Equal("2026-09-14 session (2)", SessionConfigStore.UniqueName("2026-09-14 session", ["2026-09-14 session"]));

        // A workspace with no sessions root yet has no names — an empty answer, never a throw.
        Assert.Empty(SessionConfigStore.ExistingNames(Path.Combine(_workspaceRoot, "never-created")));
    }

    [Fact]
    public void Create_ThenLoad_RoundTripsEveryField()
    {
        var sessionId = SessionId.New();
        var store = new SessionConfigStore(_workspaceRoot, sessionId);
        var now = DateTimeOffset.UtcNow;

        var created = store.Create("payments extraction", "workspace-1", [Max, Codex], Max, now);
        var loaded = store.Load();

        Assert.Equal(sessionId, loaded.SessionId);
        Assert.Equal("payments extraction", loaded.Name);
        Assert.Equal("workspace-1", loaded.WorkspaceId);
        Assert.Equal(created.CreatedAt, loaded.CreatedAt);
        Assert.Equal(created.Accounts, loaded.Accounts);
        Assert.Equal(created.DefaultAccount, loaded.DefaultAccount);
    }

    [Fact]
    public void Load_SurvivesAFreshStoreInstance_ProvingItIsReallyPersisted()
    {
        var sessionId = SessionId.New();
        var writer = new SessionConfigStore(_workspaceRoot, sessionId);
        writer.Create("payments extraction", "workspace-1", [Max], Max, DateTimeOffset.UtcNow);

        var reader = new SessionConfigStore(_workspaceRoot, sessionId);
        var loaded = reader.Load();

        Assert.Equal([Max], loaded.Accounts);
    }

    /// <summary>
    /// Clause 3's oracle: a toggle applies to NEW runs only. A run captures the config in effect at
    /// its own start; because <see cref="SessionConfig"/> is an immutable record and every mutation
    /// through the store produces a fresh instance, a snapshot a run already captured must never
    /// change under it when a later toggle lands.
    /// </summary>
    [Fact]
    public void SetAccounts_NeverMutatesAConfigARunAlreadyCaptured()
    {
        var sessionId = SessionId.New();
        var store = new SessionConfigStore(_workspaceRoot, sessionId);
        store.Create("payments extraction", "workspace-1", [Max, Codex], Max, DateTimeOffset.UtcNow);

        // "run 1" captures the config in effect now.
        var runOneConfig = store.Load();
        Assert.Equal([Max, Codex], runOneConfig.Accounts);

        // The operator drops the codex account mid-session.
        store.SetAccounts([Max], DateTimeOffset.UtcNow);

        // run 1's already-captured snapshot must read exactly as it did when captured.
        Assert.Equal([Max, Codex], runOneConfig.Accounts);

        // A NEW run ("run 2") captures the change.
        var runTwoConfig = store.Load();
        Assert.Equal([Max], runTwoConfig.Accounts);
    }

    [Fact]
    public void SetAccounts_EmitsASessionConfigEvent()
    {
        var sessionId = SessionId.New();
        var store = new SessionConfigStore(_workspaceRoot, sessionId);
        store.Create("payments extraction", "workspace-1", [Max], Max, DateTimeOffset.UtcNow);

        store.SetAccounts([Max, Codex], DateTimeOffset.UtcNow);

        var events = store.ReadEvents();
        Assert.Equal(2, events.Count); // session.open from Create, session.config from the toggle
        Assert.Equal(SessionEventKinds.Open, events[0].Kind);
        Assert.Equal(SessionEventKinds.Config, events[1].Kind);
    }

    /// <summary>
    /// The append-only half of clause 3's oracle, at the persisted-event layer rather than the
    /// in-memory-record layer: an event already written to <c>session-events.jsonl</c> is never
    /// rewritten by a later toggle.
    /// </summary>
    [Fact]
    public void SessionEventsFile_EarlierEventsSurviveByteForByteAfterALaterToggle()
    {
        var sessionId = SessionId.New();
        var store = new SessionConfigStore(_workspaceRoot, sessionId);
        store.Create("payments extraction", "workspace-1", [Max], Max, DateTimeOffset.UtcNow);

        var eventsPath = SessionPaths.EventsFile(_workspaceRoot, sessionId);
        var firstLineAfterCreate = File.ReadAllLines(eventsPath)[0];

        store.SetAccounts([Max, Codex], DateTimeOffset.UtcNow);
        store.SetAccounts([Codex], DateTimeOffset.UtcNow);

        var firstLineAfterTwoToggles = File.ReadAllLines(eventsPath)[0];
        Assert.Equal(firstLineAfterCreate, firstLineAfterTwoToggles);
    }

    /// <summary>
    /// Fails if: anything writes a run log anywhere. Dynamic half — exercises the store's full
    /// lifecycle (create, two toggles, reads) and asserts the reserved subtree never came into
    /// existence. <c>RunLogStore</c> is Phase 3 and this node must not build it.
    /// </summary>
    [Fact]
    public void Lifecycle_NeverWritesUnderTheReservedRunsDirectory()
    {
        var sessionId = SessionId.New();
        var store = new SessionConfigStore(_workspaceRoot, sessionId);
        store.Create("payments extraction", "workspace-1", [Max], Max, DateTimeOffset.UtcNow);
        store.SetAccounts([Max, Codex], DateTimeOffset.UtcNow);
        store.SetAccounts([Codex], DateTimeOffset.UtcNow);
        _ = store.Load();
        _ = store.ReadEvents();

        var runsDirectory = SessionPaths.RunsDirectory(_workspaceRoot, sessionId);
        var reservedRunLog = SessionPaths.RunLogFile(_workspaceRoot, sessionId, "run-1");

        Assert.False(Directory.Exists(runsDirectory), $"{runsDirectory} must not exist — RunLogStore is Phase 3");
        Assert.False(File.Exists(reservedRunLog), $"{reservedRunLog} must not exist — RunLogStore is Phase 3");
    }

    // ---- S2: the settings and sentinels commit (ADR-0033 §3/§4; Rulings 56, 68, 70, 72) ----------

    /// <summary>
    /// The red this commit's four new fields must turn green: a <c>session.json</c> written by
    /// TODAY'S code — before this commit — carries none of them, and reading it back must yield the
    /// ruled defaults rather than an error or a silently wrong value. Written by hand, from the exact
    /// shape the store's writer produced before this change (no
    /// <c>FanOutCeiling</c>/<c>BudgetCap</c>/<c>CompileMode</c>/<c>DefaultTaskClass</c> keys), rather
    /// than produced by today's store — the file under test must predate the code under test.
    /// </summary>
    [Fact]
    public void Load_AnOldSessionFileWithNoneOfTheFourNewFields_ReadsBackWithTheirDefaults()
    {
        var sessionId = SessionId.New();
        Directory.CreateDirectory(SessionPaths.SessionDirectory(_workspaceRoot, sessionId));

        const string oldShapeJson = """
            {
              "SessionId": "will-be-replaced",
              "Name": "payments extraction",
              "WorkspaceId": "workspace-1",
              "CreatedAt": "2026-01-01T00:00:00+00:00",
              "EnabledBackends": ["claude-code"],
              "AttachEnabled": false
            }
            """;
        File.WriteAllText(
            SessionPaths.SessionFile(_workspaceRoot, sessionId),
            oldShapeJson.Replace("will-be-replaced", sessionId, StringComparison.Ordinal));

        var loaded = new SessionConfigStore(_workspaceRoot, sessionId).Load();

        Assert.Equal(2, loaded.FanOutCeiling);
        Assert.Null(loaded.BudgetCap);
        Assert.Equal(CompileModes.MechanicalOnly, loaded.CompileMode);
        Assert.Equal(TaskClasses.FreeForm, loaded.DefaultTaskClass);
    }

    /// <summary>A session created by today's <see cref="SessionConfigStore.Create"/> gets the same defaults.</summary>
    [Fact]
    public void Create_SetsTheRuledDefaultsForTheFourNewFields()
    {
        var sessionId = SessionId.New();
        var store = new SessionConfigStore(_workspaceRoot, sessionId);

        var created = store.Create("payments extraction", "workspace-1", [Max], Max, DateTimeOffset.UtcNow);

        Assert.Equal(2, created.FanOutCeiling);
        Assert.Null(created.BudgetCap);
        Assert.Equal(CompileModes.MechanicalOnly, created.CompileMode);
        Assert.Equal(TaskClasses.FreeForm, created.DefaultTaskClass);
    }

    /// <summary>Each new field round-trips a non-default value through the store's own JSON contract.</summary>
    /// <summary>
    /// Rulings 72 and 56: the New Session sheet decides the ceiling, the cap and the default class at
    /// create, so <c>Create</c> takes them — and an old caller that passes none still gets the ruled
    /// defaults (the S2 test above). Red before CV-0: <c>Create</c> took only the four original
    /// arguments.
    /// </summary>
    [Fact]
    public void Create_WritesTheSettingsItIsGiven_AndTheyReadBack()
    {
        var now = new DateTimeOffset(2026, 9, 12, 9, 0, 0, TimeSpan.Zero);
        var store = new SessionConfigStore(_workspaceRoot, "20260912T090000Z-settings");

        var created = store.Create(
            "settings", "w-1", [Max], Max, now,
            fanOutCeiling: 3,
            budgetCap: new RunBudget(40, 90_000),
            defaultTaskClass: "review");

        Assert.Equal(3, created.FanOutCeiling);
        Assert.Equal(new RunBudget(40, 90_000), created.BudgetCap);
        Assert.Equal("review", created.DefaultTaskClass);

        var loaded = new SessionConfigStore(_workspaceRoot, "20260912T090000Z-settings").Load();
        Assert.Equal(3, loaded.FanOutCeiling);
        Assert.Equal(new RunBudget(40, 90_000), loaded.BudgetCap);
        Assert.Equal("review", loaded.DefaultTaskClass);
    }

    [Fact]
    public void EachOfTheFourNewFields_RoundTripsANonDefaultValueThroughPersistedJson()
    {
        var sessionId = SessionId.New();
        var store = new SessionConfigStore(_workspaceRoot, sessionId);
        var created = store.Create("payments extraction", "workspace-1", [Max], Max, DateTimeOffset.UtcNow);

        var nonDefault = created with
        {
            FanOutCeiling = 4,
            BudgetCap = new RunBudget(250, 600_000),
            CompileMode = CompileModes.Agentic,
            DefaultTaskClass = "refactor",
        };

        File.WriteAllText(
            SessionPaths.SessionFile(_workspaceRoot, sessionId),
            JsonSerializer.Serialize(nonDefault));

        var loaded = new SessionConfigStore(_workspaceRoot, sessionId).Load();

        Assert.Equal(4, loaded.FanOutCeiling);
        Assert.Equal(new RunBudget(250, 600_000), loaded.BudgetCap);
        Assert.Equal(CompileModes.Agentic, loaded.CompileMode);
        Assert.Equal("refactor", loaded.DefaultTaskClass);
    }
}
