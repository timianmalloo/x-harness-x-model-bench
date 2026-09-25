using AiDe.Core.Extraction;

namespace AiDe.Core.Projections;

/// <summary>
/// How many census-folders and file-artifacts a tree query asks for.
/// </summary>
/// <remarks>
/// Two integers only. A named drop-set is a projection/test-host parameter, never a field here
/// and never an IPC member (ADR-0038 N6).
/// </remarks>
public sealed record SolutionTreeQuery(
    int MaxCensusFolders = SolutionTreeProjection.DefaultMaxCensusFolders,
    int MaxFileArtifacts = SolutionTreeProjection.DefaultMaxFileArtifacts);

public enum SolutionTreeNodeKind { FileArtifact, CensusFolder }

public enum CensusFolderCoverage { IndexedParent, Unindexed }

public enum SolutionTreeShortfallCause
{
    Io, Permission, Cap, UnresolvablePath, PythonTsPerFile, ReparsePoint
}

/// <summary>One tree node is exactly one <c>(Path, Kind)</c>.</summary>
/// <param name="Path">Workspace-relative, <c>/</c> separators, no trailing slash. Root is <c>""</c>.</param>
/// <param name="Coverage">Non-null iff <see cref="Kind"/> is <see cref="SolutionTreeNodeKind.CensusFolder"/>.</param>
/// <param name="NodeId">Activate handle for a file-artifact; null on census-folders.</param>
/// <param name="NodeKind"><c>node_dim.node_kind</c> / <c>has_type</c> for glyphs; N8 maps chrome.</param>
public sealed record SolutionTreeNode(
    string Path,
    SolutionTreeNodeKind Kind,
    CensusFolderCoverage? Coverage,
    string? NodeId,
    string? NodeKind);

public sealed record SolutionTreeDisclosure(
    SolutionTreeShortfallCause Cause,
    string Message,
    int? Count,
    string? Path);

public sealed record SolutionTreeResult(
    IReadOnlyList<SolutionTreeNode> Nodes,
    int SkipListedDirectoriesOmitted,
    int OmittedByCap,
    IReadOnlyList<SolutionTreeDisclosure> Disclosures,
    string SourceRevision);

/// <summary>
/// Query-time census join: disk-now folders minus <see cref="UnanalysedLanguages.Skip"/>, plus
/// latest-generation files that <c>ResolveWithinWorkspace</c> accepts.
/// </summary>
/// <remarks>
/// Pattern: Query-time join (DM7; ADR-0038). No <c>folder_dim</c>. Named omit is a constructor
/// argument so production IPC cannot hide folders behind <c>Omitted (N)</c>.
/// </remarks>
public sealed class SolutionTreeProjection
{
    /// <summary>
    /// Production folder count default. Inferred — no measured census cardinality yet; retune when
    /// the query emits counts.
    /// </summary>
    public const int DefaultMaxCensusFolders = 2_000;

    /// <summary>Aligned with <see cref="GraphProjection.DefaultMaxNodes"/>.</summary>
    public const int DefaultMaxFileArtifacts = 5_000;

    internal const string NotRecordedCopy = "Not recorded";

    internal const string PythonTsCopy =
        "Python and TypeScript files are not listed individually. The scope folder is indexed.";

    private readonly HashSet<string>? _omitRelativePaths;
    private readonly Func<string, IEnumerable<string>>? _censusChildren;

    /// <summary>
    /// Test-host omit set and census enumerator. Production passes null for both.
    /// </summary>
    /// <remarks>
    /// simplify: one Func beats a public IWorkspaceDirectoryCensus. Upgrade if a second production
    /// walker needs the same hook.
    /// </remarks>
    internal SolutionTreeProjection(
        IEnumerable<string>? omitRelativePaths,
        Func<string, IEnumerable<string>>? censusChildren = null)
    {
        if (omitRelativePaths is not null)
        {
            _omitRelativePaths = new HashSet<string>(PathComparer);
            foreach (var path in omitRelativePaths)
            {
                _omitRelativePaths.Add(NormalizeRelative(path));
            }
        }

        _censusChildren = censusChildren;
    }

    internal static StringComparer PathComparer => OperatingSystem.IsWindows()
        ? StringComparer.OrdinalIgnoreCase
        : StringComparer.Ordinal;

    internal static string NormalizeRelative(string path)
    {
        if (string.IsNullOrEmpty(path) || path == ".") return "";
        var s = path.Replace('\\', '/').TrimEnd('/');
        return s == "." ? "" : s;
    }

