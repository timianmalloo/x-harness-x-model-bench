using System.Text.Json;
using System.Text.Json.Nodes;

namespace AiDe.Core.Presentation.Composer;

/// <summary>
/// The two audit channels a send writes, and the hard line between them.
/// </summary>
/// <remarks>
/// <para><b>The committed channel gets COUNTS ONLY.</b> It is append-only, cloned, pushed and has no
/// erasure path — <c>audit-log.py</c> contains no redaction anywhere, and <c>--supersedes</c> records
/// a correction without removing the original. So short of a history rewrite on a pushed repository
/// there is no way to take something back out of it.</para>
///
/// <para><b>What it MUST NOT contain, ever:</b> attachment contents · any absolute path · for an
/// outside-workspace file, its basename, extension, directory or content hash — <i>a hash of a
/// cloned file is a confirmable fingerprint; anyone holding a candidate copy can prove the developer
/// attached exactly that file</i> · the composed prompt text whenever it carries an attachment.</para>
///
/// <para><b><c>attach_enabled</c> rides beside the counts and makes the record self-describing.</b>
/// With attach off, a count of zero is indistinguishable from "the operator chose not to" — the
/// boolean is the difference between <i>could not</i> and <i>chose not</i>.</para>
///
/// <para><b>Channel B is machine-local and git-ignored.</b> It carries the resolved path, byte count
/// and hash, which is what makes the egress reviewable without making it permanent. Its erasure path
/// is "delete <c>.aide/</c>", which is statable and testable. <b>A blocked attach is bound by the
/// same rule in both channels: a count, never a name.</b></para>
/// </remarks>
public static class ComposerSendRecord
{
    /// <summary>Channel B's file, inside the git-ignored sidecar directory.</summary>
    public const string ChannelBFileName = "attachments.jsonl";

    /// <summary>The committed channel's record for one send. Counts, and one boolean.</summary>
    /// <param name="attachEnabled">The session's setting at send time.</param>
    /// <param name="prompt">The compiled prompt — read for its COUNTS and never carried.</param>
    /// <param name="blockedByAttachSetting">How many attaches the setting refused. A count.</param>
    public static JsonObject Committed(bool attachEnabled, CompiledPrompt prompt, int blockedByAttachSetting)
    {
        ArgumentNullException.ThrowIfNull(prompt);

        return new JsonObject
        {
            ["attach_enabled"] = attachEnabled,
            ["attachments"] = new JsonObject
            {
                ["count"] = prompt.AttachmentCount,
                ["bytes_total"] = prompt.AttachmentBytes,
                ["inside_workspace"] = prompt.InsideWorkspaceCount,
                ["outside_workspace"] = prompt.OutsideWorkspaceCount,
                ["blocked_by_setting"] = blockedByAttachSetting,
            },
        };
    }

    /// <summary>Channel B's path for a workspace.</summary>
    public static string ChannelBFile(string workspaceRoot)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(workspaceRoot);
        return Path.Combine(workspaceRoot, ".aide", ChannelBFileName);
    }

    /// <summary>
    /// Appends one line per attachment to the machine-local reviewable record.
    /// </summary>
    /// <remarks>
    /// A blocked attach writes <b>one count line and nothing else</b> — no path, no basename, no
    /// size — because C21(d) binds Channel B exactly as it binds the committed channel.
    /// </remarks>
    public static void AppendChannelB(
        string workspaceRoot,
        IReadOnlyList<ComposerAttachment> attachments,
        int blockedByAttachSetting,
        DateTimeOffset now)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(workspaceRoot);
        ArgumentNullException.ThrowIfNull(attachments);

        var file = ChannelBFile(workspaceRoot);
        Directory.CreateDirectory(Path.GetDirectoryName(file)!);

        var lines = new List<string>();

        foreach (var attachment in attachments)
        {
            lines.Add(JsonSerializer.Serialize(new JsonObject
            {
                ["ts"] = now.ToString("O"),
                ["resolved_path"] = attachment.ResolvedPath,
                ["bytes"] = attachment.Bytes,
                ["sha256"] = attachment.Sha256,
                ["outside_workspace"] = attachment.IsOutsideWorkspace,
            }));
        }

        if (blockedByAttachSetting > 0)
        {
            lines.Add(JsonSerializer.Serialize(new JsonObject
            {
                ["ts"] = now.ToString("O"),
                ["blocked_by_setting"] = blockedByAttachSetting,
            }));
        }

        if (lines.Count > 0)
        {
            File.AppendAllLines(file, lines);
        }
    }
}
