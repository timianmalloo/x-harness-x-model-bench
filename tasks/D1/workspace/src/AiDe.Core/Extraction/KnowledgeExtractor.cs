using AiDe.Core.Facts;

namespace AiDe.Core.Extraction;

/// <summary>
/// The knowledge graph: documents that declare an identity, a kind and typed links.
/// </summary>
/// <remarks>
/// <para><b>Reported by the user: the graph showed knowledge as ZERO and code as a large count.</b>
/// The reason was not that repositories have no knowledge — it is that nothing ever looked. A reader
/// for these documents has existed since Phase 1 inside the fixture extractor, with tests, and
/// scope discovery produced six kinds of scope (<c>csharp</c>, <c>bicep</c>, <c>schema</c>,
/// <c>python</c>, <c>typescript</c>, <c>sql</c>) and no knowledge scope at all. The capability was
/// real, tested, and unreachable on any real repository.</para>
///
/// <para><b>A zero that means "nobody looked" reads as "there is none".</b> That is the shape this
/// product exists to avoid, and it was in the product's own headline surface — on a repository whose
/// entire premise is that <em>docs hold intent, code holds reality, and the expensive defects live
/// in the gap</em>. Half of that sentence was never being read.</para>
///
/// <para><b>The body is now read, for exactly one thing.</b> Until this landed the reader saw only
/// frontmatter and disclosed <c>knowledge-body-not-analysed</c> on every scope — 877 documents on
/// TheTerrace present in the graph as their own metadata. A markdown hyperlink to another document
/// is the one thing in a body that is a DECLARATION: the author wrote a path, and the path either
/// resolves to a file this scope read or it does not. Everything else a body contains was measured
/// and left unread on purpose; <see cref="KnowledgeBody"/> carries the numbers and the reasons, and
/// each one is disclosed with a count rather than skipped in silence.</para>
///
/// <para><b>Nothing here is matched by resemblance.</b> The user's decision of 2026-08-30 — <em>"do
/// not infer, the graph should only be on observable links/relationships"</em> — rules out reading
/// prose for names that look like code or like a document id. Measured against it: 26,924 inline
/// code spans in TheTerrace's documents match zero C# node ids exactly, and the knowledge-id variant
/// that does fire is wrong often enough to reject (<c>`architecture`</c> names an MCP tool in 4 of
/// its 5 occurrences in this repository). A link is different in kind: <c>[x](../y.md)</c> has one
/// reading.</para>
///
/// <para><b>READ WIDELY, EMIT NARROWLY — and this reverses a decision made the day before.</b>
/// Knowledge scopes NEST: discovery yields a scope for every directory holding a document with an
/// id, so <c>docs</c> and <c>docs/adr</c> are both scopes, and a reader that walked its scope
/// RECURSIVELY indexed <c>docs/adr/0001.md</c> from both. MEASURED on TheTerrace: <b>2,371
/// <c>node_class</c> rows for 878 distinct documents</b> — every knowledge fact stored ~2.7 times.
/// Walking each scope's OWN directory fixes that exactly, and on its own it cost <b>30 of the 42
/// prose-link edges</b>: a link from <c>docs/adr</c> to <c>docs/specs</c> only resolved because the
/// recursive parent had read both sides. That change was made, measured and reverted rather than
/// shipped (DC-051).</para>
///
/// <para><b>So the two jobs are separated instead of traded.</b> RESOLUTION reads the whole
/// workspace — <see cref="WorkspaceKnowledge"/>, built once per revision by <c>WorkspaceCore</c> and
/// handed to every scope, exactly as <c>WorkspaceModules</c> already is for Python and TypeScript.
/// EMISSION covers only the markdown directly in this scope's directory, so each document is
/// extracted by exactly one scope. Measured on TheTerrace: 878 documents preserved, <c>node_class</c>
/// 2,371 → 878, distinct <c>links_to</c> edges 42 → 42 (rows 68 → 42).</para>
///
/// <para><b>What that overturns.</b> The reader shipped on 2026-08-31 with <em>"a link above the
/// scope is its own boundary"</em> — a path climbing out of the scope was refused because a wider
/// scope might hold it and this reader had no way to know. That was RIGHT while the scope was the
/// unit of resolution, and is WRONG now that each document belongs to exactly one scope: under the
/// old rule a link from <c>docs/adr/0001.md</c> to <c>../specs/workspace.md</c> would be a boundary
/// on the only scope that will ever read <c>0001.md</c>, and the edge would exist nowhere. The
/// boundary has not been deleted, it has MOVED OUT to the workspace root, which is the real edge of
/// what this product reads. Measured consequence on this repository: 19 links to
/// <c>../../spikes/*/RESULT.md</c> that used to be counted as "outside the scope" are now correctly
/// counted as "resolves to a markdown file that declares no id".</para>
///
/// <para><b>Widening resolution is not widening inference.</b> The user's decision of 2026-08-30
/// still governs: a link enters the graph only because an author WROTE a path and that path names a
/// file this reader opened and found an id in. Nothing here matches by name, by resemblance or by
/// proximity — the workspace map is keyed by PATH, and a document's id is only ever read out of the
/// file the path lands on.</para>
///
/// <para><b>Why not point the fixture extractor at the repository instead.</b> It enumerates
/// <c>*</c> recursively with no exclusions — pointed at a real checkout it would walk
/// <c>node_modules</c>, <c>bin</c> and <c>.git</c>. It also stamps <c>fixture-extractor</c> into
/// provenance, which would be a lie on a real document. The parsing is shared
/// (<see cref="KnowledgeFrontmatter"/>); only the walking and the identity differ.</para>
/// </remarks>
/// <summary>Every markdown file in the workspace, and the node id it declares — or none.</summary>
/// <param name="Root">
/// The workspace root. A prose link that resolves ABOVE this is outside what the product reads, and
/// is a boundary rather than a broken cross-reference — the same distinction, one level out from
/// where it used to sit.
/// </param>
/// <param name="Documents">
/// Full path to declared id, or <c>null</c> for a markdown file that declares none. BOTH answers are
/// needed and they are different: absent means the link names a file that is not there (a defect in
/// the document), present-with-null means the file is there and declined to join the graph (this
/// product's boundary). Collapsing them buries the first inside the second.
/// </param>
/// <remarks>
/// <para><b>Keyed by PATH, never by name.</b> The map is what makes cross-directory resolution
/// possible without inference: a link is followed to a file, and the id is whatever that file says
/// it is. Nothing is matched by resemblance.</para>
///
/// <para>The comparer is ORDINAL-IGNORE-CASE, and this is part of the contract rather than an
/// implementation detail — these paths come off a Windows filesystem where <c>../ADR/0001.md</c> and
/// <c>../adr/0001.md</c> are one file, and a case-exact lookup would silently miss one of them.
/// <see cref="KnowledgeExtractor.Survey"/> is the only thing that should build one.</para>
/// </remarks>
public sealed record WorkspaceKnowledge(string Root, IReadOnlyDictionary<string, string?> Documents);

