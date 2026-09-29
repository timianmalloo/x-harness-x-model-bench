using AiDe.Core.Extraction;
using AiDe.Core.Facts;

namespace AiDe.Core.Tests;

/// <summary>
/// What the Bicep reader folds, and — more importantly — what it refuses to.
/// </summary>
/// <remarks>
/// <para><b>Measured before it was designed.</b> Across every <c>.bicep</c> file in TheTerrace and
/// this repository (2 files, 27 resource declarations) the names break down as: 8 quoted string
/// literals, 3 string interpolations, 10 bare references to a <c>var</c> or <c>param</c>, and 6
/// <c>guid(...)</c> calls. There are <b>zero</b> loops.</para>
///
/// <para><b>The reason this was worth building is a defect, not coverage.</b> The old
/// <c>IsLiteral</c> test was "contains no <c>$</c> and no <c>(</c>", which is true of a bare
/// identifier — so <c>name: workspaceName</c> was asserted as <c>resource_name =
/// "workspaceName"</c>. MEASURED on TheTerrace: <b>10 of 27</b> resource names in the graph were the
/// identifier text rather than a name, and none of them was disclosed, because they never took the
/// expression branch. A name nobody would find in the portal, asserted as fact.</para>
///
/// <para>So these tests come in two halves. The folding half asserts a name is EXACTLY what Azure
/// deploys for the declared defaults — verified against <c>artifacts/bicep-validation/main.json</c>,
/// the compiled ARM output. The refusal half asserts that everything else keeps no name at all,
/// because a plausible wrong name is the worst thing this reader can produce.</para>
/// </remarks>
public sealed class BicepConstantFoldingTests : IDisposable
{
    private readonly string _root = Path.Combine(
        Path.GetTempPath(), "aide-bicep-fold", Guid.NewGuid().ToString("N"));

    public BicepConstantFoldingTests() => Directory.CreateDirectory(_root);

    public void Dispose()
    {
        try { Directory.Delete(_root, recursive: true); } catch (IOException) { }
    }

    private async Task<ExtractionResult> Extract(string content, string file = "main.bicep")
    {
        var path = Path.Combine(_root, file);
        Directory.CreateDirectory(Path.GetDirectoryName(path)!);
        await File.WriteAllTextAsync(path, content);

        return await new BicepExtractor().ExtractAsync(
            new ExtractionRequest("bicep:main", path, "rev-1", 1), CancellationToken.None);
    }

    private static IEnumerable<EvidenceAssertion> Where(ExtractionResult r, string predicate) =>
        r.Assertions.Where(a => a.Predicate == predicate);

    private static string? NameOf(ExtractionResult r, string symbol) =>
        Where(r, "resource_name")
            .SingleOrDefault(a => a.Subject.EndsWith("/" + symbol, StringComparison.Ordinal))?.Object;

    private static string? ExpressionOf(ExtractionResult r, string symbol) =>
        Where(r, "resource_name_expression")
            .SingleOrDefault(a => a.Subject.EndsWith("/" + symbol, StringComparison.Ordinal))?.Object;

    private static string? Disclosure(ExtractionResult r, string prefix) =>
        Where(r, CSharpExtractor.DisclosurePredicate)
            .SingleOrDefault(a => a.Object.StartsWith(prefix, StringComparison.Ordinal))?.Object;

    // ---- what IS folded ----------------------------------------------------

    [Fact]
    public async Task AVariableOverAParameterDefaultFoldsToTheNameAzureDeploys()
    {
        // Verbatim from TheTerrace/infra/main.bicep lines 7 and 148, and the compiled ARM at
        // artifacts/bicep-validation/main.json agrees: "workspaceName": "[format('{0}-log',
        // parameters('namePrefix'))]" with namePrefix defaultValue "theterrace-s00".
        var result = await Extract("""
            param namePrefix string = 'theterrace-s00'
            var workspaceName = '${namePrefix}-log'

            resource workspace 'Microsoft.OperationalInsights/workspaces@2023-09-01' = {
              name: workspaceName
            }
            """);

        Assert.Equal("theterrace-s00-log", NameOf(result, "workspace"));
    }

