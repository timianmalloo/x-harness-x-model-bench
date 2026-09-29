using System.Diagnostics;
using System.IO.Pipes;
using System.Runtime.Versioning;
using System.Text.Json;

namespace AiDe.Core.Ipc;

/// <summary>What the wire carries: which exchange this is, and its envelope.</summary>
/// <remarks>
/// The kind is separate from the operation because <c>open</c> is the exchange that <i>grants</i>
/// authority and every other one <i>spends</i> it. Making it just another operation name would put
/// the one unauthenticated entry point in the same table as the authorized ones, one typo away from
/// being reachable without a capability.
/// </remarks>
public sealed record IpcMessage(string Kind, IpcRequest Request)
{
    public const string Open = "open";
    public const string Invoke = "invoke";
}

/// <summary>Bounds on what one daemon will accept.</summary>
/// <remarks>
/// Every value is a refusal threshold rather than a tuning knob: each one is the point past which
/// the daemon stops serving rather than degrading, because a boundary that queues without limit has
/// simply moved the failure somewhere less visible.
/// </remarks>
public sealed record IpcServerOptions(
    int MaxConnections = 8,
    TimeSpan? IdleGrace = null,
    TimeSpan? StartupGrace = null,
    TimeSpan? ResponseTimeout = null)
{
    /// <summary>How long a single response may take to write before the connection is abandoned.</summary>
    /// <remarks>
    /// A client that pipelines requests and never reads its responses fills the pipe's buffer; the
    /// daemon then blocks writing, stops reading, and that listener is held for as long as the client
    /// cares to hold it. With a fixed listener pool, enough such clients make the daemon unreachable
    /// to honest shells. This bounds how long one of them can occupy a listener.
    /// </remarks>
    public TimeSpan Response => ResponseTimeout ?? TimeSpan.FromSeconds(15);

    /// <summary>How long the daemon lingers after its last client leaves.</summary>
    /// <remarks>
    /// Long enough to survive a shell restarting — otherwise every restart pays a cold start and
    /// loses warm state — and short enough that a forgotten daemon is not resident indefinitely.
    /// </remarks>
    public TimeSpan Idle => IdleGrace ?? TimeSpan.FromSeconds(30);

    /// <summary>How long the daemon waits for its first client before concluding it was orphaned.</summary>
    public TimeSpan Startup => StartupGrace ?? TimeSpan.FromSeconds(60);
}

/// <summary>
/// The named-pipe transport: establishes who the peer is, and hands bytes to the endpoint.
/// </summary>
/// <remarks>
/// <para><b>This layer decides nothing about authorization.</b> Version acceptance, capability
/// binding and the order of the checks all live in <see cref="DaemonEndpoint"/>, which is why they
/// were testable long before this existed. What belongs here is only what cannot be known without a
/// connection: who the peer is, how many of them there are, and how fast they are asking.</para>
///
/// <para><b>Identity is established twice, on purpose.</b> The pipe's ACL admits only the owner, and
/// then the peer's SID is derived from the connection and checked again. The ACL is not redundant
/// with the check, nor the check with the ACL: an ACL stops the connection existing, and the check
/// is what a test can observe — a control that nothing verifies is one nobody notices losing.</para>
///
/// <para><b>The daemon exits when nobody needs it.</b> A workspace daemon outliving every shell is
/// an orphan holding a store lock, and the user has no way to see it or reason about it. So
/// <see cref="RunAsync"/> returns — rather than looping forever — once the grace period passes with
/// no client attached.</para>
/// </remarks>
[SupportedOSPlatform("windows")]
public sealed class IpcServer
{
    private static readonly ActivitySource Telemetry = new("aide.ipc.connection");

    private static readonly JsonSerializerOptions Wire = new(JsonSerializerDefaults.Web);

    private readonly string _pipeName;
    private readonly DaemonEndpoint _endpoint;
    private readonly IpcServerOptions _options;
    private readonly string _ownerSid;

    private int _active;
    private int _served;
    private long _idleSinceTicks = DateTimeOffset.UtcNow.UtcTicks;

