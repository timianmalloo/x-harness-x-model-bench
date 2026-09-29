using System.Text.Json.Nodes;
using AiDe.Core.AgentPlane;
using AiDe.Core.Presentation.Composer;
using AiDe.Core.PromptCompilation;
using AiDe.Core.Sessions;

namespace AiDe.Core.Tests.PromptCompilation;

/// <summary>
/// ADR-0033's falsifying tests 2, 3 and 5 (the headless half) and US-D1/US-D2: the
/// <c>projection_sha</c> domain, the budget as a declared value, the task class as a decoration,
/// the pre-compile's determinism, and the one shared mention regex.
/// </summary>
public sealed class TheProjectionIsTheOneProducerTests
{
    private const string Session = "20260912T100000Z-0000aaaa";

    private static PreCompileInput Input(ComposerDraft draft, string taskClass = "free-form", PromptTemplate? template = null) =>
        new(draft, template, Session, "claude-code", CompileModes.MechanicalOnly, taskClass);

    private static ComposerDraft GoalBlockDraft(string text = "Rename the helper in @src/Payments/Money.cs.\n")
    {
        var draft = new ComposerDraft();
        draft.SwitchTo(ComposerShape.GoalBlock);
        draft.SetFreeFormText(text);
        draft.SetGoalValue(GoalBlockFields.GoalKey, "Rename the helper.");
        draft.SetGoalValue(GoalBlockFields.DoneWhenKey, "It compiles under the new name.");
        draft.SetGoalValue(GoalBlockFields.NotInScopeKey, "Nothing else changes.");
        return draft;
    }

    // ── ADR-0033 test 2: the projection_sha domain ──

    /// <summary>An <c>operator</c> <c>task_class</c> row whose value equals the session default yields a different sha — only <c>source</c> moves it.</summary>
    [Fact]
    public void AnOperatorTaskClassRowWithTheSameValueChangesTheProjectionSha()
    {
        var draft = GoalBlockDraft();
        var without = Projection.Project(PreCompile.Live(Input(draft, "free-form")));

        draft.ChooseTaskClass("free-form");
        var with = Projection.Project(PreCompile.Live(Input(draft, "free-form")));

        Assert.Equal(without.TaskClass, with.TaskClass);
        Assert.Equal(DecorationSources.SessionDefault, without.TaskClassSource);
        Assert.Equal(DecorationSources.Operator, with.TaskClassSource);
        Assert.NotEqual(without.ProjectionSha, with.ProjectionSha);

        // And a different class moves it again.
        draft.ChooseTaskClass("refactor");
        Assert.NotEqual(with.ProjectionSha, Projection.Project(PreCompile.Live(Input(draft, "free-form"))).ProjectionSha);
    }

    [Fact]
    public void TheShaMovesWithEveryMemberOfItsDomainAndWithNothingElse()
    {
        var baseline = Projection.Project(PreCompile.Live(Input(GoalBlockDraft()))).ProjectionSha;

        // A structure line.
        var edited = GoalBlockDraft();
        edited.SetGoalValue(GoalBlockFields.NotInScopeKey, "Nothing else changes, and the ADR.");
        Assert.NotEqual(baseline, Projection.Project(PreCompile.Live(Input(edited))).ProjectionSha);

        // The source text (a different mention: the lease and sha256(source_text) both move).
        Assert.NotEqual(baseline, Projection.Project(PreCompile.Live(Input(GoalBlockDraft("Rename the helper in @src/Orders/Money.cs.\n")))).ProjectionSha);

        // The tier override.
        var overridden = GoalBlockDraft();
        overridden.OverrideTier("T2");
        Assert.NotEqual(baseline, Projection.Project(PreCompile.Live(Input(overridden))).ProjectionSha);

        // The ceilings (fan-out) and the budget cap.
        var ceiling = GoalBlockDraft();
        ceiling.UseSessionSettings(new SessionConfig(Session, "n", "w", DateTimeOffset.UnixEpoch, [new AccountRef("anthropic", "max")], new AccountRef("anthropic", "max")) { FanOutCeiling = 1 });
        Assert.NotEqual(baseline, Projection.Project(PreCompile.Live(Input(ceiling))).ProjectionSha);
        var capped = GoalBlockDraft();
        capped.UseSessionSettings(new SessionConfig(Session, "n", "w", DateTimeOffset.UnixEpoch, [new AccountRef("anthropic", "max")], new AccountRef("anthropic", "max")) { BudgetCap = new RunBudget(250, 600_000) });
        Assert.NotEqual(baseline, Projection.Project(PreCompile.Live(Input(capped))).ProjectionSha);

        // An attachment BY REFERENCE moves it; its body does not (bodies are never in the domain).
        var attached = GoalBlockDraft();
        attached.Add(new ComposerAttachment("notes.md", "C:/repo/notes.md", 5, "hello", false, "sha-a"));
        var withA = Projection.Project(PreCompile.Live(Input(attached))).ProjectionSha;
        Assert.NotEqual(baseline, withA);
        var sameRefOtherBody = GoalBlockDraft();
        sameRefOtherBody.Add(new ComposerAttachment("notes.md", "C:/repo/notes.md", 5, "WORLD", false, "sha-a"));
        Assert.Equal(withA, Projection.Project(PreCompile.Live(Input(sameRefOtherBody))).ProjectionSha);

        // The same draft twice: the same sha (no clock, no id in the domain).
        Assert.Equal(baseline, Projection.Project(PreCompile.Live(Input(GoalBlockDraft()))).ProjectionSha);
    }

