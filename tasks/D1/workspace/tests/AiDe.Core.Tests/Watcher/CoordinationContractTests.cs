using System.Text;
using System.Text.Json;
using AiDe.Core.Watcher;

namespace AiDe.Core.Tests.Watcher;

/// <summary>
/// LK-COORD-01..N - the injected coordination contract (design-watcher-coordination-contract, slice 2).
/// The claims: a non-AI-Forward session registers and heartbeats over the coord-core append log and
/// appears identically in the fact store (US-5); the parser tolerantly reads the real writer shape
/// (LOG-A leading newline, CRLF, blank/malformed skip, version pin, sort by at/seq); and the capability
/// lives in the adapter, so a heartbeat for a session never registered here is dropped (ADR-0020 trusted-registrar-harness-model-identity).
/// </summary>
public sealed class CoordinationContractTests
{
    private static readonly DateTimeOffset At = DateTimeOffset.UnixEpoch;

    // --- fixtures -----------------------------------------------------------------------------

    private static Dictionary<string, string?> RegisterAttrs(string? harness = "claude-code", string? model = "opus-4-8")
    {
        var attrs = new Dictionary<string, string?>(StringComparer.Ordinal)
        {
            [OtelAttributes.RepoPath] = "C:/repos/ext-app",
            [OtelAttributes.RepoDisplay] = "ext-app",
            [OtelAttributes.WorktreeBranch] = "main",
            [OtelAttributes.WorktreePath] = "C:/repos/ext-app",
            [OtelAttributes.TerminalId] = "term-9",
            [OtelAttributes.AgentName] = "agent-ext",
        };
        if (harness is not null)
        {
            attrs[OtelAttributes.ServiceName] = harness;
            attrs[OtelAttributes.ServiceVersion] = "1.2.0";
        }
        if (model is not null)
        {
            attrs[OtelAttributes.GenAiModel] = model;
        }

        return attrs;
    }

    private static string RegisterLine(string session, double at, int seq, string version = CoordContract.Version,
        IReadOnlyDictionary<string, string?>? attrs = null)
    {
        var payload = new Dictionary<string, object?>
        {
            ["kind"] = "register",
            ["contract"] = version,
            ["session"] = session,
            ["at"] = at,
            ["seq"] = seq,
            ["attrs"] = (attrs ?? RegisterAttrs()).ToDictionary(kv => kv.Key, kv => kv.Value),
        };
        return JsonSerializer.Serialize(payload);
    }

    private static string HeartbeatLine(string session, double at, int seq, string version = CoordContract.Version)
        => JsonSerializer.Serialize(new Dictionary<string, object?>
        {
            ["kind"] = "heartbeat", ["contract"] = version, ["session"] = session, ["at"] = at, ["seq"] = seq,
        });

    private static (InjectedContractIngest adapter, InMemoryWatcherObservationStore store, LivenessProjection liveness, FakeMonotonicClock clock)
        NewAdapter()
    {
        var store = new InMemoryWatcherObservationStore();
        var clock = new FakeMonotonicClock();
        var n = 0;
        var registrar = new TrustedRegistrar(store, new SequentialCapabilityFactory(), clock, () => $"session-{++n}");
        var host = new IngestHost(store, registrar, new FixedTimeProvider(At));
        var liveness = new LivenessProjection(store, clock, TimeSpan.FromSeconds(30));
        return (new InjectedContractIngest(host), store, liveness, clock);
    }

    // --- parser (D1) --------------------------------------------------------------------------

    [Fact]
    public void Parse_RegisterAndHeartbeat_ReturnsBothSortedByAt()
    {
        var jsonl = RegisterLine("ext-1", 1000, 1) + "\n" + HeartbeatLine("ext-1", 1030, 2) + "\n";

        var events = CoordContractParser.Parse(jsonl, out var stats);

        Assert.Equal(2, events.Count);
        Assert.Equal(2, stats.Parsed);
        var register = Assert.IsType<ContractRegister>(events[0]);
        Assert.Equal("ext-1", register.ExternalSessionId);
        Assert.Equal("claude-code", register.Attributes[OtelAttributes.ServiceName]);
        Assert.IsType<ContractHeartbeat>(events[1]);
    }

