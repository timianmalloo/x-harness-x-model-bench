using AiDe.Core.Watcher;

namespace AiDe.Core.Tests.Watcher;

/// <summary>
/// What the Daydream vertical produces against <b>this repository's own audit log</b>, not a fixture.
/// </summary>
/// <remarks>
/// <para><b>Why a test over the real corpus.</b> Every other test here builds the episodes it then
/// measures, so all of them pass in a world where the corpus is empty. The question this answers is
/// the one a fixture cannot: given what has actually been recorded here, can Daydream produce
/// anything at all?</para>
///
/// <para><b>It has now measured a transition, which is the point of pointing it at real data.</b>
/// On 2026-09-03 it recorded 111 episodes, 7 clean, 103 carrying nothing to assess and ONE
/// observation — one short of the recurrence threshold, so the output over the whole recorded
/// history was zero however good the engine was. Later the same day, after Proof Pack capture was
/// stipulated and ratcheted: 120 episodes, 17 assessed, <b>103 still unassessed</b>, two
/// observations, one candidate.</para>
///
/// <para><b>The 103 never moved, and were never going to.</b> Capture accumulates forward, so
/// episodes closed without evidence are unreachable — the claim made before the change, confirmed
/// by the measurement after it rather than restated.</para>
///
/// <para><b>One test here expired on purpose and was rewritten, not deleted.</b> A claim about what
/// does NOT exist decays when someone else acts, with the author absent and no reason to look
/// (DC-094), so it was tied to something that fails the day it stops being true. It failed. Its
/// replacement asserts the rule the world cannot change on its own: a candidate with no
/// disconfirming check cannot be promoted.</para>
///
/// <para><b>Assertions are threshold relationships, never the measured numbers.</b> Pinning "103"
/// would go red on the next audit entry and be edited back without thought, which is a control that
/// trains people to ignore it.</para>
/// </remarks>
public sealed class WhatTheRealCorpusCanProduceTests
{
    /// <summary>Walks up for the repository root, so the test does not depend on the runner's cwd.</summary>
    private static string? FindRepositoryRoot()
    {
        var dir = new DirectoryInfo(AppContext.BaseDirectory);
        while (dir is not null)
        {
            if (File.Exists(Path.Combine(dir.FullName, "docs", "audit", "audit-log.jsonl")))
            {
                return dir.FullName;
            }

            dir = dir.Parent;
        }

        return null;
    }

    private sealed record Measurement(
        int Scored,
        DaydreamReach Reach,
        int Observations,
        IReadOnlyList<DaydreamCandidate> Candidates);

    private static Measurement Measure()
    {
        var root = FindRepositoryRoot();

        // Loud, not skipped. A test that silently passes when it cannot find its subject is an
        // absence rendered as success (DC-025) — in the one test whose whole purpose is measuring
        // an absence.
        Assert.True(root is not null, "could not locate the repository root from " + AppContext.BaseDirectory);

        var scratch = Path.Combine(Path.GetTempPath(), "aide-corpus-" + Guid.NewGuid().ToString("n")[..8]);
        Directory.CreateDirectory(scratch);

        try
        {
            using var host = WatcherHost.Open(scratch, Path.Combine(scratch, "coord"));

            // The record goes in the SCRATCH directory, never in the repository. A test must not
            // write this repository's own docs/daydream/, or running the suite would author
            // committed content as a side effect.
            var record = DaydreamRepositoryRecord.For(scratch);

            var scored = host.ImportAndScoreEpisodesFromAuditLog(
                Path.Combine(root!, "docs", "audit", "audit-log.jsonl"),
                WorkspaceKey.From(root!),
                daydream: new DaydreamRecorder(record));

            var read = record.Read();
            return new Measurement(
                scored,
                new DaydreamReachProbe(host.Store, record).Probe(),
                read.Observations.Count,
                new DaydreamFold().Fold(read.Observations, read.Events));
        }
        finally
        {
            try { Directory.Delete(scratch, recursive: true); } catch (IOException) { /* best effort */ }
        }
    }

    /// <summary>
    /// The import path works against real data — episodes are read and scored.
    /// </summary>
    /// <remarks>
    /// The half worth confirming before drawing any conclusion from the rest: a zero here would mean
    /// the reader is broken, which is a completely different finding from "there is nothing to read".
    /// </remarks>
    [Fact]
    public void TheRealAuditLogYieldsScoredEpisodes()
    {
        var m = Measure();

        Assert.True(m.Scored > 0, "the real audit log produced no scored episodes at all");
        Assert.Equal(m.Scored, m.Reach.EpisodesScored);
    }