    /// <param name="expectedOwnerSid">
    /// The SID a peer must present. Defaults to this process's own user, which is the only correct
    /// value in production.
    /// </param>
    /// <remarks>
    /// <para><b>Why the owner is injectable at all.</b> The check that a peer's SID matches the
    /// workspace owner cannot fire in a single-user test environment: the ACL admits only this user,
    /// so every peer a test can produce is already the right one. A mutation run confirmed it — the
    /// check could be deleted outright and nothing failed, which makes it an untested control, and
    /// an untested control is not a control.</para>
    ///
    /// <para>Varying the <i>expected</i> value tests the decision honestly without needing a second
    /// user account: a server told to expect a different owner must refuse the connection it gets.
    /// The alternative was to leave the branch permanently unexercised and say so in a comment,
    /// which is how a security check quietly becomes decoration.</para>
    /// </remarks>
    public IpcServer(
        string pipeName,
        DaemonEndpoint endpoint,
        IpcServerOptions? options = null,
        string? expectedOwnerSid = null)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(pipeName);
        ArgumentNullException.ThrowIfNull(endpoint);

        _pipeName = pipeName;
        _endpoint = endpoint;
        _options = options ?? new IpcServerOptions();
        _ownerSid = expectedOwnerSid ?? IpcPipeFactory.OwnerSid();
    }

    /// <summary>Connections currently attached.</summary>
    public int ActiveConnections => Volatile.Read(ref _active);

    /// <summary>Connections accepted over this server's life. Never decreases.</summary>
    public int ServedConnections => Volatile.Read(ref _served);

    /// <summary>Connections closed because the peer was not the workspace owner.</summary>
    public long IdentityRefusals { get; private set; }

    /// <summary>Connections abandoned because the peer stopped reading its responses.</summary>
    public long StalledConnections { get; private set; }

    /// <summary>Serves until cancelled, or until the idle grace passes with no client.</summary>
    public async Task RunAsync(CancellationToken cancellationToken)
    {
        using var shutdown = CancellationTokenSource.CreateLinkedTokenSource(cancellationToken);

        var listeners = Enumerable
            .Range(0, _options.MaxConnections)
            .Select(_ => ListenAsync(shutdown.Token))
            .ToArray();

        var reaper = ReapWhenIdleAsync(shutdown);

        await Task.WhenAny(Task.WhenAll(listeners), reaper).ConfigureAwait(false);
        await shutdown.CancelAsync().ConfigureAwait(false);

        // Every listener is awaited before returning, so a caller that disposes the daemon's state
        // on return cannot pull it out from under a connection still being served.
        await Task.WhenAll(listeners.Select(Swallow)).ConfigureAwait(false);
        await Swallow(reaper).ConfigureAwait(false);
    }

    /// <summary>
    /// One listener instance: accept, serve, go back to listening.
    /// </summary>
    /// <remarks>
    /// A fixed pool rather than an accept-and-spawn loop. The pool size <i>is</i> the connection
    /// limit, enforced by the operating system: further clients wait at connect rather than being
    /// accepted and then refused. Accepting first would mean allocating a connection's worth of
    /// state for every attacker who can open a pipe.
    /// </remarks>
    private async Task ListenAsync(CancellationToken cancellationToken)
    {
        while (!cancellationToken.IsCancellationRequested)
        {
            NamedPipeServerStream pipe;

            try
            {
                pipe = IpcPipeFactory.CreateServer(_pipeName, _options.MaxConnections);
            }
            catch (IOException)
            {
                // All instances busy — another listener holds them. Nothing to do but stop; the
                // pool is already at its limit, which is the intended state.
                return;
            }

            await using (pipe.ConfigureAwait(false))
            {
                try
                {
                    await pipe.WaitForConnectionAsync(cancellationToken).ConfigureAwait(false);
                }
                catch (OperationCanceledException)
                {
                    return;
                }
                catch (IOException)
                {
                    continue; // A client vanished between connect and accept. Listen again.
                }

                Interlocked.Increment(ref _active);
                Interlocked.Increment(ref _served);

                try
                {
                    await ServeAsync(pipe, cancellationToken).ConfigureAwait(false);
                }
                finally
                {
                    Interlocked.Decrement(ref _active);

                    // Stamped when the connection ENDS rather than sampled by the reaper. A client
                    // that connects and leaves between two polls would otherwise never be observed
                    // as having been here at all, and the daemon would sit out the full startup
                    // grace instead of the short idle one — measured, not theorised.
                    Interlocked.Exchange(ref _idleSinceTicks, DateTimeOffset.UtcNow.UtcTicks);
                }
            }
        }
    }

    private async Task ServeAsync(NamedPipeServerStream pipe, CancellationToken cancellationToken)
    {
        var connectionId = Guid.NewGuid().ToString("N");

        using var span = Telemetry.StartActivity("ipc.connection");

        // Established after the first frame, not on connect: Windows refuses to impersonate a named
        // pipe client "until data has been read from that pipe". No authorization decision is made
        // before it exists — the first message is read, then identity is settled, then it is served
        // or the connection ends.
        IpcPeer? peer = null;

        while (!cancellationToken.IsCancellationRequested && pipe.IsConnected)
        {
            string? raw;

            try
            {
                raw = await IpcFraming.ReadAsync(pipe, cancellationToken).ConfigureAwait(false);
            }
            catch (InvalidDataException)
            {
                // A malformed frame means we can no longer find message boundaries. Continuing would
                // resynchronise on attacker-chosen data, so the connection ends.
                span?.SetTag("ipc.rejected", IpcErrorCodes.MalformedEnvelope);
                return;
            }
            catch (IOException)
            {
                return; // Peer hung up mid-frame.
            }

            if (raw is null)
            {
                return;
            }

            if (peer is null)
            {
                peer = IpcPipeFactory.PeerOf(pipe, connectionId);
                span?.SetTag("peer.process_id", peer.ProcessId);

                if (!string.Equals(peer.OwnerSid, _ownerSid, StringComparison.Ordinal))
                {
                    // Should be unreachable: the ACL admits only this user. Enforced anyway, because
                    // "the ACL made it impossible" is an assumption about a system call's behaviour,
                    // and this check is what would notice if it ever stopped being true.
                    IdentityRefusals++;
                    span?.SetTag("ipc.rejected", IpcErrorCodes.NotAuthorized);

                    await Respond(
                        pipe,
                        IpcResponse.Error(
                            IpcErrorCodes.NotAuthorized, "this workspace belongs to another user"),
                        cancellationToken).ConfigureAwait(false);
                    return;
                }
            }

            // ONE REQUEST AT A TIME, and that is the bound (P2-IPC-07).
            //
            // An earlier revision guarded this with a per-connection in-flight semaphore that could
            // never fire: the loop reads, serves, and only then reads again, so in-flight is one by
            // construction. A limit that cannot be reached is worse than no limit, because it reads
            // as protection — it was removed rather than made reachable by introducing concurrency
            // the design does not otherwise want.
            //
            // What bounds a flood is therefore: serial service per connection, a capped frame size,
            // and a capped number of connections. A client that writes faster than we read fills the
            // OS pipe buffer and blocks on its own write, which is backpressure applied by the
            // kernel rather than memory spent by us.
            try
            {
                await RespondWithinTimeout(pipe, Handle(raw, peer), cancellationToken)
                    .ConfigureAwait(false);
            }
            catch (IOException)
            {
                return;
            }
            catch (OperationCanceledException) when (!cancellationToken.IsCancellationRequested)
            {
                // The response could not be written in time: the peer is not reading. Abandoning the
                // connection frees the listener, which is the resource actually at stake.
                StalledConnections++;
                span?.SetTag("ipc.rejected", "ipc.response_stalled");
                return;
            }
        }
    }

    private IpcResponse Handle(string raw, IpcPeer peer)
    {
        IpcMessage? message;

        try
        {
            message = JsonSerializer.Deserialize<IpcMessage>(raw, Wire);
        }
        catch (JsonException)
        {
            return IpcResponse.Error(IpcErrorCodes.MalformedEnvelope, "the message was not valid JSON");
        }

        if (message?.Request is null)
        {
            return IpcResponse.Error(IpcErrorCodes.MalformedEnvelope, "the message carried no request");
        }

        return message.Kind switch
        {
            IpcMessage.Open => _endpoint.OpenWorkspace(message.Request, peer),
            IpcMessage.Invoke => _endpoint.Invoke(message.Request, peer),
            _ => IpcResponse.Error(
                IpcErrorCodes.MalformedEnvelope, $"unknown message kind '{message.Kind}'"),
        };
    }

    /// <summary>
    /// Writes a response, or — when it will not fit a frame — writes an error that says so.
    /// </summary>
    /// <remarks>
    /// <para><b>INV-0003.</b> The whole-graph response for a real repository serialises to
    /// <b>1,522,284 bytes</b> against a 1 MiB frame. <see cref="IpcFraming.WriteAsync"/> throws for
    /// that, the serve loop caught <see cref="IOException"/> and
    /// <see cref="OperationCanceledException"/> but not this, so the exception escaped, the
    /// connection closed with no reply, and the user was told the daemon had gone away.</para>
    ///
    /// <para>The size is checked BEFORE writing rather than caught after, because a partially
    /// written frame is not recoverable — the peer would be left reading a length prefix whose body
    /// never arrives, which is a hang rather than an error.</para>
    /// </remarks>
    private static Task Respond(Stream pipe, IpcResponse response, CancellationToken cancellationToken)
    {
        var payload = JsonSerializer.Serialize(response, Wire);

        if (System.Text.Encoding.UTF8.GetByteCount(payload) <= IpcFraming.MaxFrameBytes)
        {
            return IpcFraming.WriteAsync(pipe, payload, cancellationToken);
        }

        var refusal = JsonSerializer.Serialize(
            IpcResponse.Error(
                IpcErrorCodes.PayloadTooLarge,
                $"the response is {System.Text.Encoding.UTF8.GetByteCount(payload):N0} bytes and one " +
                $"message carries at most {IpcFraming.MaxFrameBytes:N0}; ask for less of it"),
            Wire);

        return IpcFraming.WriteAsync(pipe, refusal, cancellationToken);
    }

    /// <summary>Writes a response, giving up if the peer is not draining its end.</summary>
    private async Task RespondWithinTimeout(
        Stream pipe, IpcResponse response, CancellationToken cancellationToken)
    {
        using var deadline = CancellationTokenSource.CreateLinkedTokenSource(cancellationToken);
        deadline.CancelAfter(_options.Response);

        await Respond(pipe, response, deadline.Token).ConfigureAwait(false);
    }

    /// <summary>Ends the server once nobody has needed it for the grace period.</summary>
    /// <remarks>
    /// Polled rather than event-driven because the condition is "has been true continuously for a
    /// while", not "became true". An event on the last disconnect would fire during an ordinary
    /// shell restart and take the daemon with it.
    /// </remarks>
    private async Task ReapWhenIdleAsync(CancellationTokenSource shutdown)
    {
        var startedAt = DateTimeOffset.UtcNow;

        while (!shutdown.IsCancellationRequested)
        {
            try
            {
                await Task.Delay(TimeSpan.FromMilliseconds(100), shutdown.Token).ConfigureAwait(false);
            }
            catch (OperationCanceledException)
            {
                return;
            }

            if (ActiveConnections > 0)
            {
                continue;
            }

            // Which grace applies is decided by whether anyone has EVER connected, not by what the
            // last poll happened to see. The two are different questions, and answering the first
            // with a sample is how a short-lived client leaves the daemon waiting out a grace period
            // meant for one that was never used at all.
            var servedAnyone = ServedConnections > 0;
            var grace = servedAnyone ? _options.Idle : _options.Startup;
            var since = servedAnyone
                ? new DateTimeOffset(Interlocked.Read(ref _idleSinceTicks), TimeSpan.Zero)
                : startedAt;

            if (DateTimeOffset.UtcNow - since >= grace)
            {
                Telemetry.StartActivity("ipc.daemon_idle_exit")?.Dispose();
                await shutdown.CancelAsync().ConfigureAwait(false);
                return;
            }
        }
    }

    private static async Task Swallow(Task task)
    {
        try
        {
            await task.ConfigureAwait(false);
        }
        catch (OperationCanceledException)
        {
        }
    }
}
