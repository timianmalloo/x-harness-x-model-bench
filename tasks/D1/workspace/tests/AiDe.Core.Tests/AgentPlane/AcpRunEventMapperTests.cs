using System.Text.Json.Nodes;
using AiDe.Core.AgentPlane;

namespace AiDe.Core.Tests.AgentPlane;

/// <summary>
/// The ACP mapper, proven against <b>the real captured frame corpus</b> in
/// <c>spikes/acp-subscription-lane/frames/</c> — not against events this test wrote.
/// </summary>
/// <remarks>
/// <para><b>Why the corpus is the oracle.</b> A wire-contract test whose author also wrote the
/// input proves only that the author was self-consistent. The corpus is every frame captured
/// verbatim from live <c>claude-code</c> ACP sessions before any parse or re-serialization (the
/// two Phase-1 probes and CV-5.3's thought capture; the files are enumerated, never counted here — DC-184)
/// (<c>frames/PROVENANCE.md</c>), so a mapping assumption that the adapter does not share fails
/// here rather than in a governed run.</para>
///
/// <para><b>The corpus is read from the committed files, never restated inline.</b> A fixture that
/// retypes the data it is supposed to derive is defect class DC-021, and
/// <c>tools/verify-fixture-derivation.py</c> exists because it happened three times.</para>
///
/// <para><b>The round-trip check compares the whole JSON structure, not a handful of properties.</b>
/// Every leaf of the original frame — including empty objects, empty arrays and explicit nulls,
/// which a naive walker silently skips — must appear exactly once across <c>Body</c> and
/// <c>Ext</c>, with the same value, at a path that is a suffix of where it started. Equal leaf
/// counts on top of that means nothing was dropped <i>and</i> nothing was duplicated: the mapper
/// only ever lifts a subtree to a new root, it never renames, invents or copies a key.</para>
///
/// <para><b>What the corpus actually contains, against what the spike README first claimed.</b>
/// <c>_auth/status_update</c> is a <i>top-level method</i>; <c>usage_update</c> is a
/// <c>session/update</c> discriminator and not a method at all; <c>_session/goal</c> and
/// <c>_meta.jetbrains.air</c> never appear as traffic — they are declared capabilities inside the
/// <c>initialize</c> result. Tests here assert what was captured, and one asserts the absence, so
/// nobody re-adds a test for traffic that does not exist.</para>
/// </remarks>
public sealed class AcpRunEventMapperTests
{
    private const string RunId = "r-0912";
    private const string AgentId = "claude-code-lane";
    private static readonly DateTimeOffset ReceivedAt = new(2026, 9, 9, 18, 47, 0, TimeSpan.Zero);

    /// <summary>One captured line, with enough provenance for a failure to name it.</summary>
    private sealed record Frame(string File, int Line, string Raw);

    /// <summary>
    /// Walks up for the repository root, so the test does not depend on the runner's cwd — the same
    /// approach <c>WhatTheRealCorpusCanProduceTests</c> uses for the audit log.
    /// </summary>
    private static string CorpusDirectory() => AcpCorpus.Directory();

    /// <summary>The corpus file names, enumerated from disk rather than listed here (DC-021).</summary>
    public static TheoryData<string> CorpusFiles
    {
        get
        {
            var data = new TheoryData<string>();
            foreach (var path in Directory.EnumerateFiles(CorpusDirectory(), "*.jsonl").Order(StringComparer.Ordinal))
            {
                data.Add(Path.GetFileName(path));
            }

            return data;
        }
    }

    private static IReadOnlyList<Frame> Read(string fileName)
    {
        var path = Path.Combine(CorpusDirectory(), fileName);
        var frames = new List<Frame>();
        var lines = File.ReadAllLines(path);
        for (var i = 0; i < lines.Length; i++)
        {
            if (!string.IsNullOrWhiteSpace(lines[i]))
            {
                frames.Add(new Frame(fileName, i + 1, lines[i]));
            }
        }

        return frames;
    }

    private static IReadOnlyList<Frame> ReadAll()
        => Directory.EnumerateFiles(CorpusDirectory(), "*.jsonl")
            .Order(StringComparer.Ordinal)
            .SelectMany(p => Read(Path.GetFileName(p)))
            .ToList();

