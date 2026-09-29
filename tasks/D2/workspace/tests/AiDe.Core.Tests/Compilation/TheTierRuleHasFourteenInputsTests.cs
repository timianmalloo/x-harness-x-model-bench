using System.Text.Json.Nodes;
using AiDe.Core.AgentPlane;
using AiDe.Core.Presentation.Composer;
using AiDe.Core.PromptCompilation;
using AiDe.Core.Sessions;

namespace AiDe.Core.Tests.PromptCompilation;

/// <summary>
/// P-D1 (US-D3): the fourteen enumerated inputs of Addendum D §A9, each asserting
/// <c>(tier, rationale)</c> against <see cref="Projection.Project"/> — the structure-bearing ones
/// (6)–(12) three times, with the structure filled by the operator, by a template and by a fake
/// deriver, asserting <c>structure_source</c>. Red first: no projection over a fold existed.
/// </summary>
public sealed class TheTierRuleHasFourteenInputsTests
{
    private const string Session = "20260912T100000Z-0000aaaa";

    /// <summary>A fold with the structure filled by <paramref name="by"/>, over <paramref name="text"/>.</summary>
    private static Envelope Fold(string text, string? goal, string? doneWhen, string by = StructureSources.Operator, string? tierOverride = null)
    {
        // A derived row exists only under an agentic rung (no call is made under mechanical-only),
        // so the fixture opens the envelope in the mode the product would.
        var events = new List<EnvelopeEvent>
        {
            new Opened("e", text, Session, "claude-code", by == StructureSources.Derived ? CompileModes.Agentic : CompileModes.MechanicalOnly, null, PreCompile.ConstantsFor("1")),
            new Decorated("e", DecorationNames.Ceilings, new JsonObject { ["fan_out"] = 3, ["budget"] = null }, DecorationSources.Mechanical),
            new Decorated("e", DecorationNames.TaskClass, JsonValue.Create("free-form"), DecorationSources.SessionDefault),
        };

        void Line(string name, string? value)
        {
            if (value is null) return;
            events.Add(by switch
            {
                StructureSources.Derived => new Decorated("e", name, JsonValue.Create(value), DecorationSources.Derived) { CallSeq = 1, Confidence = 0.8 },
                StructureSources.Template => new Decorated("e", name, JsonValue.Create(value), DecorationSources.Mechanical) { Inputs = [new DecorationInput(PreCompile.TemplateWriter, "goal-block", "1")] },
                _ => new Decorated("e", name, JsonValue.Create(value), DecorationSources.Operator),
            });
        }

        Line(DecorationNames.Goal, goal);
        Line(DecorationNames.DoneWhen, doneWhen);
        if (tierOverride is not null)
        {
            events.Add(new Decorated("e", DecorationNames.Tier, JsonValue.Create(tierOverride), DecorationSources.Operator));
        }

        return Envelope.Pending(events);
    }

    // (1)–(5): R0 — no goal block, whatever the mentions.
    [Theory]
    [InlineData("", null, null)]                                                       // (1) empty text
    [InlineData("look at @src/A/ and @src/B/ and @docs/plan.md", null, null)]          // (2) prose, no structure, three mentions
    [InlineData("touch @src/A/", "a goal", null)]                                      // (3) goal filled, done_when blank
    [InlineData("touch @src/A/", null, "done")]                                        // (4) goal blank, done_when filled
    [InlineData("touch @src/A/", "   ", "\t")]                                         // (5) both whitespace-only
    public void R0_NoGoalBlockIsT0WhateverItMentions(string text, string? goal, string? doneWhen)
    {
        var p = Projection.Project(Fold(text, goal, doneWhen));

        Assert.Equal(("T0", "no goal block", "R0"), (p.Tier, p.Rationale, p.Rule));
        Assert.Equal("message", p.Shape);
        Assert.Equal(0, p.FanOutCap);
        Assert.Null(p.GoalBlock);
        Assert.True(p.IsReadOnly);
        Assert.Equal(string.Empty, p.StructureSource);
    }

    /// <summary>(6)–(12), each three times: by the operator, by a template, by a fake deriver.</summary>
    public static TheoryData<int, string, string, string, string> StructureBearing()
    {
        var data = new TheoryData<int, string, string, string, string>();
        var cases = new (int N, string Text, string Tier, string Rule, string Leases)[]
        {
            (6, "do the thing", "T1", "R1", "no write scope"),                       // both filled, no mention
            (7, "do it in @../x", "T1", "R1", "no write scope"),                     // @../x only → dropped → L = 0
            (8, "do it in @src/*.cs", "T1", "R1", "no write scope"),                 // a wildcard mention → dropped → L = 0
            (9, "touch @src/A/", "T1", "R2", "one lease"),                           // one directory
            (10, "touch @src/a.cs @src/a.cs", "T1", "R2", "one lease"),              // the same file twice → L = 1
            (11, "touch @src/A/ @src/A/ @src/B/", "T2", "R3", "2 leases"),           // de-duplicated → L = 2
            (12, "touch @src/a.cs @src/b.cs", "T2", "R3", "2 leases"),               // two files
        };

        foreach (var (n, text, tier, rule, leases) in cases)
        {
            foreach (var by in new[] { StructureSources.Operator, StructureSources.Template, StructureSources.Derived })
            {
                data.Add(n, text, by, tier, $"goal block filled by {Word(by)}, {leases}");
            }
        }

        return data;

        static string Word(string by) => by switch
        {
            StructureSources.Derived => "the model",
            StructureSources.Template => "the template",
            _ => "you",
        };
    }

