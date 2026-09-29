using System.Text.Json;

namespace AiDe.Core.Presentation.Composer;

/// <summary>One draft as it survives a restart — every shape's retained content, and no attachment.</summary>
/// <param name="Shape">The shape that was active.</param>
/// <param name="FreeFormText">The retained free-form text.</param>
/// <param name="TemplateId">The bound template, when there was one.</param>
/// <param name="GoalValues">The goal-block field values by wire name.</param>
/// <param name="TemplateValues">The template field values by field name.</param>
public sealed record PersistedComposerDraft(
    ComposerShape Shape,
    string FreeFormText,
    string? TemplateId,
    IReadOnlyDictionary<string, string> GoalValues,
    IReadOnlyDictionary<string, IReadOnlyList<string>> TemplateValues);

/// <summary>
/// Persists composer drafts per session, so "the draft persists across restart" is a property of the
/// bytes rather than of a view model that happened not to be collected.
/// </summary>
/// <remarks>
/// <para><b>Attachment CONTENT is deliberately not persisted.</b> An attachment is file bytes the
/// operator affirmed for one send; writing them into a sidecar would put arbitrary file bodies on
/// disk with no expiry and no deletion path, which is precisely the exposure Privacy's Blocker 2 was
/// about. The draft comes back; the attachments are re-offered.</para>
///
/// <para><b>It writes under the git-ignored sidecar</b>, which is the control that stops Channel B
/// becoming Channel A by accident — <c>tools/verify-aide-gitignore.py</c> is what keeps that true.</para>
/// </remarks>
public sealed class ComposerDraftStore
{
    private static readonly JsonSerializerOptions Options = new() { WriteIndented = true };

    private readonly Lock _gate = new();

    /// <param name="workspaceRoot">The workspace whose sidecar holds the drafts.</param>
    public ComposerDraftStore(string workspaceRoot)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(workspaceRoot);
        WorkspaceRoot = workspaceRoot;
    }

    /// <summary>The workspace this store is bound to.</summary>
    public string WorkspaceRoot { get; }

    /// <summary>The sidecar file. Inside <c>.aide/</c>, and therefore git-ignored.</summary>
    public string File => Path.Combine(WorkspaceRoot, ".aide", "composer-drafts.json");

    /// <summary>Writes one session's draft, replacing whatever was there.</summary>
    public void Save(string sessionId, ComposerDraft draft)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(sessionId);
        ArgumentNullException.ThrowIfNull(draft);

        lock (_gate)
        {
            var all = ReadUnsafe();
            all[sessionId] = new PersistedComposerDraft(
                draft.Shape,
                draft.FreeFormText,
                draft.TemplateId,
                draft.GoalValues.ToDictionary(StringComparer.Ordinal),
                draft.TemplateValues.ToDictionary(StringComparer.Ordinal));

            Directory.CreateDirectory(Path.GetDirectoryName(File)!);
            System.IO.File.WriteAllText(File, JsonSerializer.Serialize(all, Options));
        }
    }

    /// <summary>Reads one session's draft back, or null when none was stored.</summary>
    /// <remarks>
    /// <b>Returns a fresh <see cref="ComposerDraft"/>, never a shared instance.</b> "Transfers
    /// one-way" is asserted against the fact that nothing downstream holds a reference the composer
    /// can see change.
    /// </remarks>
    public ComposerDraft? Load(string sessionId)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(sessionId);

        lock (_gate)
        {
            if (!ReadUnsafe().TryGetValue(sessionId, out var stored))
            {
                return null;
            }

            var draft = new ComposerDraft();
            draft.SetFreeFormText(stored.FreeFormText);

            foreach (var (field, value) in stored.GoalValues)
            {
                draft.SetGoalValue(field, value);
            }

            if (stored.TemplateId is { } templateId)
            {
                draft.UseTemplate(templateId);
            }

            foreach (var (field, values) in stored.TemplateValues)
            {
                draft.SetTemplateValue(field, values);
            }

            draft.SwitchTo(stored.Shape);
            return draft;
        }
    }

    private Dictionary<string, PersistedComposerDraft> ReadUnsafe()
    {
        if (!System.IO.File.Exists(File))
        {
            return new Dictionary<string, PersistedComposerDraft>(StringComparer.Ordinal);
        }

        try
        {
            return JsonSerializer.Deserialize<Dictionary<string, PersistedComposerDraft>>(
                System.IO.File.ReadAllText(File))
                ?? new Dictionary<string, PersistedComposerDraft>(StringComparer.Ordinal);
        }
        catch (JsonException)
        {
            // A corrupt sidecar loses drafts, not the session. Refusing to open the composer because
            // a cache file is malformed would be the worse failure.
            return new Dictionary<string, PersistedComposerDraft>(StringComparer.Ordinal);
        }
    }
}
