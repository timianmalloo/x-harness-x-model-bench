using AiDe.Core.Watcher;

namespace AiDe.Core.Tests.Watcher;

/// <summary>
/// An agent declaring its evidence on <c>episode-close</c>, end to end over the real contract.
/// </summary>
/// <remarks>
/// Driven the way an agent drives it — a contract line, not a service call — because the point of
/// the channel is that a harness with no pack and no directives can use it. A test that called
/// <c>DeclareArtifacts</c> directly would pass while the wire format was unreachable.
/// </remarks>
public sealed class ContractDeclaredArtifactTests
{
    private const double At = 1_700_000_000d;

    private static Dictionary<string, string?> RegisterAttrs() => new(StringComparer.Ordinal)
    {
        [OtelAttributes.RepoPath] = "C:/repos/app",
        [OtelAttributes.RepoDisplay] = "app",
        [OtelAttributes.WorktreeBranch] = "main",
        [OtelAttributes.WorktreePath] = "C:/repos/app",
        [OtelAttributes.TerminalId] = "term-1",
        [OtelAttributes.AgentName] = "copilot",
    };

    private static Dictionary<string, string?> OpenAttrs() => new(StringComparer.Ordinal)
    {
        [CoordContract.EpisodeAttributes.Goal] = "Close the evidence gap",
        [CoordContract.EpisodeAttributes.DoneWhen] = "a declared path reaches the store",
    };

    private static Dictionary<string, string?> CloseAttrs(string outcome, string? artifacts)
    {
        var attrs = new Dictionary<string, string?>(StringComparer.Ordinal)
        {
            [CoordContract.EpisodeAttributes.Outcome] = outcome,
        };

        if (artifacts is not null)
        {
            attrs[CoordContract.EpisodeAttributes.Artifacts] = artifacts;
        }

        return attrs;
    }

    private static (InjectedContractIngest adapter, InMemoryWatcherObservationStore store) Opened()
    {
        var store = new InMemoryWatcherObservationStore();
        var clock = new FakeMonotonicClock();
        var n = 0;
        var registrar = new TrustedRegistrar(store, new SequentialCapabilityFactory(), clock, () => $"session-{++n}");
        var host = new IngestHost(store, registrar, new FixedTimeProvider(DateTimeOffset.UnixEpoch.AddSeconds(At)));
        var adapter = new InjectedContractIngest(host);

        adapter.Apply(new ContractRegister("ext-1", RegisterAttrs(), At, 1));
        adapter.Apply(new ContractEpisodeOpen("ext-1", OpenAttrs(), At + 1, 2));
        return (adapter, store);
    }

    private static string EpisodeId(InMemoryWatcherObservationStore store) =>
        store.EpisodesForSession("session-1").Single().EpisodeId;

    // ---------------------------------------------------------------- the happy path

    [Fact]
    public void ADeclaredPathReachesTheStoreAndTheEpisodeCloses()
    {
        var (adapter, store) = Opened();
        var episodeId = EpisodeId(store);

        adapter.Apply(new ContractEpisodeClose(
            "ext-1", CloseAttrs("Completed", "docs/proof/pp-0001.md\ndocs/proof/pp-0002.md"), At + 2, 3));

        var declared = store.DeclaredArtifactsFor(episodeId);
        Assert.Equal(
            ["docs/proof/pp-0001.md", "docs/proof/pp-0002.md"],
            declared.Select(a => a.Path));
        Assert.Equal(1, adapter.Stats.EpisodesClosed);
        Assert.Equal(2, adapter.Stats.ArtifactsDeclared);
        Assert.Equal(EpisodeState.Closed, store.FindEpisode(episodeId)!.State);
    }

    /// <summary>
    /// The attribute is optional, and omitting it costs an agent nothing it had before.
    /// </summary>
    /// <remarks>
    /// The normal case for every harness that never adopts this. The episode closes exactly as it
    /// did, and its scorecard stays honestly Not Scored.
    /// </remarks>
    [Fact]
    public void AnEpisodeThatDeclaresNothingClosesExactlyAsBefore()
    {
        var (adapter, store) = Opened();
        var episodeId = EpisodeId(store);

        adapter.Apply(new ContractEpisodeClose("ext-1", CloseAttrs("Completed", artifacts: null), At + 2, 3));

        Assert.Empty(store.DeclaredArtifactsFor(episodeId));
        Assert.Equal(1, adapter.Stats.EpisodesClosed);
        Assert.Equal(0, adapter.Stats.ArtifactsDeclared);
        Assert.Equal(0, adapter.Stats.Quarantined);
    }

    // ---------------------------------------------------------------- refusals

