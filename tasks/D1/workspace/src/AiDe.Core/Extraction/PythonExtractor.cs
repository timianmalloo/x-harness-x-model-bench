using System.Text.RegularExpressions;
using AiDe.Core.Facts;

namespace AiDe.Core.Extraction;

/// <summary>
/// Python modules, their top-level declarations, and what they import.
/// </summary>
/// <remarks>
/// <para><b>Six repositories disclosed unread Python before this existed.</b> The disclosure was the
/// right behaviour and it is not a substitute for reading the code — a graph that says "there is
/// Python here and I cannot see it" is honest and still blind.</para>
///
/// <para><b>It reads structure, not semantics, and says so.</b> There is no Python compiler here:
/// this recognises module-level <c>import</c>, <c>from … import</c>, <c>class</c> and <c>def</c> at
/// column zero, and nothing else. Names are not resolved, so an import edge points at the module
/// PATH as written rather than at a symbol; a call graph is not attempted. Every one of those gaps
/// is a disclosure on the scope rather than a silence — the C# extractor's rule, applied to a
/// language where the gap is much wider.</para>
///
/// <para><b>Why not a real parser.</b> The Solution-Selection Ladder asks for the smallest thing that
/// is still correct, and correct here means "does not assert what it cannot see". A dependency on a
/// Python grammar would buy type resolution this product has nowhere to put yet, and would make the
/// extractor's reach a question about a third-party package's version. When call edges or resolved
/// imports are actually wanted, that is the upgrade trigger.</para>
///
/// <para><c>simplify: line-oriented recognition rather than a Python grammar; ceiling is top-level
/// declarations and import edges with unresolved targets; upgrade trigger = a consumer needs call
/// edges, resolved import targets, or anything nested inside a class or function.</c></para>
/// </remarks>
public sealed class PythonExtractor : IExtractor
{
    public string ScopeKind => "python";

    /// <summary>Gaps this extractor always has, stated on every scope it produces.</summary>
    public static class Disclosures
    {
        /// <summary>No name resolution: an import names a module path, not a symbol.</summary>
        public const string ImportsNotResolved = "python-imports-not-resolved";

        /// <summary>Imports naming the standard library — a boundary of the product, not a gap in it.</summary>
        public const string StandardLibraryNotIndexed = "python-standard-library-not-indexed";

        /// <summary>
        /// Declarations nested deeper than a class's own body — closures, and definitions inside
        /// methods.
        /// </summary>
        /// <remarks>
        /// A class's METHODS are read now, as members. What remains is what a module cannot reach:
        /// MEASURED across 113 Python files in two repositories, 42 closures and 12 classes declared
        /// inside another class or a function. Counted rather than stated flatly, because "nested
        /// declarations are not analysed" and "42 closures are not analysed" are different claims
        /// about how much is missing (DC-050).
        /// </remarks>
        public const string NestedDeclarationsNotAnalysed = "python-nested-declarations-not-analysed";

        /// <summary>Nothing dynamic is followed — importlib, __import__, conditional imports.</summary>
        public const string DynamicImportsNotAnalysed = "python-dynamic-imports-not-analysed";
    }

    // Column zero on purpose. An indented `def` is a method or a closure, and claiming it as a
    // module-level function would put a symbol in the graph that no importer can reach.
    private static readonly Regex TopLevelClass =
        new(@"^class\s+([A-Za-z_][A-Za-z0-9_]*)", RegexOptions.Compiled | RegexOptions.Multiline);

    private static readonly Regex TopLevelDef =
        new(@"^(?:async\s+)?def\s+([A-Za-z_][A-Za-z0-9_]*)", RegexOptions.Compiled | RegexOptions.Multiline);

    private static readonly Regex ImportModule =
        new(@"^import\s+([A-Za-z_][A-Za-z0-9_.]*)", RegexOptions.Compiled | RegexOptions.Multiline);

    private static readonly Regex FromImport =
        new(@"^from\s+([A-Za-z_.][A-Za-z0-9_.]*)\s+import\s", RegexOptions.Compiled | RegexOptions.Multiline);