    /// <summary>
    /// The domain, one member at a time (the Test Architect's condition): each of the twelve
    /// members of §A12.2's <c>projection_sha</c> moves the sha when it alone changes — so a mutation
    /// dropping any one member from the canonical array cannot survive.
    /// </summary>
    public static TheoryData<string, Func<Args, Args>> Members() => new()
    {
        { "goal", a => a with { Goal = "other" } },
        { "done_when", a => a with { DoneWhen = "other" } },
        { "not_in_scope", a => a with { NotInScope = "other" } },
        { "tier", a => a with { Tier = "T2" } },
        { "fan_out_cap", a => a with { FanOutCap = 3 } },
        { "budget", a => a with { Budget = new RunBudget(1, 2) } },
        { "exclusive", a => a with { Exclusive = ["src/B/**"] } },
        { "source_text", a => a with { SourceText = "other text" } },
        { "family_profile", a => a with { FamilyProfile = JsonNode.Parse("{\"family\":\"openai\",\"version\":null,\"sha\":null}") } },
        { "attachments", a => a with { Attachments = JsonNode.Parse("[{\"path\":\"y\",\"sha256\":\"b\"}]") } },
        { "task_class", a => a with { TaskClass = "defect" } },
        { "task_class_source", a => a with { TaskClassSource = DecorationSources.Operator } },
    };

    public sealed record Args(
        string? Goal, string? DoneWhen, string? NotInScope, string Tier, int FanOutCap, RunBudget Budget,
        IReadOnlyList<string> Exclusive, string SourceText, JsonNode? FamilyProfile, JsonNode? Attachments, string TaskClass, string TaskClassSource)
    {
        public static readonly Args Baseline = new(
            "g", "d", "n", "T1", 2, RunBudget.SubscriptionBounded, ["src/A/**"], "text",
            JsonNode.Parse("{\"family\":\"anthropic\",\"version\":null,\"sha\":null}"),
            JsonNode.Parse("[{\"path\":\"x\",\"sha256\":\"a\"}]"),
            "free-form", DecorationSources.SessionDefault);

        public string Sha() => Projection.ProjectionSha(Goal, DoneWhen, NotInScope, Tier, FanOutCap, Budget, Exclusive, SourceText, FamilyProfile, Attachments, TaskClass, TaskClassSource);
    }

    [Theory]
    [MemberData(nameof(Members))]
    public void EachMemberOfTheShaDomainMovesTheShaAlone(string member, Func<Args, Args> vary)
    {
        var baseline = Args.Baseline.Sha();
        Assert.NotEqual(baseline, vary(Args.Baseline).Sha());
        Assert.Equal(baseline, Args.Baseline.Sha());   // deterministic
        Assert.NotNull(member);
    }