    /// <summary>
    /// Every leaf of a JSON tree as (path, value). Empty objects and arrays are leaves in their own
    /// right — <c>"rawInput": {}</c> and <c>"content": []</c> are both in the corpus, and a walker
    /// that only records scalars would let either vanish without the count moving.
    /// </summary>
    private static void Flatten(JsonNode? node, string path, List<KeyValuePair<string, string>> into)
    {
        switch (node)
        {
            case null:
                into.Add(new KeyValuePair<string, string>(path, "null"));
                break;
            case JsonObject o when o.Count == 0:
                into.Add(new KeyValuePair<string, string>(path, "{}"));
                break;
            case JsonObject o:
                foreach (var pair in o)
                {
                    Flatten(pair.Value, path + "." + pair.Key, into);
                }

                break;
            case JsonArray a when a.Count == 0:
                into.Add(new KeyValuePair<string, string>(path, "[]"));
                break;
            case JsonArray a:
                for (var i = 0; i < a.Count; i++)
                {
                    Flatten(a[i], path + "[" + i + "]", into);
                }

                break;
            default:
                into.Add(new KeyValuePair<string, string>(path, node.ToJsonString()));
                break;
        }
    }

    /// <summary>
    /// Flattens a mapped container. An empty container at the root contributes nothing: it is the
    /// absence of a payload, not a field that was in the frame.
    /// </summary>
    private static void FlattenRoot(JsonObject root, string name, List<KeyValuePair<string, string>> into)
    {
        if (root.Count > 0)
        {
            Flatten(root, name, into);
        }
    }

    private static string Relative(string mappedPath)
    {
        var dot = mappedPath.IndexOf('.', StringComparison.Ordinal);
        return dot < 0 ? string.Empty : mappedPath[dot..];
    }

    /// <summary>
    /// <b>The node's reason to exist.</b> Every frame in the corpus round-trips with no field lost
    /// and none invented.
    /// </summary>
    [Theory]
    [MemberData(nameof(CorpusFiles))]
    public void EveryCapturedFrameRoundTripsWithNoFieldLost(string fileName)
    {
        var frames = Read(fileName);
        Assert.NotEmpty(frames);

        var mapper = new AcpRunEventMapper(RunId, AgentId);
        foreach (var frame in frames)
        {
            var mapped = mapper.Map(frame.Raw, ReceivedAt);
            var where = $"{frame.File}:{frame.Line}";

            var original = new List<KeyValuePair<string, string>>();
            Flatten(JsonNode.Parse(frame.Raw), "$", original);

            var carried = new List<KeyValuePair<string, string>>();
            FlattenRoot(mapped.Body, "body", carried);
            FlattenRoot(mapped.Ext, "ext", carried);

            var remaining = new List<KeyValuePair<string, string>>(carried);
            foreach (var leaf in original)
            {
                var index = remaining.FindIndex(
                    m => leaf.Key.EndsWith(Relative(m.Key), StringComparison.Ordinal) && m.Value == leaf.Value);

                Assert.True(
                    index >= 0,
                    $"{where}: field lost — {leaf.Key} = {leaf.Value} appears in neither body nor ext");

                remaining.RemoveAt(index);
            }

            Assert.True(
                remaining.Count == 0,
                remaining.Count == 0
                    ? string.Empty
                    : $"{where}: {remaining.Count} field(s) invented or duplicated, first is {remaining[0].Key}");

            Assert.Equal(original.Count, carried.Count);
        }
    }

    /// <summary>
    /// <c>_auth/status_update</c> is real traffic and is <b>not</b> a v1 kind, so the whole frame
    /// survives under <c>ext</c> — §13's stated mitigation for adapter drift.
    /// </summary>
    /// <remarks>
    /// It arrives as a <b>top-level method</b>. That is the corrected reading of the spike README,
    /// and the assertion is written against the capture so a future adapter that moves it shows up
    /// here rather than in a governed run.
    /// </remarks>
    [Fact]
    public void UnrecognizedAuthStatusTrafficSurvivesWholeInExt()
    {
        var mapper = new AcpRunEventMapper(RunId, AgentId);
        var seen = 0;

        foreach (var frame in ReadAll())
        {
            var node = JsonNode.Parse(frame.Raw)!.AsObject();
            if (node["method"]?.GetValue<string>() != "_auth/status_update")
            {
                continue;
            }

            seen++;
            var mapped = mapper.Map(frame.Raw, ReceivedAt);

            Assert.Equal("acp._auth.status_update", mapped.Kind);
            Assert.Empty(mapped.Body);
            Assert.Equal("_auth/status_update", mapped.Ext["method"]!.GetValue<string>());
            Assert.NotNull(mapped.Ext["params"]!["authStatus"]);
        }

        Assert.True(seen > 0, "the corpus no longer contains _auth/status_update traffic");
    }

