using AiDe.Core;
using AiDe.Core.Extraction;
using AiDe.Core.Facts;
using AiDe.Core.Projections;

namespace AiDe.Core.Tests;

/// <summary>
/// Workspaces that are missing something, and what the tool says about it.
/// </summary>
/// <remarks>
/// <para><b>The control for DC-025 — absence rendered as success.</b> Four instances, every one found
/// by pointing the panes at a real repository and none by a test: a missing context map read as
/// perfect coverage, a search bounded at fifty read as the whole workspace, unreadable source read as
/// no source, and a file that would not parse read as a smaller file. Each time the arithmetic was
/// right and the claim was false, which is why counting more carefully could never have caught
/// them.</para>
///
/// <para><b>Fixtures always have the thing.</b> That is the whole reason the class survived: a
/// fixture is built by the person building the feature, so it contains a context map, compiles, and
/// is written in the language the extractor reads. This file is the opposite — a corpus of
/// workspaces defined by what they LACK, each asserting that the absence is stated rather than
/// rendered as a clean zero.</para>
///
/// <para><b>Every case asserts a sentence, not a count.</b> A count is what was already right.</para>
/// </remarks>
public sealed class LackingWorkspaceTests : IDisposable
{
    private readonly string _dir =
        Path.Combine(Path.GetTempPath(), "aide-lacking", Guid.NewGuid().ToString("N"));

    public void Dispose()
    {
        try { Directory.Delete(_dir, recursive: true); } catch (IOException) { }
    }

    private string Make(string name, Action<string> build)
    {
        var root = Path.Combine(_dir, name);
        Directory.CreateDirectory(root);
        build(root);
        return root;
    }

    private async Task<WorkspaceCore.IndexResult> IndexAsync(string root)
    {
        using var core = WorkspaceCore.Open(
            "lacking", root, Path.Combine(_dir, "data", Guid.NewGuid().ToString("N")),
            WorkspaceExtractors.Default());

        return await core.IndexCSharpAsync("rev-1", CancellationToken.None);
    }

    private static void Project(string root, string source = "namespace N { public class Good { } }")
    {
        File.WriteAllText(Path.Combine(root, "Lacking.csproj"),
            """<Project Sdk="Microsoft.NET.Sdk"><PropertyGroup><TargetFramework>net10.0</TargetFramework></PropertyGroup></Project>""");
        File.WriteAllText(Path.Combine(root, "Good.cs"), source);
    }

    // ── Lacking: anything at all ──────────────────────────────────────────────────────────

    // Platform=Windows: counts PATH entries under Windows PATH semantics; every entry exists on the Linux runner
    [Trait("Platform", "Windows")]
    [Fact]
    public async Task AnEmptyWorkspaceSaysThereWasNothingToRead()
    {
        var result = await IndexAsync(Make("empty", _ => { }));

        Assert.Equal(0, result.ScopesFound);

        // The only case where a clean zero IS the truth — and it still has to be a sentence, because
        // a pane rendering nothing is what every other case in this file looks like.
        var summary = new Ipc.IndexSummary(
            result.ScopesFound, result.ScopesIndexed, result.Assertions,
            result.Failed, result.Disclosures, result.Contexts, result.ScopesReused);

        Assert.Contains("No C# projects", summary.Describe(), StringComparison.Ordinal);
    }

    // ── Lacking: a language this build can read ───────────────────────────────────────────

