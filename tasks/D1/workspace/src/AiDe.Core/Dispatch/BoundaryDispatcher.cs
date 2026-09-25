using System.Text;
using AiDe.Core.Facts;
using AiDe.Core.Store;

namespace AiDe.Core.Dispatch;

/// <summary>The write-ahead half of a dispatch, as answered by whoever owns the store.</summary>
/// <param name="Receipt">
/// The receipt as it now stands: an existing one when this key was already attempted, otherwise the
/// freshly written <see cref="DispatchState.Pending"/> attempt.
/// </param>
/// <param name="AlreadyAttempted">
/// True when a prior attempt was found and nothing new was written. The caller must NOT write to the
/// terminal — that is what makes a retry safe rather than a second prompt in the agent's session.
/// </param>
public sealed record DispatchBeginResult(DispatchReceipt Receipt, bool AlreadyAttempted);

/// <summary>
/// The durable half of dispatch, split so it can be answered across the daemon boundary.
/// </summary>
/// <remarks>
/// <para><b>Why this split exists.</b> D1 settled that terminal processes live in the shell while the
/// store lives in the daemon, so the two halves of a two-phase delivery are now in <i>different
/// processes</i>: only the shell can write to the pty, and only the daemon can make the attempt
/// durable. <see cref="DispatchService"/> does both in one call and remains correct in-process; this
/// is the same choreography with the side effect lifted out.</para>
///
/// <para><b>The crash window got bigger, which makes the write-ahead matter more, not less.</b>
/// In-process the window between "attempt recorded" and "outcome recorded" was a pty write. Across
/// the boundary it is a pty write plus two IPC round trips plus the possibility that the shell dies
/// while the daemon lives. Every one of those leaves a <see cref="DispatchState.Pending"/> row, which
/// <see cref="DispatchService.SweepPendingToUnknown"/> resolves to an honest
/// <see cref="DispatchState.DeliveryUnknown"/> rather than a missing row a retry would read as
/// "never sent".</para>
/// </remarks>
public sealed class BoundaryDispatcher(WorkspaceStore store)
{
    private readonly DispatchService _dispatch = new(store);

    /// <summary>
    /// Phase 1 — make the attempt durable. Runs where the STORE is.
    /// </summary>
    /// <remarks>
    /// The session-binding check deliberately does <b>not</b> happen here: this process has no
    /// session to check against. It is the caller's obligation, asserted in
    /// <see cref="BeginAndWriteAsync"/> before this is ever called, because a check performed against
    /// a value the caller also supplied would prove nothing.
    /// </remarks>
    public DispatchBeginResult Begin(DispatchCommand command)
    {
        ArgumentNullException.ThrowIfNull(command);

        // Any prior attempt wins, including a still-Pending one. Reading first is what makes a
        // retry safe, and across a boundary a retry is no longer hypothetical — a lost reply is an
        // ordinary event.
        var existing = _dispatch.ReadReceipt(command.DispatchKey);
        if (existing is not null)
        {
            return new DispatchBeginResult(existing, AlreadyAttempted: true);
        }

        if (command.WorkspaceEpoch != store.CoreEpoch)
        {
            throw new WorkspaceStoreException(DispatchErrorCodes.EpochStale,
                $"command epoch {command.WorkspaceEpoch} is not the current {store.CoreEpoch}");
        }

        using (var writer = store.BeginWrite())
        {
            writer.SavePromptRevision(command.DraftId, command.RevisionNo, command.Body);
            writer.RecordDispatchAttempt(
                command.DispatchKey, command.WorkspaceId, command.WorkspaceEpoch,
                command.DraftId, command.RevisionNo, command.SessionId, command.SessionGeneration);
            writer.Commit();
        }

        return new DispatchBeginResult(_dispatch.ReadReceipt(command.DispatchKey)!, AlreadyAttempted: false);
    }

    /// <summary>
    /// Phase 2 — record the outcome of the side effect the caller performed. Runs where the STORE is.
    /// </summary>
    /// <remarks>
    /// Finalizing a key that has already been finalized is a no-op returning the existing receipt,
    /// not an error: a retried finalize after a lost reply must not turn a delivered prompt into a
    /// failure.
    /// </remarks>
    public DispatchReceipt Finalize(string dispatchKey, DispatchState state, string? errorCode)
    {
        ArgumentException.ThrowIfNullOrEmpty(dispatchKey);

        var existing = _dispatch.ReadReceipt(dispatchKey)
            ?? throw new WorkspaceStoreException(DispatchErrorCodes.SessionUnknown,
                $"no dispatch attempt exists for key '{dispatchKey}'");

        if (existing.State != DispatchState.Pending)
        {
            return existing;
        }

        using (var writer = store.BeginWrite())
        {
            writer.RecordDispatchOutcome(dispatchKey, state, errorCode);
            writer.Commit();
        }

        return _dispatch.ReadReceipt(dispatchKey)!;
    }

