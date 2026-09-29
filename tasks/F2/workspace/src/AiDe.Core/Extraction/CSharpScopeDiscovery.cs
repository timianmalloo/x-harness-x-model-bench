namespace AiDe.Core.Extraction;

/// <summary>One extraction scope: a project built for one target framework.</summary>
/// <param name="ScopeId">Stable identity, of the form <c>csharp:&lt;project&gt;:&lt;tfm&gt;</c>.</param>
public sealed record ScopeDescriptor(string ScopeId, string ProjectPath, string TargetFramework)
{
    /// <summary>What the user sees in a pane title or a scope list.</summary>
    public string DisplayName =>
        $"{Path.GetFileNameWithoutExtension(ProjectPath)} ({TargetFramework})";
}

/// <summary>
/// Finds the C# scopes in a repository — <b>one per (project, target framework)</b>.
/// </summary>
/// <remarks>
/// <para>The grain is the finding, not a preference: a multi-targeted project's <c>#if</c>-gated
/// types genuinely differ between frameworks, so a single scope per project would have to pick one
/// and be silently wrong about the others (measured in <c>spikes/extraction-fidelity</c>).</para>
///
/// <para><b>Directories are skipped by name, and the list is deliberately short.</b> Skipping too
/// much is how a real project silently fails to appear; <c>bin</c>, <c>obj</c> and <c>.git</c> are
/// the ones that contain no source a user wrote.</para>
/// </remarks>
public static class CSharpScopeDiscovery
{
    // `artifacts` is the .NET SDK's own output layout — the modern sibling of bin and obj — and it
    // was missing here while `UnanalysedLanguages` already skipped it, so the two lists disagreed
    // about what counts as build output (DC-022). MEASURED on TheTerrace: TypeScript discovery
    // indexed `artifacts/s00/publish/wwwroot/_framework`, putting Blazor's published JavaScript in
    // the graph as source — nodes whose recorded path could not even be resolved back to a file.
    private static readonly string[] Skip =
        ["bin", "obj", ".git", "node_modules", "artifacts"];

    /// <summary>
    /// Every C# scope under <paramref name="rootPath"/>, ordered so the list is stable between runs.
    /// </summary>
    /// <remarks>
    /// A stable order matters more than it looks: scope ids feed generation numbers and the health
    /// view, and a set that reshuffles between runs makes two identical repositories look different.
    /// </remarks>
    public static IReadOnlyList<ScopeDescriptor> Discover(string rootPath, CSharpProjectReader? reader = null)
    {
        if (!Directory.Exists(rootPath)) return [];

        reader ??= new CSharpProjectReader();
        var scopes = new List<ScopeDescriptor>();

        foreach (var project in Projects(rootPath).OrderBy(p => p, StringComparer.OrdinalIgnoreCase))
        {
            var name = Path.GetFileNameWithoutExtension(project);
            var frameworks = reader.TargetFrameworks(project);

            if (frameworks.Count == 0)
            {
                // A project file that cannot be READ still gets a scope, deliberately. Returning
                // nothing here would make an unparseable project VANISH: not indexed, not failed,
                // not counted — the user would never learn it exists. The scope goes on to fail
                // extraction, which quarantines it and raises a health incident, so "we could not
                // read this project" is a reported outcome rather than an absence.
                scopes.Add(new ScopeDescriptor($"csharp:{name}:unknown", project, "unknown"));
                continue;
            }

            foreach (var tfm in frameworks)
            {
                scopes.Add(new ScopeDescriptor($"csharp:{name}:{tfm}", project, tfm));
            }
        }

        return scopes;
    }

