using System.Security.AccessControl;
using System.Security.Principal;
using System.Text;
using System.Text.Json;
using System.Text.Json.Nodes;
using AiDe.Core.Watcher;

namespace AiDe.Core.Tests.Watcher;

/// <summary>
/// Contributing AI-DE's server to <c>.mcp.json</c> without taking the file over.
/// </summary>
/// <remarks>
/// <para>The product may write here — ensuring the enlightened experience is a legitimate reason —
/// but it is <b>not AI-DE's file</b>: a user or another tool may have servers in it. So the rule is
/// create-when-absent and merge-when-present, and the tests that matter are the ones asserting what
/// is left alone.</para>
/// </remarks>
public sealed class McpConfigWriterTests : IDisposable
{
    private readonly string _root = Path.Combine(
        Path.GetTempPath(), "aide-mcpcfg-" + Guid.NewGuid().ToString("n")[..8]);

    private readonly string _server;

    public McpConfigWriterTests()
    {
        Directory.CreateDirectory(_root);
        _server = Path.Combine(_root, "AiDe.Mcp.exe");
        File.WriteAllText(_server, "not really an executable, but it exists");
    }

    public void Dispose()
    {
        try { Directory.Delete(_root, recursive: true); } catch (IOException) { /* best effort */ }
    }

    private string ConfigPath => Path.Combine(_root, McpConfigWriter.FileName);

    private JsonElement Config() =>
        JsonDocument.Parse(File.ReadAllText(ConfigPath)).RootElement.Clone();

    [Fact]
    public void WithNoFile_ItCreatesOne()
    {
        var result = McpConfigWriter.Ensure(_root, _server);

        Assert.Equal(McpConfigOutcome.Created, result.Outcome);
        Assert.Equal(_server, Config().GetProperty("mcpServers").GetProperty("aide").GetProperty("command").GetString());
    }

    /// <summary>
    /// Another tool's servers survive the merge untouched.
    /// </summary>
    /// <remarks>
    /// The property the whole design turns on. A template write would be simpler and would silently
    /// delete somebody's configuration to add a convenience — the kind of help nobody asks for twice.
    /// </remarks>
    [Fact]
    public void ItMergesBesideSomeoneElsesServers()
    {
        File.WriteAllText(ConfigPath, """
            {
              "mcpServers": {
                "sentry": { "command": "npx", "args": ["sentry-mcp"] }
              }
            }
            """);

        var result = McpConfigWriter.Ensure(_root, _server);

        Assert.Equal(McpConfigOutcome.Merged, result.Outcome);
        var servers = Config().GetProperty("mcpServers");
        Assert.Equal("npx", servers.GetProperty("sentry").GetProperty("command").GetString());
        Assert.Equal(_server, servers.GetProperty("aide").GetProperty("command").GetString());
    }

    /// <summary>Unrelated top-level keys survive too — including ones this version never heard of.</summary>
    [Fact]
    public void ItPreservesKeysItDoesNotUnderstand()
    {
        File.WriteAllText(ConfigPath, """
            {
              "someFutureKey": { "nested": [1, 2, 3] },
              "mcpServers": {}
            }
            """);

        McpConfigWriter.Ensure(_root, _server);

        Assert.Equal(3, Config().GetProperty("someFutureKey").GetProperty("nested").GetArrayLength());
    }

    /// <summary>
    /// An unparseable file is LEFT ALONE, byte for byte.
    /// </summary>
    /// <remarks>
    /// A file that fails to parse is far likelier to be mid-edit, or written by a tool this version
    /// does not understand, than to be corrupt. Rewriting it — even "helpfully", even with a backup —
    /// destroys work to add a convenience. The refusal is reported so it can be fixed, which is the
    /// only honest thing to do with a file we will not touch.
    /// </remarks>
    [Fact]
    public void AnUnparseableFileIsNotTouched()
    {
        const string mangled = "{ this is not json, someone was mid-edit";
        File.WriteAllText(ConfigPath, mangled);

        var result = McpConfigWriter.Ensure(_root, _server);

        Assert.Equal(McpConfigOutcome.RefusedUnparseable, result.Outcome);
        Assert.Equal(mangled, File.ReadAllText(ConfigPath));
        Assert.Contains("left untouched", result.Reason);
    }