    [Fact]
    public async Task AFoldedNameIsInferred_BecauseADefaultCanBeOverriddenAtDeployTime()
    {
        // A quoted literal is what deploys, full stop. A folded name is what deploys FOR THE
        // DECLARED DEFAULTS, and `az deployment group create --parameters namePrefix=...` can say
        // otherwise. Two different claims, so two different statuses.
        var result = await Extract("""
            param namePrefix string = 'demo'
            resource a 'Microsoft.Sql/servers@2022-05-01' = {
              name: '${namePrefix}-sql'
            }
            resource b 'Microsoft.Sql/servers/databases@2022-05-01' = {
              name: 'terrace'
            }
            """);

        Assert.Equal(
            VerificationStatus.Inferred,
            Where(result, "resource_name").Single(a => a.Subject.EndsWith("/a", StringComparison.Ordinal)).Status);
        Assert.Equal(
            VerificationStatus.Verified,
            Where(result, "resource_name").Single(a => a.Subject.EndsWith("/b", StringComparison.Ordinal)).Status);
    }

    [Fact]
    public async Task NestedStringFunctionsOverKnownValuesAreFolded()
    {
        // TheTerrace/infra/main.bicep:137 — the one resource name in the corpus that needs more than
        // interpolation. toLower leaves it alone (already lower) and replace strips the hyphen.
        //
        // GROUND TRUTH, not reasoning: Azure's own what-if output, captured at
        // TheTerrace/docs/delivery/evidence/S00/recovery/91351669.../recovery-plan.json, names the
        // deployed resource `providers/Microsoft.Storage/storageAccounts/theterraces00dp`. This
        // assertion was FIRST WRITTEN as `theterrace00dp` — the 's' dropped by hand — and the
        // extractor disagreed. Checking the evidence rather than the test is why the wrong value is
        // not in the graph.
        var result = await Extract("""
            param namePrefix string = 'theterrace-s00'
            var storageName = replace(toLower('${namePrefix}dp'), '-', '')

            resource storage 'Microsoft.Storage/storageAccounts@2025-06-01' = {
              name: storageName
            }
            """);

        Assert.Equal("theterraces00dp", NameOf(result, "storage"));
    }

    [Fact]
    public async Task AParameterDefaultThatIsItselfAnExpressionIsFolded()
    {
        // main.bicep:23. A default may reference another parameter, so folding is recursive or it
        // stops one link short of every name in the file.
        var result = await Extract("""
            param namePrefix string = 'theterrace-s00'
            param appInsightsName string = '${namePrefix}-ai'

            resource insights 'Microsoft.Insights/components@2020-02-02' = {
              name: appInsightsName
            }
            """);

        Assert.Equal("theterrace-s00-ai", NameOf(result, "insights"));
    }

    [Fact]
    public async Task AFoldedNameCarriesNoLeftoverExpressionFact()
    {
        // `resource_name_expression` means "this reader could not evaluate it" — that is what
        // JoinProjection counts to decide whether to disclose `sql-resource-name-unresolved`, and
        // what EvidencePredicates describes as the place unevaluated strings go. Emitting it beside
        // a folded name would make a closed gap read as an open one.
        var result = await Extract("""
            param namePrefix string = 'demo'
            resource a 'Microsoft.Sql/servers@2022-05-01' = {
              name: '${namePrefix}-sql'
            }
            """);

        Assert.Null(ExpressionOf(result, "a"));
        Assert.Equal("demo-sql", NameOf(result, "a"));
    }

    // ---- what is REFUSED ---------------------------------------------------

    [Fact]
    public async Task AParameterWithNoDefaultIsNotFoldable_AndItsNameIsNotInvented()
    {
        // THE SHIPPED DEFECT. `param webAppName string` has no value at read time, and
        // provider-vault.bicep names a resource with it. Before this change the graph said the
        // resource was called "webAppName".
        var result = await Extract("""
            param webAppName string

            resource web 'Microsoft.Web/sites@2024-04-01' existing = {
              name: webAppName
            }
            """);

        Assert.Null(NameOf(result, "web"));
        Assert.Equal("webAppName", ExpressionOf(result, "web"));
    }

    [Fact]
    public async Task ASecureParameterDefaultIsNeverFoldedIntoAName()
    {
        // The regression an evaluator makes available for the first time. This extractor's strongest
        // documented guarantee is that no code path reads the value of a `@secure()` parameter — and
        // Bicep permits one to carry a default. Folding it would carry the secret into the store
        // through the graph rather than through the parameter's own facts, which is the same store.
        var result = await Extract("""
            @secure()
            @description('Legal, and a bad idea, and this reader must survive it.')
            param adminName string = 'super-secret-value'

            resource a 'Microsoft.Sql/servers@2022-05-01' = {
              name: adminName
            }
            """);

        Assert.Null(NameOf(result, "a"));
        Assert.DoesNotContain(
            result.Assertions,
            a => a.Object.Contains("super-secret-value", StringComparison.Ordinal));
    }

