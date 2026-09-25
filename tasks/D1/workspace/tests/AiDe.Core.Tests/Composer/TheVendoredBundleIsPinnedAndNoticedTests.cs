using System.Security.Cryptography;
using System.Text.Json;
using AiDe.Core.Tests.Sessions;

namespace AiDe.Core.Tests.Composer;

/// <summary>
/// Security <b>C18</b> — the F4 production bundle re-fires C1–C8 — and specifically the half the hash
/// gate cannot see: <b>every package in the manifest is in <c>THIRD-PARTY-NOTICES.md</c></b>.
/// </summary>
/// <remarks>
/// <para><b>Why this is a test and not another mode of the hash gate.</b> The gate pins bytes: it
/// proves the committed bundle is the bundle that was recorded. It cannot see whether the MIT notice
/// obligation was discharged, because a notices file is prose to it. The cross-check is the one that
/// goes stale the moment the package set changes — which is exactly what F4 did, 26 packages to 24.
/// </para>
///
/// <para><b>Both directions, deliberately.</b> A package in the manifest and not in the notices is an
/// undischarged obligation; a package in the notices and not in the manifest is a notice for
/// something that is not shipped, which reads as a longer list and is a claim about a file that does
/// not exist.</para>
/// </remarks>
public sealed class TheVendoredBundleIsPinnedAndNoticedTests
{
    private sealed record ManifestFile(string Path, string Sha256, long Bytes);

    private static JsonElement Manifest() =>
        JsonDocument.Parse(RepoFiles.SourceFile(
            "src", "AiDe.App", "Web", "vendor", "vendor-manifest.json")).RootElement;

    [Fact]
    public void C18_EveryPackageInTheManifestIsNamedWithItsVersionInTheNotices()
    {
        var notices = RepoFiles.SourceFile("THIRD-PARTY-NOTICES.md");
        var packages = Manifest().GetProperty("provenance").GetProperty("packages");

        var missing = new List<string>();

        foreach (var package in packages.EnumerateArray())
        {
            var name = package.GetProperty("name").GetString()!;
            var version = package.GetProperty("version").GetString()!;

            if (!notices.Contains($"`{name}` {version}", StringComparison.Ordinal))
            {
                missing.Add($"{name}@{version}");
            }
        }

        Assert.True(
            missing.Count == 0,
            "the manifest ships package(s) that THIRD-PARTY-NOTICES.md does not name, so the MIT "
            + "notice obligation is undischarged for them:\n  " + string.Join("\n  ", missing));
    }

    [Fact]
    public void C18_TheNoticesNameNoPackageTheManifestDoesNotShip()
    {
        var notices = RepoFiles.SourceFile("THIRD-PARTY-NOTICES.md");
        var shipped = Manifest().GetProperty("provenance").GetProperty("packages")
            .EnumerateArray()
            .Select(p => $"`{p.GetProperty("name").GetString()}` {p.GetProperty("version").GetString()}")
            .ToHashSet(StringComparer.Ordinal);

        // The section's own bulleted list is the claim about what is in the bundle.
        var section = notices[notices.IndexOf("The bundled packages:", StringComparison.Ordinal)..];
        var listed = section.Split('\n')
            .Where(l => l.StartsWith("- `", StringComparison.Ordinal))
            .Select(l => l[2..].Trim())
            .ToList();

        Assert.NotEmpty(listed);
        Assert.All(listed, entry => Assert.Contains(entry, shipped));
        Assert.Equal(shipped.Count, listed.Count);
    }

    [Fact]
    public void C18_TheCommittedBytesAreTheRecordedBytesAndTheLockfileTheyCameFrom()
    {
        var manifest = Manifest();
        var root = RepoFiles.Root();

        foreach (var file in manifest.GetProperty("files").EnumerateArray())
        {
            var path = Path.Combine(root, file.GetProperty("path").GetString()!);
            Assert.True(File.Exists(path), $"the manifest lists '{path}', which is not on disk");

            var bytes = File.ReadAllBytes(path);
            Assert.Equal(file.GetProperty("bytes").GetInt64(), bytes.LongLength);
            Assert.Equal(
                file.GetProperty("sha256").GetString(),
                Convert.ToHexStringLower(SHA256.HashData(bytes)));
        }

        var provenance = manifest.GetProperty("provenance");
        var lockfile = Path.Combine(root, provenance.GetProperty("lockfile").GetString()!);
        Assert.Equal(
            provenance.GetProperty("lockfile_sha256").GetString(),
            Convert.ToHexStringLower(SHA256.HashData(File.ReadAllBytes(lockfile))));
    }

    [Fact]
    public void C18_TheProductionPinIsNotTheSpikesPin()
    {
        // Ruling 33: the spike's SHA-256 is spike evidence and is never cited as the production pin.
        var manifest = Manifest();
        var bundle = manifest.GetProperty("files").EnumerateArray().First();

        Assert.NotEqual(
            "ee3d19a44a330c43d03889ace6424732a5314073c96a36c39e83a2e1ee340981",
            bundle.GetProperty("sha256").GetString());

        Assert.Contains(
            "PRODUCTION BUNDLE",
            manifest.GetProperty("description").GetString()!,
            StringComparison.Ordinal);
    }

    [Fact]
    public void C7_TheInputSetIsNarrowedToWhatTheComposerRenders()
    {
        var names = Manifest().GetProperty("provenance").GetProperty("packages")
            .EnumerateArray()
            .Select(p => p.GetProperty("name").GetString()!)
            .ToList();

        // In, because the composer renders through them.
        Assert.Contains("@codemirror/view", names);
        Assert.Contains("@codemirror/lang-markdown", names);
        Assert.Contains("@codemirror/autocomplete", names);
        Assert.Contains("@codemirror/commands", names);

        // Out: the meta-package pulls a catalog the composer does not render, and the source viewer
        // has not landed (its re-entry trigger is recorded in the plan, not in the bundle).
        Assert.DoesNotContain("codemirror", names);
        Assert.DoesNotContain("@codemirror/search", names);
    }

    [Fact]
    public void C19_TheAdvisoryRecordIsPresentAndCarriesItsHonestLimit()
    {
        var scan = Manifest().GetProperty("provenance").GetProperty("advisory_scan");

        foreach (var field in new[]
                 {
                     "command", "working_directory", "date", "result", "raw", "raw_sha256",
                     "against_lockfile_sha256", "honest_limit",
                 })
        {
            Assert.True(scan.TryGetProperty(field, out var value), $"advisory_scan has no '{field}'");
            Assert.False(string.IsNullOrWhiteSpace(value.GetString()));
        }

        // The limit is stated rather than implied: a stored scan is a photograph, and the recurring
        // step is the control.
        Assert.Contains(
            "RECURRING STEP IS THE CONTROL",
            scan.GetProperty("honest_limit").GetString()!,
            StringComparison.Ordinal);

        // And the recurring step exists, wired into the build rather than described in a plan.
        var workflow = RepoFiles.SourceFile(".github", "workflows", "build.yml");
        Assert.Contains("python tools/verify-vendored-advisories.py", workflow, StringComparison.Ordinal);
        Assert.Contains("python tools/verify-vendored-advisories.py --self-test", workflow, StringComparison.Ordinal);
    }
}
