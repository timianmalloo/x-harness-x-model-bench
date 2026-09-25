using AiDe.Core.Watcher;

namespace AiDe.Core.Tests.Watcher;

/// <summary>
/// LK-MAP-01..10 - the ingest wire's deterministic core (design-watcher-ingest-wire). Proves the OTel
/// span and registration mappings established by spike S1, the honest Not-Recorded degradation, the
/// LK-0004 malformed-event guard, and the pinned-schema regression gate (A6).
/// </summary>
public sealed class OtelSpanMapperTests
{
    private static readonly DateTimeOffset At = DateTimeOffset.UnixEpoch;

    private static Dictionary<string, string?> FullRegistration() => new(StringComparer.Ordinal)
    {
        [OtelAttributes.RepoPath] = "C:/repos/ai-de",
        [OtelAttributes.RepoDisplay] = "ai-de",
        [OtelAttributes.WorktreeBranch] = "main",
        [OtelAttributes.WorktreePath] = "C:/repos/ai-de",
        [OtelAttributes.TerminalId] = "term-1",
        [OtelAttributes.AgentName] = "claude-code",
        [OtelAttributes.ServiceName] = "claude-code",
        [OtelAttributes.ServiceVersion] = "1.0.0",
        [OtelAttributes.GenAiModel] = "claude-opus-4-8",
        [OtelAttributes.GenAiModelVersion] = "2026-08",
    };

    [Fact]
    public void MapSpan_ValidSpan_MapsAllFields()
    {
        var span = new HarnessSpan("a6651377534188dcca9aa2f3db16f798", "cca9aa2f3db16f79", "chat.completion",
            new Dictionary<string, string?>(StringComparer.Ordinal) { [OtelAttributes.SessionId] = "cc-7f3a" });

        var observed = OtelSpanMapper.MapSpan(span, At);

        Assert.Equal("cc-7f3a", observed.SessionId);
        Assert.Equal("a6651377534188dcca9aa2f3db16f798", observed.TraceId);
        Assert.Equal("cca9aa2f3db16f79", observed.SourceSpanId);
        Assert.Equal("chat.completion", observed.OperationName);
        Assert.Equal(At, observed.RecordedAt);
    }

    [Fact]
    public void MapSpan_NoSessionId_ThrowsMalformed()
    {
        var span = new HarnessSpan("trace", "span", "op",
            new Dictionary<string, string?>(StringComparer.Ordinal));

        var ex = Assert.Throws<WatcherException>(() => OtelSpanMapper.MapSpan(span, At));

        Assert.Equal(WatcherErrorCodes.MalformedEvent, ex.Code);
    }

    [Fact]
    public void MapRegistration_Full_MapsHarnessModelAndVerifiedTrust()
    {
        var binding = OtelSpanMapper.MapRegistration(new HarnessRegistration(FullRegistration()));

        // Compared against the product's own canonicalisation, not a spelling. RepositoryIdentity
        // normalises its path on construction (C2), so asserting the raw literal would be asserting
        // that the identity does NOT canonicalise — the opposite of what the type promises.
        Assert.Equal(
            new RepositoryIdentity("C:/repos/ai-de", "ai-de").CanonicalPath,
            binding.Repository.CanonicalPath);
        Assert.Equal("claude-code", binding.Harness!.Name);
        Assert.Equal("1.0.0", binding.Harness.Version);
        Assert.Equal("claude-opus-4-8", binding.Model!.Name);
        Assert.Equal(TrustClassification.Verified, binding.Trust);
    }

    [Fact]
    public void MapRegistration_NoHarnessOrModel_IsNotRecordedAndAsserted()
    {
        var attrs = FullRegistration();
        attrs.Remove(OtelAttributes.ServiceName);
        attrs.Remove(OtelAttributes.ServiceVersion);
        attrs.Remove(OtelAttributes.GenAiModel);
        attrs.Remove(OtelAttributes.GenAiModelVersion);

        var binding = OtelSpanMapper.MapRegistration(new HarnessRegistration(attrs));

        Assert.Null(binding.Harness);
        Assert.Null(binding.Model);
        Assert.Equal(TrustClassification.Asserted, binding.Trust);
    }

    [Theory]
    [InlineData(OtelAttributes.RepoPath)]
    [InlineData(OtelAttributes.WorktreeBranch)]
    [InlineData(OtelAttributes.TerminalId)]
    [InlineData(OtelAttributes.AgentName)]
    public void MapRegistration_MissingRequiredAttribute_ThrowsMalformed(string missing)
    {
        var attrs = FullRegistration();
        attrs.Remove(missing);

        var ex = Assert.Throws<WatcherException>(
            () => OtelSpanMapper.MapRegistration(new HarnessRegistration(attrs)));

        Assert.Equal(WatcherErrorCodes.MalformedEvent, ex.Code);
    }

    [Fact]
    public void MapRegistration_BlankRequiredAttribute_ThrowsMalformed()
    {
        var attrs = FullRegistration();
        attrs[OtelAttributes.AgentName] = "   ";

        var ex = Assert.Throws<WatcherException>(
            () => OtelSpanMapper.MapRegistration(new HarnessRegistration(attrs)));

        Assert.Equal(WatcherErrorCodes.MalformedEvent, ex.Code);
    }

    // A6 - the OTel GenAI vocabulary is Development-status upstream, so its keys are pinned here.
    // A silent upstream rename must fail this gate rather than break ingest in production (spike S1).
    [Fact]
    public void OtelAttributes_PinnedSchemaSnapshot_IsUnchanged()
    {
        Assert.Equal("session.id", OtelAttributes.SessionId);
        Assert.Equal("service.name", OtelAttributes.ServiceName);
        Assert.Equal("service.version", OtelAttributes.ServiceVersion);
        Assert.Equal("gen_ai.request.model", OtelAttributes.GenAiModel);
        Assert.Equal("gen_ai.model.version", OtelAttributes.GenAiModelVersion);
        Assert.Equal("repo.canonical_path", OtelAttributes.RepoPath);
        Assert.Equal("repo.display_name", OtelAttributes.RepoDisplay);
        Assert.Equal("worktree.branch", OtelAttributes.WorktreeBranch);
        Assert.Equal("worktree.path", OtelAttributes.WorktreePath);
        Assert.Equal("terminal.id", OtelAttributes.TerminalId);
        Assert.Equal("agent.name", OtelAttributes.AgentName);
    }

    [Fact]
    public void Mapper_ComposesThroughRegistrarAndIngest()
    {
        // The wire's mapping composes with the already-built core through the real in-memory store.
        var store = new InMemoryWatcherObservationStore();
        var registrar = new TrustedRegistrar(store, new SequentialCapabilityFactory(), new FakeMonotonicClock(), () => "cc-7f3a");
        var ingest = new SpanIngest(store, registrar);

        var registered = registrar.Register(OtelSpanMapper.MapRegistration(new HarnessRegistration(FullRegistration())));

        var span = OtelSpanMapper.MapSpan(
            new HarnessSpan("trace-1", "span-1", "chat.completion",
                new Dictionary<string, string?>(StringComparer.Ordinal) { [OtelAttributes.SessionId] = registered.SessionId }),
            At);

        Assert.Equal(IngestOutcome.Accepted, ingest.Ingest(registered.SessionId, registered.Capability, span));
        Assert.Equal("claude-opus-4-8", registered.Binding.Model!.Name);
        Assert.Equal(1, store.SpanCount(registered.SessionId));
    }
}
