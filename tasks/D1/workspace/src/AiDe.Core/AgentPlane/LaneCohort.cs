using AiDe.Core.Watcher;

namespace AiDe.Core.AgentPlane;

/// <summary>
/// Which door an episode came through — spec §6.1's two coordination modes.
/// </summary>
/// <remarks>
/// <para><b>A cohort attribute, never a partition axis.</b> The partition is
/// <see cref="ScoreSegment"/> and a comparison never crosses it; the mode lives beside the segment so
/// <b>one cell holds both cohorts</b>, which is exactly what R4 requires and what a fourth segment
/// axis would prevent.</para>
///
/// <para><b>Constants rather than three literals.</b> The strings were spelled out at the store, in
/// its tests, and would have been spelled again at each door. Two definitions of one quantity is a
/// defect signature (DM7), and the failure it produces here is invisible: an episode stamped
/// <c>"Governed"</c> is a third cohort of one, and the cell still renders.</para>
///
/// <para><b>Absent is "not recorded", never a default.</b> There is no member for an unknown mode —
/// the store answers <c>null</c>, which is what every row written before the column existed means.
/// </para>
/// </remarks>
public static class LaneMode
{
    /// <summary>An ACP lane the plane drove: the runtime opened and closed the episode.</summary>
    public const string Governed = "governed";

    /// <summary>A CLI lane the watcher watched: the session declared its own episode.</summary>
    public const string Observed = "observed";
}

/// <summary>
/// The two scoring doors, each stamping the cohort it came through — spec R4.
/// </summary>
/// <remarks>
/// <para><b>Neither path is new machinery.</b> The governed door is
/// <see cref="ClosedEpisodeScoring"/> over a registered session; the observed door is
/// <see cref="WatcherHost.ImportAndScoreEpisodesFromAuditLog"/>. Both run the <b>unchanged</b>
/// <see cref="ScoringService"/>. What this type adds is the two things a caller must not be able to
/// forget: naming the task class, and stamping which door it was.</para>
///
/// <para><b><c>taskClass</c> has no default here, deliberately.</b> Both underlying paths carry one —
/// <c>"audit-import"</c> and <see cref="ScoreSegment.Unclassified"/> — and only the second is
/// incomparable. An episode that acquires <c>"audit-import"</c> by default therefore does <b>not</b>
/// surface as unranked (<see cref="ScoreSegment.IncomparableReason"/> never fires for it); it ranks
/// silently inside a cohort whose name is an implementation detail of an import routine. A required
/// parameter is the only version of this that cannot be forgotten.</para>
/// </remarks>
public static class LaneScoring
{
    /// <summary>
    /// The task class <see cref="WatcherHost.ImportAndScoreEpisodesFromAuditLog"/> applies when the
    /// caller names none — <b>comparable</b>, and therefore the dangerous one.
    /// </summary>
    /// <remarks>
    /// Named as a constant so a test can assert a stored class is not this, rather than describe it.
    /// Retiring the default is owed to Phase 3 (§8.4 controlled task classes); until then this is the
    /// value that must never appear on a cell somebody chose the class for.
    /// </remarks>
    public const string AuditImportDefaultClass = "audit-import";

    /// <summary>
    /// Scores a governed lane's closed episode under the caller's task class and stamps its cohort.
    /// </summary>
    /// <remarks>
    /// <b>Score, then stamp.</b> <see cref="IWatcherObservationStore.RecordEpisodeMode"/> is an
    /// update over an already-scored cell, so stamping first would silently record nothing — and the
    /// episode would rank in the right cell with no cohort, which reads as a pre-migration row.
    /// </remarks>
    /// <param name="taskClass">The kind of work. Required — see the type's remarks.</param>
    /// <exception cref="AgentPlaneException">
    /// <see cref="AgentPlaneErrorCodes.GovernedEpisodeNotScored"/> when the sweep produced no
    /// scorecard for this episode — which means it was not closed, or its session was not registered,
    /// and a lane whose work scores nowhere is a failure to report rather than absorb.
    /// </exception>
    public static ScoredEpisode ScoreGoverned(
        IWatcherObservationStore store,
        TimeProvider time,
        string episodeId,
        string taskClass,
        IAdvisoryEvaluator? evaluator = null,
        CalibrationRegistry? registry = null,
        DaydreamRecorder? daydream = null)
    {
        ArgumentNullException.ThrowIfNull(store);
        ArgumentNullException.ThrowIfNull(time);
        ArgumentException.ThrowIfNullOrWhiteSpace(episodeId);
        ArgumentException.ThrowIfNullOrWhiteSpace(taskClass);

        ClosedEpisodeScoring.Run(store, time, taskClass, evaluator, registry, daydream);

        var scored = store.FindScoredEpisode(episodeId)
            ?? throw new AgentPlaneException(
                AgentPlaneErrorCodes.GovernedEpisodeNotScored,
                $"episode '{episodeId}' has no scorecard after the closed-episode sweep, so it belongs to no "
                + "cohort; a governed lane whose work scores nowhere is not a lane that did nothing");

        store.RecordEpisodeMode(episodeId, LaneMode.Governed);
        return scored;
    }

    /// <summary>
    /// Imports and scores a repository's observed (audit-declared) episodes under the caller's task
    /// class, and stamps each one's cohort. Returns the episode ids stamped.
    /// </summary>
    /// <remarks>
    /// <b>The source is read again for the ids.</b> The import returns a count, and the cohort stamp
    /// needs identities. Re-parsing the same file is the cost of leaving
    /// <see cref="WatcherHost"/>'s contract alone: R4-core is that the watcher gains callers, not
    /// semantics, and widening a return type to serve one caller is a semantic change.
    /// </remarks>
    /// <param name="taskClass">The kind of work. Required — see the type's remarks.</param>
    public static IReadOnlyList<string> ImportObserved(
        WatcherHost host,
        string auditLogPath,
        WorkspaceKey? workspace,
        string taskClass,
        IAdvisoryEvaluator? evaluator = null,
        CalibrationRegistry? registry = null,
        DaydreamRecorder? daydream = null)
    {
        ArgumentNullException.ThrowIfNull(host);
        ArgumentException.ThrowIfNullOrWhiteSpace(auditLogPath);
        ArgumentException.ThrowIfNullOrWhiteSpace(taskClass);

        host.ImportAndScoreEpisodesFromAuditLog(auditLogPath, workspace, taskClass, evaluator, registry, daydream);

        var stamped = new List<string>();
        foreach (var episode in AuditLogEpisodeSource.ReadFile(auditLogPath))
        {
            // False means there was no scored cell to stamp. Left out of the result rather than
            // reported as stamped: the caller's count is then the count of episodes that really
            // carry a cohort, which is the number a cell comparison depends on.
            if (host.Store.RecordEpisodeMode(episode.EpisodeId, LaneMode.Observed))
            {
                stamped.Add(episode.EpisodeId);
            }
        }

        return stamped;
    }
}
