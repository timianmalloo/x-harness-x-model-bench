using System.Runtime.Versioning;

namespace AiDe.Core.Tests;

/// <summary>
/// The helper a test launches is the one built in the test's own configuration — never a stale
/// binary from another one that happens to be on disk.
/// </summary>
/// <remarks>
/// <b>Red-first, observed 2026-09-12 (X-2b's join):</b> ten helper-launching tests failed with
/// <i>exit 4: no console window — launch with CREATE_NEW_CONSOLE</i>, an exit code the helper's
/// source no longer contained, because <c>LocateHelper</c> preferred a Release helper built
/// three hours earlier over the Debug one the test step had just built. A test that runs a
/// different program from the one it was built with is not measuring the change under test.
/// </remarks>
[Trait("Platform", "Windows")]
[SupportedOSPlatform("windows")]
public sealed class TerminalHostLauncherConfigurationTests
{
    [Fact]
    public void TheHelperIsTheOneBuiltInTheTestsOwnConfiguration()
    {
        var configuration = TerminalHostLauncher.ConfigurationOf(AppContext.BaseDirectory);
        var helper = TerminalHostLauncher.LocateHelper();

        Assert.Contains($"{Path.DirectorySeparatorChar}{configuration}{Path.DirectorySeparatorChar}", helper, StringComparison.Ordinal);
        var other = configuration == "Debug" ? "Release" : "Debug";
        Assert.DoesNotContain($"{Path.DirectorySeparatorChar}{other}{Path.DirectorySeparatorChar}", helper, StringComparison.Ordinal);
    }

    [Theory]
    [InlineData(@"C:\x\tests\AiDe.Core.Tests\bin\Debug\net10.0\", "Debug")]
    [InlineData(@"C:\x\tests\AiDe.Core.Tests\bin\Release\net10.0\", "Release")]
    [InlineData("/x/tests/AiDe.Core.Tests/bin/Debug/net10.0/", "Debug")]
    public void TheConfigurationIsReadFromTheOutputDirectory(string directory, string expected)
        => Assert.Equal(expected, TerminalHostLauncher.ConfigurationOf(directory));
}