    /// <summary>
    /// The corpus produces a candidate — the first thing Daydream has ever proposed.
    /// </summary>
    /// <remarks>
    /// <para><b>This test expired on 2026-09-03, exactly as designed, and this is its rewrite.</b>
    /// It previously asserted that the corpus could NOT produce a candidate: one observation, and a
    /// recurrence threshold of two, so the output over the whole recorded history was zero however
    /// good the engine was. Its own remark said the red would be good news and instructed a rewrite
    /// rather than a deletion.</para>
    ///
    /// <para><b>What closed it was capture, not code.</b> The owner stipulated Proof Pack capture;
    /// the ratchet made new skill entries carry a goal, a done condition and evidence; nine such
    /// entries arrived within the day. Measured across that transition, with the historical debt
    /// untouched exactly as predicted:</para>
    ///
    /// <list type="table">
    ///   <item><description>episodes 111 → 120, assessed 8 → 17, <b>unassessed 103 → 103</b></description></item>
    ///   <item><description>observations 1 → 2, recurrences 0 → 1, <b>candidates 0 → 1</b></description></item>
    /// </list>
    ///
    /// <para>The 103 did not move, and were never going to: capture accumulates forward, so episodes
    /// closed without evidence are unreachable. That was the claim, and this is the measurement that
    /// confirms it rather than a repetition of it.</para>
    /// </remarks>
    [Fact]
    public void TheRealCorpusNowProducesACandidate()
    {
        var m = Measure();

        Assert.True(
            m.Observations >= 2,
            $"only {m.Observations} observation(s) — the corpus has regressed below recurrence, which "
            + "means capture stopped or an import path broke. This test previously asserted the "
            + "opposite; do not simply invert it back.");

        Assert.NotEmpty(m.Candidates);
    }

    /// <summary>
    /// And every candidate is BLOCKED from promotion, because nothing has disconfirmed it.
    /// </summary>
    /// <remarks>
    /// <para>The acceptance criterion most likely to be quietly relaxed under pressure to show the
    /// feature doing something: a candidate with no disconfirming check has promotion <b>disabled</b>,
    /// not discouraged, and no amount of recurrence substitutes for one.</para>
    ///
    /// <para><b>This asserts the rule, not a count.</b> <c>Assert.Single(m.Candidates)</c> expired the
    /// same way the test above it once did: the corpus is designed to grow, so the number of
    /// candidates it yields is not durable — an unrelated audit entry (e.g. two superseding entries
    /// differing only in <c>Shortfalls</c>) can turn one candidate into two without the rule the test
    /// cares about changing at all. A count over a growing corpus cannot stay true indefinitely; only
    /// a per-candidate rule can. So this asserts the rule over <b>every</b> candidate, with a
    /// non-vacuity guard (<see cref="Assert.NotEmpty{T}(IEnumerable{T})"/>) so an empty corpus cannot
    /// pass by having nothing to check — only a human attaching a disconfirming check can move a
    /// candidate past this, which is the design.</para>
    /// </remarks>
    [Fact]
    public void TheCandidateCannotBePromotedWithoutADisconfirmingCheck()
    {
        var m = Measure();

        Assert.NotEmpty(m.Candidates);
        Assert.All(m.Candidates, candidate =>
        {
            Assert.False(candidate.CanPromote);
            Assert.NotNull(candidate.BlockedBecause);
        });
    }

    /// <summary>
    /// And the surface says WHY it is empty, rather than "no patterns observed yet".
    /// </summary>
    /// <remarks>
    /// The reason the probe exists. Against the real corpus the honest reading is that most turns
    /// recorded nothing assessable — not that the work went well — and the finding has to carry that
    /// or a permanently quiet Daydream reads as a healthy repository (DC-025).
    /// </remarks>
    [Fact]
    public void TheProbeExplainsTheRealCorpusRatherThanReportingSilence()
    {
        var m = Measure();

        Assert.True(m.Reach.NothingWasAssessed > 0, "expected unassessed episodes in the real corpus");
        Assert.NotNull(m.Reach.Finding);
        Assert.Contains("carried nothing to assess", m.Reach.Finding);
    }

    /// <summary>
    /// The gap is in capture, not in reading — checked rather than concluded.
    /// </summary>
    /// <remarks>
    /// <c>docs/proof/</c> exists and holds real Proof Packs, and some episodes ARE assessed. So the
    /// reader finds what is there; most turns simply never recorded evidence in their audit entry.
    /// Without this, "103 carried nothing to assess" would be equally consistent with a broken
    /// reader, and the fix for those two is opposite.
    /// </remarks>
    [Fact]
    public void SomeEpisodesAreAssessed_SoTheReaderIsNotTheProblem()
    {
        var m = Measure();

        Assert.True(
            m.Reach.NothingWentWrong + m.Reach.WouldRecord > 0,
            "no episode was assessed at all — that would point at the reader, not at capture");
    }
}
