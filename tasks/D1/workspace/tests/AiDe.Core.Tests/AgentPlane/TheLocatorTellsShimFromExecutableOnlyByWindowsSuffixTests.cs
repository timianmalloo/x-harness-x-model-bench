using AiDe.Core.AgentPlane;

namespace AiDe.Core.Tests.AgentPlane;

/// <summary>
/// Characterisation, not an aspiration. <see cref="NativeCommandLocator"/> tells a direct executable
/// from an npm shim <b>only by the Windows suffix</b> — <c>.exe</c> for pass 1, <c>.cmd</c> for pass 2
/// (<c>EngineCatalog.cs:141-169</c>). Off Windows both probes are the bare command name, so pass 1
/// returns whichever executable file PATH reaches first and an npm shim <b>is</b> the launch: the
/// refusals cannot fire, because there is nothing left to refuse.
/// </summary>
/// <remarks>
/// <b>Why this test exists.</b> Four locator tests state Windows scenarios verbatim in their own doc
/// comments ("measured with <c>where copilot</c>", "<c>%APPDATA%\npm\gemini.cmd</c>") and were born red
/// on the Linux half of CI at the engines join (<c>9f2044bc</c>, 2026-09-14) — never green there, so a
/// wrong-runner test rather than a regression (INV-0012 §4.1; Rulings 112, 117). Ruling 117 scopes
/// those four to <c>Platform=Windows</c> and requires this test so the Linux truth is a control rather
/// than a memoir (CI6).
/// <para>
/// <b>Residual, with its trigger.</b> On Linux <see cref="EngineCatalog.ResolveLaunch"/> would exec an
/// npm shim (a <c>#!/bin/sh</c> file) and cannot refuse one; the DC-027 hazard the refusals guard —
/// <c>cmd.exe</c> dropping stdio — is Windows-specific. Ruling 118 fixed the platform scope: v1 is
/// Windows-only by <c>docs/adr/0008-shell-host.md:67</c> and the <c>net10.0-windows</c> targets of App
/// and Daemon, and no portable process calls the launcher today. <b>Trigger:</b> a portable process
/// hosts the launcher — the reference-census gate is the tripwire, and this test is where the
/// behaviour difference is written down.
/// </para>
/// <para>
/// So: the day the locator becomes platform-independent, this test fails and names why, instead of
/// four refusal tests going quietly red on one runner for two days.
/// </para>
/// </remarks>
public sealed class TheLocatorTellsShimFromExecutableOnlyByWindowsSuffixTests
{
    private const string InstallRoot = @"C:\repo\spikes\acp-subscription-lane";

    /// <summary>
    /// `copilot` has an npm package and no observed npm launch, so on Windows its <c>.cmd</c> shim is
    /// refused by name rather than run through a shell. Off Windows the same file is simply an
    /// executable on PATH, so it resolves as the launch itself — no refusal is possible.
    /// </summary>
    [Fact]
    public void AnNpmShimIsRefusedOnWindows_AndIsItselfTheLaunchOffWindows()
    {
        using var path = new EngineCatalogTests.FakePath();
        path.AddNpmShim("copilot", "@github/copilot", "npm-loader.js");

        if (OperatingSystem.IsWindows())
        {
            var error = Assert.Throws<AgentPlaneException>(
                () => EngineCatalog.ResolveLaunch("copilot", InstallRoot, path.Locator));

            Assert.Equal(AgentPlaneErrorCodes.EngineNotOnPath, error.Code);
            Assert.Contains("shell", error.Message, StringComparison.OrdinalIgnoreCase);
        }
        else
        {
            // Derived from the fixture, never hand-written: `AddNpmShim` returns the SCRIPT beside
            // the shim, and an earlier draft compared against that by mistake — green on Windows,
            // which never reaches this arm, and red on the Linux runner. That is the very shape
            // INV-0012 diagnosed, reproduced by the test written to document it; the expected value
            // is now read off the fixture's own PATH entries, where it cannot drift.
            var shim = path.Entries
                .Select(entry => Path.Combine(entry, "copilot"))
                .First(File.Exists);

            var launch = EngineCatalog.ResolveLaunch("copilot", InstallRoot, path.Locator);

            Assert.Equal(shim, launch.FileName);
        }
    }
}
