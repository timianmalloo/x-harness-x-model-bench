using System.Text.RegularExpressions;
using AiDe.Core.Facts;

namespace AiDe.Core.Extraction;

/// <summary>
/// The infrastructure extractor — Bicep read as <b>data</b>, never compiled.
/// </summary>
/// <remarks>
/// <para><b>Why not <c>bicep build</c>.</b> Spike D3 measured that compiling repository-supplied
/// input runs repository-supplied logic, and Bicep resolves module references and evaluates template
/// functions at build time. Invoking the compiler on a cloned repository is the same exposure
/// MSBuild was, so the same answer applies: read it.</para>
///
/// <para><b>Measured at parity for what it claims.</b> Against <c>az bicep build</c> on a real
/// 677-line template: 24 of 24 resources, 19 of 19 types, 18 of 18 parameters
/// (<c>spikes/bicep-as-data</c>).</para>
///
/// <para><b>Names are CONSTANT-FOLDED, not evaluated.</b> Parameters with a declared default and
/// variables are substituted, string interpolation and four pure string functions are folded over
/// values already known, and everything else is refused and counted. MEASURED across every
/// <c>.bicep</c> file in TheTerrace and this repository — 27 resource declarations — that resolves
/// 20 names and leaves 7. The residue is <c>guid(...)</c>, whose arguments are resource IDs that do
/// not exist until a deployment names a subscription, and one parameter with no default. Both are
/// boundaries, not gaps: no amount of reading a file closes either.</para>
///
/// <para>The reason it folds at all is a defect rather than coverage. The old test for "literal" was
/// <i>contains no <c>$</c> and no <c>(</c></i>, which a bare identifier passes — so
/// <c>name: workspaceName</c> was asserted as the name <c>workspaceName</c>. That was <b>10 of the
/// 27</b>, undisclosed, because they never reached the expression branch.</para>
///
/// <para><b>The value of an <c>@secure()</c> parameter is never read.</b> Not redacted after the
/// fact: the parameter is recorded as existing and as secret, and its value is never looked at, so
/// there is no path by which it could reach a store, a log or a projection.</para>
/// </remarks>
public sealed partial class BicepExtractor(string extractorVersion = "1.0.0") : IExtractor
{
    public const string ExtractorId = "bicep-extractor";

    public string ScopeKind => "bicep";

    // Captures what follows the '=' so a loop, a condition or an `existing` reference is
    // recognised rather than missed. The previous form required '=' to be followed by '{' on the
    // same line, which silently dropped every `[for ...]` and every `if (...)` resource — a
    // template using them would have reported a smaller infrastructure than it has.
    [GeneratedRegex(
        @"^\s*resource\s+(?<symbol>\w+)\s+'(?<type>[^@']+)@(?<api>[^']+)'\s+(?<existing>existing\s+)?=\s*(?<tail>.*)$",
        RegexOptions.Multiline)]
    private static partial Regex ResourceDeclaration();

    [GeneratedRegex(@"^\s*module\s+(?<symbol>\w+)\s+'(?<path>[^']+)'\s*=", RegexOptions.Multiline)]
    private static partial Regex ModuleDeclaration();

    [GeneratedRegex(@"^\s*param\s+(?<name>\w+)\s+(?<type>\w+)", RegexOptions.Multiline)]
    private static partial Regex ParameterDeclaration();

    [GeneratedRegex(@"^\s*name:\s*(?<name>.+)$", RegexOptions.Multiline)]
    private static partial Regex NameProperty();

    // dependsOn is either a single-line array or a block. Both forms are captured up to the closing
    // bracket, and the SYMBOLS inside are what matter — a dependsOn on an expression is not a
    // resource reference this reader can resolve, and is left out rather than guessed at.
    [GeneratedRegex(@"dependsOn:\s*\[(?<body>[^\]]*)\]", RegexOptions.Multiline)]
    private static partial Regex DependsOnBlock();

    [GeneratedRegex(@"^\s*(?<symbol>[A-Za-z_]\w*)\s*$", RegexOptions.Multiline)]
    private static partial Regex BareSymbol();

