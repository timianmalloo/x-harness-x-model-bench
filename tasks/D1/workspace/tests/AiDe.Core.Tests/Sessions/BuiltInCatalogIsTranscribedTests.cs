using System.Collections.Generic;
using System.Linq;
using System.Text.Json;
using AiDe.Core.Sessions;

namespace AiDe.Core.Tests.Sessions;

/// <summary>
/// FT clause 6 — the twelve built-ins are TRANSCRIBED from Addendum B §B4, not authored (Ruling 30).
/// </summary>
/// <remarks>
/// <para><b>Every row cites B4 by reading it.</b> The rows come out of the committed spec on each
/// run, so the citation cannot rot into a comment that once was true.</para>
///
/// <para><b>Three recorded deviations</b> are asserted as deviations rather than hidden: (i)
/// <c>goal-block</c>'s why drops the trailing re-base parenthetical and keeps it as provenance; (ii)
/// <c>ruling-request</c> takes B3.1's excerpt verbatim for its fields and body; (iii) all twelve ship
/// at version 1, because B3.1's illustrative <c>version: 3</c> would claim a history nobody
/// observed.</para>
/// </remarks>
public sealed class BuiltInCatalogIsTranscribedTests
{
    private static readonly TemplateCatalog Catalog = TemplateCatalog.BuiltIn();

    [Fact]
    public void TheCatalogIsExactlyB4sTwelveRows()
    {
        Assert.Equal(
            AddendumB.CatalogRows().Select(r => r.Id).Order(StringComparer.Ordinal),
            Catalog.Entries.Select(e => e.Id).Order(StringComparer.Ordinal));
    }

    [Theory]
    [MemberData(nameof(Ids))]
    public void WhenToUseIsByteForByteFromB4(string id)
    {
        var row = AddendumB.Row(id);

        Assert.Equal(row.WhenToUse, Catalog.Find(id)!.Template!.WhenToUse);
    }

    [Theory]
    [MemberData(nameof(Ids))]
    public void WhyIsByteForByteFromB4ExceptTheOneRecordedDrop(string id)
    {
        var row = AddendumB.Row(id);

        Assert.Equal(AddendumB.WhyForTemplate(row), Catalog.Find(id)!.Template!.Why);
    }

    [Fact]
    public void OnlyGoalBlockDropsAnythingFromItsWhy()
    {
        var dropping = AddendumB.CatalogRows()
            .Where(r => AddendumB.DroppedFromWhy(r) is not null)
            .Select(r => r.Id)
            .ToList();

        Assert.Equal(["goal-block"], dropping);
    }

    [Fact]
    public void GoalBlocksDroppedParentheticalIsKeptAsTemplateProvenance()
    {
        var dropped = AddendumB.DroppedFromWhy(AddendumB.Row("goal-block"));
        var template = Catalog.Find("goal-block")!.Template!;

        Assert.NotNull(dropped);
        Assert.DoesNotContain(dropped!, template.Why, StringComparison.Ordinal);
        Assert.Equal(dropped, template.UnknownFrontmatter["provenance_dropped_from_why"]);
    }

    [Theory]
    [MemberData(nameof(Ids))]
    public void IntentAndAudienceComeFromB4(string id)
    {
        var row = AddendumB.Row(id);
        var template = Catalog.Find(id)!.Template!;

        Assert.Equal(row.Intent, template.Intent);
        Assert.Equal(row.Audience, template.Audience);
    }

    [Theory]
    [MemberData(nameof(Ids))]
    public void CoreFieldsAreTheMechanicalSlugOfB4sColumn(string id)
    {
        if (id == "ruling-request")
        {
            // Deviation ii: B4's cell reads "options+costs" where B3.1 — the file-format authority —
            // names the field `options` and puts the cost in its hint. B3.1's own body slot
            // {{#options}} would dangle against any other name, so B3.1 wins and this is recorded
            // rather than resolved silently.
            return;
        }

        if (id == "goal-block")
        {
            // Deviation iii (Rulings 56, 63, 72; CV-1): B4's cell still lists tier, fan_out_cap and
            // budget, which are no longer per-prompt fields — the tier is the compile step's
            // projection and the cap and budget are session settings. The template declares B4's
            // column MINUS those three, mechanically; the row is a finding for the spec's owner,
            // recorded rather than resolved silently.
            Assert.Equal(
                AddendumB.FieldNames(AddendumB.Row(id))
                    .Except(AiDe.Core.Presentation.Composer.ComposerDraft.SessionSuppliedGoalFields, StringComparer.Ordinal),
                Catalog.Find(id)!.Template!.Fields.Select(f => f.Name));
            return;
        }

        Assert.Equal(
            AddendumB.FieldNames(AddendumB.Row(id)),
            Catalog.Find(id)!.Template!.Fields.Select(f => f.Name));
    }

