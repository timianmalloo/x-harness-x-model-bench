using System.Reflection;
using AiDe.Core.Facts;

public sealed class ImportOriginRuleHiddenTests
{
    // Any pre-existing type in AiDe.Core is enough to anchor the assembly; EvidenceAssertion
    // (AiDe.Core.Facts) already exists on the base workspace, unlike the type under test.
    private static readonly Assembly Core = typeof(EvidenceAssertion).Assembly;

    private static Type RequiredType(string name)
    {
        var type = Core.GetType($"AiDe.Core.Extraction.{name}");
        Assert.NotNull(type);
        return type!;
    }

    private static MethodInfo ClassifyMethod()
    {
        var method = RequiredType("ImportOriginRule").GetMethod("Classify", BindingFlags.Public | BindingFlags.Static);
        Assert.NotNull(method);
        return method!;
    }

    /// <summary>Invokes Classify and returns the resulting enum member's name, without the test
    /// project needing a compile-time reference to the (not-yet-existing) ImportOrigin type.</summary>
    private static string ClassifyName(string? language, string? specifier, IEnumerable<string>? workspaceModuleIds)
    {
        var ids = workspaceModuleIds is null ? null : new HashSet<string>(workspaceModuleIds, StringComparer.Ordinal);
        var result = ClassifyMethod().Invoke(null, [language, specifier, ids]);
        Assert.NotNull(result);
        return result!.ToString()!;
    }

    private static Exception InnerOf(Action call) =>
        Assert.Throws<TargetInvocationException>(call).InnerException!;

    [Theory]
    [InlineData("python", "os", "Builtin")]
    [InlineData("python", "sys", "Builtin")]
    [InlineData("python", "urllib.request", "Builtin")]
    [InlineData("node", "fs", "Builtin")]
    [InlineData("node", "node:fs/promises", "Builtin")]
    public void ClassifiesRuntimeAndStandardLibraryModulesAsBuiltin(string language, string specifier, string expected)
    {
        Assert.Equal(expected, ClassifyName(language, specifier, []));
    }

    [Theory]
    [InlineData("python", ".sibling")]
    [InlineData("python", "..pkg.mod")]
    [InlineData("node", "./sibling")]
    [InlineData("node", "../pkg/mod")]
    [InlineData("node", "/abs/path")]
    public void ClassifiesRelativeOrPathShapedSpecifiersAsWorkspaceEvenWhenUnknown(string language, string specifier)
    {
        Assert.Equal("Workspace", ClassifyName(language, specifier, []));
    }

    [Fact]
    public void ClassifiesAnExactWorkspaceModuleIdAsWorkspace()
    {
        Assert.Equal("Workspace", ClassifyName("python", "mypkg.util", ["mypkg.util", "other"]));
        Assert.Equal("Workspace", ClassifyName("node", "@scope/local", ["@scope/local"]));
    }

    [Fact]
    public void DoesNotNormalizeBetweenSpecifierTextAndModuleIdText()
    {
        // "mypkg/util" (slash form) is present, but the specifier is "mypkg.util" (dot form): no
        // cross-format match, so this is External, not Workspace.
        Assert.Equal("External", ClassifyName("python", "mypkg.util", ["mypkg/util"]));
    }

    [Theory]
    [InlineData("python", "requests")]
    [InlineData("python", "numpy")]
    [InlineData("node", "lodash")]
    [InlineData("node", "left-pad")]
    public void ClassifiesUnknownBareSpecifiersAsExternal(string language, string specifier)
    {
        Assert.Equal("External", ClassifyName(language, specifier, []));
    }

    [Fact]
    public void BuiltinRuleOutranksWorkspaceMembershipForTheSameSpecifier()
    {
        // "os" is stdlib; even if a workspace module happens to be named "os", the specifier is
        // still Builtin because the builtin rule is evaluated before workspace membership.
        Assert.Equal("Builtin", ClassifyName("python", "os", ["os"]));
    }

    [Fact]
    public void RejectsAnUnknownLanguage()
    {
        var inner = InnerOf(() => ClassifyMethod().Invoke(null, ["ruby", "os", new HashSet<string>()]));
        Assert.IsType<ArgumentException>(inner);
        Assert.Contains("language", ((ArgumentException)inner).ParamName);
    }

    [Fact]
    public void RejectsAnEmptySpecifier()
    {
        var inner = InnerOf(() => ClassifyMethod().Invoke(null, ["python", "", new HashSet<string>()]));
        Assert.IsType<ArgumentException>(inner);
        Assert.Equal("specifier", ((ArgumentException)inner).ParamName);
    }

    [Fact]
    public void RejectsNullArguments()
    {
        Assert.IsType<ArgumentNullException>(InnerOf(() => ClassifyMethod().Invoke(null, [null, "os", new HashSet<string>()])));
        Assert.IsType<ArgumentNullException>(InnerOf(() => ClassifyMethod().Invoke(null, ["python", null, new HashSet<string>()])));
        Assert.IsType<ArgumentNullException>(InnerOf(() => ClassifyMethod().Invoke(null, ["python", "os", null])));
    }
}
