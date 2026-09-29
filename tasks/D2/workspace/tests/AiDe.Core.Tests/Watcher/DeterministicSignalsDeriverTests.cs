using AiDe.Core.Watcher;

namespace AiDe.Core.Tests.Watcher;

/// <summary>
/// LK-SIGNALS-01..07 - the deterministic signals derivation + auto-score (conn-10). The claims: a committed
/// Proof Pack is the one honest verification signal (proof pack -> HasVerificationPath, so the episode
/// scores an honest Partial; no proof pack -> Not-Scored); acceptance stays null (never fabricated to a met
/// outcome, so no floor trips and OutcomeIntegrity renders Not-Recorded); and the host import auto-scores
/// each imported episode, idempotently (a re-run upserts, never duplicates).
/// </summary>
public sealed class DeterministicSignalsDeriverTests
{
    private static readonly DateTimeOffset Opened = DateTimeOffset.UnixEpoch;
    private static readonly DateTimeOffset Closed = DateTimeOffset.UnixEpoch.AddMinutes(10);

    private static WorkEpisode ClosedEpisode(EpisodeOutcome outcome = EpisodeOutcome.Completed)
        => new("ep:al-1", "sess-1", new EpisodeGeneration(1), new Goal("Ship it"),
               new DoneCondition("tests green"), null, Opened, Closed, outcome);

    // ---- deriver honesty ----------------------------------------------------------------------------

    [Fact]
    public void Derive_WithProofPack_SetsTheVerificationPath_ButNeverFabricatesAcceptance()
    {
        var signals = DeterministicSignalsDeriver.Derive(
            ClosedEpisode(), new EpisodeEvidence(HasProofPack: true), new InMemoryWatcherObservationStore());

        Assert.True(signals.HasVerificationPath);
        Assert.True(signals.RequiredVerificationExecuted);
        Assert.Null(signals.AcceptanceCriteriaMet); // unknown from an audit entry - never fabricated to "met"
        Assert.False(signals.RegressionPresent);
        Assert.False(signals.CoverageCalibrated);
    }

    [Fact]
    public void Derive_WithoutProofPack_HasNoVerificationPath()
    {
        var signals = DeterministicSignalsDeriver.Derive(
            ClosedEpisode(), new EpisodeEvidence(HasProofPack: false), new InMemoryWatcherObservationStore());

        Assert.False(signals.HasVerificationPath);
        Assert.False(signals.RequiredVerificationExecuted);
    }

    // ---- honest scoring end to end (through the real WeaveScorer) -----------------------------------

    [Fact]
    public void ProofPackEpisode_ScoresPartial_NotNotScored_AndTripsNoFloor()
    {
        var episode = ClosedEpisode();
        var signals = DeterministicSignalsDeriver.Derive(
            episode, new EpisodeEvidence(HasProofPack: true), new InMemoryWatcherObservationStore());

        var card = new WeaveScorer().Score(episode, signals, new FixedTimeProvider(Closed));

        Assert.Equal(WeaveVerdict.Partial, card.Verdict); // Focus scores; acceptance null -> Outcome Not-Recorded
        Assert.Empty(card.TrippedFloors);                 // acceptance null + verification executed -> no floor
    }

    [Fact]
    public void NoProofPackEpisode_IsNotScored_NotBlocked()
    {
        var episode = ClosedEpisode();
        var signals = DeterministicSignalsDeriver.Derive(
            episode, new EpisodeEvidence(HasProofPack: false), new InMemoryWatcherObservationStore());

        var card = new WeaveScorer().Score(episode, signals, new FixedTimeProvider(Closed));

        Assert.Equal(WeaveVerdict.NotScored, card.Verdict); // "no minimum verification path" - honest
    }

    // ---- richer telemetry signals (t3): explicit signals lift the score, absent stays conservative ---

    [Fact]
    public void Derive_WithExplicitSignals_UsesThem_OverTheConservativeDefaults()
    {
        var full = new AuditSignals(
            VerificationPath: true, VerificationExecuted: true, AcceptanceMet: true, Regression: false,
            GuidanceRequired: 5, GuidanceSatisfied: 5, CoordinationRequired: 2, CoordinationObserved: 2);

        var s = DeterministicSignalsDeriver.Derive(
            ClosedEpisode(), new EpisodeEvidence(HasProofPack: false, Signals: full),
            new InMemoryWatcherObservationStore());

        Assert.True(s.HasVerificationPath);          // explicit signal, even with no proof pack
        Assert.True(s.AcceptanceCriteriaMet);        // explicit acceptance (not the null default)
        Assert.Equal(5, s.RequiredGuidanceTriggers);
        Assert.Equal(2, s.ObservedCoordinationSignals);
        Assert.True(s.CoverageCalibrated);           // explicit required-total -> coverage is real
    }

