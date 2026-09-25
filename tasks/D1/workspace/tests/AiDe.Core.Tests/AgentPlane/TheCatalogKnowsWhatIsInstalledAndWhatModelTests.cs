using AiDe.Core.AgentPlane;

namespace AiDe.Core.Tests.AgentPlane;

/// <summary>
/// The accounts lane's two seam requests (2026-09-14), taken by the conductor: "installed" is the
/// catalog's own reading, one derivation for the sheet and for first use (DC-223); the model first
/// use writes into <c>engines.&lt;id&gt;.model</c> comes from the row, not from a table in a dialog (DC-224).
/// </summary>
/// <remarks>
/// <b>Red-first.</b> Neither <c>EngineCatalog.InstallRefusal</c> nor <c>EngineRow.DefaultModel</c>
/// existed: the first observed red is CS0117 / CS1061.
/// </remarks>
public sealed class TheCatalogKnowsWhatIsInstalledAndWhatModelTests : IDisposable
{
    private readonly string _root = Path.Combine(Path.GetTempPath(), "aide-catalog-installed-" + Guid.NewGuid().ToString("N")[..8]);

    public void Dispose()
    {
        if (Directory.Exists(_root)) { Directory.Delete(_root, recursive: true); }
    }

    /// <summary>An adapter whose entry module is not on disk is refused by name — the file, not a guess.</summary>
    [Fact]
    public void AnAdapterWhoseEntryIsNotOnDiskIsRefusedByName()
    {
        var refusal = EngineCatalog.InstallRefusal("claude-code", _root);

        Assert.NotNull(refusal);
        Assert.Contains(Path.Combine("@agentclientprotocol", "claude-agent-acp", "dist", "index.js"), refusal, StringComparison.Ordinal);
        Assert.Contains("not on disk", refusal, StringComparison.Ordinal);
    }

    /// <summary>The same adapter, its entry present, reads installed — null refusal.</summary>
    [Fact]
    public void AnAdapterWhoseEntryIsOnDiskIsInstalled()
    {
        var entry = Path.Combine(_root, "node_modules", "@agentclientprotocol", "claude-agent-acp", "dist", "index.js");
        Directory.CreateDirectory(Path.GetDirectoryName(entry)!);
        File.WriteAllText(entry, "// stand-in");

        Assert.Null(EngineCatalog.InstallRefusal("claude-code", _root));
    }

    /// <summary>
    /// A native engine's "installed" is its executable on PATH — never <c>Arguments[0]</c> read as a
    /// file (the sheet's local probe would have read <c>--acp</c> as a missing entry).
    /// </summary>
    [Fact]
    public void ANativeEnginesInstalledReadingIsItsExecutableNotItsFirstArgument()
    {
        var refusal = EngineCatalog.InstallRefusal(
            "copilot", _root, new NativeCommandLocator(pathEntries: [], windows: OperatingSystem.IsWindows()));

        Assert.NotNull(refusal);
        Assert.DoesNotContain("--acp", refusal, StringComparison.Ordinal);
        Assert.Contains("copilot", refusal, StringComparison.Ordinal);
    }

    /// <summary>A row that cannot launch at all reads its launch refusal, not an install one.</summary>
    [Fact]
    public void AnUnobservedRowReadsItsLaunchRefusal()
    {
        var refusal = EngineCatalog.InstallRefusal("nope", _root);

        Assert.NotNull(refusal);
        Assert.Contains("unknown engine id", refusal, StringComparison.Ordinal);
    }

    /// <summary>Every catalog row carries the model the spike observed on its wire; none is blank.</summary>
    [Theory]
    [InlineData("claude-code", "claude-sonnet-5")]
    [InlineData("codex", "gpt-6-astra")]
    [InlineData("copilot", "claude-sonnet-5")]
    [InlineData("gemini", "auto")]
    [InlineData("grok", "grok-4.6")]
    public void EveryRowCarriesTheModelObservedOnItsWire(string engineId, string model)
    {
        Assert.Equal(model, EngineCatalog.Find(engineId).DefaultModel);
    }
}