    /// <summary>And a `mcpServers` that is not an object is refused for the same reason.</summary>
    /// <remarks>
    /// Replacing it would discard whatever is there. The shape is wrong for a merge, so there is no
    /// merge — not a merge that throws the obstacle away.
    /// </remarks>
    [Fact]
    public void AServersKeyOfTheWrongShapeIsRefusedRatherThanReplaced()
    {
        const string odd = """{"mcpServers": "somebody put a string here"}""";
        File.WriteAllText(ConfigPath, odd);

        var result = McpConfigWriter.Ensure(_root, _server);

        Assert.Equal(McpConfigOutcome.RefusedUnparseable, result.Outcome);
        Assert.Equal(odd, File.ReadAllText(ConfigPath));
    }

    /// <summary>A second call changes nothing and says so.</summary>
    /// <remarks>
    /// This runs on every terminal launch, so a write each time would churn the file, touch its
    /// mtime, and make every launch look like a configuration change to anything watching it.
    /// </remarks>
    [Fact]
    public void ASecondCallIsUnchanged()
    {
        McpConfigWriter.Ensure(_root, _server);
        var before = File.GetLastWriteTimeUtc(ConfigPath);

        var result = McpConfigWriter.Ensure(_root, _server);

        Assert.Equal(McpConfigOutcome.Unchanged, result.Outcome);
        Assert.Equal(before, File.GetLastWriteTimeUtc(ConfigPath));
    }

    /// <summary>A stale entry is refreshed, so moving the install fixes itself.</summary>
    [Fact]
    public void AnEntryPointingSomewhereElseIsCorrected()
    {
        File.WriteAllText(ConfigPath, """{"mcpServers":{"aide":{"command":"C:/old/AiDe.Mcp.exe"}}}""");

        var result = McpConfigWriter.Ensure(_root, _server);

        Assert.Equal(McpConfigOutcome.Merged, result.Outcome);
        Assert.Equal(_server, Config().GetProperty("mcpServers").GetProperty("aide").GetProperty("command").GetString());
    }

    /// <summary>
    /// A server binary that is not there writes NOTHING and says why.
    /// </summary>
    /// <remarks>
    /// Naming a path that does not exist would leave the agent with a server that cannot start and
    /// no reason given — worse than no entry at all, because it looks configured. This is the shape
    /// the published-layout gate exists for, one layer out.
    /// </remarks>
    [Fact]
    public void AMissingServerBinaryWritesNothing()
    {
        var result = McpConfigWriter.Ensure(_root, Path.Combine(_root, "not-there.exe"));

        Assert.Equal(McpConfigOutcome.Failed, result.Outcome);
        Assert.False(File.Exists(ConfigPath));
        Assert.Contains("not found", result.Reason);
    }

    /// <summary>No workspace writes nothing, and says that rather than throwing.</summary>
    [Theory]
    [InlineData(null)]
    [InlineData("")]
    public void NoWorkspaceWritesNothing(string? root)
    {
        var result = McpConfigWriter.Ensure(root, _server);

        Assert.Equal(McpConfigOutcome.Failed, result.Outcome);
        Assert.NotNull(result.Reason);
    }

    /// <summary>
    /// No env block is written.
    /// </summary>
    /// <remarks>
    /// The server inherits <c>AIDE_SESSION</c> from the terminal that launched the harness — verified
    /// 2026-09-04, <c>spikes/mcp-stdio-environment</c>. An env block here would be per-WORKSPACE, so
    /// every agent in it would share one identity and their board posts would be mutually
    /// misattributed. Asserted because it is the kind of thing a later "improvement" adds.
    /// </remarks>
    [Fact]
    public void NoEnvBlockIsWritten_SoIdentityStaysPerSession()
    {
        McpConfigWriter.Ensure(_root, _server);

        var entry = Config().GetProperty("mcpServers").GetProperty("aide");
        Assert.False(entry.TryGetProperty("env", out _));
    }