    [Fact]
    public void Parse_MalformedLine_IsSkippedAndCounted_OthersSurvive()
    {
        var jsonl = "{ not json\n" + HeartbeatLine("ext-1", 1000, 1) + "\n";

        var events = CoordContractParser.Parse(jsonl, out var stats);

        Assert.Single(events);
        Assert.Equal(1, stats.Malformed);
    }

    [Fact]
    public void Parse_BlankAndLogALeadingNewlineAndCrlf_AreTolerated()
    {
        // A LOG-A leading newline before the register, a CRLF terminator, and a blank line.
        var jsonl = "\n" + RegisterLine("ext-1", 1000, 1) + "\r\n" + "\n" + HeartbeatLine("ext-1", 1010, 2) + "\n";

        var events = CoordContractParser.Parse(jsonl, out var stats);

        Assert.Equal(2, events.Count);
        Assert.Equal(0, stats.Malformed);
    }

    [Fact]
    public void Parse_WrongContractVersion_IsRejectedAndCounted()
    {
        var jsonl = HeartbeatLine("ext-1", 1000, 1, version: "loomkeeper/2") + "\n"
                    + HeartbeatLine("ext-1", 1005, 2) + "\n";

        var events = CoordContractParser.Parse(jsonl, out var stats);

        Assert.Single(events);
        Assert.Equal(1, stats.VersionRejected);
    }

    [Fact]
    public void Parse_OutOfOrderLines_AreSortedByAtThenSeq()
    {
        var jsonl = HeartbeatLine("ext-1", 1030, 9) + "\n"
                    + RegisterLine("ext-1", 1000, 1) + "\n"
                    + HeartbeatLine("ext-1", 1005, 5) + "\n";

        var events = CoordContractParser.Parse(jsonl);

        Assert.Collection(events,
            e => Assert.Equal(1000, e.At),
            e => Assert.Equal(1005, e.At),
            e => Assert.Equal(1030, e.At));
    }

    [Fact]
    public void Parse_UnknownKindWithValidVersion_IsSilentlySkipped_NotMalformed()
    {
        // A future board post shares the same log; it is not this parser's event, not an error.
        var board = JsonSerializer.Serialize(new Dictionary<string, object?>
        {
            ["kind"] = "question", ["contract"] = CoordContract.Version, ["session"] = "ext-1", ["at"] = 1000.0, ["seq"] = 1,
        });
        var jsonl = board + "\n" + HeartbeatLine("ext-1", 1010, 2) + "\n";

        var events = CoordContractParser.Parse(jsonl, out var stats);

        Assert.Single(events);
        Assert.Equal(0, stats.Malformed);
        Assert.Equal(0, stats.VersionRejected);
    }

    [Fact]
    public void Parse_RealCoordCoreByteShape_GoldenFixture()
    {
        // The exact sorted-key line shape the coord-core writer produces (spike S4 capture), with the
        // LOG-A leading newline. Proves the reader consumes the real writer's bytes, not a convenience shape.
        var golden = new StringBuilder();
        golden.Append("""{"agent":"claude-code","at":1000.0,"attrs":{"agent.name":"agent-ext","repo.canonical_path":"C:/repos/ext-app","repo.display_name":"ext-app","service.name":"claude-code","terminal.id":"term-9","worktree.branch":"main","worktree.path":"C:/repos/ext-app"},"contract":"loomkeeper/1","kind":"register","path":"-","seq":1,"session":"ext-1","wi":"WI-0"}""");
        golden.Append('\n').Append('\n'); // LOG-A leading newline before the next
        golden.Append("""{"agent":"claude-code","at":1030.0,"contract":"loomkeeper/1","kind":"heartbeat","path":"-","seq":2,"session":"ext-1","wi":"WI-0"}""");
        golden.Append('\n');

        var events = CoordContractParser.Parse(golden.ToString(), out var stats);

        Assert.Equal(2, stats.Parsed);
        var register = Assert.IsType<ContractRegister>(events[0]);
        Assert.Equal("claude-code", register.Attributes[OtelAttributes.ServiceName]);
        Assert.Equal("C:/repos/ext-app", register.Attributes[OtelAttributes.RepoPath]);
    }