    public Task<ExtractionResult> ExtractAsync(ExtractionRequest request, CancellationToken cancellationToken)
    {
        ArgumentNullException.ThrowIfNull(request);

        // RootPath IS the scope's directory: discovery passes the scope's own path as the override,
        // the same way the Bicep extractor receives a template path rather than a repository root.
        // Deriving it from the scope id instead produced pkg\pkg and a scope that failed every run.
        var directory = request.RootPath;

        if (!Directory.Exists(directory))
        {
            return Task.FromResult(new ExtractionResult([], Complete: false,
                [new ExtractionDiagnostic("AIDE-PY-NO-DIRECTORY", request.ScopeId,
                    $"the scope's directory does not exist: {directory}")]));
        }

        var assertions = new List<EvidenceAssertion>();
        var unreadable = new List<string>();

        // Every module in THIS scope, so an import naming one of them can be resolved to it rather
        // than left as a string. Collected first because an import may name a module that appears
        // later in the walk, and resolution that depends on file order is resolution that is wrong
        // half the time.
        var prefix = ModuleNaming.ScopePrefix(request.ScopeId);

        var modules = Files(directory)
            .Select(f => ModuleNaming.Qualify(prefix, ModuleName(directory, f)))
            .ToHashSet(StringComparer.Ordinal);

        // The rest of the workspace, when the caller supplied it. Kept separate from this scope's
        // own modules so the two can be distinguished in the edge that results.
        var elsewhere = request.WorkspaceModules ?? new HashSet<string>(StringComparer.Ordinal);

        // The gaps first, so a scope truncated later still carries what it cannot see. The same
        // ordering the C# extractor uses, and for the same reason.
        // ImportsNotResolved is NOT here: it is now conditional and carries a count, because some
        // imports resolve. A blanket "imports are not resolved" was true when none were and became a
        // closed gap reported as open the moment resolution landed — the same defect as hiding one.
        var unresolved = 0;
        var standardLibrary = 0;
        var nestedDeclarations = 0;

        assertions.Add(ScopeFact(
            request, directory, ScopeNode(request.ScopeId), "discloses",
            Disclosures.DynamicImportsNotAnalysed));

        foreach (var file in Files(directory))
        {
            cancellationToken.ThrowIfCancellationRequested();

            string text;
            try { text = File.ReadAllText(file); }
            catch (Exception ex) when (ex is IOException or UnauthorizedAccessException)
            {
                unreadable.Add(Path.GetFileName(file));
                continue;
            }

            // A docstring holds example code at column zero — the one place this reader's
            // column-zero rule cannot tell documentation from declaration.
            text = SourceText.WithoutPythonComments(text);

            var module = ModuleNaming.Qualify(prefix, ModuleName(directory, file));
            var relativePath = ArtifactPath(directory, file);
            assertions.Add(Fact(request, relativePath, module, "has_type", "python-module"));

            foreach (var name in Names(TopLevelClass, text))
            {
                assertions.Add(Fact(request, relativePath, $"{module}.{name}", "has_type", "python-class"));
                assertions.Add(Fact(request, relativePath, $"{module}.{name}", "declared_in", module));
            }

            // A CLASS'S METHODS, as members.
            //
            // The column-zero rule was right about what it refused — an indented `def` is not a
            // module-level function and claiming it as one puts a symbol in the graph no importer
            // can reach. It was wrong that the only options were "module function" or "invisible": a
            // method is a member OF its class, exactly as `has_member` already records for C#, and a
            // class with no members renders as an empty box.
            //
            // MEASURED across 113 Python files in two repositories: 33 methods on 22 classes. Thin,
            // and the difference between a class diagram that works for Python and one that does not.
            var methods = Methods(text, out var nested);

            foreach (var (owner, method) in methods)
            {
                assertions.Add(Fact(request, relativePath, $"{module}.{owner}", "has_member", method));
            }

            nestedDeclarations += nested;

            foreach (var name in Names(TopLevelDef, text))
            {
                assertions.Add(Fact(request, relativePath, $"{module}.{name}", "has_type", "python-function"));
                assertions.Add(Fact(request, relativePath, $"{module}.{name}", "declared_in", module));
            }

            // INFERRED, and labelled: the target is the module path as written. Whether it resolves
            // to a file in this repository, a package, or nothing at all is not established here,
            // and calling that Verified would be the exact defect DC-022 is about.
            foreach (var target in Names(ImportModule, text).Concat(Names(FromImport, text)).Distinct(StringComparer.Ordinal))
            {
                // A relative import (`from .models import X`) is resolved against the importing
                // module's package; an absolute one is matched against the scope's modules as
                // written. Anything that matches a module this scope actually contains becomes
                // VERIFIED — the target is a file that exists and was read.
                // This scope first, then the workspace. A module in THIS directory is what the
                // import means when both could match, because that is what Python itself does with
                // the package directory ahead of the wider path.
                var resolved = Resolve(target, module, modules) ?? Resolve(target, module, elsewhere);

                // The standard library is not a gap. Counting `import sys` as something this scope
                // "does not contain" was arithmetically true and read as a coverage hole — MEASURED
                // on a real workspace, all 246 unresolved imports across all 32 distinct names were
                // stdlib. The C# extractor already declines to draw the BCL for the same reason.
                // The standard library is COUNTED, not drawn.
                //
                // Counting `import sys` as something this scope "does not contain" was arithmetically
                // true and read as a coverage hole — MEASURED on a real workspace, all 246 unresolved
                // imports across all 32 distinct names were stdlib. Drawing them is the same mistake
                // one layer along: 226 edges to `sys`, `os`, `json` and `re` put the standard library
                // among the most connected nodes in the graph, and the C# extractor already declines
                // to draw the BCL because "a first view centred on the BCL is not a picture of
                // anybody's domain".
                if (resolved is null && PythonStandardLibrary.Contains(target))
                {
                    standardLibrary++;
                    continue;
                }

                if (resolved is null) unresolved++;

                assertions.Add(resolved is null
                    // Unresolved stays INFERRED and keeps the name as written: it may be a package,
                    // a module in another scope, or nothing. Asserting which would be the guess
                    // DC-022 is about.
                    ? Fact(request, relativePath, module, "imports", target, VerificationStatus.Inferred)
                    : Fact(request, relativePath, module, "imports", resolved, VerificationStatus.Verified));
            }
        }

        if (unresolved > 0)
        {
            // Counted, because "imports are not resolved" and "31 of 330 imports point outside this
            // scope" are different statements about how much of the graph is a guess.
            assertions.Add(ScopeFact(request, directory, ScopeNode(request.ScopeId), "discloses",
                $"{Disclosures.ImportsNotResolved} ({unresolved:N0} import(s) name something this " +
                "scope does not contain)"));
        }

        if (nestedDeclarations > 0)
        {
            // Conditional now, and counted. It used to fire on every scope whether or not anything
            // was nested, which trains a reader to skip disclosures (DC-025) — and it said nothing
            // about size, which is what decides whether the gap is worth closing.
            assertions.Add(ScopeFact(request, directory, ScopeNode(request.ScopeId), "discloses",
                $"{Disclosures.NestedDeclarationsNotAnalysed} ({nestedDeclarations:N0} declaration(s) " +
                "are nested inside a function or a method and cannot be reached by an importer)"));
        }

        if (standardLibrary > 0)
        {
            // Said plainly, and separately from the unknowns. "The standard library is not indexed"
            // is a boundary of this product; "31 imports name something nobody can identify" is a
            // gap in it. Reporting them as one number made the second invisible inside the first.
            assertions.Add(ScopeFact(request, directory, ScopeNode(request.ScopeId), "discloses",
                $"{Disclosures.StandardLibraryNotIndexed} ({standardLibrary:N0} import(s) name the " +
                "Python standard library, which this product does not index)"));
        }

        if (unreadable.Count > 0)
        {
            assertions.Add(ScopeFact(request, directory, ScopeNode(request.ScopeId), "discloses",
                $"python-source-unreadable ({unreadable.Count:N0} file(s))"));
        }

        // Complete: the disclosures are IN the snapshot rather than missing from it, so a scope that
        // read what it could is a whole answer about a narrow question.
        
        // Identical facts are ONE fact. Two files can share a module name — `app.ts` beside a
        // compiled `app.js` is the common case, and an import specifier resolves to one module
        // regardless — so the same triple can be asserted twice in a scope. The store's natural key
        // rejects that (P1-STORE-05, deliberately), which surfaced as a raw SQLite constraint error
        // from the middle of an index on a real repository. Deduplicating here is the honest fix:
        // the duplicate carries no information, and silencing the key would weaken a real control.
        var deduplicated = ExtractionFacts.Distinct(assertions);

        return Task.FromResult(new ExtractionResult(deduplicated, Complete: true, []));
    }

