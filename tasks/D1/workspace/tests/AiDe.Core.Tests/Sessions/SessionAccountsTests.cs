using AiDe.Core.AgentPlane;
using AiDe.Core.Sessions;

namespace AiDe.Core.Tests.Sessions;

/// <summary>
/// Ruling 105 (1) and condition 2: a session's config holds <b>account selections and one default
/// account</b> — engine ids are never stored on the session (the engine is derived from the provider
/// through the catalog) — a default change is a config-changed event that applies to new turns
/// only, and the migration from <c>enabledBackends</c> maps a singleton-account provider and
/// refuses to guess among several.
/// </summary>
public sealed class SessionAccountsTests : IDisposable
{
    private readonly string _workspaceRoot;
    private readonly string _providersDirectory;

    public SessionAccountsTests()
    {
        _workspaceRoot = Directory.CreateTempSubdirectory("aide-session-accounts-tests-").FullName;
        _providersDirectory = Directory.CreateTempSubdirectory("aide-session-accounts-providers-").FullName;
    }

    public void Dispose()
    {
        Directory.Delete(_workspaceRoot, recursive: true);
        Directory.Delete(_providersDirectory, recursive: true);
    }

    private static readonly AccountRef Max = new("anthropic", "max");
    private static readonly AccountRef Work = new("anthropic", "work");

    [Fact]
    public void Create_WritesAccountsAndADefault_AndTheyRoundTrip()
    {
        var sessionId = SessionId.New();
        var store = new SessionConfigStore(_workspaceRoot, sessionId);

        var created = store.Create("payments", "ws", [Max, Work], Max, DateTimeOffset.UtcNow);

        Assert.Equal([Max, Work], created.Accounts);
        Assert.Equal(Max, created.DefaultAccount);

        var loaded = new SessionConfigStore(_workspaceRoot, sessionId).Load();
        Assert.Equal([Max, Work], loaded.Accounts);
        Assert.Equal(Max, loaded.DefaultAccount);

        // Engine ids are NOT on the session (Ruling 105: derived from the provider via the catalog).
        var json = File.ReadAllText(SessionPaths.SessionFile(_workspaceRoot, sessionId));
        Assert.DoesNotContain("EnabledBackends", json, StringComparison.Ordinal);
        Assert.DoesNotContain("claude-code", json, StringComparison.Ordinal);
    }

    /// <summary>
    /// Ruling 105 condition 2 (first half): changing <c>DefaultAccount</c> mid-session leaves every
    /// prior turn's recorded binding unchanged — the config a turn captured and the event lines
    /// already on disk — and applies to the next turn only.
    /// </summary>
    [Fact]
    public void SetDefaultAccount_NeverMutatesAConfigARunAlreadyCaptured_AndAppliesToTheNextTurnOnly()
    {
        var sessionId = SessionId.New();
        var store = new SessionConfigStore(_workspaceRoot, sessionId);
        store.Create("payments", "ws", [Max, Work], Max, DateTimeOffset.UtcNow);

        var eventsPath = SessionPaths.EventsFile(_workspaceRoot, sessionId);
        var turnOne = store.Load();                       // turn 1 binds against this
        var linesBefore = File.ReadAllLines(eventsPath);

        var changed = store.SetDefaultAccount(Work, DateTimeOffset.UtcNow);

        Assert.Equal(Max, turnOne.DefaultAccount);         // turn 1's binding is untouched
        Assert.Equal(Work, changed.DefaultAccount);
        Assert.Equal(Work, store.Load().DefaultAccount);   // turn 2 picks the new default up

        var linesAfter = File.ReadAllLines(eventsPath);
        Assert.Equal(linesBefore, linesAfter.Take(linesBefore.Length));   // earlier lines byte-for-byte
        Assert.Equal(SessionEventKinds.Config, store.ReadEvents()[^1].Kind);
        Assert.Contains("\"defaultAccount\"", linesAfter[^1], StringComparison.Ordinal);
    }

    [Fact]
    public void SetAccounts_DropsADefaultThatIsNoLongerSelected_RatherThanKeepingAPhantom()
    {
        var store = new SessionConfigStore(_workspaceRoot, SessionId.New());
        store.Create("payments", "ws", [Max, Work], Work, DateTimeOffset.UtcNow);

        var updated = store.SetAccounts([Max], DateTimeOffset.UtcNow);

        Assert.Equal([Max], updated.Accounts);
        Assert.Null(updated.DefaultAccount);
    }

    /// <summary>
    /// Ruling 105 condition 2 (second half, case 1): an old <c>session.json</c> carrying
    /// <c>EnabledBackends: ["claude-code"]</c> maps to its provider's account when that provider
    /// carries exactly one. The file under test predates the code under test.
    /// </summary>
    [Fact]
    public void MigrateLegacyBackends_MapsASingletonAccountProvider()
    {
        var sessionId = WriteLegacySession(["claude-code"]);
        var providers = WriteProviders("""
            { "providers": { "anthropic": { "auth": "subscription", "accounts": [ { "label": "max", "health": "ready" } ] } },
              "engines": { "claude-code": { "model": "claude-sonnet-5" } } }
            """);

        var store = new SessionConfigStore(_workspaceRoot, sessionId);
        var before = store.Load();
        Assert.Empty(before.Accounts);
        Assert.Null(before.DefaultAccount);
        Assert.Equal(["claude-code"], before.LegacyEnabledBackends);

        var migrated = store.MigrateLegacyBackends(providers, DateTimeOffset.UtcNow);

        Assert.Equal([Max], migrated.Accounts);
        Assert.Equal(Max, migrated.DefaultAccount);
        Assert.Empty(migrated.LegacyEnabledBackends);

        // Contracted: the legacy key is gone from the file, and the migration is an event.
        var json = File.ReadAllText(SessionPaths.SessionFile(_workspaceRoot, sessionId));
        Assert.DoesNotContain("EnabledBackends", json, StringComparison.Ordinal);
        Assert.Equal(SessionEventKinds.Config, store.ReadEvents()[^1].Kind);
    }