    /// <summary>
    /// A malformed optional attribute quarantines the LINE — it does not close while dropping it.
    /// </summary>
    /// <remarks>
    /// <para>Closing while discarding the evidence would leave the agent believing it declared a
    /// Proof Pack and the product silently disagreeing, with no channel to tell either of them. That
    /// is the silent-disagreement failure the registration correction exists to prevent, one level
    /// down.</para>
    ///
    /// <para>The episode stays OPEN, which is what makes the refusal recoverable: a corrected
    /// re-close works, and until then the scorer reports an episode that never closed, honestly and
    /// with the reason.</para>
    /// </remarks>
    [Fact]
    public void AMalformedArtifactListQuarantinesTheCloseRatherThanDroppingTheEvidence()
    {
        var (adapter, store) = Opened();
        var episodeId = EpisodeId(store);

        adapter.Apply(new ContractEpisodeClose("ext-1", CloseAttrs("Completed", "   "), At + 2, 3));

        Assert.Equal(1, adapter.Stats.Quarantined);
        Assert.Equal(0, adapter.Stats.EpisodesClosed);
        Assert.Empty(store.DeclaredArtifactsFor(episodeId));
        Assert.Equal(EpisodeState.Active, store.FindEpisode(episodeId)!.State);
    }

    /// <summary>And the corrected re-close then works, so a refusal is not a lost episode.</summary>
    [Fact]
    public void ACorrectedRecloseSucceedsAfterAQuarantine()
    {
        var (adapter, store) = Opened();
        var episodeId = EpisodeId(store);

        adapter.Apply(new ContractEpisodeClose("ext-1", CloseAttrs("Completed", "   "), At + 2, 3));
        adapter.Apply(new ContractEpisodeClose(
            "ext-1", CloseAttrs("Completed", "docs/proof/pp-0001.md"), At + 3, 4));

        Assert.Equal(1, adapter.Stats.EpisodesClosed);
        Assert.Equal("docs/proof/pp-0001.md", Assert.Single(store.DeclaredArtifactsFor(episodeId)).Path);
    }

    /// <summary>
    /// An over-long list is refused whole rather than truncated to the cap.
    /// </summary>
    /// <remarks>
    /// The bound is a resource bound on writes from outside the product, and truncating it would
    /// store a partial evidence list that reads as a complete one.
    /// </remarks>
    [Fact]
    public void AnOverlongListIsRefusedWholeRatherThanCapped()
    {
        var (adapter, store) = Opened();
        var episodeId = EpisodeId(store);
        var tooMany = string.Join("\n",
            Enumerable.Range(0, DeclaredArtifactBounds.MaxPaths + 1).Select(i => $"docs/proof/{i}.md"));

        adapter.Apply(new ContractEpisodeClose("ext-1", CloseAttrs("Completed", tooMany), At + 2, 3));

        Assert.Equal(1, adapter.Stats.Quarantined);
        Assert.Empty(store.DeclaredArtifactsFor(episodeId));
    }

    /// <summary>
    /// An unregistered session cannot declare evidence, for the reason it cannot open an episode.
    /// </summary>
    /// <remarks>
    /// Evidence attributed to a session that was never admitted has no one behind it. Registration
    /// is where trust is decided, and this is the same refusal an <c>episode-open</c> gets.
    /// </remarks>
    [Fact]
    public void AnUnregisteredSessionDeclaresNothing()
    {
        var (adapter, store) = Opened();

        adapter.Apply(new ContractEpisodeClose(
            "ext-nobody", CloseAttrs("Completed", "docs/proof/pp-0001.md"), At + 2, 3));

        Assert.Empty(store.DeclaredArtifactsFor(EpisodeId(store)));
        Assert.Equal(1, adapter.Stats.Unknown);
    }

    // ------------------------------------------------- untrusted, and stored as sent

    /// <summary>
    /// A path that escapes the repository is stored verbatim, not rejected and not resolved.
    /// </summary>
    /// <remarks>
    /// <para>The property the whole design rests on: this side records what was <b>said</b>, the
    /// scoring side decides what is <b>true</b>. Rejecting it here would feel safer and would destroy
    /// the only evidence separating an agent that lied from a file that moved — and it would put a
    /// security decision in a parser with no repository root to check against.</para>
    ///
    /// <para>Nothing on this path opens, resolves or stats the string. It is untrusted data, handled
    /// exactly like board content.</para>
    /// </remarks>
    [Fact]
    public void AnEscapingPathIsRecordedVerbatimForTheVerifierToRefuse()
    {
        var (adapter, store) = Opened();
        var episodeId = EpisodeId(store);

        adapter.Apply(new ContractEpisodeClose(
            "ext-1", CloseAttrs("Completed", "../../../etc/passwd"), At + 2, 3));

        Assert.Equal("../../../etc/passwd", Assert.Single(store.DeclaredArtifactsFor(episodeId)).Path);
    }

    /// <summary>Declaration order survives, so a reader sees what the agent listed first.</summary>
    [Fact]
    public void DeclarationOrderIsPreserved()
    {
        var (adapter, store) = Opened();
        var episodeId = EpisodeId(store);

        adapter.Apply(new ContractEpisodeClose(
            "ext-1", CloseAttrs("Completed", "z.md\na.md\nm.md"), At + 2, 3));

        Assert.Equal(["z.md", "a.md", "m.md"], store.DeclaredArtifactsFor(episodeId).Select(a => a.Path));
    }
}