public sealed class KnowledgeExtractor : IExtractor
{
    public string ScopeKind => "knowledge";

    private const string ExtractorId = "knowledge-extractor";
    private const string ExtractorVersion = "1.1.0";

    /// <summary>
    /// What this reader does not see, stated on the scope with a count.
    /// </summary>
    /// <remarks>
    /// <para><b>Every one of these is conditional.</b> The disclosure they replaced —
    /// <c>knowledge-body-not-analysed</c> — fired on every scope whether or not anything had been
    /// hidden, and it would now be false on any scope whose prose links resolve. That is the exact
    /// shape the Python reader had to correct: <em>"a blanket 'imports are not resolved' was true
    /// when none were, and became a closed gap reported as open the moment resolution landed"</em>.
    /// A disclosure that cannot be absent teaches a reader to stop reading disclosures.</para>
    ///
    /// <para><b>Boundaries and gaps are kept apart</b> (DC-050). What this product declines to read
    /// — headings, glossary terms, backticked identifiers, a link out of this scope — is a statement
    /// about scope. A link naming a markdown file that is not there is a defect IN THE DOCUMENT, and
    /// merging the two would bury the second inside the first.</para>
    /// </remarks>
    public static class Disclosures
    {
        /// <summary>
        /// A markdown file with frontmatter but no id cannot be a node.
        /// </summary>
        /// <remarks>
        /// <b>Counted over this scope's OWN directory only</b>, since that is now the only markdown
        /// it emits for. The residual: a directory whose markdown declares graph frontmatter and no
        /// id is not a scope (nothing in it declares one), so nothing counts its files — where
        /// before, an ancestor scope's recursive walk did. MEASURED on both corpora at the moment of
        /// the change: TheTerrace has 209 markdown files in non-scope directories and ai-de 187, and
        /// <b>zero of either</b> carry graph frontmatter without an id, so nothing observable is lost
        /// today. Stated here rather than left silent (DC-025): if that number stops being zero the
        /// fix is in DISCOVERY — such a directory is one that meant to hold knowledge — not another
        /// recursive walk here, which is the thing this change exists to remove.
        /// </remarks>
        public const string ArtifactsWithoutIds = "knowledge-artifacts-without-ids";