    [Fact]
    public void ContractVersion_IsPinned() // A6: a bump must be a deliberate, gated change
        => Assert.Equal("loomkeeper/1", CoordContract.Version);

    // --- adapter (D1) -------------------------------------------------------------------------

    [Fact]
    public void Apply_Register_MintsSessionInTheStore_WithVerifiedTrust()
    {
        var (adapter, store, _, _) = NewAdapter();

        adapter.Apply(new ContractRegister("ext-1", RegisterAttrs(harness: "claude-code"), 1000, 1));

        Assert.Equal(1, adapter.Stats.Registered);
        var session = store.FindSession("session-1");
        Assert.NotNull(session);
        Assert.Equal(TrustClassification.Verified, session!.Binding.Trust);
    }

    [Fact]
    public void Apply_RegisterWithoutHarnessName_IsAssertedTrust()
    {
        var (adapter, store, _, _) = NewAdapter();

        adapter.Apply(new ContractRegister("ext-1", RegisterAttrs(harness: null), 1000, 1));

        Assert.Equal(TrustClassification.Asserted, store.FindSession("session-1")!.Binding.Trust);
    }

    [Fact]
    public void Apply_DuplicateRegister_IsIgnoredAndCounted()
    {
        var (adapter, _, _, _) = NewAdapter();

        adapter.Apply(new ContractRegister("ext-1", RegisterAttrs(), 1000, 1));
        adapter.Apply(new ContractRegister("ext-1", RegisterAttrs(), 1005, 2));

        Assert.Equal(1, adapter.Stats.Registered);
        Assert.Equal(1, adapter.Stats.DuplicateRegister);
    }

    /// <summary>
    /// A duplicate register is dropped ENTIRELY — its attributes are discarded, not merged.
    /// </summary>
    /// <remarks>
    /// <para><b>Why this exists beside the test above.</b>
    /// <see cref="Apply_DuplicateRegister_IsIgnoredAndCounted"/> passes the SAME attributes twice, so
    /// it proves the counters and cannot distinguish "ignored" from "merged" — it would pass
    /// identically if a second register enriched the first. That is DC-016: a control that cannot
    /// fail for the reason it matters.</para>
    ///
    /// <para><b>The question it answers.</b> AI-DE registers a terminal before knowing which harness
    /// or model runs inside it (<c>WorkbenchShell.IdentityFor</c> leaves both null). The obvious
    /// enrichment — let the agent re-register with <c>service.name</c> and
    /// <c>gen_ai.request.model</c> once it knows them — depends entirely on whether a second
    /// register merges.</para>
    ///
    /// <para><b>OBSERVED, 2026-09-01: it does not merge. The second register's attributes are
    /// discarded.</b> Recorded as an observation rather than a reading because this test is a
    /// genuine discriminator — it asserts <c>Harness</c> and <c>Model</c> are STILL null after an
    /// enriching re-register, so it <i>fails</i> if the behaviour is ever changed to merge. Run
    /// against the shipped implementation, both assertions held.</para>
    ///
    /// <para><b>Consequence, and it is load-bearing.</b> Enrichment-by-re-register cannot work, so
    /// the harness must be known at FIRST registration — which is why
    /// <c>docs/design/ux-agent-session-registration.md</c> makes the per-harness launch entry the
    /// only mechanism that can supply it, rather than one convenient option among several. §3.2 of
    /// that spec was written the other way round and this test corrected it.</para>
    /// </remarks>
    [Fact]
    public void Apply_DuplicateRegister_DiscardsTheSecondAttributes_ItDoesNotMerge()
    {
        var (adapter, store, _, _) = NewAdapter();

        // First: the shape AI-DE can emit — identity known, harness and model NOT known.
        adapter.Apply(new ContractRegister("ext-1", RegisterAttrs(harness: null, model: null), 1000, 1));

        var before = store.FindSession("session-1")!.Binding;
        Assert.Null(before.Harness);
        Assert.Null(before.Model);

        // Then: the enrichment an agent would send once it knows what it is.
        adapter.Apply(new ContractRegister("ext-1", RegisterAttrs(harness: "claude-code", model: "opus-4-8"), 1005, 2));

        var after = store.FindSession("session-1")!.Binding;
        Assert.Null(after.Harness);      // still null — the second register never reached the registrar
        Assert.Null(after.Model);
        Assert.Equal(1, adapter.Stats.Registered);
        Assert.Equal(1, adapter.Stats.DuplicateRegister);
    }

