namespace AiDe.Core.Watcher;

/// <summary>
/// Turns a contract-closed Work Episode into a scored one - the link the agent collaboration loop was
/// missing (US-16).
/// </summary>
/// <remarks>
/// <para><b>The break this closes.</b> An agent registers through the coordination contract, declares
/// an episode, and closes it; every one of those steps worked and was tested at its seam. Scoring had
/// exactly one producer - <c>WatcherHost.ImportAndScoreEpisodesFromAuditLog</c> - which reads AI-DE's
/// own audit log, and takes its session id from the log's <c>session</c> field while
/// <see cref="TrustedRegistrar"/> mints a fresh one. The two identifier spaces could never meet, so a
/// registered agent produced a closed episode, no scorecard, and therefore no standing, forever. No
/// seam test could show that; only a test that walks the whole chain.</para>
///
/// <para><b>Why a pass and not a hook on close.</b> Closing an episode is a <i>declaration</i>;
/// scoring it is a <i>judgement</i>. Coupling them would make the agent's own <c>episode-close</c>
/// line the thing that produced its score, and the two would fail together. An idempotent sweep over
/// closed-but-unscored is the shape every other watcher pass already has, so re-running it is free.</para>
///
/// <para><b>Registered sessions only</b>, which keeps the two scoring producers disjoint: an
/// audit-imported episode has no <see cref="SessionRecord"/>, so this never re-scores one under a
/// different task class and the upsert can never flip-flop between the two.</para>
///
/// <para><b>A pure function of the store</b>, deliberately: the host has a database, a pump and a
/// receiver, and none of them are involved in deciding whether an episode should be scored.</para>
/// </remarks>
public static class ClosedEpisodeScoring
{
    /// <summary>
    /// Scores every closed episode of a registered session that has no scorecard, and returns the
    /// number newly scored.
    /// </summary>
    /// <remarks>
    /// <para><b>The evidence is observed, and honestly empty when it is empty.</b> This paragraph
    /// used to say <c>HasProofPack: false</c> was built here as a literal; that stopped being true
    /// when <see cref="EvidenceFor"/> landed and started asking the store what the agent declared,
    /// and a stale doc comment describing the defect a method no longer has is how DC-115 survived
    /// one layer up. What is still true is the shape of the answer for an episode that declares
    /// nothing: <see cref="DeterministicSignalsDeriver"/>'s conservative defaults apply - no
    /// verification path, acceptance unknown, requirements zero - and what falls out is <b>Not
    /// Scored, with the reason</b>, which is the honest first thing an agent can receive.</para>
    ///
    /// <para>It is emphatically <b>not a low score</b>. A derived-signals path that returned 0 for
    /// "nothing was observed" would be a statement about the agent where only a statement about the
    /// evidence is warranted, and it would be indistinguishable from a real failure.</para>
    ///
    /// <para><b>Another component depends on this refusal, and the damage would start HERE.</b>
    /// <see cref="DaydreamObservationOutcome"/> distinguishes "nothing went wrong" from "nothing was
    /// assessed", and that distinction rests entirely on this path not fabricating a floor or a
    /// rubric it did not observe. Relax the honesty above - default a rubric to zero, trip a
    /// verification floor because none was seen - and the signature stops being unremarkable, the
    /// recorder stops being able to tell a clean episode from an unassessed one, and a permanently
    /// deaf Daydream reports as a healthy repository. Nothing in that component would change and
    /// nothing there would fail.</para>
    ///
    /// <para>Found by mutation across the boundary rather than by reading either side: making an
    /// unevidenced episode trip a floor reddens this repository's Daydream tests as well as the
    /// scoring ones. Recorded here rather than only there, because the person who would cause it is
    /// editing this file.</para>
    ///
    /// <para><b>The task class is absent, not invented.</b> The coordination contract carries a goal
    /// and a done-condition but no task class, so the segment is
    /// <see cref="ScoreSegment.Unclassified"/> and therefore not comparable: the episode is scored
    /// and delivered, and ranks nowhere. Supplying a placeholder class to make a leaderboard row
    /// appear would put a value on a surface that reads as meaning something.</para>
    /// </remarks>
    public static int Run(
        IWatcherObservationStore store,
        TimeProvider time,
        string taskClass = ScoreSegment.Unclassified,
        IAdvisoryEvaluator? evaluator = null,
        CalibrationRegistry? registry = null,
        DaydreamRecorder? daydream = null,
        IRepositoryLocator? locator = null)
    {
        ArgumentNullException.ThrowIfNull(store);
        ArgumentNullException.ThrowIfNull(time);
        ArgumentException.ThrowIfNullOrEmpty(taskClass);

        // Defaulted rather than required, for the same reason IngestHost defaults its own: no
        // existing call site has an opinion about it. Injectable so a caller that cannot see the
        // registrant's filesystem can supply one that always answers "unknown" — which costs that
        // caller nothing, because an unadmitted worktree just leaves the repository root.
        var checkouts = locator ?? new FileSystemRepositoryLocator();

        var scoring = new ScoringService(store, time, daydream);
        var scored = 0;

        foreach (var episode in store.AllEpisodes())
        {
            if (episode.State is not EpisodeState.Closed || store.FindScoredEpisode(episode.EpisodeId) is not null)
            {
                continue;
            }

            // No session record means an audit-imported episode, which the import path owns.
            if (store.FindSession(episode.SessionId) is not { } session)
            {
                continue;
            }

            var signals = DeterministicSignalsDeriver.Derive(
                episode, EvidenceFor(episode, session, store, checkouts), store);

            scoring.ScoreAndRecord(
                episode,
                signals,
                operatorId: episode.SessionId,
                taskClass: taskClass,
                workspace: WorkspaceKey.From(session.Binding.Repository),
                harness: session.Binding.Harness?.Name,
                model: session.Binding.Model?.Name,
                evaluator: evaluator,
                registry: registry);

            scored++;
        }

        return scored;
    }

