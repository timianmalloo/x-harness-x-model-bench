namespace AiDe.Core.Watcher;

/// <summary>
/// The non-secret identity a terminal/agent session presents when it registers with the watcher - the
/// attributes the coordination-contract register event carries (US-4/US-6). Harness and model are
/// optional (a plain shell has neither); everything else is required for a well-formed registration.
/// </summary>
public sealed record SessionCoordinationIdentity(
    string RepoPath,
    string RepoDisplay,
    string WorktreeBranch,
    string WorktreePath,
    string TerminalId,
    string AgentName,
    string? Harness = null,
    string? HarnessVersion = null,
    string? Model = null,
    string? ModelVersion = null)
{
    /// <summary>Maps the identity onto the OTel attribute keys the register event uses.</summary>
    public IReadOnlyDictionary<string, string?> ToAttributes()
    {
        var attrs = new Dictionary<string, string?>(StringComparer.Ordinal)
        {
            [OtelAttributes.RepoPath] = RepoPath,
            [OtelAttributes.RepoDisplay] = RepoDisplay,
            [OtelAttributes.WorktreeBranch] = WorktreeBranch,
            [OtelAttributes.WorktreePath] = WorktreePath,
            [OtelAttributes.TerminalId] = TerminalId,
            [OtelAttributes.AgentName] = AgentName,
        };

        // Only emitted when known - an absent harness/model is Not Recorded, never a guessed value (US-13).
        if (!string.IsNullOrEmpty(Harness))
        {
            attrs[OtelAttributes.ServiceName] = Harness;
            attrs[OtelAttributes.ServiceVersion] = HarnessVersion ?? string.Empty;
        }

        if (!string.IsNullOrEmpty(Model))
        {
            attrs[OtelAttributes.GenAiModel] = Model;
            attrs[OtelAttributes.GenAiModelVersion] = ModelVersion ?? string.Empty;
        }

        return attrs;
    }
}

/// <summary>
/// Writes the coordination-contract log a session opts in with so it appears in the watcher (US-4): a
/// register on start, periodic heartbeats while alive (so liveness stays Alive rather than going Stale),
/// and a session-end on close. This is the app-side WRITER; the <see cref="WatcherHost"/>'s pump is the
/// reader. Running both in one process is what makes a terminal launched in the app show up live.
/// </summary>
/// <remarks>
/// <para>Pure and explicit (Register / Heartbeat / HeartbeatAll / End) - no timer of its own, so it is
/// fully testable; the caller (the shell) drives heartbeats on whatever timer it already runs. It tracks
/// the live session ids so <see cref="HeartbeatAll"/> can keep them all alive with one call.</para>
/// <para>Re-reading the whole coordination log directory is idempotent on the reader side (registration
/// is keyed by external id), so a duplicate register is harmless; the emitter still guards against
/// re-registering an id it already tracks, to keep the log clean.</para>
/// </remarks>
public sealed class SessionCoordinationEmitter(CoordContractWriter writer)
{
    private readonly CoordContractWriter _writer = writer ?? throw new ArgumentNullException(nameof(writer));
    private readonly HashSet<string> _live = new(StringComparer.Ordinal);
    private readonly object _gate = new();

    /// <summary>The number of sessions currently registered and not yet ended.</summary>
    public int LiveCount
    {
        get { lock (_gate) { return _live.Count; } }
    }

    /// <summary>Registers a session (once) and writes its register event with the identity's attributes.</summary>
    public void Register(string externalSessionId, SessionCoordinationIdentity identity)
    {
        ArgumentException.ThrowIfNullOrEmpty(externalSessionId);
        ArgumentNullException.ThrowIfNull(identity);
        lock (_gate)
        {
            if (!_live.Add(externalSessionId))
            {
                return; // already registered - the register event is idempotent, but do not re-write it
            }
        }

        _writer.WriteRegister(externalSessionId, identity.ToAttributes());
    }

    /// <summary>Writes a heartbeat for one registered session; a no-op for an unknown/ended session.</summary>
    public void Heartbeat(string externalSessionId)
    {
        ArgumentException.ThrowIfNullOrEmpty(externalSessionId);
        lock (_gate)
        {
            if (!_live.Contains(externalSessionId))
            {
                return;
            }
        }

        _writer.WriteHeartbeat(externalSessionId);
    }

    /// <summary>Heartbeats every live session - the shell calls this on its refresh tick.</summary>
    public void HeartbeatAll()
    {
        string[] ids;
        lock (_gate)
        {
            ids = [.. _live];
        }

        foreach (var id in ids)
        {
            _writer.WriteHeartbeat(id);
        }
    }

    /// <summary>Writes a session-end for a session and stops tracking it; a no-op if unknown.</summary>
    public void End(string externalSessionId)
    {
        ArgumentException.ThrowIfNullOrEmpty(externalSessionId);
        lock (_gate)
        {
            if (!_live.Remove(externalSessionId))
            {
                return;
            }
        }

        _writer.WriteSessionEnd(externalSessionId);
    }

    /// <summary>
    /// Reconciles the live set against the sessions that currently exist: registers a new one, heartbeats
    /// one already live, and ends one that has gone. This lets the caller drive the emitter from a simple
    /// periodic snapshot of "which sessions exist now" (e.g. the terminal surfaces in the layout) without
    /// precise per-session start/close events. <paramref name="identityFor"/> supplies the register
    /// attributes for a newly-seen session.
    /// </summary>
    public void Reconcile(IReadOnlySet<string> currentSessionIds, Func<string, SessionCoordinationIdentity> identityFor)
    {
        ArgumentNullException.ThrowIfNull(currentSessionIds);
        ArgumentNullException.ThrowIfNull(identityFor);

        foreach (var id in currentSessionIds)
        {
            bool isLive;
            lock (_gate)
            {
                isLive = _live.Contains(id);
            }

            if (isLive)
            {
                Heartbeat(id);
            }
            else
            {
                Register(id, identityFor(id));
            }
        }

        // End any tracked session that is no longer present.
        string[] gone;
        lock (_gate)
        {
            gone = [.. _live.Where(id => !currentSessionIds.Contains(id))];
        }

        foreach (var id in gone)
        {
            End(id);
        }
    }
}
