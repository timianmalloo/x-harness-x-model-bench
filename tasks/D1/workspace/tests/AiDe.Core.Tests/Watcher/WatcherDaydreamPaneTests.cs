using AiDe.Core.Presentation;
using AiDe.Core.Watcher;

namespace AiDe.Core.Tests.Watcher;

/// <summary>
/// D4 — the Daydreams pane read model: three stages, honest empty states, and a promote affordance
/// only where promotion is actually possible (US-9).
/// </summary>
public sealed class WatcherDaydreamPaneTests
{
    private static readonly DaydreamSignature Pattern = new(
        "implement", ScoreSchema.Weave1Version, WeaveVerdict.Blocked, "Correctness", "OutcomeIntegrity:1");

    private sealed class Fixed(params DaydreamCandidate[] candidates) : IWatcherDaydreamQuery
    {
        public string? Unavailable => null;

        public int UnreadableLines { get; init; }

        public string? ReachFinding { get; init; }

        public IReadOnlyList<DaydreamCandidate> GetCandidates() => candidates;
    }

    private sealed class Broken : IWatcherDaydreamQuery
    {
        public string? Unavailable => null;

        public int UnreadableLines => 0;

        public string? ReachFinding => null;

        public IReadOnlyList<DaydreamCandidate> GetCandidates() => throw new InvalidOperationException("record gone");
    }

    private sealed class NoRepository : IWatcherDaydreamQuery
    {
        public string? Unavailable => "No repository is open, so nothing is recorded.";

        public int UnreadableLines => 0;

        public string? ReachFinding => null;

        // Never reached. A query that reports itself unavailable must not also be asked for a
        // result: if the pane calls this, the absence check ran too late.
        public IReadOnlyList<DaydreamCandidate> GetCandidates() =>
            throw new InvalidOperationException("asked an unavailable record for candidates");
    }

    private static DaydreamCandidate Candidate(
        DaydreamState state, string? blocked = null, int episodes = 2) =>
        new(Pattern, state,
            new CandidateEvidence([.. Enumerable.Range(1, episodes).Select(i => "ep-" + i)], "Inferred — few occurrences"),
            blocked);

    private static WatcherDaydreamPaneViewModel Loaded(IWatcherDaydreamQuery? query)
    {
        var pane = new WatcherDaydreamPaneViewModel(query);
        pane.Load();
        return pane;
    }

    // ---------------------------------------------------------------- states

    [Fact]
    public void NoStoreIsAnHonestUnavailableRatherThanAnEmptyList()
    {
        var pane = Loaded(null);

        Assert.Equal(PaneState.Empty, pane.State);
        Assert.Contains("no watcher store is attached", pane.StatusMessage);
        Assert.Empty(pane.Rows);
    }

    /// <summary>A failing store is Error, never a plausible-looking empty pane.</summary>
    /// <remarks>
    /// "No patterns observed yet" over an unreadable store is an absence over a set nobody looked
    /// at — the same shape the privacy probe refuses with exit 9.
    /// </remarks>
    [Fact]
    public void AnUnreadableStoreIsAnErrorNotAnEmptyPane()
    {
        var pane = Loaded(new Broken());

        Assert.Equal(PaneState.Error, pane.State);
        Assert.Contains("could not be read", pane.StatusMessage);
        Assert.Empty(pane.Rows);
    }

    [Fact]
    public void AnEmptyStoreSaysSoWithoutBlamingAnything()
    {
        var pane = Loaded(new Fixed());

        Assert.Equal(PaneState.Empty, pane.State);
        Assert.Equal("No patterns observed yet.", pane.StatusMessage);
    }

    // ---------------------------------------------------------------- the promote affordance

    /// <summary>
    /// Only a Promotable candidate offers promotion, and every other state says why not.
    /// </summary>
    /// <remarks>
    /// The surface reads <c>CanPromote</c> to decide whether the affordance exists <b>at all</b>,
    /// not whether it is enabled and refuses on click. A control a user can press and be refused by
    /// teaches that the refusal is negotiable.
    /// </remarks>
    [Theory]
    [InlineData(DaydreamState.NeedsDisconfirm, false)]
    [InlineData(DaydreamState.Disconfirmed, false)]
    [InlineData(DaydreamState.Deferred, false)]
    [InlineData(DaydreamState.Rejected, false)]
    [InlineData(DaydreamState.Retracted, false)]
    [InlineData(DaydreamState.Promoted, false)]
    [InlineData(DaydreamState.Promotable, true)]
    public void PromotionIsOfferedOnlyWhereItIsPossible(DaydreamState state, bool expected)
    {
        var row = WatcherDaydreamRow.From(Candidate(state, blocked: expected ? null : "a reason"));

        Assert.Equal(expected, row.CanPromote);
    }

