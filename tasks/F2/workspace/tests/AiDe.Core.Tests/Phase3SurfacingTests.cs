using AiDe.Core.Workbench;
using AiDe.Core.Ipc;
using AiDe.Core.Extraction;
using AiDe.Core.Facts;
using AiDe.Core.Projections;
using AiDe.Core.Terminal;

namespace AiDe.Core.Tests;

/// <summary>
/// Making the Phase 3 evidence usable: a configurable readiness marker, a crossing that can be
/// opened, and uncovered symbols a user can act on.
/// </summary>
/// <remarks>
/// Every test here exists because a number was being shown that nobody could check, or a refusal
/// was being made that nobody could fix.
/// </remarks>
public sealed class Phase3SurfacingTests : IDisposable
{
    private readonly string _dir =
        Path.Combine(Path.GetTempPath(), "aide-readiness", Guid.NewGuid().ToString("N"));

    public void Dispose()
    {
        try { Directory.Delete(_dir, recursive: true); } catch (IOException) { }
    }

    private string Write(string json)
    {
        Directory.CreateDirectory(_dir);
        File.WriteAllText(Path.Combine(_dir, AgentReadinessProfiles.FileName), json);
        return _dir;
    }

    // ── Readiness markers, per agent ──────────────────────────────────────────────────────

    [Fact]
    public void NoFile_LeavesTheBuiltInMarkersInForce()
    {
        var profiles = AgentReadinessProfiles.Load(_dir);

        Assert.Empty(profiles.Problems);
        Assert.Equal(AgentReadinessWatcher.KnownAgents["claude"], profiles.For("claude")!.Pattern);
        Assert.Equal("built-in", profiles.For("claude")!.Origin);
    }

    [Fact]
    public void AConfiguredMarkerReplacesTheBuiltInOne()
    {
        // The point of the whole file: a built-in marker that does not match a real agent's prompt
        // refused that agent forever, and the only way to change it was a rebuild.
        var profiles = AgentReadinessProfiles.Load(Write("""{ "claude": "READY>\\s*$" }"""));

        Assert.Empty(profiles.Problems);
        Assert.Equal(@"READY>\s*$", profiles.For("claude")!.Pattern);
        Assert.Equal(AgentReadinessProfiles.FileName, profiles.For("claude")!.Origin);

        var watcher = profiles.WatcherFor("claude")!;
        watcher.Observe("thinking...\nREADY>");
        Assert.True(watcher.IsReady);
    }

    [Fact]
    public void AnUnusablePatternIsReported_AndTheBuiltInMarkerStaysInForce()
    {
        // Never fails open. A pattern that does not compile must not become "assume ready" — the
        // one thing worse than refusing a ready agent is dispatching into an unready one.
        var profiles = AgentReadinessProfiles.Load(Write("""{ "claude": "([unclosed" }"""));

        Assert.Single(profiles.Problems);
        Assert.Contains("claude", profiles.Problems[0], StringComparison.Ordinal);
        Assert.Equal(AgentReadinessWatcher.KnownAgents["claude"], profiles.For("claude")!.Pattern);
    }

    [Fact]
    public void AnEmptyMarkerMeansThisAgentHasNone_AndDispatchCannotEstablishReadiness()
    {
        // A legitimate thing to say: it makes the refusal deliberate rather than the accident of a
        // pattern that happens never to match.
        var profiles = AgentReadinessProfiles.Load(Write("""{ "claude": "" }"""));

        Assert.Empty(profiles.Problems);
        Assert.Null(profiles.For("claude"));
        Assert.Null(profiles.WatcherFor("claude"));
    }

    [Fact]
    public void AnAgentTheBuildNeverHeardOfCanBeAdded()
    {
        var profiles = AgentReadinessProfiles.Load(Write("""{ "aider": "\\n>\\s*$" }"""));

        Assert.NotNull(profiles.WatcherFor("aider"));
        Assert.Equal(AgentReadinessProfiles.FileName, profiles.For("aider")!.Origin);
    }

    [Fact]
    public void AMalformedFileIsReported_NotSilentlyIgnored()
    {
        var profiles = AgentReadinessProfiles.Load(Write("{ not json"));

        Assert.Single(profiles.Problems);
        Assert.NotNull(profiles.For("claude"));
    }

    [Fact]
    public void TheTemplateIsNeverWrittenOverAUsersEdits()
    {
        // The file exists to hold a marker someone tuned. Regenerating it over their edit would
        // destroy the only copy of the thing this feature is for.
        var path = AgentReadinessProfiles.WriteTemplate(_dir);
        File.WriteAllText(path, """{ "claude": "MINE$" }""");

        AgentReadinessProfiles.WriteTemplate(_dir);

        Assert.Equal("""{ "claude": "MINE$" }""", File.ReadAllText(path));
    }

    [Fact]
    public void TheWatcherReportsTheTailItJudged()
    {
        // Tuning a marker by reasoning about what an agent probably prints is how a pattern that
        // never matches survives. This is what it actually printed.
        var watcher = new AgentReadinessWatcher(@"NEVERMATCHES$");
        watcher.Observe("╭─────╮\r\n│ > │\r\n╰─────╯");

        Assert.False(watcher.IsReady);
        Assert.Contains("│ > │", watcher.LastJudged, StringComparison.Ordinal);
        Assert.Equal("NEVERMATCHES$", watcher.Pattern);
    }

    [Fact]
    public void ARealTrustGateIsNotMistakenForAPrompt()
    {
        // MEASURED, not imagined. spikes/agent-readiness captured what Claude Code actually draws
        // when this shell starts it, and the bytes contain a chevron — at ESC[14;2H, as the SELECTION
        // CURSOR of the trust dialog, sitting on "No, exit".
        //
        // A looser marker is the obvious repair when a pattern does not match, and it would report
        // READY at the exact moment dispatch is most dangerous: the Enter that submits a prompt is
        // the Enter that confirms "No, exit". This is the negative control on that repair.
        var watcher = new AgentReadinessWatcher(AgentReadinessWatcher.KnownAgents["claude"]);
        watcher.Observe(TrustGateOutput());

        Assert.False(watcher.IsReady);
        Assert.Contains("❯", watcher.LastJudged, StringComparison.Ordinal);
    }