    [Fact]
    public async Task NoResourceNameIsEverTheTextOfADeclaredSymbol()
    {
        // The class of the defect rather than its instance: a `resource_name` that happens to equal
        // a param or var identifier declared in the same file is the reader having reported the
        // reference instead of the value.
        var result = await Extract("""
            param namePrefix string = 'theterrace-s00'
            param unset string
            var vaultName = '${namePrefix}-kv'

            resource vault 'Microsoft.KeyVault/vaults@2023-07-01' = {
              name: vaultName
            }
            resource other 'Microsoft.Web/sites@2024-04-01' = {
              name: unset
            }
            """);

        string[] symbols = ["namePrefix", "unset", "vaultName"];

        Assert.DoesNotContain(Where(result, "resource_name"), a => symbols.Contains(a.Object));
    }

    [Fact]
    public async Task GuidIsNeverFolded_BecauseItsInputsDoNotExistUntilDeployment()
    {
        // Six of the 27 names in the corpus, every one of them a role assignment. `guid()` is a
        // deterministic hash whose arguments are resource IDs — which need a subscription and a
        // resource group that a file cannot supply. There is no partial credit available here.
        var result = await Extract("""
            param namePrefix string = 'demo'
            var roleId = subscriptionResourceId('Microsoft.Authorization/roleDefinitions', 'ba92f5b4')

            resource web 'Microsoft.Web/sites@2024-04-01' = {
              name: '${namePrefix}-web'
            }
            resource role 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
              name: guid(web.id, roleId)
            }
            resource foldableArguments 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
              name: guid('scope', namePrefix)
            }
            """);

        Assert.Null(NameOf(result, "role"));
        Assert.Equal("guid(web.id, roleId)", ExpressionOf(result, "role"));

        // The second case exists because the first does not actually test the refusal it names.
        // `web.id` is a property access, so it is refused as an ARGUMENT and `guid` is never reached
        // — MEASURED by adding guid to the function table and watching this test stay green, which
        // is DC-016 wearing a tick. Every argument here folds, so the only thing standing between
        // this template and an invented GUID is the function table itself.
        Assert.Null(NameOf(result, "foldableArguments"));
        Assert.Equal("guid('scope', namePrefix)", ExpressionOf(result, "foldableArguments"));
    }

    [Fact]
    public async Task UniqueStringIsNeverFolded()
    {
        // Zero uses in the corpus, and named here because it LOOKS foldable — it takes strings and
        // returns one. It is a 13-character hash whose algorithm is not part of any contract Azure
        // publishes, so a folded value would be a guess with a plausible shape.
        var result = await Extract("""
            param namePrefix string = 'demo'
            resource s 'Microsoft.Storage/storageAccounts@2023-01-01' = {
              name: uniqueString(namePrefix)
            }
            """);

        Assert.Null(NameOf(result, "s"));
        Assert.Equal("uniqueString(namePrefix)", ExpressionOf(result, "s"));
    }

    [Fact]
    public async Task AnUnrecognisedFunctionIsRefusedRatherThanApproximated()
    {
        // Default-deny. `format` is excluded deliberately: it needs a placeholder parser, it has
        // ZERO uses in any resource name across the corpus, and a mis-read `{0}` produces a wrong
        // name rather than no name.
        var result = await Extract("""
            param namePrefix string = 'demo'
            resource a 'Microsoft.Sql/servers@2022-05-01' = {
              name: format('{0}-sql', namePrefix)
            }
            resource b 'Microsoft.Sql/servers@2022-05-01' = {
              name: resourceGroup().location
            }
            """);

        Assert.Null(NameOf(result, "a"));
        Assert.Null(NameOf(result, "b"));
    }

    [Fact]
    public async Task AConditionalExpressionIsRefused_BecauseTheConditionMayBeUnknowable()
    {
        var result = await Extract("""
            param enable bool
            param namePrefix string = 'demo'
            resource a 'Microsoft.Sql/servers@2022-05-01' = {
              name: enable ? '${namePrefix}-a' : '${namePrefix}-b'
            }
            """);

        Assert.Null(NameOf(result, "a"));
    }