    [Fact]
    public async Task AWorkspaceOfUnreadableLanguagesNamesThem()
    {
        // Measured on a real repository: 63 Python files produced zero scopes, zero assertions and
        // an EMPTY disclosure list — indistinguishable from an empty directory.
        // Go and Rust, because Python and TypeScript are READ now. A language that gains an
        // extractor leaves this list on the same day — a closed gap reported as open is the same
        // defect as an open one hidden — so this fixture has to move as coverage grows.
        var root = Make("polyglot", r =>
        {
            File.WriteAllText(Path.Combine(r, "main.py"), "print('hi')");
            File.WriteAllText(Path.Combine(r, "main.go"), "package main");
            File.WriteAllText(Path.Combine(r, "lib.rs"), "pub fn go() {}");
        });

        var result = await IndexAsync(root);

        Assert.DoesNotContain(result.Disclosures, d => d.StartsWith("python-not-analysed", StringComparison.Ordinal));
        Assert.DoesNotContain(result.Disclosures, d => d.StartsWith("typescript-not-analysed", StringComparison.Ordinal));
        Assert.Contains(result.Disclosures, d => d.StartsWith("go-not-analysed", StringComparison.Ordinal));
        Assert.Contains(result.Disclosures, d => d.StartsWith("rust-not-analysed", StringComparison.Ordinal));
    }

    // ── Lacking: source that parses ───────────────────────────────────────────────────────

    [Fact]
    public async Task AProjectWithSourceThatWillNotParseSaysWhichFile()
    {
        // Roslyn returns a tree with error nodes rather than throwing, so extraction SUCCEEDS and
        // finds less. The state a developer is in most often.
        var root = Make("unparseable", r =>
        {
            Project(r);
            File.WriteAllText(Path.Combine(r, "Bad.cs"), "namespace N { public class Bad { void M( { } }");
        });

        var result = await IndexAsync(root);

        Assert.Contains(result.Disclosures, d => d.StartsWith("source-did-not-parse", StringComparison.Ordinal));
        Assert.Contains(result.Disclosures, d => d.Contains("Bad.cs", StringComparison.Ordinal));

        // Still indexed: half a project's evidence beats none, provided the gap is stated.
        Assert.Empty(result.Failed);
    }

    // ── Lacking: a declared context map ───────────────────────────────────────────────────

    [Fact]
    public async Task AWorkspaceWithNoContextMapDoesNotClaimFullCoverage()
    {
        var root = Make("nomap", r => Project(r));
        await IndexAsync(root);

        using var core = WorkspaceCore.Open(
            "lacking", root, Path.Combine(_dir, "data", "nomap"), WorkspaceExtractors.Default());

        using var reader = core.Store.BeginRead();
        var map = BoundedContextReader.Load(
            Path.Combine(root, BoundedContextReader.DefaultRelativePath), reader.ReadDeclaredSubjects());

        var view = new ContextProjection(map, []).Compute();

        // The field, not a cleverer count. No map means no uncovered list, so every number reads as
        // complete — and it did, in the sentence "every declared symbol belongs to a context".
        Assert.False(view.IsDeclared);
    }

    // ── Lacking: evidence the read could reach ────────────────────────────────────────────

    [Fact]
    public void ABoundedReadThatMissedSomethingSaysSo()
    {
        // The panes computed crossings, joins and coverage from 50 nodes of 2,164 and presented the
        // result as the answer. The shortfall is the sentence that could not previously be said.
        var short_ = new EvidenceRead([], NodesMatched: 2164, NodesRead: 50, NeighbourLimit: 50,
            NodesAtNeighbourLimit: 0);

        Assert.False(short_.IsComplete);
        Assert.Contains("lower bounds", short_.Shortfall!, StringComparison.Ordinal);

        // And silence when there is nothing to caveat — a banner on every refresh is a banner
        // nobody reads, and then the one that mattered goes unread too.
        var whole = new EvidenceRead([], 2164, 2164, 50, 0);
        Assert.Null(whole.Shortfall);
    }

    // ── Lacking: a successful extraction, where the graph shows the LAST one ──────────────

