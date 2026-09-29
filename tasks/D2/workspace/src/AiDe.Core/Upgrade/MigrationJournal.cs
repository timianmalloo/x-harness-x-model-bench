using System.Text.Json;

namespace AiDe.Core.Upgrade;

/// <summary>Where a migration had got to when it was last written down.</summary>
public enum MigrationState
{
    /// <summary>The store may be half-migrated. Nothing may assume it is readable.</summary>
    Started,

    /// <summary>The migration finished and passed its gate.</summary>
    Completed,

    /// <summary>The migration was undone and the pre-migration store restored.</summary>
    RolledBack,
}

/// <summary>One migration, as recorded on disk.</summary>
public sealed record MigrationRecord(
    string MigrationId,
    int FromSchema,
    int ToSchema,
    string SnapshotPath,
    MigrationState State,
    DateTimeOffset At);

/// <summary>
/// The durable note that says whether a migration is in flight.
/// </summary>
/// <remarks>
/// <para><b>It exists for the case where nothing gets to run.</b> Power loss, a kill, a bug that
/// takes the process out mid-migration: no cleanup handler fires, no finally block completes. What
/// survives is what was already on disk, so recovery has to be something the <i>next</i> start can
/// do from a file — and that file has to be written before the risky part, not after.</para>
///
/// <para><b>Written by atomic replace, never in place.</b> A journal updated in place can be found
/// half-written by exactly the crash it exists to survive. Writing a temporary file and renaming it
/// means a reader sees either the old record or the new one, never a torn one.</para>
///
/// <para><b>Readers must share delete for that to hold on Windows</b>, which is the part that is
/// easy to get wrong: a rename over a file another handle has open fails unless that handle opened
/// with <see cref="FileShare.Delete"/>. With the ordinary <c>File.ReadAllText</c>, a concurrent
/// reader does not see a torn file — it makes the <i>writer</i> throw instead.</para>
///
/// <para><b>Latest state only, not a log.</b> The journal answers one question — "is a migration in
/// flight?" — and an append-only file would turn that read into a parse, with the recovery path
/// depending on correctly interpreting a history.</para>
///
/// <para><b>A torn or unreadable journal reads as "nothing in flight".</b> The alternative is that
/// the recovery path is the thing that crashes after a crash. That is a deliberate bias: an
/// unreadable journal means we cannot prove a migration was running, and proceeding as though one
/// was would restore a snapshot over a store that may be fine.</para>
/// </remarks>
public sealed class MigrationJournal(string path)
{
    private static readonly JsonSerializerOptions Format =
        new(JsonSerializerDefaults.Web) { WriteIndented = true };

    /// <summary>The current record, or <c>null</c> when there is nothing to recover.</summary>
    public MigrationRecord? Read()
    {
        if (!File.Exists(path))
        {
            return null;
        }

        try
        {
            // FileShare.Delete is the load-bearing flag, and it is easy to omit. On Windows a
            // rename over a file that another handle has open FAILS unless that handle shared
            // delete — so a reader using the ordinary File.ReadAllText makes the atomic replace
            // throw, and the writer is the one that breaks. Measured: a concurrent reader produced
            // UnauthorizedAccessException from File.Move.
            using var stream = new FileStream(
                path, FileMode.Open, FileAccess.Read,
                FileShare.ReadWrite | FileShare.Delete);
            using var reader = new StreamReader(stream);

            return JsonSerializer.Deserialize<MigrationRecord>(reader.ReadToEnd(), Format);
        }
        catch (JsonException)
        {
            return null; // Torn by the crash this file exists to survive.
        }
        catch (IOException)
        {
            return null;
        }
    }

    /// <summary>Records that a migration is about to run. Call before touching the store.</summary>
    public void Begin(string migrationId, int fromSchema, int toSchema, string snapshotPath) =>
        Write(new MigrationRecord(
            migrationId, fromSchema, toSchema, snapshotPath, MigrationState.Started,
            DateTimeOffset.UtcNow));

    /// <summary>Records that the migration finished and its gate passed.</summary>
    public void Complete() => Transition(MigrationState.Completed);

    /// <summary>Records that the migration was undone.</summary>
    public void RolledBack() => Transition(MigrationState.RolledBack);

    private void Transition(MigrationState state)
    {
        var current = Read();
        if (current is null)
        {
            return; // Nothing in flight; there is no state to move.
        }

        Write(current with { State = state, At = DateTimeOffset.UtcNow });
    }

    /// <summary>
    /// Renames <paramref name="temporary"/> over <paramref name="destination"/>, retrying briefly.
    /// </summary>
    /// <remarks>
    /// <para><b>The retry is not defensive padding — it closes a real Windows behaviour.</b> When a
    /// reader still holds the previous file, the rename leaves that file <i>delete-pending</i>, and
    /// the next attempt to create the same name can fail with access-denied even though nothing is
    /// wrong. Measured here: a reader polling the journal in a loop made the writer throw
    /// <see cref="UnauthorizedAccessException"/> from <c>File.Move</c>.</para>
    ///
    /// <para>Bounded, because a retry loop with no end is a hang wearing a fix. The last attempt is
    /// allowed to throw: a journal that cannot be written is a real failure and the caller must not
    /// proceed believing it was recorded.</para>
    /// </remarks>
    private static void Replace(string temporary, string destination)
    {
        const int Attempts = 20;

        for (var attempt = 1; ; attempt++)
        {
            try
            {
                File.Move(temporary, destination, overwrite: true);
                return;
            }
            catch (Exception ex) when (
                (ex is UnauthorizedAccessException or IOException) && attempt < Attempts)
            {
                Thread.Sleep(attempt); // Backs off a little each time; total well under a second.
            }
        }
    }

    /// <summary>Replaces the journal atomically.</summary>
    /// <remarks>
    /// Temp-then-rename. A rename is atomic on NTFS, so a reader interrupted at any instant sees one
    /// whole record — writing in place would leave a window where the file is neither.
    /// </remarks>
    private void Write(MigrationRecord record)
    {
        var directory = Path.GetDirectoryName(path);
        if (!string.IsNullOrEmpty(directory))
        {
            Directory.CreateDirectory(directory);
        }

        // Unique per write: two writers sharing one temporary name would clobber each other's
        // half-written file and rename the result.
        var temporary = $"{path}.{Environment.ProcessId}.{Environment.CurrentManagedThreadId}.tmp";

        File.WriteAllText(temporary, JsonSerializer.Serialize(record, Format));
        Replace(temporary, path);
    }
}
