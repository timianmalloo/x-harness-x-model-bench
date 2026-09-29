namespace AiDe.Core.Extraction;

/// <summary>One declared bounded context.</summary>
public sealed record BoundedContext(
    string Name,
    string? Description,
    IReadOnlyList<string> Includes,
    IReadOnlyList<string> Tables);

/// <summary>A validation problem. Every one of these FAILS the load — none is a warning.</summary>
public sealed record ContextProblem(string Code, string Message);

/// <summary>
/// The declared context map, and what validating it against the real symbols found.
/// </summary>
/// <param name="Uncovered">
/// Symbols matched by no context. Reported so "we have contexts" cannot quietly mean "we have
/// contexts for 12% of the code".
/// </param>
public sealed record BoundedContextMap(
    IReadOnlyList<BoundedContext> Contexts,
    IReadOnlyList<ContextProblem> Problems,
    IReadOnlyList<string> Uncovered,
    int CoveredSymbols,
    int TotalSymbols,
    bool IsDeclared = true)
{
    public bool IsValid => Problems.Count == 0;

    public double Coverage => TotalSymbols == 0 ? 0 : (double)CoveredSymbols / TotalSymbols;

    public string Describe()
    {
        if (Contexts.Count == 0 && Problems.Count == 0)
        {
            return "No bounded contexts are declared. Add docs/bounded-contexts.yaml to group the domain view.";
        }

        if (Problems.Count > 0)
        {
            return $"The context map is invalid: {string.Join("; ", Problems.Take(3).Select(p => p.Message))}" +
                   (Problems.Count > 3 ? $" (+{Problems.Count - 3} more)" : string.Empty);
        }

        return $"{Contexts.Count} context(s) covering {Coverage:P0} of {TotalSymbols:N0} symbol(s)." +
               (Uncovered.Count > 0 ? $" {Uncovered.Count} uncovered, e.g. {string.Join(", ", Uncovered.Take(3))}." : string.Empty);
    }
}

/// <summary>
/// Reads and <b>validates</b> <c>docs/bounded-contexts.yaml</c> (ADR-0016).
/// </summary>
/// <remarks>
/// <para><b>Validated, not merely parsed.</b> A context naming a namespace that does not exist fails
/// loudly. A declaration file that silently tolerates stale entries becomes fiction within a release,
/// and fiction that looks like configuration is worse than no configuration.</para>
///
/// <para><b>A deliberately small YAML subset</b>, and anything outside it is an ERROR rather than a
/// best-effort guess. Hand-rolling a general YAML parser is how a config file starts meaning
/// something slightly different from what its author read — so this accepts exactly the shape ADR-0016
/// documents and rejects the rest by name. `simplify: a subset reader rather than a YAML dependency;
/// ceiling is the documented shape; upgrade trigger = a real map needs anchors, nested maps or
/// multi-line scalars.`</para>
/// </remarks>
public static class BoundedContextReader
{
    /// <summary>The file's conventional location, relative to a repository root.</summary>
    public const string DefaultRelativePath = "docs/bounded-contexts.yaml";

