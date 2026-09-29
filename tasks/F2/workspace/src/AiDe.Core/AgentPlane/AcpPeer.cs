using System.Globalization;
using System.Text.Json;
using System.Text.Json.Nodes;
using System.Threading.Channels;

namespace AiDe.Core.AgentPlane;

/// <summary>
/// The bounds an ACP peer runs under. Every one of them is a number a reader can find.
/// </summary>
/// <remarks>
/// <b>Stated, not buried.</b> A cap or a timeout written inline at its call site is a decision that
/// only the person who wrote it knows was made. These four are the whole of the peer's resource
/// story: how much it will buffer for one frame, how many events it will hold before it pushes back,
/// and how long it will wait for each of the two very different kinds of answer.
/// </remarks>
public sealed record AcpPeerOptions
{
    /// <summary>
    /// The default event-queue depth.
    /// </summary>
    /// <remarks>
    /// Matches <c>IngestHost</c>'s default for the same reason: it is deep enough that an ordinary
    /// burst never reaches the reader, and shallow enough that a consumer which has genuinely
    /// stopped is felt rather than absorbed into memory.
    /// </remarks>
    public const int DefaultEventQueueCapacity = 1024;

    /// <summary>
    /// The largest single frame the splitter will assemble, in characters.
    /// </summary>
    /// <remarks>
    /// <b>Measured against the corpus, not guessed.</b> The largest frame the pinned adapter
    /// actually wrote across all 88 captured lines is 24,692 characters
    /// (<c>frames/read.jsonl</c>), so this is roughly 170x the observed maximum — large enough that
    /// no honest frame reaches it, small enough that a peer emitting an unterminated stream cannot
    /// exhaust memory before anything notices.
    /// </remarks>
    public const int DefaultMaxFrameChars = 4 * 1024 * 1024;

    /// <summary>
    /// How long an ordinary request may go unanswered before the peer calls the child hung.
    /// </summary>
    /// <remarks>
    /// <c>initialize</c> and <c>session/new</c> are handshake calls: the adapter answers them in
    /// milliseconds or it is not going to. Sixty seconds is generous enough to absorb a cold Node
    /// start and a credential-store read, and short enough that a wedged adapter surfaces as a
    /// refusal rather than as a lane that is "still working".
    /// </remarks>
    public static readonly TimeSpan DefaultRequestTimeout = TimeSpan.FromSeconds(60);

    /// <summary>
    /// How long a <c>session/prompt</c> may run.
    /// </summary>
    /// <remarks>
    /// A prompt is a whole agent turn — it may compile, run a suite, and edit files — so the
    /// handshake bound is wrong for it by orders of magnitude. Fifteen minutes is a bound, not an
    /// expectation: its purpose is that a lane whose engine has died quietly still ends.
    /// </remarks>
    public static readonly TimeSpan DefaultPromptTimeout = TimeSpan.FromMinutes(15);

    /// <summary>How many run events may be queued before the reader is pushed back.</summary>
    public int EventQueueCapacity { get; init; } = DefaultEventQueueCapacity;

    /// <summary>The largest single frame the splitter will assemble.</summary>
    public int MaxFrameChars { get; init; } = DefaultMaxFrameChars;

    /// <summary>The default per-request answer bound.</summary>
    public TimeSpan RequestTimeout { get; init; } = DefaultRequestTimeout;

    /// <summary>The bound a whole agent turn runs under.</summary>
    public TimeSpan PromptTimeout { get; init; } = DefaultPromptTimeout;
}

/// <summary>
/// One normalized run event, with the measurement of how long normalizing it took.
/// </summary>
/// <remarks>
/// <para><b>The latency is nullable because the measurement can be absent.</b> A measurement path
/// degrades to "not recorded", never to a plausible wrong number (IO12): a zero here would read as
/// "instantaneous" and would be indistinguishable from "nobody stamped the receipt".</para>
///
/// <para><b>It is carried on the event rather than accumulated in the peer.</b> A peer-held list of
/// every latency is an unbounded allocation for the life of a lane; travelling with the event lets
/// the consumer keep exactly what it needs — which for the SLO evaluation is a running p50/p95, and
/// for a surface is nothing at all.</para>
/// </remarks>
/// <param name="Event">The normalized envelope.</param>
/// <param name="ReceivedAt">When the line was read, or <c>null</c> when nothing stamped it.</param>
/// <param name="NormalizationLatency">Publish minus receipt, or <c>null</c> when there is no receipt.</param>
public sealed record ObservedRunEvent(RunEvent Event, DateTimeOffset? ReceivedAt, TimeSpan? NormalizationLatency)
{
    /// <summary>What an absent measurement reads as. Never <c>"0 ms"</c>.</summary>
    public const string NotRecorded = "not recorded";

