using System.IO;
using System.Text.Json;
using System.Text.Json.Serialization;
using AiDe.Core.Sessions;

namespace AiDe.Core.Presentation.Sessions;

/// <summary>
/// What a session document restores to (R13 b3): which canvas mode was active, whether the canvas
/// was split and with what, and where both splitters sat.
/// </summary>
/// <param name="SchemaVersion">Bumped when a field changes meaning; an unreadable envelope restores the default.</param>
/// <param name="ActiveModeId">The mode that was active. Restored verbatim — never re-defaulted to Console.</param>
/// <param name="SplitModeId">The mode beside it, or null when the canvas was not split.</param>
/// <param name="CanvasSplitWeight">The primary mode's share of the canvas split.</param>
/// <param name="ComposerWeight">The composer's share of the paired zone.</param>
/// <param name="CompiledPromptOpen">
/// Whether the composer's compiled-prompt disclosure was open (Ruling 96: opened once, it stays open
/// for the session document — across turns and a reopen). Absent from an envelope written before
/// the field existed, which reads as collapsed at rest (Ruling 57) — the same schema version, because
/// no existing field changes meaning.
/// </param>
public sealed record SessionDocumentEnvelope(
    [property: JsonPropertyName("schemaVersion")] int SchemaVersion,
    [property: JsonPropertyName("activeModeId")] string ActiveModeId,
    [property: JsonPropertyName("splitModeId")] string? SplitModeId,
    [property: JsonPropertyName("canvasSplitWeight")] double CanvasSplitWeight,
    [property: JsonPropertyName("composerWeight")] double ComposerWeight,
    [property: JsonPropertyName("compiledPromptOpen")] bool CompiledPromptOpen = false);

/// <summary>
/// Reads and writes one session document's <c>session-document.json</c>, beside that session's
/// config.
/// </summary>
/// <remarks>
/// <para><b>A sibling of <c>session.json</c>, never inside the reserved run subtree.</b> This is
/// document state — which pane was showing — not a run's record. The reservation
/// (<c>runs/&lt;run-id&gt;.jsonl</c>) belongs to Phase 3's <c>RunLogStore</c> and this slice must
/// leave it empty; <c>TheSessionDocumentNeverCreatesIt</c> exercises this
/// store and then asserts the reserved directory does not exist, which is the App-layer twin of
/// <c>SessionConfigStoreTests.Lifecycle_NeverWritesUnderTheReservedRunsDirectory</c> and the only
/// cover for a hard-coded literal that a token scan cannot see (Ruling 38, item 2).</para>
///
/// <para><b>An unreadable envelope restores the default rather than throwing.</b> A document that
/// refused to open because its remembered splitter position was corrupt would lose the session over
/// a cosmetic fact.</para>
/// </remarks>
public sealed class SessionDocumentStore(string workspaceRoot, string sessionId)
{
    /// <summary>The file name, beside <c>session.json</c> in the session's own directory.</summary>
    public const string FileName = "session-document.json";

    /// <summary>Bumped when a field changes meaning.</summary>
    public const int CurrentSchemaVersion = 1;

    private static readonly JsonSerializerOptions Json = new() { WriteIndented = true };

    /// <summary>Where this document's state is written.</summary>
    public string FilePath =>
        Path.Combine(SessionPaths.SessionDirectory(workspaceRoot, sessionId), FileName);

    /// <summary>Writes the envelope, creating the session directory if it is not there yet.</summary>
    public void Save(SessionDocumentEnvelope envelope)
    {
        ArgumentNullException.ThrowIfNull(envelope);

        Directory.CreateDirectory(SessionPaths.SessionDirectory(workspaceRoot, sessionId));
        File.WriteAllText(FilePath, JsonSerializer.Serialize(envelope, Json));
    }

    /// <summary>The saved envelope, or null when there is none or it cannot be read.</summary>
    public SessionDocumentEnvelope? Load()
    {
        if (!File.Exists(FilePath))
        {
            return null;
        }

        try
        {
            var envelope = JsonSerializer.Deserialize<SessionDocumentEnvelope>(File.ReadAllText(FilePath));
            return envelope?.SchemaVersion == CurrentSchemaVersion ? envelope : null;
        }
        catch (Exception error) when (error is IOException or JsonException or UnauthorizedAccessException)
        {
            return null;
        }
    }
}
