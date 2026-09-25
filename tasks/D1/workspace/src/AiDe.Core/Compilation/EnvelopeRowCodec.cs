using System.Globalization;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using System.Text.Json.Nodes;
using AiDe.Core.AgentPlane;

namespace AiDe.Core.PromptCompilation;

/// <summary>The one hash the store, the projection and the rebuild share: sha256 as lowercase hex over UTF-8.</summary>
public static class EnvelopeHash
{
    /// <summary>sha256 of <paramref name="text"/>'s UTF-8 bytes, lowercase hex.</summary>
    public static string Sha256Hex(string text)
    {
        ArgumentNullException.ThrowIfNull(text);
        return Convert.ToHexStringLower(SHA256.HashData(Encoding.UTF8.GetBytes(text)));
    }

    /// <summary>sha256 of raw bytes, lowercase hex.</summary>
    public static string Sha256Hex(ReadOnlySpan<byte> bytes) => Convert.ToHexStringLower(SHA256.HashData(bytes));
}

/// <summary>
/// Writes one <see cref="EnvelopeEvent"/> as one <c>compiled-envelope/1</c> line and reads one back
/// — the members in one fixed order, no indentation, so the same event is the same bytes (US-D2).
/// </summary>
/// <remarks>
/// Hand-written over <see cref="JsonObject"/> rather than reflection-serialized for the READER's
/// sake, not the writer's: the fold is lenient by contract (DM11 g — a missing member reads
/// <i>not recorded</i>, an unknown kind or schema is skipped and counted, a key is read from any
/// line), which a serializer over positional records refuses at the first absent member without a
/// converter per record. The writer's fixed member order (§A12.1) rides along; an attribute could
/// give that alone.
/// </remarks>
internal static class EnvelopeRowCodec
{
    private static readonly JsonSerializerOptions Compact = new() { WriteIndented = false, Encoder = System.Text.Encodings.Web.JavaScriptEncoder.UnsafeRelaxedJsonEscaping };

    /// <summary>The row, as one line without its newline.</summary>
    public static string Write(EnvelopeEvent evt, string schema, string prevSha)
    {
        var row = new JsonObject
        {
            ["schema"] = schema,
            ["envelope_id"] = evt.EnvelopeId,
            ["seq"] = evt.Seq,
            ["kind"] = evt.Kind,
            ["at"] = (evt.At ?? throw new InvalidOperationException("a row is stamped before it is written")).ToUniversalTime().ToString("O", CultureInfo.InvariantCulture),
            ["prev_sha"] = prevSha,
        };

        switch (evt)
        {
            case Opened o:
                row["source_text"] = o.SourceText;
                row["session_id"] = o.SessionId;
                row["engine_id"] = o.EngineId;
                row["compile_mode"] = o.CompileMode;
                row["supersedes"] = o.Supersedes;
                row["constants"] = new JsonObject { ["k"] = o.Constants.K, ["byte_bound"] = o.Constants.ByteBound, ["bound_ms"] = o.Constants.BoundMs };
                break;

            case Decorated d:
                row["name"] = d.Name;
                row["value"] = d.Value?.DeepClone();
                row["source"] = d.Source;
                if (d.Inputs is { Count: > 0 } inputs)
                {
                    row["inputs"] = new JsonArray([.. inputs.Select(i =>
                    {
                        var input = new JsonObject { ["writer"] = i.Writer };
                        if (i.Id is not null) input["id"] = i.Id;
                        if (i.Version is not null) input["version"] = i.Version;
                        return (JsonNode)input;
                    })]);
                }

                if (d.CallSeq is { } callSeq) row["call_seq"] = callSeq;
                if (d.Confidence is { } confidence) row["confidence"] = confidence;
                if (d.GroundedIn is { Count: > 0 } spans)
                {
                    row["grounded_in"] = new JsonArray([.. spans.Select(s => (JsonNode)new JsonObject { ["input"] = s.Input, ["span"] = new JsonArray(s.Start, s.End) })]);
                }

                if (d.Bytes is { } bytes) row["bytes"] = bytes;
                break;

            case Called c:
                row["engine_id"] = c.EngineId;
                row["model_configured"] = c.ModelConfigured;
                row["model_observed"] = c.ModelObserved;
                row["latency_ms"] = c.LatencyMs;
                row["cost"] = c.Cost is { } cost
                    ? new JsonObject { ["tokens_in"] = cost.TokensIn, ["tokens_out"] = cost.TokensOut, ["cache_read"] = cost.CacheRead, ["requests"] = cost.Requests }
                    : null;
                row["outcome"] = c.Outcome;
                row["reason"] = c.Reason;
                row["inputs_sha"] = c.InputsSha;
                row["prompt_sha"] = c.PromptSha;
                row["contract_version"] = c.ContractVersion;
                row["permission_requests"] = c.PermissionRequests;
                row["tool_calls"] = c.ToolCalls;
                row["dropped"] = new JsonObject
                {
                    ["unknown_name"] = c.Dropped.UnknownName,
                    ["already_supplied"] = c.Dropped.AlreadySupplied,
                    ["ungrounded"] = c.Dropped.Ungrounded,
                    ["mention_bearing"] = c.Dropped.MentionBearing,
                    ["type_fail"] = c.Dropped.TypeFail,
                };
                break;

            case Submitted s:
                row["accepted"] = s.Accepted;
                row["refusal"] = s.Refusal;
                row["text_sha256"] = s.TextSha256;
                row["projection_sha"] = s.ProjectionSha;
                row["projector_version"] = s.ProjectorVersion;
                break;

            case Consumed k:
                row["run_id"] = k.RunId;
                row["episode_id"] = k.EpisodeId;
                row["outcome"] = k.Outcome;
                row["reason"] = k.Reason;
                break;

            default:
                throw new ArgumentOutOfRangeException(nameof(evt), evt.Kind, "an unknown event kind cannot be written");
        }

        return row.ToJsonString(Compact);
    }

