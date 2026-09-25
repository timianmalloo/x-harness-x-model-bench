namespace AiDe.Core.Extraction;

/// <summary>
/// Source this build cannot read, counted so its absence from the graph is stated.
/// </summary>
/// <remarks>
/// <para><b>Measured on a fourth repository.</b> 63 Python files and 40 TypeScript files produced
/// <c>scopes: 0 of 0</c>, zero assertions and an <b>empty disclosure list</b>. Every number was
/// correct and the result was indistinguishable from an empty directory — "nothing here" and
/// "nothing I can read" rendered identically.</para>
///
/// <para><b>This is the same class three repositories running.</b> A missing context map read as
/// perfect coverage; a bounded search read as the whole workspace; unreadable source reads as no
/// source. Each time the arithmetic was right and the claim was false, which is why none of them
/// could be fixed by counting more carefully.</para>
///
/// <para><b>It names languages, never guesses at support.</b> Listing a language here is a statement
/// that files exist and were not read. It is not a roadmap, and the wording says so — a disclosure
/// that reads like a promise is a different kind of lie.</para>
/// </remarks>
public static class UnanalysedLanguages
{
    /// <summary>Extensions worth naming, and what to call them.</summary>
    /// <remarks>
    /// Deliberately short. A long list turns a real signal into noise, and an extension nobody has
    /// in a repository is a line of code that has never been read by anyone.
    /// </remarks>
    private static readonly (string Extension, string Language)[] Known =
    [
        // .py is NOT here: PythonExtractor reads it now, and disclosing a gap that has been closed
        // is the same defect as hiding one that has not. What Python extraction cannot see is
        // disclosed by that extractor, on the scope, in its own words.
        // .ts/.tsx/.js/.jsx are NOT here: TypeScriptExtractor reads them. What it cannot see is
        // disclosed by that extractor, on the scope, in its own words.
        // .sql is NOT here: SqlSchemaExtractor reads CREATE TABLE now. Leaving it would have said
        // `sql-not-analysed (2 file(s))` on a workspace whose eight tables had just been read —
        // which is the third time this list has needed the same correction, so the rule is worth
        // stating plainly: THIS LIST IS THE LAST STEP OF ADDING AN EXTRACTOR, not an afterthought.
        (".go", "Go"),
        (".rs", "Rust"),
        (".java", "Java"),
        (".kt", "Kotlin"),
        (".rb", "Ruby"),
        (".php", "PHP"),
        (".swift", "Swift"),
    ];

    internal static readonly HashSet<string> Skip = new(StringComparer.OrdinalIgnoreCase)
    {
        "bin", "obj", ".git", ".vs", "node_modules", "artifacts", "packages", "dist", "build",
        "__pycache__", ".venv", "venv", ".tox", "target", "vendor",
    };

    /// <summary>
    /// Disclosure strings for languages present in the workspace and not extracted.
    /// </summary>
    /// <remarks>
    /// The count is included because "some Python" and "10,760 Python files" are different
    /// statements about how much of a repository the graph is silent on. Capped at a shallow-ish
    /// walk depth by the skip list rather than by a limit, so the number is the real one.
    /// </remarks>
    public static IReadOnlyList<string> Survey(string rootPath)
    {
        if (!Directory.Exists(rootPath)) return [];

        var counts = new Dictionary<string, int>(StringComparer.Ordinal);
        var byExtension = Known.ToDictionary(k => k.Extension, k => k.Language, StringComparer.OrdinalIgnoreCase);

        foreach (var file in Enumerate(rootPath))
        {
            if (byExtension.TryGetValue(Path.GetExtension(file), out var language))
            {
                counts[language] = counts.GetValueOrDefault(language) + 1;
            }
        }

        return
        [
            .. counts
                .OrderByDescending(kv => kv.Value)
                .ThenBy(kv => kv.Key, StringComparer.Ordinal)
                .Select(kv => $"{kv.Key.ToLowerInvariant()}-not-analysed ({kv.Value:N0} file(s))")
        ];
    }

    private static IEnumerable<string> Enumerate(string directory)
    {
        var pending = new Stack<string>();
        pending.Push(directory);

        while (pending.Count > 0)
        {
            var current = pending.Pop();

            string[] files;
            try { files = Directory.GetFiles(current); }
            catch (Exception ex) when (ex is IOException or UnauthorizedAccessException) { continue; }

            foreach (var file in files) yield return file;

            IEnumerable<string> children;
            try { children = Directory.EnumerateDirectories(current); }
            catch (Exception ex) when (ex is IOException or UnauthorizedAccessException) { continue; }

            foreach (var child in children)
            {
                if (!Skip.Contains(Path.GetFileName(child))) pending.Push(child);
            }
        }
    }
}
