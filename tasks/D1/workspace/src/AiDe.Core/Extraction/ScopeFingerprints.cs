using System.Globalization;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;

namespace AiDe.Core.Extraction;

/// <summary>
/// What a scope's inputs looked like the last time it was extracted successfully.
/// </summary>
/// <remarks>
/// <para><b>Every index re-extracted every scope.</b> On a real repository that is 4.5 seconds and
/// seven scopes, and it grows with the codebase — paid in full whether one file changed or none.
/// A fingerprint that has not moved means the evidence in the store is already the answer.</para>
///
/// <para><b>A skip is reported, never disguised as work.</b> <c>IndexResult</c> counts reused scopes
/// separately from indexed ones, because "7 of 7 indexed" would be a true sentence about a run that
/// read nothing, and the operator's next question after a surprising graph is always "did it
/// actually look?".</para>
///
/// <para><b>It fails towards re-extraction.</b> An unreadable directory, a missing sidecar, a
/// changed extractor version — every uncertainty produces a fingerprint that does not match, and the
/// scope is read again. The cost of an unnecessary extraction is seconds; the cost of a skipped one
/// is a graph that quietly describes code that no longer exists.</para>
/// </remarks>
public sealed class ScopeFingerprints
{
    /// <summary>
    /// Bumped whenever extraction output could change for unchanged input.
    /// </summary>
    /// <remarks>
    /// Part of every fingerprint, so upgrading the product invalidates the whole sidecar. Without it
    /// an extractor improvement would reach only the files a user happened to touch afterwards —
    /// and the graph would be a mix of two extractor generations with nothing saying so.
    /// </remarks>
    // 2026-08-30.1 — the knowledge extractor, node_class classification, comment stripping in four
    // readers, the SQL fold and uses_table. Every one of those changes extraction OUTPUT for input
    // that did not change, so a store built before them is a mix of two generations. The user saw
    // exactly that: Knowledge read 0 on a repository holding 2,343 knowledge nodes, because the
    // scopes were cached from a build that had no knowledge reader.
    // 2026-08-30.2 — SourceRevision. The .1 bump was correct and reached nothing: a second reuse
    // check inside RefreshScopeAsync matched on the unchanged artifact revision and returned an empty
    // result, so 66 scopes were visited and none re-read (DC-044). This bump is the first one that
    // can actually take effect.
    // 2026-08-31.1 — `declared_at`. Every scope now records WHERE its files are, relative to the
    // workspace root, because nothing did: an assertion's provenance path is relative to its scope
    // and no fact said where the scope was, so a node could not be resolved to a file at all. A store
    // written before this cannot answer a content query, and the reader would show "source could not
    // be located" for everything — which is the shape a stale generation always takes.
    // 2026-09-01.5 — Python classes carry their methods as members, and the nested-declaration
    // disclosure is conditional and counted instead of firing on every scope.
    // 2026-09-01.6 — TypeScript classes and interfaces carry their members, and its
    // nested-declaration and dynamic-import disclosures are conditional and counted. Bicep resource
    // names are folded against declared defaults; this half is a CORRECTNESS bump, not a coverage
    // one — 10 of 27 resource names in every existing store are the text of an identifier
    // (`workspaceName`) rather than a name (`theterrace-s00-log`), and no store fixes itself until
    // this changes.
    // 2026-09-01.7 — NO extraction change. A doc comment in `KnowledgeBody` was corrected (it
    // argued against extracting headings partly because attribute text was unfindable, which
    // stopped being true when `StoreReader.SearchNodes` began matching attribute values), and the
    // generation gate cannot tell a comment from a behaviour change without parsing C#. Paying one
    // re-index is the cheap side of that trade: the gate exists because a stale generation once made
    // a repository of 2,343 knowledge nodes read as 0, and a gate taught to ignore "harmless"
    // changes is a gate that will one day ignore the wrong one.
    // 2026-09-01.8 — every C# call SITE is recorded as `calls_at`, in call order, with the called
    // member's name. `calls` keeps its deduplicated one-row-per-pair shape for the graph; this is
    // the interaction a sequence diagram draws, where a repeated call is a repeated message rather
    // than a duplicate to be folded away. An attribute, so it is never drawn.
    // 2026-09-05.1 — COMMENT ONLY, and bumped anyway. The ADR citation in `CSharpExtractor` was
    // disambiguated (`ADR-0020` meant two different decisions; it is now `ADR-0026
    // class-diagram-architecture`). Extraction output is unchanged, and that is precisely the
    // judgement this gate refuses to let anyone make: it cannot tell a comment from a behaviour
    // change without parsing C#, and a gate taught to trust "it is only a comment" is a gate that
    // will one day be wrong about it silently. One re-index is the cheap side of that trade.
    // 2026-09-06.1 — REAL OUTPUT CHANGE, unlike the comment-only bump above. Reference packs were
    // located through `ProgramFiles`, which is the EMPTY STRING on Unix, so the probe became the
    // relative path `dotnet/packs/…` and never matched. With no pack the compilation carries no
    // framework references, so `[Table]` is not recognised (no `declares_table`) and `Console` and
    // `List<T>` stop being classified as runtime types — extraction still succeeds and quietly
    // returns fewer facts. The root is now taken from the runtime the process is already running on,
    // with DOTNET_ROOT and the usual install locations behind it (INV-0005).
    // 2026-09-10.1 — REAL OUTPUT CHANGE on POSIX. Two extractors carried a separator-terminated
    // containment check that folded case unconditionally, so on Linux and macOS a knowledge link
    // spelled `../DOCS/x.md` inside a root of `docs` resolved to a DIFFERENT directory's document
    // and the edge was emitted anyway. Both now use `PathComparison.ForThisFileSystem`, so those
    // links stop resolving where the filesystem says they were never the same file — fewer, and
    // truer, knowledge edges. Windows output is unchanged, and the bump is taken on both anyway:
    // this gate cannot tell one platform's behaviour change from the other's, and neither can a
    // workspace that was indexed on one and opened on the other.
    // 2026-09-14.1 — A CONSTANT ONLY, and bumped anyway. `SourceRevision` names the retired fixture
    // literal (`RetiredFixtureLiteral`, Ruling 98) so the reuse guard can refuse a snapshot stamped
    // with it; no extractor's output changes. The bump is the gate's trade, taken as the 2026-09-05.1
    // note explains — and it is not wasted: one re-index on every workspace is exactly the migration
    // a pre-Ruling-85 store needs to leave `rev-1` behind, so the guard and the generation agree.
    // 2026-09-15.1 — `UnanalysedLanguages.Skip` visibility `private` → `internal` so UV-0 census
    // consumes the same instance (ADR-0038). Members unchanged; the gate keys off the file.
    // 2026-09-17.1 — REAL OUTPUT CHANGE, and the one that most needs this gate. The TypeScript and
    // Python readers passed `request.ScopeId` into `Provenance.ArtifactPathId`, so every assertion
    // they have ever written cites a value that names no file (INV-0014 §2, DC-229). One consumer
    // told the operator — "the source for this node could not be located (`typescript:src/frontend`)"
    // — and the other, content search, counted it as a skip and returned "no matches" over every
    // TypeScript and Python file in every workspace, for an unknown span of time. Both readers now
    // cite the file. NO STORE FIXES ITSELF UNTIL THIS MOVES: `Provenance` is outside `AssertionId`,
    // so the corrected fact hashes to the same id as the wrong one and a re-commit would collide on
    // `ux_assertion_natural` rather than overwrite. The generation is what changes the id, through
    // `SourceRevision`'s suffix into `artifact_revision`, which IS in the hash — so this bump is the
    // whole of the repair's store half, and `extractor_version` could not have been (it is in
    // neither key, and putting it there would be a schema change).
    public const string ExtractorGeneration = "2026-09-17.1";

