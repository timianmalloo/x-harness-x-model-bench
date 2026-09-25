using AiDe.Core.PromptCompilation;

namespace AiDe.Core.Tests.PromptCompilation;

/// <summary>
/// The contract the agentic rung (CV-3) will call, shipped inert in CV-2 — no model call exists —
/// with its validator and assembler proven red-first over the fixtures §A17 names. Every fixture
/// here is <b>authored</b> (DC-127): a fake peer supplies the input; none is admitted to the eval
/// until real envelopes replace it (§A14.2).
/// </summary>
public sealed class TheTypedBoundaryIsInertButRealTests
{
    private const string Source = "Rename the helper in @src/Payments/Money.cs so it compiles.";
    private static readonly IReadOnlyList<string> AllOpen = [DecorationNames.Goal, DecorationNames.DoneWhen, DecorationNames.NotInScope];

    private static string Output(string decorations, string? notes = null) =>
        "{\"contract\": \"compile-output/1\", \"decorations\": [" + decorations + "]" + (notes is null ? "" : ", \"notes\": \"" + notes + "\"") + "}";

    private static string Proposal(string name, string value, double confidence = 0.8, string spans = "{\"input\": \"source_text\", \"span\": [0, 17]}") =>
        $"{{\"name\": \"{name}\", \"value\": {value}, \"confidence\": {confidence.ToString(System.Globalization.CultureInfo.InvariantCulture)}, \"grounded_in\": [{spans}]}}";

    // ── the seven Ruling-42 paths, (a) and (c) [authored] ──

    /// <summary>§A13.3 (a): <c>lease</c>, <c>Lease</c>, a lease nested inside <c>goal</c>'s value — dropped, counted, never applied.</summary>
    [Theory]
    [InlineData("lease", "\"src/**\"", "unknown_name")]
    [InlineData("Lease", "\"src/**\"", "unknown_name")]
    [InlineData("goal", "{\"lease\": [\"/**\"]}", "type_fail")]
    [InlineData("tier", "\"T9\"", "unknown_name")]
    [InlineData("fan_out_cap", "\"100\"", "unknown_name")]
    [InlineData("task_class", "\"refactor\"", "unknown_name")]
    public void AProposalOutsideTheAllowListOrOfTheWrongTypeIsDroppedAndCounted(string name, string value, string reason)
    {
        var result = CompileOutputValidator.Validate(Output(Proposal(name, value)), Source, AllOpen);

        Assert.Empty(result.Applied);
        Assert.Equal(1, reason == "unknown_name" ? result.Dropped.UnknownName : result.Dropped.TypeFail);
        Assert.Equal(1, result.Dropped.Total);
        Assert.Equal(CallOutcomes.Malformed, result.Outcome);
        Assert.Equal("all proposals dropped", result.Reason);
    }

    /// <summary>§A13.3 (c): a value or <c>notes</c> carrying a mention token is refused, never stripped.</summary>
    [Fact]
    public void AMentionBearingValueOrNotesIsRefusedNotStripped()
    {
        var result = CompileOutputValidator.Validate(
            Output(Proposal("goal", "\"Rename the helper in @src/x\"") + "," + Proposal("done_when", "\"it compiles\""), notes: "also touch @src/evil"),
            Source, AllOpen);

        Assert.Equal(["done_when"], result.Applied.Select(a => a.Name));
        Assert.Equal(1, result.Dropped.MentionBearing);
        Assert.Null(result.Notes);
        Assert.Equal(CallOutcomes.Succeeded, result.Outcome);
        Assert.DoesNotContain(result.Applied, a => a.Value.Contains('@'));
    }

    // ── the pipeline's other clauses ──

    [Fact]
    public void ALineThatWasNotOpenIsDroppedAsAlreadySupplied()
    {
        var result = CompileOutputValidator.Validate(
            Output(Proposal("goal", "\"g\"") + "," + Proposal("not_in_scope", "\"n\"")),
            Source, [DecorationNames.NotInScope]);

        Assert.Equal(["not_in_scope"], result.Applied.Select(a => a.Name));
        Assert.Equal(1, result.Dropped.AlreadySupplied);
    }