    internal static string? ParentOf(string relative)
    {
        if (string.IsNullOrEmpty(relative)) return null;
        var slash = relative.LastIndexOf('/');
        return slash < 0 ? "" : relative[..slash];
    }

    internal static int DepthOf(string relative)
    {
        if (string.IsNullOrEmpty(relative)) return 0;
        var depth = 1;
        foreach (var c in relative)
        {
            if (c == '/') depth++;
        }

        return depth;
    }

    internal static bool PathsEqual(string left, string right) =>
        string.Equals(NormalizeRelative(left), NormalizeRelative(right), PathComparison.ForThisFileSystem);

    internal static bool IsPythonOrTypeScriptScope(string scopeId) =>
        scopeId.StartsWith("python:", StringComparison.Ordinal)
        || scopeId.StartsWith("typescript:", StringComparison.Ordinal);

    internal static string OmittedCopy(int count) => $"Omitted ({count})";

    internal readonly record struct JoinedFile(
        string RelativePath,
        string NodeId,
        string? NodeKind);

    internal readonly record struct ScopeDeclaredAt(
        string ScopeId,
        string DeclaredAt);

    /// <summary>
    /// Census + coverage + named omit + count caps. Frame shrink is applied by the host that
    /// knows <see cref="ProjectionService.MaxFramedGraphBytes"/>.
    /// </summary>
    internal SolutionTreeResult Compute(
        string? workspaceRoot,
        SolutionTreeQuery query,
        IReadOnlyList<JoinedFile> files,
        IReadOnlyList<ScopeDeclaredAt> scopes,
        IReadOnlyList<SolutionTreeDisclosure> joinDisclosures,
        string sourceRevision,
        CancellationToken cancellationToken)
    {
        ArgumentNullException.ThrowIfNull(query);
        files ??= [];
        scopes ??= [];
        joinDisclosures ??= [];

        var disclosures = new List<SolutionTreeDisclosure>(joinDisclosures);
        var skipOmitted = 0;
        var folders = new Dictionary<string, CensusFolderCoverage>(PathComparer);

        if (!string.IsNullOrWhiteSpace(workspaceRoot) && Directory.Exists(workspaceRoot))
        {
            var root = Path.GetFullPath(workspaceRoot);
            skipOmitted = WalkCensus(root, folders, disclosures, cancellationToken);
        }

        ApplyCoverage(folders, files, scopes);
        var pythonTsIndexed = PythonTsFolderIsIndexed(scopes, folders);

        var omittedByCap = 0;
        if (_omitRelativePaths is { Count: > 0 })
        {
            omittedByCap += DropNamed(folders);
        }

        var maxFolders = Math.Clamp(query.MaxCensusFolders, 1, DefaultMaxCensusFolders);
        var maxFiles = Math.Clamp(query.MaxFileArtifacts, 0, DefaultMaxFileArtifacts);

        var rankedFolders = RankFolders(folders);
        if (rankedFolders.Count > maxFolders)
        {
            omittedByCap += rankedFolders.Count - maxFolders;
            rankedFolders = rankedFolders.Take(maxFolders).ToList();
        }

        var keptFolderSet = rankedFolders.Select(f => f.Path).ToHashSet(PathComparer);

        var collapsedFiles = CollapseFiles(files);
        if (collapsedFiles.Count > maxFiles)
        {
            omittedByCap += collapsedFiles.Count - maxFiles;
            collapsedFiles = collapsedFiles.Take(maxFiles).ToList();
        }

        collapsedFiles = DropOrphanFiles(collapsedFiles, keptFolderSet);

        if (pythonTsIndexed)
        {
            disclosures.Add(new SolutionTreeDisclosure(
                SolutionTreeShortfallCause.PythonTsPerFile, PythonTsCopy, null, null));
        }

        var nodes = new List<SolutionTreeNode>(rankedFolders.Count + collapsedFiles.Count);
        nodes.AddRange(rankedFolders);
        foreach (var file in collapsedFiles)
        {
            nodes.Add(new SolutionTreeNode(
                file.RelativePath, SolutionTreeNodeKind.FileArtifact, null, file.NodeId, file.NodeKind));
        }

        return new SolutionTreeResult(
            nodes,
            skipOmitted,
            omittedByCap,
            FinalizeDisclosures(disclosures, omittedByCap),
            sourceRevision);
    }