    private const string FileName = "scope-fingerprints.json";

    private static readonly HashSet<string> Skip = new(StringComparer.OrdinalIgnoreCase)
    {
        "bin", "obj", ".git", ".vs", "node_modules", "artifacts", "packages", "TestResults",
    };

    private readonly string _path;
    private readonly Dictionary<string, string> _byScope;

    private ScopeFingerprints(string path, Dictionary<string, string> byScope)
    {
        _path = path;
        _byScope = byScope;
    }

    public static ScopeFingerprints Load(string dataDirectory)
    {
        var path = Path.Combine(dataDirectory, FileName);

        try
        {
            if (File.Exists(path))
            {
                var stored = JsonSerializer.Deserialize<Dictionary<string, string>>(File.ReadAllText(path));
                if (stored is not null)
                {
                    return new ScopeFingerprints(path, new Dictionary<string, string>(stored, StringComparer.Ordinal));
                }
            }
        }
        catch (Exception ex) when (ex is JsonException or IOException or UnauthorizedAccessException)
        {
            // An unreadable sidecar means every scope is re-extracted. That is the slow answer, and
            // it is the only safe one: a corrupt cache that is trusted is worse than no cache.
        }

        return new ScopeFingerprints(path, new Dictionary<string, string>(StringComparer.Ordinal));
    }

    /// <summary>True when this scope's inputs are byte-for-byte what they were when it last ran.</summary>
    public bool IsUnchanged(string scopeId, string fingerprint) =>
        fingerprint.Length > 0
        && _byScope.TryGetValue(scopeId, out var previous)
        && string.Equals(previous, fingerprint, StringComparison.Ordinal);

