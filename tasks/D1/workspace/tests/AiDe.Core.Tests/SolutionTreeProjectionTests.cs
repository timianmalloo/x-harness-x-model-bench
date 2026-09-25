using System.Diagnostics;
using System.Text;
using System.Text.Json;
using AiDe.Core;
using AiDe.Core.Extraction;
using AiDe.Core.Facts;
using AiDe.Core.Ipc;
using AiDe.Core.Projections;
using AiDe.Core.Store;
using AiDe.Testing;

namespace AiDe.Core.Tests;

/// <summary>
/// UV-0 Core census join against composed fixture F* (US-T1–T7, T5a–c DTO).
/// </summary>
public sealed class SolutionTreeProjectionTests
{
    private static readonly DateTimeOffset Observed = DateTimeOffset.UnixEpoch;

    [Fact]
    public void Catalog_NamesSolutionTreeAndDoesNotMapOntoOverviewOrGraph()
    {
        Assert.Equal("solution-tree", WorkspaceOperations.SolutionTree);
        Assert.NotEqual(WorkspaceOperations.Overview, WorkspaceOperations.SolutionTree);
        Assert.NotEqual(WorkspaceOperations.Graph, WorkspaceOperations.SolutionTree);
        Assert.NotEqual("overview", WorkspaceOperations.SolutionTree);
        Assert.NotEqual("graph", WorkspaceOperations.SolutionTree);
    }

    [Fact]
    public async Task FakeWorkspaceQueries_RefusesSolutionTreeAsyncByName()
    {
        var fake = new SilentFake();
        var thrown = await Assert.ThrowsAsync<NotSupportedException>(
            () => fake.SolutionTreeAsync(new SolutionTreeQuery(), CancellationToken.None));
        Assert.Contains(nameof(IWorkspaceQueries.SolutionTreeAsync), thrown.Message, StringComparison.Ordinal);
    }

    [Fact]
    public void QueryJson_HasNoDropRelativePathsField()
    {
        var json = JsonSerializer.Serialize(new SolutionTreeQuery(), WorkspaceOperations.Wire);
        Assert.DoesNotContain("dropRelativePaths", json, StringComparison.OrdinalIgnoreCase);
        Assert.Contains("maxCensusFolders", json, StringComparison.Ordinal);
        Assert.Contains("maxFileArtifacts", json, StringComparison.Ordinal);
    }

    [Fact]
    public void ExtraJsonDropRelativePaths_DoesNotOmitFolders()
    {
        using var star = Star.Create();
        var query = JsonSerializer.Deserialize<SolutionTreeQuery>(
            """{"maxCensusFolders":2000,"maxFileArtifacts":5000,"dropRelativePaths":["omit_probe","omit_probe_2"]}""",
            WorkspaceOperations.Wire);
        Assert.NotNull(query);
        var result = star.Projections.SolutionTree(query);
        Assert.Contains(result.Nodes, n => PathsEqual(n.Path, "omit_probe"));
        Assert.Contains(result.Nodes, n => PathsEqual(n.Path, "unindexed_probe"));
    }

    [Fact]
    public void NormalizeRelative_MapsDotSlashAndTrailingSlash()
    {
        Assert.Equal("", SolutionTreeProjection.NormalizeRelative(""));
        Assert.Equal("", SolutionTreeProjection.NormalizeRelative("."));
        Assert.Equal("src", SolutionTreeProjection.NormalizeRelative("src/"));
        Assert.Equal("src/Program.cs", SolutionTreeProjection.NormalizeRelative(@"src\Program.cs"));
        Assert.Equal(
            SolutionTreeProjection.NormalizeRelative("src/"),
            SolutionTreeProjection.NormalizeRelative(SolutionTreeProjection.NormalizeRelative("src/")));
    }

    [Fact]
    public void ProductionSkip_ContainsBinWithoutATestInjectedSet()
    {
        Assert.Contains("bin", UnanalysedLanguages.Skip);
        Assert.Contains("obj", UnanalysedLanguages.Skip);
        Assert.Contains(".git", UnanalysedLanguages.Skip);
        Assert.Contains("node_modules", UnanalysedLanguages.Skip);
    }