    public Task<ExtractionResult> ExtractAsync(ExtractionRequest request, CancellationToken cancellationToken)
    {
        ArgumentNullException.ThrowIfNull(request);

        var path = Path.GetFullPath(request.RootPath);
        if (!File.Exists(path))
        {
            return Task.FromResult(new ExtractionResult(
                [], Complete: false,
                [new ExtractionDiagnostic("AIDE-BICEP-MISSING", request.RootPath, "no bicep file at this path")]));
        }

        string text;
        try
        {
            text = File.ReadAllText(path);
        }
        catch (IOException ex)
        {
            return Task.FromResult(new ExtractionResult(
                [], Complete: false,
                [new ExtractionDiagnostic("AIDE-BICEP-UNREADABLE", request.ScopeId, ex.Message)]));
        }

        // Commentary is removed before anything is believed. This reader PASSED the shared
        // invent-rate control — its matchers are line-anchored on `resource`, `module` and `param`,
        // and a sweep of a repository it was not written against produced only real parameter names
        // and real Azure types. It is stripped anyway: it was the last line-oriented reader still
        // parsing raw text, and all three readers caught inventing were caught reading commented-out
        // code, which is real syntax precisely because it WAS code. Newlines survive the blanking,
        // so provenance line numbers stay true.
        text = SourceText.WithoutCComments(text);

        var assertions = new List<EvidenceAssertion>();
        var observedAt = DateTimeOffset.UtcNow;
        var fileName = Path.GetFileName(path);
        var scopeNode = CSharpExtractor.ScopeNodeId(request.ScopeId);
        var unresolved = 0;
        var named = 0;
        var resources = 0;
        var loops = 0;
        var conditionals = 0;

        // What the template declares about itself, read once. Built from the COMMENT-STRIPPED text,
        // so a commented-out `var` is not a binding.
        var folder = BicepConstantFolder.From(text);

        Provenance At(int index)
        {
            var line = text.Take(index).Count(c => c == '\n') + 1;
            return new Provenance(fileName, $"{line}:1", ExtractorId, extractorVersion, observedAt);
        }

        EvidenceAssertion Fact(
            string subject, string predicate, string obj, Provenance provenance,
            VerificationStatus status = VerificationStatus.Verified) =>
            new(request.ScopeId, request.ArtifactRevision, subject, predicate, obj,
                EvidenceOrigin.Static, status, provenance);

        // Where each declaration ends, so a dependsOn is attributed to the resource that contains
        // it rather than to whichever declaration happened to come before it in the file.
        var declarationStarts = ResourceDeclaration().Matches(text).Select(m => m.Index)
            .Concat(ModuleDeclaration().Matches(text).Select(m => m.Index))
            .OrderBy(i => i).ToList();

        int declarationEnds(int start)
        {
            var next = declarationStarts.FirstOrDefault(i => i > start, -1);
            return next < 0 ? text.Length : next;
        }

        foreach (Match match in ResourceDeclaration().Matches(text))
        {
            cancellationToken.ThrowIfCancellationRequested();

            var symbol = match.Groups["symbol"].Value;
            var node = $"{request.ScopeId}/{symbol}";
            var provenance = At(match.Index);
            resources++;

            var tail = match.Groups["tail"].Value.TrimStart();
            var isExisting = match.Groups["existing"].Success;
            var isLoop = tail.StartsWith("[for", StringComparison.Ordinal);
            var isConditional = tail.StartsWith("if", StringComparison.Ordinal);

            assertions.Add(Fact(node, "has_type", "azure-resource", provenance));
            assertions.Add(Fact(node, "resource_type", match.Groups["type"].Value, provenance));
            assertions.Add(Fact(node, "api_version", match.Groups["api"].Value, provenance));
            assertions.Add(Fact(node, "declared_in", request.ScopeId, provenance));

            // `existing` REFERENCES a resource this template does not deploy. Recorded distinctly,
            // because "this template creates a SQL server" and "this template talks to one someone
            // else creates" are different facts about ownership.
            if (isExisting) assertions.Add(Fact(node, "is_existing_reference", "true", provenance));

            // A loop declares an unknown NUMBER of resources — one per item in a collection this
            // reader does not evaluate. The declaration is one row; how many it becomes is not
            // knowable here, so it is stated rather than counted as one.
            if (isLoop)
            {
                assertions.Add(Fact(node, "is_loop", "true", provenance));
                loops++;
            }

            // A conditional resource may or may not be deployed, and the condition is an expression.
            if (isConditional)
            {
                assertions.Add(Fact(node, "is_conditional", "true", provenance));
                conditionals++;
            }

            // The resource GRAPH, not just the resource list. dependsOn is the only place a Bicep
            // template states deployment order outright, and it is the edge a C4 view is made of.
            foreach (var dependency in DependenciesAfter(text, match.Index, declarationEnds))
            {
                assertions.Add(Fact(node, "depends_on", $"{request.ScopeId}/{dependency}", provenance));
            }

            var name = NameAfter(text, match.Index, declarationEnds);
            if (name.Length == 0) continue;

            named++;

            // A literal name is a fact. A FOLDED name is a fact about the template's declared
            // defaults — exact for those defaults, and Inferred because `--parameters namePrefix=…`
            // can say otherwise. Anything else is a fact ABOUT an expression, recorded verbatim so a
            // reader can see what it is, and never resolved.
            //
            // The old test for "literal" was `contains no $ and no (`, which a bare identifier
            // passes: `name: workspaceName` was asserted as the name `workspaceName`. MEASURED on
            // TheTerrace, that was 10 of 27 resource names, undisclosed because they never reached
            // the expression branch — a confident wrong edge between a table and a server, which is
            // exactly what this branch exists to prevent.
            if (folder.TryFold(name, out var value, out var computed))
            {
                assertions.Add(Fact(
                    node, "resource_name", value!, provenance,
                    computed ? VerificationStatus.Inferred : VerificationStatus.Verified));
            }
            else
            {
                unresolved++;
                assertions.Add(Fact(node, "resource_name_expression", name, provenance));
            }
        }

        foreach (Match match in ModuleDeclaration().Matches(text))
        {
            var symbol = match.Groups["symbol"].Value;
            var node = $"{request.ScopeId}/{symbol}";
            var provenance = At(match.Index);

            assertions.Add(Fact(node, "has_type", "azure-module", provenance));
            assertions.Add(Fact(node, "module_path", match.Groups["path"].Value, provenance));
            assertions.Add(Fact(node, "declared_in", request.ScopeId, provenance));
        }

        var lines = text.Split('\n');
        for (var i = 0; i < lines.Length; i++)
        {
            var match = ParameterDeclaration().Match(lines[i]);
            if (!match.Success) continue;

            var name = match.Groups["name"].Value;
            var node = $"{request.ScopeId}#{name}";
            var provenance = new Provenance(fileName, $"{i + 1}:1", ExtractorId, extractorVersion, observedAt);

            assertions.Add(Fact(node, "has_type", "azure-parameter", provenance));
            assertions.Add(Fact(node, "parameter_type", match.Groups["type"].Value, provenance));
            assertions.Add(Fact(node, "declared_in", request.ScopeId, provenance));

            if (IsSecure(lines, i))
            {
                // Recorded as SECRET, never with a value. There is no code path here that reads one.
                assertions.Add(Fact(node, "is_secret", "true", provenance));
            }
        }

        var scopeProvenance = new Provenance(fileName, "1:1", ExtractorId, extractorVersion, observedAt);

        // Counted, and only when something is actually hidden. It used to fire whenever ANY name was
        // not a bare literal, which after folding would report a closed gap as an open one — and it
        // said nothing about size, which is what decides whether the residue is worth closing. It is
        // still a BOUNDARY: what remains after folding is `guid()`/`uniqueString()`, whose inputs do
        // not exist until a deployment names a subscription, and parameters with no default, whose
        // values do not exist until somebody supplies them. Neither is a defect anybody can fix
        // (DC-025, DC-050).
        if (unresolved > 0)
        {
            assertions.Add(Fact(
                scopeNode, CSharpExtractor.DisclosurePredicate,
                $"{ExtractionDisclosures.BicepExpressionsNotEvaluated} ({unresolved:N0} of {named:N0} " +
                "resource name(s) are expressions this reader does not evaluate)",
                scopeProvenance));
        }

        // How many resources a loop actually deploys depends on a collection nobody here evaluates,
        // and whether a conditional one is deployed depends on an expression. Both are disclosed so
        // a resource count is never mistaken for a deployment count — now with the two counted
        // separately, because a loop can make the declaration count wrong by any amount while a
        // conditional can only make it one too many.
        //
        // Loop COUNTS are deliberately not resolved. MEASURED: zero `[for …]` resources across every
        // .bicep file in both corpora, so evaluating collections would be a fold for a measured zero
        // — the same reading that closed `schema-changed-by-raw-sql`.
        if (loops > 0 || conditionals > 0)
        {
            assertions.Add(Fact(
                scopeNode, CSharpExtractor.DisclosurePredicate,
                $"{ExtractionDisclosures.BicepResourceCountIndeterminate} ({loops:N0} loop(s) and " +
                $"{conditionals:N0} conditional resource(s) of {resources:N0} declaration(s))",
                scopeProvenance));
        }

        return Task.FromResult(new ExtractionResult(assertions, Complete: true, []));
    }

