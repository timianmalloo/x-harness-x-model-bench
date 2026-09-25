using System.IO.Pipes;
using System.Runtime.Versioning;
using System.Text.Json;

namespace AiDe.Core.Ipc;

/// <summary>
/// The shell's side of the boundary.
/// </summary>
/// <remarks>
/// <para><b>Holds the capability and nothing else.</b> The token exists only in memory here and is
/// attached to every request; it is never written anywhere, because a capability on disk is a file
/// whose theft equals the authority it carries.</para>
///
/// <para><b>Serialises its own requests.</b> A pipe is one stream, so two overlapping writes would
/// interleave frames and the daemon would resynchronise on data that was never a length prefix.
/// One outstanding exchange at a time is not a limitation to work around — it is what makes the
/// framing sound.</para>
/// </remarks>
[SupportedOSPlatform("windows")]
public sealed class IpcClient : IAsyncDisposable
{
    private static readonly JsonSerializerOptions Wire = new(JsonSerializerDefaults.Web);

    private readonly NamedPipeClientStream _pipe;
    private readonly SemaphoreSlim _exchange = new(1, 1);

    private string? _capability;
    private bool _disposed;

    private IpcClient(NamedPipeClientStream pipe) => _pipe = pipe;

    /// <summary>The capability this connection holds, once a workspace has been opened.</summary>
    public bool IsOpen => _capability is not null;

    /// <summary>The epoch the daemon reported at handshake, which every request is judged against.</summary>
    public long Epoch { get; private set; }

    /// <summary>Connects to the daemon serving <paramref name="pipeName"/>.</summary>
    public static async Task<IpcClient> ConnectAsync(
        string pipeName, TimeSpan timeout, CancellationToken cancellationToken)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(pipeName);

        var pipe = IpcPipeFactory.CreateClient(pipeName);

        try
        {
            await pipe.ConnectAsync((int)timeout.TotalMilliseconds, cancellationToken).ConfigureAwait(false);
        }
        catch
        {
            await pipe.DisposeAsync().ConfigureAwait(false);
            throw;
        }

        return new IpcClient(pipe);
    }

    /// <summary>
    /// Performs the handshake and keeps the capability it returns.
    /// </summary>
    /// <remarks>
    /// The token is stored rather than handed back so a caller cannot accidentally log it, put it in
    /// a span, or pass it somewhere it outlives the connection it is bound to.
    /// </remarks>
    public async Task<IpcResponse> OpenWorkspaceAsync(
        string workspaceId, long epoch, CancellationToken cancellationToken)
    {
        var response = await ExchangeAsync(
            new IpcMessage(
                IpcMessage.Open,
                new IpcRequest(IpcVersion.Current, "open", Guid.NewGuid().ToString("N"),
                    workspaceId, epoch, null, null)),
            cancellationToken).ConfigureAwait(false);

        if (!response.Ok)
        {
            return response;
        }

        var opened = IpcPayload.Read<IpcOpenResult>(response.Payload, Wire);
        if (opened is null)
        {
            return IpcResponse.Error(
                IpcErrorCodes.MalformedEnvelope, "the daemon's handshake response was not readable");
        }

        _capability = opened.Capability;
        Epoch = opened.Epoch;

        return response;
    }

    /// <summary>Invokes an operation, attaching the held capability.</summary>
    public Task<IpcResponse> InvokeAsync(
        string operation,
        string commandId,
        string workspaceId,
        long epoch,
        JsonElement? payload,
        CancellationToken cancellationToken) =>
        ExchangeAsync(
            new IpcMessage(
                IpcMessage.Invoke,
                new IpcRequest(
                    IpcVersion.Current, operation, commandId, workspaceId, epoch, _capability, payload)),
            cancellationToken);

    /// <summary>Sends a raw message. Exists so tests can send what a correct client never would.</summary>
    internal Task<IpcResponse> SendAsync(IpcMessage message, CancellationToken cancellationToken) =>
        ExchangeAsync(message, cancellationToken);

    private async Task<IpcResponse> ExchangeAsync(IpcMessage message, CancellationToken cancellationToken)
    {
        ObjectDisposedException.ThrowIf(_disposed, this);

        await _exchange.WaitAsync(cancellationToken).ConfigureAwait(false);

        try
        {
            await IpcFraming
                .WriteAsync(_pipe, JsonSerializer.Serialize(message, Wire), cancellationToken)
                .ConfigureAwait(false);

            var raw = await IpcFraming.ReadAsync(_pipe, cancellationToken).ConfigureAwait(false);

            if (raw is null)
            {
                // The daemon closed rather than answering. Reported as a response, not an exception:
                // "the daemon went away" is an outcome a caller must handle either way, and an
                // exception here would make the ordinary case of a daemon exiting look exceptional.
                return IpcResponse.Error(
                    IpcErrorCodes.TransportClosed, "the daemon closed the connection without responding");
            }

            return JsonSerializer.Deserialize<IpcResponse>(raw, Wire)
                ?? IpcResponse.Error(IpcErrorCodes.MalformedEnvelope, "the daemon sent an empty response");
        }
        finally
        {
            _exchange.Release();
        }
    }

    public async ValueTask DisposeAsync()
    {
        if (_disposed)
        {
            return;
        }

        _disposed = true;
        _capability = null; // In memory only, and not for longer than the connection.

        await _pipe.DisposeAsync().ConfigureAwait(false);
        _exchange.Dispose();
    }
}