    [Fact]
    public void Apply_RegisterMissingRequiredIdentity_IsQuarantined_AndTheStreamSurvives()
    {
        var (adapter, store, _, _) = NewAdapter();
        var incomplete = new Dictionary<string, string?>(StringComparer.Ordinal)
        {
            [OtelAttributes.AgentName] = "agent-ext", // missing repo.canonical_path etc. -> LK-0004
        };

        adapter.Apply(new ContractRegister("ext-1", incomplete, 1000, 1));
        adapter.Apply(new ContractRegister("ext-2", RegisterAttrs(), 1005, 2)); // a good one still lands

        Assert.Equal(1, adapter.Stats.Quarantined);
        Assert.Equal(1, adapter.Stats.Registered);
    }

    [Fact]
    public void Apply_HeartbeatForRegisteredSession_RefreshesLivenessToAlive()
    {
        var (adapter, _, liveness, clock) = NewAdapter();

        adapter.Apply(new ContractRegister("ext-1", RegisterAttrs(), 1000, 1));
        Assert.Equal(LivenessState.Alive, liveness.Evaluate("session-1")); // registration is the first liveness tick

        clock.Advance(TimeSpan.FromSeconds(31));
        Assert.Equal(LivenessState.Stale, liveness.Evaluate("session-1")); // gone quiet

        adapter.Apply(new ContractHeartbeat("ext-1", 1030, 2)); // the heartbeat refreshes it

        Assert.Equal(1, adapter.Stats.Heartbeats);
        Assert.Equal(LivenessState.Alive, liveness.Evaluate("session-1"));
    }

    [Fact]
    public void Apply_HeartbeatForUnregisteredSession_IsDroppedAndCounted()
    {
        var (adapter, _, _, _) = NewAdapter();

        adapter.Apply(new ContractHeartbeat("never-registered", 1000, 1));

        Assert.Equal(1, adapter.Stats.Unknown);
        Assert.Equal(0, adapter.Stats.Heartbeats);
    }

    [Fact]
    public void Apply_SessionEnd_ForgetsTheMapping_SoALaterHeartbeatIsUnknown()
    {
        var (adapter, _, _, _) = NewAdapter();
        adapter.Apply(new ContractRegister("ext-1", RegisterAttrs(), 1000, 1));

        adapter.Apply(new ContractSessionEnd("ext-1", 1030, 2));
        adapter.Apply(new ContractHeartbeat("ext-1", 1040, 3)); // after end -> no mapping

        Assert.Equal(1, adapter.Stats.Unknown);
    }

    // --- end-to-end composition (E11: JSONL text -> parse -> adapter -> real registrar/store/liveness) ---

    [Fact]
    public void EndToEnd_JsonlRegisterThenHeartbeat_SessionIsAlive_ThenGoesStale()
    {
        var (adapter, store, liveness, clock) = NewAdapter();
        var jsonl = RegisterLine("ext-1", 1000, 1) + "\n" + HeartbeatLine("ext-1", 1030, 2) + "\n";

        adapter.ApplyAll(CoordContractParser.Parse(jsonl));

        Assert.NotNull(store.FindSession("session-1"));
        Assert.Equal(LivenessState.Alive, liveness.Evaluate("session-1"));

        clock.Advance(TimeSpan.FromSeconds(31)); // no further heartbeat
        Assert.Equal(LivenessState.Stale, liveness.Evaluate("session-1"));
    }
}