    /// <summary>Builds the observation, computing the latency only when there is a receipt to compute it from.</summary>
    public static ObservedRunEvent From(RunEvent evt, DateTimeOffset? receivedAt, DateTimeOffset normalizedAt)
        => new(evt, receivedAt, receivedAt is { } stamped ? normalizedAt - stamped : null);

    /// <summary>The latency in words a person or a log line can read.</summary>
    public string DescribeLatency()
        => NormalizationLatency is { } elapsed
            ? elapsed.TotalMilliseconds.ToString("0.###", CultureInfo.InvariantCulture) + " ms"
            : NotRecorded;
}

/// <summary>
/// The bounded queue every normalized run event passes through: overflow applies
/// <b>backpressure</b>, and any drop is counted and surfaced.
/// </summary>
/// <remarks>
/// <para><b>The counting idiom is <c>IngestHost</c>'s</b> (<c>IngestHost.cs</c>, the
/// <c>itemDropped</c> callback): a drop is a coverage-gap signal, so it is a number somebody can
/// read rather than an absence nobody can.</para>
///
/// <para><b>The overflow policy is deliberately NOT <c>ConPtyTerminalSession</c>'s.</b> That session
/// uses <c>DropOldest</c>, which is right there — <c>ITerminalSession</c> states terminal bytes are
/// ephemeral by contract and must never reach the fact store. ACP events are the opposite: spec
/// §7.1 calls the run log "the truth", so a silent drop is data loss in the durable record. This
/// queue blocks the reader instead, which backs the pressure up the pipe to the engine — the engine
/// stalls on a full stdout buffer, which is exactly the right thing for it to do.</para>
///
/// <para><b>A drop is still modelled</b>, because "cannot drop" is not a property a bounded queue
/// can have: the lane stops and whatever was waiting is lost. What is required is that it is
/// counted and named when it happens.</para>
/// </remarks>
public sealed class AcpEventQueue
{
    private readonly Channel<ObservedRunEvent> _channel;
    private readonly Action<string> _diagnostics;
    private long _published;
    private long _backpressureWaits;
    private long _dropped;

    /// <param name="capacity">How many events may be held before a publish waits.</param>
    /// <param name="diagnostics">Where a wait or a drop is reported. Defaults to stderr.</param>
    public AcpEventQueue(int capacity, Action<string>? diagnostics = null)
    {
        ArgumentOutOfRangeException.ThrowIfLessThan(capacity, 1);

        Capacity = capacity;
        _diagnostics = diagnostics ?? Console.Error.WriteLine;
        _channel = Channel.CreateBounded<ObservedRunEvent>(
            new BoundedChannelOptions(capacity)
            {
                FullMode = BoundedChannelFullMode.Wait,
                SingleReader = true,
                SingleWriter = true,
            });
    }

    /// <summary>The configured depth.</summary>
    public int Capacity { get; }

    /// <summary>How many events reached the queue.</summary>
    public long Published => Interlocked.Read(ref _published);

    /// <summary>How many publishes had to wait for room. Every one of them is a visible slow-consumer signal.</summary>
    public long BackpressureWaits => Interlocked.Read(ref _backpressureWaits);

    /// <summary>How many events were lost. Any value above zero is a hole in what §7.1 calls the truth.</summary>
    public long Dropped => Interlocked.Read(ref _dropped);

    /// <summary>The consumer side.</summary>
    public ChannelReader<ObservedRunEvent> Reader => _channel.Reader;