    [Fact]
    public void StarDto_IndexedParentFileArtifact_UnindexedProbe_BinAbsentWithSkipCount()
    {
        using var star = Star.Create();
        var result = star.Projections.SolutionTree(new SolutionTreeQuery());

        var src = Folder(result, "src");
        Assert.Equal(CensusFolderCoverage.IndexedParent, src.Coverage);

        var file = FileNode(result, "src/Program.cs");
        Assert.Equal("Program", file.NodeId);
        Assert.Equal("class", file.NodeKind);
        Assert.Null(file.Coverage);

        var probe = Folder(result, "unindexed_probe");
        Assert.Equal(CensusFolderCoverage.Unindexed, probe.Coverage);

        Assert.DoesNotContain(result.Nodes, n => PathsEqual(n.Path, "bin"));
        Assert.True(result.SkipListedDirectoriesOmitted >= 1, "production Skip must omit bin");
        Assert.DoesNotContain(result.Disclosures, d => d.Cause == SolutionTreeShortfallCause.Cap);
    }

    [Fact]
    public void TwoAssertionsForOnePath_CollapseToOneFileArtifact()
    {
        using var star = Star.Create(extra: (store, root) =>
        {
            IndexScope(store, "csharp:src-dup", "",
                ("Program", "class", "src/Program.cs"),
                ("Program2", "class", "src/Program.cs"));
        });

        var result = star.Projections.SolutionTree(new SolutionTreeQuery());
        Assert.Equal(1, result.Nodes.Count(n =>
            n.Kind == SolutionTreeNodeKind.FileArtifact && PathsEqual(n.Path, "src/Program.cs")));
    }

    [Fact]
    public void DirectoryValuedAssertion_IsCensusFolderNotFileArtifact()
    {
        using var star = Star.Create(extra: (store, root) =>
        {
            IndexScope(store, "csharp:dir", "", ("SrcDir", "class", "src"));
        });

        var result = star.Projections.SolutionTree(new SolutionTreeQuery());
        Assert.DoesNotContain(result.Nodes, n =>
            n.Kind == SolutionTreeNodeKind.FileArtifact && PathsEqual(n.Path, "src"));
        Assert.Equal(CensusFolderCoverage.IndexedParent, Folder(result, "src").Coverage);
    }

    [Fact]
    public void TwoFilesInDifferentCensusFolders_SitUnderTheEmittedParents()
    {
        using var star = Star.Create(extra: (store, root) =>
        {
            Directory.CreateDirectory(Path.Combine(root, "lib"));
            File.WriteAllText(Path.Combine(root, "lib", "Util.cs"), "class Util {}");
            IndexScope(store, "csharp:lib", "", ("Util", "class", "lib/Util.cs"));
        });

        var result = star.Projections.SolutionTree(new SolutionTreeQuery());
        Assert.NotNull(FileNode(result, "src/Program.cs"));
        Assert.NotNull(FileNode(result, "lib/Util.cs"));
        Assert.Equal(CensusFolderCoverage.IndexedParent, Folder(result, "lib").Coverage);
        Assert.Equal("src", SolutionTreeProjection.ParentOf("src/Program.cs"));
        Assert.Equal("lib", SolutionTreeProjection.ParentOf("lib/Util.cs"));
    }

    [Fact]
    public void IoShortfallOnIoProbe_DisclosesNotRecordedAndLeavesUnindexedProbe()
    {
        using var star = Star.Create();
        var result = star.Projections.SolutionTree(
            new SolutionTreeQuery(),
            omitRelativePaths: null,
            abs =>
            {
                var rel = SolutionTreeProjection.NormalizeRelative(Path.GetRelativePath(star.Root, abs));
                if (SolutionTreeProjection.PathsEqual(rel, "io_probe"))
                {
                    throw new IOException("arranged io_probe shortfall");
                }

                return Directory.EnumerateDirectories(abs);
            });

        Assert.Contains(result.Disclosures, d =>
            d.Cause == SolutionTreeShortfallCause.Io
            && d.Message == SolutionTreeProjection.NotRecordedCopy
            && SolutionTreeProjection.PathsEqual(d.Path ?? "", "io_probe"));
        Assert.DoesNotContain(result.Nodes, n => PathsEqual(n.Path, "io_probe"));
        Assert.Equal(CensusFolderCoverage.Unindexed, Folder(result, "unindexed_probe").Coverage);
        Assert.DoesNotContain(result.Nodes, n => PathsEqual(n.Path, "bin"));
    }