        /// <summary>GAP: a prose link names a markdown file that is nowhere in the workspace.</summary>
        public const string LinkTargetMissing = "knowledge-prose-link-target-missing";

        /// <summary>BOUNDARY: a prose link resolves to a markdown file that declares no id.</summary>
        public const string LinkTargetNotANode = "knowledge-prose-link-target-not-a-node";

        /// <summary>
        /// BOUNDARY: a prose link points above the WORKSPACE root, where this product does not look.
        /// </summary>
        /// <remarks>
        /// <para><b>Renamed from <c>knowledge-prose-link-target-outside-scope</c>, because the
        /// boundary moved.</b> It used to mean "above this scope's directory", which fired 71 times
        /// across 16 scopes on TheTerrace for links that a sibling scope could perfectly well
        /// resolve — a boundary reported where there was none. Now that resolution reads the whole
        /// workspace, the only place this reader genuinely cannot look is outside the workspace, and
        /// that is what the disclosure says.</para>
        ///
        /// <para><b>It fires on NEITHER corpus, and that is measured rather than assumed</b> — 0 of
        /// TheTerrace's 237 prose links and 0 of this repository's escape the workspace root. Kept,
        /// and proved by fixture rather than by corpus, because a docs tree that links into a
        /// sibling checkout is one commit away and this repository is itself worked in sibling
        /// worktrees; the alternative is calling such a link a broken cross-reference, which is a
        /// wrong number rather than a missing one (DC-016, DC-050).</para>
        /// </remarks>
        public const string LinkTargetOutsideWorkspace = "knowledge-prose-link-target-outside-workspace";

        /// <summary>BOUNDARY: a document's structure is counted, not extracted.</summary>
        public const string HeadingsNotAnalysed = "knowledge-headings-not-analysed";

        /// <summary>BOUNDARY: a glossary's term definitions are counted as documents, not read.</summary>
        public const string GlossaryTermsNotAnalysed = "knowledge-glossary-terms-not-analysed";

        /// <summary>BOUNDARY: backticked identifiers are not matched against anything.</summary>
        public const string InlineCodeNotResolved = "knowledge-inline-code-not-resolved";
    }

    /// <summary>One document, read once, held until every other document's id is known.</summary>
    private sealed record Read(
        string File, string Relative, KnowledgeRecord Record, KnowledgeBodySurvey Body);

