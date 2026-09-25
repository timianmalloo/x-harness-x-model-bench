using AiDe.Core.AgentPlane;
using AiDe.Core.Presentation.Composer;
using AiDe.Core.Sessions;
using AiDe.Core.Tests.Sessions;

namespace AiDe.Core.Tests.Composer;

/// <summary>
/// The F4 clauses whose subject is a <b>document, a piece of copy, or the absence of a code path</b>
/// — each of which is still a clause with an oracle, and each of which is easiest to leave unchecked.
/// </summary>
/// <remarks>
/// <b>These are the ones that quietly become prose.</b> "Nothing describes the caps as a ceiling on a
/// run", "no Phase-1 code reads the locale", "the provider record exists" — every one of them reads
/// as satisfied by intention, and none of them is until something re-reads the tree.
/// </remarks>
public sealed class ThePrivacyResidualsAreCoveredTests
{
    private static IEnumerable<string> ComposerSources() =>
        Directory.EnumerateFiles(
                Path.Combine(RepoFiles.Root(), "src", "AiDe.Core", "Presentation", "Composer"), "*.cs")
            .Concat(Directory.EnumerateFiles(
                Path.Combine(RepoFiles.Root(), "src", "AiDe.App", "Workbench", "Composer"), "*.cs"))
            .Concat([Path.Combine(RepoFiles.Root(), "src", "AiDe.App", "Web", "composer.mjs")])
            .Concat([Path.Combine(RepoFiles.Root(), "src", "AiDe.App", "Web", "composer.html")]);

    [Fact]
    public void Blocker1_TheConductorProviderRecordAndItsSupersessionExist()
    {
        // Privacy's veto was on "a document that does not exist and a .gitignore line that does not
        // exist". It is a document, not code, and it changes nothing in F4's design — which is
        // precisely why nothing in the build would have noticed its absence.
        var record = Path.Combine(RepoFiles.Root(), "docs", "security", "conductor-privacy-review.md");
        Assert.True(File.Exists(record), $"the conductor provider record is not at {record}");

        var text = File.ReadAllText(record);

        Assert.Contains("## Supersession", text, StringComparison.Ordinal);
        Assert.Contains("privacy-review-ai-native-ide", text, StringComparison.Ordinal);

        // Gate 4's eight fields, each present as a row rather than as an intention.
        foreach (var field in new[]
                 {
                     "Purpose / basis", "Permitted data classes", "Processor / subprocessor role",
                     "Residency / transfer mechanism", "Training posture", "Retention",
                     "Deletion / rights path", "Repository-policy authorization",
                 })
        {
            Assert.Contains(field, text, StringComparison.Ordinal);
        }

        // Row 2 names THREE data classes, not two — the third being what the agent itself reads and
        // forwards during a run, which no C14 cap bounds.
        Assert.Contains("Three classes leave this machine, not two", text, StringComparison.Ordinal);
    }

    [Fact]
    public void TheCapsAreNeverDescribedAsACeilingOnWhatARunSends()
    {
        // The caps ceiling the ATTACH path only. The agent's own file reads are unbounded by them, so
        // any copy presenting 32 KiB / 128 KiB / 5 files as a limit on a run's egress would be a wrong
        // ceiling — which is worse than a named absence.
        var policy = RepoFiles.SourceFile("src", "AiDe.Core", "Presentation", "Composer", "AttachmentPolicy.cs");

        Assert.Contains("bound the ATTACH path only, never what a RUN sends", policy, StringComparison.Ordinal);

        foreach (var path in ComposerSources())
        {
            var text = File.ReadAllText(path);
            Assert.DoesNotContain("data budget", text, StringComparison.OrdinalIgnoreCase);
        }
    }