    [Fact]
    public async Task AFailedScopeSaysItsEvidenceIsStale()
    {
        // A failed extraction deliberately leaves the last good snapshot rendering — blanking the
        // graph on a build error would be worse. But what renders is then OLD, and nothing said so:
        // a stale scope drew exactly like a current one, and only the incident sidecar knew.
        //
        // The fix states it rather than retracting, because retracting would contradict a decision
        // recorded in RefreshScopeAsync rather than build on it.
        var root = Make("goes-bad", r =>
        {
            Project(r);
            File.WriteAllText(Path.Combine(r, "infra.bicep"),
                "resource site 'Microsoft.Web/sites@2023-01-01' = {" + (char)10 + "  name: 'ok'" + (char)10 + "}" + (char)10);
        });

        var data = Path.Combine(_dir, "data", "goes-bad");

        using (var first = WorkspaceCore.Open("stale", root, data, WorkspaceExtractors.Default()))
        {
            var initial = await first.IndexCSharpAsync("rev-1", CancellationToken.None);
            Assert.Empty(initial.Failed);
        }

        // An extractor that now refuses the bicep scope, with the C# one untouched.
        using var core = WorkspaceCore.Open("stale", root, data,
            new CompositeExtractor(
                csharp: new CSharpExtractor(),
                fallback: new FixtureExtractor(),
                bicep: new RefusingExtractor(),
                schema: new EfSchemaExtractor()));

        var result = await core.IndexCSharpAsync("rev-2", CancellationToken.None, force: true);

        Assert.Contains("bicep:infra", result.Failed);
        Assert.Contains(result.Disclosures, d => d.StartsWith("stale-scope", StringComparison.Ordinal));
        Assert.Contains(result.Disclosures, d => d.Contains("rev-1", StringComparison.Ordinal));
    }

    /// <summary>An extractor that always fails, for exercising the stale path.</summary>
    private sealed class RefusingExtractor : IExtractor
    {
        public string ScopeKind => "refusing";

        public Task<ExtractionResult> ExtractAsync(ExtractionRequest request, CancellationToken cancellationToken) =>
            Task.FromResult(new ExtractionResult([], false,
                [new ExtractionDiagnostic("AIDE-TEST-REFUSED", request.ScopeId, "refused on purpose")]));
    }

    // -- No longer lacking: Python is read, and what is NOT read is stated ---------------

    [Fact]
    public async Task PythonIsExtracted_WithItsGapsDeclared()
    {
        // Six repositories disclosed unread Python before anything could read it. The disclosure was
        // right and it is not a substitute: a graph that says "there is Python here and I cannot see
        // it" is honest and still blind.
        var root = Make("python", r =>
        {
            Directory.CreateDirectory(Path.Combine(r, "pkg"));
            File.WriteAllText(Path.Combine(r, "pkg", "service.py"),
                "import os" + (char)10 +
                "from .models import Order" + (char)10 +
                "" + (char)10 +
                "class Service:" + (char)10 +
                "    def handle(self):" + (char)10 +
                "        pass" + (char)10 +
                "" + (char)10 +
                "def main():" + (char)10 +
                "    pass" + (char)10);
        });

        var result = await IndexAsync(root);
        Assert.Equal(1, result.ScopesIndexed);

        using var core = WorkspaceCore.Open("py", root, Path.Combine(_dir, "pydata"),
            WorkspaceExtractors.Default());
        await core.IndexCSharpAsync("rev-1", CancellationToken.None);

        using var reader = core.Store.BeginRead();
        var facts = reader.AllCurrentAssertions();

        Assert.Contains(facts, a => a.Predicate == "has_type" && a.Object == "python-class"
            && a.Subject.EndsWith("Service", StringComparison.Ordinal));
        Assert.Contains(facts, a => a.Predicate == "has_type" && a.Object == "python-function"
            && a.Subject.EndsWith("main", StringComparison.Ordinal));
        // `os` is NOT an edge. The standard library is a boundary of this product, not a gap in it,
        // and drawing it put sys/os/json/re among the most connected nodes of a real graph — the same
        // reason the C# extractor declines to draw the BCL. It is counted in a disclosure instead.
        Assert.DoesNotContain(facts, a => a.Predicate == "imports" && a.Object == "os");

        Assert.Contains(facts, a => a.Predicate == "discloses"
            && a.Object.StartsWith(
                PythonExtractor.Disclosures.StandardLibraryNotIndexed, StringComparison.Ordinal));

        // The method is not claimed as a FUNCTION — asserting `handle` as a module-level function
        // would put a symbol in the graph no importer can reach — and it IS claimed as a member of
        // the class that declares it, which is what a class diagram needs and what the column-zero
        // rule used to throw away along with the error it was avoiding.
        Assert.DoesNotContain(facts, a => a.Predicate == "has_type"
            && a.Subject.EndsWith(".handle", StringComparison.Ordinal));

        Assert.Contains(facts, a => a.Predicate == "has_member" && a.Object == "handle");

        // An import target is INFERRED: the module path as written, not a resolved symbol. Calling
        // that Verified is exactly the defect DC-022 is about.
        Assert.All(facts.Where(a => a.Predicate == "imports"),
            a => Assert.Equal(VerificationStatus.Inferred, a.Status));

        // And every gap is stated rather than left silent.
        var disclosed = facts.Where(a => a.Predicate == "discloses").Select(a => a.Object).ToList();
        // Carries a COUNT now, because "imports are not resolved" and "2 imports name something this
        // scope does not contain" are different statements about how much of the graph is a guess.
        Assert.Contains(disclosed, d =>
            d.StartsWith(PythonExtractor.Disclosures.ImportsNotResolved, StringComparison.Ordinal));
        // The nested-declaration disclosure is CONDITIONAL now: this fixture's method is read as a
        // member, and nothing else is nested, so a disclosure here would be describing a gap that is
        // no longer there. A disclosure that fires when nothing was hidden trains a reader to skip
        // disclosures (DC-025), and `PythonMethodTests` asserts it still fires — with a count — when
        // something genuinely is nested inside a method.
        Assert.DoesNotContain(disclosed, d =>
            d.StartsWith(PythonExtractor.Disclosures.NestedDeclarationsNotAnalysed, StringComparison.Ordinal));
        Assert.Contains(PythonExtractor.Disclosures.DynamicImportsNotAnalysed, disclosed);
    }