    public Task<ExtractionResult> ExtractAsync(ExtractionRequest request, CancellationToken cancellationToken)
    {
        ArgumentNullException.ThrowIfNull(request);

        var directory = request.RootPath;

        if (!Directory.Exists(directory))
        {
            return Task.FromResult(new ExtractionResult([], Complete: false,
                [new ExtractionDiagnostic("AIDE-KB-NO-DIRECTORY", request.ScopeId,
                    $"the scope's directory does not exist: {directory}")]));
        }

        var observedAt = DateTimeOffset.UtcNow;
        var assertions = new List<EvidenceAssertion>();
        var scopeNode = CSharpExtractor.ScopeNodeId(request.ScopeId);

        var scopeProvenance = new Provenance(
            Path.GetFileName(directory), "1:1", ExtractorId, ExtractorVersion, observedAt);

        var withoutIds = 0;
        var headings = 0;
        var documentsWithHeadings = 0;
        var codeSpans = 0;
        var glossaries = 0;

        // Every document in this scope, read ONCE and held. A link's target cannot be resolved until
        // every id is known, and a link may name a document the walk has not reached yet —
        // resolution that depends on file order is resolution that is wrong half the time. The
        // Python reader collects its module names first for exactly this reason.
        var read = new List<Read>();

        // RESOLUTION READS THE WHOLE WORKSPACE; EMISSION IS THIS DIRECTORY ONLY. The map is keyed by
        // PATH — a link names a path, and a path is the only thing that tells two documents apart
        // before their ids are known — and a null value means "the file is there and declares no
        // id", which is a different statement from "not in the map" and must stay separable.
        //
        // The fallback is the SCOPE's own tree, not an empty map: a null map would turn every prose
        // link into a broken cross-reference, which is a wrong number rather than a missing one. It
        // matters only to a caller that builds a request by hand; WorkspaceCore always supplies one.
        var workspace = request.WorkspaceKnowledge ?? Survey(directory);
        var resolutionRoot = Path.GetFullPath(workspace.Root);

        foreach (var file in OwnFiles(directory).OrderBy(f => f, StringComparer.OrdinalIgnoreCase))
        {
            cancellationToken.ThrowIfCancellationRequested();

            string[] lines;
            try { lines = File.ReadAllLines(file); }
            catch (Exception ex) when (ex is IOException or UnauthorizedAccessException) { continue; }

            var record = KnowledgeFrontmatter.Read(lines, out var missingId);

            if (missingId) withoutIds++;
            if (record is null) continue;

            var body = KnowledgeBody.Survey(lines, Path.GetFileName(file), record.Type);

            headings += body.Headings;
            if (body.Headings > 0) documentsWithHeadings++;
            codeSpans += body.InlineCodeSpans;
            if (body.DeclaresItselfAGlossary) glossaries++;

            var relative = Path.GetRelativePath(directory, file).Replace((char)92, '/');

            read.Add(new Read(Path.GetFullPath(file), relative, record, body));
        }

        var linksMissing = 0;
        var linksNotANode = 0;
        var linksOutsideWorkspace = 0;

        foreach (var document in read)
        {
            cancellationToken.ThrowIfCancellationRequested();

            var record = document.Record;

            Provenance Where(int line) =>
                new(document.Relative, $"{line}:1", ExtractorId, ExtractorVersion, observedAt);

            // A document without a declared type is a node whose KIND is unknown, which is different
            // from one that is untyped by design — so the fact exists and carries Unverified rather
            // than being omitted.
            assertions.Add(Fact(
                request, record.Id, "has_type", record.Type ?? "unknown",
                record.Type is null ? VerificationStatus.Unverified : VerificationStatus.Verified,
                Where(2)));

            assertions.Add(Fact(
                request, record.Id, "declared_in", request.ScopeId, VerificationStatus.Verified, Where(2)));

            // The PRODUCER says this is knowledge. Nothing downstream should have to infer it from a
            // type name or a scope id: `has_type` is emitted by six extractors and says nothing about
            // which half of the graph a node is in, and inferring it was INV-0004's root cause.
            assertions.Add(Fact(
                request, record.Id, "node_class", "knowledge", VerificationStatus.Verified, Where(2)));

            // Owner names a person, so it stays workspace-local and never reaches telemetry.
            if (!string.IsNullOrEmpty(record.Owner))
            {
                assertions.Add(Fact(
                    request, record.Id, "owned_by", record.Owner, VerificationStatus.Verified, Where(3)));
            }

            // A review date is a FACT ABOUT the document, so it is an attribute rather than an edge:
            // drawing it would put a date in the graph as a thing to navigate to.
            if (!string.IsNullOrEmpty(record.ReviewBy))
            {
                assertions.Add(Fact(
                    request, record.Id, "review_by", record.ReviewBy, VerificationStatus.Verified, Where(3)));
            }

            foreach (var (to, rel) in record.Links)
            {
                assertions.Add(Fact(request, record.Id, rel, to, VerificationStatus.Verified, Where(4)));
            }

            var declared = record.Links.Select(l => l.To).ToHashSet(StringComparer.Ordinal);

            foreach (var link in document.Body.MarkdownLinks)
            {
                var target = Resolve(document.File, link.Target, resolutionRoot);

                if (target is null)
                {
                    // Not a relative markdown path inside the WORKSPACE. A URL, an .html page, or a
                    // path that climbs out of the tree this product reads — the last of which may
                    // well exist somewhere else on the machine, which this reader has no way to know
                    // and will not guess at by stat-ing paths outside what it was given.
                    if (IsMarkdownReference(link.Target)) linksOutsideWorkspace++;
                    continue;
                }

                if (!workspace.Documents.TryGetValue(target, out var destination))
                {
                    // A file that is not there at all is a broken cross-reference — a defect in the
                    // document, and the only GAP this reader reports.
                    linksMissing++;
                    continue;
                }

                if (destination is null)
                {
                    // The file IS there and declares no id. That is this product's BOUNDARY rather
                    // than a defect: it indexes documents that opt in. Kept apart from the case
                    // above on purpose (DC-050) — merging them would bury a broken cross-reference
                    // inside a statement about scope.
                    linksNotANode++;
                    continue;
                }

                // A document linking to itself is a table of contents, not a relationship.
                if (string.Equals(destination, record.Id, StringComparison.Ordinal)) continue;

                // Already an EDGE, and a better one. 81 of the 128 resolving prose links on
                // TheTerrace name a document the frontmatter already links with a TYPED relation
                // (`refines`, `depends-on`); an untyped second edge between the same pair says
                // nothing the graph does not carry, and doubles the pair's weight in every view
                // that counts edges.
                if (declared.Contains(destination)) continue;

                // VERIFIED, and it is worth being precise about why. Two things were observed rather
                // than inferred: the author wrote this href in this document, and the path it names
                // is a file this reader opened and found an id in. The predicate is deliberately not
                // one of the frontmatter relation names — a hyperlink does not say WHY, and
                // borrowing `relates-to` would make an untyped mention indistinguishable from a
                // declared relation (DC-022: a predicate is a name, and names collide).
                assertions.Add(Fact(
                    request, record.Id, "links_to", destination,
                    VerificationStatus.Verified, Where(link.Line)));
            }
        }

        if (withoutIds > 0)
        {
            // Counted, because a document that MEANT to join the graph and cannot is a defect in
            // that document — distinct from an ordinary markdown file that was never a node. Over
            // THIS DIRECTORY only, matching what the scope emits for; the residual and its
            // measurement are on Disclosures.ArtifactsWithoutIds.
            Disclose($"{Disclosures.ArtifactsWithoutIds} ({withoutIds:N0} file(s) have frontmatter but no id)");
        }

        if (linksMissing > 0)
        {
            // A GAP, and the only one here. MEASURED on TheTerrace: 109 of 237 prose links name a
            // markdown file that is nowhere in the workspace — cross-references that rotted when a
            // document moved, and nothing had ever said so. The count is unchanged by workspace-wide
            // resolution, which is the check that matters: widening WHERE the reader looks must not
            // turn broken links into found ones, and it did not.
            Disclose($"{Disclosures.LinkTargetMissing} ({linksMissing:N0} prose link(s) name a " +
                     "markdown file that is not in this workspace)");
        }

        if (linksNotANode > 0)
        {
            // NOW FIRES ON A REAL CORPUS, and that is the visible half of the boundary moving out to
            // the workspace root. The 19 links in this repository naming `../../spikes/*/RESULT.md`
            // used to be counted as "outside this scope" — a boundary claimed where there was none,
            // since the files are right there and simply declare no id. Measured: 19 on ai-de, 0 on
            // TheTerrace.
            Disclose($"{Disclosures.LinkTargetNotANode} ({linksNotANode:N0} prose link(s) resolve to " +
                     "a markdown file that declares no id, so there is nothing to link to)");
        }

        if (linksOutsideWorkspace > 0)
        {
            Disclose($"{Disclosures.LinkTargetOutsideWorkspace} ({linksOutsideWorkspace:N0} prose " +
                     "link(s) point above the workspace root)");
        }

        if (headings > 0)
        {
            // Counted rather than read, and the count IS the point: "this reader does not extract
            // headings" is a sentence, and "4,471 headings in 375 documents" is the size of the
            // decision. The reasoning is in KnowledgeBody's remarks — the body text already travels
            // whole through node content, and an attribute per heading would push a document's own
            // relations out of its node card.
            Disclose($"{Disclosures.HeadingsNotAnalysed} ({headings:N0} heading(s) in " +
                     $"{documentsWithHeadings:N0} document(s); the body text itself is served whole " +
                     "by node content)");
        }

        if (glossaries > 0)
        {
            Disclose($"{Disclosures.GlossaryTermsNotAnalysed} ({glossaries:N0} document(s) declare " +
                     "themselves a glossary; the terms they define are not read)");
        }

        if (codeSpans > 0)
        {
            // The no-inference decision of 2026-08-30, stated as a number on every scope. Nothing is
            // matched against these: measured on TheTerrace, none of 26,924 exactly names a code
            // node, and matching by resemblance is what produced 7,426 false Verified edges once
            // already.
            Disclose($"{Disclosures.InlineCodeNotResolved} ({codeSpans:N0} inline code span(s) are " +
                     "not matched against code symbols)");
        }

        return Task.FromResult(new ExtractionResult(
            ExtractionFacts.Distinct(assertions), Complete: true, []));

        void Disclose(string text) => assertions.Add(Fact(
            request, scopeNode, CSharpExtractor.DisclosurePredicate, text,
            VerificationStatus.Verified, scopeProvenance));
    }