    [Fact]
    public void FullyInstrumentedEpisode_ScoresEveryDeterministicDimension_NotJustFocus()
    {
        var episode = ClosedEpisode();
        var full = new AuditSignals(
            VerificationPath: true, VerificationExecuted: true, AcceptanceMet: true, Regression: false,
            GuidanceRequired: 5, GuidanceSatisfied: 5, CoordinationRequired: 2, CoordinationObserved: 2);

        var s = DeterministicSignalsDeriver.Derive(
            episode, new EpisodeEvidence(HasProofPack: false, Signals: full), new InMemoryWatcherObservationStore());
        var card = new WeaveScorer().Score(episode, s, new FixedTimeProvider(Closed));

        // All FOUR deterministic dimensions now score (vs Focus-only for a proof-pack-only episode). The
        // verdict stays Partial because the two ADVISORY dimensions still need the evaluator (task 4) - so
        // this is the honest ceiling of deterministic-only scoring, and coverage is now recorded.
        Assert.Equal(WeaveVerdict.Partial, card.Verdict);
        Assert.Empty(card.TrippedFloors);
        Assert.NotNull(card.Coverage);
        Assert.Equal(4, card.Assessments.Count(a => a.EarnedPoints is not null));
    }

    [Fact]
    public void Derive_WithNoSignals_IsUnchanged_Conservative()
    {
        // The honesty invariant: an un-instrumented entry behaves exactly as before (acceptance null,
        // guidance/coordination 0, coverage uncalibrated). Absent signals never fabricate a value.
        var s = DeterministicSignalsDeriver.Derive(
            ClosedEpisode(), new EpisodeEvidence(HasProofPack: true, Signals: null),
            new InMemoryWatcherObservationStore());

        Assert.Null(s.AcceptanceCriteriaMet);
        Assert.Equal(0, s.RequiredGuidanceTriggers);
        Assert.Equal(0, s.RequiredCoordinationSignals);
        Assert.False(s.CoverageCalibrated);
    }

    [Fact]
    public void ParseWithEvidence_ReadsTheOptionalSignalsObject()
    {
        var line = """{"id":"al-x","session":"s","goal":"g","done_when":"d","outcome":"success","artifacts":["docs/proof/x.md"],"signals":{"acceptance_met":true,"guidance_required":3,"guidance_satisfied":2,"coordination_required":2,"coordination_observed":2}}""";

        var imported = Assert.Single(AuditLogEpisodeSource.ParseWithEvidence([line]));

        Assert.NotNull(imported.Evidence.Signals);
        Assert.True(imported.Evidence.Signals!.AcceptanceMet);
        Assert.Equal(3, imported.Evidence.Signals.GuidanceRequired);
        Assert.Null(imported.Evidence.Signals.VerificationPath); // absent field stays null (conservative)
    }

    [Fact]
    public void ParseWithEvidence_NoSignalsObject_LeavesSignalsNull()
    {
        var line = """{"id":"al-y","session":"s","goal":"g","done_when":"d","outcome":"success"}""";

        var imported = Assert.Single(AuditLogEpisodeSource.ParseWithEvidence([line]));

        Assert.Null(imported.Evidence.Signals);
    }

    // ---- host import + auto-score (D4, real SQLite) -------------------------------------------------

