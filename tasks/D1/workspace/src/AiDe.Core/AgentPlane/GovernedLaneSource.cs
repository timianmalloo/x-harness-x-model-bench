using AiDe.Core.Watcher;

namespace AiDe.Core.AgentPlane;

/// <summary>
/// Who a governed lane is, in the terms the watcher's registration already speaks.
/// </summary>
/// <remarks>
/// <b><see cref="LaneId"/> is registered as the terminal id.</b> A governed lane has no ConPTY, but
/// the terminal id is the watcher's key for "the host surface this session lives in", and for a
/// governed lane the lane <i>is</i> that surface. It also buys the behaviour a lane wants: the
/// ingest host adopts an existing session for a known terminal id and bumps its generation, so a
/// respawned lane continues its own history instead of minting a second session.
/// </remarks>
/// <param name="LaneId">The lane's stable identity — see the remarks.</param>
/// <param name="AgentName">What this lane is, for a person reading the fleet map.</param>
/// <param name="RepositoryPath">The repository the work belongs to — the parent checkout, not the tree.</param>
/// <param name="RepositoryDisplay">Its display name.</param>
/// <param name="WorktreeBranch">The provisioned branch.</param>
/// <param name="WorktreePath">The provisioned tree.</param>
/// <param name="Harness">The engine, when known.</param>
/// <param name="Model">The model, when known. A standings cohort axis.</param>
public sealed record LaneIdentity(
    string LaneId,
    string AgentName,
    string RepositoryPath,
    string RepositoryDisplay,
    string WorktreeBranch,
    string WorktreePath,
    string? Harness = null,
    string? Model = null);

/// <summary>
/// Opens governed episodes on the live ingest path — spec §6.2's <c>GovernedSessionSource</c>,
/// renamed <c>GovernedLaneSource</c> by Ruling 15 (A3): see <c>note-conductor-spec-errata-lane-rename</c>.
/// </summary>
/// <remarks>
/// <para><b>No new seam.</b> Registration, episode open, artifact declaration and close all go
/// through <see cref="IngestHost"/> and are capability-verified by <c>ITrustedRegistrar</c>, exactly
/// as <c>InjectedContractIngest</c> does for a session that declares its own episodes. An
/// episode-source interface was declined by ruling until a third implementer exists — the name is
/// left unwritten deliberately, because a doc comment that cites a type nobody declared reads as a
/// guarantee (DC-095); two implementations are not evidence of a shape, and the interface would
/// have to be guessed from one of them.</para>
///
/// <para><b>The difference from the observed door is authorship, not mechanism</b> (§6.1). An
/// observed session <i>declares</i> its episode over the coordination log and could in principle
/// declare anything; a governed lane's episode is opened here, by the runtime, from the goal block
/// that was a precondition of the spawn. The capability never leaves this object, so the lane cannot
/// forge an open, a close or an outcome.</para>
/// </remarks>
public sealed class GovernedLaneSource
{
    private readonly IngestHost _host;

    public GovernedLaneSource(IngestHost host)
    {
        ArgumentNullException.ThrowIfNull(host);
        _host = host;
    }

    /// <summary>
    /// Registers the lane's session and opens its episode from the goal block.
    /// </summary>
    /// <remarks>
    /// <para><b>Validated before anything is created.</b> R2 is "no block, no spawn": an incomplete
    /// block leaves no session and no episode behind, so a rejected spawn is not visible in the store
    /// as a lane that never did anything.</para>
    ///
    /// <para><b>The attributes are the block's strings, untouched.</b> Nothing is trimmed,
    /// normalized or re-encoded on the way through — the episode is what the agent is later scored
    /// against, and a helpful transformation here would score it against a goal nobody wrote.</para>
    /// </remarks>
    /// <exception cref="AgentPlaneException">
    /// <see cref="AgentPlaneErrorCodes.GoalBlockIncomplete"/>, naming every missing field.
    /// </exception>
    public GovernedEpisode Open(LaneIdentity identity, GoalBlock block)
    {
        ArgumentNullException.ThrowIfNull(identity);

        var errors = SpawnContract.Validate(block);
        if (errors.Count > 0)
        {
            throw new AgentPlaneException(
                AgentPlaneErrorCodes.GoalBlockIncomplete,
                "a governed episode cannot open on an incomplete goal block — "
                + string.Join("; ", errors.Select(e => e.Message)));
        }

        var attributes = new Dictionary<string, string?>(StringComparer.Ordinal)
        {
            [CoordContract.EpisodeAttributes.Goal] = block.Goal,
            [CoordContract.EpisodeAttributes.DoneWhen] = block.DoneWhen,
            [CoordContract.EpisodeAttributes.NotInScope] = block.NotInScope,
        };

        var session = _host.Register(new HarnessRegistration(Registration(identity)));

        var episode = _host.OpenEpisode(
            session.SessionId,
            session.Capability,
            new Goal(attributes[CoordContract.EpisodeAttributes.Goal]!),
            new DoneCondition(attributes[CoordContract.EpisodeAttributes.DoneWhen]!),
            attributes[CoordContract.EpisodeAttributes.NotInScope]);

        return new GovernedEpisode(_host, session, episode.EpisodeId, attributes);
    }

