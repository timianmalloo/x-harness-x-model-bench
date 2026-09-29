using AiDe.Core.Facts;

namespace AiDe.Core.Extraction;

public static class ExtractionErrorCodes
{
    public const string Timeout = "AIDE-EXTRACT-TIMEOUT";
    public const string Quarantined = "AIDE-EXTRACT-QUARANTINED";
    public const string PathContainment = "AIDE-PATH-CONTAINMENT";
    public const string Malformed = "AIDE-EXTRACT-MALFORMED";
}

/// <summary>One scope's extraction, and what the rest of the workspace contains.</summary>
/// <param name="WorkspaceModules">
/// Every module id the workspace holds, so an import that leaves this scope can be resolved instead
/// of disclosed.
/// </param>
/// <param name="WorkspaceKnowledge">
/// Every markdown file the workspace holds and the node id it declares, so a prose link that leaves
/// this scope's directory can be resolved instead of disclosed. The knowledge reader's counterpart
/// to <paramref name="WorkspaceModules"/>, and it exists for a sharper reason: knowledge scopes
/// NEST, so each document is now emitted by exactly one scope and there is no wider scope left to
/// resolve a cross-directory link (DC-051).
/// </param>
/// <remarks>
/// <para><b>Why a whole-workspace set rather than per-scope discovery.</b> A Python or TypeScript
/// scope is one directory, and an import that names a sibling package resolves to a file in a
/// DIFFERENT scope. Resolving that from inside the scope is impossible, and resolving it by
/// extraction order would be resolution that is wrong whenever the order changes — the same trap
/// the Python extractor already avoids within a scope by collecting modules before it reads any.</para>
///
/// <para>Null means "not supplied", which is not the same as empty: an extractor treats it as no
/// cross-scope knowledge and falls back to disclosing what it could not resolve.</para>
/// </remarks>
public sealed record ExtractionRequest(
    string ScopeId,
    string RootPath,
    string ArtifactRevision,
    long DesiredGeneration,
    IReadOnlySet<string>? WorkspaceModules = null,
    WorkspaceKnowledge? WorkspaceKnowledge = null);

public sealed record ExtractionDiagnostic(string ErrorCode, string ArtifactPathId, string Message);

public sealed record ExtractionResult(
    IReadOnlyList<EvidenceAssertion> Assertions,
    bool Complete,
    IReadOnlyList<ExtractionDiagnostic> Diagnostics);

/// <summary>The extractor seam. Phase 1 ships the fixture adapter; Phase 2 substitutes Roslyn behind it.</summary>
public interface IExtractor
{
    string ScopeKind { get; }

    Task<ExtractionResult> ExtractAsync(ExtractionRequest request, CancellationToken cancellationToken);
}

/// <summary>
/// Reads a fixture repository and emits provenance-labelled assertions.
/// </summary>
/// <remarks>
/// Two artifact shapes, both deliberately repo-shaped rather than synthetic:
/// <list type="bullet">
/// <item><c>*.facts</c> — one relation per line, <c>Subject -> predicate -> Object [Status]</c>,
/// standing in for a source extractor.</item>
/// <item><c>*.md</c> with YAML-ish frontmatter — knowledge nodes and their <c>links:</c> edges,
/// which is what US-4's knowledge navigation actually reads.</item>
/// </list>
/// A malformed line becomes a diagnostic and marks the snapshot incomplete; it never silently
/// vanishes, because an empty graph reported as a clean graph is the failure this design forbids.
/// </remarks>
public sealed class FixtureExtractor(string extractorVersion = "1.0.0") : IExtractor
{
    public const string ExtractorId = "fixture-extractor";

    public string ScopeKind => "fixture";

