using AiDe.Core.Watcher;

namespace AiDe.Core.Tests.Watcher;

/// <summary>
/// D3 — the promotion staircase. Every landing that can stop the climb (spec US-9).
/// </summary>
/// <remarks>
/// <para>US-9 has five acceptance criteria and each maps to a test here, named for the refusal
/// rather than for the feature. Four of the five are things the system must <b>decline</b> to do,
/// which is the shape of the whole slice: the value of a learning pipeline is in what it refuses to
/// promote.</para>
///
/// <para><b>Promotion is unreachable, not refused.</b> There is no method that validates and throws.
/// A <c>Promoted</c> event against a candidate that is not Promotable simply does not move it, so an
/// event written by any path — including a hand-edited store — cannot promote something
/// unpromotable.</para>
/// </remarks>
public sealed class DaydreamCandidateTests
{
    private static readonly DaydreamSignature Pattern = new(
        "implement", ScoreSchema.Weave1Version, WeaveVerdict.Blocked, "Correctness", "OutcomeIntegrity:1");

    private static DaydreamObservation Seen(string episodeId, int minute = 0) =>
        new("obs-" + episodeId, Pattern, episodeId, DateTimeOffset.UnixEpoch.AddMinutes(minute));

    private static IReadOnlyList<DaydreamObservation> SeenTwice() => [Seen("ep-1"), Seen("ep-2", 1)];

    private static long _seq;

    private static DaydreamEvent Event(
        DaydreamEventKind kind, string actor = "operator", string? detail = null,
        DisconfirmingOutcome? outcome = null) =>
        new("evt-" + ++_seq, Pattern, kind, actor, detail, outcome,
            DateTimeOffset.UnixEpoch.AddMinutes(_seq), _seq);

    /// <summary>Attaches every authored part, so only the check outcome remains.</summary>
    private static DaydreamEvent[] FullyEvidenced() =>
    [
        Event(DaydreamEventKind.EvidenceAttached, detail: "counter:two episodes went the other way"),
        Event(DaydreamEventKind.EvidenceAttached, detail: "effect:fewer unrun verifications"),
        Event(DaydreamEventKind.EvidenceAttached, detail: "check:re-run the fixture with the guard removed"),
    ];

    private static DaydreamCandidate Only(
        IEnumerable<DaydreamObservation> observations, params DaydreamEvent[] events) =>
        Assert.Single(new DaydreamFold().Fold(observations, events));

    // ---------------------------------------------------------------- criterion 1

    /// <summary>One unverified occurrence stays an Observation and is not generalised.</summary>
    /// <remarks>
    /// US-9's first criterion, and the rule most likely to be quietly relaxed under pressure to show
    /// the feature doing something.
    /// </remarks>
    [Fact]
    public void OneOccurrenceStaysAnObservation()
    {
        Assert.Empty(new DaydreamFold().Fold([Seen("ep-1")], []));
    }

    [Fact]
    public void RepeatedEvidenceProposesACandidateWithItsSources()
    {
        var candidate = Only(SeenTwice());

        Assert.Equal(DaydreamState.NeedsDisconfirm, candidate.State);
        Assert.Equal(["ep-1", "ep-2"], candidate.Evidence.SourceEpisodes);
        Assert.False(candidate.CanPromote);
    }

    // ---------------------------------------------------------------- criterion 3

    /// <summary>
    /// Promotion is blocked while any authored part is missing, and the block names which.
    /// </summary>
    /// <remarks>
    /// US-9's third criterion. The reason is asserted, not just the refusal: "promotion is disabled"
    /// with no explanation is the empty state that DC-087 registered — a surface stating a cause it
    /// never checked. Here the cause is the check.
    /// </remarks>
    [Theory]
    [InlineData(0, "counter-evidence")]
    [InlineData(1, "expected effect")]
    [InlineData(2, "disconfirming check")]
    public void PromotionIsBlockedUntilEveryAuthoredPartIsPresent(int provided, string missing)
    {
        var candidate = Only(SeenTwice(), [.. FullyEvidenced().Take(provided)]);

        Assert.Equal(DaydreamState.NeedsDisconfirm, candidate.State);
        Assert.False(candidate.CanPromote);
        Assert.Contains(missing, candidate.BlockedBecause);
    }

    /// <summary>An attached check that has not been run is not a completed check.</summary>
    [Fact]
    public void AnUnrunCheckDoesNotMakeACandidatePromotable()
    {
        var candidate = Only(SeenTwice(), FullyEvidenced());

        Assert.Equal(DaydreamState.NeedsDisconfirm, candidate.State);
        Assert.Contains("has not been run", candidate.BlockedBecause);
    }

