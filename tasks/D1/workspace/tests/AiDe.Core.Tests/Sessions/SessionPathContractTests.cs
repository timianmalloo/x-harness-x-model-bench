using AiDe.Core.Sessions;

namespace AiDe.Core.Tests.Sessions;

/// <summary>
/// F0 clause 1 and clause 2 (docs/plans/conductor-front-door.md): <c>session.json</c>, not
/// <c>.yaml</c> (Ruling 23), and the run-log path is reserved for Phase 3's <c>RunLogStore</c> and
/// must be provably unused by this slice.
/// </summary>
public sealed class SessionPathContractTests
{
    private const string WorkspaceRoot = @"C:\workspace";
    private const string TestSessionId = "20260910T120000Z-deadbeef";

    [Fact]
    public void SessionFile_IsJsonNotYaml()
    {
        var path = SessionPaths.SessionFile(WorkspaceRoot, TestSessionId);

        Assert.EndsWith(".json", path, StringComparison.Ordinal);
        Assert.DoesNotContain(".yaml", path, StringComparison.Ordinal);
        Assert.DoesNotContain(".yml", path, StringComparison.Ordinal);
    }

    [Fact]
    public void SessionFile_IsAtTheExactContractPath()
    {
        var path = SessionPaths.SessionFile(WorkspaceRoot, TestSessionId);
        var expected = Path.Combine(
            WorkspaceRoot, ".aide", "sessions", TestSessionId, "session.json");

        Assert.Equal(expected, path);
    }

    [Fact]
    public void RunLogFile_IsAtTheReservedContractPath()
    {
        var path = SessionPaths.RunLogFile(WorkspaceRoot, TestSessionId, "run-1");
        var expected = Path.Combine(
            WorkspaceRoot, ".aide", "sessions", TestSessionId, "runs", "run-1.jsonl");

        Assert.Equal(expected, path);
    }

    /// <summary>
    /// Fails if: anything outside <see cref="AllowlistedRunLogReservationFiles"/> uses the run-log
    /// reservation. <b>Scan:</b> root <c>src/</c>, <b>recursive</b>, <c>*.cs</c>. <b>Tokens:</b>
    /// <c>RunLogFile</c> | <c>RunsDirectory</c> | <c>RunsDirectoryName</c>. <b>Allowlist:</b>
    /// <see cref="AllowlistedRunLogReservationFiles"/> — currently <c>SessionPaths.cs</c> only,
    /// where all three are declared (skipped whole-file, not line-by-line: <c>RunLogFile</c>'s own
    /// body calls <c>RunsDirectory</c> on a separate line, so a per-line declaration skip cannot
    /// tell that composition apart from a real external call). <c>tests/</c> is deliberately
    /// <b>not scanned</b> — tests legitimately reference these
    /// (<c>SessionConfigStoreTests.cs:145-146</c>), and scanning them would fail on correct code.
    /// </summary>
    /// <remarks>
    /// <para><b>Widened by Ruling 38 (DC-118, second instance of the same class).</b> The F0-era
    /// form of this guard scanned only <c>src/AiDe.Core/Sessions</c>, top-directory-only, for the
    /// single token <c>RunLogFile</c> — narrower than its own doc comment ("anything writes a run
    /// log <i>anywhere</i>") in two dimensions at once: the directory scope, and the token set. A
    /// writer reaching the reserved subtree through <c>SessionPaths.RunsDirectory(...)</c> or
    /// <c>RunsDirectoryName</c> — from anywhere under <c>src/</c>, including <c>AiDe.App/</c>,
    /// where the next node (F2) builds the session document, the paired-zone preset and the
    /// Console merged stream — passed the old guard cleanly. <c>RunLogStore</c> is Phase 3, so
    /// that gap made the reservation theatre: if F2 squatted the path, Phase 3 would inherit it and
    /// nothing today would go red.</para>
    /// <para><b>Extension point, not a wall.</b> <see cref="AllowlistedRunLogReservationFiles"/> is
    /// a named constant precisely so this guard can be extended instead of deleted: Phase 3 adds
    /// <c>RunLogStore.cs</c> to it, citing its ruling, when it legitimately starts writing run
    /// logs. A guard that must be deleted to make progress is one people delete.</para>
    /// <para><b>Declared residual.</b> A hard-coded <c>"runs"</c> string literal defeats every
    /// token this scan looks for — that is not chased statically here. It is covered dynamically,
    /// per App surface, by the obligation Ruling 38 assigns to F2: exercise the surface, then
    /// assert <c>SessionPaths.RunsDirectory(...)</c> does not exist, the App-layer twin of
    /// <c>SessionConfigStoreTests.Lifecycle_NeverWritesUnderTheReservedRunsDirectory</c>. That is a
    /// control F2 writes, not a caution in this one's prose.</para>
    /// </remarks>
    [Fact]
    public void RunLogReservation_IsUnusedOutsideSessionPaths_NothingInSrcWritesThere()
    {
        var srcDirectory = Path.Combine(RepoRoot(), "src");
        Assert.True(Directory.Exists(srcDirectory), $"expected {srcDirectory} to exist");

        var tokens = new[] { "RunLogFile", "RunsDirectory", "RunsDirectoryName" };
        var callers = new List<string>();

        foreach (var file in Directory.EnumerateFiles(srcDirectory, "*.cs", SearchOption.AllDirectories))
        {
            var fileName = Path.GetFileName(file);
            if (AllowlistedRunLogReservationFiles.Contains(fileName))
            {
                // The reservation's own declarations (and their internal composition — RunLogFile
                // calls RunsDirectory on a line of its own) live only here. Extend the allowlist
                // for a legitimate new writer; never delete the guard.
                continue;
            }

            foreach (var line in File.ReadAllLines(file))
            {
                var trimmed = line.TrimStart();

                // Skip a re-declaration of one of the three names (none exists outside the
                // allowlist today) and prose in a comment about the reservation — neither is a use.
                if (trimmed.StartsWith("public static string RunLogFile", StringComparison.Ordinal)
                    || trimmed.StartsWith("public static string RunsDirectory", StringComparison.Ordinal)
                    || trimmed.StartsWith("public const string RunsDirectoryName", StringComparison.Ordinal)
                    || trimmed.StartsWith("///", StringComparison.Ordinal)
                    || trimmed.StartsWith("//", StringComparison.Ordinal))
                {
                    continue;
                }

                foreach (var token in tokens)
                {
                    if (line.Contains(token, StringComparison.Ordinal))
                    {
                        callers.Add($"{fileName}: {line.Trim()}");
                        break;
                    }
                }
            }
        }

        Assert.True(
            callers.Count == 0,
            "the run-log reservation (RunLogFile / RunsDirectory / RunsDirectoryName) is reserved "
                + "for Phase 3's RunLogStore and must be unused outside SessionPaths.cs; found a use site: "
                + string.Join(" | ", callers));
    }