    /// <summary>
    /// No copy of the file survives — on the path that succeeds, OR on the path that fails.
    /// </summary>
    /// <remarks>
    /// <para><b>The temp file is the exposure, not a tidiness problem.</b> It is a byte-complete copy
    /// of every third-party <c>env</c> block in <c>.mcp.json</c>, sitting at a path none of the
    /// protections a user built were written for: a path-literal <c>.gitignore</c> line does not match
    /// <c>.mcp.json.tmp</c>, ACL hardening was applied to the other inode, and a secret-scanner path
    /// rule names the other file.</para>
    ///
    /// <para><b>And the failing move is not hypothetical.</b> It is precisely the operation that fails
    /// when a harness holds the file open — the case this writer's own comment calls a state that WILL
    /// occur rather than one that might. The success half of this case passed for as long as it has
    /// existed, while the half that matters went unasked.</para>
    ///
    /// <para>On Windows a harness holding the file open with write denied is the real shape. POSIX
    /// <c>rename()</c> does not care about open handles, so there the obstacle is a DIRECTORY standing
    /// where the file should be — a different cause reaching the same catch clause.</para>
    /// </remarks>
    [Fact]
    public void NoPartialFileIsLeftBehind()
    {
        McpConfigWriter.Ensure(_root, _server);

        Assert.Empty(Directory.GetFiles(_root, "*.tmp"));

        File.Delete(ConfigPath);
        FileStream? held = null;
        try
        {
            if (OperatingSystem.IsWindows())
            {
                File.WriteAllText(ConfigPath, SomeoneElsesSecret);
                held = new FileStream(ConfigPath, FileMode.Open, FileAccess.Read, FileShare.Read);
            }
            else
            {
                Directory.CreateDirectory(ConfigPath);
            }

            var result = McpConfigWriter.Ensure(_root, _server);

            Assert.Equal(McpConfigOutcome.Failed, result.Outcome);
            Assert.Empty(Directory.GetFiles(_root, "*.tmp"));
        }
        finally
        {
            held?.Dispose();
            if (Directory.Exists(ConfigPath))
            {
                Directory.Delete(ConfigPath);
            }
        }
    }

    /// <summary>
    /// A merge leaves the file's PROTECTION exactly as it was.
    /// </summary>
    /// <remarks>
    /// <para><b>Measured, not reasoned.</b> <c>File.Move(temporary, path, overwrite: true)</c> replaces
    /// the target's security descriptor with the freshly created temp file's directory-inherited one.
    /// A user who hardened <c>.mcp.json</c> to owner-only <i>because</i> it holds a live third-party
    /// API key had it silently unlocked, and inheritance re-enabled so that it then tracked every
    /// future change to the directory's ACL. Measured on Windows: owner-only with
    /// <c>AreAccessRulesProtected: True</c> became SYSTEM + Administrators + owner, all inherited,
    /// protection off.</para>
    ///
    /// <para><c>File.Replace</c> is the fix, because <c>ReplaceFile</c> preserves the REPLACED file's
    /// attributes and ACL rather than the replacement's, while staying atomic and same-volume — which
    /// this already is. Measured too, on the same hardened file: protection and the ACE set came back
    /// identical.</para>
    ///
    /// <para>The same mechanism applies on POSIX, where a <c>0600</c> file returns as
    /// <c>0666 &amp; ~umask</c>. This case carries no platform trait ON PURPOSE, and the Linux runner
    /// earned its keep on the first push: <c>File.Replace</c> alone does NOT preserve the mode there.
    /// It failed with <c>Expected: "UserWrite, UserRead"</c> / <c>Actual: "OtherRead, GroupRead,
    /// UserWrite, UserRead"</c> — a file the user made private, published to the group and the world.
    /// The writer now sets the mode on the replacement before the swap. Had this case been written
    /// Windows-only, the fix would have shipped half-done and looked complete.</para>
    /// </remarks>
    [Fact]
    public void AMergeLeavesTheFilesProtectionExactlyAsItWas()
    {
        File.WriteAllText(ConfigPath, SomeoneElsesSecret);
        Harden(ConfigPath);

        var before = Protection(ConfigPath);

        var result = McpConfigWriter.Ensure(_root, _server);

        Assert.Equal(McpConfigOutcome.Merged, result.Outcome);
        Assert.Equal(before, Protection(ConfigPath));
    }