    [Fact]
    public void PermissionShortfallOnOmitProbe_DisclosesAndLeavesUnindexedProbeAndSkipCount()
    {
        using var star = Star.Create();
        var result = star.Projections.SolutionTree(
            new SolutionTreeQuery(),
            omitRelativePaths: null,
            abs =>
            {
                var rel = SolutionTreeProjection.NormalizeRelative(Path.GetRelativePath(star.Root, abs));
                if (SolutionTreeProjection.PathsEqual(rel, "omit_probe"))
                {
                    throw new UnauthorizedAccessException("arranged omit_probe deny");
                }

                return Directory.EnumerateDirectories(abs);
            });

        Assert.Contains(result.Disclosures, d =>
            d.Cause == SolutionTreeShortfallCause.Permission
            && d.Message == SolutionTreeProjection.NotRecordedCopy
            && SolutionTreeProjection.PathsEqual(d.Path ?? "", "omit_probe"));
        Assert.DoesNotContain(result.Nodes, n => PathsEqual(n.Path, "omit_probe"));
        Assert.Equal(CensusFolderCoverage.Unindexed, Folder(result, "unindexed_probe").Coverage);
        Assert.True(result.SkipListedDirectoriesOmitted >= 1);
    }

    [Fact]
    public void NamedOmit_DropsOmitProbeDirs_KeepsUnindexedProbe_DerivesOmittedN()
    {
        using var star = Star.Create();
        var result = star.Projections.SolutionTree(
            new SolutionTreeQuery(),
            omitRelativePaths: ["omit_probe", "omit_probe_2"]);

        Assert.DoesNotContain(result.Nodes, n => PathsEqual(n.Path, "omit_probe"));
        Assert.DoesNotContain(result.Nodes, n => PathsEqual(n.Path, "omit_probe_2"));
        Assert.Equal(CensusFolderCoverage.Unindexed, Folder(result, "unindexed_probe").Coverage);
        Assert.True(result.OmittedByCap >= 2, "named omit must increment OmittedByCap");
        Assert.True(result.SkipListedDirectoriesOmitted >= 1);

        var cap = Assert.Single(result.Disclosures, d => d.Cause == SolutionTreeShortfallCause.Cap);
        Assert.Equal(result.OmittedByCap, cap.Count);
        Assert.Equal(SolutionTreeProjection.OmittedCopy(result.OmittedByCap), cap.Message);
        Assert.DoesNotContain(result.Nodes, n => n.Coverage is null && n.Kind == SolutionTreeNodeKind.CensusFolder);
        Assert.DoesNotContain(result.Disclosures, d =>
            d.Cause == SolutionTreeShortfallCause.Cap && d.Count != result.OmittedByCap);
    }

    [Fact]
    public void GenericCapBelowCount_MayDropUnindexedProbe_AndThereforeIsNotT5c()
    {
        using var star = Star.Create();
        var capped = star.Projections.SolutionTree(new SolutionTreeQuery(MaxCensusFolders: 3, MaxFileArtifacts: 50));
        Assert.DoesNotContain(capped.Nodes, n => PathsEqual(n.Path, "unindexed_probe"));

        var named = star.Projections.SolutionTree(
            new SolutionTreeQuery(),
            omitRelativePaths: ["omit_probe", "omit_probe_2"]);
        Assert.Contains(named.Nodes, n => PathsEqual(n.Path, "unindexed_probe"));
        Assert.DoesNotContain(named.Nodes, n => PathsEqual(n.Path, "omit_probe"));
    }

    [Fact]
    public void PythonTsScope_IndexesFolderWithoutPerFileRows_ExactCopy()
    {
        using var star = Star.Create(extra: (store, root) =>
        {
            Directory.CreateDirectory(Path.Combine(root, "pkg"));
            File.WriteAllText(Path.Combine(root, "pkg", "mod.py"), "x = 1\n");
            IndexScope(store, "python:pkg", "pkg",
                [("pkg.mod", "python-module", "python:pkg")],
                "python-extractor");
        });

        var result = star.Projections.SolutionTree(new SolutionTreeQuery());
        Assert.Equal(CensusFolderCoverage.IndexedParent, Folder(result, "pkg").Coverage);
        Assert.DoesNotContain(result.Nodes, n =>
            n.Kind == SolutionTreeNodeKind.FileArtifact
            && (n.Path.EndsWith(".py", StringComparison.OrdinalIgnoreCase)
                || n.Path.EndsWith(".ts", StringComparison.OrdinalIgnoreCase)));
        Assert.Contains(result.Disclosures, d =>
            d.Cause == SolutionTreeShortfallCause.PythonTsPerFile
            && d.Message == SolutionTreeProjection.PythonTsCopy);
        Assert.DoesNotContain(result.Nodes, n => PathsEqual(n.Path, "python:pkg"));
    }

