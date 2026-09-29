using AiDe.Core.Sessions;

namespace AiDe.Core.PromptCompilation;

/// <summary>
/// What <c>aide session purge &lt;id&gt;</c> will do, resolved and read before anything is touched
/// — the confirmation names an identity, never a count alone (DC-120; US-D13).
/// </summary>
/// <param name="Name">The session's name, from <c>session.json</c>.</param>
/// <param name="SessionId">The id, validated as one segment of the session-id grammar.</param>
/// <param name="WorkspaceRoot">The workspace the id was resolved under.</param>
/// <param name="ResolvedFilePath">The absolute path of the one file the purge removes.</param>
/// <param name="Rows">How many lines the file holds — zero (or no file: the store creates it empty at open) is nothing to purge.</param>
/// <param name="EnvelopeCount">How many envelopes the file folds to.</param>
/// <param name="NewestAt">The newest <c>at</c> in the file, or null.</param>
public sealed record PurgePlan(
    string Name,
    string SessionId,
    string WorkspaceRoot,
    string ResolvedFilePath,
    int Rows,
    int EnvelopeCount,
    DateTimeOffset? NewestAt)
{
    /// <summary>Whether there is any history to purge: a file with at least one line (an empty file is the store's own handle, not history).</summary>
    public bool HasHistory => Rows > 0;

    /// <summary>The confirmation, one line per fact.</summary>
    public string Describe() =>
        $"session: {Name}\nid: {SessionId}\nworkspace: {WorkspaceRoot}\nfile: {ResolvedFilePath}\nenvelopes: {EnvelopeCount}\nnewest: {(NewestAt is { } at ? at.ToUniversalTime().ToString("O", System.Globalization.CultureInfo.InvariantCulture) : Envelope.NotRecorded)}";
}

/// <summary>
/// Deletes a session's <c>envelope-events.jsonl</c> and nothing else (ADR-0034 rule 6; §A13.5 rule 1).
/// <c>session.json</c>, <c>session-events.jsonl</c>, the layout files and <c>runs/</c> belong to
/// the Session aggregate and its own command.
/// </summary>
public static class EnvelopePurge
{
    /// <summary>
    /// Resolves the plan: validates the id as one segment, resolves it under
    /// <c>&lt;workspace&gt;/.aide/sessions/</c> without following a junction or symlink, and reads
    /// the file — refused visibly while a writer holds it.
    /// </summary>
    /// <exception cref="EnvelopeStoreException">
    /// <see cref="EnvelopeStoreErrorCodes.PurgeRefused"/> before any file is touched;
    /// <see cref="EnvelopeStoreErrorCodes.HeldByAnotherWriter"/> while a composer holds the file.
    /// </exception>
    public static PurgePlan Resolve(string workspaceRoot, string sessionId)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(workspaceRoot);
        ArgumentNullException.ThrowIfNull(sessionId);

        // ONE SEGMENT OF THE GRAMMAR, checked before the path is even formed: `..\..`, a slash, a
        // name that is not a session id — every one is refused here, so no traversal can resolve.
        if (!SessionId.IsValid(sessionId))
        {
            throw new EnvelopeStoreException(
                EnvelopeStoreErrorCodes.PurgeRefused,
                $"'{sessionId}' is not one segment of the session-id grammar (yyyyMMddTHHmmssZ-xxxxxxxx); nothing was touched");
        }

        var root = Path.GetFullPath(workspaceRoot);
        var sessionsRoot = Path.GetFullPath(SessionPaths.SessionsRoot(root));
        var directory = Path.GetFullPath(SessionPaths.SessionDirectory(root, sessionId));

        if (!string.Equals(Path.GetDirectoryName(directory), sessionsRoot, StringComparison.Ordinal))
        {
            throw new EnvelopeStoreException(EnvelopeStoreErrorCodes.PurgeRefused, $"'{sessionId}' does not resolve directly under {sessionsRoot}; nothing was touched");
        }

