using System.Text.Json;
using System.Text.Json.Nodes;
using System.Text.Json.Serialization;

namespace AiDe.Core.Watcher;

/// <summary>
/// One thing the product changed about a session's own claim, to be told back to that session.
/// </summary>
public sealed record RegistrationNotice(
    string SessionId, string RepositorySent, string RepositoryUsed, string Reason);

/// <summary>
/// Delivers a registration correction to the agent, as a file beside the contract log.
/// </summary>
/// <remarks>
/// <para><b>Why this exists at all.</b> The product corrects a registration that names a linked
/// worktree as its repository, because rejecting it would remove the agent from observation to
/// protect a segmentation key. But silently rewriting a registrant's claim about itself leaves it
/// sending the wrong value forever, with the correction depending permanently on our resolution
/// staying right. The correction is only defensible because this file exists.</para>
///
/// <para><b>Why not the standing file.</b> A standing appears only once there is a scored episode,
/// and a registration correction has to be readable <b>before the agent's first episode</b> —
/// otherwise the agent works a whole episode on a board nobody is on before anything tells it.
/// Worse, the standing file's <i>absence</i> is already load-bearing: it documents "you have no
/// scored episode yet", and putting a second meaning on that absence is the shape this codebase has
/// registered twice (DC-087).</para>
///
/// <para><b>Invisible to the pump, for the same two reasons as the standing.</b>
/// <c>CoordinationContractLog.ReadDirectory</c> enumerates <c>*.jsonl</c> with no
/// <c>SearchOption</c>, so top-directory-only. A notice written as <c>.jsonl</c> in the root would
/// be parsed every tick and counted MALFORMED — the feature working while the ingest counters filled
/// with corruption that was not corruption. Both properties, the extension and the depth, are
/// asserted by tests rather than assumed.</para>
///
/// <para><b>Rewritten, never appended.</b> This is a machine-written directory holding a
/// machine-read document, and the current state of a session's registration is one fact, not a
/// history. The line agreed with the concurrent session: <i>rewrite what the product alone reads;
/// append to, or leave alone, what a person may edit.</i></para>
/// </remarks>
public static class RegistrationPublisher
{
    /// <summary>The subdirectory of the coordination log that carries registration notices.</summary>
    public const string DirectoryName = "registration";

    /// <summary>The provenance marker, under the one field name used in every format.</summary>
    public const string GeneratedByField = StandingPublisher.GeneratedByField;

    /// <summary>This component's provenance value.</summary>
    public const string GeneratedBy = "ai-de/registration-publisher";

    private static readonly JsonSerializerOptions Json = new(JsonSerializerDefaults.Web)
    {
        WriteIndented = true,
        DefaultIgnoreCondition = JsonIgnoreCondition.Never,
    };

    /// <summary>
    /// Writes the notice for one session, and returns the path written.
    /// </summary>
    /// <remarks>
    /// Written via a temp file and a move, because the agent reads it on its own schedule and
    /// "in the middle of a write" is a state that will occur rather than one that might.
    /// </remarks>
    public static string Publish(string coordLogDirectory, RegistrationNotice notice)
    {
        ArgumentException.ThrowIfNullOrEmpty(coordLogDirectory);
        ArgumentNullException.ThrowIfNull(notice);

        var directory = Path.Combine(coordLogDirectory, DirectoryName);
        Directory.CreateDirectory(directory);

        // The same NTFS defence as the standing file: an agent session id is agent:<name>#<hex>, and
        // a colon on NTFS opens an ALTERNATE DATA STREAM — the write succeeds, the bytes exist, and
        // nothing enumerating the directory can see them (DC-086).
        var path = Path.Combine(directory, StandingPublisher.FileNameFor(notice.SessionId));

        var document = JsonSerializer.SerializeToNode(notice, Json)!.AsObject();
        document.Insert(0, GeneratedByField, JsonValue.Create(GeneratedBy));

        var temporary = path + ".tmp";
        File.WriteAllText(temporary, document.ToJsonString(Json));
        File.Move(temporary, path, overwrite: true);

        return path;
    }
}