    [Fact]
    public void NoPhase1CodeReadsTheLocaleTheTimezoneOrTheOsRegionForAResidencyPurpose()
    {
        // Deriving residency from a machine signal would write a FABRICATED value into a record whose
        // rule is "unknown fields fail closed" — and a fabricated value does not fail closed, it
        // passes. The cheapest privacy control is not collecting it.
        foreach (var path in Directory.EnumerateFiles(
                     Path.Combine(RepoFiles.Root(), "src"), "*.cs", SearchOption.AllDirectories))
        {
            if (path.Contains($"{Path.DirectorySeparatorChar}obj{Path.DirectorySeparatorChar}", StringComparison.Ordinal)
                || path.Contains($"{Path.DirectorySeparatorChar}bin{Path.DirectorySeparatorChar}", StringComparison.Ordinal))
            {
                continue;
            }

            var text = File.ReadAllText(path);
            Assert.DoesNotContain("RegionInfo", text, StringComparison.Ordinal);
            Assert.DoesNotContain("TimeZoneInfo.Local", text, StringComparison.Ordinal);
        }

        foreach (var path in ComposerSources())
        {
            var text = File.ReadAllText(path);
            Assert.DoesNotContain("CurrentCulture", text, StringComparison.Ordinal);
            Assert.DoesNotContain("CurrentUICulture", text, StringComparison.Ordinal);
            Assert.DoesNotContain("navigator.language", text, StringComparison.Ordinal);
            Assert.DoesNotContain("timeZone", text, StringComparison.Ordinal);
        }
    }

    [Fact]
    public void NoAssistPathExistsAnywhereInTheComposer()
    {
        // R20 and R21 are Phase 3. "An assist call is made" is a clause on two of F4's own bullets,
        // and the honest oracle for a call that must not happen is that there is nothing to call.
        foreach (var path in ComposerSources())
        {
            var text = File.ReadAllText(path);

            Assert.DoesNotContain("Assist", text, StringComparison.Ordinal);
            Assert.DoesNotContain("Promote", text, StringComparison.Ordinal);
            Assert.DoesNotContain("Suggest", text, StringComparison.Ordinal);
        }
    }

    [Fact]
    public void S1_NoTemplateCodeRunsOnAFreeFormSend()
    {
        // A template whose body is a marker: if ANY template code ran, the marker would be in the
        // output. Passing it alongside a free-form draft is the strongest available form of "no
        // template code executes" short of instrumenting the compiler.
        var booby = new PromptTemplate(
            "booby-trap", 1, "intent", "audience", "when", "why", null,
            [new TemplateField("anything", TemplateFieldType.Text, Required: true, null, null)],
            "TEMPLATE-CODE-RAN {{anything}}\n",
            new Dictionary<string, string>());

        var draft = new ComposerDraft();
        draft.SetFreeFormText("a free-form prompt about @src/Payments\n");

        Assert.Empty(ComposerFormEngine.Validate(draft, booby));

        var compiled = ComposerCompiler.Compile(draft, booby);
        Assert.Equal("a free-form prompt about @src/Payments\n", compiled.Text);
        Assert.DoesNotContain("TEMPLATE-CODE-RAN", compiled.Text, StringComparison.Ordinal);
    }

    [Fact]
    public void TheApiKeyExceptionIsNotReachableAtAllInPhase1()
    {
        // The residual is "the API-key exception is enabled while attach is enabled and the record
        // covers only the subscription tier". In Phase 1 the exception cannot be enabled: a direct-API
        // spawn is refused by the terms-of-service gate whenever a subscription account exists, and
        // that refusal is checked FIRST so no other error can mask it.
        var registry = new ProviderRegistry(
        [
            new ProviderRow(
                ProviderRegistry.AnthropicProviderId,
                ProviderAuth.Subscription,
                [new ProviderAccount("max-personal", AccountHealth.Ready, null)]),
        ]);

        var error = Assert.Throws<AgentPlaneException>(() => SpawnContract.Authorize(
            new SpawnRequest(
                new GoalBlock("g", "d", "n", "T1", 0, new RunBudget(10, 1000)),
                ProviderRegistry.DirectApiEngineId,
                "sonnet",
                "api-key",
                new ObservedAuthStatus(ObservedAuthStatus.AccountKind, "max", "Claude Max")),
            registry));

        Assert.Equal(AgentPlaneErrorCodes.DirectApiRefusedByToS, error.Code);
    }
}