    [Fact]
    public void AncestorCoverage_PythonTsOnlyParentOfIndexedDescendant_IsIndexedParent()
    {
        using var star = Star.Create(extra: (store, root) =>
        {
            Directory.CreateDirectory(Path.Combine(root, "outer", "inner"));
            File.WriteAllText(Path.Combine(root, "outer", "inner", "Lib.cs"), "class Lib {}");
            IndexScope(store, "python:outer", "outer",
                [("outer", "python-package", "python:outer")],
                "python-extractor");
            IndexScope(store, "csharp:inner", "", ("Lib", "class", "outer/inner/Lib.cs"));
        });

        var result = star.Projections.SolutionTree(new SolutionTreeQuery());
        Assert.Equal(CensusFolderCoverage.IndexedParent, Folder(result, "outer").Coverage);
        Assert.Equal(CensusFolderCoverage.IndexedParent, Folder(result, "outer/inner").Coverage);
        Assert.NotNull(FileNode(result, "outer/inner/Lib.cs"));
    }

    [Fact]
    public void BicepFilenameOnly_ResolvesUnderExistingCensusFolder()
    {
        using var star = Star.Create(extra: (store, root) =>
        {
            Directory.CreateDirectory(Path.Combine(root, "infra"));
            File.WriteAllText(Path.Combine(root, "infra", "main.bicep"), "param x string\n");
            IndexScope(store, "bicep:infra", "infra", ("main", "bicep-file", "main.bicep"));
        });

        var result = star.Projections.SolutionTree(new SolutionTreeQuery());
        Assert.NotNull(FileNode(result, "infra/main.bicep"));
        Assert.DoesNotContain(result.Nodes, n =>
            n.Kind == SolutionTreeNodeKind.CensusFolder && PathsEqual(n.Path, "main.bicep"));
        Assert.Equal(CensusFolderCoverage.IndexedParent, Folder(result, "infra").Coverage);
    }

    [Fact]
    public void BicepFilenameOnlyUnresolvable_DisclosesAndDoesNotMintAFolder()
    {
        using var star = Star.Create(extra: (store, root) =>
        {
            IndexScope(store, "bicep:ghost", "ghost", ("missing", "bicep-file", "missing.bicep"));
        });

        var result = star.Projections.SolutionTree(new SolutionTreeQuery());
        Assert.Contains(result.Disclosures, d =>
            d.Cause == SolutionTreeShortfallCause.UnresolvablePath
            && d.Message == SolutionTreeProjection.NotRecordedCopy);
        Assert.DoesNotContain(result.Nodes, n => PathsEqual(n.Path, "missing.bicep"));
        Assert.DoesNotContain(result.Nodes, n => PathsEqual(n.Path, "ghost"));
    }

    [Fact]
    public void HostileDotDot_DisclosesAndDoesNotInventAFolder()
    {
        using var star = Star.Create(extra: (store, root) =>
        {
            IndexScope(store, "csharp:escape", "", ("Escaped", "class", "../outside.cs"));
        });

        var result = star.Projections.SolutionTree(new SolutionTreeQuery());
        Assert.Contains(result.Disclosures, d => d.Cause == SolutionTreeShortfallCause.UnresolvablePath);
        Assert.DoesNotContain(result.Nodes, n => n.Path.Contains("..", StringComparison.Ordinal));
        Assert.DoesNotContain(result.Nodes, n => PathsEqual(n.Path, "outside.cs"));
    }

    [Fact]
    public void FileUnderNamedOmittedParent_IsAbsent()
    {
        using var star = Star.Create(extra: (store, root) =>
        {
            File.WriteAllText(Path.Combine(root, "omit_probe", "Hidden.cs"), "class Hidden {}");
            IndexScope(store, "csharp:omit", "", ("Hidden", "class", "omit_probe/Hidden.cs"));
        });

        var result = star.Projections.SolutionTree(
            new SolutionTreeQuery(),
            omitRelativePaths: ["omit_probe", "omit_probe_2"]);

        Assert.DoesNotContain(result.Nodes, n => PathsEqual(n.Path, "omit_probe/Hidden.cs"));
        Assert.DoesNotContain(result.Nodes, n => PathsEqual(n.Path, "omit_probe"));
    }