    /// <summary>
    /// The module this import names, when the scope contains it. Null otherwise.
    /// </summary>
    /// <remarks>
    /// Leading dots are Python's relative-import syntax: one dot is the importing module's own
    /// package, each further dot climbs one level. Resolved textually against the modules actually
    /// found, so a match means a file that exists and was read — which is what lets the edge be
    /// Verified rather than Inferred.
    /// </remarks>
    internal static string? Resolve(string target, string importingModule, IReadOnlySet<string> modules)
    {
        // Module IDS are repository-relative PATHS; import TARGETS are dotted names. An absolute
        // import is read from the repository root, which is exactly what a path id is measured from,
        // so `a.b.c` is the module `a/b/c`.
        if (!target.StartsWith('.'))
        {
            var absolute = target.Replace('.', '/');

            if (modules.Contains(absolute)) return absolute;

            // A package import names the directory; its module is the __init__ inside it.
            var package = absolute + "/__init__";
            return modules.Contains(package) ? package : null;
        }

        var levels = target.TakeWhile(c => c == '.').Count();
        var rest = target[levels..].Replace('.', '/');

        // The importing module's package is its path minus the file; each extra dot climbs one more.
        var parts = importingModule.Split('/');
        var keep = parts.Length - levels;
        if (keep < 0) return null;

        var directory = string.Join('/', parts.Take(keep));
        var candidate = string.IsNullOrEmpty(rest)
            ? directory
            : (directory.Length == 0 ? rest : directory + "/" + rest);

        if (modules.Contains(candidate)) return candidate;

        var relativePackage = candidate.Length == 0 ? "__init__" : candidate + "/__init__";
        return modules.Contains(relativePackage) ? relativePackage : null;
    }