    /// <summary>
    /// A promote event against a candidate that is not promotable does nothing.
    /// </summary>
    /// <remarks>
    /// The human gate cannot be skipped by writing the event that follows it. This is why the guard
    /// lives in the transition rather than in a method: any writer reaching the store — a future
    /// surface, an import, a hand edit — meets the same refusal.
    /// </remarks>
    [Fact]
    public void PromotingAnUnpromotableCandidateDoesNotPromoteIt()
    {
        var candidate = Only(SeenTwice(), Event(DaydreamEventKind.Promoted));

        Assert.NotEqual(DaydreamState.Promoted, candidate.State);
        Assert.Equal(DaydreamState.NeedsDisconfirm, candidate.State);
    }

    // ---------------------------------------------------------------- criterion 4

    /// <summary>A completed check that refutes the candidate marks it Disconfirmed and blocks it.</summary>
    [Fact]
    public void ARefutedCheckDisconfirmsAndBlocks()
    {
        var candidate = Only(SeenTwice(),
            [.. FullyEvidenced(), Event(DaydreamEventKind.CheckCompleted, outcome: DisconfirmingOutcome.Refuted)]);

        Assert.Equal(DaydreamState.Disconfirmed, candidate.State);
        Assert.False(candidate.CanPromote);
        Assert.Contains("refuted", candidate.BlockedBecause);
    }

    /// <summary>A disconfirmed candidate stays blocked when someone tries to promote it anyway.</summary>
    [Fact]
    public void ADisconfirmedCandidateCannotBePromotedAfterwards()
    {
        var candidate = Only(SeenTwice(),
        [
            .. FullyEvidenced(),
            Event(DaydreamEventKind.CheckCompleted, outcome: DisconfirmingOutcome.Refuted),
            Event(DaydreamEventKind.Promoted),
        ]);

        Assert.Equal(DaydreamState.Disconfirmed, candidate.State);
    }

    /// <summary>A surviving check makes it promotable, and only then does a human decision take.</summary>
    [Fact]
    public void ASurvivingCheckMakesItPromotableAndAHumanPromotesIt()
    {
        var evidenced = new[]
        {
            FullyEvidenced()[0], FullyEvidenced()[1], FullyEvidenced()[2],
            Event(DaydreamEventKind.CheckCompleted, outcome: DisconfirmingOutcome.Survived),
        };

        var promotable = Only(SeenTwice(), evidenced);
        Assert.Equal(DaydreamState.Promotable, promotable.State);
        Assert.True(promotable.CanPromote);
        Assert.Null(promotable.BlockedBecause);

        var promoted = Only(SeenTwice(), [.. evidenced, Event(DaydreamEventKind.Promoted, actor: "@timianmalloo")]);
        Assert.Equal(DaydreamState.Promoted, promoted.State);
    }

    // ---------------------------------------------------------------- criterion 5

    /// <summary>
    /// A promoted learning whose evidence disappears falls back to an Observation.
    /// </summary>
    /// <remarks>
    /// US-9's fifth criterion. The fold reads evidence <b>before</b> events for exactly this: a
    /// decision was made about episodes that no longer exist, so the decision does not survive them.
    /// A lesson outliving its evidence is a claim nobody can check — which is the thing this whole
    /// pipeline exists to avoid producing.
    /// </remarks>
    [Fact]
    public void APromotedLearningWhoseSourceIsGoneFallsBack()
    {
        var promoted = new[]
        {
            FullyEvidenced()[0], FullyEvidenced()[1], FullyEvidenced()[2],
            Event(DaydreamEventKind.CheckCompleted, outcome: DisconfirmingOutcome.Survived),
            Event(DaydreamEventKind.Promoted),
        };

        Assert.Equal(DaydreamState.Promoted, Only(SeenTwice(), promoted).State);

        // Retention, correction or a purged workspace takes the sources away.
        var withoutEvidence = Only([], promoted);
        Assert.Equal(DaydreamState.Observation, withoutEvidence.State);
        Assert.Contains("no longer present", withoutEvidence.BlockedBecause);
    }

    /// <summary>Losing enough episodes to drop below the threshold has the same effect.</summary>
    [Fact]
    public void FallingBelowTheRecurrenceThresholdReturnsToObservation()
    {
        Assert.Equal(DaydreamState.Observation, Only([Seen("ep-1")], FullyEvidenced()).State);
    }

