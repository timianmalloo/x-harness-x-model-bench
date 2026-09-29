using AiDe.Core.Watcher;

namespace AiDe.Core.Tests.Watcher;

/// <summary>
/// What the Daydream record would learn from an agent's contract-declared episode: nothing, today.
/// </summary>
/// <remarks>
/// <para><b>Written to answer a prediction, and it refuted it.</b> Before wiring
/// <see cref="DaydreamRecorder"/> to the tick-based scoring pass, the concern raised was the
/// opposite of what happens: that every agent episode would carry the <i>same</i> Not-Scored
/// signature, so one pattern would recur across every episode and the recurrence detector would
/// rank it first — right, and useless.</para>
///
/// <para><b>Measured instead of assumed.</b> An agent's Not-Scored episode trips <b>no floor</b> and
/// records <b>no shortfall</b>, so its signature is <i>unremarkable</i> and
/// <see cref="DaydreamRecorder.Observe"/> writes nothing at all. The reason is the same honesty that
/// produces the Not Scored verdict: with no Proof Pack there is no evidence, every dimension is
/// Not-Recorded, and a Not-Recorded dimension has a null rubric — so it is absent from the
/// shortfall list rather than counted as a zero. A floor is tripped by an observed failure, and
/// nothing was observed.</para>
///
/// <para><b>So the question is not "will Daydream drown", it is "will Daydream hear anything".</b>
/// Wiring the recorder to this pass today is a call site that can only ever no-op, which is a
/// different defect from the one anticipated and a worse one to discover later — a green suite plus
/// a live call site reads as a closed vertical.</para>
///
/// <para><b>Replayed (DC-099).</b> Making an unevidenced episode acquire a tripped floor reddens
/// both tests here AND four of the concurrent session's Daydream tests — the crossover is the useful
/// part, because it shows this honesty invariant and that recorder are load-bearing on each other
/// rather than merely adjacent.</para>
///
/// <para><b>These assertions are written to fail when that changes.</b> The day an agent episode
/// carries verification evidence — a task class on the contract, a Proof Pack, an observed
/// regression — a floor or a shortfall appears, the signature becomes remarkable, and the first
/// test below goes red. That failure is the signal that the recorder now has something to record.</para>
/// </remarks>
public sealed class WhatDaydreamSeesInAnAgentEpisodeTests
{
    private const double At = 1000;
    private const string Repo = "C:/repos/app";

    private static Dictionary<string, string?> RegisterAttrs(string terminal, string agent) =>
        new(StringComparer.Ordinal)
        {
            [OtelAttributes.RepoPath] = Repo,
            [OtelAttributes.RepoDisplay] = "app",
            [OtelAttributes.WorktreePath] = Repo,
            [OtelAttributes.WorktreeBranch] = "main",
            [OtelAttributes.TerminalId] = terminal,
            [OtelAttributes.AgentName] = agent,
            [OtelAttributes.ServiceName] = "claude-code",
        };

    private static InMemoryWatcherObservationStore CircuitWith(params string[] externalIds)
    {
        var store = new InMemoryWatcherObservationStore();
        var n = 0;
        var registrar = new TrustedRegistrar(
            store, new SequentialCapabilityFactory(), new FakeMonotonicClock(), () => $"session-{++n}");
        var host = new IngestHost(store, registrar, new FixedTimeProvider(DateTimeOffset.UnixEpoch.AddSeconds(At)));
        var adapter = new InjectedContractIngest(host);

        var sequence = 1;
        foreach (var external in externalIds)
        {
            adapter.Apply(new ContractRegister(external, RegisterAttrs(external, "agent-" + external), At, sequence++));
            adapter.Apply(new ContractEpisodeOpen(
                external,
                new Dictionary<string, string?>(StringComparer.Ordinal)
                {
                    [CoordContract.EpisodeAttributes.Goal] = "g-" + external,
                    [CoordContract.EpisodeAttributes.DoneWhen] = "d-" + external,
                },
                At + 1, sequence++));
            adapter.Apply(new ContractEpisodeClose(
                external,
                new Dictionary<string, string?>(StringComparer.Ordinal)
                {
                    [CoordContract.EpisodeAttributes.Outcome] = "completed",
                },
                At + 2, sequence++));
        }

        ClosedEpisodeScoring.Run(store, TimeProvider.System);
        return store;
    }

    [Fact]
    public void AnAgentEpisodeSignatureIsUnremarkable_SoNothingWouldBeRecorded()
    {
        var store = CircuitWith("ext-1");
        var scored = Assert.Single(store.AllScoredEpisodes());

        var signature = DaydreamSignature.For(scored);

        Assert.Equal(WeaveVerdict.NotScored, signature.Verdict);

        // No floor tripped: a floor is an OBSERVED failure, and nothing was observed.
        Assert.Empty(signature.Floors);

        // No shortfall either — and the reason is stronger than "every rubric is null". There are
        // NO ASSESSMENTS AT ALL: nothing was evaluated, so there is no dimension to fall short.
        //
        // Asserted as Empty rather than with Assert.All over the rubrics, because Assert.All passes
        // vacuously on an empty collection: the weaker assertion was green for a reason that was not
        // the reason it named, and would have stayed green if assessments later appeared with null
        // rubrics — a different state entirely.
        Assert.Empty(signature.Shortfalls);
        Assert.Empty(scored.Scorecard.Assessments);

        Assert.True(signature.IsUnremarkable);
    }

    [Fact]
    public void SoTheRecorderWritesNothing_ForEveryAgentEpisode()
    {
        // Three agents, three sessions, three closed episodes, and nothing to learn from any of
        // them. Not because the recorder is broken - because there is no evidence yet to observe.
        var store = CircuitWith("ext-1", "ext-2", "ext-3");
        var scored = store.AllScoredEpisodes();

        Assert.Equal(3, scored.Count);
        Assert.All(scored, e => Assert.True(DaydreamSignature.For(e).IsUnremarkable));

        // And the recurrence detector, fed all of them, finds no pattern - which is the honest
        // answer rather than one pattern repeated three times.
        var observations = scored
            .Select(e => new DaydreamObservation(
                DaydreamRecorder.IdFor(e.EpisodeId, DaydreamSignature.For(e)),
                DaydreamSignature.For(e),
                e.EpisodeId,
                DateTimeOffset.UnixEpoch))
            .ToList();

        Assert.Empty(new RecurrenceDetector().Recurring(observations));
    }
}