    /// <summary>
    /// A third party's subtree comes back VALUE-identical, not merely present.
    /// </summary>
    /// <remarks>
    /// The merge round-trips someone else's configuration through a parser and a serializer, and the
    /// existing pass-through cases only ever asserted that a key survived. The values here are the
    /// ones a round-trip actually loses: non-ASCII, surrogate pairs, <c>\uXXXX</c> escapes that the
    /// writer re-encodes differently, an embedded quote, a tab and a newline, the empty string, and a
    /// 4 KiB value. Byte-identity is NOT the property — the writer re-indents and re-escapes on
    /// purpose — so this compares parsed trees.
    /// </remarks>
    [Fact]
    public void AThirdPartysSubtreeSurvivesValueForValue()
    {
        var original = """
            {
              "mcpServers": {
                "acme": {
                  "command": "npx",
                  "args": ["acme-mcp", "--verbose"],
                  "env": {
                    "PLAIN": "sk-live-0123456789",
                    "LITERAL_UNICODE": "é 中文 🚀",
                    "ESCAPED_UNICODE": "\u00e9 \u4e2d\u6587 \ud83d\ude80",
                    "QUOTED": "he said \"hello\" and left",
                    "CONTROL": "line\nbreak\ttab\\slash",
                    "EMPTY": "",
                    "BIG": "@BIG@"
                  }
                }
              }
            }
            """.Replace("@BIG@", new string('x', 4096), StringComparison.Ordinal);

        var expected = JsonNode.Parse(original)!["mcpServers"]!["acme"];

        File.WriteAllText(ConfigPath, original);

        var result = McpConfigWriter.Ensure(_root, _server);

        Assert.Equal(McpConfigOutcome.Merged, result.Outcome);

        var actual = JsonNode.Parse(File.ReadAllText(ConfigPath))!["mcpServers"]!["acme"];
        Assert.True(
            JsonNode.DeepEquals(expected, actual),
            $"the third party's subtree changed:\nexpected {expected}\nactual   {actual}");
    }