    /// <summary>Whether a link target is a relative markdown path at all.</summary>
    /// <remarks>
    /// Separated from <see cref="Resolve"/> so the "outside this scope" count means what it says. A
    /// URL and a path that climbs out of the tree both fail to resolve; only the second is something
    /// this reader would have read if it could, and counting the 329 http links on TheTerrace among
    /// them would make the number describe something that does not exist (DC-050).
    /// </remarks>
    private static bool IsMarkdownReference(string target) =>
        target.EndsWith(".md", StringComparison.OrdinalIgnoreCase)
        && !target.StartsWith("//", StringComparison.Ordinal)
        && !Uri.IsWellFormedUriString(target, UriKind.Absolute);

    /// <summary>
    /// The full path a link names, or null when it is not a markdown file inside
    /// <paramref name="resolutionRoot"/>.
    /// </summary>
    /// <remarks>
    /// <para><b>The root is the WORKSPACE, not the scope</b> — that is the decision this change
    /// reverses. A scope-bounded root refused <c>../specs/workspace.md</c> written in
    /// <c>docs/adr/0001.md</c>, and once each document is extracted by exactly one scope there is no
    /// second reader to pick it up: the edge would exist nowhere. Bounding at the workspace keeps
    /// the check doing its real job, which is telling a link this product declines to follow apart
    /// from a link that is broken.</para>
    ///
    /// <para>Only <c>.md</c> targets. A link to an <c>.html</c> page or a <c>.cs</c> file names
    /// something this graph has no node for — 31 such links on TheTerrace, 30 of them to HTML — and
    /// resolving one would mean inventing a node kind to point at.</para>
    ///
    /// <para>The escape check is on the RESOLVED path, so <c>../../../x.md</c> is refused by where
    /// it lands rather than by how it is spelled.</para>
    /// </remarks>
    internal static string? Resolve(string fromFile, string target, string resolutionRoot)
    {
        if (!IsMarkdownReference(target)) return null;

        // A root-absolute path is not relative to this file, and Path.Combine would resolve it
        // against the drive rather than the document.
        if (target.StartsWith('/') || target.StartsWith('\\')) return null;

        string full;
        try
        {
            full = Path.GetFullPath(Path.Combine(Path.GetDirectoryName(fromFile)!, target));
        }
        catch (Exception ex) when (ex is ArgumentException or NotSupportedException or PathTooLongException)
        {
            // A target carrying characters no path can hold is not a link to anything here.
            return null;
        }

        // Inside the root, or nothing. The trailing separator matters: without it a sibling
        // directory called `docs-old` passes the prefix test against a root of `docs`.
        var bounded = resolutionRoot.TrimEnd(Path.DirectorySeparatorChar, Path.AltDirectorySeparatorChar)
            + Path.DirectorySeparatorChar;

        // The platform's own case rule, not a hardcoded fold: on POSIX `<root>/DOCS` is a
        // DIFFERENT directory from `<root>/docs`, and folding here resolves a knowledge edge to a
        // document outside the root this reader was bounded to. See PathComparison.
        return full.StartsWith(bounded, PathComparison.ForThisFileSystem) ? full : null;
    }