    /// <summary>
    /// Case 2: two accounts and no selection is <b>never</b> guessed — the session opens with no
    /// default account (the sheet/settings say "choose one"), and the legacy key survives on disk
    /// untouched (expand-migrate-contract: nothing is contracted until something was migrated).
    /// </summary>
    [Fact]
    public void MigrateLegacyBackends_RefusesToGuessAmongSeveral_AndOpensWithNoDefault()
    {
        var sessionId = WriteLegacySession(["claude-code"]);
        var providers = WriteProviders("""
            { "providers": { "anthropic": { "auth": "subscription", "accounts": [
                { "label": "max", "health": "ready" }, { "label": "work", "health": "ready" } ] } },
              "engines": { "claude-code": { "model": "claude-sonnet-5" } } }
            """);

        var store = new SessionConfigStore(_workspaceRoot, sessionId);
        var migrated = store.MigrateLegacyBackends(providers, DateTimeOffset.UtcNow);

        Assert.Empty(migrated.Accounts);
        Assert.Null(migrated.DefaultAccount);
        Assert.Equal(["claude-code"], migrated.LegacyEnabledBackends);
        Assert.Contains("EnabledBackends", File.ReadAllText(SessionPaths.SessionFile(_workspaceRoot, sessionId)), StringComparison.Ordinal);
        Assert.Equal(SessionEventKinds.Open, store.ReadEvents()[^1].Kind);   // nothing changed, nothing emitted
    }

    /// <summary>
    /// Ruling 105 condition 8: the file's <c>engines.&lt;id&gt;.account</c> key is the <b>fallback
    /// default only</b> — the migration honours it among several accounts because the operator wrote
    /// it, which is a selection, not a guess.
    /// </summary>
    [Fact]
    public void MigrateLegacyBackends_HonoursTheFilesEngineAccountKeyAsTheFallbackDefault()
    {
        var sessionId = WriteLegacySession(["claude-code"]);
        var providers = WriteProviders("""
            { "providers": { "anthropic": { "auth": "subscription", "accounts": [
                { "label": "max", "health": "ready" }, { "label": "work", "health": "ready" } ] } },
              "engines": { "claude-code": { "model": "claude-sonnet-5", "account": "work" } } }
            """);

        var migrated = new SessionConfigStore(_workspaceRoot, sessionId).MigrateLegacyBackends(providers, DateTimeOffset.UtcNow);

        Assert.Equal([Work], migrated.Accounts);
        Assert.Equal(Work, migrated.DefaultAccount);
    }

    /// <summary>
    /// Ruling 104 (2): <c>adapterInstallRoot</c> is optional — absent reads as the <c>adapters</c>
    /// directory beside the file (<c>~/.aide/adapters</c> at the default path); present overrides.
    /// </summary>
    [Fact]
    public void AdapterInstallRoot_AbsentIsTheAdaptersDirectoryBesideTheFile_PresentOverrides()
    {
        var absent = WriteProviders("""{ "providers": {} }""");
        Assert.Equal(Path.Combine(_providersDirectory, "adapters"), absent.AdapterInstallRoot);
        Assert.True(absent.AdapterInstallRootIsDefault);

        var present = WriteProviders("""{ "adapterInstallRoot": "D:/elsewhere", "providers": {} }""", "present.json");
        Assert.Equal("D:/elsewhere", present.AdapterInstallRoot);
        Assert.False(present.AdapterInstallRootIsDefault);
    }

    private string WriteLegacySession(string[] enabledBackends)
    {
        var sessionId = SessionId.New();
        Directory.CreateDirectory(SessionPaths.SessionDirectory(_workspaceRoot, sessionId));
        var backends = string.Join(", ", enabledBackends.Select(b => $"\"{b}\""));
        File.WriteAllText(
            SessionPaths.SessionFile(_workspaceRoot, sessionId),
            $$"""
            {
              "SessionId": "{{sessionId}}",
              "Name": "payments",
              "WorkspaceId": "ws",
              "CreatedAt": "2026-01-01T00:00:00+00:00",
              "EnabledBackends": [{{backends}}],
              "AttachEnabled": false
            }
            """);
        // The file predates the code: it has a session.open line and no config line.
        new SessionConfigStore(_workspaceRoot, sessionId).AppendOpenForTests(DateTimeOffset.UtcNow);
        return sessionId;
    }

    private ProviderConfiguration WriteProviders(string json, string name = "providers.json")
    {
        var path = Path.Combine(_providersDirectory, name);
        File.WriteAllText(path, json);
        return ProviderConfiguration.Read(path);
    }
}
