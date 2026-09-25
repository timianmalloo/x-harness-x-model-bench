using System.Diagnostics;

namespace AiDe.Core.Ipc;

/// <summary>
/// The daemon's side of the boundary: handshake, authorization, dispatch to an operation.
/// </summary>
/// <remarks>
/// <para>Transport-free on purpose. Everything security-relevant here — version acceptance,
/// capability binding, the order the checks run in — is decided without a socket, so it can be
/// tested without one. The named-pipe layer's only job is to establish who the peer is and hand
/// bytes across; if that layer were also making authorization decisions, those decisions would only
/// be testable by standing up a pipe.</para>
///
/// <para><b>Check order is load-bearing:</b> version, then envelope shape, then workspace, then
/// capability, then epoch. Each stage assumes the previous one held, and reordering them leaks
/// information — validating a capability before checking the workspace would tell an unauthorized
/// caller whether a token is live on a workspace it has no business naming.</para>
/// </remarks>
public sealed class DaemonEndpoint
{
    private static readonly ActivitySource Telemetry = new("aide.ipc.command");

    private readonly CapabilityRegistry _capabilities;
    private readonly Func<string, long> _epochOf;
    private readonly Dictionary<string, Func<IpcRequest, IpcPeer, IpcResponse>> _operations;

    public DaemonEndpoint(
        string workspaceId,
        CapabilityRegistry capabilities,
        Func<string, long> epochOf)
    {
        WorkspaceId = workspaceId;
        _capabilities = capabilities;
        _epochOf = epochOf;
        _operations = new Dictionary<string, Func<IpcRequest, IpcPeer, IpcResponse>>(StringComparer.Ordinal);
    }

    public string WorkspaceId { get; }

    /// <summary>Registers an operation. Unregistered operations are rejected, never guessed at.</summary>
    public void Register(string operation, Func<IpcRequest, IpcPeer, IpcResponse> handler) =>
        _operations[operation] = handler;

    /// <summary>
    /// The opening exchange: agree a version and issue a capability, in that order.
    /// </summary>
    /// <remarks>
    /// Version is settled BEFORE a capability exists, so a peer speaking an unsupported protocol
    /// never obtains authority — not even briefly. The reverse order would hand out a token and then
    /// discover the holder cannot be understood.
    /// </remarks>
    public IpcResponse OpenWorkspace(IpcRequest request, IpcPeer peer)
    {
        ArgumentNullException.ThrowIfNull(request);
        ArgumentNullException.ThrowIfNull(peer);

        using var span = Telemetry.StartActivity("ipc.open_workspace");
        span?.SetTag("ipc.version", request.Version);
        span?.SetTag("peer.process_id", peer.ProcessId);

        if (!IpcVersion.IsSupported(request.Version))
        {
            span?.SetTag("ipc.rejected", IpcErrorCodes.UnsupportedVersion);
            return IpcResponse.UnsupportedVersion(request.Version);
        }

        if (!string.Equals(request.WorkspaceId, WorkspaceId, StringComparison.Ordinal))
        {
            span?.SetTag("ipc.rejected", IpcErrorCodes.WorkspaceMismatch);
            return IpcResponse.Error(
                IpcErrorCodes.WorkspaceMismatch,
                "this daemon serves a different workspace");
        }

        var epoch = _epochOf(WorkspaceId);
        var capability = _capabilities.Issue(peer, WorkspaceId, epoch);
        span?.SetTag("ipc.capability_issued", true);

        // The token rides in the payload and appears nowhere else — not in the span, not in a log.
        // The epoch travels with it because a freshly connected shell cannot ask for it: asking is a
        // command, and every command is judged against the epoch it claims.
        return IpcResponse.Success(
            new IpcOpenResult(capability.Token, epoch), WorkspaceOperations.Wire);
    }

    /// <summary>Handles a command: every gate, in order, before any operation runs.</summary>
    public IpcResponse Invoke(IpcRequest request, IpcPeer peer)
    {
        ArgumentNullException.ThrowIfNull(request);
        ArgumentNullException.ThrowIfNull(peer);

        using var span = Telemetry.StartActivity("ipc.invoke");
        span?.SetTag("ipc.operation", request.Operation);
        span?.SetTag("ipc.version", request.Version);
        span?.SetTag("command.id", request.CommandId);

        if (!IpcVersion.IsSupported(request.Version))
        {
            return Reject(span, IpcResponse.UnsupportedVersion(request.Version));
        }

        if (string.IsNullOrWhiteSpace(request.Operation) || string.IsNullOrWhiteSpace(request.CommandId))
        {
            return Reject(span, IpcResponse.Error(
                IpcErrorCodes.MalformedEnvelope,
                "operation and commandId are required on every request"));
        }

        if (!string.Equals(request.WorkspaceId, WorkspaceId, StringComparison.Ordinal))
        {
            return Reject(span, IpcResponse.Error(
                IpcErrorCodes.WorkspaceMismatch, "this daemon serves a different workspace"));
        }

        var currentEpoch = _epochOf(WorkspaceId);
        var check = _capabilities.Validate(request.Capability, peer, WorkspaceId, currentEpoch);
        if (!check.Ok)
        {
            return Reject(span, IpcResponse.Error(check.ErrorCode!, check.Reason!));
        }

        // The caller's stated epoch is checked SEPARATELY from the capability's. A capability can be
        // current while the caller is reasoning about a stale one, and acting on a command whose
        // author believed different state is the mistake the epoch fence exists to stop.
        if (request.WorkspaceEpoch != currentEpoch)
        {
            return Reject(span, IpcResponse.Error(
                IpcErrorCodes.EpochStale,
                $"command was authored against epoch {request.WorkspaceEpoch}, current is {currentEpoch}"));
        }

        if (!_operations.TryGetValue(request.Operation, out var handler))
        {
            return Reject(span, IpcResponse.Error(
                IpcErrorCodes.MalformedEnvelope, $"unknown operation '{request.Operation}'"));
        }

        return handler(request, peer);
    }

    private static IpcResponse Reject(Activity? span, IpcResponse response)
    {
        span?.SetTag("ipc.rejected", response.ErrorCode);
        span?.SetStatus(ActivityStatusCode.Error, response.ErrorCode);
        return response;
    }
}