    /// <summary>The captured session output, control characters restored.</summary>
    /// <remarks>
    /// Stored escaped so the fixture is readable and diffable in exactly the whitespace a
    /// tail-anchored pattern turns on. Unescaped here so the watcher sees the real bytes.
    /// </remarks>
    private static string TrustGateOutput()
    {
        var path = Path.Combine(AppContext.BaseDirectory, "fixtures", "claude-trust-gate.escaped.txt");
        Assert.True(File.Exists(path), $"the captured agent output is missing: {path}");

        return File.ReadAllText(path)
            .Replace("<ESC>", "\u001b", StringComparison.Ordinal)
            .Replace("<BEL>", "\a", StringComparison.Ordinal)
            .Replace("<TAB>", "\t", StringComparison.Ordinal)
            .Replace("<CR>", "\r", StringComparison.Ordinal)
            // The escaper prints a real newline after <LF> so the dump wraps; both go.
            .Replace("<LF>\n", "\n", StringComparison.Ordinal)
            .Replace("<LF>", "\n", StringComparison.Ordinal);
    }

    // ── An unchanged scope is not re-read, and a changed one always is ────────────────────

    private string Workspace()
    {
        var root = Path.Combine(_dir, "ws");
        Directory.CreateDirectory(Path.Combine(root, "infra"));
        File.WriteAllText(Path.Combine(root, "infra", "main.bicep"),
            "resource site 'Microsoft.Web/sites@2023-01-01' = {\n  name: 'probe'\n}\n");
        return root;
    }

    /// <summary>A revision of the shape the product attaches since Ruling 85 — the observed HEAD — never the retired fixture literal (Ruling 98).</summary>
    private const string ObservedHead = "51e806f8";

    private async Task<(int Indexed, int Reused)> IndexAsync(string root, string data, bool force = false, string revision = ObservedHead)
    {
        using var core = WorkspaceCore.Open("fp", root, data, WorkspaceExtractors.Default());
        var result = await core.IndexCSharpAsync(revision, CancellationToken.None, force: force);
        return (result.ScopesIndexed, result.ScopesReused);
    }

    private static string CurrentRevision(string root, string data)
    {
        using var core = WorkspaceCore.Open("fp", root, data, WorkspaceExtractors.Default());
        using var reader = core.Store.BeginRead();
        return reader.CurrentSourceRevision();
    }

    /// <summary>
    /// Ruling 98 (R-1): a store the pre-Ruling-85 product wrote carries <c>rev-1</c> on every
    /// snapshot, and the reuse guard — unchanged fingerprint, a committed snapshot — never opens the
    /// snapshot's revision, so Ruling 85's fix at the WRITER could not reach a store the old writer
    /// had already written: the operator's TheTerrace still read <i>rev rev-1</i> on build 51e806f8.
    /// A snapshot whose revision base is the retired literal is not reusable: the next index
    /// re-extracts once and stamps the observed HEAD; the one after that reuses it.
    /// </summary>
    [Fact]
    public async Task ASnapshotStampedWithTheRetiredFixtureLiteral_IsReExtractedOnce_ThenTheObservedHeadStands()
    {
        var root = Workspace();
        var data = Path.Combine(_dir, "data");

        // The pre-85 store: the product attached the fixture literal to everything it indexed.
        var first = await IndexAsync(root, data, revision: SourceRevision.RetiredFixtureLiteral);
        Assert.Equal((1, 0), first);
        Assert.Equal(SourceRevision.RetiredFixtureLiteral, CurrentRevision(root, data));

        // The next index, on the same unchanged tree, carries the observed HEAD: re-extracted, not reused.
        var second = await IndexAsync(root, data);
        Assert.Equal((1, 0), second);
        Assert.Equal(ObservedHead, CurrentRevision(root, data));

        // Exactly once: the re-stamped snapshot is reusable like any other.
        var third = await IndexAsync(root, data);
        Assert.Equal((0, 1), third);
        Assert.Equal(ObservedHead, CurrentRevision(root, data));
    }

    [Fact]
    public async Task AWorkspaceCanBeIndexedAgainAfterARestart()
    {
        // Found while testing the fingerprint cache, and it has nothing to do with caching. The
        // generation counter lives in memory and starts at zero on every open, while the store does
        // not — so the SECOND index of any workspace after a restart re-used generation 1 and
        // violated the desired-generation primary key. The daemon opens the store fresh every time
        // it starts. Nothing had ever indexed twice across a reopen, so nothing had ever noticed.
        var root = Workspace();
        var data = Path.Combine(_dir, "data");

        await IndexAsync(root, data);

        // A different core over the same store — exactly what a daemon restart is.
        var after = await IndexAsync(root, data, force: true);

        Assert.Equal(1, after.Indexed);
    }

    [Fact]
    public async Task AnUnchangedScopeIsReused_AndTheReuseIsReportedSeparately()
    {
        var root = Workspace();
        var data = Path.Combine(_dir, "data");

        var first = await IndexAsync(root, data);
        var second = await IndexAsync(root, data);

        Assert.Equal(1, first.Indexed);
        Assert.Equal(0, first.Reused);

        // Reported as REUSED, never folded into indexed: "1 of 1 indexed" would be a true sentence
        // about a run that read nothing.
        Assert.Equal(0, second.Indexed);
        Assert.Equal(1, second.Reused);
    }

    [Fact]
    public async Task AChangedFileIsAlwaysReRead()
    {
        var root = Workspace();
        var data = Path.Combine(_dir, "data");

        await IndexAsync(root, data);

        File.WriteAllText(Path.Combine(root, "infra", "main.bicep"),
            "resource other 'Microsoft.Web/sites@2023-01-01' = {\n  name: 'changed'\n}\n");

        var after = await IndexAsync(root, data);

        Assert.Equal(1, after.Indexed);
        Assert.Equal(0, after.Reused);
    }

    [Fact]
    public async Task ForceReReadsEverything()
    {
        // The escape hatch. An operator must always be able to say "I do not believe the cache".
        var root = Workspace();
        var data = Path.Combine(_dir, "data");

        await IndexAsync(root, data);
        var forced = await IndexAsync(root, data, force: true);

        Assert.Equal(1, forced.Indexed);
        Assert.Equal(0, forced.Reused);
    }