        if (!Directory.Exists(directory))
        {
            throw new EnvelopeStoreException(EnvelopeStoreErrorCodes.PurgeRefused, $"no session '{sessionId}' under {sessionsRoot}; nothing was touched");
        }

        // JUNCTIONS AND SYMLINKS ARE NOT FOLLOWED: a session directory that is a reparse point
        // points somewhere this command was not asked about.
        if (new DirectoryInfo(directory).Attributes.HasFlag(FileAttributes.ReparsePoint))
        {
            throw new EnvelopeStoreException(EnvelopeStoreErrorCodes.PurgeRefused, $"'{directory}' is a junction or symbolic link and is not followed; nothing was touched");
        }

        var file = Path.Combine(directory, EnvelopeStore.FileName);
        var name = ReadName(root, sessionId);

        if (new FileInfo(file) is { Exists: true } info && info.Attributes.HasFlag(FileAttributes.ReparsePoint))
        {
            throw new EnvelopeStoreException(EnvelopeStoreErrorCodes.PurgeRefused, $"'{file}' is a symbolic link and is not followed; nothing was touched");
        }

        var fold = EnvelopeStore.ReadFile(file);
        return new PurgePlan(name, sessionId, root, file, fold.Rows, fold.Envelopes.Count, fold.NewestAt);
    }

    /// <summary>Removes the one file the plan names. A file already absent is not an error.</summary>
    /// <exception cref="EnvelopeStoreException"><see cref="EnvelopeStoreErrorCodes.HeldByAnotherWriter"/> when a composer opened it since the plan was read.</exception>
    public static void Execute(PurgePlan plan)
    {
        ArgumentNullException.ThrowIfNull(plan);

        // THE PATH IS RE-VALIDATED HERE, not trusted from the plan: a PurgePlan is a public record, so
        // containment lives at the moment of deletion too — the file is the envelope file, directly
        // under <workspace>/.aide/sessions/<one segment>/, and that segment is the plan's session id.
        var file = Path.GetFullPath(plan.ResolvedFilePath);
        var directory = Path.GetDirectoryName(file);
        var expected = Path.GetFullPath(Path.Combine(SessionPaths.SessionDirectory(plan.WorkspaceRoot, plan.SessionId), EnvelopeStore.FileName));
        if (!SessionId.IsValid(plan.SessionId)
            || !string.Equals(file, expected, StringComparison.Ordinal)
            || directory is null
            || new DirectoryInfo(directory).Attributes.HasFlag(FileAttributes.ReparsePoint))
        {
            throw new EnvelopeStoreException(EnvelopeStoreErrorCodes.PurgeRefused, $"'{plan.ResolvedFilePath}' is not the envelope file of session '{plan.SessionId}' under {plan.WorkspaceRoot}; nothing was touched");
        }

        if (!File.Exists(file))
        {
            return;
        }

        if (new FileInfo(file).Attributes.HasFlag(FileAttributes.ReparsePoint))
        {
            throw new EnvelopeStoreException(EnvelopeStoreErrorCodes.PurgeRefused, $"'{file}' became a symbolic link between the plan and the act; nothing was touched");
        }

        try
        {
            // Acquire exclusively and delete under the handle: a writer that opened the file since
            // the plan was read is refused here rather than raced.
            using var handle = new FileStream(file, FileMode.Open, FileAccess.ReadWrite, FileShare.None, 1, FileOptions.DeleteOnClose);
        }
        catch (FileNotFoundException)
        {
            // Gone between the plan and the act — the outcome the operator asked for.
        }
        catch (IOException error)
        {
            throw new EnvelopeStoreException(EnvelopeStoreErrorCodes.HeldByAnotherWriter, $"another AI-DE has this session's compile history open ({plan.ResolvedFilePath}); close it and purge again", error);
        }
    }

    private static string ReadName(string root, string sessionId)
    {
        try
        {
            return new SessionConfigStore(root, sessionId).Load().Name;
        }
        catch (Exception error) when (error is IOException or System.Text.Json.JsonException or InvalidOperationException)
        {
            return Envelope.NotRecorded;
        }
    }
}
