using System.Diagnostics;
using System.Security.Cryptography;
using System.Text;
using AiDe.Core.Facts;
using AiDe.Core.Store;

namespace AiDe.Core.Dispatch;

public static class DispatchErrorCodes
{
    public const string GenerationChanged = "AIDE-DISPATCH-GENERATION-CHANGED";
    public const string DeliveryUnknown = "AIDE-DISPATCH-DELIVERY-UNKNOWN";
    public const string EpochStale = "AIDE-AUTH-EPOCH-STALE";
    public const string SessionUnknown = "AIDE-DISPATCH-SESSION-UNKNOWN";
    public const string WriteFailed = "AIDE-DISPATCH-WRITE-FAILED";

    /// <summary>
    /// The session does not report readiness, or reports that it is not ready.
    /// </summary>
    /// <remarks>
    /// A refusal, not a failure: nothing was attempted and no receipt exists, so a retry once the
    /// session is ready is a first attempt rather than a duplicate.
    /// </remarks>
    public const string SessionNotReady = "AIDE-DISPATCH-SESSION-NOT-READY";
}

/// <summary>A user-confirmed request to transfer one immutable prompt revision to one session.</summary>
public sealed record DispatchCommand(
    string WorkspaceId,
    long WorkspaceEpoch,
    CallerPrincipal Caller,
    string CommandId,
    string DraftId,
    int RevisionNo,
    string Body,
    string SessionId,
    long SessionGeneration)
{
    /// <summary>
    /// Derived from <see cref="CommandId"/>, so the command and dispatch idempotency namespaces are
    /// one. Two namespaces would let a retry miss the receipt it was meant to find.
    /// </summary>
    public string DispatchKey { get; } = Convert.ToHexStringLower(
        SHA256.HashData(Encoding.UTF8.GetBytes($"dispatch{WorkspaceId}{CommandId}")))[..32];
}

/// <summary>
/// Prompt delivery under a write-ahead two-phase receipt (ADR-0010).
/// </summary>
/// <remarks>
/// Pattern: Write-Ahead Receipt / Two-Phase Delivery (LOA P8 — idempotency at side-effect boundaries).
/// A terminal cannot atomically acknowledge a write and persist a store receipt, so recording the
/// receipt *after* the write leaves a crash window in which no receipt exists: the state reads
/// `NotRecorded`, a protocol-conformant retry treats it as never-sent, and a duplicate consequential
/// prompt lands in the agent session. Committing the attempt first turns that window into an honest
/// `DeliveryUnknown` instead.
/// </remarks>
public sealed class DispatchService(WorkspaceStore store)
{
    private static readonly ActivitySource Activity = new("aide.terminal.session");

    /// <summary>
    /// Returns the existing receipt if this dispatch key was ever attempted — including a still
    /// `Pending` one — and otherwise performs the two-phase delivery. Never re-executes.
    /// </summary>
    public async Task<DispatchReceipt> DispatchAsync(
        DispatchCommand command, ITerminalSession session, CancellationToken cancellationToken = default)
    {
        using var activity = Activity.StartActivity("aide.terminal.session");
        activity?.SetTag("command.id", command.CommandId);
        activity?.SetTag("core.epoch", command.WorkspaceEpoch);

        // 1. Any prior attempt wins. Reading the receipt FIRST is what makes a retry safe.
        var existing = ReadReceipt(command.DispatchKey);
        if (existing is not null)
        {
            activity?.SetTag("outcome", $"existing:{existing.State}");
            return existing;
        }

        // 2. Revalidate the binding. A failure here happened before any attempt, so it records a
        //    command rejection rather than a dispatch attempt — nothing was attempted.
        if (command.WorkspaceEpoch != store.CoreEpoch)
        {
            throw new WorkspaceStoreException(DispatchErrorCodes.EpochStale,
                $"command epoch {command.WorkspaceEpoch} is not the current {store.CoreEpoch}");
        }

        if (!string.Equals(session.SessionId, command.SessionId, StringComparison.Ordinal))
        {
            throw new WorkspaceStoreException(DispatchErrorCodes.SessionUnknown,
                $"session '{command.SessionId}' was not the supplied session '{session.SessionId}'");
        }

        // 3. WRITE-AHEAD: the attempt is durable BEFORE any byte can leave the process.
        using (var writer = store.BeginWrite())
        {
            writer.SavePromptRevision(command.DraftId, command.RevisionNo, command.Body);
            writer.RecordDispatchAttempt(
                command.DispatchKey, command.WorkspaceId, command.WorkspaceEpoch,
                command.DraftId, command.RevisionNo, command.SessionId, command.SessionGeneration);
            writer.Commit();
        }

        // 4. The side effect. A process death anywhere in here leaves the attempt Pending, which is
        //    exactly what recovery resolves — deliberately NOT wrapped in a catch-all, because
        //    swallowing a fatal here would fabricate an outcome we do not have.
        PtyWriteResult result;
        try
        {
            result = await session
                .WriteAsync(command.SessionGeneration, Encoding.UTF8.GetBytes(command.Body), cancellationToken)
                .ConfigureAwait(false);
        }
        catch (OperationCanceledException)
        {
            Finalize(command.DispatchKey, DispatchState.TimedOut, DispatchErrorCodes.WriteFailed);
            return ReadReceipt(command.DispatchKey)!;
        }

        // 5. Append the outcome.
        var (state, errorCode) = result switch
        {
            PtyWriteResult.Accepted => (DispatchState.PtyWriteAccepted, (string?)null),
            PtyWriteResult.GenerationChanged => (DispatchState.Rejected, DispatchErrorCodes.GenerationChanged),
            _ => (DispatchState.Failed, DispatchErrorCodes.WriteFailed),
        };

        Finalize(command.DispatchKey, state, errorCode);
        activity?.SetTag("outcome", state.ToString());
        return ReadReceipt(command.DispatchKey)!;
    }

    /// <summary>
    /// Recovery. Resolves every attempt that never recorded an outcome to <see cref="DispatchState.DeliveryUnknown"/>.
    /// Run at core startup — this is what converts a crash window into an honest state instead of a
    /// missing row that a retry would read as "never sent".
    /// </summary>
    public int SweepPendingToUnknown()
    {
        List<string> pending;
        using (var reader = store.BeginRead())
        {
            pending = [.. reader.PendingDispatchKeys()];
        }

        if (pending.Count == 0)
        {
            return 0;
        }

        using var writer = store.BeginWrite();
        foreach (var key in pending)
        {
            writer.RecordDispatchOutcome(key, DispatchState.DeliveryUnknown, DispatchErrorCodes.DeliveryUnknown);
        }

        writer.Commit();
        return pending.Count;
    }

    public DispatchReceipt? ReadReceipt(string dispatchKey)
    {
        using var reader = store.BeginRead();
        return reader.ReadDispatchReceipt(dispatchKey);
    }

    private void Finalize(string dispatchKey, DispatchState state, string? errorCode)
    {
        using var writer = store.BeginWrite();
        writer.RecordDispatchOutcome(dispatchKey, state, errorCode);
        writer.Commit();
    }
}