    /// <summary>
    /// Publishes one event, waiting for room rather than discarding anything.
    /// </summary>
    /// <exception cref="OperationCanceledException">
    /// The lane is stopping while this event was waiting for room. The loss is counted and named
    /// first, so the cancellation never hides it.
    /// </exception>
    public async ValueTask PublishAsync(ObservedRunEvent observed, CancellationToken cancellationToken = default)
    {
        ArgumentNullException.ThrowIfNull(observed);

        if (_channel.Writer.TryWrite(observed))
        {
            Interlocked.Increment(ref _published);
            return;
        }

        Interlocked.Increment(ref _backpressureWaits);
        _diagnostics(
            $"acp: the run-event queue is full at {Capacity}; applying backpressure to the engine "
            + $"(seq {observed.Event.Seq}, kind '{observed.Event.Kind}')");

        try
        {
            await _channel.Writer.WriteAsync(observed, cancellationToken);
            Interlocked.Increment(ref _published);
        }
        catch (Exception error) when (error is OperationCanceledException or ChannelClosedException)
        {
            Interlocked.Increment(ref _dropped);
            _diagnostics(
                $"acp: DROPPED run event seq {observed.Event.Seq} kind '{observed.Event.Kind}' — the queue "
                + "closed while it waited for room; the run log for this lane is now incomplete");

            if (error is OperationCanceledException)
            {
                throw;
            }
        }
    }

    /// <summary>No more events will be published. A consumer waiting on the reader stops.</summary>
    public void Complete() => _channel.Writer.TryComplete();
}

/// <summary>A snapshot of what the peer has seen. Every field is a fact somebody can act on.</summary>
/// <param name="FramesRead">Complete, well-formed frames.</param>
/// <param name="MalformedFrames">Lines that arrived whole and were not a JSON object.</param>
/// <param name="OverLongFrames">Lines refused for exceeding <see cref="AcpPeerOptions.MaxFrameChars"/>.</param>
/// <param name="UnterminatedTailChars">Characters left in the splitter when the stream ended.</param>
/// <param name="Notifications">Inbound frames with a method and no id. Correctly unanswered.</param>
/// <param name="InboundRequestsAnswered">Inbound requests answered with a result.</param>
/// <param name="UnknownMethodsAnswered">Inbound requests answered <c>-32601</c>.</param>
/// <param name="UnmatchedResponses">Replies carrying an id this peer never sent.</param>
public sealed record AcpPeerCounters(
    long FramesRead,
    long MalformedFrames,
    long OverLongFrames,
    long UnterminatedTailChars,
    long Notifications,
    long InboundRequestsAnswered,
    long UnknownMethodsAnswered,
    long UnmatchedResponses);

/// <summary>
/// A bidirectional ACP peer: newline-delimited JSON-RPC over a child process's stdio, where the
/// agent calls <b>us</b> as often as we call it.
/// </summary>
/// <remarks>
/// <para><b>A server loop, not a request/response client.</b> The spike established that the
/// adapter initiates <c>session/request_permission</c>, <c>fs/read_text_file</c>,
/// <c>fs/write_text_file</c>, <c>terminal/create|output|wait_for_exit|kill|release</c> and
/// <c>elicitation/create</c>. A client that only sends and waits deadlocks the first time the agent
/// asks it something — which is on the first edit.</para>
///
/// <para><b>The correlation is the part that had to be designed.</b> <c>probe-write.js</c>
/// dispatched on <c>m.id === 1 | 2 | 3</c>: three literals for three known requests. Two rules
/// replace it, and both are about presence rather than value —</para>
/// <list type="number">
///   <item>a frame carrying <c>method</c> is <b>inbound</b>, whatever its id; everything else is a
///   reply to something this peer sent;</item>
///   <item>an inbound frame is a <b>request</b> when the <c>id</c> <i>key is present and not JSON
///   null</i> — never when the id is "truthy". <c>frames/write.jsonl:12</c> is a real
///   <c>session/request_permission</c> with <c>"id":0</c>, and a truthiness test answers it never.
///   </item>
/// </list>
/// <para>Replies are matched through a pending table keyed on the id's canonical text, so ids are
/// correlated by identity rather than by arrival order — the corpus already answers out of order
/// relative to nothing, and a real session interleaves.</para>
///
/// <para><b>Normalization happens before dispatch, and that ordering is load-bearing.</b> Each frame
/// becomes a <see cref="RunEvent"/> and is published <i>before</i> the peer answers anything. That
/// is Ruling 11's required ordinal: the run event for a tool call is observable before the response
/// to the next inbound request for the same call id, on any hardware, with no stopwatch.</para>
///
/// <para><b>Inherited from <c>src/AiDe.Mcp/Program.cs</c>:</b> stdout is the protocol and every
/// diagnostic goes to stderr; one bad message never kills the loop; an unknown method is
/// <i>answered</i>, not ignored, because silence looks like a hung peer.</para>
/// </remarks>
public sealed class AcpPeer
{
    // mirrors src/AiDe.Mcp/Program.cs framing
    //
    // simplify: the NDJSON loop discipline, the Result/Error envelope builders and the -32601 case
    // are COPIED from the MCP server rather than shared. Ceiling: two stdio JSON-RPC consumers in
    // this repository, each owning its own copy, with a grep-able marker in both files. Upgrade
    // trigger: a THIRD stdio JSON-RPC consumer appears, or the first defect that must be fixed in
    // both places. Until then extraction would be a generic JsonRpcPeer with one real user, and the
    // two are not the same shape anyway - the MCP server has a single peer that never initiates, so
    // it has no outbound ids, no pending table and no write serialization at all.
    private static readonly JsonSerializerOptions Json = new() { WriteIndented = false };