    [Fact]
    public void RulingRequestTakesItsFieldsAndBodyFromB31Verbatim()
    {
        var template = Catalog.Find("ruling-request")!.Template!;

        Assert.Equal(["question", "options", "recommendation", "evidence", "decides_by"], template.Fields.Select(f => f.Name));
        Assert.Equal(TemplateFieldType.List, template.Fields.Single(f => f.Name == "options").Type);
        Assert.Equal(2, template.Fields.Single(f => f.Name == "options").Min);
        Assert.Equal(TemplateFieldType.Mentions, template.Fields.Single(f => f.Name == "evidence").Type);
        Assert.Equal("T0", template.TierDefault);

        var excerpt = RepoFiles.AddendumBHtml();
        Assert.Contains("A ruling is requested. Authority: your decision counts as the user's (CT20).", excerpt, StringComparison.Ordinal);
        Assert.StartsWith("A ruling is requested. Authority: your decision counts as the user's (CT20).", template.Body, StringComparison.Ordinal);
        Assert.Contains("{{#options}}- {{.}}{{/options}}", template.Body, StringComparison.Ordinal);
    }

    [Theory]
    [MemberData(nameof(Ids))]
    public void EveryBuiltInShipsAtVersionOne(string id)
    {
        // Deviation iii: B3.1 illustrates `version: 3`. A v3 with no v1 or v2 claims a history that
        // was not observed.
        Assert.Equal(1, Catalog.Find(id)!.Template!.Version);
    }

    [Theory]
    [MemberData(nameof(Ids))]
    public void EveryBuiltInCitesTheB4RowItCameFrom(string id)
    {
        var provenance = Catalog.Find(id)!.Template!.UnknownFrontmatter["provenance"];

        Assert.Contains("B4", provenance, StringComparison.Ordinal);
        Assert.Contains(id, provenance, StringComparison.Ordinal);
    }

    [Fact]
    public void LaunchsFieldsEachMapOntoASectionOfTheRealLaunchPrompt()
    {
        // B4 says launch was "Derived from this project's launch prompt". This is that claim, checked
        // against the prompt itself rather than taken on trust.
        var prompt = AuditPrompt("al-01M23NQ3H2X748YSBMDKDVV9EJ");
        var anchors = new Dictionary<string, string>(StringComparer.Ordinal)
        {
            ["goal_block"] = "Goal:",
            ["roles_authority"] = "ROLES AND AUTHORITY",
            ["setup_sequence"] = "SETUP (in order)",
            ["standing_constraints"] = "STANDING CONSTRAINTS",
            ["phase_gate"] = "Later phases proceed only on an explicit Owner ruling per phase.",
        };

        var template = Catalog.Find("launch")!.Template!;
        Assert.Equal(anchors.Keys.Order(StringComparer.Ordinal), template.Fields.Select(f => f.Name).Order(StringComparer.Ordinal));
        Assert.All(template.Fields, f => Assert.Contains(anchors[f.Name], prompt, StringComparison.Ordinal));
    }

    [Fact]
    public void ChangeOrdersFieldsEachMapOntoBothRealChangeOrderPrompts()
    {
        var template = Catalog.Find("change-order")!.Template!;

        var addendumA = new Dictionary<string, string>(StringComparer.Ordinal)
        {
            ["what_changed"] = "Addendum A: The Session Experience",
            ["intake_steps"] = "Ingest, reconcile against reality",
            ["amended_goal_block"] = "amend the goal block",
            ["re_plan_scope"] = "the admission of this scope change",
            ["added_constraints"] = "the same authority chain as everything else",
        };

        var addendumB = new Dictionary<string, string>(StringComparer.Ordinal)
        {
            ["what_changed"] = "Addendum B: Prompt Templates",
            ["intake_steps"] = "Ingest, reconcile against the front-door work in flight",
            ["amended_goal_block"] = "amend the goal block",
            ["re_plan_scope"] = "ratification admits the scope",
            ["added_constraints"] = "record the ruling as decision note + audit entry",
        };

        Assert.Equal(addendumA.Keys.Order(StringComparer.Ordinal), template.Fields.Select(f => f.Name).Order(StringComparer.Ordinal));

        var first = AuditPrompt("al-01M24B0ERPJYMCAR1BS49N7J4P");
        var second = AuditPrompt("al-01M2687RD6P8RK5KZJXQ0ZBEJS");

        Assert.All(template.Fields, f => Assert.Contains(addendumA[f.Name], first, StringComparison.Ordinal));
        Assert.All(template.Fields, f => Assert.Contains(addendumB[f.Name], second, StringComparison.Ordinal));
    }

    public static TheoryData<string> Ids() => AddendumB.Ids();

    /// <summary>
    /// The prompt text of one audit entry, by id.
    /// </summary>
    /// <remarks>
    /// Looked up by id rather than filtered by <c>kind</c>: the launch prompt is <c>kind:prompt</c>
    /// but both change orders were recorded as <c>kind:manual</c>, and the evidence is the prompt
    /// text either way.
    /// </remarks>
    private static string AuditPrompt(string id)
    {
        foreach (var line in RepoFiles.AuditLogJsonl().Split('\n'))
        {
            if (string.IsNullOrWhiteSpace(line))
            {
                continue;
            }

            using var document = JsonDocument.Parse(line);
            if (document.RootElement.TryGetProperty("id", out var entryId)
                && entryId.GetString() == id
                && document.RootElement.TryGetProperty("prompt", out var prompt))
            {
                return prompt.GetString() ?? string.Empty;
            }
        }

        Assert.Fail($"audit entry '{id}' carries no prompt");
        return string.Empty;
    }
}