    private static IEnumerable<string> Names(Regex pattern, string text) =>
        pattern.Matches(text).Select(m => m.Groups[1].Value).Where(n => n.Length > 0);

    /// <summary>A module's dotted name, from its path relative to the scope.</summary>
    /// <summary>
    /// Each top-level class and the methods declared directly in its body.
    /// </summary>
    /// <param name="nested">
    /// Declarations deeper than a class body — closures, and definitions inside methods. Counted so
    /// the scope can disclose the size of what it still cannot see.
    /// </param>
    /// <remarks>
    /// <para><b>One indent level, not any.</b> A `def` in a class's own body is a method; a `def`
    /// inside that method is a closure, and a closure is not a member of anything an importer can
    /// reach. The body's indent is taken from the class's FIRST indented line rather than assumed to
    /// be four spaces, because a file that indents with tabs or eight spaces is still Python and a
    /// hard-coded width would read its methods as closures.</para>
    ///
    /// <para><c>simplify: indentation tracking rather than a Python grammar; ceiling is methods of a
    /// top-level class; upgrade trigger = a consumer needs signatures, decorators, or anything
    /// declared inside a function.</c></para>
    /// </remarks>
    private static IEnumerable<(string Owner, string Method)> Methods(string text, out int nested)
    {
        var found = new List<(string, string)>();
        var deeper = 0;

        string? owner = null;
        var bodyIndent = -1;

        foreach (var raw in text.Split('\n'))
        {
            var line = raw.TrimEnd('\r');
            var trimmed = line.TrimStart();

            if (trimmed.Length == 0 || trimmed[0] == '#') continue;

            var indent = line.Length - trimmed.Length;

            if (indent == 0)
            {
                // A new column-zero statement ends whatever class was open, including another class.
                owner = null;
                bodyIndent = -1;

                var top = TopLevelClass.Match(line);
                if (top.Success) owner = top.Groups[1].Value;

                continue;
            }

            if (owner is null) continue;

            // The first indented line of the class fixes what "its own body" means.
            if (bodyIndent < 0) bodyIndent = indent;

            var isDeclaration = trimmed.StartsWith("def ", StringComparison.Ordinal)
                || trimmed.StartsWith("async def ", StringComparison.Ordinal)
                || trimmed.StartsWith("class ", StringComparison.Ordinal);

            if (!isDeclaration) continue;

            if (indent > bodyIndent)
            {
                deeper++;
                continue;
            }

            var name = MethodName.Match(trimmed);
            if (name.Success) found.Add((owner, name.Groups[1].Value));
        }

        nested = deeper;
        return found;
    }

    /// <summary>The name in a `def`, `async def` or `class` line already known to be indented.</summary>
    private static readonly Regex MethodName =
        new(@"^(?:async\s+)?(?:def|class)\s+([A-Za-z_][A-Za-z0-9_]*)", RegexOptions.Compiled);