    /// <summary>An explicit retraction is recorded with its reason and is terminal.</summary>
    [Fact]
    public void ARetractionIsTerminalAndCarriesItsReason()
    {
        var candidate = Only(SeenTwice(),
        [
            .. FullyEvidenced(),
            Event(DaydreamEventKind.CheckCompleted, outcome: DisconfirmingOutcome.Survived),
            Event(DaydreamEventKind.Promoted),
            Event(DaydreamEventKind.Retracted, detail: "contradicted by ep-9"),
            Event(DaydreamEventKind.Promoted),
        ]);

        Assert.Equal(DaydreamState.Retracted, candidate.State);
        Assert.Equal("contradicted by ep-9", candidate.BlockedBecause);
    }

    // ---------------------------------------------------------------- the human decisions

    [Fact]
    public void ARejectionIsTerminalAndCarriesItsReason()
    {
        var candidate = Only(SeenTwice(),
            [.. FullyEvidenced(), Event(DaydreamEventKind.Rejected, detail: "already covered by DC-016")]);

        Assert.Equal(DaydreamState.Rejected, candidate.State);
        Assert.Equal("already covered by DC-016", candidate.BlockedBecause);
    }

    /// <summary>
    /// A deferral persists, and is re-opened only by new evidence.
    /// </summary>
    /// <remarks>
    /// <para>Written first as "deferring leaves it NeedsDisconfirm", which failed — and the failure
    /// was the useful part. The spec's review flow says <i>defer → remain Candidate</i> and its state
    /// vocabulary lists <c>deferred</c> as its own state, so a deferral has to survive later events;
    /// otherwise the next unrelated event silently undoes a human's choice.</para>
    ///
    /// <para>But it must not survive a change to the thing they deferred <i>on</i>, or a candidate
    /// could be parked once and never resurface however much evidence arrived. So: persists through
    /// anything, re-opens on evidence.</para>
    /// </remarks>
    [Fact]
    public void ADeferralPersistsUntilNewEvidenceArrives()
    {
        var deferred = Only(SeenTwice(), Event(DaydreamEventKind.Deferred));
        Assert.Equal(DaydreamState.Deferred, deferred.State);
        Assert.False(deferred.CanPromote);

        // A later unrelated decision does not undo the deferral.
        var stillDeferred = Only(SeenTwice(),
            Event(DaydreamEventKind.Deferred), Event(DaydreamEventKind.Promoted));
        Assert.Equal(DaydreamState.Deferred, stillDeferred.State);

        // New evidence re-opens it, and it re-derives to whatever the evidence now supports.
        var reopened = Only(SeenTwice(),
        [
            Event(DaydreamEventKind.Deferred),
            .. FullyEvidenced(),
            Event(DaydreamEventKind.CheckCompleted, outcome: DisconfirmingOutcome.Survived),
        ]);
        Assert.Equal(DaydreamState.Promotable, reopened.State);
    }

    // ---------------------------------------------------------------- confidence

    /// <summary>
    /// Confidence is never "Verified", however often the pattern recurs.
    /// </summary>
    /// <remarks>
    /// A pattern seen many times is still an observation about outcomes, not a proven claim. Only a
    /// surviving disconfirming check earns more, and that is expressed by the <i>state</i> rather
    /// than by relabelling the evidence — which is the difference between the pack's Verified and
    /// Inferred meaning something and being decoration.
    /// </remarks>
    [Fact]
    public void ConfidenceIsNeverVerifiedHoweverOftenItRecurs()
    {
        var many = Enumerable.Range(1, 12).Select(i => Seen("ep-" + i, i)).ToList();

        var candidate = Only(many);

        Assert.DoesNotContain("Verified", candidate.Evidence.Confidence);
        Assert.Contains("Inferred", candidate.Evidence.Confidence);
    }

    /// <summary>The fold is deterministic, so a replay produces the same standing.</summary>
    [Fact]
    public void TheFoldIsDeterministicUnderReordering()
    {
        var events = new[]
        {
            FullyEvidenced()[0], FullyEvidenced()[1], FullyEvidenced()[2],
            Event(DaydreamEventKind.CheckCompleted, outcome: DisconfirmingOutcome.Survived),
        };

        Assert.Equal(
            Only(SeenTwice(), events).State,
            Only(SeenTwice().Reverse(), [.. events.Reverse()]).State);
    }
}