    [Fact]
    public void Census_DoesNotDescendAJunction_DisclosesReparsePoint()
    {
        using var star = Star.Create();
        var target = Path.Combine(star.Root, "junction_target");
        Directory.CreateDirectory(target);
        File.WriteAllText(Path.Combine(target, "secret.cs"), "class Secret {}");
        var link = Path.Combine(star.Root, "junction_probe");
        CreateJunction(link, target);
        Assert.True(new DirectoryInfo(link).Attributes.HasFlag(FileAttributes.ReparsePoint));

        var result = star.Projections.SolutionTree(new SolutionTreeQuery());
        Assert.DoesNotContain(result.Nodes, n => PathsEqual(n.Path, "junction_probe"));
        Assert.DoesNotContain(result.Nodes, n =>
            n.Path.StartsWith("junction_probe/", PathComparison.ForThisFileSystem));
        Assert.Contains(result.Disclosures, d =>
            d.Cause == SolutionTreeShortfallCause.ReparsePoint
            && d.Message == SolutionTreeProjection.NotRecordedCopy
            && SolutionTreeProjection.PathsEqual(d.Path ?? "", "junction_probe"));
        Assert.Contains(result.Nodes, n => PathsEqual(n.Path, "junction_target"));
    }

    [Fact]
    public void EnumsTravelAsDeclaredNames_NotKebabOrNumbers()
    {
        using var star = Star.Create();
        var result = star.Projections.SolutionTree(new SolutionTreeQuery());
        var json = JsonSerializer.Serialize(result, WorkspaceOperations.Wire);
        Assert.Contains("\"FileArtifact\"", json, StringComparison.Ordinal);
        Assert.Contains("\"CensusFolder\"", json, StringComparison.Ordinal);
        Assert.Contains("\"IndexedParent\"", json, StringComparison.Ordinal);
        Assert.Contains("\"Unindexed\"", json, StringComparison.Ordinal);
        Assert.DoesNotContain("\"file-artifact\"", json, StringComparison.Ordinal);
        Assert.DoesNotContain("\"kind\":0", json, StringComparison.Ordinal);
    }

    [Fact]
    public void CancelMidWalk_ThrowsOperationCanceled_NotAPartialTree()
    {
        using var star = Star.Create();
        using var cts = new CancellationTokenSource();
        Assert.ThrowsAny<OperationCanceledException>(() =>
            star.Projections.SolutionTree(
                new SolutionTreeQuery(),
                omitRelativePaths: null,
                abs =>
                {
                    cts.Cancel();
                    cts.Token.ThrowIfCancellationRequested();
                    return Directory.EnumerateDirectories(abs);
                },
                cts.Token));
    }

    [Fact]
    public void SolutionTreeSpan_EmitsCountsNotPaths()
    {
        using var star = Star.Create();
        var captured = new List<Activity>();
        using var listener = new ActivityListener
        {
            ShouldListenTo = source => source.Name == "aide.projection.query",
            Sample = (ref ActivityCreationOptions<ActivityContext> _) => ActivitySamplingResult.AllDataAndRecorded,
            ActivityStopped = captured.Add,
        };
        ActivitySource.AddActivityListener(listener);

        var result = star.Projections.SolutionTree(new SolutionTreeQuery());

        var span = Assert.Single(captured, a => Equals(a.GetTagItem("projection"), "solution-tree"));
        Assert.NotNull(span.GetTagItem("returned.census_folders"));
        Assert.NotNull(span.GetTagItem("returned.file_artifacts"));
        Assert.NotNull(span.GetTagItem("returned.indexed_parent"));
        Assert.NotNull(span.GetTagItem("returned.unindexed"));
        Assert.NotNull(span.GetTagItem("skip.omitted"));
        Assert.NotNull(span.GetTagItem("omitted.by_cap"));
        Assert.NotNull(span.GetTagItem("returned.bytes"));
        Assert.NotNull(span.GetTagItem("shrunk.attempts"));
        Assert.Equal("ok", span.GetTagItem("outcome"));
        var folders = result.Nodes.Count(n => n.Kind == SolutionTreeNodeKind.CensusFolder);
        var files = result.Nodes.Count(n => n.Kind == SolutionTreeNodeKind.FileArtifact);
        Assert.True(
            folders < SolutionTreeProjection.DefaultMaxCensusFolders,
            $"F* census folders {folders} reached the production cap {SolutionTreeProjection.DefaultMaxCensusFolders}");
        Assert.True(
            files < SolutionTreeProjection.DefaultMaxFileArtifacts,
            $"F* file-artifacts {files} reached the production cap {SolutionTreeProjection.DefaultMaxFileArtifacts}");
        if (result.Disclosures.Count == 0)
        {
            Assert.Null(span.GetTagItem("shortfall.causes"));
        }
        else
        {
            Assert.NotNull(span.GetTagItem("shortfall.causes"));
        }
        foreach (var (key, value) in span.Tags)
        {
            Assert.False(key.Contains("path", StringComparison.OrdinalIgnoreCase));
            Assert.DoesNotContain(star.Root, value ?? "", StringComparison.OrdinalIgnoreCase);
        }
    }