    public void Record(string scopeId, string fingerprint)
    {
        if (fingerprint.Length == 0)
        {
            // A fingerprint that could not be computed is not recorded. Recording an empty one would
            // make the next run believe an unreadable scope was up to date.
            _byScope.Remove(scopeId);
            return;
        }

        _byScope[scopeId] = fingerprint;
    }

    /// <summary>Forgets a scope, so the next run reads it whatever the filesystem says.</summary>
    public void Invalidate(string scopeId) => _byScope.Remove(scopeId);

    /// <summary>
    /// Forgets every scope this run did not see, and reports whether the SET of scopes changed.
    /// </summary>
    /// <remarks>
    /// <para><b>A project appearing is not a change to any existing scope.</b> Every per-scope
    /// fingerprint can be identical while the workspace has gained a project, lost one, or had one
    /// renamed — and a cache keyed only per scope would report "all reused" for a workspace whose
    /// shape had changed underneath it.</para>
    ///
    /// <para>Discovery runs on every index regardless, so a NEW scope is always extracted — it has
    /// no fingerprint to match. The case this closes is the opposite one: a scope that has gone.
    /// Its evidence would otherwise sit in the store forever, describing code that no longer exists,
    /// with nothing to remove it and nothing to say so.</para>
    /// </remarks>
    public bool Reconcile(IEnumerable<string> discoveredScopeIds)
    {
        var present = new HashSet<string>(discoveredScopeIds, StringComparer.Ordinal);
        var departed = _byScope.Keys.Where(id => !present.Contains(id)).ToList();

        foreach (var id in departed) _byScope.Remove(id);

        var arrived = present.Count(id => !_byScope.ContainsKey(id));
        return departed.Count > 0 || arrived > 0;
    }

    /// <summary>Scope ids this sidecar still remembers. For reporting what a run left behind.</summary>
    public IReadOnlyCollection<string> Known => _byScope.Keys;

    public void Save()
    {
        try
        {
            var directory = Path.GetDirectoryName(_path);
            if (!string.IsNullOrEmpty(directory)) Directory.CreateDirectory(directory);

            File.WriteAllText(_path, JsonSerializer.Serialize(
                _byScope, new JsonSerializerOptions { WriteIndented = true }));
        }
        catch (Exception ex) when (ex is IOException or UnauthorizedAccessException)
        {
            // A cache that cannot be written is a slow next run, never a failed this one.
        }
    }

    /// <summary>
    /// A stable digest of a scope's input files: relative path, size and modification time.
    /// </summary>
    /// <remarks>
    /// <para>Not content hashes. Reading every byte of every file to decide whether to read every
    /// byte of every file is a cache that costs what it saves. Path, length and mtime miss only an
    /// edit that preserves both size and timestamp, which a tool does not do by accident.</para>
    ///
    /// <para>Returns empty when the scope's inputs cannot be enumerated, and an empty fingerprint
    /// never matches — so an unreadable scope is always re-read.</para>
    /// </remarks>
    public static string Compute(string rootPath, ScopeDescriptor scope)
    {
        // What the scope actually READS, which is not the same for every kind.
        //
        // A C# scope is a project directory: its extraction depends on every source file under it.
        // A Bicep scope is ONE TEMPLATE, and a schema scope is one Migrations directory. Treating a
        // single-file scope as its containing folder made two templates in one `infra/` directory
        // share a fingerprint basis, so deleting either invalidated both — over-invalidation, which
        // is safe but wrong, and it made "one scope departed" look like "everything changed".
        var single = scope.ScopeId.StartsWith("bicep:", StringComparison.Ordinal)
            && File.Exists(scope.ProjectPath);

        var target = single
            ? scope.ProjectPath
            : File.Exists(scope.ProjectPath)
                ? Path.GetDirectoryName(scope.ProjectPath) ?? rootPath
                : Directory.Exists(scope.ProjectPath) ? scope.ProjectPath : rootPath;

        var entries = new List<string>();

        try
        {
            foreach (var file in single ? [target] : Enumerate(target))
            {
                var info = new FileInfo(file);
                var name = single ? Path.GetFileName(file) : Path.GetRelativePath(target, file);
                entries.Add(string.Create(CultureInfo.InvariantCulture,
                    $"{name}|{info.Length}|{info.LastWriteTimeUtc.Ticks}"));
            }
        }
        catch (Exception ex) when (ex is IOException or UnauthorizedAccessException)
        {
            return string.Empty;
        }

        if (entries.Count == 0) return string.Empty;

        entries.Sort(StringComparer.Ordinal);

        var payload = Encoding.UTF8.GetBytes(
            ExtractorGeneration + "\n" + scope.TargetFramework + "\n" + string.Join("\n", entries));

        return Convert.ToHexStringLower(SHA256.HashData(payload));
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
