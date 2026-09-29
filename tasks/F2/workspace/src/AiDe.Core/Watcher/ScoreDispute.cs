namespace AiDe.Core.Watcher;

/// <summary>
/// An operator's dispute of a scored episode (spec US-16 / rule 12). It is an <b>append-only fact</b>:
/// raising a dispute NEVER overwrites the prior Scorecard - "a dispute appends a superseding evaluation
/// record; prior scores are not overwritten" (spec rule 12). The episode then reads as <b>Disputed</b>,
/// a first-class state that must stay distinguishable from Scored/Blocked/Not Scored (spec §10).
/// </summary>
/// <remarks>
/// <para>A dispute may target one <see cref="DisputedDimension"/> (the operator contests one dimension's
/// assessment) or the whole score (<c>null</c>). The <see cref="Reason"/> is the operator's own words -
/// non-secret, retained as the audit trail of why a score was contested. Resolution (deterministic
/// evidence or a human disposition producing a new Scorecard version) is a separate, later step; this
/// records the dispute itself, honestly and immutably.</para>
/// </remarks>
public sealed record ScoreDispute(
    string DisputeId,
    string EpisodeId,
    string OperatorId,
    ScoreDimension? DisputedDimension,
    string Reason,
    DateTimeOffset RaisedAt);

/// <summary>
/// The deterministic read over disputes: which episodes are Disputed and how many disputes each carries
/// (spec §10 - Disputed is derived from the append-only dispute facts, never a stored flag, DM7). Pure;
/// folds the store's disputes into an episode-keyed view the Sessions/Leaderboard surfaces consult.
/// </summary>
public sealed class DisputeProjection(IWatcherObservationStore store)
{
    private readonly IWatcherObservationStore _store = store ?? throw new ArgumentNullException(nameof(store));

    /// <summary>Whether an episode has at least one dispute (its derived Disputed state).</summary>
    public bool IsDisputed(string episodeId) => _store.DisputesForEpisode(episodeId).Count > 0;

    /// <summary>The number of disputes raised against an episode (an additive count).</summary>
    public int DisputeCount(string episodeId) => _store.DisputesForEpisode(episodeId).Count;

    /// <summary>The distinct episode ids that carry at least one dispute.</summary>
    public IReadOnlySet<string> DisputedEpisodeIds() =>
        _store.AllDisputes().Select(d => d.EpisodeId).ToHashSet(StringComparer.Ordinal);

    /// <summary>
    /// Whether a session has any disputed episode - the session's derived Disputed state for the Sessions
    /// surface (US-16 "discoverable from the Sessions view"). A session is disputed iff any of its
    /// episodes carries a dispute fact (DM7 - derived, never stored on the session).
    /// </summary>
    public bool IsSessionDisputed(string sessionId)
    {
        var disputed = DisputedEpisodeIds();
        if (disputed.Count == 0)
        {
            return false;
        }

        return _store.EpisodesForSession(sessionId).Any(e => disputed.Contains(e.EpisodeId));
    }
}