    /// <summary>
    /// What the product could actually observe about this episode's evidence.
    /// </summary>
    /// <remarks>
    /// <para><b>This replaced a hardcoded <c>HasProofPack: false</c></b>, which asserted an absence
    /// without looking. That literal collapsed two states wanting opposite responses: <i>we looked
    /// and there was none</i>, a fact about the episode, and <i>there was nowhere to look</i>, a fact
    /// about the product. It was always the second, spelled as the first — a scorecard making a
    /// statement about the agent when the true statement was about a missing channel.</para>
    ///
    /// <para><b>Now it looks.</b> The agent declares paths on <c>episode-close</c>, the store keeps
    /// them verbatim and unverified, and <see cref="ProofPackVerifier"/> decides which are real. The
    /// agent names a file and the product checks whether the file is there, so it cannot make the
    /// check pass by asserting harder — which is what makes declared evidence admissible where a
    /// self-reported <c>acceptance_met</c> stays refused.</para>
    ///
    /// <para><b>A failed path never makes the episode unscoreable.</b> A declaration that does not
    /// verify means the evidence was not there — a fact about the evidence. Treating it as a
    /// malformed line would make a moved file look like a protocol error, which is a claim about the
    /// agent's formatting instead, and a worse one because it is wrong.</para>
    ///
    /// <para><b>The Unverifiable case is the one to watch.</b> When the repository is not reachable
    /// from here, no verdict is possible, and <c>HasProofPack</c> is false because the type has no
    /// third state — so the collapse the tri-state exists to prevent is reintroduced AT THIS
    /// BOUNDARY, deliberately and visibly rather than silently. It is honest today only because a
    /// registered session's repository is a local path this process just read; the day a remote
    /// registrant appears, this is the line that starts lying and
    /// <c>AnUnverifiableRepositoryIsNotEvidenceOfAbsence</c> is the test that says so.</para>
    /// </remarks>
    private static EpisodeEvidence EvidenceFor(
        WorkEpisode episode, SessionRecord session, IWatcherObservationStore store, IRepositoryLocator locator)
    {
        var checkouts = CheckoutsOf(session.Binding, locator);

        var verified = store.DeclaredArtifactsFor(episode.EpisodeId)
            .Any(a => ProofPackVerifier.VerifyInCheckouts(checkouts, a.Path) is ProofPackVerdict.Verified);

        return new EpisodeEvidence(HasProofPack: verified);
    }

    /// <summary>
    /// The working trees this session's evidence could honestly be in (DC-115).
    /// </summary>
    /// <remarks>
    /// <para><b>A canonical identity is not a path.</b> <c>Repository.CanonicalPath</c> is normalised
    /// so that every worktree of one repository groups into one cohort — right for the fleet map, the
    /// board partition and the leaderboard cell, and wrong the moment it is handed to
    /// <c>File.Exists</c>, because it then names the PARENT checkout: a different working tree, on a
    /// different branch, which does not contain what the lane committed on its own. The episode
    /// scored <c>Not Scored — no minimum verification path</c> while the path existed, was committed
    /// and was named. Every layer was individually correct and the composed claim was false.</para>
    ///
    /// <para><b>The second checkout is OBSERVED, never claimed.</b> <c>worktree.path</c> is composed
    /// by the registrant like every other registration attribute, so admitting it on the claim alone
    /// would let a session keep an honest <c>repo.path</c> — board and cohort looking right — while
    /// pointing evidence verification at any directory on the machine. It is admitted only when the
    /// locator reads its <c>.git</c> pointer and finds the repository the session is bound to: the
    /// same filesystem fact <see cref="RepositoryCorrection"/> already resolves, so the two agree by
    /// construction rather than by coincidence.</para>
    ///
    /// <para><b>A session that is not in a worktree is unaffected, exactly.</b> A repository root's
    /// <c>.git</c> is a directory, so the locator answers null and the list is the single root this
    /// method always returned — the same one call, on the same path, with the same verdict.</para>
    ///
    /// <para><b>What this still does not reach:</b> a lane whose tree was released before the sweep
    /// ran. The branch keeps the commit but the working tree is gone, so there is nothing to read and
    /// the verdict falls back to the parent checkout's honest <c>NotFound</c>. Asking git for the
    /// blob would cover it and is not done here: Core does not shell out, and a process launch per
    /// declared artifact on a sweep is a cost per episode forever. DC-115 records the residue.</para>
    /// </remarks>
    private static IReadOnlyList<string?> CheckoutsOf(SessionBinding binding, IRepositoryLocator locator)
    {
        var repository = binding.Repository.CanonicalPath;
        var worktree = binding.Worktree.Path;

        if (string.IsNullOrWhiteSpace(worktree))
        {
            return [repository];
        }

        var owner = locator.RepositoryFor(worktree);

        var belongs = owner is not null
            && string.Equals(RepositoryIdentity.Canonicalise(owner), repository, StringComparison.Ordinal);

        return belongs ? [worktree, repository] : [repository];
    }
}
