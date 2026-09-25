using System.Text;
using System.Text.Json;
using System.Text.Json.Nodes;

namespace AiDe.Core.Watcher;

/// <summary>What writing <c>.mcp.json</c> did, so the caller can say so rather than guess.</summary>
public enum McpConfigOutcome
{
    /// <summary>No file existed; one was created.</summary>
    Created,

    /// <summary>A file existed and AI-DE's entry was added or refreshed beside what was there.</summary>
    Merged,

    /// <summary>The entry was already correct. Nothing was written.</summary>
    Unchanged,

    /// <summary>The file exists and could not be parsed, so it was LEFT ALONE.</summary>
    RefusedUnparseable,

    /// <summary>There was nowhere to write, or the write failed.</summary>
    Failed,
}

/// <summary>The outcome and the path, or the reason there is none.</summary>
/// <param name="Outcome">What the write did.</param>
/// <param name="Path">The file, when there was one to name.</param>
/// <param name="Reason">The user-facing sentence. ANNOUNCED VERBATIM, so it carries nothing
/// read out of the file.</param>
/// <param name="Detail">The diagnostic detail for the log. May quote the file, so it is never
/// announced.</param>
public sealed record McpConfigResult(
    McpConfigOutcome Outcome, string? Path, string? Reason, string? Detail = null);

/// <summary>
/// Puts AI-DE's MCP server where a harness will discover it, without taking the file over.
/// </summary>
/// <remarks>
/// <para><b>The product may contribute to this file.</b> It is not AI-DE's file — a user or another
/// tool may have servers in it — but ensuring the enlightened experience is a legitimate reason to
/// write, so the rule is create-when-absent and MERGE-when-present. That is the owner's principle 4,
/// and it is the reason this class is a merge rather than a template.</para>
///
/// <para><b>An unparseable file is left alone.</b> Not rewritten, not backed up and replaced —
/// left. A file that fails to parse is far more likely to be mid-edit or written by a tool this
/// version does not understand than to be corrupt, and overwriting someone's configuration to add a
/// convenience is the kind of help nobody asks for twice. The refusal is reported so it can be
/// fixed, which is the only honest thing to do with a file we will not touch.</para>
///
/// <para><b>Only AI-DE's own key is written.</b> Every other server, and every unrelated top-level
/// key, is carried through untouched — including ones this version has never heard of.</para>
/// </remarks>
public static class McpConfigWriter
{
    /// <summary>The workspace-relative file a harness reads.</summary>
    public const string FileName = ".mcp.json";

    /// <summary>The key AI-DE owns. Everything else in the file belongs to someone else.</summary>
    public const string ServerKey = "aide";

    private const string ServersKey = "mcpServers";

    private static readonly JsonSerializerOptions Json = new() { WriteIndented = true };

    /// <summary>
    /// Reading options. <c>AllowDuplicateProperties: false</c> because the default is true, and a
    /// duplicate then surfaces as an <c>ArgumentException</c> out of the lazily built dictionary at
    /// the first index into the object holding it — which is outside the catch that exists for a bad
    /// file, and so out of <see cref="Ensure"/> entirely. Refusing at the parse gives a duplicate the
    /// same answer this class already gives any file it cannot model, by the same path.
    /// </summary>
    private static readonly JsonDocumentOptions Reading = new() { AllowDuplicateProperties = false };