    [Fact]
    public async Task AScopeWhoseEvidenceIsGoneIsReRead_EvenThoughItsInputsAreUnchanged()
    {
        // The fingerprint says the INPUTS have not changed. It says nothing about whether the output
        // survived — and a store rebuilt under an unchanged working tree would otherwise leave the
        // scope skipped forever with its evidence permanently missing.
        var root = Workspace();
        var data = Path.Combine(_dir, "data");

        await IndexAsync(root, data);

        // The sidecar survives; the store does not. Exactly the shape of a compaction or a reset.
        File.Delete(Path.Combine(data, "workspace.db"));

        var after = await IndexAsync(root, data);

        Assert.Equal(1, after.Indexed);
        Assert.Equal(0, after.Reused);
    }

    [Fact]
    public void AnUpgradedExtractorInvalidatesEveryFingerprint()
    {
        // Without the generation in the digest, an extractor improvement would reach only the files
        // a user happened to touch afterwards, and the graph would be built by two extractor
        // versions with nothing saying which produced what.
        Assert.False(string.IsNullOrWhiteSpace(ScopeFingerprints.ExtractorGeneration));

        var scope = new ScopeDescriptor("bicep:main", Path.Combine(Workspace(), "infra", "main.bicep"), "bicep");
        var digest = ScopeFingerprints.Compute(Path.Combine(_dir, "ws"), scope);

        Assert.NotEqual(string.Empty, digest);
    }

    [Fact]
    public async Task AScopeThatDisappearsIsForgotten_AndItsDepartureIsRecorded()
    {
        // A project appearing or leaving is not a change to any EXISTING scope, so every per-scope
        // fingerprint can be identical while the workspace's shape has changed underneath. A new
        // scope is always read because it has nothing to match; the case that needed closing is the
        // opposite one — evidence for a scope that has gone, sitting in the store describing code
        // that no longer exists, with nothing to remove it and nothing to say so.
        var root = Workspace();
        var data = Path.Combine(_dir, "data");

        File.WriteAllText(Path.Combine(root, "infra", "second.bicep"),
            "resource other 'Microsoft.Web/sites@2023-01-01' = {" + (char)10 + "  name: 'second'" + (char)10 + "}" + (char)10);

        var first = await IndexAsync(root, data);
        Assert.Equal(2, first.Indexed);

        File.Delete(Path.Combine(root, "infra", "second.bicep"));

        var after = await IndexAsync(root, data);

        // The survivor is reused; the departed one is gone from the sidecar rather than reused
        // forever.
        Assert.Equal(1, after.Reused);
        Assert.Equal(0, after.Indexed);

        var incidents = File.ReadAllText(Path.Combine(data, "health-incidents.jsonl"));
        Assert.Contains("scope_departed", incidents, StringComparison.Ordinal);
    }

    [Fact]
    public async Task ADepartedScopesEvidenceStopsBeingDrawn_ButItsHistorySurvives()
    {
        // Removing a project left its symbols, edges and crossings in every projection for ever:
        // nothing re-extracts a scope that no longer exists, so nothing ever replaced its snapshot.
        // The graph kept drawing deleted code.
        var root = Workspace();
        var data = Path.Combine(_dir, "data");

        File.WriteAllText(Path.Combine(root, "infra", "second.bicep"),
            "resource departed 'Microsoft.Web/sites@2023-01-01' = {" + (char)10 + "  name: 'departed'" + (char)10 + "}" + (char)10);

        await IndexAsync(root, data);

        using (var before = WorkspaceCore.Open("fp", root, data, WorkspaceExtractors.Default()))
        using (var reader = before.Store.BeginRead())
        {
            Assert.Contains(reader.AllCurrentAssertions(), a => a.ScopeId == "bicep:second");
        }

        File.Delete(Path.Combine(root, "infra", "second.bicep"));
        await IndexAsync(root, data);

        using var core = WorkspaceCore.Open("fp", root, data, WorkspaceExtractors.Default());
        using var after = core.Store.BeginRead();

        // Retired from the CURRENT view…
        Assert.DoesNotContain(after.AllCurrentAssertions(), a => a.ScopeId == "bicep:second");

        // …and superseded rather than deleted: the snapshot that retired it is a real, empty,
        // committed generation, so what the graph once said is still readable.
        var snapshot = after.LatestCommittedSnapshot("bicep:second");
        Assert.NotNull(snapshot);
        Assert.Equal(0, snapshot!.Value.AssertionCount);

        // The surviving scope is untouched.
        Assert.Contains(after.AllCurrentAssertions(), a => a.ScopeId == "bicep:main");
    }

    [Fact]
    public async Task ForceReachesTheCoreThroughTheCommandSurface()
    {
        // The escape hatch existed as an API parameter with nothing able to reach it. This is the
        // path the Ctrl+K, Shift+I command takes.
        var root = Workspace();
        var data = Path.Combine(_dir, "data");

        using var core = WorkspaceCore.Open("fp", root, data, WorkspaceExtractors.Default());
        var commands = new LocalWorkspaceCommands(
            (_, _, _) => Task.FromResult(0),
            (revision, force, ct) => core.IndexCSharpAsync(revision, ct, force: force)
                .ContinueWith(t => new IndexSummary(
                    t.Result.ScopesFound, t.Result.ScopesIndexed, t.Result.Assertions,
                    t.Result.Failed, t.Result.Disclosures, t.Result.Contexts, t.Result.ScopesReused), ct));

        await commands.IndexSolutionAsync(ObservedHead, CancellationToken.None);

        var cached = await commands.IndexSolutionAsync(ObservedHead, CancellationToken.None);
        Assert.Equal(1, cached.ScopesReused);
        Assert.Contains("reused", cached.Describe(), StringComparison.OrdinalIgnoreCase);

        var forced = await commands.IndexSolutionAsync(ObservedHead, CancellationToken.None, force: true);
        Assert.Equal(0, forced.ScopesReused);
    }

