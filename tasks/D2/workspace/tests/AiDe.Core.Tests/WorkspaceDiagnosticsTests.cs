using AiDe.Core.Health;
using AiDe.Core.Presentation;
using AiDe.Core.Upgrade;

namespace AiDe.Core.Tests;

/// <summary>
/// What the shell reports about the daemon behind it.
/// </summary>
/// <remarks>
/// The case that matters is <b>rollback unavailability</b>. Keeping the previous build is what makes
/// rollback possible at all, so a fresh install has nothing to go back to — and an operator told
/// only "rollback" with no state would discover that at the worst possible moment.
/// </remarks>
public sealed class WorkspaceDiagnosticsTests : IDisposable
{
    private readonly string _root = Path.Combine(
        Path.GetTempPath(), "aide-diag", Guid.NewGuid().ToString("N"));

    public WorkspaceDiagnosticsTests() => Directory.CreateDirectory(_root);

    private DaemonInstallation Installation() => new(_root);

    private string StageBuild(string marker)
    {
        var source = Path.Combine(_root, "staged", Guid.NewGuid().ToString("N"));
        Directory.CreateDirectory(source);
        File.WriteAllText(Path.Combine(source, "AiDe.Daemon.dll"), marker);
        return source;
    }

    [Fact]
    public void WithNoInstallation_ItSaysSoRatherThanImplyingAVersion()
    {
        var text = new WorkspaceDiagnosticsViewModel(null, null).Read().Describe();

        Assert.Contains("running in place", text, StringComparison.OrdinalIgnoreCase);
        Assert.Contains("Rollback: unavailable", text, StringComparison.Ordinal);
    }

    [Fact]
    public void ASingleInstalledVersionReportsRollbackUnavailable()
    {
        // The trap this exists to avoid: an operator who believes rollback is always there.
        var installation = Installation();
        installation.Install("1.0.0", StageBuild("one"));
        installation.Repoint("1.0.0");

        var state = new WorkspaceDiagnosticsViewModel(installation, null).Read();

        Assert.Equal("1.0.0", state.CurrentVersion);
        Assert.Null(state.RollbackTarget);
        Assert.Contains("Rollback: unavailable", state.Describe(), StringComparison.Ordinal);
    }

    [Fact]
    public void WithAPreviousVersionItNamesWhatRollbackWouldReturnTo()
    {
        var installation = Installation();
        installation.Install("1.0.0", StageBuild("one"));
        installation.Install("1.1.0", StageBuild("two"));
        installation.Repoint("1.1.0");

        var state = new WorkspaceDiagnosticsViewModel(installation, null).Read();

        Assert.Equal("1.1.0", state.CurrentVersion);
        Assert.Equal("1.0.0", state.RollbackTarget);
    }

    [Fact]
    public void AfterARollbackTheTargetIsTheNEWERBuild_NotTheOneWeJustLeft()
    {
        // After rolling back, "current" is an OLDER version — so "the second newest" would name the
        // build that was just rolled away from and offer to reinstate the failure.
        var installation = Installation();
        installation.Install("1.0.0", StageBuild("one"));
        installation.Install("1.1.0", StageBuild("two"));
        installation.Repoint("1.0.0");

        var state = new WorkspaceDiagnosticsViewModel(installation, null).Read();

        Assert.Equal("1.0.0", state.CurrentVersion);
        Assert.Equal("1.1.0", state.RollbackTarget);
    }

    [Fact]
    public void OpenIncidentsAreReported_AndAcknowledgedOnesAreNot()
    {
        var path = Path.Combine(_root, "incidents.jsonl");
        var sidecar = new HealthIncidentSidecar(path);
        sidecar.Record("extraction.failed", "csharp:A:net10.0", "broken", DateTimeOffset.UtcNow);
        sidecar.Record("extraction.timeout", "csharp:B:net10.0", "slow", DateTimeOffset.UtcNow);
        sidecar.Acknowledge("extraction.failed", "csharp:A:net10.0");

        var state = new WorkspaceDiagnosticsViewModel(null, sidecar).Read();

        Assert.Single(state.Incidents);
        Assert.Contains("extraction.timeout", state.Incidents[0], StringComparison.Ordinal);
    }

    [Fact]
    public void TheMcpToolListIsReported_SoTheCapabilityIsDiscoverable()
    {
        // The tools were registered and tested for a whole phase without being visible anywhere in
        // the product. A capability nobody can find is one nobody uses.
        var text = new WorkspaceDiagnosticsViewModel(null, null).Read().Describe();

        Assert.Contains("describe", text, StringComparison.Ordinal);
        Assert.Contains("read-only, local-only", text, StringComparison.Ordinal);
    }

    public void Dispose()
    {
        try { Directory.Delete(_root, recursive: true); } catch (IOException) { }
    }
}