    /// <summary>
    /// Loads and validates the map against <paramref name="knownSymbols"/>.
    /// </summary>
    /// <param name="knownSymbols">
    /// Every symbol the extractor found. Validation without these would only check the file's shape,
    /// which is the half that never goes stale.
    /// </param>
    public static BoundedContextMap Load(
        string path, IReadOnlyCollection<string> knownSymbols, IReadOnlyCollection<string>? knownTables = null)
    {
        if (!File.Exists(path))
        {
            // IsDeclared: false, and it matters. With no map there is no uncovered list, so every
            // count reads as complete coverage — which is what a second repository's pane actually
            // said before this argument existed.
            return new BoundedContextMap([], [], [], 0, knownSymbols.Count, IsDeclared: false);
        }

        string[] lines;
        try { lines = File.ReadAllLines(path); }
        catch (IOException ex)
        {
            return new BoundedContextMap(
                [], [new ContextProblem("AIDE-CTX-UNREADABLE", $"could not read {Path.GetFileName(path)}: {ex.Message}")],
                [], 0, knownSymbols.Count);
        }

        var (contexts, problems) = Parse(lines);
        Validate(contexts, knownSymbols, knownTables ?? [], problems);

        // Judged against CODE symbols only. Measured on a real repository: the uncovered list was
        // led by 114 entries with no namespace, and they were Bicep parameters — bicep:main#appName
        // and friends. A bounded-context map is a statement about a codebase's domain; counting a
        // template's parameters against it blames the map for artifacts it was never about, and
        // makes the coverage number quietly wrong in the flattering direction for anyone who adds
        // infrastructure. The same shape as counting package types in the denominator, which was
        // fixed once already.
        knownSymbols = [.. knownSymbols.Where(IsCodeSymbol)];

        var covered = knownSymbols
            .Where(symbol => contexts.Any(c => c.Includes.Any(p => Matches(p, symbol))))
            .ToList();

        var uncovered = knownSymbols
            .Except(covered, StringComparer.Ordinal)
            .OrderBy(s => s, StringComparer.Ordinal)
            .ToList();

        return new BoundedContextMap(contexts, problems, uncovered, covered.Count, knownSymbols.Count);
    }

    /// <summary>
    /// Whether an id names a code symbol, as opposed to another artifact kind's subject.
    /// </summary>
    /// <remarks>
    /// Scope-qualified ids — <c>bicep:main#appName</c>, <c>table:Orders</c>, <c>schema:...</c> — are
    /// subjects of other artifact kinds. They are real evidence and they belong in the store; they
    /// are simply not what a bounded-context map is about. The rule lives here rather than at each
    /// call site because two callers already need it and a second copy is a second thing to drift.
    /// </remarks>
    public static bool IsCodeSymbol(string id) =>
        !string.IsNullOrEmpty(id) && !id.Contains(':', StringComparison.Ordinal);

    /// <summary>Whether a namespace pattern covers a symbol. <c>*</c> is a suffix wildcard only.</summary>
    public static bool Matches(string pattern, string symbol) =>
        pattern.EndsWith('*')
            ? symbol.StartsWith(pattern[..^1], StringComparison.Ordinal)
            : string.Equals(pattern, symbol, StringComparison.Ordinal);

    // ---------------------------------------------------------------- the subset reader

    private static (List<BoundedContext> Contexts, List<ContextProblem> Problems) Parse(string[] lines)
    {
        var contexts = new List<BoundedContext>();
        var problems = new List<ContextProblem>();

        string? name = null, description = null;
        var includes = new List<string>();
        var tables = new List<string>();
        var section = string.Empty;
        var sawContextsKey = false;

        void Flush(int lineNumber)
        {
            if (name is null) return;
            contexts.Add(new BoundedContext(name, description, [.. includes], [.. tables]));
            name = null;
            description = null;
            includes = [];
            tables = [];
        }

        for (var i = 0; i < lines.Length; i++)
        {
            var raw = lines[i];
            var line = raw.Split('#')[0].TrimEnd();
            if (line.Trim().Length == 0) continue;

            var trimmed = line.TrimStart();

            if (trimmed.StartsWith("contexts:", StringComparison.Ordinal))
            {
                sawContextsKey = true;
                continue;
            }

            if (trimmed.StartsWith("- name:", StringComparison.Ordinal))
            {
                Flush(i);
                name = Value(trimmed["- name:".Length..]);
                section = string.Empty;
                continue;
            }

            if (trimmed.StartsWith("description:", StringComparison.Ordinal))
            {
                var inline = trimmed["description:".Length..].Trim();

                // A folded block scalar. Added because the FIRST real context map needed one, which
                // is precisely the upgrade trigger the simplify: marker named — not the parser
                // growing every time something is inconvenient. Anchors and nested maps are still
                // rejected.
                if (inline is ">-" or ">" or "|-" or "|")
                {
                    var fold = inline.StartsWith('>');
                    var indent = line.Length - trimmed.Length;
                    var parts = new List<string>();

                    while (i + 1 < lines.Length)
                    {
                        var next = lines[i + 1];
                        if (next.Trim().Length == 0) { i++; parts.Add(string.Empty); continue; }
                        if (next.Length - next.TrimStart().Length <= indent) break;
                        parts.Add(next.Trim());
                        i++;
                    }

                    description = fold
                        ? string.Join(' ', parts.Where(x => x.Length > 0))
                        : string.Join(Environment.NewLine, parts);
                }
                else
                {
                    description = Value(inline);
                }

                section = string.Empty;
                continue;
            }

            if (trimmed.StartsWith("includes:", StringComparison.Ordinal)) { section = "includes"; continue; }
            if (trimmed.StartsWith("tables:", StringComparison.Ordinal)) { section = "tables"; continue; }

            if (trimmed.StartsWith("- ", StringComparison.Ordinal))
            {
                var item = Value(trimmed[2..]);
                if (section == "includes") includes.Add(item);
                else if (section == "tables") tables.Add(item);
                else problems.Add(new ContextProblem("AIDE-CTX-STRAY-ITEM",
                    $"line {i + 1}: a list item outside includes: or tables:"));

                continue;
            }

            // Anything else is outside the documented subset. Reported by LINE, because a config
            // file whose parser silently ignores what it does not understand is a file that means
            // something different from what its author read.
            problems.Add(new ContextProblem("AIDE-CTX-UNSUPPORTED",
                $"line {i + 1}: unsupported syntax '{trimmed}' — see ADR-0016 for the accepted shape"));
        }

        Flush(lines.Length);

        if (!sawContextsKey && contexts.Count == 0)
        {
            problems.Add(new ContextProblem("AIDE-CTX-EMPTY", "no contexts: key found"));
        }

        return (contexts, problems);
    }