    [Fact]
    public void SourceThisBuildCannotReadIsDisclosed()
    {
        // MEASURED on a fourth repository: 63 Python files and 40 TypeScript produced zero scopes,
        // zero assertions and an EMPTY disclosure list — indistinguishable from an empty directory.
        // Third repository in a row where the arithmetic was right and the claim was false.
        var root = Path.Combine(_dir, "polyglot");
        Directory.CreateDirectory(Path.Combine(root, "app"));
        Directory.CreateDirectory(Path.Combine(root, "node_modules", "junk"));

        File.WriteAllText(Path.Combine(root, "app", "main.py"), "print('hi')");
        File.WriteAllText(Path.Combine(root, "app", "util.py"), "x = 1");
        File.WriteAllText(Path.Combine(root, "app", "main.go"), "package main");

        // Vendored code is somebody else's; counting it would make the disclosure a number about
        // node_modules rather than about this repository.
        File.WriteAllText(Path.Combine(root, "node_modules", "junk", "vendored.js"), "module.exports = {}");

        var disclosures = UnanalysedLanguages.Survey(root);

        // Python and TypeScript moved OFF this list when their extractors landed. Go is still
        // unread and is still named — the survey reports what is genuinely not analysed, and a
        // language that gains an extractor must leave the list on the same day.
        Assert.DoesNotContain(disclosures, d => d.StartsWith("python-not-analysed", StringComparison.Ordinal));
        Assert.Contains(disclosures, d => d.StartsWith("go-not-analysed", StringComparison.Ordinal));
        Assert.DoesNotContain(disclosures, d => d.StartsWith("javascript", StringComparison.Ordinal));
    }

    [Fact]
    public void AWorkspaceWithNothingToIndexStillSaysWhatItDidNotRead()
    {
        var summary = new IndexSummary(0, 0, 0, [], ["python-not-analysed (63 file(s))"]);

        Assert.Contains("python-not-analysed", summary.Describe(), StringComparison.Ordinal);
        Assert.Contains("Not analysed", summary.Describe(), StringComparison.Ordinal);
    }

    [Fact]
    public void ACSharpWorkspaceDisclosesNothingItCanRead()
    {
        // The other half: a disclosure that fires on every workspace is noise, and a repository this
        // build CAN read must not be told its own source went unanalysed.
        var root = Path.Combine(_dir, "csonly");
        Directory.CreateDirectory(root);
        File.WriteAllText(Path.Combine(root, "Program.cs"), "class P { }");

        Assert.Empty(UnanalysedLanguages.Survey(root));
    }

    [Fact]
    public void EveryCatalogCommandDeclaresItsMenu()
    {
        // Placement is a Core decision that used to live in a design-owned file: a conformance test
        // requires every catalog command to be reachable from a menu, so adding one here forced an
        // edit there. Declaring it on the command lets the menu builder derive its grouping, and the
        // seam stops crossing. This is the half that makes the derivation possible — a command with
        // no menu would silently vanish from a builder that reads this field.
        var homeless = WorkbenchCommandCatalog.All
            .Where(c => string.IsNullOrWhiteSpace(c.Menu))
            .Select(c => c.Id)
            .ToList();

        Assert.True(homeless.Count == 0,
            "catalog commands with no declared menu: " + string.Join(", ", homeless));
    }

    [Fact]
    public void EveryCommandNamesAMenuTheShellRenders()
    {
        // WHAT THIS CAN AND CANNOT CHECK. `MainMenuBuilder` is internal to AiDe.App, so this test
        // cannot see what the builder renders — despite its name, it never compared two sources. It
        // asserted six hard-coded per-menu COUNTS against the catalog alone, which proves nothing
        // about the builder and breaks every time anybody adds a command. It broke on `_View`
        // (9 → 11) the day the design session added the search and sequence surfaces, and the
        // correct response to that failure was to change a number, which is the signature of a test
        // that is measuring the wrong thing (DC-021).
        //
        // The real invariant — every catalog command appears in the rendered menu — is asserted by
        // `MainMenuTests.TheMenuCoversEveryCatalogCommand`, App-side, against the actual builder.
        // What is left here is what Core CAN see and what actually holds: every command declares a
        // menu, and that menu is one the shell knows how to render.
        // The six top-level names are the design language's (DESIGN.md PS-M1): Terminal became
        // Prompt once the terminal verbs moved to File as entry verbs (Addendum C US-C11).
        var menus = new HashSet<string>(
            ["_File", "_Edit", "_View", "_Window", "_Prompt", "_Help"], StringComparer.Ordinal);

        var undeclared = WorkbenchCommandCatalog.All
            .Where(c => string.IsNullOrEmpty(c.Menu) || !menus.Contains(c.Menu))
            .Select(c => $"{c.Id} -> '{c.Menu}'")
            .ToList();

        Assert.True(undeclared.Count == 0,
            "these commands name a menu the shell does not render, so they are unreachable from it: "
            + string.Join(", ", undeclared));

        // And the check is asserted to be looking at something: an empty catalog would satisfy every
        // line above (DC-016).
        Assert.True(WorkbenchCommandCatalog.All.Count > 20,
            $"only {WorkbenchCommandCatalog.All.Count} command(s) found — this test would pass by "
            + "looking at nothing");
    }

    [Fact]
    public async Task ASourceFileThatDoesNotParseIsDisclosed()
    {
        // The state a developer is in most often, and it was invisible. Roslyn does not throw on
        // broken source — it returns a tree with error nodes — so the extraction SUCCEEDS and simply
        // finds less, which is indistinguishable from a smaller file. Measured on a copy of a real
        // repository with one deliberate syntax error: 10 of 10 scopes, 0 failed, and nothing
        // anywhere saying a file had not been read (DC-025, fourth instance).
        var root = Path.Combine(_dir, "broken");
        Directory.CreateDirectory(root);

        File.WriteAllText(Path.Combine(root, "Broken.csproj"),
            "<Project Sdk=\"Microsoft.NET.Sdk\"><PropertyGroup><TargetFramework>net10.0</TargetFramework>" +
            "</PropertyGroup></Project>");

        File.WriteAllText(Path.Combine(root, "Good.cs"), "namespace N { public class Good { } }");
        File.WriteAllText(Path.Combine(root, "Bad.cs"), "namespace N { public class Bad { void M( { } }");

        using var core = WorkspaceCore.Open("broken", root, Path.Combine(_dir, "data"),
            WorkspaceExtractors.Default());

        var result = await core.IndexCSharpAsync("rev-1", CancellationToken.None);

        Assert.Contains(result.Disclosures, d => d.StartsWith("source-did-not-parse", StringComparison.Ordinal));
        Assert.Contains(result.Disclosures, d => d.Contains("Bad.cs", StringComparison.Ordinal));

        // The scope is NOT failed: half a file's evidence is better than none, as long as the gap is
        // stated. A build error must not cost the developer every other type in the project.
        Assert.Empty(result.Failed);
        Assert.Equal(1, result.ScopesIndexed);
    }