    /// <summary>
    /// Files allowed to use the run-log reservation tokens — today, only their declaration site.
    /// A named constant, not a literal in the scan loop, because Ruling 38 makes this an extension
    /// point: Phase 3 adds <c>RunLogStore.cs</c> here, citing its ruling, rather than the guard
    /// being weakened or deleted to let it through.
    /// </summary>
    private static readonly IReadOnlySet<string> AllowlistedRunLogReservationFiles =
        new HashSet<string>(StringComparer.Ordinal) { "SessionPaths.cs" };

    /// <summary>
    /// Fails if: the session-config path takes a YAML dependency. Ruling 23's subject is session
    /// config, not the project as a whole — Ruling 35 explicitly carves YamlDotNet out, scoped to
    /// the template loader (<c>TemplateFrontmatterReader.cs</c>; scoping proven by
    /// <c>TemplateFrontmatterParserTests.TheDependencyIsScopedToTheTemplateLoader</c>), so a
    /// repo-wide <c>AiDe.Core.csproj</c> scan is falsified by that loader's own explanatory comment
    /// on the dependency, not by an actual violation of Ruling 23. Ruling 36 narrows this guard to
    /// what Ruling 23 actually governs: <see cref="SessionConfig"/> and
    /// <see cref="SessionConfigStore"/> take no YAML dependency, full stop. Same shape as
    /// <see cref="RunLogReservation_IsUnusedOutsideSessionPaths_NothingInSrcWritesThere"/>: a
    /// source scan collecting hits rather than a substring check on one file.
    /// </summary>
    [Fact]
    public void SessionConfigSource_ContainsNoYamlToken()
    {
        var sessionsDirectory = Path.Combine(RepoRoot(), "src", "AiDe.Core", "Sessions");
        var sessionConfigFiles = new[] { "SessionConfig.cs", "SessionConfigStore.cs" };

        var hits = new List<string>();

        foreach (var fileName in sessionConfigFiles)
        {
            var path = Path.Combine(sessionsDirectory, fileName);
            Assert.True(File.Exists(path), $"expected {path} to exist");

            foreach (var line in File.ReadAllLines(path))
            {
                if (line.Contains("Yaml", StringComparison.OrdinalIgnoreCase))
                {
                    hits.Add($"{fileName}: {line.Trim()}");
                }
            }
        }

        Assert.True(
            hits.Count == 0,
            "session config must take no YAML dependency (Ruling 23); found: " + string.Join(" | ", hits));
    }

    private static string RepoRoot()
    {
        var directory = new DirectoryInfo(AppContext.BaseDirectory);

        while (directory is not null && !File.Exists(Path.Combine(directory.FullName, "AiDe.sln")))
        {
            directory = directory.Parent;
        }

        return directory?.FullName
            ?? throw new InvalidOperationException("could not locate the repository root from the test output directory");
    }
}