    [Fact]
    public void CancelMidWalk_EmitsOutcomeCanceled_OmitsCountTags()
    {
        using var star = Star.Create();
        var captured = new List<Activity>();
        using var listener = new ActivityListener
        {
            ShouldListenTo = source => source.Name == "aide.projection.query",
            Sample = (ref ActivityCreationOptions<ActivityContext> _) => ActivitySamplingResult.AllDataAndRecorded,
            ActivityStopped = captured.Add,
        };
        ActivitySource.AddActivityListener(listener);

        using var cts = new CancellationTokenSource();
        Assert.ThrowsAny<OperationCanceledException>(() =>
            star.Projections.SolutionTree(
                new SolutionTreeQuery(),
                omitRelativePaths: null,
                abs =>
                {
                    cts.Cancel();
                    cts.Token.ThrowIfCancellationRequested();
                    return Directory.EnumerateDirectories(abs);
                },
                cts.Token));

        var span = Assert.Single(captured, a => Equals(a.GetTagItem("projection"), "solution-tree"));
        Assert.Equal("canceled", span.GetTagItem("outcome"));
        Assert.Null(span.GetTagItem("returned.census_folders"));
        Assert.Null(span.GetTagItem("returned.file_artifacts"));
        Assert.Null(span.GetTagItem("shortfall.causes"));
    }

    [Fact]
    public void HostileCensus_ShrinksUnderTheFrame()
    {
        var dir = Path.Combine(Path.GetTempPath(), "aide-st-hostile", Guid.NewGuid().ToString("N"));
        Directory.CreateDirectory(dir);
        var store = WorkspaceStore.Open(Path.Combine(dir, "facts.db"));
        try
        {
            var folder = new string('w', 80);
            Directory.CreateDirectory(Path.Combine(dir, folder));
            var assertions = new List<EvidenceAssertion>
            {
                Assertion("csharp:h", "csharp:h", "declared_at", "", "", "workspace-core"),
            };
            for (var i = 0; i < 3_000; i++)
            {
                var name = $"F{i:D4}.cs";
                File.WriteAllText(Path.Combine(dir, folder, name), "class X {}");
                var id = $"Long.Namespace.{new string('N', 240)}.Type{i}";
                assertions.Add(Assertion("csharp:h", id, "has_type", "class", $"{folder}/{name}", "csharp-extractor"));
            }

            using (var writer = store.BeginWrite())
            {
                writer.DesireScopeGeneration("csharp:h", 1, "rev-1");
                writer.CommitSnapshot("csharp:h", 1, "rev-1", assertions, complete: true);
                writer.Commit();
            }

            var projections = new ProjectionService(store, dir);
            var result = projections.SolutionTree(new SolutionTreeQuery());
            var bytes = Encoding.UTF8.GetByteCount(
                JsonSerializer.Serialize(result, WorkspaceOperations.Wire));
            Assert.True(bytes <= IpcFraming.MaxFrameBytes, $"tree payload {bytes} exceeds the frame");
            Assert.True(result.OmittedByCap > 0, "hostile census must shrink or cap-omit");
        }
        finally
        {
            store.Dispose();
            try { Directory.Delete(dir, recursive: true); } catch (IOException) { }
        }
    }

    private static SolutionTreeNode Folder(SolutionTreeResult result, string path) =>
        Assert.Single(result.Nodes, n =>
            n.Kind == SolutionTreeNodeKind.CensusFolder && PathsEqual(n.Path, path));