    [Fact]
    public void AnImportThatNamesAModuleInTheScopeIsVerified()
    {
        // 330 import edges on a real repository were all Inferred and all unresolved. An import that
        // names a module this scope CONTAINS points at a file that exists and was read, which is
        // what lets the edge be Verified rather than a string.
        // Module IDS are repository-relative PATHS; import TARGETS are dotted names. An absolute
        // import is read from the repository root, which is what a path id is measured from.
        var modules = new HashSet<string>(StringComparer.Ordinal) { "pkg/models", "pkg/service", "top" };

        // Absolute, present.
        Assert.Equal("top", PythonExtractor.Resolve("top", "pkg/service", modules));
        Assert.Equal("pkg/models", PythonExtractor.Resolve("pkg.models", "pkg/service", modules));

        // Relative: one dot is the importing module's own package.
        Assert.Equal("pkg/models", PythonExtractor.Resolve(".models", "pkg/service", modules));

        // Absent stays unresolved rather than being invented — it may be a package, a module in
        // another scope, or nothing at all, and asserting which is the guess DC-022 is about.
        Assert.Null(PythonExtractor.Resolve("os", "pkg/service", modules));
        Assert.Null(PythonExtractor.Resolve(".nope", "pkg/service", modules));

        // Climbing above the root resolves to nothing rather than throwing.
        Assert.Null(PythonExtractor.Resolve("....x", "pkg/service", modules));
    }

    [Fact]
    public async Task ResolvedAndUnresolvedImportsCarryDifferentStatus()
    {
        var root = Make("pyimports", r =>
        {
            Directory.CreateDirectory(Path.Combine(r, "pkg"));
            File.WriteAllText(Path.Combine(r, "pkg", "models.py"), "class Order:" + (char)10 + "    pass" + (char)10);
            File.WriteAllText(Path.Combine(r, "pkg", "service.py"),
                // A stdlib import, a resolvable local one, and one nobody can identify — the three
                // outcomes this test distinguishes.
                "import os" + (char)10 + "import third_party_thing" + (char)10
                + "from .models import Order" + (char)10);
        });

        using var core = WorkspaceCore.Open("pyimp", root, Path.Combine(_dir, "pyimpdata"),
            WorkspaceExtractors.Default());

        await core.IndexCSharpAsync("rev-1", CancellationToken.None);

        using var reader = core.Store.BeginRead();
        var imports = reader.AllCurrentAssertions().Where(a => a.Predicate == "imports").ToList();

        var resolved = Assert.Single(imports, i => i.Object == "pkg/models");
        Assert.Equal(VerificationStatus.Verified, resolved.Status);

        // The standard library is counted, not drawn — so the contrast this test exists to pin is
        // now between a resolved local module and an import nobody can identify, which is the pair
        // that actually differs in status.
        Assert.DoesNotContain(imports, i => i.Object == "os");

        var unknown = Assert.Single(imports, i => i.Object == "third_party_thing");
        Assert.Equal(VerificationStatus.Inferred, unknown.Status);
    }