    [Fact]
    public async Task AProjectThatParsesCleanlyDisclosesNoParseFailure()
    {
        // The other half. A disclosure that fires on every project is noise, and this one would be
        // read as "your code is broken" by everyone whose code is fine.
        var root = Path.Combine(_dir, "clean");
        Directory.CreateDirectory(root);

        File.WriteAllText(Path.Combine(root, "Clean.csproj"),
            "<Project Sdk=\"Microsoft.NET.Sdk\"><PropertyGroup><TargetFramework>net10.0</TargetFramework>" +
            "</PropertyGroup></Project>");

        File.WriteAllText(Path.Combine(root, "Good.cs"), "namespace N { public class Good { } }");

        using var core = WorkspaceCore.Open("clean", root, Path.Combine(_dir, "data2"),
            WorkspaceExtractors.Default());

        var result = await core.IndexCSharpAsync("rev-1", CancellationToken.None);

        Assert.DoesNotContain(result.Disclosures,
            d => d.StartsWith("source-did-not-parse", StringComparison.Ordinal));
    }

    [Fact]
    public void TheWeakestStatusWinsBecauseTheEnumIsOrderedStrongestFirst()
    {
        // DeriveClaimCurrent folds several assertions of one triple with `g.Max(a => a.Status)` and
        // a comment saying the WEAKEST status wins — "promoting on the strongest would manufacture
        // confidence". That is true only because the enum is ordered strongest-first, so Max picks
        // the numerically largest, which is the least certain. Reorder the enum and the fold
        // silently inverts into exactly what the comment forbids, with nothing failing.
        Assert.True(VerificationStatus.Verified < VerificationStatus.Inferred);
        Assert.True(VerificationStatus.Inferred < VerificationStatus.Unverified);

        var statuses = new[] { VerificationStatus.Verified, VerificationStatus.Inferred };
        Assert.Equal(VerificationStatus.Inferred, statuses.Max());

        var withUnverified = new[] { VerificationStatus.Verified, VerificationStatus.Unverified };
        Assert.Equal(VerificationStatus.Unverified, withUnverified.Max());
    }

    // ── Paging that cannot skip or repeat a row ───────────────────────────────────────────

    [Fact]
    public async Task PagingReturnsEveryAssertionExactlyOnce()
    {
        // The panes want every current assertion and were rebuilding that set node by node through
        // Describe, bounded at 50 neighbours, which lost two join edges of 124 on a real repository.
        // Paging is the fix, and paging is where records quietly go missing — so this asserts the
        // union of the pages equals the whole set, with nothing repeated.
        var root = Workspace();
        var data = Path.Combine(_dir, "data");

        using var core = WorkspaceCore.Open("page", root, data, WorkspaceExtractors.Default());
        await core.IndexCSharpAsync("rev-1", CancellationToken.None);

        var queries = new LocalWorkspaceQueries(core.Projections);

        List<EvidenceAssertion> everything;
        using (var reader = core.Store.BeginRead())
        {
            everything = [.. reader.AllCurrentAssertions().Select(a => new EvidenceAssertion(
                a.ScopeId, a.ArtifactRevision, a.Subject, a.Predicate, a.Object,
                a.Origin, a.Status, a.Provenance))];
        }

        Assert.NotEmpty(everything);

        // A page size of ONE, so every boundary in the set is exercised. A comfortable page size
        // tests that the query runs, not that the cursor is right.
        var paged = new List<EvidenceAssertion>();
        string? cursor = null;
        var pages = 0;

        do
        {
            var page = await queries.EvidenceAsync(cursor, 1, CancellationToken.None);
            paged.AddRange(page.Assertions);
            cursor = page.NextCursor;
            pages++;
        }
        while (cursor is not null && pages < 500);

        Assert.Equal(everything.Count, paged.Count);

        var key = (EvidenceAssertion a) => $"{a.Subject}|{a.Predicate}|{a.Object}";
        Assert.Equal(
            everything.Select(key).OrderBy(k => k, StringComparer.Ordinal),
            paged.Select(key).OrderBy(k => k, StringComparer.Ordinal));

        // Nothing repeated — the failure mode a cursor over a non-unique ordering produces.
        Assert.Equal(paged.Count, paged.Select(key).Distinct(StringComparer.Ordinal).Count());
    }

    [Fact]
    public async Task PagingDoesNotLoseARowWhenTwoScopesAssertTheSameTriple()
    {
        // MEASURED on a real repository: 2,158 assertions in the store, 2,157 through the paged
        // read. (subject, predicate, object) is NOT unique — two scopes can assert the same triple —
        // and a cursor over a non-unique ordering silently loses exactly the rows that tie, when a
        // page boundary happens to land on one. The scope is part of the ordering and the cursor now.
        var root = Path.Combine(_dir, "ties");
        Directory.CreateDirectory(Path.Combine(root, "a"));
        Directory.CreateDirectory(Path.Combine(root, "b"));

        // Two identical modules in two scopes: the same triples from different scope ids.
        foreach (var package in new[] { "a", "b" })
        {
            File.WriteAllText(Path.Combine(root, package, "same.py"),
                "import os" + (char)10 + "class Same:" + (char)10 + "    pass" + (char)10);
        }

        using var core = WorkspaceCore.Open("ties", root, Path.Combine(_dir, "tiedata"),
            WorkspaceExtractors.Default());

        await core.IndexCSharpAsync("rev-1", CancellationToken.None);

        int inStore;
        using (var reader = core.Store.BeginRead())
        {
            inStore = reader.AllCurrentAssertions().Count;
        }

        var queries = new LocalWorkspaceQueries(core.Projections);
        var paged = 0;
        string? cursor = null;

        // A page size of one, so every boundary — including the tied ones — is a boundary.
        do
        {
            var page = await queries.EvidenceAsync(cursor, 1, CancellationToken.None);
            paged += page.Assertions.Count;
            cursor = page.NextCursor;
        }
        while (cursor is not null && paged <= inStore + 10);

        Assert.Equal(inStore, paged);
    }