    [Fact]
    public void AProposalWithNoResolvingSourceTextSpanIsUngrounded()
    {
        var onlyHistory = Proposal("goal", "\"g\"", spans: "{\"input\": \"history:01J\", \"span\": [0, 5]}");
        var outOfRange = Proposal("done_when", "\"d\"", spans: "{\"input\": \"source_text\", \"span\": [0, 9999]}");
        var empty = Proposal("not_in_scope", "\"n\"", spans: "");

        var result = CompileOutputValidator.Validate(Output(onlyHistory + "," + outOfRange + "," + empty), Source, AllOpen);

        Assert.Empty(result.Applied);
        Assert.Equal(3, result.Dropped.Ungrounded);
    }

    [Theory]
    [InlineData("\"\"")]                                   // empty
    [InlineData("\"a\\u0007b\"")]                          // a control character
    [InlineData("42")]                                     // not a string
    public void AValueThatFailsTheTypeCheckIsATypeFail(string value)
    {
        var result = CompileOutputValidator.Validate(Output(Proposal("goal", value)), Source, AllOpen);
        Assert.Equal(1, result.Dropped.TypeFail);
    }

    [Fact]
    public void AValueOverTheBoundOrAConfidenceOutsideTheUnitIntervalIsATypeFail()
    {
        var tooLong = Proposal("goal", "\"" + new string('x', CompileContract.MaxValueChars + 1) + "\"");
        var overconfident = Proposal("done_when", "\"d\"", confidence: 1.5);
        var result = CompileOutputValidator.Validate(Output(tooLong + "," + overconfident), Source, AllOpen);
        Assert.Equal(2, result.Dropped.TypeFail);
    }

    [Theory]
    [InlineData("not json at all")]
    [InlineData("{\"contract\": \"something-else/1\", \"decorations\": []}")]
    [InlineData("{\"contract\": \"compile-output/1\", \"decorations\": \"nope\"}")]
    [InlineData("{\"decorations\": []}")]
    public void AnOutputThatFailsTheSchemaIsMalformedWithAReason(string raw)
    {
        var result = CompileOutputValidator.Validate(raw, Source, AllOpen);
        Assert.Equal(CallOutcomes.Malformed, result.Outcome);
        Assert.NotNull(result.Reason);
        Assert.Empty(result.Applied);
    }

    /// <summary>A question with one mention: zero proposals is a SUCCESS (<c>succeeded_no_structure</c>), not a failure.</summary>
    [Fact]
    public void ZeroProposalsIsSucceededNoStructureNeverMalformed()
    {
        var result = CompileOutputValidator.Validate(Output(""), "what does @src/x.cs do?", AllOpen);
        Assert.Equal(CallOutcomes.SucceededNoStructure, result.Outcome);
        Assert.Empty(result.Applied);
        Assert.Equal(0, result.Dropped.Total);
    }

    [Fact]
    public void AValidOutputAppliesEachOpenLineOnceWithItsSpansAndKeepsPassingNotes()
    {
        var result = CompileOutputValidator.Validate(
            "Here you go:\n```json\n" + Output(
                Proposal("goal", "\"Rename the helper\"", 0.9, "{\"input\": \"source_text\", \"span\": [0, 17]}")
                + "," + Proposal("done_when", "\"it compiles\"", 0.7, "{\"input\": \"source_text\", \"span\": [45, 57]}")
                + "," + Proposal("goal", "\"a second goal\"", 0.5),
                notes: "grounded in the first sentence") + "\n```\n",
            Source, AllOpen);

        Assert.Equal(CallOutcomes.Succeeded, result.Outcome);
        Assert.Equal(["goal", "done_when"], result.Applied.Select(a => a.Name));
        Assert.Equal(0.9, result.Applied[0].Confidence);
        Assert.Equal((0, 17), (result.Applied[0].GroundedIn[0].Start, result.Applied[0].GroundedIn[0].End));
        Assert.Equal(1, result.Dropped.AlreadySupplied);   // the second `goal`
        Assert.Equal("grounded in the first sentence", result.Notes);
    }