    public Task<ExtractionResult> ExtractAsync(ExtractionRequest request, CancellationToken cancellationToken)
    {
        var root = Path.GetFullPath(request.RootPath);
        if (!Directory.Exists(root))
        {
            return Task.FromResult(new ExtractionResult([], false,
                [new ExtractionDiagnostic(ExtractionErrorCodes.PathContainment, request.RootPath, "root does not exist")]));
        }

        var assertions = new List<EvidenceAssertion>();
        var diagnostics = new List<ExtractionDiagnostic>();
        var observedAt = DateTimeOffset.UtcNow;

        foreach (var file in Directory.EnumerateFiles(root, "*", SearchOption.AllDirectories).OrderBy(f => f, StringComparer.Ordinal))
        {
            cancellationToken.ThrowIfCancellationRequested();

            // Containment against the LEXICAL full path, and this boundary is narrower than the
            // comment that used to sit here claimed. That comment said "a junction or symlink that
            // escapes the fixture root must not be extracted (P1-FS)". MEASURED on .NET 10.0.11:
            // Directory.EnumerateFiles DOES traverse a junction, and Path.GetFullPath does NOT
            // resolve one - it normalises text. So a junction inside the root yields a path still
            // spelled under the root, this test passes, and the file is read from wherever the
            // junction points. Refusing a reparse point means resolving link targets and is a
            // separate change; describing a boundary as stronger than it is helps nobody.
            //
            // What this DOES refuse is a path whose TEXT leaves the root - and today nothing
            // produces one, because every path the enumerator yields is `root` with segments
            // appended. It is a guard against a future caller, not an active filter. (The one way
            // it fires today is wrong: a RootPath ending in a separator makes `root + separator` a
            // DOUBLE separator, and then EVERY file reports as escaping. Also measured; also a
            // separate change.)
            //
            // The comparison itself is the platform's own, never a hardcoded fold - see
            // PathComparison, and tools/verify-containment-comparisons.py, which refuses the
            // hardcoded shape this line carried through three repairs of the same defect.
            var resolved = Path.GetFullPath(file);
            if (!resolved.StartsWith(root + Path.DirectorySeparatorChar, PathComparison.ForThisFileSystem))
            {
                diagnostics.Add(new ExtractionDiagnostic(ExtractionErrorCodes.PathContainment, file, "escapes the scope root"));
                continue;
            }

            var relative = Path.GetRelativePath(root, resolved).Replace('\\', '/');
            var extension = Path.GetExtension(resolved);

            if (extension.Equals(".facts", StringComparison.OrdinalIgnoreCase))
            {
                ReadFactsFile(resolved, relative, request, observedAt, assertions, diagnostics);
            }
            else if (extension.Equals(".md", StringComparison.OrdinalIgnoreCase))
            {
                ReadKnowledgeFile(resolved, relative, request, observedAt, assertions, diagnostics);
            }
        }

        return Task.FromResult(new ExtractionResult(assertions, diagnostics.Count == 0, diagnostics));
    }

    private void ReadFactsFile(
        string path, string relative, ExtractionRequest request, DateTimeOffset observedAt,
        List<EvidenceAssertion> assertions, List<ExtractionDiagnostic> diagnostics)
    {
        var lineNumber = 0;
        foreach (var raw in File.ReadLines(path))
        {
            lineNumber++;
            var line = raw.Trim();
            if (line.Length == 0 || line.StartsWith('#'))
            {
                continue;
            }

            var parts = line.Split("->", StringSplitOptions.TrimEntries);
            if (parts.Length != 3)
            {
                diagnostics.Add(new ExtractionDiagnostic(
                    ExtractionErrorCodes.Malformed, relative, $"line {lineNumber}: expected 'S -> p -> O'"));
                continue;
            }

            // A trailing [Inferred] marks a convention-derived relation. Absent it, a fixture
            // relation is Verified only because the fixture *is* the artifact — never promoted.
            var target = parts[2];
            var status = VerificationStatus.Verified;
            var bracket = target.IndexOf('[');
            if (bracket >= 0)
            {
                var label = target[(bracket + 1)..].TrimEnd(']').Trim();
                target = target[..bracket].Trim();
                if (!Enum.TryParse(label, ignoreCase: true, out status))
                {
                    diagnostics.Add(new ExtractionDiagnostic(
                        ExtractionErrorCodes.Malformed, relative, $"line {lineNumber}: unknown status '{label}'"));
                    continue;
                }
            }

            assertions.Add(new EvidenceAssertion(
                request.ScopeId, request.ArtifactRevision, parts[0], parts[1], target,
                EvidenceOrigin.Static, status,
                new Provenance(relative, $"{lineNumber}:1", ExtractorId, extractorVersion, observedAt)));
        }
    }