    [Fact]
    public async Task AMalformedCursorRestartsRatherThanFailing()
    {
        // The cursor is opaque and a caller was never meant to construct one. A read that throws on
        // a value nobody was supposed to inspect turns a cosmetic problem into a dead pane.
        var root = Workspace();
        var data = Path.Combine(_dir, "data");

        using var core = WorkspaceCore.Open("page", root, data, WorkspaceExtractors.Default());
        await core.IndexCSharpAsync("rev-1", CancellationToken.None);

        var queries = new LocalWorkspaceQueries(core.Projections);
        var page = await queries.EvidenceAsync("not-a-cursor", 50, CancellationToken.None);

        Assert.NotEmpty(page.Assertions);
    }

    // ── A bounded read says what it did not see ───────────────────────────────────────────

    [Fact]
    public void ACompleteReadSaysNothing()
    {
        // Silence is the correct output when there is nothing to caveat. A banner on every refresh
        // is a banner the user stops reading, and then the one that mattered goes unread too.
        var read = new EvidenceRead([], NodesMatched: 12, NodesRead: 12, NeighbourLimit: 60,
            NodesAtNeighbourLimit: 0);

        Assert.True(read.IsComplete);
        Assert.Null(read.Shortfall);
    }

    [Fact]
    public void UnreadNodesAreNamedWithTheirCount()
    {
        var read = new EvidenceRead([], NodesMatched: 9000, NodesRead: 4000, NeighbourLimit: 60,
            NodesAtNeighbourLimit: 0);

        Assert.False(read.IsComplete);
        Assert.Contains("5,000 of 9,000", read.Shortfall!, StringComparison.Ordinal);
        Assert.Contains("lower bounds", read.Shortfall!, StringComparison.Ordinal);
    }

    [Fact]
    public void BothCausesAreReported_BecauseTheyHaveDifferentFixes()
    {
        // "The workspace is bigger than the search cap" and "these nodes are unusually connected"
        // are different problems. Collapsing them into one sentence leaves the reader guessing which
        // they have, and the fixes point in opposite directions.
        var read = new EvidenceRead([], NodesMatched: 9000, NodesRead: 4000, NeighbourLimit: 60,
            NodesAtNeighbourLimit: 17);

        Assert.Contains("were not read", read.Shortfall!, StringComparison.Ordinal);
        Assert.Contains("17 node(s) had more than 60", read.Shortfall!, StringComparison.Ordinal);
    }

    [Fact]
    public void ANodeExactlyAtTheLimitCountsAsTruncated()
    {
        // The read cannot tell "exactly 60 neighbours" from "60 of many", and guessing in the
        // flattering direction is how a cap becomes a quieter wrong number.
        var read = new EvidenceRead([], NodesMatched: 1, NodesRead: 1, NeighbourLimit: 60,
            NodesAtNeighbourLimit: 1);

        Assert.False(read.IsComplete);
        Assert.NotNull(read.Shortfall);
    }

    [Fact]
    public void ASearchIsNotBoundedByTheNeighbourCeiling()
    {
        // Find borrowed MaxNeighborsCeiling, which is 50. The workbench asked for 20,000 matches to
        // build the context and join panes and received 50 — so those panes computed crossing
        // counts, join counts and coverage from roughly three percent of a real workspace and
        // presented the result as the answer. A search returns identity columns only; its payload
        // per row is small, which is why it can have a much larger ceiling than a neighbour list.
        Assert.True(
            ProjectionService.MaxSearchResultsCeiling > ProjectionService.MaxNeighborsCeiling * 100,
            "a search ceiling within two orders of magnitude of the neighbour ceiling is the bug " +
            "this constant exists to prevent");
    }

    // ── One composition, and it routes where it says ──────────────────────────────────────

    [Fact]
    public void TheShippedCompositionRoutesEveryScopeKindToItsOwnExtractor()
    {
        // The router is four positional constructor parameters and getting their order wrong is
        // SILENT: a mis-ordered composite sent every bicep: scope to the schema extractor, both
        // failed, and the run reported a repository with no infrastructure in it. That happened, in
        // a spike, and it produced a confidently wrong write-up before anyone noticed.
        var composite = Assert.IsType<CompositeExtractor>(WorkspaceExtractors.Default());

        foreach (var (prefix, kind) in WorkspaceExtractors.RoutedKinds)
        {
            Assert.Equal(kind, composite.RouteFor(prefix + "anything").ScopeKind);
        }
    }

    [Fact]
    public void AnUnknownScopeKindFallsThroughRatherThanBeingMisrouted()
    {
        // The fallback is a real answer, not a hole: Phase 2's fixture evidence still renders beside
        // real extraction, and a scope kind this build does not know must not be quietly handed to
        // whichever extractor happens to be first.
        var composite = Assert.IsType<CompositeExtractor>(WorkspaceExtractors.Default());

        Assert.Equal("fixture", composite.RouteFor("timeline:whatever").ScopeKind);
    }

    // ── The screen, not the byte stream ───────────────────────────────────────────────────

    [Fact]
    public void TextLandsWhereTheCursorSaysItDoes_NotWhereItArrived()
    {
        // The measured shape. An agent draws with absolute addressing and repaints regions in
        // whatever order it likes, so the LAST bytes are not the BOTTOM line. Asserted through the
        // watcher rather than a screen of its own: a second model of one terminal disagrees with the
        // pane the first time either is fixed.
        var watcher = new AgentReadinessWatcher(readyPattern: "^middle$");
        watcher.Observe("\u001b[3;1Hmiddle" + "\u001b[1;1Htop");

        Assert.Contains("top", watcher.LastJudged, StringComparison.Ordinal);
        Assert.Contains("middle", watcher.LastJudged, StringComparison.Ordinal);

        // "middle" is on row 3 and "top" on row 1, so the last DRAWN line is middle — even though
        // "top" was the last thing written.
        Assert.True(watcher.IsReady);
    }