    /// <summary>The symbols a declaration's own <c>dependsOn</c> names.</summary>
    /// <remarks>
    /// Bounded to this declaration's span. Searching forward without a bound attributes a later
    /// resource's dependencies to an earlier one, which produces edges that are individually
    /// plausible and collectively a fiction.
    /// </remarks>
    private static IEnumerable<string> DependenciesAfter(string text, int start, Func<int, int> endOf)
    {
        var end = endOf(start);
        var match = DependsOnBlock().Match(text, start);
        if (!match.Success || match.Index >= end) yield break;

        foreach (Match symbol in BareSymbol().Matches(match.Groups["body"].Value))
        {
            yield return symbol.Groups["symbol"].Value;
        }
    }

    /// <summary>The <c>name:</c> a declaration states, bounded to its own span.</summary>
    /// <remarks>
    /// Bounded for the same reason <c>dependsOn</c> is: a child resource declared with
    /// <c>parent:</c> and no <c>name:</c> would otherwise be given whatever name appeared next in
    /// the file. That is a name that is individually plausible and collectively a fiction, and it is
    /// the one thing this reader must never produce.
    /// </remarks>
    private static string NameAfter(string text, int declarationIndex, Func<int, int> endOf)
    {
        var match = NameProperty().Match(text, declarationIndex);
        if (!match.Success || match.Index >= endOf(declarationIndex)) return string.Empty;

        return match.Groups["name"].Value.Trim();
    }

    /// <summary>Whether a <c>@secure()</c> decorator sits above this parameter.</summary>
    /// <remarks>
    /// <para>Scanned backwards past other decorators and doc lines, stopping at the first line that
    /// is clearly not part of this declaration's preamble — so a <c>@secure()</c> belonging to the
    /// PREVIOUS parameter is not attributed to this one.</para>
    ///
    /// <para><b>Internal because the constant folder needs the same answer.</b> A <c>@secure()</c>
    /// parameter may legally carry a default, and folding one into a resource name would put its
    /// value in the store — through the graph rather than through the parameter's own facts, but in
    /// the store all the same. One definition, so the guarantee cannot drift between the two
    /// readers that depend on it.</para>
    /// </remarks>
    internal static bool IsSecure(string[] lines, int declarationLine)
    {
        for (var back = declarationLine - 1; back >= 0 && back >= declarationLine - 6; back--)
        {
            var previous = lines[back].Trim();
            if (previous.StartsWith("@secure", StringComparison.Ordinal)) return true;
            if (previous.Length == 0) continue;
            if (!previous.StartsWith('@') && !previous.StartsWith("'''", StringComparison.Ordinal)) return false;
        }

        return false;
    }
}