    /// <summary>
    /// <c>usage_update</c> is a <c>session/update</c> discriminator, <b>not</b> a top-level method.
    /// </summary>
    /// <remarks>
    /// Worth its own case because the README's phrase "non-schema-v1 traffic" reads as though it
    /// were a distinct wire method. It is not, and a mapper written to that reading would drop every
    /// usage frame on the floor.
    /// </remarks>
    [Fact]
    public void UsageUpdateIsASessionUpdateDiscriminatorNotAMethod()
    {
        var mapper = new AcpRunEventMapper(RunId, AgentId);
        var asDiscriminator = 0;

        foreach (var frame in ReadAll())
        {
            var node = JsonNode.Parse(frame.Raw)!.AsObject();

            Assert.NotEqual("usage_update", node["method"]?.GetValue<string>());

            if (node["params"]?["update"]?["sessionUpdate"]?.GetValue<string>() != "usage_update")
            {
                continue;
            }

            asDiscriminator++;
            var mapped = mapper.Map(frame.Raw, ReceivedAt);

            Assert.Equal("acp.session.update.usage_update", mapped.Kind);
            Assert.Empty(mapped.Body);
            Assert.Equal("usage_update", mapped.Ext["params"]!["update"]!["sessionUpdate"]!.GetValue<string>());
        }

        Assert.True(asDiscriminator > 0, "the corpus no longer contains usage_update frames");
    }

    /// <summary>
    /// <c>_session/goal</c> and <c>_meta.jetbrains.air</c> are <b>declared capabilities</b>, never
    /// observed traffic — so no test may claim to map them.
    /// </summary>
    /// <remarks>
    /// This asserts the absence deliberately. The spike README claimed both as frame kinds; the
    /// capture disproved it. Without a control the claim comes back, and the next author writes a
    /// handler for a frame the adapter has never sent. If a future capture does carry either, this
    /// goes red and the mapping question is reopened on evidence.
    /// </remarks>
    [Fact]
    public void SessionGoalAndJetbrainsAirAreCapabilitiesNotTraffic()
    {
        var initializeResults = 0;

        foreach (var frame in ReadAll())
        {
            var node = JsonNode.Parse(frame.Raw)!.AsObject();

            Assert.NotEqual("_session/goal", node["method"]?.GetValue<string>());
            Assert.Null(node["params"]?["_meta"]?["jetbrains"]);

            if (node["result"]?["_meta"]?["goal"] is not null)
            {
                initializeResults++;
                Assert.Equal("_session/goal", node["result"]!["_meta"]!["goal"]!["controlMethod"]!.GetValue<string>());
                Assert.NotNull(node["result"]!["_meta"]!["jetbrains"]!["air"]);
            }
        }

        Assert.True(initializeResults > 0, "the corpus no longer contains an initialize result to read _meta from");
    }