    [Fact]
    public async Task AnEscapeSequenceIsRefusedRatherThanGuessedAt()
    {
        // Bicep's escapes are \\ \' \n \r \t \$ \u{...}. Getting one wrong yields a name that is
        // wrong by one character, which is indistinguishable from right until somebody searches the
        // portal for it. Zero uses in the corpus, so the whole class is refused.
        var result = await Extract("""
            resource a 'Microsoft.Sql/servers@2022-05-01' = {
              name: 'a\tb'
            }
            """);

        Assert.Null(NameOf(result, "a"));
    }

    [Fact]
    public async Task AVariableCycleTerminatesAndFoldsNothing()
    {
        // Not valid Bicep, and this reader never compiles anything — it will meet whatever a
        // repository contains, including a file mid-edit. A resolver with no termination variant
        // hangs the indexer on it.
        var result = await Extract("""
            var a = '${b}-x'
            var b = '${a}-y'

            resource r 'Microsoft.Sql/servers@2022-05-01' = {
              name: a
            }
            """);

        Assert.Null(NameOf(result, "r"));
    }

    // ---- the disclosures ---------------------------------------------------

    [Fact]
    public async Task TheExpressionDisclosureSaysHowManyNamesAreStillUnresolved()
    {
        var result = await Extract("""
            param namePrefix string = 'demo'
            resource a 'Microsoft.Sql/servers@2022-05-01' = {
              name: '${namePrefix}-sql'
            }
            resource b 'Microsoft.Sql/servers@2022-05-01' = {
              name: 'literal'
            }
            resource c 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
              name: guid(a.id)
            }
            """);

        Assert.Equal(
            "bicep-expressions-not-evaluated (1 of 3 resource name(s) are expressions this reader does not evaluate)",
            Disclosure(result, ExtractionDisclosures.BicepExpressionsNotEvaluated));
    }

    [Fact]
    public async Task ATemplateWhoseNamesAllFoldDisclosesNothingAboutExpressions()
    {
        // DC-025: a disclosure that fires when nothing was hidden teaches a reader to skip
        // disclosures. Before folding, this template disclosed; now there is nothing to disclose.
        var result = await Extract("""
            param namePrefix string = 'demo'
            var siteName = '${namePrefix}-web'

            resource a 'Microsoft.Web/sites@2024-04-01' = {
              name: siteName
            }
            """);

        Assert.Null(Disclosure(result, ExtractionDisclosures.BicepExpressionsNotEvaluated));
        Assert.Equal("demo-web", NameOf(result, "a"));
    }

    [Fact]
    public async Task TheCountDisclosureSaysHowManyLoopsAndConditionalsCauseIt()
    {
        // "the count is indeterminate" and "one loop and one conditional make it indeterminate" are
        // different statements about how far off the declaration count can be.
        var result = await Extract("""
            param names array = ['a', 'b']
            param enable bool = true

            resource many 'Microsoft.Storage/storageAccounts@2023-01-01' = [for n in names: {
              name: n
            }]
            resource maybe 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (enable) {
              name: 'role'
            }
            """);

        Assert.Equal(
            "bicep-resource-count-indeterminate (1 loop(s) and 1 conditional resource(s) of 2 declaration(s))",
            Disclosure(result, ExtractionDisclosures.BicepResourceCountIndeterminate));
    }

    // ---- name attribution --------------------------------------------------

    [Fact]
    public async Task AResourceWithNoNameOfItsOwnDoesNotBorrowTheNextOnes()
    {
        // The same unbounded-forward-search defect already fixed for `dependsOn` in this file. A
        // child resource declared with `parent:` and no `name:` would otherwise be given whatever
        // name appeared next in the file — an edge that is individually plausible and collectively
        // a fiction.
        var result = await Extract("""
            resource nameless 'Microsoft.Sql/servers@2022-05-01' = {
              location: 'westeurope'
            }

            resource next 'Microsoft.Sql/servers@2022-05-01' = {
              name: 'the-next-one'
            }
            """);

        Assert.Null(NameOf(result, "nameless"));
        Assert.Null(ExpressionOf(result, "nameless"));
        Assert.Equal("the-next-one", NameOf(result, "next"));
    }
}