    [Fact]
    public void EscapeSequencesNeverBecomeScreenText()
    {
        // A parser that fell through to "write the bytes as text" would put escape codes into the
        // screen it models, and the readiness pattern would match text no human ever saw.
        var watcher = new AgentReadinessWatcher(readyPattern: "NEVER");
        watcher.Observe("\u001b[38;2;150;108;30mcoloured\u001b[m \u001b]0;title\adone");

        Assert.Contains("coloured done", watcher.LastJudged, StringComparison.Ordinal);
        Assert.DoesNotContain("38;2;150", watcher.LastJudged, StringComparison.Ordinal);
    }

    [Fact]
    public void TheRenderedScreenIsWhatTheUserWouldSee()
    {
        // Against the CAPTURED bytes. The dialog's text is spread across rows 3 to 17 by absolute
        // addressing, and only a screen model puts it back together.
        var watcher = new AgentReadinessWatcher(readyPattern: "NEVER");
        watcher.Observe(TrustGateOutput());

        Assert.Contains("Quick safety check", watcher.LastJudged, StringComparison.Ordinal);
        Assert.Contains("Yes, I trust this folder", watcher.LastJudged, StringComparison.Ordinal);
    }

    // ── The trust gate is a state, not a silent refusal ───────────────────────────────────

    [Fact]
    public void AnAgentWaitingOnAPersonSaysSo_AndIsNotReady()
    {
        // Measured: this gate is the NORMAL first screen, not an edge case. Reporting it as an
        // unexplained refusal is DC-011 — refusal indistinguishable from breakage.
        var watcher = AgentReadinessProfiles.BuiltIn.WatcherFor("claude")!;
        watcher.Observe(TrustGateOutput());

        Assert.True(watcher.NeedsAttention);
        Assert.Contains("trust", watcher.AttentionLine, StringComparison.OrdinalIgnoreCase);
        Assert.False(watcher.IsReady);
    }

    [Fact]
    public void AttentionOutranksAPromptLookingScreen()
    {
        // The dialog draws a chevron on its selected option. Even a marker that matches it must not
        // produce READY while a person is being asked a safety question.
        var watcher = new AgentReadinessWatcher(readyPattern: ".", attentionPattern: "trust");
        watcher.Observe("\u001b[1;1HDo you trust this folder?");

        Assert.True(watcher.NeedsAttention);
        Assert.False(watcher.IsReady);
    }

    [Fact]
    public void WithNoDialogOnScreen_ThePromptLineDecides()
    {
        var watcher = new AgentReadinessWatcher(readyPattern: "^>$", attentionPattern: "trust");
        watcher.Observe("thinking...\u001b[2;1H> ");

        Assert.False(watcher.NeedsAttention);
        Assert.True(watcher.IsReady);
    }

    // ── Crossings can be opened ───────────────────────────────────────────────────────────

    private static EvidenceAssertion Edge(string subject, string obj) =>
        new("view", "rev-1", subject, "references", obj, EvidenceOrigin.Static, VerificationStatus.Verified,
            new Provenance("test", null, "test", "1", DateTimeOffset.UnixEpoch));

    private const string TwoContextYaml =
        """
        contexts:
          - name: Editorial
            includes:
              - Ed.*
          - name: Football
            includes:
              - Fb.*
        """;

    /// <summary>Written to disk because the reader validates a FILE against the symbols found.</summary>
    private BoundedContextMap Map(IReadOnlyCollection<string> symbols)
    {
        Directory.CreateDirectory(_dir);
        var path = Path.Combine(_dir, "bounded-contexts.yaml");
        File.WriteAllText(path, TwoContextYaml);
        return BoundedContextReader.Load(path, symbols);
    }

    [Fact]
    public void ACrossingCarriesTheEdgesThatMakeIt()
    {
        // A count is not evidence. "Editorial → Football, 47 edges" is a claim about the user's code
        // that they cannot check, act on, or disagree with.
        var view = new ContextProjection(Map(["Ed.A", "Ed.B", "Fb.X", "Fb.Y"]),
            [Edge("Ed.A", "Fb.X"), Edge("Ed.B", "Fb.Y")]).Compute();

        var crossing = Assert.Single(view.Edges);
        Assert.Equal(2, crossing.Weight);
        Assert.Equal(2, crossing.Members.Count);
        Assert.Contains(crossing.Members, m => m.Subject == "Ed.A" && m.Object == "Fb.X");
        Assert.Equal(0, crossing.Undisclosed);
    }

    [Fact]
    public void TheMemberCapNeverBecomesAQuieterWrongNumber()
    {
        // The list is capped so a pane rendering thousands of rows does not stop responding. The
        // WEIGHT must stay the true total, and the difference must be stated — a cap that silently
        // truncated would turn a correct count into a confident wrong one.
        var edges = Enumerable.Range(0, ContextEdge.MemberCap + 25)
            .Select(i => Edge($"Ed.A{i}", $"Fb.X{i}"))
            .ToList();

        var map = Map([.. edges.Select(e => e.Subject), .. edges.Select(e => e.Object)]);

        var crossing = Assert.Single(new ContextProjection(map, edges).Compute().Edges);

        Assert.Equal(ContextEdge.MemberCap + 25, crossing.Weight);
        Assert.Equal(ContextEdge.MemberCap, crossing.Members.Count);
        Assert.Equal(25, crossing.Undisclosed);
    }

    // ── A predicate is a name, and two extractors gave it two meanings ────────────────────

    private static EvidenceAssertion Say(string subject, string predicate, string obj) =>
        new("view", "rev-1", subject, predicate, obj, EvidenceOrigin.Static, VerificationStatus.Verified,
            new Provenance("test", null, "test", "1", DateTimeOffset.UnixEpoch));