    /// <summary>
    /// Every Phase-3 scope: C# projects, Bicep templates, and EF migration directories.
    /// </summary>
    /// <remarks>
    /// One list rather than three call sites, because a repository is indexed as a whole and a
    /// caller that had to remember to ask for infrastructure separately would eventually forget.
    /// </remarks>
    public static IReadOnlyList<ScopeDescriptor> DiscoverAll(string rootPath, CSharpProjectReader? reader = null)
    {
        var scopes = new List<ScopeDescriptor>(Discover(rootPath, reader));

        if (!Directory.Exists(rootPath)) return scopes;

        foreach (var template in Walk(rootPath, "*.bicep").OrderBy(p => p, StringComparer.OrdinalIgnoreCase))
        {
            var name = Path.GetFileNameWithoutExtension(template);
            scopes.Add(new ScopeDescriptor($"bicep:{name}", template, "bicep"));
        }

        // One scope per Migrations DIRECTORY, not per migration: the schema is the fold over all of
        // them, so a scope per file would be a scope per increment of an answer nobody wants
        // incrementally.
        foreach (var directory in MigrationDirectories(rootPath).OrderBy(p => p, StringComparer.OrdinalIgnoreCase))
        {
            var owner = Path.GetFileName(Path.GetDirectoryName(directory.TrimEnd(Path.DirectorySeparatorChar))!);
            scopes.Add(new ScopeDescriptor($"schema:{owner}", directory, "schema"));
        }

        // One scope per directory that directly contains Python, so a package is a scope and a
        // repository of loose scripts is one scope rather than none. Six repositories disclosed
        // unread Python before there was anything to read it with.
        foreach (var directory in PythonDirectories(rootPath).OrderBy(p => p, StringComparer.OrdinalIgnoreCase))
        {
            var relative = Path.GetRelativePath(rootPath, directory).Replace(Path.DirectorySeparatorChar, '/');
            scopes.Add(new ScopeDescriptor($"python:{relative}", directory, "python"));
        }

        // One scope per directory holding TypeScript or JavaScript directly, mirroring Python.
        foreach (var directory in TypeScriptDirectories(rootPath).OrderBy(p => p, StringComparer.OrdinalIgnoreCase))
        {
            var relative = Path.GetRelativePath(rootPath, directory).Replace(Path.DirectorySeparatorChar, '/');
            scopes.Add(new ScopeDescriptor($"typescript:{relative}", directory, "typescript"));
        }

        // One scope per directory holding .sql DIRECTLY. Found by measuring a second repository:
        // BioHacker declares its whole schema in one 197-line file with eight CREATE TABLEs, the
        // tool said `sql-not-analysed (2 file(s))` and produced zero joins, and every measurement
        // before it came from a codebase that happened to use EF migrations.
        foreach (var directory in SqlDirectories(rootPath).OrderBy(p => p, StringComparer.OrdinalIgnoreCase))
        {
            var relative = Path.GetRelativePath(rootPath, directory).Replace(Path.DirectorySeparatorChar, '/');
            scopes.Add(new ScopeDescriptor($"sql:{relative}", directory, "sql"));
        }

        // KNOWLEDGE. Reported by the user: the graph showed knowledge as zero and code as a large
        // count. The reader had existed since Phase 1, with tests, and no scope ever routed to it —
        // so the answer to "how much knowledge is in this repository" was computed over nothing.
        // A zero that means "nobody looked" reads as "there is none".
        foreach (var directory in KnowledgeDirectories(rootPath).OrderBy(p => p, StringComparer.OrdinalIgnoreCase))
        {
            var relative = Path.GetRelativePath(rootPath, directory).Replace(Path.DirectorySeparatorChar, '/');
            scopes.Add(new ScopeDescriptor($"knowledge:{relative}", directory, "knowledge"));
        }

        return scopes;
    }