    internal IReadOnlyList<SolutionTreeNode> ShrinkRankedPrefix(
        IReadOnlyList<SolutionTreeNode> nodes,
        int alreadyOmitted,
        Func<IReadOnlyList<SolutionTreeNode>, int, IReadOnlyList<SolutionTreeDisclosure>, SolutionTreeResult> pack,
        Func<SolutionTreeResult, int> framedCost,
        int budget)
    {
        // simplify: ranked prefix shrink. Ceiling: this stays correct while ranking is total.
        // Upgrade trigger: if ranking becomes non-total, switch to Graph's proportional+recovery loop.
        var ranked = RankAll(nodes);
        if (ranked.Count == 0) return ranked;

        var disclosures = Array.Empty<SolutionTreeDisclosure>();
        if (framedCost(pack(ranked, alreadyOmitted, disclosures)) <= budget)
        {
            return ranked;
        }

        var lo = 1;
        var hi = ranked.Count;
        var best = DropOrphanNodes(ranked.Take(1).ToList());

        while (lo < hi)
        {
            var mid = (lo + hi + 1) / 2;
            var candidate = DropOrphanNodes(ranked.Take(mid).ToList());
            var omitted = alreadyOmitted + (nodes.Count - candidate.Count);
            if (framedCost(pack(candidate, omitted, disclosures)) <= budget)
            {
                best = candidate;
                lo = mid;
            }
            else
            {
                hi = mid - 1;
            }
        }

        return best;
    }

    private int WalkCensus(
        string root,
        Dictionary<string, CensusFolderCoverage> folders,
        List<SolutionTreeDisclosure> disclosures,
        CancellationToken cancellationToken)
    {
        var skipOmitted = 0;
        var stack = new Stack<(string Absolute, string Relative)>();
        stack.Push((root, ""));

        while (stack.Count > 0)
        {
            cancellationToken.ThrowIfCancellationRequested();
            var (absolute, relative) = stack.Pop();

            IReadOnlyList<string> children;
            try
            {
                children = ChildrenOf(absolute).ToList();
            }
            catch (IOException)
            {
                disclosures.Add(Disclosure(SolutionTreeShortfallCause.Io, NotRecordedCopy, relative));
                continue;
            }
            catch (UnauthorizedAccessException)
            {
                disclosures.Add(Disclosure(SolutionTreeShortfallCause.Permission, NotRecordedCopy, relative));
                continue;
            }

            folders[relative] = CensusFolderCoverage.Unindexed;

            foreach (var childAbsolute in children)
            {
                var name = Path.GetFileName(childAbsolute);
                if (UnanalysedLanguages.Skip.Contains(name))
                {
                    skipOmitted++;
                    continue;
                }

                var childRelative = string.IsNullOrEmpty(relative) ? name.Replace('\\', '/') : relative + "/" + name.Replace('\\', '/');

                bool reparse;
                try
                {
                    // Pattern: Reparse refusal (EnvelopePurge class)
                    reparse = new DirectoryInfo(childAbsolute).Attributes.HasFlag(FileAttributes.ReparsePoint);
                }
                catch (IOException)
                {
                    disclosures.Add(Disclosure(SolutionTreeShortfallCause.Io, NotRecordedCopy, childRelative));
                    continue;
                }
                catch (UnauthorizedAccessException)
                {
                    disclosures.Add(Disclosure(SolutionTreeShortfallCause.Permission, NotRecordedCopy, childRelative));
                    continue;
                }

                if (reparse)
                {
                    disclosures.Add(Disclosure(SolutionTreeShortfallCause.ReparsePoint, NotRecordedCopy, childRelative));
                    continue;
                }

                stack.Push((childAbsolute, NormalizeRelative(childRelative)));
            }
        }

        return skipOmitted;
    }

    private IEnumerable<string> ChildrenOf(string absoluteDirectory) =>
        _censusChildren is null
            ? Directory.EnumerateDirectories(absoluteDirectory)
            : _censusChildren(absoluteDirectory);

    private int DropNamed(Dictionary<string, CensusFolderCoverage> folders)
    {
        var dropped = 0;
        foreach (var path in _omitRelativePaths!)
        {
            if (string.IsNullOrEmpty(path)) continue;
            if (folders.Remove(path)) dropped++;
        }

        return dropped;
    }

    private static void ApplyCoverage(
        Dictionary<string, CensusFolderCoverage> folders,
        IReadOnlyList<JoinedFile> files,
        IReadOnlyList<ScopeDeclaredAt> scopes)
    {
        foreach (var file in files)
        {
            MarkAncestorsIndexed(folders, ParentOf(file.RelativePath));
        }

        foreach (var scope in scopes)
        {
            var declared = NormalizeRelative(scope.DeclaredAt);
            if (!folders.ContainsKey(declared)) continue;
            folders[declared] = CensusFolderCoverage.IndexedParent;
            MarkAncestorsIndexed(folders, ParentOf(declared));
        }

        foreach (var path in folders.Keys.OrderByDescending(DepthOf))
        {
            if (folders[path] != CensusFolderCoverage.IndexedParent) continue;
            MarkAncestorsIndexed(folders, ParentOf(path));
        }
    }