    [Fact]
    public void TypeScriptSpecifiersResolveOnlyWhenTheScopeContainsThem()
    {
        var modules = new HashSet<string>(StringComparer.Ordinal)
        {
            "src/app", "src/models", "src/util/index",
        };

        // Relative, present, with and without an extension.
        Assert.Equal("src/models", TypeScriptExtractor.Resolve("./models", "src/app", modules));
        Assert.Equal("src/models", TypeScriptExtractor.Resolve("./models.ts", "src/app", modules));

        // A directory specifier means its index file.
        Assert.Equal("src/util/index", TypeScriptExtractor.Resolve("./util", "src/app", modules));

        // A BARE specifier is a package or a path alias, and resolving it needs configuration this
        // extractor deliberately does not read — so it is left alone rather than guessed at.
        Assert.Null(TypeScriptExtractor.Resolve("react", "src/app", modules));
        Assert.Null(TypeScriptExtractor.Resolve("@scope/thing", "src/app", modules));

        // Absent, and climbing above the root, both resolve to nothing rather than throwing.
        Assert.Null(TypeScriptExtractor.Resolve("./nope", "src/app", modules));
        Assert.Null(TypeScriptExtractor.Resolve("../../../x", "src/app", modules));
    }

    [Fact]
    public async Task TypeScriptIsExtracted_WithItsGapsDeclared()
    {
        var root = Make("ts", r =>
        {
            Directory.CreateDirectory(Path.Combine(r, "src"));
            File.WriteAllText(Path.Combine(r, "src", "models.ts"),
                "export interface Order { id: string; }" + (char)10);
            File.WriteAllText(Path.Combine(r, "src", "app.ts"),
                "import { Order } from './models';" + (char)10 +
                "import React from 'react';" + (char)10 +
                "export class App { run() {} }" + (char)10 +
                "function hidden() {}" + (char)10);

            // A declaration file re-states types defined elsewhere; indexing it would put every
            // symbol in the graph twice, once with nothing behind it.
            File.WriteAllText(Path.Combine(r, "src", "globals.d.ts"), "declare const X: number;" + (char)10);
        });

        using var core = WorkspaceCore.Open("ts", root, Path.Combine(_dir, "tsdata"),
            WorkspaceExtractors.Default());

        var result = await core.IndexCSharpAsync("rev-1", CancellationToken.None);
        Assert.Empty(result.Failed);

        using var reader = core.Store.BeginRead();
        var facts = reader.AllCurrentAssertions();

        Assert.Contains(facts, a => a.Predicate == "has_type" && a.Object == "typescript-class"
            && a.Subject.EndsWith(".App", StringComparison.Ordinal));
        Assert.Contains(facts, a => a.Predicate == "has_type" && a.Object == "typescript-interface"
            && a.Subject.EndsWith(".Order", StringComparison.Ordinal));

        // POLICY CHANGED, and this assertion changed with it rather than being deleted. It read "not
        // exported, so not claimed" — which is why 13 TypeScript scopes on TheTerrace produced no
        // class, function, interface or type at all while every one of them disclosed
        // `typescript-non-exported-not-analysed`. A function at column zero is a thing that exists;
        // the export keyword says who may REACH it, so it is now an attribute of the declaration
        // rather than a condition on seeing it. The limit that remains is column zero, which is what
        // `typescript-nested-declarations-not-analysed` discloses.
        Assert.Contains(facts, a => a.Predicate == "has_type" && a.Object == "typescript-function"
            && a.Subject.EndsWith(".hidden", StringComparison.Ordinal));

        Assert.Contains(facts, a => a.Predicate == "is_exported" && a.Object == "false"
            && a.Subject.EndsWith(".hidden", StringComparison.Ordinal));

        Assert.Contains(facts, a => a.Predicate == "is_exported" && a.Object == "true"
            && a.Subject.EndsWith(".App", StringComparison.Ordinal));

        // Nor is the declaration file.
        Assert.DoesNotContain(facts, a => a.Subject.Contains("globals", StringComparison.Ordinal));

        // Modules are named by their REPOSITORY-relative path, not their scope-relative one. The
        // scope-relative rule this replaces is what let two scopes name one node: every Python
        // package has an `__init__.py` and every TypeScript directory an `index.ts`, so a repository
        // with five packages produced five scopes each declaring `__init__` — one node in the graph
        // carrying the merged edges of five unrelated files.
        var relative = Assert.Single(facts, a => a.Predicate == "imports" && a.Object == "src/models");
        Assert.Equal(VerificationStatus.Verified, relative.Status);

        var package = Assert.Single(facts, a => a.Predicate == "imports" && a.Object == "react");
        Assert.Equal(VerificationStatus.Inferred, package.Status);

        // And TypeScript must no longer be reported as unread.
        Assert.DoesNotContain(result.Disclosures,
            d => d.StartsWith("typescript-not-analysed", StringComparison.Ordinal));
    }

