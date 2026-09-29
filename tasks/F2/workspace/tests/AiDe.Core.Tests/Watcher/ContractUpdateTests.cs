using AiDe.Core.Watcher;

namespace AiDe.Core.Tests.Watcher;

/// <summary>
/// The <c>update</c> event kind: harness and model learned after registration.
/// </summary>
/// <remarks>
/// <para><b>The gap it closes.</b> AI-DE registers a terminal before knowing what runs inside it,
/// and the model is knowable only by the agent — chosen inside the session and changeable
/// mid-session. A repeat <c>register</c> cannot carry it: the attributes are discarded, which is
/// correct for a duplicate but leaves the model unrecordable for every AI-DE-launched session
/// (<c>CoordinationContractTests.Apply_DuplicateRegister_DiscardsTheSecondAttributes_ItDoesNotMerge</c>).
/// </para>
///
/// <para><b>Additive within <c>loomkeeper/1</c>.</b> The parser already skips a valid line whose
/// kind it does not handle, so an older reader ignores an update rather than rejecting the log.</para>
/// </remarks>
public sealed class ContractUpdateTests
{
    private const double At = 1_700_000_000d;

    private static Dictionary<string, string?> RegisterAttrs() => new(StringComparer.Ordinal)
    {
        [OtelAttributes.RepoPath] = "C:/repos/app",
        [OtelAttributes.RepoDisplay] = "app",
        [OtelAttributes.WorktreeBranch] = "main",
        [OtelAttributes.WorktreePath] = "C:/repos/app",
        [OtelAttributes.TerminalId] = "term-1",
        [OtelAttributes.AgentName] = "claude",
    };

    private static (InjectedContractIngest adapter, InMemoryWatcherObservationStore store) NewAdapter()
    {
        var store = new InMemoryWatcherObservationStore();
        var clock = new FakeMonotonicClock();
        var n = 0;
        var registrar = new TrustedRegistrar(store, new SequentialCapabilityFactory(), clock, () => $"session-{++n}");
        return (new InjectedContractIngest(new IngestHost(store, registrar, new FixedTimeProvider(DateTimeOffset.UnixEpoch.AddSeconds(At)))), store);
    }

    [Fact]
    public void AnUpdate_AddsTheModelARegisterCouldNotCarry()
    {
        var (adapter, store) = NewAdapter();
        adapter.Apply(new ContractRegister("ext-1", RegisterAttrs(), At, 1));

        Assert.Null(store.FindSession("session-1")!.Binding.Model);

        adapter.Apply(new ContractUpdate("ext-1", new Dictionary<string, string?>(StringComparer.Ordinal)
        {
            [OtelAttributes.ServiceName] = "claude-code",
            [OtelAttributes.GenAiModel] = "claude-opus-5",
        }, At + 5, 2));

        var binding = store.FindSession("session-1")!.Binding;
        Assert.Equal("claude-opus-5", binding.Model!.Name);
        Assert.Equal("claude-code", binding.Harness!.Name);
        Assert.Equal(1, adapter.Stats.Updated);
    }

    /// <summary>
    /// An update does not raise trust, however convincing its harness claim.
    /// </summary>
    /// <remarks>
    /// The coordination log is a local, forgeable file (ADR-0007). A registration carrying a harness
    /// is <c>Verified</c> because it arrived through the registrar; the same string arriving later on
    /// a file is evidence about the HARNESS, not about the trustworthiness of the claim. Promoting
    /// here would let anything that can append to a file upgrade its own classification.
    /// </remarks>
    [Fact]
    public void AnUpdate_DoesNotPromoteTrust()
    {
        var (adapter, store) = NewAdapter();
        adapter.Apply(new ContractRegister("ext-1", RegisterAttrs(), At, 1));   // no harness -> Asserted

        Assert.Equal(TrustClassification.Asserted, store.FindSession("session-1")!.Binding.Trust);

        adapter.Apply(new ContractUpdate("ext-1", new Dictionary<string, string?>(StringComparer.Ordinal)
        {
            [OtelAttributes.ServiceName] = "claude-code",
        }, At + 5, 2));

        Assert.Equal(TrustClassification.Asserted, store.FindSession("session-1")!.Binding.Trust);
    }

    [Fact]
    public void AnUpdate_CannotRestateIdentity()
    {
        var (adapter, store) = NewAdapter();
        adapter.Apply(new ContractRegister("ext-1", RegisterAttrs(), At, 1));

        adapter.Apply(new ContractUpdate("ext-1", new Dictionary<string, string?>(StringComparer.Ordinal)
        {
            [OtelAttributes.GenAiModel] = "some-model",
            [OtelAttributes.RepoPath] = "C:/repos/SOMEWHERE-ELSE",
            [OtelAttributes.WorktreeBranch] = "attacker",
        }, At + 5, 2));

        var binding = store.FindSession("session-1")!.Binding;
        // The identity is unchanged by the update — compared through the canonicaliser, since the
        // stored key is canonical and the literal here is one of several spellings of it.
        Assert.Equal(
            new RepositoryIdentity("C:/repos/app", "app").CanonicalPath,
            binding.Repository.CanonicalPath);
        Assert.Equal("main", binding.Worktree.Branch);
        Assert.Equal("some-model", binding.Model!.Name);   // the one field it may carry
    }

    [Fact]
    public void AnUpdateForAnUnknownSession_IsDroppedAndCounted()
    {
        var (adapter, _) = NewAdapter();

        adapter.Apply(new ContractUpdate("never-registered", new Dictionary<string, string?>(StringComparer.Ordinal)
        {
            [OtelAttributes.GenAiModel] = "m",
        }, At, 1));

        Assert.Equal(0, adapter.Stats.Updated);
        Assert.Equal(1, adapter.Stats.Unknown);
    }

    [Fact]
    public void TheParserReadsAnUpdateLine_WithoutABumpedVersion()
    {
        var line = "{\"kind\":\"update\",\"contract\":\"" + CoordContract.Version
            + "\",\"session\":\"ext-1\",\"at\":1,\"seq\":2,"
            + "\"attrs\":{\"gen_ai.request.model\":\"claude-opus-5\"}}";

        var events = CoordContractParser.Parse(line);

        var update = Assert.IsType<ContractUpdate>(Assert.Single(events));
        Assert.Equal("ext-1", update.ExternalSessionId);
        Assert.Equal("claude-opus-5", update.Attributes[OtelAttributes.GenAiModel]);
    }
}
