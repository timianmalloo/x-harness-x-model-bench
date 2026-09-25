using AiDe.Core.Watcher;

namespace AiDe.Mcp;

/// <summary>
/// Everything the server resolved about where it is and who is calling — including the absences.
/// </summary>
/// <remarks>
/// <para>Resolved once at startup rather than per call, because the answers are properties of how the
/// process was launched and cannot change under it. The one thing that could — a session ending —
/// is read from the store on each call instead.</para>
///
/// <para><b>Every failure here is a state, not an exception.</b> No workspace, no store, no session:
/// the server starts anyway and each tool says which of them is missing. A server that refuses to
/// start tells the agent only that something is wrong, and the agent has no way to find out what.</para>
/// </remarks>
public sealed record ServerContext(
    string? ContractLogDirectory,
    string? StorePath,
    ResolvedIdentity Identity,
    string? Unavailable)
{
    /// <summary>The store, opened read-only per call. Null when there is none to open.</summary>
    public string? DatabasePath => StorePath;

    /// <summary>A context that resolved nothing, for a self-test or a shell outside AI-DE.</summary>
    public static ServerContext None(string reason) =>
        new(null, null, new ResolvedIdentity(null, IdentitySource.None,
            "This is not an AI-DE session. Open a terminal from AI-DE's Terminal menu."), reason);

    /// <summary>
    /// Resolves the context from the environment and the working directory.
    /// </summary>
    /// <remarks>
    /// <c>AIDE_CONTRACT_LOG</c> gives the coordination directory; the workspace store sits beside it,
    /// because <c>WatcherHost.Open</c> puts the coord log inside the workspace data directory. That
    /// relationship is derived from the launcher rather than configured, so there is no second path
    /// to keep in step.
    /// </remarks>
    public static ServerContext Discover()
    {
        var contractLog = Environment.GetEnvironmentVariable("AIDE_CONTRACT_LOG");
        var sessionId = Environment.GetEnvironmentVariable(SessionIdentity.SessionVariable);
        var cwd = Directory.GetCurrentDirectory();

        if (string.IsNullOrWhiteSpace(contractLog))
        {
            return None(
                $"{SessionIdentity.SessionVariable} and AIDE_CONTRACT_LOG are unset, so this shell was "
                + "not started by AI-DE.");
        }

        // The coord log lives at <workspaceData>/loomkeeper-coord, so its parent holds watcher.db.
        var workspaceData = Path.GetDirectoryName(contractLog.TrimEnd('\\', '/'));
        var store = workspaceData is null ? null : Path.Combine(workspaceData, "watcher.db");
        if (store is not null && !File.Exists(store))
        {
            store = null;
        }

        var sessions = ReadSessions(store);
        var identity = SessionIdentity.Resolve(sessionId, cwd, sessions);

        return new ServerContext(
            contractLog,
            store,
            identity,
            store is null ? "The workspace store has not been created yet — open the workspace in AI-DE." : null);
    }

    /// <summary>One line for stderr, so a failure to identify is visible in the client's log.</summary>
    public string Describe() =>
        Identity.IsResolved
            ? $"session {Identity.Session!.SessionId} ({Identity.Source})"
            : $"no session ({Identity.Source}): {Identity.Reason}";

    /// <summary>Opens the store read-only, or returns an empty list with the reason.</summary>
    /// <remarks>
    /// <b>Read-only is a design property, not caution.</b> The server's claim is that it holds no
    /// authority an agent lacks; a write handle to the fact store would be exactly such an authority,
    /// and would bypass every guarantee the ingest provides. A test asserts the connection string
    /// carries it.
    /// </remarks>
    public static IReadOnlyList<SessionRecord> ReadSessions(string? storePath)
    {
        if (string.IsNullOrWhiteSpace(storePath) || !File.Exists(storePath))
        {
            return [];
        }

        try
        {
            using var store = SqliteWatcherObservationStore.OpenReadOnly(storePath);
            return store.AllSessions();
        }
        catch (Exception ex) when (ex is IOException or InvalidOperationException)
        {
            return [];
        }
    }
}
