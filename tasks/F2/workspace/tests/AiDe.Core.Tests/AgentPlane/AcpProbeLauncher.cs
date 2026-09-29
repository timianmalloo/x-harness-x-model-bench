using System.Diagnostics;

namespace AiDe.Core.Tests.AgentPlane;

/// <summary>
/// Locates and runs <c>AiDe.Core.AcpProbe</c>, the ACP client's own harness.
/// </summary>
/// <remarks>
/// Found relative to the test binaries, the same way <c>TerminalHostLauncher</c> finds the ConPTY
/// helper. It is a build-order dependency of this project, so an absence here means the solution was
/// not built — which is reported loudly rather than skipped (DC-012).
/// </remarks>
internal static class AcpProbeLauncher
{
    /// <summary>The helper executable, built alongside the tests.</summary>
    internal static string Executable()
    {
        var root = Path.GetFullPath(Path.Combine(
            AppContext.BaseDirectory, "..", "..", "..", "..", "AiDe.Core.AcpProbe", "bin"));

        // The configuration is read from THIS assembly's own path, not preferred. A machine that has
        // built both would otherwise run a stale Release probe against Debug tests - a control
        // reporting on a binary that is not the one under test, which is the DC-012 shape.
        var configuration = new DirectoryInfo(AppContext.BaseDirectory).Parent?.Name ?? "Debug";
        var name = "AiDe.Core.AcpProbe" + (OperatingSystem.IsWindows() ? ".exe" : string.Empty);
        var candidate = Path.Combine(root, configuration, "net10.0", name);

        Assert.True(
            File.Exists(candidate),
            $"the ACP probe helper was not built. Expected it at:\n  {candidate}\n"
            + "Build the solution rather than the test project alone.");

        return candidate;
    }

    /// <summary>Runs the helper to completion and returns its exit code and stderr.</summary>
    internal static (int ExitCode, string StandardError) Run(params string[] arguments)
    {
        var info = new ProcessStartInfo(Executable())
        {
            RedirectStandardError = true,
            RedirectStandardOutput = true,
            UseShellExecute = false,
            CreateNoWindow = true,
        };

        foreach (var argument in arguments)
        {
            info.ArgumentList.Add(argument);
        }

        using var process = Process.Start(info)!;
        var stderr = process.StandardError.ReadToEndAsync();
        var stdout = process.StandardOutput.ReadToEndAsync();

        Assert.True(process.WaitForExit(120_000), "the ACP probe did not finish");
        stdout.GetAwaiter().GetResult();
        return (process.ExitCode, stderr.GetAwaiter().GetResult());
    }
}