    /// <summary>
    /// Nothing a file can contain escapes <see cref="McpConfigWriter.Ensure"/> as an exception.
    /// </summary>
    /// <remarks>
    /// <para>This runs on every terminal launch against a file the product does not own, so the only
    /// acceptable answer to a hostile — or merely odd — file is a RESULT. Two inputs proved it was
    /// not. A duplicate property name raised <c>ArgumentException</c> from the lazily materialized
    /// <c>JsonObject</c>, thrown at the first index into the object holding it, which is outside the
    /// catch that exists for exactly this. And a JSON root that is an array or a scalar raised
    /// <c>InvalidOperationException</c> from <c>AsObject()</c>, which made the writer's own documented
    /// "exists but is not a JSON object" refusal unreachable for every input except literal
    /// <c>null</c>.</para>
    ///
    /// <para>The expected outcome is asserted rather than merely "it returned", because a case that
    /// only proved no-throw would keep passing if the writer began refusing files it should merge.</para>
    /// </remarks>
    [Theory]
    [InlineData("duplicate-top-level-key", McpConfigOutcome.RefusedUnparseable)]
    [InlineData("duplicate-server-name", McpConfigOutcome.RefusedUnparseable)]
    [InlineData("duplicate-env-key", McpConfigOutcome.RefusedUnparseable)]
    [InlineData("array-root", McpConfigOutcome.RefusedUnparseable)]
    [InlineData("number-root", McpConfigOutcome.RefusedUnparseable)]
    [InlineData("string-root", McpConfigOutcome.RefusedUnparseable)]
    [InlineData("null-root", McpConfigOutcome.RefusedUnparseable)]
    [InlineData("null-servers", McpConfigOutcome.RefusedUnparseable)]
    [InlineData("utf16-without-bom", McpConfigOutcome.RefusedUnparseable)]
    [InlineData("prototype-pollution", McpConfigOutcome.Merged)]
    [InlineData("ten-megabyte-string", McpConfigOutcome.Merged)]
    [InlineData("wrong-types", McpConfigOutcome.Merged)]
    [InlineData("byte-order-mark", McpConfigOutcome.Merged)]
    [InlineData("utf16-with-bom", McpConfigOutcome.Merged)]
    public void NoInputEscapesAsAnException(string shape, McpConfigOutcome expected)
    {
        WriteHostile(shape);

        var result = McpConfigWriter.Ensure(_root, _server);

        Assert.Equal(expected, result.Outcome);
    }

    /// <summary>
    /// A third party's key NAMES do not reach a user-visible surface.
    /// </summary>
    /// <remarks>
    /// <para>The refusal reason is announced verbatim to the workbench live region, so anything in it
    /// is on screen and in the accessibility tree. A <c>JsonException</c> raised while materializing
    /// the document names the offending property — "Duplicate property 'ACME_API_KEY' encountered
    /// during deserialization" — so pasting that message into the reason puts another vendor's secret
    /// NAMES in front of whoever is looking at the screen. Names, not values, which is why this is a
    /// Minor rather than the blocker; it is still a disclosure the user did not choose.</para>
    ///
    /// <para>The reason therefore reports the outcome and the path. The detail is kept on
    /// <c>Detail</c> for the log, so nothing is LOST — it just stops being announced.</para>
    /// </remarks>
    [Theory]
    [InlineData("duplicate-env-key")]
    [InlineData("duplicate-server-name")]
    [InlineData("malformed-at-the-env-node")]
    public void AThirdPartysKeyNamesDoNotReachAUserVisibleSurface(string shape)
    {
        WriteHostile(shape);

        var result = McpConfigWriter.Ensure(_root, _server);

        Assert.Equal(McpConfigOutcome.RefusedUnparseable, result.Outcome);
        Assert.NotNull(result.Reason);
        Assert.DoesNotContain("acme", result.Reason, StringComparison.OrdinalIgnoreCase);
        Assert.DoesNotContain("ACME_API_KEY", result.Reason, StringComparison.OrdinalIgnoreCase);
        Assert.DoesNotContain("live-key", result.Reason, StringComparison.OrdinalIgnoreCase);

        // Not announced is not the same as not recorded.
        Assert.NotNull(result.Detail);
    }

    /// <summary>A third party's entry, with a live-looking key in it.</summary>
    private const string SomeoneElsesSecret =
        """{"mcpServers":{"acme":{"command":"npx","env":{"ACME_API_KEY":"live-key-0123456789"}}}}""";