    private readonly TextReader _input;
    private readonly TextWriter _output;
    private readonly AcpRunEventMapper _mapper;
    private readonly TimeProvider _time;
    private readonly AcpPeerOptions _options;
    private readonly Action<string> _diagnostics;

    private readonly SemaphoreSlim _writeLock = new(1, 1);
    private readonly Lock _pendingGate = new();
    private readonly Dictionary<string, PendingRequest> _pending = new(StringComparer.Ordinal);

    private long _nextRequestId;
    private long _framesRead;
    private long _malformedFrames;
    private long _overLongFrames;
    private long _unterminatedTailChars;
    private long _notifications;
    private long _inboundRequestsAnswered;
    private long _unknownMethodsAnswered;
    private long _unmatchedResponses;

    /// <param name="input">The child's stdout.</param>
    /// <param name="output">The child's stdin. This is the protocol channel; nothing else may reach it.</param>
    /// <param name="mapper">The one ACP-to-envelope mapper. Frames are normalized before they are acted on.</param>
    /// <param name="time">Stamps receipt and publication. Defaults to the system clock.</param>
    /// <param name="options">The peer's bounds. Defaults to <see cref="AcpPeerOptions"/>'s stated values.</param>
    /// <param name="diagnostics">Where everything that is not protocol goes. Defaults to stderr.</param>
    public AcpPeer(
        TextReader input,
        TextWriter output,
        AcpRunEventMapper mapper,
        TimeProvider? time = null,
        AcpPeerOptions? options = null,
        Action<string>? diagnostics = null)
    {
        ArgumentNullException.ThrowIfNull(input);
        ArgumentNullException.ThrowIfNull(output);
        ArgumentNullException.ThrowIfNull(mapper);

        _input = input;
        _output = output;
        _mapper = mapper;
        _time = time ?? TimeProvider.System;
        _options = options ?? new AcpPeerOptions();
        _diagnostics = diagnostics ?? Console.Error.WriteLine;
        Events = new AcpEventQueue(_options.EventQueueCapacity, _diagnostics);
    }

    /// <summary>Every frame this peer read, normalized, in receipt order.</summary>
    public AcpEventQueue Events { get; }

    /// <summary>
    /// The handler for inbound requests. Returning <c>null</c> means "not handled", which is
    /// answered <c>-32601</c> rather than ignored.
    /// </summary>
    public Func<string, JsonObject?, JsonNode?>? InboundHandler { get; set; }

    /// <summary>
    /// What the adapter last said about how it is authenticated, or <c>null</c> when it has not said.
    /// </summary>
    /// <remarks>
    /// Observed off the wire as <c>_auth/status_update</c> goes past, because a measurement of where
    /// requests will bill is the only version-robust evidence there is — an environment API key
    /// outranks the stored subscription inside the adapter and bills silently.
    /// </remarks>
    public ObservedAuthStatus? ObservedAuth { get; private set; }

    /// <summary>Everything the peer has counted.</summary>
    public AcpPeerCounters Counters => new(
        Interlocked.Read(ref _framesRead),
        Interlocked.Read(ref _malformedFrames),
        Interlocked.Read(ref _overLongFrames),
        Interlocked.Read(ref _unterminatedTailChars),
        Interlocked.Read(ref _notifications),
        Interlocked.Read(ref _inboundRequestsAnswered),
        Interlocked.Read(ref _unknownMethodsAnswered),
        Interlocked.Read(ref _unmatchedResponses));