    private static EvidenceAssertion Fact(
        ExtractionRequest request, string subject, string predicate, string obj,
        VerificationStatus status, Provenance provenance) =>
        new(request.ScopeId, request.ArtifactRevision, subject, predicate, obj,
            EvidenceOrigin.Static, status, provenance);

    /// <summary>
    /// The markdown this scope EMITS for: its own directory, and no deeper.
    /// </summary>
    /// <remarks>
    /// <b>Non-recursive, and that is the whole de-duplication.</b> Discovery yields a scope for every
    /// directory holding a document with an id, so scopes nest; a recursive walk indexed
    /// <c>docs/adr/0001.md</c> from <c>knowledge:docs</c> AND <c>knowledge:docs/adr</c>, and the
    /// store held every knowledge fact ~2.7 times — 2,371 <c>node_class</c> rows for 878 distinct
    /// documents on TheTerrace. Reading only this directory makes each document belong to exactly
    /// one scope. It is safe ONLY because resolution no longer uses this walk: see
    /// <see cref="Survey"/> and DC-051.
    /// </remarks>
    internal static IEnumerable<string> OwnFiles(string directory)
    {
        string[] files;
        try { files = Directory.GetFiles(directory, "*.md"); }
        catch (Exception ex) when (ex is IOException or UnauthorizedAccessException) { yield break; }

        foreach (var file in files.Where(f => !IsTemplate(f))) yield return file;
    }