    /// <summary>The key every line carries regardless of schema or kind — what the writer's walk reads.</summary>
    public static bool TryReadKey(JsonObject row, out string envelopeId, out int seq)
    {
        envelopeId = string.Empty;
        seq = 0;
        return row["envelope_id"] is JsonValue id && id.TryGetValue(out string? e) && e is not null
            && row["seq"] is JsonValue s && s.TryGetValue(out int n)
            && (envelopeId = e) is not null && (seq = n) > 0;
    }

    /// <summary>
    /// One <c>/1</c> row as its event, or null when the kind is not one this reader knows — the
    /// caller skips and counts it (DM11 g).
    /// </summary>
    public static EnvelopeEvent? TryRead(JsonObject row)
    {
        if (!TryReadKey(row, out var envelopeId, out var seq))
        {
            return null;
        }

        var kind = Str(row, "kind");
        DateTimeOffset? at = DateTimeOffset.TryParse(Str(row, "at"), CultureInfo.InvariantCulture, DateTimeStyles.RoundtripKind, out var parsed) ? parsed : null;

        EnvelopeEvent? evt = kind switch
        {
            EnvelopeEventKinds.Opened => new Opened(
                envelopeId,
                Str(row, "source_text") ?? string.Empty,
                Str(row, "session_id") ?? string.Empty,
                Str(row, "engine_id") ?? string.Empty,
                Str(row, "compile_mode") ?? string.Empty,
                Str(row, "supersedes"),
                row["constants"] is JsonObject k
                    ? new CompileConstants(Int(k, "k") ?? 0, Int(k, "byte_bound") ?? 0, Int(k, "bound_ms") ?? 0)
                    : new CompileConstants(0, 0, 0)),

            EnvelopeEventKinds.Decorated => Str(row, "name") is { } name && Str(row, "source") is { } source
                ? new Decorated(envelopeId, name, row["value"]?.DeepClone(), source)
                {
                    Inputs = row["inputs"] is JsonArray inputs
                        ? [.. inputs.OfType<JsonObject>().Select(i => new DecorationInput(Str(i, "writer") ?? "not recorded", Str(i, "id"), Str(i, "version")))]
                        : null,
                    CallSeq = Int(row, "call_seq"),
                    Confidence = row["confidence"] is JsonValue cv && cv.TryGetValue(out double c) ? c : null,
                    GroundedIn = row["grounded_in"] is JsonArray spans
                        ? [.. spans.OfType<JsonObject>().Select(s => new GroundedSpan(
                            Str(s, "input") ?? string.Empty,
                            s["span"] is JsonArray { Count: 2 } sp && sp[0] is JsonValue a && a.TryGetValue(out int start) ? start : 0,
                            s["span"] is JsonArray { Count: 2 } sp2 && sp2[1] is JsonValue b && b.TryGetValue(out int end) ? end : 0))]
                        : null,
                    Bytes = Int(row, "bytes"),
                }
                : null,

            EnvelopeEventKinds.Called => new Called(
                envelopeId,
                Str(row, "engine_id") ?? string.Empty,
                Str(row, "model_configured") ?? Envelope.NotRecorded,
                Str(row, "model_observed") ?? Envelope.NotRecorded,
                Int(row, "latency_ms"),
                row["cost"] is JsonObject cost
                    ? new RunEventCost(Long(cost, "tokens_in") ?? 0, Long(cost, "tokens_out") ?? 0, Long(cost, "cache_read") ?? 0, Int(cost, "requests") ?? 0)
                    : null,
                Str(row, "outcome") ?? Envelope.NotRecorded,
                Str(row, "reason"),
                Str(row, "inputs_sha") ?? string.Empty,
                Str(row, "prompt_sha") ?? string.Empty,
                Str(row, "contract_version") ?? string.Empty,
                Int(row, "permission_requests") ?? 0,
                Int(row, "tool_calls") ?? 0,
                row["dropped"] is JsonObject dropped
                    ? new DroppedCounts(Int(dropped, "unknown_name") ?? 0, Int(dropped, "already_supplied") ?? 0, Int(dropped, "ungrounded") ?? 0, Int(dropped, "mention_bearing") ?? 0, Int(dropped, "type_fail") ?? 0)
                    : DroppedCounts.None),

            EnvelopeEventKinds.Submitted => new Submitted(
                envelopeId,
                row["accepted"] is JsonValue av && av.TryGetValue(out bool accepted) && accepted,
                Str(row, "refusal"),
                Str(row, "text_sha256") ?? string.Empty,
                Str(row, "projection_sha") ?? string.Empty,
                Str(row, "projector_version") ?? Envelope.NotRecorded),

            EnvelopeEventKinds.Consumed => new Consumed(
                envelopeId,
                Str(row, "run_id") ?? Envelope.NotRecorded,
                Str(row, "episode_id"),
                Str(row, "outcome") ?? Envelope.NotRecorded,
                Str(row, "reason") ?? Envelope.NotRecorded),

            _ => null,
        };

        return evt is null ? null : evt with { Seq = seq, At = at };
    }

    private static string? Str(JsonObject row, string name) =>
        row[name] is JsonValue v && v.TryGetValue(out string? s) ? s : null;

    private static int? Int(JsonObject row, string name) =>
        row[name] is JsonValue v && v.TryGetValue(out int n) ? n : null;

    private static long? Long(JsonObject row, string name) =>
        row[name] is JsonValue v && v.TryGetValue(out long n) ? n : null;
}