    /// <summary>
    /// Reads the child's stdout until end of stream, normalizing and dispatching every frame.
    /// </summary>
    /// <remarks>
    /// <para><b>The splitter is hand-rolled rather than <c>ReadLineAsync</c></b> for exactly one
    /// reason: <c>ReadLineAsync</c> will buffer a line of any length, so a child that never emits a
    /// newline is an unbounded allocation with no error. This one enforces
    /// <see cref="AcpPeerOptions.MaxFrameChars"/>, resynchronizes at the next newline after refusing
    /// an over-long line, and can report the tail a truncated stream left behind.</para>
    ///
    /// <para><b>Whatever happens, the lane ends cleanly:</b> pending requests are failed with a named
    /// reason instead of waiting on a process that has gone, and the event queue is completed so a
    /// consumer stops rather than hangs.</para>
    /// </remarks>
    public async Task RunAsync(CancellationToken cancellationToken = default)
    {
        var buffer = new char[8192];
        var frame = new System.Text.StringBuilder();
        var skippingToNextNewline = false;

        try
        {
            while (true)
            {
                var read = await _input.ReadAsync(buffer.AsMemory(), cancellationToken);
                if (read == 0)
                {
                    break;
                }

                for (var i = 0; i < read; i++)
                {
                    var character = buffer[i];

                    if (skippingToNextNewline)
                    {
                        skippingToNextNewline = character == '\n' ? false : skippingToNextNewline;
                        continue;
                    }

                    if (character == '\n')
                    {
                        var line = frame.ToString().TrimEnd('\r');
                        frame.Clear();
                        await DispatchAsync(line, cancellationToken);
                        continue;
                    }

                    frame.Append(character);
                    if (frame.Length <= _options.MaxFrameChars)
                    {
                        continue;
                    }

                    Interlocked.Increment(ref _overLongFrames);
                    _diagnostics(
                        $"acp: refused a frame longer than {_options.MaxFrameChars} characters; skipping to the "
                        + "next newline. The engine is emitting something this client cannot be asked to buffer");
                    frame.Clear();
                    skippingToNextNewline = true;
                }
            }

            if (frame.Length > 0)
            {
                // A tail with no newline is NOT a frame. Parsing it would mean acting on half a
                // message, and the half that is missing is the half that would have said so.
                Interlocked.Add(ref _unterminatedTailChars, frame.Length);
                _diagnostics(
                    $"acp: the engine's stdout ended with {frame.Length} unterminated characters; they are not a "
                    + "frame and were not parsed");
            }
        }
        finally
        {
            FailEveryPendingRequest();
            Events.Complete();
        }
    }

    /// <summary>
    /// Sends a request and waits for the reply that carries its id.
    /// </summary>
    /// <param name="method">The ACP method.</param>
    /// <param name="parameters">Its params, or null.</param>
    /// <param name="timeout">How long to wait. Defaults to <see cref="AcpPeerOptions.RequestTimeout"/>.</param>
    /// <param name="cancellationToken">Cancels the wait.</param>
    /// <exception cref="AgentPlaneException">
    /// <see cref="AgentPlaneErrorCodes.EngineReturnedError"/> when the peer answered with an error;
    /// <see cref="AgentPlaneErrorCodes.EngineRequestTimedOut"/> when it did not answer at all;
    /// <see cref="AgentPlaneErrorCodes.EngineStreamEnded"/> when its stdout closed first.
    /// </exception>
    public async Task<JsonObject> RequestAsync(
        string method,
        JsonObject? parameters,
        TimeSpan? timeout = null,
        CancellationToken cancellationToken = default)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(method);

        var id = Interlocked.Increment(ref _nextRequestId);
        var key = id.ToString(CultureInfo.InvariantCulture);
        var completion = new TaskCompletionSource<JsonObject>(TaskCreationOptions.RunContinuationsAsynchronously);

        // Registered BEFORE the write, so a reply that comes back faster than this method resumes
        // still finds its entry. Registering after the write is a race that only shows up under load.
        lock (_pendingGate)
        {
            _pending[key] = new PendingRequest(method, completion);
        }