    /// <summary>
    /// Every markdown file under <paramref name="root"/>, and the id it declares — or none.
    /// </summary>
    /// <remarks>
    /// <para><b>Built ONCE per revision by <c>WorkspaceCore</c> and handed to every scope</b>, for
    /// the same reason <c>WorkspaceModules</c> is: thirty-nine knowledge scopes each walking the
    /// whole tree is thirty-nine walks, and resolving against what has already been extracted
    /// instead would make an edge depend on the order the scopes happened to run in.</para>
    ///
    /// <para><b>Only the frontmatter block is read.</b> The id is decided in the first few lines or
    /// not at all, and this opens every markdown file in the repository — 1,087 on TheTerrace, of
    /// which 209 are ordinary READMEs that are in the map purely so a link to one is reported as a
    /// boundary rather than as a broken cross-reference.</para>
    /// </remarks>
    public static WorkspaceKnowledge Survey(string root)
    {
        ArgumentNullException.ThrowIfNull(root);

        var documents = new Dictionary<string, string?>(StringComparer.OrdinalIgnoreCase);

        if (Directory.Exists(root))
        {
            foreach (var file in AllFiles(root))
            {
                documents[Path.GetFullPath(file)] =
                    KnowledgeFrontmatter.Read(Frontmatter(file), out _)?.Id;
            }
        }

        return new WorkspaceKnowledge(Path.GetFullPath(root), documents);
    }