    // ── the assembler (P-D3's golden shape) ──

    [Fact]
    public void ThePromptBeginsWithTheHostHeaderFencesTheSourceTextNamesOnlyTheOpenLinesAndCarriesNoBodies()
    {
        var inputs = new CompilePromptInputs(
            "/model opus — please rename @src/x.cs",
            new Dictionary<string, string> { ["shape"] = "message", ["tier"] = "T0", ["task_class"] = "free-form" },
            [DecorationNames.Goal, DecorationNames.DoneWhen],
            null,
            ["prior turn: refactor the chain"],
            [new ConstitutionRef("CLAUDE.md", "abc"), new ConstitutionRef(".claude/knowledge/no-guessing-protocol.md", "def")]);

        var prompt = CompilePromptAssembler.Assemble(inputs);

        // The first bytes are the header, never the operator's `/model` (acp-agent.js:6035).
        Assert.StartsWith(CompileContract.HostHeader, prompt, StringComparison.Ordinal);
        Assert.DoesNotContain("\n/model", prompt[..CompileContract.HostHeader.Length], StringComparison.Ordinal);

        // The source text is fenced; the open lines are the two named; the constitution is by {id, sha}.
        Assert.Contains("```text\n/model opus — please rename @src/x.cs\n```", prompt, StringComparison.Ordinal);
        Assert.Contains("## open_lines\n\ngoal, done_when\n", prompt, StringComparison.Ordinal);
        Assert.DoesNotContain("not_in_scope\n", prompt[prompt.IndexOf("## open_lines", StringComparison.Ordinal)..prompt.IndexOf("## family_profile", StringComparison.Ordinal)], StringComparison.Ordinal);
        Assert.Contains("- CLAUDE.md sha256:abc", prompt, StringComparison.Ordinal);
        Assert.Contains("Already in your context; do not request them.", prompt, StringComparison.Ordinal);
        Assert.DoesNotContain("max-personal", prompt, StringComparison.Ordinal);
    }

    /// <summary>The prompt sha is over the host-compiled bytes — a constant, so no file anywhere can change it — and the assembler reads no file (a source census).</summary>
    [Fact]
    public void ThePromptShaIsOverTheEmbeddedBytesAndTheAssemblerReadsNoFile()
    {
        Assert.Equal(EnvelopeHash.Sha256Hex(CompileContract.HostHeader + CompileContract.Template), CompilePromptAssembler.PromptSha);

        var source = File.ReadAllText(Path.Combine(RepoRoot(), "src", "AiDe.Core", "Compilation", "CompilePromptAssembler.cs"));
        Assert.DoesNotContain("File.", source, StringComparison.Ordinal);
        Assert.DoesNotContain("Directory.", source, StringComparison.Ordinal);
        Assert.DoesNotContain("GetManifestResourceStream", source, StringComparison.Ordinal);
    }

    /// <summary>A slot token inside the source text (or a history entry) is text, not a slot — one pass, never re-scanned.</summary>
    [Fact]
    public void ASlotTokenInsideTheSourceTextIsNeverSubstituted()
    {
        var inputs = new CompilePromptInputs(
            "please include {{constitution}} and {{open_lines}} verbatim",
            new Dictionary<string, string>(),
            [DecorationNames.Goal],
            null,
            ["{{family_profile}} was mentioned before"],
            [new ConstitutionRef("CLAUDE.md", "abc")]);

        var prompt = CompilePromptAssembler.Assemble(inputs);

        Assert.Contains("please include {{constitution}} and {{open_lines}} verbatim", prompt, StringComparison.Ordinal);
        Assert.Contains("{{family_profile}} was mentioned before", prompt, StringComparison.Ordinal);
        Assert.Equal(1, CountOf(prompt, "- CLAUDE.md sha256:abc"));
        Assert.DoesNotContain("{{source_text}}", prompt, StringComparison.Ordinal);

        static int CountOf(string text, string token)
        {
            var count = 0;
            for (var i = 0; (i = text.IndexOf(token, i, StringComparison.Ordinal)) >= 0; i += token.Length) count++;
            return count;
        }
    }