    /// <summary>Maps a pty result onto the durable outcome. One place, so both hosting modes agree.</summary>
    public static (DispatchState State, string? ErrorCode) Outcome(PtyWriteResult result) => result switch
    {
        PtyWriteResult.Accepted => (DispatchState.PtyWriteAccepted, null),
        PtyWriteResult.GenerationChanged => (DispatchState.Rejected, DispatchErrorCodes.GenerationChanged),
        _ => (DispatchState.Failed, DispatchErrorCodes.WriteFailed),
    };

    /// <summary>
    /// The caller's side of the choreography: begin, write to the session it owns, finalize.
    /// </summary>
    /// <remarks>
    /// <para>Written once, here, and given the two durable phases as delegates — so the shell talking
    /// to a daemon and a core talking to itself run <b>the same ordering</b>. A second copy of this
    /// sequence for the remote case is how the two modes would drift into disagreeing about when the
    /// attempt becomes durable.</para>
    /// </remarks>
    /// <param name="readiness">
    /// Whether the session is known to be waiting for input. **Refused unless
    /// <see cref="SessionReadiness.Ready"/>**, and refused BEFORE anything is made durable.
    /// </param>
    public static async Task<DispatchReceipt> BeginAndWriteAsync(
        DispatchCommand command,
        ITerminalSession session,
        Func<DispatchCommand, CancellationToken, Task<DispatchBeginResult>> begin,
        Func<string, DispatchState, string?, CancellationToken, Task<DispatchReceipt>> finalize,
        CancellationToken cancellationToken = default,
        SessionReadiness readiness = SessionReadiness.Ready)
    {
        ArgumentNullException.ThrowIfNull(command);
        ArgumentNullException.ThrowIfNull(session);

        // Refused BEFORE the write-ahead, so a refusal leaves no durable attempt behind — there is
        // nothing to sweep to DeliveryUnknown, because nothing was attempted.
        //
        // Measured, not theoretical: dispatched into a real agent CLI showing its first-run trust
        // gate, the write was accepted and the prompt was consumed by that dialog, where the same
        // Enter that submits a prompt confirms "No, exit". PtyWriteAccepted was true about the bytes
        // and misleading about the outcome (spikes/agent-dispatch).
        if (readiness != SessionReadiness.Ready)
        {
            throw new WorkspaceStoreException(
                DispatchErrorCodes.SessionNotReady, SessionReadinessPolicy.Explain(readiness));
        }

        // Checked HERE because this is the only place that holds the real session. Sending the
        // session id across the boundary and comparing it there would compare the caller's claim
        // with the caller's claim.
        if (!string.Equals(session.SessionId, command.SessionId, StringComparison.Ordinal))
        {
            throw new WorkspaceStoreException(DispatchErrorCodes.SessionUnknown,
                $"session '{command.SessionId}' was not the supplied session '{session.SessionId}'");
        }

        var began = await begin(command, cancellationToken).ConfigureAwait(false);
        if (began.AlreadyAttempted)
        {
            return began.Receipt;
        }

        PtyWriteResult result;
        try
        {
            result = await session
                .WriteAsync(command.SessionGeneration, Encoding.UTF8.GetBytes(command.Body), cancellationToken)
                .ConfigureAwait(false);
        }
        catch (OperationCanceledException)
        {
            return await finalize(
                command.DispatchKey, DispatchState.TimedOut, DispatchErrorCodes.WriteFailed, CancellationToken.None)
                .ConfigureAwait(false);
        }

        var (state, errorCode) = Outcome(result);

        // CancellationToken.None on purpose: the write already happened, and abandoning the finalize
        // because the caller's token tripped would leave a delivered prompt recorded as Pending and
        // later swept to DeliveryUnknown — losing an outcome we actually have.
        return await finalize(command.DispatchKey, state, errorCode, CancellationToken.None)
            .ConfigureAwait(false);
    }
}