    private static string Value(string text)
    {
        var trimmed = text.Trim();
        if (trimmed.Length >= 2 && (trimmed[0] == '"' || trimmed[0] == '\'') && trimmed[^1] == trimmed[0])
        {
            return trimmed[1..^1];
        }

        return trimmed;
    }

    // ---------------------------------------------------------------- validation

    private static void Validate(
        List<BoundedContext> contexts,
        IReadOnlyCollection<string> knownSymbols,
        IReadOnlyCollection<string> knownTables,
        List<ContextProblem> problems)
    {
        foreach (var duplicate in contexts.GroupBy(c => c.Name, StringComparer.Ordinal).Where(g => g.Count() > 1))
        {
            problems.Add(new ContextProblem("AIDE-CTX-DUPLICATE", $"context '{duplicate.Key}' is declared twice"));
        }

        foreach (var context in contexts)
        {
            if (string.IsNullOrWhiteSpace(context.Name))
            {
                problems.Add(new ContextProblem("AIDE-CTX-UNNAMED", "a context has no name"));
            }

            if (context.Includes.Count == 0)
            {
                problems.Add(new ContextProblem("AIDE-CTX-NO-INCLUDES", $"context '{context.Name}' includes nothing"));
            }

            // A pattern matching nothing is the drift ADR-0016 exists to make fail. It is almost
            // always a namespace that was renamed, and it is invisible without this check.
            foreach (var pattern in context.Includes.Where(p => !knownSymbols.Any(s => Matches(p, s))))
            {
                problems.Add(new ContextProblem("AIDE-CTX-UNKNOWN-NAMESPACE",
                    $"context '{context.Name}' includes '{pattern}', which matches no extracted symbol"));
            }

            foreach (var table in context.Tables.Where(t => knownTables.Count > 0 && !knownTables.Contains(t)))
            {
                problems.Add(new ContextProblem("AIDE-CTX-UNKNOWN-TABLE",
                    $"context '{context.Name}' claims table '{table}', which no migration creates"));
            }
        }

        // Overlap is an ERROR, not a merge. Contexts that overlap are not bounded, and quietly
        // picking the first match would hide a real modelling problem behind a working tool.
        foreach (var symbol in knownSymbols)
        {
            var owners = contexts.Where(c => c.Includes.Any(p => Matches(p, symbol))).Select(c => c.Name).ToList();
            if (owners.Count > 1)
            {
                problems.Add(new ContextProblem("AIDE-CTX-OVERLAP",
                    $"'{symbol}' is claimed by {string.Join(" and ", owners)}"));
            }
        }
    }
}