    /// <summary>§A9: a mechanical structure row is a template's only when its inputs name the template writer; an unnamed mechanical writer reads <i>not recorded</i>, never a plausible "template".</summary>
    [Fact]
    public void AMechanicalStructureRowWithNoTemplateWriterReadsNotRecorded()
    {
        var events = new List<EnvelopeEvent>
        {
            new Opened("e", "text", Session, "claude-code", CompileModes.MechanicalOnly, null, PreCompile.ConstantsFor("1")),
            new Decorated("e", DecorationNames.Ceilings, new JsonObject { ["fan_out"] = 3, ["budget"] = null }, DecorationSources.Mechanical),
            new Decorated("e", DecorationNames.TaskClass, JsonValue.Create("free-form"), DecorationSources.SessionDefault),
            new Decorated("e", DecorationNames.Goal, JsonValue.Create("g"), DecorationSources.Mechanical),
            new Decorated("e", DecorationNames.DoneWhen, JsonValue.Create("d"), DecorationSources.Mechanical),
        };

        var unnamed = Projection.Project(Envelope.Pending(events));
        Assert.Equal(Envelope.NotRecorded, unnamed.StructureSource);
        Assert.Equal("goal block filled by an unnamed writer, no write scope", unnamed.Rationale);

        var named = events.Select(e => e is Decorated { Source: DecorationSources.Mechanical, Name: DecorationNames.Goal or DecorationNames.DoneWhen } d
            ? d with { Inputs = [new DecorationInput(PreCompile.TemplateWriter, "goal-block", "1")] }
            : e).ToList();
        Assert.Equal(StructureSources.Template, Projection.Project(Envelope.Pending(named)).StructureSource);
    }

    /// <summary>DM11 (b): the paired test — render Prepare from a fold, submit the same fold, the GoalBlock is equal.</summary>
    [Fact]
    public void TheRenderAndTheSubmitReadOneProjection()
    {
        var draft = GoalBlockDraft("touch @src/A/ and @src/B/\n");
        draft.OverrideTier("T1");
        var envelope = PreCompile.Live(Input(draft, "refactor"));

        var rendered = Projection.Project(envelope);
        var submitted = Projection.Project(envelope, draft);
        var rows = ComposerCompiler.Decorations(rendered, draft);

        Assert.Equal(rendered.GoalBlock, submitted.GoalBlock);
        Assert.Equal(rendered.ProjectionSha, submitted.ProjectionSha);
        Assert.Equal(rendered.Tier, rows.Single(r => r.Name == "tier").Value);
        Assert.Equal("refactor", rows.Single(r => r.Name == "class").Value);
        Assert.Equal("src/A/** · src/B/**", rows.Single(r => r.Name == "lease").Value);
        Assert.Equal("goal block", rows.Single(r => r.Name == "shape").Value);

        // The rendered prompt carries the OVERRIDDEN tier — the projection's block, not a second one.
        Assert.Contains("## tier\n\nT1\n", submitted.Prompt, StringComparison.Ordinal);
        Assert.Equal(EnvelopeHash.Sha256Hex(submitted.Prompt!), submitted.TextSha256);
        Assert.Null(rendered.Prompt);   // the offline rebuild has no held bodies
    }

    // ── ADR-0033 test 3: budget ──

    [Fact]
    public void ASessionWithNoCapProjectsSubscriptionBoundedAndTheCompiledBlockCarriesNeitherNumeral()
    {
        var draft = GoalBlockDraft();
        var p = Projection.Project(PreCompile.Live(Input(draft)), draft);

        Assert.True(p.Budget.IsSubscriptionBounded);
        Assert.Empty(SpawnContract.Validate(p.GoalBlock));
        Assert.DoesNotContain(int.MaxValue.ToString(System.Globalization.CultureInfo.InvariantCulture), p.Prompt, StringComparison.Ordinal);
        Assert.DoesNotContain(long.MaxValue.ToString(System.Globalization.CultureInfo.InvariantCulture), p.Prompt, StringComparison.Ordinal);
        Assert.Contains(RunBudget.SubscriptionBoundedDisplay, p.Prompt, StringComparison.Ordinal);

        // The ceilings row folded to a null budget.
        var row = PreCompile.Live(Input(draft)).Current(DecorationNames.Ceilings)!;
        Assert.Null(row.Value!["budget"]);
        Assert.Equal(PreCompile.CeilingsWriter, row.Inputs!.Single().Writer);
    }

