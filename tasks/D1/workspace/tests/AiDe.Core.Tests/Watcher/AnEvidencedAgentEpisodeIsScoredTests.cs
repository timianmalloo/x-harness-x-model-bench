using AiDe.Core.Watcher;

namespace AiDe.Core.Tests.Watcher;

/// <summary>
/// The last link: an agent that declares a real Proof Pack is scored on the evidence.
/// </summary>
/// <remarks>
/// <para><b>What this closes.</b> <c>ClosedEpisodeScoring</c> built its evidence with a hardcoded
/// <c>HasProofPack: false</c> — an absence asserted without looking. Every agent episode therefore
/// scored Not Scored, and would have kept doing so <i>after</i> agents became instrumented, because
/// nothing on that path would have noticed. The gap was closed on the product's side before agents
/// got the chance to close it on theirs.</para>
///
/// <para><b>The four states, kept apart.</b> Declared-and-real, declared-and-absent,
/// declared-but-escaping, and nothing-declared are different facts, and only the first is evidence.
/// Collapsing any of the other three into "the agent did badly" is the shape this whole slice
/// exists to prevent.</para>
/// </remarks>
public sealed class AnEvidencedAgentEpisodeIsScoredTests : IDisposable
{
    private const double At = 1000;
    private readonly string _repository = NewDirectory();

    public void Dispose()
    {
        try
        {
            if (Directory.Exists(_repository))
            {
                Directory.Delete(_repository, recursive: true);
            }
        }
        catch (IOException)
        {
        }
    }

    private Dictionary<string, string?> Attrs() => new(StringComparer.Ordinal)
    {
        [OtelAttributes.RepoPath] = _repository,
        [OtelAttributes.RepoDisplay] = "app",
        [OtelAttributes.WorktreePath] = _repository,
        [OtelAttributes.WorktreeBranch] = "main",
        [OtelAttributes.TerminalId] = "term-1",
        [OtelAttributes.AgentName] = "agent-ext",
        [OtelAttributes.ServiceName] = "claude-code",
    };

    private (InjectedContractIngest Adapter, InMemoryWatcherObservationStore Store) Circuit()
    {
        var store = new InMemoryWatcherObservationStore();
        var n = 0;
        var registrar = new TrustedRegistrar(
            store, new SequentialCapabilityFactory(), new FakeMonotonicClock(), () => $"session-{++n}");
        var host = new IngestHost(store, registrar, new FixedTimeProvider(DateTimeOffset.UnixEpoch.AddSeconds(At)));

        return (new InjectedContractIngest(host), store);
    }

    private void CloseWith(InjectedContractIngest adapter, string? artifacts)
    {
        adapter.Apply(new ContractRegister("ext-1", Attrs(), At, 1));
        adapter.Apply(new ContractEpisodeOpen(
            "ext-1",
            new Dictionary<string, string?>(StringComparer.Ordinal)
            {
                [CoordContract.EpisodeAttributes.Goal] = "g",
                [CoordContract.EpisodeAttributes.DoneWhen] = "d",
            },
            At + 1, 2));

        var close = new Dictionary<string, string?>(StringComparer.Ordinal)
        {
            [CoordContract.EpisodeAttributes.Outcome] = "completed",
        };

        if (artifacts is not null)
        {
            close[CoordContract.EpisodeAttributes.Artifacts] = artifacts;
        }

        adapter.Apply(new ContractEpisodeClose("ext-1", close, At + 2, 3));
    }

    private string GivenProofPack(string relative)
    {
        var full = Path.Combine(_repository, relative.Replace('/', Path.DirectorySeparatorChar));
        Directory.CreateDirectory(Path.GetDirectoryName(full)!);
        File.WriteAllText(full, "proof");
        return full;
    }

    private static bool HasVerificationPath(InMemoryWatcherObservationStore store)
    {
        var scored = Assert.Single(store.AllScoredEpisodes());
        return scored.Scorecard.Verdict is not WeaveVerdict.NotScored;
    }