    /// <summary>The frontmatter block of a file, delimiters included, or nothing.</summary>
    /// <remarks>
    /// The whole block rather than a fixed number of lines, so this and
    /// <see cref="KnowledgeFrontmatter.Read"/> answer "is this a node" identically. A cap would make
    /// the answer depend on how many typed links a document happens to declare first, and the header
    /// is not always short: MEASURED in this repository, three frontmatter blocks run to 62, 54 and
    /// 48 lines. A file that is a node to one reader and not to the other is the shape that produced
    /// DC-041 here — two correct components disagreeing, with nothing comparing them.
    /// </remarks>
    private static IReadOnlyList<string> Frontmatter(string file)
    {
        var block = new List<string>();

        try
        {
            using var reader = new StreamReader(file);

            if (reader.ReadLine() is not { } first || first.Trim() != "---") return block;

            block.Add(first);

            while (reader.ReadLine() is { } line)
            {
                block.Add(line);
                if (line.Trim() == "---") break;
            }
        }
        catch (Exception ex) when (ex is IOException or UnauthorizedAccessException)
        {
            return [];
        }

        return block;
    }

    /// <summary>Markdown anywhere under a root, excluding vendored and generated trees.</summary>
    internal static IEnumerable<string> AllFiles(string directory)
    {
        var skip = new HashSet<string>(StringComparer.OrdinalIgnoreCase)
        {
            "node_modules", "bin", "obj", ".git", ".vs", "dist", "build", "out",
            "__pycache__", ".venv", "venv", "packages", "artifacts",
        };

        var pending = new Stack<string>();
        pending.Push(directory);

        while (pending.Count > 0)
        {
            var current = pending.Pop();

            string[] files;
            try { files = Directory.GetFiles(current, "*.md"); }
            catch (Exception ex) when (ex is IOException or UnauthorizedAccessException) { continue; }

            foreach (var file in files.Where(f => !IsTemplate(f))) yield return file;

            IEnumerable<string> children;
            try { children = Directory.EnumerateDirectories(current); }
            catch (Exception ex) when (ex is IOException or UnauthorizedAccessException) { continue; }

            foreach (var child in children)
            {
                if (!skip.Contains(Path.GetFileName(child))) pending.Push(child);
            }
        }
    }

    /// <summary>
    /// Whether a file is a TEMPLATE rather than an artifact.
    /// </summary>
    /// <remarks>
    /// A template carries frontmatter in exactly the shape a real document does, with placeholders
    /// where the values go. Indexing one puts a node in the graph that describes the shape of a
    /// document rather than anything in this repository — measured on this repo, seven of them.
    /// </remarks>
    private static bool IsTemplate(string file) =>
        Path.GetFileName(file).Contains(".template.", StringComparison.OrdinalIgnoreCase);
}