    [Fact]
    public void ACapProjectsExactlyAndAFoldWhoseCeilingsRowLacksTheMemberIsIncomplete()
    {
        var draft = GoalBlockDraft();
        draft.UseSessionSettings(new SessionConfig(Session, "n", "w", DateTimeOffset.UnixEpoch, [new AccountRef("anthropic", "max")], new AccountRef("anthropic", "max")) { BudgetCap = new RunBudget(250, 600_000) });
        Assert.Equal(new RunBudget(250, 600_000), Projection.Project(PreCompile.Live(Input(draft))).Budget);

        // A row lacking `budget` is not a snapshot: the fold is incomplete and Project refuses, never defaults.
        var events = PreCompile.Open(Input(draft), "e")
            .Select(e => e is Decorated { Name: DecorationNames.Ceilings } ? new Decorated("e", DecorationNames.Ceilings, new JsonObject { ["fan_out"] = 3 }, DecorationSources.Mechanical) : e)
            .ToList();
        var incomplete = Assert.Throws<EnvelopeStoreException>(() => Projection.Project(Envelope.Pending(events)));
        Assert.Equal(EnvelopeStoreErrorCodes.ProjectionIncomplete, incomplete.Code);

        // A fresh row appended after it is what the fold reads (Current = highest seq).
        events.Add(new Decorated("e", DecorationNames.Ceilings, new JsonObject { ["fan_out"] = 3, ["budget"] = null }, DecorationSources.Mechanical));
        Assert.True(Projection.Project(Envelope.Pending(events)).Budget.IsSubscriptionBounded);
    }

    [Fact]
    public void AFoldWithNoOpenedRowOrNoTaskClassRowIsIncomplete()
    {
        var noOpened = Assert.Throws<EnvelopeStoreException>(() => Projection.Project(Envelope.Pending([new Decorated("e", "goal", JsonValue.Create("g"), DecorationSources.Operator)])));
        Assert.Equal(EnvelopeStoreErrorCodes.ProjectionIncomplete, noOpened.Code);

        var events = PreCompile.Open(Input(GoalBlockDraft()), "e").Where(e => e is not Decorated { Name: DecorationNames.TaskClass }).ToList();
        var noClass = Assert.Throws<EnvelopeStoreException>(() => Projection.Project(Envelope.Pending(events)));
        Assert.Equal(EnvelopeStoreErrorCodes.ProjectionIncomplete, noClass.Code);
    }

    // ── ADR-0033 test 5: task class ──

    [Fact]
    public void ANewSessionWithNothingChosenProjectsFreeFormWithSourceSessionDefault_AndAPerPromptChoiceReachesThatPromptOnly()
    {
        var draft = GoalBlockDraft();
        var defaulted = Projection.Project(PreCompile.Live(Input(draft, AiDe.Core.Watcher.TaskClasses.FreeForm)));
        Assert.Equal(AiDe.Core.Watcher.TaskClasses.FreeForm, defaulted.TaskClass);
        Assert.Equal(DecorationSources.SessionDefault, defaulted.TaskClassSource);
        Assert.True(new AiDe.Core.Watcher.ScoreSegment(AiDe.Core.Watcher.WorkspaceKey.From("C:/repo"), defaulted.TaskClass, "weave/1").IsComparable);

        draft.ChooseTaskClass("refactor");
        var chosen = Projection.Project(PreCompile.Live(Input(draft, AiDe.Core.Watcher.TaskClasses.FreeForm)));
        Assert.Equal("refactor", chosen.TaskClass);
        Assert.Equal(DecorationSources.Operator, chosen.TaskClassSource);

        // The default stays: the next prompt (a fresh draft) is free-form again.
        Assert.Equal(AiDe.Core.Watcher.TaskClasses.FreeForm, Projection.Project(PreCompile.Live(Input(GoalBlockDraft(), AiDe.Core.Watcher.TaskClasses.FreeForm))).TaskClass);
    }

    // ── US-D2: the pre-compile is pure, total and deterministic ──

    [Fact]
    public void ThePreCompileRunTwiceYieldsByteIdenticalMechanicalPayloads()
    {
        static string Canonical(IEnumerable<EnvelopeEvent> events) =>
            string.Join("\n", events.OfType<Decorated>().Select(d => $"{d.Name}|{d.Value?.ToJsonString() ?? "null"}|{d.Source}"));

        var draft = GoalBlockDraft();
        draft.Add(new ComposerAttachment("notes.md", "C:/repo/notes.md", 5, "hello", false, "sha-a"));

        var first = PreCompile.Open(Input(draft), "e1");
        var second = PreCompile.Open(Input(draft), "e2");

        Assert.Equal(Canonical(first), Canonical(second));
        Assert.All(first, e => Assert.Null(e.At));   // no clock in a value: the store stamps `at`, not the pre-compile
        Assert.Equal(
            [DecorationNames.Ceilings, DecorationNames.TaskClass, DecorationNames.FamilyProfile, DecorationNames.TemplateApplied, DecorationNames.Attachments, DecorationNames.Goal, DecorationNames.DoneWhen, DecorationNames.NotInScope],
            first.OfType<Decorated>().Select(d => d.Name));

        // US-D1: nothing named lease, shape, fan_out_effective, or a rule-computed tier.
        Assert.DoesNotContain(first.OfType<Decorated>(), d => d.Name is "lease" or "shape" or "fan_out_effective" || (d.Name == DecorationNames.Tier && d.Source != DecorationSources.Operator));
    }