    /// <summary>A blocked row carries the reason in the row itself, not behind an interaction.</summary>
    [Fact]
    public void ABlockedRowNamesWhatIsMissingWhereItIsRead()
    {
        var row = WatcherDaydreamRow.From(
            Candidate(DaydreamState.NeedsDisconfirm, "No disconfirming check has been attached."));

        Assert.Contains("No disconfirming check has been attached.", row.DisplayLabel);
        Assert.Contains("blocked: No disconfirming check has been attached.", row.AccessibleName);
    }

    /// <summary>A promotable row announces that it is ready, so the state is not colour-only.</summary>
    [Fact]
    public void APromotableRowAnnouncesItIsReady()
    {
        var row = WatcherDaydreamRow.From(Candidate(DaydreamState.Promotable));

        Assert.Contains("ready to promote", row.AccessibleName);
    }

    // ---------------------------------------------------------------- the three stages

    [Theory]
    [InlineData(DaydreamState.Observation, "Observations")]
    [InlineData(DaydreamState.NeedsDisconfirm, "Candidates")]
    [InlineData(DaydreamState.Promotable, "Candidates")]
    [InlineData(DaydreamState.Promoted, "Promoted")]
    public void EachStateSitsUnderTheStageTheSpecNames(DaydreamState state, string stage)
    {
        Assert.Equal(stage, WatcherDaydreamRow.StageOf(state));
    }

    /// <summary>
    /// A disconfirmed candidate stays visible under Candidates.
    /// </summary>
    /// <remarks>
    /// It is the most informative row on the surface — the system having done the disconfirming work
    /// and reported the answer nobody wanted. Hiding it would leave a reader looking only at the
    /// proposals that survived, which is the selection bias this pipeline exists to avoid.
    /// </remarks>
    [Fact]
    public void ADisconfirmedCandidateStaysVisible()
    {
        var pane = Loaded(new Fixed(Candidate(DaydreamState.Disconfirmed, "A completed check refuted it.")));

        Assert.Single(pane.RowsFor("Candidates"));
        Assert.Contains("refuted", pane.RowsFor("Candidates")[0].DisplayLabel);
    }

    /// <summary>Every stage is named even when it holds nothing, with a reason that fits it.</summary>
    /// <remarks>
    /// Each empty state names only what the pane has looked at. None mentions the extractor, the
    /// scorer, or any subsystem this surface does not read — the mistake DC-087 registered.
    /// </remarks>
    [Fact]
    public void EveryStageHasAnEmptyStateThatClaimsOnlyWhatItChecked()
    {
        Assert.Equal(3, WatcherDaydreamPaneViewModel.Stages.Count);

        foreach (var stage in WatcherDaydreamPaneViewModel.Stages)
        {
            var empty = WatcherDaydreamPaneViewModel.EmptyStateFor(stage);
            Assert.False(string.IsNullOrWhiteSpace(empty));
            Assert.DoesNotContain("extractor", empty, StringComparison.OrdinalIgnoreCase);
            Assert.DoesNotContain("scorer", empty, StringComparison.OrdinalIgnoreCase);
        }
    }

    [Fact]
    public void TheStatusLineSaysHowManyAreActuallyReady()
    {
        var none = Loaded(new Fixed(Candidate(DaydreamState.NeedsDisconfirm, "no check")));
        Assert.Contains("none ready to promote", none.StatusMessage);

        var one = Loaded(new Fixed(
            Candidate(DaydreamState.NeedsDisconfirm, "no check"), Candidate(DaydreamState.Promotable)));
        Assert.Contains("1 ready to promote", one.StatusMessage);
    }

    // ------------------------------------------------- end to end over the repository record

    /// <summary>
    /// The pane reads a real repository record through the real fold.
    /// </summary>
    /// <remarks>
    /// Through <c>WatcherDaydreamQuery</c> and a record on disk rather than a stub, because the
    /// whole point of D4 is that the surface renders something a writer actually produced. A pane
    /// tested only against fixtures is the shape DC-089 registered.
    /// </remarks>
    [Fact]
    public void ThePaneRendersWhatWasWrittenToTheRepository()
    {
        using var repo = new TempRepository();
        repo.Record.Append(new DaydreamObservation("obs-1", Pattern, "ep-1", DateTimeOffset.UnixEpoch));
        repo.Record.Append(new DaydreamObservation("obs-2", Pattern, "ep-2", DateTimeOffset.UnixEpoch));

        var pane = Loaded(new WatcherDaydreamQuery(repo.Record));

        var row = Assert.Single(pane.RowsFor("Candidates"));
        Assert.Equal(2, row.Episodes);
        Assert.False(row.CanPromote);
        Assert.Contains("implement", row.Pattern);
        Assert.Contains("Correctness", row.Pattern);
    }

    /// <summary>One observation stays an Observation all the way to the surface.</summary>
    [Fact]
    public void OneObservationNeverReachesTheCandidatesStage()
    {
        using var repo = new TempRepository();
        repo.Record.Append(new DaydreamObservation("obs-1", Pattern, "ep-1", DateTimeOffset.UnixEpoch));

        var pane = Loaded(new WatcherDaydreamQuery(repo.Record));

        Assert.Empty(pane.RowsFor("Candidates"));
        Assert.Equal(PaneState.Empty, pane.State);
    }