    private static Dictionary<string, string?> Registration(LaneIdentity identity)
    {
        var attributes = new Dictionary<string, string?>(StringComparer.Ordinal)
        {
            [OtelAttributes.RepoPath] = identity.RepositoryPath,
            [OtelAttributes.RepoDisplay] = identity.RepositoryDisplay,
            [OtelAttributes.WorktreeBranch] = identity.WorktreeBranch,
            [OtelAttributes.WorktreePath] = identity.WorktreePath,
            [OtelAttributes.TerminalId] = identity.LaneId,
            [OtelAttributes.AgentName] = identity.AgentName,
        };

        // Absent, not blank, when unknown — the mapper reads an absent harness/model as Not Recorded,
        // and a blank one would render as a name that is the empty string.
        if (identity.Harness is not null)
        {
            attributes[OtelAttributes.ServiceName] = identity.Harness;
        }

        if (identity.Model is not null)
        {
            attributes[OtelAttributes.GenAiModel] = identity.Model;
        }

        return attributes;
    }
}

/// <summary>One open governed episode, and the only object that can close it.</summary>
/// <remarks>
/// Renamed from <c>GovernedSession</c> by Ruling 15 (A3) / Ruling 15a — the target
/// <c>GovernedLane</c> is not available (see <see cref="GovernedLane"/> below, an unrelated
/// pre-existing composite of the same name); see <c>note-addendum-a-ruling-15a-governed-episode</c>.
/// </remarks>
public sealed class GovernedEpisode
{
    private readonly IngestHost _host;
    private readonly RegisteredSession _session;

    internal GovernedEpisode(
        IngestHost host, RegisteredSession session, string episodeId, IReadOnlyDictionary<string, string?> openAttributes)
    {
        _host = host;
        _session = session;
        EpisodeId = episodeId;
        OpenAttributes = openAttributes;
    }

    /// <summary>
    /// The watcher session this lane registered as.
    /// </summary>
    /// <remarks>
    /// <b>Boundary note (Ruling 15 / A3).</b> This "session" is <see cref="IngestHost"/>'s sense of
    /// the word, not this type's: a registered identity carrying a <c>SessionCapability</c>, verified
    /// by <c>ITrustedRegistrar</c>, that <see cref="IngestHost.OpenEpisode"/> binds an episode to
    /// (backed by the <c>agent_session_dim</c> table). It is the Watcher's lane-identity vocabulary
    /// and migrates to "lane" only opportunistically — A3 forbids a big-bang rename, so it stays
    /// session-named here even though this type is now <see cref="GovernedEpisode"/>.
    /// </remarks>
    public string SessionId => _session.SessionId;

    /// <summary>The episode the goal block opened.</summary>
    public string EpisodeId { get; }

    /// <summary>
    /// The attributes the episode opened with, exactly as sent.
    /// </summary>
    /// <remarks>
    /// Exposed so the equality to the goal block is checkable from outside — an invariant only the
    /// implementation can see is one only the implementation can be wrong about.
    /// </remarks>
    public IReadOnlyDictionary<string, string?> OpenAttributes { get; }

    /// <summary>Records the evidence paths this lane names. Declared, never verified here.</summary>
    public int DeclareArtifacts(IReadOnlyList<string> paths)
        => _host.DeclareEpisodeArtifacts(EpisodeId, _session.Capability, paths);