    [Fact]
    public void TheCompositionRoutesTypeScriptToTheTypeScriptExtractor()
    {
        var composite = Assert.IsType<CompositeExtractor>(WorkspaceExtractors.Default());
        Assert.Equal("typescript", composite.RouteFor("typescript:src").ScopeKind);
    }

    [Fact]
    public void TheCompositionRoutesPythonToThePythonExtractor()
    {
        var composite = Assert.IsType<CompositeExtractor>(WorkspaceExtractors.Default());
        Assert.Equal("python", composite.RouteFor("python:pkg").ScopeKind);
    }

    // -- Lacking: an environment a child process can carry -------------------------------

    [Fact]
    public void AnOversizedPathIsReportedWithItsSizeAndItsCause()
    {
        // MEASURED on the reporting machine: PATH is 22,297 characters and cmd.exe silently drops a
        // variable that large, so every .cmd shim - which is every npm-installed CLI - starts with
        // an EMPTY PATH. Proven not to be this product's doing: the same shim run from a plain
        // PowerShell also received an empty PATH, and trimming PATH to 1,799 characters made it
        // arrive whole. What WAS ours is that the terminal opened looking perfectly healthy.
        var junk = string.Join(";", Enumerable.Range(0, 200).Select(i =>
            $@"C:\Users\u\AppData\Local\Temp\build-nuget-{i:x8}deadbeef{i:x4}\dotnet-home\.dotnet\tools"));

        var findings = AiDe.Core.Terminal.EnvironmentHealth.Inspect($@"C:\Windows\system32;{junk}");

        // BOTH findings apply here and both are said: the entries are dead AND the total is past the
        // limit. Reporting only the size would leave the user with a number and no lead; reporting
        // only the dead entries would understate why it matters.
        Assert.Equal(2, findings.Count);
        var finding = findings.Single(f => f.Contains("characters across", StringComparison.Ordinal));

        // The number, so the user can see how far past the limit they are...
        Assert.Contains(AiDe.Core.Terminal.EnvironmentHealth.CmdVariableLimit.ToString("N0"),
            finding, StringComparison.Ordinal);

        // ...and the CAUSE, because two hundred unique paths is a number, not a lead. The entries
        // are unique by construction, so grouping on the literal path finds nothing.
        Assert.Contains("200 entries", finding, StringComparison.Ordinal);
        Assert.Contains("Temp", finding, StringComparison.Ordinal);
    }