    [Theory]
    [MemberData(nameof(StructureBearing))]
    public void R1ToR3_AGoalBlockIsTieredByItsDistinctLeases_AndTheRationaleNamesWhoFilledIt(int input, string text, string by, string tier, string rationale)
    {
        var p = Projection.Project(Fold(text, "a goal", "done", by));

        Assert.Equal(tier, p.Tier);
        Assert.Equal(rationale, p.Rationale);
        Assert.Equal(by, p.StructureSource);
        Assert.Equal("goal block", p.Shape);
        Assert.NotNull(p.GoalBlock);
        Assert.Equal(tier, p.GoalBlock!.Tier);
        Assert.Equal(Math.Min(ComposerCompiler.CapOf(tier), 3), p.FanOutCap);
        Assert.True(input is >= 6 and <= 12);

        // Lease ≠ tier, but a goal block WITH a lease is a write: (9)–(12) derive one, (6)–(8) none.
        if (p.Rule == "R1")
        {
            Assert.True(p.IsReadOnly);
        }
        else
        {
            Assert.NotNull(p.Lease);
            Assert.Equal(p.Patterns, p.Lease!.Exclusive);
        }
    }

    /// <summary>(13): R2 then an operator override to T2 → R4 with <c>source: operator</c> and <i>operator (rule said T1)</i>.</summary>
    [Fact]
    public void R4_AnOperatorOverrideReplacesTheRulesValueAndSaysWhatTheRuleSaid()
    {
        var before = Projection.Project(Fold("touch @src/A/", "a goal", "done"));
        Assert.Equal(("T1", "R2"), (before.Tier, before.Rule));

        var p = Projection.Project(Fold("touch @src/A/", "a goal", "done", tierOverride: "T2"));

        Assert.Equal(("T2", "operator (rule said T1)", "R4"), (p.Tier, p.Rationale, p.Rule));
        Assert.Equal("T2", p.GoalBlock!.Tier);

        // The cap is COMPUTED from the override, never read from a stored row: min(cap(T2) = 4, ceiling 3).
        Assert.Equal(3, p.FanOutCap);
    }

    /// <summary>(14): an override to <c>T9</c> is refused — at the draft, and at the store — and the prior row stands.</summary>
    [Fact]
    public void R4_AnOverrideOutsideTheThreeTiersIsRefusedAndThePriorRowStands()
    {
        var draft = new ComposerDraft();
        Assert.Throws<ArgumentOutOfRangeException>(() => draft.OverrideTier("T9"));
        Assert.Null(draft.TierOverride);
        draft.OverrideTier("T2");
        Assert.Throws<ArgumentOutOfRangeException>(() => draft.OverrideTier("T3"));
        Assert.Equal("T2", draft.TierOverride);

        // A T9 row that somehow reached a fold is not an override: the rule's value stands.
        var p = Projection.Project(Fold("touch @src/A/", "a goal", "done", tierOverride: "T9"));
        Assert.Equal(("T1", "R2"), (p.Tier, p.Rule));
    }

    /// <summary>US-D3 b4: a T2 tier and a ceiling of 0 → cap 0, and the settings line says so without the word <i>limit</i>.</summary>
    [Fact]
    public void ATwoTierUnderACeilingOfZeroProjectsACapOfZero()
    {
        var events = Fold("touch @src/a.cs @src/b.cs", "a goal", "done").Events
            .Select(e => e is Decorated { Name: DecorationNames.Ceilings } ? new Decorated("e", DecorationNames.Ceilings, new JsonObject { ["fan_out"] = 0, ["budget"] = null }, DecorationSources.Mechanical) : e)
            .ToList();

        var p = Projection.Project(Envelope.Pending(events));

        Assert.Equal("T2", p.Tier);
        Assert.Equal(0, p.FanOutCap);
        var line = ComposerCompiler.SettingsLine(p.Tier, p.FanOutCeiling, null);
        Assert.StartsWith("fan-out cap 0 (ceiling 0)", line, StringComparison.Ordinal);
        Assert.DoesNotContain("limit", line, StringComparison.OrdinalIgnoreCase);
    }

    /// <summary>Under <c>agentic-advisory</c> an unkept derived line is blank for the shape, P and the block at once (Confirmed()).</summary>
    [Fact]
    public void UnderAdvisoryAnUnkeptDerivedLineIsBlankForTheShapeTheTierAndTheBlock()
    {
        var events = Fold("touch @src/A/", "a goal", "done", StructureSources.Derived).Events
            .Select(e => e is Opened o ? o with { CompileMode = CompileModes.AgenticAdvisory } : e)
            .ToList();
        var p = Projection.Project(Envelope.Pending(events));

        Assert.Equal(("T0", "R0"), (p.Tier, p.Rule));
        Assert.Equal("message", p.Shape);
        Assert.Null(p.GoalBlock);

        // The same lines KEPT (an operator row with the same value) project.
        events.Add(new Decorated("e", DecorationNames.Goal, JsonValue.Create("a goal"), DecorationSources.Operator));
        events.Add(new Decorated("e", DecorationNames.DoneWhen, JsonValue.Create("done"), DecorationSources.Operator));
        var kept = Projection.Project(Envelope.Pending(events));
        Assert.Equal(("T1", "R2"), (kept.Tier, kept.Rule));
        Assert.Equal(StructureSources.Operator, kept.StructureSource);
    }
}
