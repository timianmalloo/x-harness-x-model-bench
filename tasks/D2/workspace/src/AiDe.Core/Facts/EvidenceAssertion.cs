using System.Security.Cryptography;
using System.Text;

namespace AiDe.Core.Facts;

/// <summary>How the evidence was acquired. Never collapsed with <see cref="VerificationStatus"/>.</summary>
public enum EvidenceOrigin
{
    Static,
    Runtime,
}

/// <summary>
/// How well the evidence is established. Deliberately separate from <see cref="EvidenceOrigin"/>:
/// the spec forbids collapsing acquisition and validation into one confidence word.
/// </summary>
public enum VerificationStatus
{
    Verified,
    Inferred,
    Unverified,
}

/// <summary>Where an assertion came from, so a claim can always be traced back to an artifact.</summary>
public sealed record Provenance(
    string ArtifactPathId,
    string? SourceLocation,
    string ExtractorId,
    string ExtractorVersion,
    DateTimeOffset ObservedAt);

/// <summary>
/// The fact grain: one row is exactly one assertion by one extractor about one normalized
/// (subject, predicate, object) relation at one artifact revision.
/// </summary>
public sealed record EvidenceAssertion(
    string ScopeId,
    string ArtifactRevision,
    string Subject,
    string Predicate,
    string Object,
    EvidenceOrigin Origin,
    VerificationStatus Status,
    Provenance Provenance)
{
    /// <summary>
    /// Deterministic identity: re-extracting an unchanged artifact yields the same id, so a replay
    /// is idempotent rather than a duplicate. Computed, never supplied.
    /// </summary>
    public string AssertionId { get; } = ComputeId(
        ScopeId, ArtifactRevision, Subject, Predicate, Object, Provenance.ExtractorId);

    internal static string ComputeId(
        string scopeId, string artifactRevision, string subject, string predicate, string @object, string extractorId)
    {
        // Unit separator keeps the canonical form unambiguous: a field containing '|' cannot forge
        // a different field boundary and collide with another assertion's id.
        var canonical = string.Join('\u001F', scopeId, artifactRevision, subject, predicate, @object, extractorId);
        var hash = SHA256.HashData(Encoding.UTF8.GetBytes(canonical));
        return Convert.ToHexStringLower(hash);
    }
}
