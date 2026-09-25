using AiDe.Core.AgentPlane;

namespace AiDe.Core.Tests.AgentPlane;

/// <summary>
/// The engine's streams are UTF-8: a reply carrying an em dash and a section sign reaches the reader
/// as those characters, not as their bytes re-read through a single-byte code page.
/// </summary>
/// <remarks>
/// <b>Red-first (Ruling 87).</b> The operator's 2026-09-13 screenshot of a reply read
/// <c>â€"</c> for <c>—</c> and <c>Â§</c> for <c>§</c> — the UTF-8 bytes E2 80 94 and C2 A7 decoded
/// as a single-byte code page. <c>AcpEngineProcess.Start</c> redirected all three streams and set no
/// encoding, so <c>StandardOutput</c> read with the platform default. ACP is newline-delimited
/// UTF-8 JSON; the probe writes the bytes past its own console layer, as a Node adapter does.
/// </remarks>
public sealed class AcpEngineProcessStreamsAreUtf8Tests
{
    [Fact]
    public async Task AReplyWithAnEmDashAndASectionSignArrivesIntact()
    {
        using var engine = AcpEngineProcess.Start(
            new EngineLaunch(AcpProbeLauncher.Executable(), ["--echo-utf8"]), AppContext.BaseDirectory);

        var line = await engine.Output.ReadLineAsync().WaitAsync(TimeSpan.FromSeconds(30));

        Assert.Equal("— § compile", line);
    }
}