    /// <summary>Closes the episode with its outcome. The declaration is not a quality judgement.</summary>
    public WorkEpisode Close(EpisodeOutcome outcome)
        => _host.CloseEpisode(EpisodeId, _session.Capability, outcome);
}

/// <summary>What a lane teardown did: to the episode, and to the tree.</summary>
/// <param name="Outcome">The outcome the episode closed with.</param>
/// <param name="Worktree">What happened to the tree, or <c>null</c> when the lane had none.</param>
public sealed record LaneTeardown(EpisodeOutcome Outcome, WorktreeDisposition? Worktree);

/// <summary>
/// One governed lane's episode and worktree, torn down together.
/// </summary>
/// <remarks>
/// <b>The composition is the point.</b> Spec R1 requires that killing the engine both closes the
/// episode <c>Blocked</c> and parks a dirty tree; each half is already correct in its own type, and
/// the failure worth preventing is doing one and not the other — an episode left open reads as a
/// lane still working, and a deleted tree destroys the only record of what the lane had written when
/// it died.
/// </remarks>
public sealed class GovernedLane
{
    private readonly GovernedEpisode _session;
    private readonly WorktreeProvisioner _provisioner;
    private readonly ProvisionedWorktree? _worktree;
    private readonly LeaseMonitor? _seams;

    /// <param name="session">The lane's open episode.</param>
    /// <param name="provisioner">Who releases the tree.</param>
    /// <param name="worktree">The tree, or <c>null</c> when the lane had none.</param>
    /// <param name="seams">
    /// The lane's lease monitor, when it declared a lease. <c>null</c> means no lease was declared —
    /// not "no seams found": a lane with no declared scope has nothing to be outside of, and an
    /// empty <see cref="Lease"/> is refused rather than read as either extreme.
    /// </param>
    public GovernedLane(
        GovernedEpisode session,
        WorktreeProvisioner provisioner,
        ProvisionedWorktree? worktree,
        LeaseMonitor? seams = null)
    {
        ArgumentNullException.ThrowIfNull(session);
        ArgumentNullException.ThrowIfNull(provisioner);
        _session = session;
        _provisioner = provisioner;
        _worktree = worktree;
        _seams = seams;
    }

    /// <summary>
    /// The engine process died or was killed: close <c>Blocked</c>, and park the tree whatever it holds.
    /// </summary>
    /// <remarks>
    /// <para><b><c>Blocked</c>, not <c>Abandoned</c>.</b> Abandonment is a declaration somebody makes;
    /// a kill is something that happened to the lane. Recording it as an abandonment would attribute
    /// a decision to an agent that had none.</para>
    ///
    /// <para><b>Parked even when clean.</b> Removal is offered only for a lane that ended merged or
    /// explicitly abandoned, and a killed engine is neither — so this path never asks for one.</para>
    /// </remarks>
    public LaneTeardown EngineKilled(WorktreeState state)
        => Close(EpisodeOutcome.Blocked, LaneClosure.Unresolved, state, removeWorktreeWhenSafe: false);

    /// <summary>
    /// Closes the episode and releases the tree under the fail-safe rule.
    /// </summary>
    /// <remarks>
    /// <b>An open seam forces <c>Blocked</c>, whatever the lane declared</b> (spec R4 and §8.2:
    /// <c>seam_resolution_ratio</c> must be 1.0 before the final close). The outcome is overridden
    /// rather than the close refused: a refusal would leave the episode open, which reads as a lane
    /// still working — the state R1 already decided is the wrong one to leave behind. The override
    /// happens here, at the one place a governed episode closes, so there is no second path that
    /// closes without asking.
    /// </remarks>
    public LaneTeardown Close(
        EpisodeOutcome outcome, LaneClosure closure, WorktreeState state, bool removeWorktreeWhenSafe)
    {
        var forced = _seams is { MayCloseCleanly: false } ? EpisodeOutcome.Blocked : outcome;

        // The episode first: it is the durable record, and a tree that fails to release leaves a
        // reportable directory, while an episode that fails to close leaves work that scores nowhere.
        var episode = _session.Close(forced);

        var disposition = _worktree is null
            ? null
            : _provisioner.Release(_worktree, closure, state, removeWorktreeWhenSafe);

        return new LaneTeardown(episode.Outcome ?? forced, disposition);
    }
}