    // ------------------------------------------------------------------ absence

    /// <summary>
    /// No repository is not an empty Daydream.
    /// </summary>
    /// <remarks>
    /// Both render as <see cref="PaneState.Empty"/>, so only the message distinguishes them — and
    /// "No patterns observed yet" from a pane that never opened a repository is a claim about the
    /// repository it did not look at (DC-025, DC-087).
    /// </remarks>
    /// <remarks>
    /// <b>OBSERVED RED</b> on 2026-09-02 by removing the pre-read absence check from <c>Load</c>:
    /// the pane then asks an unavailable record for candidates, the stub throws, and it reports
    /// <c>Error</c> — "the record could not be read" — instead of "no repository is open". Replayed
    /// rather than assumed, because a test written at the same moment as its fix has never been
    /// shown capable of failing, and one that cannot fail is decoration (DC-016).
    /// </remarks>
    [Fact]
    public void NoRepositorySaysSoRatherThanReportingNoPatterns()
    {
        var pane = Loaded(new NoRepository());

        Assert.Equal(PaneState.Empty, pane.State);
        Assert.Contains("No repository is open", pane.StatusMessage);
        Assert.DoesNotContain("No patterns observed", pane.StatusMessage);
    }

    /// <summary>A partly unreadable record is never rendered as a whole one.</summary>
    [Fact]
    public void UnreadableLinesAreCarriedOntoTheSurface()
    {
        var pane = Loaded(new Fixed(Candidate(DaydreamState.NeedsDisconfirm)) { UnreadableLines = 3 });

        Assert.Equal(PaneState.Ready, pane.State);
        Assert.Contains("3 line(s) could not be read", pane.StatusMessage);
    }

    /// <summary>
    /// A reach finding REPLACES "no patterns observed yet" rather than being appended to it.
    /// </summary>
    /// <remarks>
    /// Order is the whole point. Both sentences are true when Daydream cannot see the work, and
    /// leading with the reassuring one lets a reader stop before the cause — which is the reading
    /// the probe exists to displace (DC-025).
    /// </remarks>
    [Fact]
    public void AReachFindingDisplacesTheReassuringEmptyMessage()
    {
        var pane = Loaded(new Fixed
        {
            ReachFinding = "3 episode(s) scored and none carried anything to assess — "
                + "Daydream cannot see this work, which is an instrumentation gap rather than a quiet repository.",
        });

        Assert.Equal(PaneState.Empty, pane.State);
        Assert.Contains("cannot see this work", pane.StatusMessage);
        Assert.DoesNotContain("No patterns observed yet", pane.StatusMessage);
    }

    /// <summary>With nothing to report, the ordinary empty message stands.</summary>
    /// <remarks>
    /// The other half, and the one that keeps the finding meaningful: a probe that always had
    /// something to say would make the sentence above furniture rather than a signal.
    /// </remarks>
    [Fact]
    public void NoReachFindingLeavesTheOrdinaryEmptyMessage()
    {
        var pane = Loaded(new Fixed());

        Assert.Equal(PaneState.Empty, pane.State);
        Assert.Equal("No patterns observed yet.", pane.StatusMessage);
    }

    /// <summary>And an EMPTY record that was partly unreadable says so too.</summary>
    /// <remarks>
    /// The case most likely to be missed: with no rows the pane takes the empty branch, and an
    /// empty branch that drops the caveat reports "nothing has happened here" about a file it could
    /// not finish reading.
    /// </remarks>
    /// <remarks>
    /// <b>OBSERVED RED</b> on 2026-09-02 by dropping <c>+ caveat</c> from the empty branch alone —
    /// the populated branch kept it, and this test went red while every other pane test stayed
    /// green. That specificity is the point: it fails for the branch it is about, and would not
    /// have caught a regression it does not cover.
    /// </remarks>
    [Fact]
    public void AnEmptyButPartlyUnreadableRecordStillSaysSo()
    {
        var pane = Loaded(new Fixed { UnreadableLines = 1 });

        Assert.Equal(PaneState.Empty, pane.State);
        Assert.Contains("1 line(s) could not be read", pane.StatusMessage);
    }

    private sealed class TempRepository : IDisposable
    {
        private readonly string _root = Path.Combine(
            Path.GetTempPath(), "aide-daydream-pane-" + Guid.NewGuid().ToString("n")[..8]);

        public TempRepository()
        {
            Directory.CreateDirectory(_root);
            Record = DaydreamRepositoryRecord.For(_root);
        }

        public DaydreamRepositoryRecord Record { get; }

        public void Dispose()
        {
            try { Directory.Delete(_root, recursive: true); } catch (IOException) { /* best effort */ }
        }
    }
}