    [Fact]
    public void ADeclaredAndCommittedProofPackIsEvidence()
    {
        // THE LINK. Before this, the verdict was Not Scored no matter what the agent committed.
        GivenProofPack("docs/proof/ep-1.md");

        var (adapter, store) = Circuit();
        CloseWith(adapter, "docs/proof/ep-1.md");

        Assert.Equal(1, ClosedEpisodeScoring.Run(store, TimeProvider.System));
        Assert.True(HasVerificationPath(store), "a real committed Proof Pack was not treated as evidence");
    }

    [Fact]
    public void ADeclaredPathThatIsNotThereIsNotEvidence_ButStillScores()
    {
        // The peer's constraint, asserted: a path that fails verification means THE EVIDENCE WAS NOT
        // THERE, which is a fact about the evidence. It must not make the episode unscoreable, or a
        // moved file would look like a protocol error — a claim about the agent's format instead.
        var (adapter, store) = Circuit();
        CloseWith(adapter, "docs/proof/never-committed.md");

        Assert.Equal(1, ClosedEpisodeScoring.Run(store, TimeProvider.System));

        var scored = Assert.Single(store.AllScoredEpisodes());
        Assert.Equal(WeaveVerdict.NotScored, scored.Scorecard.Verdict);
        Assert.NotEmpty(scored.Scorecard.Headline);
    }

    [Fact]
    public void APathEscapingTheRepositoryIsNotEvidence_EvenThoughTheFileExists()
    {
        // The security boundary reaching the scoring path. A real Proof Pack in a NEIGHBOURING
        // directory must not score this session, or one repository's evidence becomes another's.
        var outside = NewDirectory();

        try
        {
            var escaped = Path.Combine(outside, "docs", "proof");
            Directory.CreateDirectory(escaped);
            File.WriteAllText(Path.Combine(escaped, "ep-1.md"), "someone else's evidence");

            var (adapter, store) = Circuit();
            CloseWith(adapter, Path.Combine(outside, "docs", "proof", "ep-1.md"));

            ClosedEpisodeScoring.Run(store, TimeProvider.System);

            Assert.False(HasVerificationPath(store), "a file outside the repository was accepted as evidence");
        }
        finally
        {
            try
            {
                Directory.Delete(outside, recursive: true);
            }
            catch (IOException)
            {
            }
        }
    }

    [Fact]
    public void DeclaringNothingIsStillNotScored_AndThatIsNowObserved()
    {
        // The state the hardcoded literal always produced. It is still Not Scored — but now because
        // the store was ASKED and held nothing, rather than because a constant said so.
        var (adapter, store) = Circuit();
        CloseWith(adapter, artifacts: null);

        ClosedEpisodeScoring.Run(store, TimeProvider.System);

        Assert.Empty(store.DeclaredArtifactsFor(Assert.Single(store.AllEpisodes()).EpisodeId));
        Assert.False(HasVerificationPath(store));
    }

    [Fact]
    public void AnUnverifiableRepositoryIsNotEvidenceOfAbsence()
    {
        // THE HONEST LIMIT, pinned rather than hidden. When the repository cannot be read, the
        // verifier answers Unverifiable — but EpisodeEvidence.HasProofPack is a bool, so the
        // distinction dies at that boundary and the episode looks unevidenced.
        //
        // That is acceptable only while a registered session's repository is a local path this
        // process just read. This assertion documents the limit at the verifier, where the truth
        // still exists, so the day a remote registrant appears the gap has a name and a location
        // rather than being rediscovered from a wrong score.
        var unreachable = Path.Combine(Path.GetTempPath(), "aide-gone-" + Guid.NewGuid().ToString("N")[..8]);

        Assert.Equal(
            ProofPackVerdict.Unverifiable,
            ProofPackVerifier.Verify(unreachable, "docs/proof/ep-1.md"));
    }

    private static string NewDirectory()
    {
        var path = Path.Combine(Path.GetTempPath(), "aide-ev-" + Guid.NewGuid().ToString("N")[..8]);
        Directory.CreateDirectory(path);
        return path;
    }
}