    [Fact]
    public void ImportAndScore_ProofPackEntryPartial_NoProofNotScored_ReRunUpserts()
    {
        var data = Path.Combine(Path.GetTempPath(), $"aide-conn10-data-{Guid.NewGuid():N}");
        var coord = Path.Combine(Path.GetTempPath(), $"aide-conn10-coord-{Guid.NewGuid():N}");
        var auditPath = Path.Combine(Path.GetTempPath(), $"aide-conn10-audit-{Guid.NewGuid():N}.jsonl");
        Directory.CreateDirectory(data);
        Directory.CreateDirectory(coord);
        File.WriteAllLines(auditPath,
        [
            """{"id":"al-proof","session":"sess-p","goal":"g","done_when":"d","outcome":"success","artifacts":["src/x.cs","docs/proof/x.md"]}""",
            """{"id":"al-noproof","session":"sess-n","goal":"g","done_when":"d","outcome":"success","artifacts":["src/y.cs"]}""",
        ]);

        try
        {
            using var host = WatcherHost.Open(data, coord);

            var imported = host.ImportAndScoreEpisodesFromAuditLog(auditPath, TestWorkspaces.Repo);
            Assert.Equal(2, imported);

            var scored = host.Store.AllScoredEpisodes();
            Assert.Equal(2, scored.Count);
            Assert.Contains(scored, s => s.EpisodeId == "ep:al-proof" && s.Scorecard.Verdict == WeaveVerdict.Partial);
            Assert.Contains(scored, s => s.EpisodeId == "ep:al-noproof" && s.Scorecard.Verdict == WeaveVerdict.NotScored);

            // operatorId is the session id (the honest grouping key), never a human identity.
            Assert.Equal("sess-p", scored.Single(s => s.EpisodeId == "ep:al-proof").OperatorId);

            // Idempotent: a re-run re-scores, it does not duplicate.
            host.ImportAndScoreEpisodesFromAuditLog(auditPath, TestWorkspaces.Repo);
            Assert.Equal(2, host.Store.AllScoredEpisodes().Count);
        }
        finally
        {
            try { Directory.Delete(data, recursive: true); } catch (IOException) { }
            try { Directory.Delete(coord, recursive: true); } catch (IOException) { }
            try { File.Delete(auditPath); } catch (IOException) { }
        }
    }

    // ---- advisory-evaluator seam (t4): the local on-device judge folds the advisory dims when qualified --

    [Fact]
    public void ImportAndScore_WithAQualifiedLocalEvaluator_FoldsTheAdvisoryDimensions()
    {
        var data = Path.Combine(Path.GetTempPath(), $"aide-t4-data-{Guid.NewGuid():N}");
        var coord = Path.Combine(Path.GetTempPath(), $"aide-t4-coord-{Guid.NewGuid():N}");
        var auditPath = Path.Combine(Path.GetTempPath(), $"aide-t4-audit-{Guid.NewGuid():N}.jsonl");
        Directory.CreateDirectory(data);
        Directory.CreateDirectory(coord);
        // A fully-instrumented success episode with a proof pack and explicit signals.
        File.WriteAllLines(auditPath,
        [
            """{"id":"al-full","session":"s","goal":"g","done_when":"d","outcome":"success","artifacts":["docs/proof/x.md"],"signals":{"verification_path":true,"verification_executed":true,"acceptance_met":true,"guidance_required":3,"guidance_satisfied":3,"coordination_required":2,"coordination_observed":2}}""",
        ]);

        try
        {
            // Deterministic-only (the safe default): the two advisory dimensions stay excluded.
            using (var host = WatcherHost.Open(data, coord))
            {
                host.ImportAndScoreEpisodesFromAuditLog(auditPath, TestWorkspaces.Repo);
                var card = host.Store.AllScoredEpisodes().Single().Scorecard;
                Assert.DoesNotContain(card.Assessments, a =>
                    a.Dimension is ScoreDimension.EvidenceDiscipline or ScoreDimension.SolutionEconomy
                    && a.EarnedPoints is not null);
            }

            // With a QUALIFIED local (on-device, no egress) evaluator supplied, the advisory dims fold.
            using (var host = WatcherHost.Open(data, coord))
            {
                var evaluator = new LocalHeuristicAdvisoryEvaluator();
                var registry = new CalibrationRegistry();
                registry.Qualify(evaluator.EvaluatorVersion, "audit-import", ScoreSchema.Weave1.Version);

                host.ImportAndScoreEpisodesFromAuditLog(auditPath, TestWorkspaces.Repo, "audit-import", evaluator, registry);

                var card = host.Store.AllScoredEpisodes().Single().Scorecard;
                Assert.Contains(card.Assessments, a =>
                    a.Dimension is ScoreDimension.EvidenceDiscipline or ScoreDimension.SolutionEconomy
                    && a.EarnedPoints is not null); // the seam threaded the evaluator through -> folded
            }
        }
        finally
        {
            try { Directory.Delete(data, recursive: true); } catch (IOException) { }
            try { Directory.Delete(coord, recursive: true); } catch (IOException) { }
            try { File.Delete(auditPath); } catch (IOException) { }
        }
    }
}