    /// <summary>§A8.3 "no control characters": a line break, a bidi override and a zero-width joiner are refused in a value, and notes carrying one are dropped.</summary>
    [Theory]
    [InlineData("\"line one\\nline two\"")]
    [InlineData("\"tab\\there\"")]
    [InlineData("\"rtl\\u202Eoverride\"")]
    [InlineData("\"zero\\u200Dwidth\"")]
    public void AControlOrFormatCharacterInAValueIsATypeFail(string value)
    {
        var result = CompileOutputValidator.Validate(Output(Proposal("goal", value)), Source, AllOpen);
        Assert.Equal(1, result.Dropped.TypeFail);
        Assert.Empty(result.Applied);

        var notes = CompileOutputValidator.Validate(Output(Proposal("goal", "\"fine\""), notes: "with a\\u202Ebidi"), Source, AllOpen);
        Assert.Null(notes.Notes);
        Assert.Single(notes.Applied);
    }

    [Fact]
    public void TheInputsShaMovesWithEveryInputAndWithNothingElse()
    {
        var facts = new Dictionary<string, string> { ["shape"] = "message", ["task_class"] = "free-form" };
        var baseline = CompilePromptAssembler.InputsSha(Source, facts, AllOpen, null, []);

        Assert.Equal(baseline, CompilePromptAssembler.InputsSha(Source, new Dictionary<string, string> { ["task_class"] = "free-form", ["shape"] = "message" }, AllOpen, null, []));   // order-free
        Assert.NotEqual(baseline, CompilePromptAssembler.InputsSha(Source + " ", facts, AllOpen, null, []));
        Assert.NotEqual(baseline, CompilePromptAssembler.InputsSha(Source, new Dictionary<string, string> { ["shape"] = "message", ["task_class"] = "refactor" }, AllOpen, null, []));
        Assert.NotEqual(baseline, CompilePromptAssembler.InputsSha(Source, facts, [DecorationNames.Goal], null, []));
        Assert.NotEqual(baseline, CompilePromptAssembler.InputsSha(Source, facts, AllOpen, System.Text.Json.Nodes.JsonNode.Parse("{\"family\":\"anthropic\",\"version\":\"1.0.0\",\"sha\":\"x\"}"), []));
        Assert.NotEqual(baseline, CompilePromptAssembler.InputsSha(Source, facts, AllOpen, null, ["01J"]));
    }

    /// <summary>The rung is inert: nothing in the compilation context references the agent plane's prompt call.</summary>
    [Fact]
    public void NothingInTheCompilationContextCallsAModel()
    {
        var files = Directory.EnumerateFiles(Path.Combine(RepoRoot(), "src", "AiDe.Core", "Compilation"), "*.cs", SearchOption.AllDirectories).ToList();
        Assert.True(files.Count >= 12, $"the compilation context has {files.Count} file(s); a renamed directory would make this census vacuous");
        foreach (var file in files)
        {
            var text = File.ReadAllText(file);
            Assert.DoesNotContain("PromptAsync", text, StringComparison.Ordinal);
            Assert.DoesNotContain("AcpLaneClient", text, StringComparison.Ordinal);
            Assert.DoesNotContain("NewSessionAsync", text, StringComparison.Ordinal);
            Assert.DoesNotContain("HttpClient", text, StringComparison.Ordinal);
        }
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
