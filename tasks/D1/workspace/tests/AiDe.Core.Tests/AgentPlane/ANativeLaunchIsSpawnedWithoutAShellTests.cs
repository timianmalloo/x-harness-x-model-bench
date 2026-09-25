using AiDe.Core.AgentPlane;

namespace AiDe.Core.Tests.AgentPlane;

/// <summary>
/// A native engine's launch is spawned exactly as an adapter's is: no shell, no window, UTF-8 on all
/// three redirected streams, the arguments as a list — DC-170's and DC-177's rules hold for the
/// second launch path because the spawn never learns which path produced the launch.
/// </summary>
/// <remarks>
/// <see cref="AcpEngineProcess.StartInfoFor"/> is the factored seam that makes this assertable
/// without starting a process; the real spawn of each engine is
/// <c>TheEnginesAnswerInitializeOnTheWireTests</c>. The account's enterprise host reaches the
/// child through the same <c>environment</c> parameter a compile's output cap does.
/// </remarks>
public sealed class ANativeLaunchIsSpawnedWithoutAShellTests
{
    [Fact]
    public void ANativeLaunchGetsNoShellNoWindowAndUtf8Streams()
    {
        var launch = new EngineLaunch(@"C:\tools\copilot.exe", ["--acp"]);

        var info = AcpEngineProcess.StartInfoFor(launch, Path.GetTempPath());

        Assert.Equal(@"C:\tools\copilot.exe", info.FileName);
        Assert.Equal(["--acp"], info.ArgumentList);
        Assert.Equal(string.Empty, info.Arguments);
        Assert.False(info.UseShellExecute);
        Assert.True(info.CreateNoWindow);
        Assert.True(info.RedirectStandardInput);
        Assert.True(info.RedirectStandardOutput);
        Assert.True(info.RedirectStandardError);
        Assert.Equal("utf-8", info.StandardInputEncoding!.WebName);
        Assert.Equal("utf-8", info.StandardOutputEncoding!.WebName);
        Assert.Equal("utf-8", info.StandardErrorEncoding!.WebName);
        Assert.Empty(info.StandardOutputEncoding.GetPreamble());
    }

    [Fact]
    public void AnNpmDeliveredNativeLaunchKeepsItsScriptAndArgumentsInOrder()
    {
        var launch = new EngineLaunch("node", [@"C:\npm\node_modules\@google\gemini-cli\bundle\gemini.js", "--acp"]);

        var info = AcpEngineProcess.StartInfoFor(launch, Path.GetTempPath());

        Assert.Equal("node", info.FileName);
        Assert.Equal([@"C:\npm\node_modules\@google\gemini-cli\bundle\gemini.js", "--acp"], info.ArgumentList);
    }

    [Fact]
    public void TheAccountsHostReachesTheChildAsTheCatalogsVariable()
    {
        var account = new ProviderAccount("work", AccountHealth.Ready, Host: "mycompany.ghe.com");
        var environment = EngineCatalog.LaunchEnvironment(EngineCatalog.Find("copilot"), account);

        var info = AcpEngineProcess.StartInfoFor(new EngineLaunch(@"C:\tools\copilot.exe", ["--acp"]), Path.GetTempPath(), environment);

        Assert.Equal("mycompany.ghe.com", info.Environment["COPILOT_GH_HOST"]);
    }
}