    /// <summary>
    /// <b>M1 (CV-5.3, Ruling 82).</b> A real <c>agent_thought_chunk</c> frame — captured into the
    /// corpus by <c>probe-thought.js</c> on 2026-09-13, never authored — maps to <c>agent.thought</c>
    /// with its text in <c>body.content.text</c>, exactly where an <c>agent_message_chunk</c>'s
    /// text sits (the shape the review's §9 left Inferred, now Verified from the frame); the
    /// console model's one text reader yields that text, and the joined thought is the puzzle's
    /// reasoning, not the answer.
    /// </summary>
    /// <remarks>
    /// <b>Red observed</b> before the row: <c>Expected: agent.thought · Actual:
    /// acp.session.update.agent_thought_chunk</c>, with an empty body.
    /// </remarks>
    [Fact]
    public void AnAgentThoughtChunk_MapsToAgentThought_WithItsTextInBody()
    {
        var mapper = new AcpRunEventMapper(RunId, AgentId);
        var joined = new System.Text.StringBuilder();
        var seen = 0;

        foreach (var frame in Read("thought.jsonl"))
        {
            var node = JsonNode.Parse(frame.Raw)!.AsObject();
            if (node["params"]?["update"]?["sessionUpdate"]?.GetValue<string>() != "agent_thought_chunk")
            {
                continue;
            }

            seen++;
            var mapped = mapper.Map(frame.Raw, ReceivedAt);

            Assert.Equal("agent.thought", mapped.Kind);
            var text = node["params"]!["update"]!["content"]!["text"]!.GetValue<string>();
            Assert.Equal(text, mapped.Body["content"]!["text"]!.GetValue<string>());
            Assert.Equal(text, AiDe.Core.Presentation.Sessions.ConsoleStreamModel.TextOf(mapped));
            Assert.Null(mapped.Ext["params"]?["update"]);   // lifted, not copied
            joined.Append(text);
        }

        Assert.True(seen > 0, "the corpus no longer contains an agent_thought_chunk frame — the row's shape would be Inferred again");
        Assert.Equal(19, seen);   // the capture's count, asserted from the file so the Proof Pack's number is a record, not a memoir (DC-184)
        Assert.StartsWith("This is a straightforward logic puzzle", joined.ToString(), StringComparison.Ordinal);
    }

    /// <summary>
    /// The five wire shapes that <i>do</i> have a Phase-1 producer are projected onto v1 kinds, with
    /// the recognized payload in <c>body</c>.
    /// </summary>
    [Fact]
    public void RecognizedWireShapesMapToV1Kinds()
    {
        var mapper = new AcpRunEventMapper(RunId, AgentId);
        var counts = new Dictionary<string, int>(StringComparer.Ordinal);

        foreach (var frame in ReadAll())
        {
            var mapped = mapper.Map(frame.Raw, ReceivedAt);
            if (mapped.Kind.StartsWith("acp.", StringComparison.Ordinal))
            {
                continue;
            }

            counts[mapped.Kind] = counts.GetValueOrDefault(mapped.Kind) + 1;
            Assert.NotEmpty(mapped.Body);
        }

        Assert.True(counts.GetValueOrDefault("agent.msg") > 0, "no agent.msg produced");
        Assert.True(counts.GetValueOrDefault("agent.thought") > 0, "no agent.thought produced");
        Assert.True(counts.GetValueOrDefault("tool.call") > 0, "no tool.call produced");
        Assert.True(counts.GetValueOrDefault("tool.result") > 0, "no tool.result produced");
        Assert.True(counts.GetValueOrDefault("permission.request") > 0, "no permission.request produced");
    }

    /// <summary>
    /// No event carries a kind that has <b>no Phase-1 producer</b>. There is no Conductor until
    /// Phase 2 and no observed lane until Phase 4, so a handler for one of these would be code
    /// written for a caller that does not exist.
    /// </summary>
    /// <remarks>
    /// fixture-derivation: ok — these five are pinned on purpose. They are the spec's v1 kinds that
    /// Phase 1 deliberately has no producer for, and the point of the case is that the list stays
    /// empty until the phase that fills it.
    /// </remarks>
    [Fact]
    public void NoKindWithoutAPhase1ProducerIsEverEmitted()
    {
        string[] noProducer =
        [
            "block.open", "plan.submitted", "council.verdict", "decision", "quota.pressure",
        ];

        var mapper = new AcpRunEventMapper(RunId, AgentId);
        foreach (var frame in ReadAll())
        {
            var mapped = mapper.Map(frame.Raw, ReceivedAt);
            Assert.DoesNotContain(mapped.Kind, noProducer);
        }
    }

    /// <summary>
    /// <c>parent_agent_id</c> is carried and never populated: nothing can know a parent before the
    /// Conductor exists, and a fabricated one would be worse than a null.
    /// </summary>
    [Fact]
    public void ParentAgentIdIsAlwaysNullInPhase1()
    {
        var mapper = new AcpRunEventMapper(RunId, AgentId);
        foreach (var frame in ReadAll())
        {
            Assert.Null(mapper.Map(frame.Raw, ReceivedAt).ParentAgentId);
        }
    }