    [Fact]
    public void ADependsOnFromCodeIsNotReportedAsAResourceDependency()
    {
        // MEASURED on a real repository: `depends_on` is the C# extractor's predicate for type
        // dependencies — 7,426 of them — and joining on the predicate alone attached the basis
        // "declared in the resource's dependsOn" to every one. A large number with a false sentence
        // beside it, which is the most convincing kind of wrong (DC-022).
        var result = new JoinProjection([
            Say("TheTerrace.Components.Display", "depends_on", "string"),
        ]).Compute();

        Assert.DoesNotContain(result.Edges, e => e.Kind == "depends_on");
    }

    [Fact]
    public void ADependsOnBetweenDeclaredResourcesIsStillJoined()
    {
        // The other half. Narrowing a join until it can no longer fire is not a fix.
        var result = new JoinProjection([
            Say("sqlServer", "resource_type", "Microsoft.Sql/servers"),
            Say("sqlServer", "depends_on", "vnet"),
        ]).Compute();

        var edge = Assert.Single(result.Edges, e => e.Kind == "depends_on");
        Assert.Equal("sqlServer", edge.From);
        Assert.Equal("vnet", edge.To);
        Assert.Equal(VerificationStatus.Verified, edge.Status);
    }

    [Fact]
    public void AHasTypeFromTheWrongProducerIsNotConsumedAsACodeType()
    {
        // has_type is emitted by ALL THREE extractors — measured over a real repository, not assumed
        // — and its object values partition by producer only by accident. This makes the partition
        // something the code enforces: a bicep-scoped subject claiming to be a class is not joined as
        // one, whatever the object value says (DC-022's residual).
        var result = new JoinProjection([
            Say("bicep:main#Order", "has_type", "class"),
            Say("table:Order", "has_type", "table"),
        ]).Compute();

        Assert.DoesNotContain(result.Edges, e => e.Kind == "maps_to");
    }

    [Fact]
    public void ACodeTypeIsStillJoinedToItsTable()
    {
        // The other half, every time: a qualifier that also blocks the real case is not a fix.
        var result = new JoinProjection([
            Say("Shop.Sales.Order", "has_type", "class"),
            Say("table:Order", "has_type", "table"),
        ]).Compute();

        var edge = Assert.Single(result.Edges, e => e.Kind == "maps_to");
        Assert.Equal("Shop.Sales.Order", edge.From);
        Assert.Equal(VerificationStatus.Inferred, edge.Status);
    }

    [Fact]
    public void ATableSubjectMustCarryTheTablePrefix()
    {
        // A code type that happened to be described as a "table" by another extractor must not
        // become a join target. Nothing emits this today; that is exactly when a qualifier is cheap.
        var result = new JoinProjection([
            Say("Shop.Sales.Order", "has_type", "class"),
            Say("Shop.Sales.Order", "has_type", "table"),
        ]).Compute();

        Assert.DoesNotContain(result.Edges, e => e.Kind == "maps_to");
    }

    [Fact]
    public void ACrossingDominatedByOneObjectSaysWhichOne()
    {
        // Found by eye once, so now it is computed. On TheTerrace, 57 of the 72 Football-to-
        // Operations edges were AppDbContext, which made a boundary that mostly holds look like one
        // that never did. A signal a person has to notice is a signal that gets noticed once.
        var edges = Enumerable.Range(0, 9).Select(i => Edge($"Ed.A{i}", "Fb.AppDbContext"))
            .Concat([Edge("Ed.B", "Fb.Other")])
            .ToList();

        var crossing = Assert.Single(new ContextProjection(Map(
            [.. edges.Select(e => e.Subject), .. edges.Select(e => e.Object)]), edges).Compute().Edges);

        Assert.Equal("Fb.AppDbContext", crossing.DominantTarget!.Object);
        Assert.Equal(9, crossing.DominantCount);
    }

    [Fact]
    public void AnEvenlySpreadCrossingNamesNothing()
    {
        // The half that stops this becoming noise. Ordinary coupling reaches many things, and a
        // signal that fires on every crossing tells the user nothing about any of them.
        var edges = Enumerable.Range(0, 8).Select(i => Edge($"Ed.A{i}", $"Fb.X{i}")).ToList();

        var crossing = Assert.Single(new ContextProjection(Map(
            [.. edges.Select(e => e.Subject), .. edges.Select(e => e.Object)]), edges).Compute().Edges);

        Assert.Null(crossing.DominantTarget);
        Assert.Equal(0, crossing.DominantCount);
    }

    [Fact]
    public void ExactlyHalfIsNotDomination()
    {
        // "Most of this crossing is one thing" is the claim. Half is not most, and a boundary rule
        // that fires ON the boundary is the kind of detail nobody checks until it misleads someone.
        var edges = Enumerable.Range(0, 3).Select(i => Edge($"Ed.A{i}", "Fb.Shared"))
            .Concat(Enumerable.Range(0, 3).Select(i => Edge($"Ed.B{i}", $"Fb.Other{i}")))
            .ToList();

        var crossing = Assert.Single(new ContextProjection(Map(
            [.. edges.Select(e => e.Subject), .. edges.Select(e => e.Object)]), edges).Compute().Edges);

        Assert.Null(crossing.DominantTarget);
    }

    // ── Uncovered symbols become a task ───────────────────────────────────────────────────

    [Fact]
    public void UncoveredSymbolsAreRankedByNamespace_LargestFirst()
    {
        var groups = ContextProjection.GroupUncovered(
            ["A.B.One", "A.B.Two", "A.B.Three", "C.D.Only", "Bare"]);

        Assert.Equal("A.B", groups[0].Namespace);
        Assert.Equal(3, groups[0].Symbols);
        Assert.Contains("A.B.One", groups[0].Examples);
    }

    [Fact]
    public void ASymbolWithNoNamespaceIsGrouped_NotDropped()
    {
        // Silently omitting the ones that do not fit the shape is how a coverage breakdown starts
        // disagreeing with the coverage number printed beside it.
        var groups = ContextProjection.GroupUncovered(["A.B.One", "Bare"]);

        Assert.Equal(2, groups.Sum(g => g.Symbols));
        Assert.Contains(groups, g => g.Namespace == "(no namespace)");
    }
}