    /// <summary>
    /// Knowledge artifacts: the node itself, its declared type, and one edge per <c>links:</c> entry.
    /// This is the evidence US-4's knowledge projection navigates — knowledge is not a second store,
    /// it is the same fact grain with a knowledge-kind subject.
    /// </summary>
    private void ReadKnowledgeFile(
        string path, string relative, ExtractionRequest request, DateTimeOffset observedAt,
        List<EvidenceAssertion> assertions, List<ExtractionDiagnostic> diagnostics)
    {
        var lines = File.ReadAllLines(path);
        if (lines.Length == 0 || lines[0].Trim() != "---")
        {
            diagnostics.Add(new ExtractionDiagnostic(
                ExtractionErrorCodes.Malformed, relative, "knowledge artifact has no frontmatter"));
            return;
        }

        string? id = null;
        string? type = null;
        string? owner = null;
        var links = new List<(string To, string Rel)>();

        for (var i = 1; i < lines.Length; i++)
        {
            var line = lines[i];
            if (line.Trim() == "---")
            {
                break;
            }

            var trimmed = line.Trim();
            if (trimmed.StartsWith("id:", StringComparison.Ordinal))
            {
                id = Value(trimmed[3..]);
            }
            else if (trimmed.StartsWith("type:", StringComparison.Ordinal))
            {
                type = Value(trimmed[5..]);
            }
            else if (trimmed.StartsWith("owner:", StringComparison.Ordinal))
            {
                owner = Value(trimmed[6..]);
            }
            else if (trimmed.StartsWith("- { to:", StringComparison.Ordinal))
            {
                var body = trimmed[7..].TrimEnd('}').Trim();
                var segments = body.Split(',', StringSplitOptions.TrimEntries);
                var to = Value(segments[0]);
                var rel = segments.Length > 1 && segments[1].StartsWith("rel:", StringComparison.Ordinal)
                    ? Value(segments[1][4..])
                    : "relates-to";
                links.Add((to, rel));
            }
        }

        if (string.IsNullOrEmpty(id))
        {
            diagnostics.Add(new ExtractionDiagnostic(
                ExtractionErrorCodes.Malformed, relative, "knowledge artifact has no id"));
            return;
        }

        Provenance Where(int line) => new(relative, $"{line}:1", ExtractorId, extractorVersion, observedAt);

        assertions.Add(new EvidenceAssertion(
            request.ScopeId, request.ArtifactRevision, id, "has_type", type ?? "unknown",
            EvidenceOrigin.Static, type is null ? VerificationStatus.Unverified : VerificationStatus.Verified,
            Where(2)));

        // Declared, not inferred — the same statement KnowledgeExtractor makes. This reader produces
        // both knowledge nodes and fixture facts, so its scope id cannot say which a node is.
        assertions.Add(new EvidenceAssertion(
            request.ScopeId, request.ArtifactRevision, id, "node_class", "knowledge",
            EvidenceOrigin.Static, VerificationStatus.Verified, Where(2)));

        // Owner is recorded so US-4's "missing source/owner is a health finding" can be answered.
        // It names a person, so it stays workspace-local and never reaches telemetry.
        if (!string.IsNullOrEmpty(owner))
        {
            assertions.Add(new EvidenceAssertion(
                request.ScopeId, request.ArtifactRevision, id, "owned_by", owner,
                EvidenceOrigin.Static, VerificationStatus.Verified, Where(3)));
        }

        foreach (var (to, rel) in links)
        {
            assertions.Add(new EvidenceAssertion(
                request.ScopeId, request.ArtifactRevision, id, rel, to,
                EvidenceOrigin.Static, VerificationStatus.Verified, Where(4)));
        }

        static string Value(string raw) =>
            raw.Trim().Trim('"').Trim('\'').Trim();
    }
}