    [Fact]
    public void AnUnknownEngineYieldsFamilyNotRecordedNeverAnException()
    {
        var draft = GoalBlockDraft();
        var events = PreCompile.Open(new PreCompileInput(draft, null, Session, "no-such-engine", CompileModes.MechanicalOnly, "free-form"), "e");
        var family = events.OfType<Decorated>().Single(d => d.Name == DecorationNames.FamilyProfile).Value!;
        Assert.Equal(Envelope.NotRecorded, family["family"]!.GetValue<string>());
        Assert.Null(family["version"]);
        Assert.Null(family["sha"]);

        // A known engine names its provider; the profile is `none` until the pack ships one (ADR-0037 read, not populated).
        var known = PreCompile.Open(Input(draft), "e").OfType<Decorated>().Single(d => d.Name == DecorationNames.FamilyProfile).Value!;
        Assert.Equal("anthropic", known["family"]!.GetValue<string>());
        Assert.Null(known["version"]);
    }

    // ── the one shared mention regex (ADR-0033 rule 1; C-Lease) ──

    [Fact]
    public void HasMentionAndPatternsShareOneRegexInstance()
    {
        // EXACTLY ONE Regex lives in LeaseDerivation (the sharing proof: a private copy for HasMention
        // would be a second field), and the validator owns no Regex of its own (a census over its source).
        var regexFields = typeof(LeaseDerivation)
            .GetFields(System.Reflection.BindingFlags.NonPublic | System.Reflection.BindingFlags.Public | System.Reflection.BindingFlags.Static)
            .Where(f => f.FieldType == typeof(System.Text.RegularExpressions.Regex))
            .ToList();
        Assert.Single(regexFields);
        Assert.Same(regexFields[0].GetValue(null), LeaseDerivation.MentionRegex);
        var validatorSource = File.ReadAllText(Path.Combine(RepoRoot(), "src", "AiDe.Core", "Compilation", "CompileOutputValidator.cs"));
        Assert.DoesNotContain("Regex", validatorSource, StringComparison.Ordinal);
        Assert.Contains("LeaseDerivation.HasMention(", validatorSource, StringComparison.Ordinal);
        Assert.True(LeaseDerivation.HasMention("read @src/x.cs"));
        Assert.True(LeaseDerivation.HasMention("@../x"));            // a token, even where Patterns drops it: the scan refuses, never widens
        Assert.False(LeaseDerivation.HasMention("read src/x.cs"));
        Assert.False(LeaseDerivation.HasMention("mail me at bob＠example"));   // fullwidth ＠ is no mention either way
        Assert.False(LeaseDerivation.HasMention("@ src/x"));         // `@` followed by whitespace matches nothing

        // The regex that HasMention answers with is the one Patterns matches with: every text
        // Patterns finds a mention in, HasMention finds one in; every text with none, none.
        foreach (var text in new[] { "@src/A/", "touch @src/a.cs @src/b.cs", "no mention", "email@host", "@*", "@." })
        {
            Assert.Equal(LeaseDerivation.MentionRegex.IsMatch(text), LeaseDerivation.HasMention(text));
        }

        // The only members that take a string: Patterns, Derive (public) and HasMention (internal).
        var methods = typeof(LeaseDerivation).GetMethods(System.Reflection.BindingFlags.Public | System.Reflection.BindingFlags.NonPublic | System.Reflection.BindingFlags.Static | System.Reflection.BindingFlags.DeclaredOnly)
            .Where(m => m.GetParameters().Length == 1 && m.GetParameters()[0].ParameterType == typeof(string) && !m.IsSpecialName)
            .Select(m => (m.Name, m.IsPublic))
            .Order()
            .ToList();
        Assert.Equal([("Derive", true), ("HasMention", false), ("Patterns", true), ("ToPattern", false)], methods);
    }

    private static string RepoRoot()
    {
        var dir = new DirectoryInfo(AppContext.BaseDirectory);
        while (dir is not null && !File.Exists(Path.Combine(dir.FullName, "AiDe.sln")))
        {
            dir = dir.Parent;
        }

        Assert.NotNull(dir);
        return dir!.FullName;
    }
}