    /// <summary>
    /// Directories holding markdown that DECLARES itself part of the graph.
    /// </summary>
    /// <remarks>
    /// A directory qualifies only if some file in it opens with frontmatter carrying an <c>id:</c>.
    /// Every repository is full of README and CHANGELOG files that are not nodes, and a scope per
    /// directory of ordinary prose would fill the graph with empty scopes and slow every index for
    /// nothing.
    /// </remarks>
    private static IEnumerable<string> KnowledgeDirectories(string root)
    {
        var skip = new HashSet<string>(Skip, StringComparer.OrdinalIgnoreCase)
        {
            ".vs", "dist", "build", "out", "__pycache__", ".venv", "venv", "packages", "artifacts",
        };

        var pending = new Stack<string>();
        pending.Push(root);

        while (pending.Count > 0)
        {
            var current = pending.Pop();

            string[] files;
            try { files = Directory.GetFiles(current, "*.md"); }
            catch (Exception ex) when (ex is IOException or UnauthorizedAccessException) { continue; }

            if (files.Where(f => !IsTemplate(f)).Any(DeclaresAnId)) yield return current;

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

    /// <summary>Whether a markdown file opens with frontmatter that names an id.</summary>
    /// <remarks>
    /// Reads the first few lines rather than the file: this runs over every markdown file in a
    /// repository, and the answer is decided in the first handful of them or not at all.
    /// </remarks>
    private static bool DeclaresAnId(string file)
    {
        try
        {
            using var reader = new StreamReader(file);

            if (reader.ReadLine()?.Trim() != "---") return false;

            for (var i = 0; i < 40; i++)
            {
                var line = reader.ReadLine();

                if (line is null || line.Trim() == "---") return false;
                if (line.TrimStart().StartsWith("id:", StringComparison.Ordinal)) return true;
            }

            return false;
        }
        catch (Exception ex) when (ex is IOException or UnauthorizedAccessException)
        {
            return false;
        }
    }

    /// <summary>Directories holding SQL directly, excluding build output and vendored trees.</summary>
    private static IEnumerable<string> SqlDirectories(string root)
    {
        var skip = new HashSet<string>(Skip, StringComparer.OrdinalIgnoreCase) { "packages" };

        var pending = new Stack<string>();
        pending.Push(root);

        while (pending.Count > 0)
        {
            var current = pending.Pop();

            string[] files;
            try { files = Directory.GetFiles(current, "*.sql"); }
            catch (Exception ex) when (ex is IOException or UnauthorizedAccessException) { continue; }

            if (files.Length > 0) yield return current;

            IEnumerable<string> children;
            try { children = Directory.EnumerateDirectories(current); }
            catch (Exception ex) when (ex is IOException or UnauthorizedAccessException) { continue; }

            foreach (var child in children)
            {
                if (!skip.Contains(Path.GetFileName(child))) pending.Push(child);
            }
        }
    }

    /// <summary>Directories holding TypeScript or JavaScript directly, excluding vendored trees.</summary>
    private static IEnumerable<string> TypeScriptDirectories(string root)
    {
        // ONE list, defined on the reader that uses it. This set and the extractor's own directory
        // walk were two lists deciding the same question and they disagreed: discovery skipped
        // `bin`, `obj` and `artifacts`, the extractor did not, so a scope rooted at `tests/` was
        // created correctly and then indexed `tests/X/bin/Debug/net10.0/.playwright/package/` — a
        // vendored browser driver, twice, once per build configuration. That is DC-022's shape, and
        // the same divergence the note above `Skip` already records about `artifacts`.
        // Published web output stays here: `_framework` is Blazor's and a `publish` folder is the
        // result of a build rather than anything anybody wrote.
        var skip = new HashSet<string>(Skip, StringComparer.OrdinalIgnoreCase);
        skip.UnionWith(TypeScriptExtractor.SkippedDirectories);

        string[] wanted = [".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs"];

        var pending = new Stack<string>();
        pending.Push(root);

        while (pending.Count > 0)
        {
            var current = pending.Pop();

            string[] files;
            try { files = Directory.GetFiles(current); }
            catch (Exception ex) when (ex is IOException or UnauthorizedAccessException) { continue; }

            if (files.Any(f => !f.EndsWith(".d.ts", StringComparison.OrdinalIgnoreCase)
                    && wanted.Contains(Path.GetExtension(f), StringComparer.OrdinalIgnoreCase)))
            {
                yield return current;
            }

            IEnumerable<string> children;
            try { children = Directory.EnumerateDirectories(current); }
            catch (Exception ex) when (ex is IOException or UnauthorizedAccessException) { continue; }

            foreach (var child in children)
            {
                if (!skip.Contains(Path.GetFileName(child))) pending.Push(child);
            }
        }
    }

    /// <summary>Directories holding Python directly, excluding vendored and generated trees.</summary>
    private static IEnumerable<string> PythonDirectories(string root)
    {
        var skip = new HashSet<string>(Skip, StringComparer.OrdinalIgnoreCase)
        {
            "__pycache__", ".venv", "venv", ".tox", "site-packages",
        };

        var pending = new Stack<string>();
        pending.Push(root);

        while (pending.Count > 0)
        {
            var current = pending.Pop();

            string[] files;
            try { files = Directory.GetFiles(current, "*.py"); }
            catch (Exception ex) when (ex is IOException or UnauthorizedAccessException) { continue; }

            if (files.Length > 0) yield return current;

            IEnumerable<string> children;
            try { children = Directory.EnumerateDirectories(current); }
            catch (Exception ex) when (ex is IOException or UnauthorizedAccessException) { continue; }

            foreach (var child in children)
            {
                if (!skip.Contains(Path.GetFileName(child))) pending.Push(child);
            }
        }
    }

    private static IEnumerable<string> MigrationDirectories(string root)
    {
        var pending = new Stack<string>();
        pending.Push(root);

        while (pending.Count > 0)
        {
            var directory = pending.Pop();

            IEnumerable<string> children;
            try { children = Directory.EnumerateDirectories(directory); }
            catch (UnauthorizedAccessException) { continue; }
            catch (IOException) { continue; }

            foreach (var child in children)
            {
                var name = Path.GetFileName(child);
                if (Skip.Contains(name, StringComparer.OrdinalIgnoreCase)) continue;

                if (string.Equals(name, "Migrations", StringComparison.OrdinalIgnoreCase))
                {
                    yield return child;
                    continue;
                }

                pending.Push(child);
            }
        }
    }

    private static IEnumerable<string> Walk(string root, string pattern)
    {
        var pending = new Stack<string>();
        pending.Push(root);

        while (pending.Count > 0)
        {
            var directory = pending.Pop();

            string[] files;
            try { files = Directory.GetFiles(directory, pattern); }
            catch (UnauthorizedAccessException) { continue; }
            catch (IOException) { continue; }

            foreach (var file in files) yield return file;

            IEnumerable<string> children;
            try { children = Directory.EnumerateDirectories(directory); }
            catch (UnauthorizedAccessException) { continue; }
            catch (IOException) { continue; }

            foreach (var child in children)
            {
                if (Skip.Contains(Path.GetFileName(child), StringComparer.OrdinalIgnoreCase)) continue;
                pending.Push(child);
            }
        }
    }

    private static IEnumerable<string> Projects(string root)
    {
        var pending = new Stack<string>();
        pending.Push(root);

        while (pending.Count > 0)
        {
            var directory = pending.Pop();

            string[] entries;
            try { entries = Directory.GetFiles(directory, "*.csproj"); }
            catch (UnauthorizedAccessException) { continue; }
            catch (IOException) { continue; }

            foreach (var project in entries) yield return project;

            IEnumerable<string> children;
            try { children = Directory.EnumerateDirectories(directory); }
            catch (UnauthorizedAccessException) { continue; }
            catch (IOException) { continue; }

            foreach (var child in children)
            {
                var name = Path.GetFileName(child);
                if (Skip.Contains(name, StringComparer.OrdinalIgnoreCase)) continue;
                pending.Push(child);
            }
        }
    }
}

/// <summary>
/// Routes an extraction to the extractor that owns its scope kind.
/// </summary>
/// <remarks>
/// Routing on the scope id's prefix rather than on a registration table because the prefix is
/// already the scope's identity — a separate mapping is a second thing that can disagree with the
/// ids actually in the store.
/// </remarks>
public sealed class CompositeExtractor(
    IExtractor csharp,
    IExtractor fallback,
    IExtractor? bicep = null,
    IExtractor? schema = null,
    IExtractor? python = null,
    IExtractor? typescript = null,
    IExtractor? sql = null,
    IExtractor? knowledge = null) : IExtractor
{
    public string ScopeKind => "composite";

    /// <summary>Extractors by scope-id prefix. Added ones need no change here.</summary>
    private readonly Dictionary<string, IExtractor> _routes = new(StringComparer.Ordinal)
    {
        ["csharp:"] = csharp,
        ["bicep:"] = bicep ?? new BicepExtractor(),
        ["schema:"] = schema ?? new EfSchemaExtractor(),
        ["python:"] = python ?? new PythonExtractor(),
        ["typescript:"] = typescript ?? new TypeScriptExtractor(),
        ["sql:"] = sql ?? new SqlSchemaExtractor(),
        ["knowledge:"] = knowledge ?? new KnowledgeExtractor(),
    };

    /// <summary>Which extractor a scope id resolves to. Exposed so routing can be ASSERTED.</summary>
    /// <remarks>
    /// The router is four positional constructor parameters, and getting their order wrong is silent:
    /// a mis-ordered composite routes bicep scopes to the schema extractor, both fail, and the run
    /// reports a repository with no infrastructure in it. That happened. A test can now read the
    /// decision instead of trusting the call site.
    /// </remarks>
    public IExtractor RouteFor(string scopeId)
    {
        foreach (var (prefix, extractor) in _routes)
        {
            if (scopeId.StartsWith(prefix, StringComparison.Ordinal))
            {
                return extractor;
            }
        }

        return fallback;
    }

    public Task<ExtractionResult> ExtractAsync(ExtractionRequest request, CancellationToken cancellationToken) =>
        RouteFor(request.ScopeId).ExtractAsync(request, cancellationToken);

}
