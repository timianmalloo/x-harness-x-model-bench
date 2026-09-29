using System.Security.Cryptography;
using System.Text;

namespace AiDe.Core.Watcher;

/// <summary>
/// The observation fact grain: one row is exactly one observed operation emitted by one authenticated
/// session generation, identified by its source span identity, recorded at ingest. Immutable and
/// append-only (ADR-0023 watcher-observation-projection). Phase 1 carries operation metadata only - no prompt/code/transcript
/// content (that is Phase 5, behind the governance gate).
/// </summary>
public sealed record ObservedSpan(
    string SessionId,
    string TraceId,
    string SourceSpanId,
    string OperationName,
    DateTimeOffset RecordedAt)
{
    /// <summary>
    /// Deterministic content-addressed identity: the same (session, trace, source span) yields the
    /// same id, so a redelivered span is a duplicate to ignore rather than a second row. Computed,
    /// never supplied. Pattern: LOA 5.3 Idempotent Action - the id makes ingest idempotent by
    /// construction (the <see cref="AiDe.Core.Facts.EvidenceAssertion"/> idiom).
    /// </summary>
    public string SpanId { get; } = ComputeId(SessionId, TraceId, SourceSpanId);

    internal static string ComputeId(string sessionId, string traceId, string sourceSpanId)
    {
        // Unit separator keeps the canonical form unambiguous: a field containing '|' cannot forge a
        // different field boundary and collide with another span's id.
        var canonical = string.Join('\u001F', sessionId, traceId, sourceSpanId);
        var hash = SHA256.HashData(Encoding.UTF8.GetBytes(canonical));
        return Convert.ToHexStringLower(hash);
    }
}