    private static void MarkAncestorsIndexed(Dictionary<string, CensusFolderCoverage> folders, string? start)
    {
        var current = start;
        while (current is not null)
        {
            if (folders.ContainsKey(current))
            {
                folders[current] = CensusFolderCoverage.IndexedParent;
            }

            current = ParentOf(current);
        }
    }

    private static List<SolutionTreeNode> RankFolders(Dictionary<string, CensusFolderCoverage> folders) =>
        folders
            .Select(kv => new SolutionTreeNode(kv.Key, SolutionTreeNodeKind.CensusFolder, kv.Value, null, null))
            .OrderByDescending(n => string.IsNullOrEmpty(n.Path))
            .ThenByDescending(n => n.Coverage == CensusFolderCoverage.IndexedParent)
            .ThenBy(n => DepthOf(n.Path))
            .ThenBy(n => n.Path, PathComparer)
            .ToList();

    private static List<JoinedFile> CollapseFiles(IReadOnlyList<JoinedFile> files)
    {
        var byPath = new Dictionary<string, JoinedFile>(PathComparer);
        foreach (var file in files)
        {
            var path = NormalizeRelative(file.RelativePath);
            if (byPath.TryGetValue(path, out var existing))
            {
                if (string.CompareOrdinal(file.NodeId, existing.NodeId) < 0)
                {
                    byPath[path] = file with { RelativePath = path };
                }
            }
            else
            {
                byPath[path] = file with { RelativePath = path };
            }
        }

        return byPath.Values
            .OrderBy(f => DepthOf(f.RelativePath))
            .ThenBy(f => f.RelativePath, PathComparer)
            .ToList();
    }

    private static List<JoinedFile> DropOrphanFiles(
        List<JoinedFile> files, HashSet<string> keptFolders)
    {
        var kept = new List<JoinedFile>(files.Count);
        foreach (var file in files)
        {
            var parent = ParentOf(file.RelativePath);
            if (parent is not null && keptFolders.Contains(parent))
            {
                kept.Add(file);
            }
        }

        return kept;
    }

    internal static List<SolutionTreeNode> DropOrphanNodes(List<SolutionTreeNode> nodes)
    {
        var folders = nodes
            .Where(n => n.Kind == SolutionTreeNodeKind.CensusFolder)
            .Select(n => n.Path)
            .ToHashSet(PathComparer);

        return nodes
            .Where(n => n.Kind != SolutionTreeNodeKind.FileArtifact
                || (ParentOf(n.Path) is { } parent && folders.Contains(parent)))
            .ToList();
    }

    private static List<SolutionTreeNode> RankAll(IReadOnlyList<SolutionTreeNode> nodes) =>
        nodes
            .OrderByDescending(n => n.Kind == SolutionTreeNodeKind.CensusFolder && string.IsNullOrEmpty(n.Path))
            .ThenByDescending(n => n.Kind == SolutionTreeNodeKind.CensusFolder)
            .ThenByDescending(n => n.Coverage == CensusFolderCoverage.IndexedParent)
            .ThenBy(n => DepthOf(n.Path))
            .ThenBy(n => n.Path, PathComparer)
            .ThenBy(n => n.Kind)
            .ToList();

    private static bool PythonTsFolderIsIndexed(
        IReadOnlyList<ScopeDeclaredAt> scopes,
        Dictionary<string, CensusFolderCoverage> folders)
    {
        foreach (var scope in scopes)
        {
            if (!IsPythonOrTypeScriptScope(scope.ScopeId)) continue;
            if (folders.ContainsKey(NormalizeRelative(scope.DeclaredAt))) return true;
        }

        return false;
    }

    internal static IReadOnlyList<SolutionTreeDisclosure> FinalizeDisclosures(
        List<SolutionTreeDisclosure> disclosures, int omittedByCap)
    {
        disclosures.RemoveAll(d => d.Cause == SolutionTreeShortfallCause.Cap);
        if (omittedByCap > 0)
        {
            disclosures.Add(new SolutionTreeDisclosure(
                SolutionTreeShortfallCause.Cap, OmittedCopy(omittedByCap), omittedByCap, null));
        }

        return disclosures;
    }

    internal static SolutionTreeDisclosure Disclosure(
        SolutionTreeShortfallCause cause, string message, string? path) =>
        new(cause, message, null, path is null ? null : NormalizeRelative(path));
}