    /// <summary>
    /// Ensures the workspace's <c>.mcp.json</c> offers AI-DE's server.
    /// </summary>
    /// <param name="workspaceRoot">The repository the agent will work in.</param>
    /// <param name="serverExecutablePath">The server binary, beside the shell.</param>
    public static McpConfigResult Ensure(string? workspaceRoot, string? serverExecutablePath)
    {
        if (string.IsNullOrWhiteSpace(workspaceRoot) || !Directory.Exists(workspaceRoot))
        {
            return new McpConfigResult(McpConfigOutcome.Failed, null, "No workspace is open.");
        }

        if (string.IsNullOrWhiteSpace(serverExecutablePath) || !File.Exists(serverExecutablePath))
        {
            // Naming a path that does not exist would leave the agent with a server that cannot
            // start and no reason given — worse than no entry, because it looks configured.
            return new McpConfigResult(
                McpConfigOutcome.Failed, null,
                $"The MCP server was not found at {serverExecutablePath ?? "(no path)"}.");
        }

        var path = System.IO.Path.Combine(workspaceRoot, FileName);

        JsonObject root;
        bool existed;
        try
        {
            existed = File.Exists(path);
            if (existed)
            {
                var text = File.ReadAllText(path);
                var parsed = string.IsNullOrWhiteSpace(text)
                    ? new JsonObject()

                    // `as`, not AsObject(). AsObject() THROWS on a root that is an array or a scalar,
                    // so the refusal just below was unreachable for every input except a literal
                    // `null` — the one shape the doc comment above does not single out.
                    : JsonNode.Parse(text, nodeOptions: null, documentOptions: Reading) as JsonObject;
                if (parsed is null)
                {
                    return new McpConfigResult(
                        McpConfigOutcome.RefusedUnparseable, path,
                        $"{FileName} exists but is not a JSON object, so it was left untouched. "
                        + "Fix or remove it and AI-DE will add its server on the next open.");
                }

                root = parsed;
            }
            else
            {
                root = [];
            }
        }
        catch (JsonException ex)
        {
            // The message quotes the file. A duplicate reads "Duplicate property 'ACME_API_KEY'
            // encountered during deserialization", and Reason is announced VERBATIM to the live
            // region — so pasting it here puts another vendor's secret NAMES on screen and into the
            // accessibility tree, out of a file the user never asked us to read aloud. Names, not
            // values, which is why this is minor; it is still a disclosure nobody chose. The detail
            // goes to the log instead, so it is not announced and not lost either.
            return new McpConfigResult(
                McpConfigOutcome.RefusedUnparseable, path,
                $"{FileName} could not be parsed, so it was left untouched. "
                + "Fix or remove it and AI-DE will add its server on the next open.",
                ex.Message);
        }
        catch (Exception ex) when (ex is IOException or UnauthorizedAccessException)
        {
            return new McpConfigResult(McpConfigOutcome.Failed, path, ex.Message);
        }

        if (root[ServersKey] is not JsonObject servers)
        {
            // A non-object under the key we need is someone else's data in a shape we cannot merge
            // into. Replacing it would discard it silently, so this refuses for the same reason an
            // unparseable file does.
            if (root.ContainsKey(ServersKey))
            {
                return new McpConfigResult(
                    McpConfigOutcome.RefusedUnparseable, path,
                    $"{FileName} has a '{ServersKey}' that is not an object, so it was left untouched.");
            }

            servers = [];
            root[ServersKey] = servers;
        }

        var desired = new JsonObject
        {
            ["command"] = serverExecutablePath,
            ["args"] = new JsonArray(),
            // No env block. The server inherits AIDE_SESSION from the terminal that launched the
            // harness — verified 2026-09-04, spikes/mcp-stdio-environment — and an env block here
            // would be per-WORKSPACE, giving every agent in it one shared identity.
        };

        if (servers[ServerKey] is JsonObject existing
            && existing.ToJsonString() == desired.ToJsonString())
        {
            return new McpConfigResult(McpConfigOutcome.Unchanged, path, null);
        }

        servers[ServerKey] = desired;

        // Temp-and-move: a harness may read this file at any moment, so a half-written one is a
        // state that will occur rather than one that might.
        var temporary = path + ".tmp";
        try
        {
            File.WriteAllText(temporary, root.ToJsonString(Json), new UTF8Encoding(false));

            if (File.Exists(path))
            {
                // NOT File.Move(overwrite: true). Move installs the TEMP file's permissions — freshly
                // created, so whatever the directory and umask hand out — over the target's own. A
                // user who locked .mcp.json down BECAUSE it holds a live third-party key had it
                // silently unlocked. MEASURED on Windows: owner-only with inheritance disabled came
                // back SYSTEM + Administrators + owner, every ACE inherited and protection off.
                //
                // ReplaceFile preserves the REPLACED file's attributes and ACL, stays atomic, and
                // stays same-volume — which this already is. MEASURED on the same hardened file:
                // protection and the ACE set came back identical.
                //
                // BUT THAT IS THE WINDOWS HALF ONLY. On POSIX, File.Replace does NOT carry the
                // destination's mode across — MEASURED on the Linux runner, where a 0600 target came
                // back 0644, i.e. the temp file's own creation mode survived the rename. So there the
                // mode is put on the REPLACEMENT before the swap rather than restored after it: a
                // chmod afterwards would leave a window, however short, in which a file the user made
                // private is world-readable.
                if (!OperatingSystem.IsWindows())
                {
                    File.SetUnixFileMode(temporary, File.GetUnixFileMode(path));
                }

                File.Replace(temporary, path, destinationBackupFileName: null);
            }
            else
            {
                File.Move(temporary, path);
            }
        }
        catch (Exception ex) when (ex is IOException or UnauthorizedAccessException)
        {
            return new McpConfigResult(McpConfigOutcome.Failed, path, ex.Message);
        }
        finally
        {
            // The move is exactly the operation that fails when a harness holds the file open, and
            // what a failure leaves behind is a byte-complete copy of every third-party `env` block at
            // a path none of the user's protections were written for: a path-literal .gitignore line
            // does not match `.mcp.json.tmp`, the ACL hardening was applied to the other inode, and a
            // secret-scanner path rule names the other file. On both success paths the temp file is
            // already gone and this is a no-op.
            if (File.Exists(temporary))
            {
                try
                {
                    File.Delete(temporary);
                }
                catch (Exception ex) when (ex is IOException or UnauthorizedAccessException)
                {
                    // Best effort. Replacing the write's own outcome with a cleanup failure would
                    // report the less useful of two true things.
                }
            }
        }

        return new McpConfigResult(
            existed ? McpConfigOutcome.Merged : McpConfigOutcome.Created, path, null);
    }
}