    [Fact]
    public void TheLimitIsTheMeasuredOneNotTheDocumentedOne()
    {
        // Bisected on the reporting machine: cmd carried 8,151 characters and dropped 8,152, printing
        // "The input line is too long" and losing the value. The documented figure is 8,191; the
        // difference is the variable's own name plus block overhead. Pinned so the constant cannot
        // drift back to a number nobody measured.
        Assert.Equal(8151, AiDe.Core.Terminal.EnvironmentHealth.CmdVariableLimit);

        var justUnder = new string('x', AiDe.Core.Terminal.EnvironmentHealth.CmdVariableLimit);
        var justOver = new string('x', AiDe.Core.Terminal.EnvironmentHealth.CmdVariableLimit + 1);

        Assert.Empty(AiDe.Core.Terminal.EnvironmentHealth.Inspect(justUnder));
        Assert.NotEmpty(AiDe.Core.Terminal.EnvironmentHealth.Inspect(justOver));
    }

    // Platform=Windows: counts PATH entries under Windows PATH semantics; every entry exists on the Linux runner
    [Trait("Platform", "Windows")]
    [Fact]
    public void PathRegrowthIsCaughtBySHAPE_LongBeforeItReachesTheLimit()
    {
        // The oversize check only fires once PATH is past cmd's limit, which is to say after the
        // damage. 187 dead build directories accumulated before anything noticed. This fires on the
        // shape at twenty entries, while PATH is still nowhere near the limit.
        var dead = string.Join(";", Enumerable.Range(0, 20).Select(i =>
            $@"C:\Users\u\AppData\Local\Temp\build-{i:x8}\dotnet-home\.dotnet\tools"));

        var findings = AiDe.Core.Terminal.EnvironmentHealth.Inspect($@"C:\Windows;{dead}");

        var finding = Assert.Single(findings);
        Assert.Contains("do not exist", finding, StringComparison.Ordinal);
        Assert.Contains("20 of 21", finding, StringComparison.Ordinal);

        // Well under the limit, so the SIZE finding must not also fire — one finding, not two.
        Assert.DoesNotContain("characters across", finding, StringComparison.Ordinal);
    }

    [Fact]
    public void AFewDeadEntriesAreNormalAndSayNothing()
    {
        // An uninstalled tool or a moved SDK leaves a dead entry. This is looking for accumulation,
        // not for tidiness, and a warning about three stale paths is a warning nobody reads twice.
        var dead = string.Join(";", Enumerable.Range(0, 3).Select(i => $@"C:\nope\{i}"));

        Assert.Empty(AiDe.Core.Terminal.EnvironmentHealth.Inspect($@"C:\Windows;{dead}"));
    }

    [Fact]
    public void AHealthyPathSaysNothing()
    {
        // The other half. This message explains a whole class of confusion exactly once; said on
        // every machine it would be noise, and then unread on the machine it was written for.
        Assert.Empty(AiDe.Core.Terminal.EnvironmentHealth.Inspect(
            @"C:\Windows\system32;C:\Windows;C:\Program Files\dotnet"));
    }

    // ── The rule the corpus exists to hold ────────────────────────────────────────────────

    [Fact]
    public async Task EveryLackingWorkspaceSaysSomethingAboutWhatItCouldNotDo()
    {
        // The generalisation, asserted rather than described: a workspace missing something must
        // never produce a result that is silent about it. Adding a new kind of absence to this list
        // is how the next instance gets caught before a real repository finds it.
        var cases = new (string Name, Action<string> Build)[]
        {
            ("only-python", r => File.WriteAllText(Path.Combine(r, "a.py"), "x = 1")),
            ("broken-source", r =>
            {
                Project(r);
                File.WriteAllText(Path.Combine(r, "Bad.cs"), "class Bad { void M( { }");
            }),
            ("no-packages", r => Project(r)),
        };

        foreach (var (name, build) in cases)
        {
            var result = await IndexAsync(Make(name, build));

            Assert.True(result.Disclosures.Count > 0,
                $"'{name}' produced a result with nothing to say about what it could not read");
        }
    }
}
