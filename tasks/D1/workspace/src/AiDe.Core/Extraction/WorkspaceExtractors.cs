namespace AiDe.Core.Extraction;

/// <summary>
/// What this product can extract, in one place.
/// </summary>
/// <remarks>
/// <para><b>Written because the composition was assembled by hand at every boundary, and the
/// boundaries disagreed.</b> The daemon composed C# and the fixture adapter only, so the running
/// application could not see infrastructure or schema at all — while a spike composed all four and
/// reported joins the product had no way to show. Two answers to "what does this tool read",
/// depending which entry point you asked.</para>
///
/// <para><b>And the hand-written form is easy to get wrong quietly.</b> The same spike passed its
/// extractors POSITIONALLY, which put <see cref="BicepExtractor"/> in the <c>fallback</c> slot and
/// routed every <c>bicep:</c> scope to the schema extractor. Both scopes failed, and the write-up
/// concluded the repository had no Bicep in it. It had two templates and 24 resource declarations.
/// A composition nobody can mis-order is worth more than a comment asking them not to.</para>
/// </remarks>
public static class WorkspaceExtractors
{
    /// <summary>The composition every entry point uses. Named arguments, deliberately.</summary>
    public static IExtractor Default() => new CompositeExtractor(
        csharp: new CSharpExtractor(),
        fallback: new FixtureExtractor(),
        bicep: new BicepExtractor(),
        schema: new EfSchemaExtractor(),
        python: new PythonExtractor(),
        typescript: new TypeScriptExtractor(),
        sql: new SqlSchemaExtractor(),
        knowledge: new KnowledgeExtractor());

    /// <summary>
    /// The scope-id prefix each extractor answers for, as the router reads them.
    /// </summary>
    /// <remarks>
    /// Stated so a test can assert the routing rather than trusting the constructor's parameter
    /// order — which is exactly what went wrong. Anything not listed falls through to the fallback.
    /// </remarks>
    public static IReadOnlyDictionary<string, string> RoutedKinds { get; } =
        new Dictionary<string, string>(StringComparer.Ordinal)
        {
            ["csharp:"] = "csharp",
            ["bicep:"] = "bicep",
            ["schema:"] = "schema",
            ["python:"] = "python",
            ["typescript:"] = "typescript",
            ["sql:"] = "sql",
            ["knowledge:"] = "knowledge",
        };
}