    private static SolutionTreeNode FileNode(SolutionTreeResult result, string path) =>
        Assert.Single(result.Nodes, n =>
            n.Kind == SolutionTreeNodeKind.FileArtifact && PathsEqual(n.Path, path));

    private static bool PathsEqual(string left, string right) =>
        SolutionTreeProjection.PathsEqual(left, right);

    private static void IndexScope(
        WorkspaceStore store,
        string scopeId,
        string declaredAt,
        params (string NodeId, string NodeKind, string ArtifactPath)[] files) =>
        IndexScope(store, scopeId, declaredAt, files, "csharp-extractor");

    private static void IndexScope(
        WorkspaceStore store,
        string scopeId,
        string declaredAt,
        (string NodeId, string NodeKind, string ArtifactPath)[] files,
        string extractorId)
    {
        var assertions = new List<EvidenceAssertion>
        {
            Assertion(scopeId, scopeId, "declared_at", declaredAt, declaredAt, "workspace-core"),
        };
        foreach (var (nodeId, nodeKind, artifactPath) in files)
        {
            assertions.Add(Assertion(scopeId, nodeId, "has_type", nodeKind, artifactPath, extractorId));
        }

        using var writer = store.BeginWrite();
        writer.DesireScopeGeneration(scopeId, 1, "rev-1");
        writer.CommitSnapshot(scopeId, 1, "rev-1", assertions, complete: true);
        foreach (var (nodeId, nodeKind, _) in files)
        {
            writer.UpsertNode(nodeId, nodeKind, nodeId);
        }

        writer.Commit();
    }

    private static EvidenceAssertion Assertion(
        string scopeId, string subject, string predicate, string @object,
        string artifactPath, string extractorId) =>
        new(scopeId, "rev-1", subject, predicate, @object,
            EvidenceOrigin.Static, VerificationStatus.Verified,
            new Provenance(artifactPath, predicate == "declared_at" ? null : "1:1",
                extractorId, "1.0.0", Observed));

    private static void CreateJunction(string link, string target)
    {
        if (!OperatingSystem.IsWindows())
        {
            Directory.CreateSymbolicLink(link, target);
            return;
        }

        var mklink = Process.Start(new ProcessStartInfo("cmd.exe", $"/c mklink /J \"{link}\" \"{target}\"")
        {
            UseShellExecute = false,
            CreateNoWindow = true,
            RedirectStandardOutput = true,
            RedirectStandardError = true,
        })!;
        mklink.WaitForExit();
        Assert.True(mklink.ExitCode == 0, "mklink /J failed: " + mklink.StandardError.ReadToEnd());
    }

    private sealed class SilentFake : FakeWorkspaceQueries;

    private sealed class Star : IDisposable
    {
        private Star(string root, WorkspaceStore store, ProjectionService projections)
        {
            Root = root;
            Store = store;
            Projections = projections;
        }

        public string Root { get; }
        public WorkspaceStore Store { get; }
        public ProjectionService Projections { get; }

        public static Star Create(Action<WorkspaceStore, string>? extra = null)
        {
            var root = Path.Combine(Path.GetTempPath(), "aide-st", Guid.NewGuid().ToString("N"));
            var ws = Path.Combine(root, "ws");
            Directory.CreateDirectory(Path.Combine(ws, "src"));
            File.WriteAllText(Path.Combine(ws, "src", "Program.cs"), "class Program {}");
            Directory.CreateDirectory(Path.Combine(ws, "unindexed_probe"));
            Directory.CreateDirectory(Path.Combine(ws, "omit_probe"));
            Directory.CreateDirectory(Path.Combine(ws, "omit_probe_2"));
            Directory.CreateDirectory(Path.Combine(ws, "io_probe"));
            Directory.CreateDirectory(Path.Combine(ws, "bin"));
            File.WriteAllText(Path.Combine(ws, "bin", "app.dll"), "bin");

            var store = WorkspaceStore.Open(Path.Combine(root, "facts.db"));
            IndexScope(store, "csharp:src", "", ("Program", "class", "src/Program.cs"));
            extra?.Invoke(store, ws);
            return new Star(ws, store, new ProjectionService(store, ws));
        }

        public void Dispose()
        {
            Store.Dispose();
            try
            {
                Directory.Delete(Path.GetDirectoryName(Root)!, recursive: true);
            }
            catch (IOException) { }
            catch (UnauthorizedAccessException) { }
        }
    }
}
