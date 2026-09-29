namespace AiDe.Core.Watcher;

/// <summary>
/// Binds session identity and issues a per-session capability verified on every event (ADR-0020 trusted-registrar-harness-model-identity,
/// extends ADR-0007). Capabilities are held in-process and are never persisted to the observation
/// store, so the secret never reaches the durable facts.
/// </summary>
public interface ITrustedRegistrar
{
    /// <summary>Registers a new session; issues its first generation and its capability.</summary>
    RegisteredSession Register(SessionBinding binding);

    /// <summary>
    /// Registers the next generation of an existing session (a terminal restart). The new generation
    /// gets a fresh capability that invalidates the prior one, resets liveness, and clears any ended
    /// state - the new generation cannot inherit the prior generation's authority or liveness.
    /// </summary>
    RegisteredSession RegisterNextGeneration(string sessionId, SessionBinding binding);

    /// <summary>
    /// Records a harness and/or model learned after registration. Identity and trust are untouched.
    /// </summary>
    /// <remarks>
    /// Additive to the interface because the alternative — letting a repeat registration merge — is
    /// the path that must NOT work: the first registration's capability has to stand, or an external
    /// id becomes a way to re-mint authority.
    /// </remarks>
    void UpdateHarnessAndModel(
        string sessionId, SessionCapability capability, HarnessIdentity? harness, ModelIdentity? model);

    /// <summary>True only when the presented capability matches the session's current capability.</summary>
    bool Verify(string sessionId, SessionCapability presented);

    /// <summary>Records a heartbeat after verifying the capability. Throws LK-0001 on a bad capability.</summary>
    void Heartbeat(string sessionId, SessionCapability capability);

    /// <summary>Marks a session ended after verifying the capability. Throws LK-0001 on a bad capability.</summary>
    void End(string sessionId, SessionCapability capability);
}

/// <summary>The default in-process registrar. See <see cref="ITrustedRegistrar"/>.</summary>
public sealed class TrustedRegistrar : ITrustedRegistrar
{
    private readonly IWatcherObservationStore _store;
    private readonly ICapabilityFactory _capabilities;
    private readonly IMonotonicClock _clock;
    private readonly Func<string> _newSessionId;
    private readonly object _gate = new();

    // Capabilities live only in memory, keyed by session id - never written to the observation store.
    private readonly Dictionary<string, SessionCapability> _capabilityBySession = new();

    public TrustedRegistrar(
        IWatcherObservationStore store,
        ICapabilityFactory capabilities,
        IMonotonicClock clock,
        Func<string>? newSessionId = null)
    {
        _store = store;
        _capabilities = capabilities;
        _clock = clock;
        _newSessionId = newSessionId ?? (() => Guid.NewGuid().ToString("n"));
    }

    public RegisteredSession Register(SessionBinding binding)
    {
        Validate(binding);
        var sessionId = _newSessionId();
        return Issue(sessionId, new SessionGeneration(1), binding);
    }

    public RegisteredSession RegisterNextGeneration(string sessionId, SessionBinding binding)
    {
        ArgumentException.ThrowIfNullOrEmpty(sessionId);
        Validate(binding);
        var existing = _store.FindSession(sessionId);
        var generation = existing is null ? new SessionGeneration(1) : existing.Generation.Next();
        return Issue(sessionId, generation, binding);
    }

    private RegisteredSession Issue(string sessionId, SessionGeneration generation, SessionBinding binding)
    {
        var capability = _capabilities.Create();
        var record = new SessionRecord(sessionId, generation, binding);
        lock (_gate)
        {
            _capabilityBySession[sessionId] = capability; // replaces any prior generation's capability
        }
        _store.RecordSession(record);
        // A fresh generation starts Alive from now and inherits no prior liveness or ended state.
        _store.ClearEnded(sessionId);
        _store.UpsertHeartbeat(sessionId, _clock.Ticks);
        return new RegisteredSession(record, capability);
    }

    public bool Verify(string sessionId, SessionCapability presented)
    {
        ArgumentNullException.ThrowIfNull(presented);
        SessionCapability? current;
        lock (_gate)
        {
            if (!_capabilityBySession.TryGetValue(sessionId, out current))
            {
                return false;
            }
        }
        return current.Matches(presented);
    }

    public void Heartbeat(string sessionId, SessionCapability capability)
    {
        RequireCapability(sessionId, capability);
        _store.UpsertHeartbeat(sessionId, _clock.Ticks);
    }

    public void End(string sessionId, SessionCapability capability)
    {
        RequireCapability(sessionId, capability);
        _store.MarkEnded(sessionId);
    }

    /// <summary>
    /// Records a harness and/or model learned after registration. Identity and trust are untouched.
    /// </summary>
    /// <remarks>
    /// <para><b>Only these two fields, and deliberately.</b> Repository, worktree, terminal and agent
    /// are established at registration and an update cannot restate them — otherwise a session could
    /// migrate itself into another repository's view after the fact.</para>
    ///
    /// <para><b>Trust never rises.</b> A registration carrying a harness is classified
    /// <c>Verified</c>; one without is <c>Asserted</c>. It would be natural to promote a session
    /// that later supplies its harness, and it is exactly wrong: the coordination log is a local,
    /// forgeable FILE (ADR-0007, and the design doc says so in as many words), so an update arriving
    /// on it is evidence about the harness and not about the trustworthiness of the claim. A session
    /// that registers <c>Asserted</c> stays <c>Asserted</c> with its model filled in.</para>
    ///
    /// <para>Capability-gated like every other post-registration write, so knowing an id is not
    /// enough to edit a session.</para>
    /// </remarks>
    public void UpdateHarnessAndModel(
        string sessionId, SessionCapability capability, HarnessIdentity? harness, ModelIdentity? model)
    {
        RequireCapability(sessionId, capability);

        var existing = _store.FindSession(sessionId);
        if (existing is null || (harness is null && model is null))
        {
            return;
        }

        var binding = existing.Binding with
        {
            Harness = harness ?? existing.Binding.Harness,
            Model = model ?? existing.Binding.Model,
        };

        _store.RecordSession(existing with { Binding = binding });
    }

    private void RequireCapability(string sessionId, SessionCapability capability)
    {
        if (!Verify(sessionId, capability))
        {
            throw new WatcherException(
                WatcherErrorCodes.ForgeryRejected,
                "The presented session capability did not match the session's current capability.");
        }
    }

    private static void Validate(SessionBinding binding)
    {
        ArgumentNullException.ThrowIfNull(binding);
        if (string.IsNullOrWhiteSpace(binding.Repository.CanonicalPath)
            || string.IsNullOrWhiteSpace(binding.Terminal.TerminalId)
            || string.IsNullOrWhiteSpace(binding.Agent.AgentName))
        {
            throw new WatcherException(
                WatcherErrorCodes.InvalidBinding,
                "A registration binding requires a repository path, a terminal id, and an agent name.");
        }
    }
}