        var request = new JsonObject
        {
            ["jsonrpc"] = "2.0",
            ["id"] = id,
            ["method"] = method,
        };

        if (parameters is not null)
        {
            request["params"] = parameters;
        }

        var bound = timeout ?? _options.RequestTimeout;
        try
        {
            await WriteAsync(request, cancellationToken);
            using var deadline = CancellationTokenSource.CreateLinkedTokenSource(cancellationToken);
            deadline.CancelAfter(bound);
            return await completion.Task.WaitAsync(deadline.Token);
        }
        catch (OperationCanceledException) when (!cancellationToken.IsCancellationRequested)
        {
            throw new AgentPlaneException(
                AgentPlaneErrorCodes.EngineRequestTimedOut,
                $"the engine did not answer '{method}' within {bound}; the request is abandoned rather than "
                + "held open, because a lane waiting on a hung child is indistinguishable from one that is working");
        }
        finally
        {
            lock (_pendingGate)
            {
                _pending.Remove(key);
            }
        }
    }

    /// <summary>
    /// Normalizes one frame, publishes it, and only then acts on it.
    /// </summary>
    /// <remarks>
    /// The order of the two halves is the ordinal Ruling 11 requires. It is also the honest order:
    /// the run log is the record of what arrived, and a record written after the reply would be a
    /// record of what we did about it.
    /// </remarks>
    private async Task DispatchAsync(string line, CancellationToken cancellationToken)
    {
        if (line.Length == 0)
        {
            return;
        }

        JsonObject? frame;
        try
        {
            frame = JsonNode.Parse(line) as JsonObject;
        }
        catch (JsonException error)
        {
            frame = null;
            _diagnostics($"acp: unparseable frame ({error.Message}); the loop continues");
        }

        if (frame is null)
        {
            // One bad message never kills the loop: the other side would see the client vanish and
            // report a transport failure, which points away from the frame that caused it.
            Interlocked.Increment(ref _malformedFrames);
            _diagnostics("acp: a received line was not a JSON object and carries no event; it was counted and skipped");
            return;
        }

        Interlocked.Increment(ref _framesRead);

        var receivedAt = _time.GetUtcNow();
        var normalized = _mapper.Map(line, receivedAt);
        await Events.PublishAsync(
            ObservedRunEvent.From(normalized, receivedAt, _time.GetUtcNow()), cancellationToken);

        var method = (frame["method"] as JsonValue)?.TryGetValue<string>(out var name) == true ? name : null;
        if (method is null)
        {
            CompleteReply(frame);
            return;
        }

        if (method == AcpAuthStatus.Method)
        {
            ObservedAuth = AcpAuthStatus.From(frame["params"] as JsonObject);
        }

        // The id KEY, never the id's truthiness. frames/write.jsonl:12 carries "id":0 on a real
        // session/request_permission; a truthy test reads it as a notification and the agent waits
        // forever for an answer that was never going to be sent.
        if (!frame.TryGetPropertyValue("id", out var id) || id is null)
        {
            Interlocked.Increment(ref _notifications);
            return;
        }

        await AnswerAsync(method, id, frame["params"] as JsonObject, cancellationToken);
    }

    private async Task AnswerAsync(string method, JsonNode id, JsonObject? parameters, CancellationToken cancellationToken)
    {
        JsonNode? answer;
        try
        {
            answer = InboundHandler?.Invoke(method, parameters);
        }
        catch (Exception error) when (error is not OperationCanceledException)
        {
            _diagnostics($"acp: the inbound handler threw on '{method}': {error.GetType().Name}: {error.Message}");
            await WriteAsync(Error(id, -32603, $"internal error handling {method}"), cancellationToken);
            return;
        }

        if (answer is null)
        {
            // Answered as unknown rather than ignored: silence looks like a hung client, and the
            // agent cannot tell the two apart.
            Interlocked.Increment(ref _unknownMethodsAnswered);
            await WriteAsync(Error(id, -32601, $"method not found: {method}"), cancellationToken);
            return;
        }

        Interlocked.Increment(ref _inboundRequestsAnswered);
        await WriteAsync(Result(id, answer), cancellationToken);
    }

    private void CompleteReply(JsonObject frame)
    {
        if (!frame.TryGetPropertyValue("id", out var id) || id is null)
        {
            Interlocked.Increment(ref _malformedFrames);
            _diagnostics("acp: a frame carried neither a method nor an id, so it is neither a call nor a reply");
            return;
        }

        var key = Key(id);
        PendingRequest? waiting;
        lock (_pendingGate)
        {
            _pending.Remove(key, out waiting);
        }

        if (waiting is null)
        {
            Interlocked.Increment(ref _unmatchedResponses);
            _diagnostics($"acp: a reply arrived for id {key}, which this client never sent; counted and ignored");
            return;
        }

        if (frame["error"] is JsonObject failure)
        {
            var code = (failure["code"] as JsonValue)?.TryGetValue<int>(out var number) == true ? number : 0;
            var message = (failure["message"] as JsonValue)?.TryGetValue<string>(out var text) == true ? text : "(no message)";
            waiting.Completion.TrySetException(new AgentPlaneException(
                AgentPlaneErrorCodes.EngineReturnedError,
                $"the engine refused '{waiting.Method}' with JSON-RPC error {code}: {message}"));
            return;
        }

        waiting.Completion.TrySetResult(frame["result"] as JsonObject ?? []);
    }

    /// <summary>
    /// Fails every outstanding request when the child's stdout ends.
    /// </summary>
    /// <remarks>
    /// A pending request whose peer has gone will never complete, and a lane blocked forever on one
    /// looks exactly like a lane that is working. Naming the reason is the difference between a
    /// diagnosable exit and a hang.
    /// </remarks>
    private void FailEveryPendingRequest()
    {
        List<KeyValuePair<string, PendingRequest>> outstanding;
        lock (_pendingGate)
        {
            outstanding = [.. _pending];
            _pending.Clear();
        }

        foreach (var (key, pending) in outstanding)
        {
            pending.Completion.TrySetException(new AgentPlaneException(
                AgentPlaneErrorCodes.EngineStreamEnded,
                $"the engine's stdout reached end of stream while '{pending.Method}' (id {key}) was still "
                + "outstanding; the child exited or was killed mid-session"));
        }
    }

    /// <summary>One outbound request awaiting its reply. The method travels so a failure can name it.</summary>
    private sealed record PendingRequest(string Method, TaskCompletionSource<JsonObject> Completion);

    /// <summary>
    /// Writes one frame, serialized against every other writer.
    /// </summary>
    /// <remarks>
    /// <b>Two writers exist and they are not the same thread.</b> Answers to inbound requests come
    /// out of the read loop; outbound requests come from whoever is driving the lane. Interleaving
    /// two <c>JSON.stringify(...) + "\n"</c> writes produces a line that is neither frame, and the
    /// peer's own recovery would then be reading our corruption.
    /// </remarks>
    private async Task WriteAsync(JsonObject frame, CancellationToken cancellationToken)
    {
        var text = frame.ToJsonString(Json);
        await _writeLock.WaitAsync(cancellationToken);
        try
        {
            await _output.WriteAsync(text.AsMemory(), cancellationToken);
            await _output.WriteAsync("\n".AsMemory(), cancellationToken);
            await _output.FlushAsync(cancellationToken);
        }
        finally
        {
            _writeLock.Release();
        }
    }

    /// <summary>
    /// The canonical text of a JSON-RPC id.
    /// </summary>
    /// <remarks>
    /// A number and a string are different ids in JSON-RPC, so <c>1</c> and <c>"1"</c> must not
    /// collide. Numbers render bare and everything else keeps its JSON quoting, which separates them
    /// without a second field to carry the type.
    /// </remarks>
    private static string Key(JsonNode id)
        => id is JsonValue value && value.TryGetValue<long>(out var number)
            ? number.ToString(CultureInfo.InvariantCulture)
            : id.ToJsonString(Json);

    private static JsonObject Result(JsonNode id, JsonNode payload) =>
        new()
        {
            ["jsonrpc"] = "2.0",
            ["id"] = id.DeepClone(),
            ["result"] = payload,
        };

    private static JsonObject Error(JsonNode id, int code, string message) =>
        new()
        {
            ["jsonrpc"] = "2.0",
            ["id"] = id.DeepClone(),
            ["error"] = new JsonObject { ["code"] = code, ["message"] = message },
        };
}
