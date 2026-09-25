using AiDe.Core.Dispatch;
using AiDe.Core.Facts;

namespace AiDe.Core.Ipc;

/// <summary>
/// The two durable phases of prompt dispatch, as a caller sees them.
/// </summary>
/// <remarks>
/// <para>Separate from <see cref="IWorkspaceCommands"/> because it is a different obligation: a
/// workspace can answer projections and re-index without being able to record a dispatch, and a
/// shell that cannot dispatch should discover that by the capability being absent rather than by a
/// call failing.</para>
///
/// <para><b>The side effect is deliberately not here.</b> Writing to the terminal is the shell's
/// job — it owns the process (D1) — so this interface covers only what must be durable, and
/// <see cref="BoundaryDispatcher.BeginAndWriteAsync"/> is what orders the three steps.</para>
/// </remarks>
public interface IWorkspaceDispatch
{
    /// <summary>The epoch a command must carry to be accepted.</summary>
    Task<long> EpochAsync(CancellationToken cancellationToken);

    /// <summary>Phase 1 — make the attempt durable before any byte leaves the shell.</summary>
    Task<DispatchBeginResult> DispatchBeginAsync(DispatchCommand command, CancellationToken cancellationToken);

    /// <summary>Phase 2 — record the outcome the shell observed.</summary>
    Task<DispatchReceipt> DispatchFinalizeAsync(
        string dispatchKey, DispatchState state, string? errorCode, CancellationToken cancellationToken);
}