    /// <summary>
    /// Identity and ordering come from the plane, not the wire: ACP frames carry neither a run id
    /// nor a sequence nor a timestamp, so inventing one from the frame would be inventing data.
    /// </summary>
    [Fact]
    public void SequenceIsMonotonicAndIdentityComesFromThePlane()
    {
        var mapper = new AcpRunEventMapper(RunId, AgentId);
        long expected = 0;

        foreach (var frame in ReadAll())
        {
            var mapped = mapper.Map(frame.Raw, ReceivedAt);
            expected++;

            Assert.Equal(expected, mapped.Seq);
            Assert.Equal(RunId, mapped.RunId);
            Assert.Equal(AgentId, mapped.AgentId);
            Assert.Equal(ReceivedAt, mapped.Ts);
        }

        Assert.True(expected > 0);
    }

    /// <summary>
    /// Cost is read from the wire where the wire states it, and is <b>null everywhere else</b> —
    /// never a zero, which would read as "this cost nothing" (IO12).
    /// </summary>
    [Fact]
    public void CostIsPopulatedExactlyWhereTheWireReportsUsage()
    {
        var mapper = new AcpRunEventMapper(RunId, AgentId);
        var withUsage = 0;

        foreach (var frame in ReadAll())
        {
            var usage = JsonNode.Parse(frame.Raw)!["result"]?["usage"];
            var mapped = mapper.Map(frame.Raw, ReceivedAt);

            if (usage is null)
            {
                Assert.Null(mapped.Cost);
                continue;
            }

            withUsage++;
            Assert.NotNull(mapped.Cost);
            Assert.Equal(usage["inputTokens"]!.GetValue<long>(), mapped.Cost!.TokensIn);
            Assert.Equal(usage["outputTokens"]!.GetValue<long>(), mapped.Cost.TokensOut);
            Assert.Equal(usage["cachedReadTokens"]!.GetValue<long>(), mapped.Cost.CacheRead);
            Assert.Equal(1, mapped.Cost.Requests);
            Assert.Null(mapped.Cost.Credits);
        }

        Assert.True(withUsage > 0, "the corpus no longer contains a result carrying usage");
    }

    /// <summary>
    /// <b>Kind is an open string.</b> A discriminator no version of this code has ever seen still
    /// produces an event, namespaced and whole, with no code change.
    /// </summary>
    /// <remarks>
    /// Deliberately synthetic — it stands for a <i>future</i> adapter release, which by definition
    /// cannot be in a capture taken today. That is the one thing the corpus cannot be the oracle
    /// for, and it is exactly the property an enum would destroy: with a closed kind set this frame
    /// is a parse failure, and §7.2's "consumers ignore unknown kinds" becomes unimplementable.
    /// </remarks>
    [Fact]
    public void AKindNeverSeenBeforeIsCarriedRatherThanRejected()
    {
        const string future =
            """{"jsonrpc":"2.0","method":"session/update","params":{"sessionId":"s1","update":{"sessionUpdate":"weather_update","celsius":19}}}""";

        var mapped = new AcpRunEventMapper(RunId, AgentId).Map(future, ReceivedAt);

        Assert.Equal("acp.session.update.weather_update", mapped.Kind);
        Assert.Empty(mapped.Body);
        Assert.Equal(19, mapped.Ext["params"]!["update"]!["celsius"]!.GetValue<int>());
    }

    /// <summary>
    /// A line that is not a JSON object carries no event, and says so with a stable code rather than
    /// a parser's exception type.
    /// </summary>
    [Theory]
    [InlineData("")]
    [InlineData("   ")]
    [InlineData("not json at all")]
    [InlineData("[1,2,3]")]
    [InlineData("\"a string\"")]
    public void AFrameThatIsNotAJsonObjectIsRefusedWithAStableCode(string line)
    {
        var error = Assert.Throws<AgentPlaneException>(
            () => new AcpRunEventMapper(RunId, AgentId).Map(line, ReceivedAt));

        Assert.Equal(AgentPlaneErrorCodes.MalformedFrame, error.Code);
    }
}