    /// <summary>Writes the named hostile shape to the config path.</summary>
    private void WriteHostile(string shape)
    {
        switch (shape)
        {
            case "duplicate-top-level-key":
                File.WriteAllText(ConfigPath, """{"mcpServers":{},"mcpServers":{"acme":{}}}""");
                break;
            case "duplicate-server-name":
                File.WriteAllText(
                    ConfigPath,
                    """{"mcpServers":{"acme":{"command":"npx"},"acme":{"command":"other"}}}""");
                break;
            case "duplicate-env-key":
                File.WriteAllText(
                    ConfigPath,
                    """{"mcpServers":{"acme":{"env":{"ACME_API_KEY":"live-key","ACME_API_KEY":"b"}}}}""");
                break;
            case "malformed-at-the-env-node":
                File.WriteAllText(
                    ConfigPath,
                    """{"mcpServers":{"acme":{"env":{"ACME_API_KEY": live-key-unquoted}}}}""");
                break;
            case "array-root":
                File.WriteAllText(ConfigPath, "[1, 2, 3]");
                break;
            case "number-root":
                File.WriteAllText(ConfigPath, "42");
                break;
            case "string-root":
                File.WriteAllText(ConfigPath, "\"someone saved a string\"");
                break;
            case "null-root":
                File.WriteAllText(ConfigPath, "null");
                break;
            case "null-servers":
                File.WriteAllText(ConfigPath, """{"mcpServers":null}""");
                break;
            case "prototype-pollution":
                File.WriteAllText(
                    ConfigPath,
                    """{"__proto__":{"polluted":true},"constructor":{"x":1},"mcpServers":{}}""");
                break;
            case "ten-megabyte-string":
                File.WriteAllText(
                    ConfigPath,
                    $$"""{"mcpServers":{},"note":"{{new string('x', 10 * 1024 * 1024)}}"}""");
                break;
            case "wrong-types":
                File.WriteAllText(
                    ConfigPath,
                    """{"mcpServers":{"acme":42},"someFutureKey":[1,"two",null,true]}""");
                break;
            case "byte-order-mark":
                File.WriteAllText(ConfigPath, """{"mcpServers":{}}""", new UTF8Encoding(true));
                break;
            case "utf16-with-bom":
                File.WriteAllText(ConfigPath, """{"mcpServers":{}}""", new UnicodeEncoding(false, true));
                break;
            case "utf16-without-bom":
                File.WriteAllText(ConfigPath, """{"mcpServers":{}}""", new UnicodeEncoding(false, false));
                break;
            default:
                throw new ArgumentOutOfRangeException(nameof(shape), shape, "No such hostile shape.");
        }
    }

    /// <summary>Owner-only with inheritance off — what a user does to a file holding a live key.</summary>
    private static void Harden(string path)
    {
        if (OperatingSystem.IsWindows())
        {
            var info = new FileInfo(path);
            var security = info.GetAccessControl();
            security.SetAccessRuleProtection(isProtected: true, preserveInheritance: false);

            foreach (var rule in security
                         .GetAccessRules(true, true, typeof(NTAccount))
                         .Cast<FileSystemAccessRule>()
                         .ToList())
            {
                security.RemoveAccessRule(rule);
            }

            security.AddAccessRule(new FileSystemAccessRule(
                WindowsIdentity.GetCurrent().Name, FileSystemRights.FullControl, AccessControlType.Allow));
            info.SetAccessControl(security);
        }
        else
        {
            File.SetUnixFileMode(path, UnixFileMode.UserRead | UnixFileMode.UserWrite);
        }
    }

    /// <summary>The file's protection, rendered as a value two observations can be compared on.</summary>
    private static string Protection(string path)
    {
        if (!OperatingSystem.IsWindows())
        {
            return File.GetUnixFileMode(path).ToString();
        }

        var security = new FileInfo(path).GetAccessControl();
        var rules = new List<string>();
        foreach (var rule in security
                     .GetAccessRules(true, true, typeof(NTAccount))
                     .Cast<FileSystemAccessRule>())
        {
            rules.Add(
                $"{rule.IdentityReference.Value}|{rule.FileSystemRights}|"
                + $"{rule.AccessControlType}|inherited={rule.IsInherited}");
        }

        rules.Sort(StringComparer.Ordinal);
        return $"protected={security.AreAccessRulesProtected};{string.Join(";", rules)}";
    }
}