    private static string ModuleName(string directory, string file)
    {
        var relative = Path.GetRelativePath(directory, file);
        var withoutExtension = relative[..^Path.GetExtension(relative).Length];

        return withoutExtension
            .Replace(Path.DirectorySeparatorChar, '/')
            .Replace(Path.AltDirectorySeparatorChar, '/');
    }

    private static string ScopeNode(string scopeId) => scopeId;

    /// <summary>A file's path relative to the scope, in the form a reader can open.</summary>
    /// <remarks>
    /// Separate from <see cref="ModuleName"/>, which drops the extension because a module id is not
    /// a path. Conflating the two is how <c>Provenance.ArtifactPathId</c> came to hold a scope id.
    /// Forward slashes, so a value written on one platform resolves on the other.
    /// </remarks>
    private static string ArtifactPath(string directory, string file) =>
        Path.GetRelativePath(directory, file)
            .Replace(Path.DirectorySeparatorChar, '/')
            .Replace(Path.AltDirectorySeparatorChar, '/');

    /// <summary>
    /// A fact about one file, citing that file.
    /// </summary>
    /// <remarks>
    /// <para><b>DC-229.</b> <paramref name="artifactPath"/> is required and positional on purpose:
    /// this helper used to derive the citation itself, from <c>request.ScopeId</c>, so every one of
    /// its callers emitted a value that names no file — and the compiler had nothing to object to.
    /// The same two lines in the TypeScript reader produced the same defect, which is what made it a
    /// class rather than a slip.</para>
    ///
    /// <para><c>simplify: SourceLocation stays null here; <see cref="Names"/> and
    /// <see cref="Methods"/> return names rather than matches, so no line number is in hand at the
    /// call site. The path resolves, which is what View source and content search need; upgrade
    /// trigger = a consumer needs to jump to the declaration rather than open the file.</c></para>
    /// </remarks>
    private static EvidenceAssertion Fact(
        ExtractionRequest request, string artifactPath, string subject, string predicate, string obj,
        VerificationStatus status = VerificationStatus.Verified, string? sourceLocation = null) =>
        new(request.ScopeId, request.ArtifactRevision, subject, predicate, obj,
            EvidenceOrigin.Static, status,
            new Provenance(artifactPath, sourceLocation, "python-extractor", "1.0.0", DateTimeOffset.UtcNow));

    /// <summary>
    /// A fact about the scope as a whole — a disclosure — citing the scope's own directory.
    /// </summary>
    /// <remarks>
    /// The shape the EF-schema, SQL and knowledge readers already use for their scope rows: the
    /// directory's leaf name, which resolves as the scope root. A disclosure belongs to no single
    /// file, and naming one would be a citation that misleads rather than one that is merely absent.
    /// </remarks>
    private static EvidenceAssertion ScopeFact(
        ExtractionRequest request, string directory, string subject, string predicate, string obj,
        VerificationStatus status = VerificationStatus.Verified) =>
        new(request.ScopeId, request.ArtifactRevision, subject, predicate, obj,
            EvidenceOrigin.Static, status,
            new Provenance(
                Path.GetFileName(Path.TrimEndingDirectorySeparator(directory)), "1:1",
                "python-extractor", "1.0.0", DateTimeOffset.UtcNow));

    /// <summary>Python files directly under the scope, and under its packages.</summary>
    private static IEnumerable<string> Files(string directory)
    {
        var skip = new HashSet<string>(StringComparer.OrdinalIgnoreCase)
        {
            "__pycache__", ".venv", "venv", ".tox", "node_modules", ".git", "build", "dist",
        };

        var pending = new Stack<string>();
        pending.Push(directory);

        while (pending.Count > 0)
        {
            var current = pending.Pop();

            string[] files;
            try { files = Directory.GetFiles(current, "*.py"); }
            catch (Exception ex) when (ex is IOException or UnauthorizedAccessException) { continue; }

            foreach (var file in files) yield return file;

            IEnumerable<string> children;
            try { children = Directory.EnumerateDirectories(current); }
            catch (Exception ex) when (ex is IOException or UnauthorizedAccessException) { continue; }

            foreach (var child in children)
            {
                if (!skip.Contains(Path.GetFileName(child))) pending.Push(child);
            }
        }
    }
}
