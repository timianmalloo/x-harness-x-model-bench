using System.Diagnostics;
using System.Text.Json.Nodes;
using AiDe.Core.AgentPlane;
using AiDe.Core.Tests.AgentPlane;

namespace AiDe.Core.AcpProbe;

/// <summary>
/// The ACP client's own harness: the guard self-test, the live round-trip against the pinned
/// adapter, and a child that deliberately never exits.
/// </summary>
/// <remarks>
/// <para><b>A helper, not a second entry point for the run.</b> N7's governed run goes through the
/// real App-layer composition root. This exists so the guards can be demonstrated firing without an
/// adapter (DC-104), so the live handshake can be exercised by hand against a real subscription, and
/// so the process-reaping case has a real child to reap.</para>
/// </remarks>
public static class Program
{
    public static async Task<int> Main(string[] args)
    {
        if (args.Contains("--host-engine"))
        {
            return await HostEngine().ConfigureAwait(false);
        }

        if (args.Contains("--echo-utf8"))
        {
            // One line of UTF-8 BYTES, written past the console layer — what a Node adapter writes.
            // The reader on the other side decodes them with whatever encoding the engine process
            // gave its stream (Ruling 87): a single-byte code page renders `—` as `â€"` and `§` as `Â§`.
            var bytes = System.Text.Encoding.UTF8.GetBytes("— § compile" + (char)10);
            using var stdout = Console.OpenStandardOutput();
            stdout.Write(bytes, 0, bytes.Length);
            stdout.Flush();
            return 0;
        }

        if (args.Contains("--hang"))
        {
            if (args.Contains("--spawn-child"))
            {
                // A grandchild, so the reaping question is asked about a TREE and not about one
                // process. Job membership is inherited, so a contained engine takes this with it;
                // an uncontained one leaves it behind exactly as it leaves itself behind.
                using var grandchild = Process.Start(new ProcessStartInfo(Environment.ProcessPath!)
                {
                    ArgumentList = { "--hang", "--ignore-stdin" },
                    RedirectStandardInput = true,
                    UseShellExecute = false,
                    CreateNoWindow = true,
                }) ?? throw new InvalidOperationException("the grandchild did not start");

                Console.Out.WriteLine($"GRANDCHILD {grandchild.Id}");
            }

            if (args.Contains("--ignore-stdin"))
            {
                // A child that does NOT end when its stdin closes. MEASURED, because the first
                // attempt at the containment oracle proved the wrong thing: a child blocked on
                // `ReadToEnd` is reaped by the pipe breaking when its parent dies, so the tree
                // appeared contained while nothing contained it. Stdin EOF is a MITIGATION - the
                // same category as stripping `-NoExit` from a shell - and a mitigation that holds
                // for this child says nothing about an adapter that is mid-request, buffering, or
                // holding a credential session open. The self-limit bounds a leak this mode
                // deliberately creates; it is not the exit path under test.
                await Task.Delay(TimeSpan.FromSeconds(120)).ConfigureAwait(false);
                return 0;
            }

            // A child that never exits on its own: it blocks on a stdin that nobody closes. The
            // reaping case needs a process that will still be alive when the test kills it.
            await Console.In.ReadToEndAsync().ConfigureAwait(false);
            return 0;
        }

        if (args.Contains("--self-test"))
        {
            return await SelfTest().ConfigureAwait(false);
        }

        if (args.Contains("--live"))
        {
            return await Live(args).ConfigureAwait(false);
        }

        Console.Error.WriteLine("usage: AiDe.Core.AcpProbe --self-test | --live [--adapter-root DIR] [--cwd DIR] [--prompt TEXT] | --hang [--ignore-stdin] [--spawn-child] | --host-engine");
        return 2;
    }

    // ------------------------------------------------------------------ the outer ring (DC-123)

    /// <summary>
    /// Owns a real <see cref="AcpEngineProcess"/> and then waits to be killed.
    /// </summary>
    /// <remarks>
    /// <para><b>The oracle has to live outside the process that leaks.</b> DC-123's whole point is
    /// that an abandoned subtree is invisible from inside the harness that abandoned it, so the
    /// question "did the engine tree outlive its host?" cannot be asked by a test running in the
    /// host. This mode makes the host a process a driver can kill, and prints the three process ids
    /// the driver has to watch — its own, the engine's, and the engine's own child's.</para>
    ///
    /// <para><b><c>Dispose</c> is deliberately unreachable on the path this exists to measure.</b>
    /// It is written below and it is correct; a process that is killed never runs it. That is the
    /// difference between the graceful path and the abnormal one, and the abnormal one is the one
    /// containment is for.</para>
    /// </remarks>
    private static async Task<int> HostEngine()
    {
        var launch = new EngineLaunch(
            Environment.ProcessPath!, ["--hang", "--ignore-stdin", "--spawn-child"]);

        using var engine = AcpEngineProcess.Start(
            launch, AppContext.BaseDirectory, d => Console.Error.WriteLine("host: " + d));

        Console.Out.WriteLine($"HOST {Environment.ProcessId}");
        Console.Out.WriteLine($"ENGINE {engine.ProcessId}");
        Console.Out.WriteLine(await engine.Output.ReadLineAsync().ConfigureAwait(false));
        Console.Out.WriteLine("READY");

        await Console.In.ReadToEndAsync().ConfigureAwait(false);
        return 0;
    }

    // ------------------------------------------------------------------ the guards (DC-104)

    /// <summary>
    /// Proves the client's own guards can fire, without an adapter.
    /// </summary>
    /// <remarks>
    /// Mirrors <c>src/AiDe.Mcp/Program.cs</c>'s <c>--self-test</c>, guard for guard: a notification
    /// is not answered, the handshake version is checked, an unknown method is answered rather than
    /// ignored, malformed input does not kill the loop, and a measurement that cannot be taken reads
    /// "not recorded" rather than a plausible zero. A new control's first run is evidence about the
    /// control, not about the code.
    /// </remarks>
    private static async Task<int> SelfTest()
    {
        var failures = new List<string>();

        void Check(string label, bool ok)
        {
            Console.Error.WriteLine($"  {(ok ? "ok  " : "FAIL")}  {label}");
            if (!ok)
            {
                failures.Add(label);
            }
        }

        var notification = await Replay(
            null,
            """{"jsonrpc":"2.0","method":"session/update","params":{"update":{"sessionUpdate":"agent_message_chunk"}}}""")
            .ConfigureAwait(false);
        Check("a notification is not answered", notification.Written.Count == 0 && notification.Peer.Counters.Notifications == 1);

        var idZero = await Replay(
            (_, _) => new JsonObject { ["outcome"] = "rejected" },
            """{"jsonrpc":"2.0","id":0,"method":"session/request_permission","params":{"options":[]}}""")
            .ConfigureAwait(false);
        Check(
            "an inbound request with id 0 is answered, not read as a notification",
            idZero.Written.Count == 1 && idZero.Written[0].Contains("\"id\":0", StringComparison.Ordinal));

        var unknown = await Replay(null, """{"jsonrpc":"2.0","id":7,"method":"terminal/create","params":{}}""")
            .ConfigureAwait(false);
        Check(
            "an unknown method is answered, not ignored",
            unknown.Written.Count == 1 && unknown.Written[0].Contains("-32601", StringComparison.Ordinal));

        var malformed = await Replay(
            null,
            "{not json",
            """{"jsonrpc":"2.0","method":"session/update","params":{"update":{"sessionUpdate":"agent_message_chunk"}}}""")
            .ConfigureAwait(false);
        Check(
            "one malformed frame does not kill the loop",
            malformed.Peer.Counters.MalformedFrames == 1 && malformed.Peer.Events.Published == 1);

        var overLong = await Replay(
            null,
            new AcpPeerOptions { MaxFrameChars = 200 },
            "{\"pad\":\"" + new string('x', 400) + "\"}",
            """{"jsonrpc":"2.0","method":"session/update","params":{"update":{"sessionUpdate":"agent_message_chunk"}}}""")
            .ConfigureAwait(false);
        Check(
            "an over-long line is refused and the splitter resynchronizes",
            overLong.Peer.Counters.OverLongFrames == 1 && overLong.Peer.Counters.FramesRead == 1);

        Check("the handshake refuses a protocol version that is not the pinned one", await RefusesVersion().ConfigureAwait(false));

        Check("a relative session cwd never reaches the wire", await RefusesRelativeCwd().ConfigureAwait(false));

        var queue = new AcpEventQueue(capacity: 1);
        var first = queue.PublishAsync(Sample(1));
        var blocked = queue.PublishAsync(Sample(2));
        Check(
            "a full event queue applies backpressure and drops nothing",
            first.IsCompletedSuccessfully && !blocked.IsCompleted && queue.BackpressureWaits == 1 && queue.Dropped == 0);

        var unmeasured = ObservedRunEvent.From(Sample(3).Event, receivedAt: null, normalizedAt: DateTimeOffset.UnixEpoch);
        Check(
            "an unmeasured latency reads \"not recorded\", never 0",
            unmeasured.DescribeLatency() == ObservedRunEvent.NotRecorded);

        Console.Error.WriteLine();
        if (failures.Count > 0)
        {
            Console.Error.WriteLine($"acp-probe --self-test: {failures.Count} guard(s) did not fire.");
            return 1;
        }

        Console.Error.WriteLine("acp-probe --self-test: every guard fires.");
        return 0;
    }

    private static ObservedRunEvent Sample(long seq)
        => new(
            new RunEvent("run", "lane", null, seq, DateTimeOffset.UnixEpoch, "acp.frame", null, [], []),
            DateTimeOffset.UnixEpoch,
            TimeSpan.Zero);

    private sealed record Replayed(AcpPeer Peer, IReadOnlyList<string> Written);

    private static Task<Replayed> Replay(Func<string, JsonObject?, JsonNode?>? inbound, params string[] lines)
        => Replay(inbound, null, lines);

    private static async Task<Replayed> Replay(
        Func<string, JsonObject?, JsonNode?>? inbound, AcpPeerOptions? options, params string[] lines)
    {
        var input = new PushTextReader();
        var output = new RecordingTextWriter();
        var peer = new AcpPeer(input, output, new AcpRunEventMapper("self-test", "lane"), options: options)
        {
            InboundHandler = inbound,
        };

        var run = peer.RunAsync();
        foreach (var line in lines)
        {
            input.Push(line + "\n");
        }

        input.EndOfStream();
        await run.ConfigureAwait(false);
        return new Replayed(peer, [.. output.Lines.Select(l => l.Line)]);
    }

    private static async Task<bool> RefusesVersion()
    {
        var input = new PushTextReader();
        var output = new RecordingTextWriter();
        var peer = new AcpPeer(input, output, new AcpRunEventMapper("self-test", "lane"));
        var client = new AcpLaneClient(peer);
        var run = peer.RunAsync();
        var initialize = client.InitializeAsync();
        input.Push("""{"jsonrpc":"2.0","id":1,"result":{"protocolVersion":2}}""" + "\n");

        var refused = false;
        try
        {
            await initialize.ConfigureAwait(false);
        }
        catch (AgentPlaneException error)
        {
            refused = error.Code == AgentPlaneErrorCodes.ProtocolVersionMismatch;
        }

        input.EndOfStream();
        await run.ConfigureAwait(false);
        return refused;
    }

    private static async Task<bool> RefusesRelativeCwd()
    {
        var output = new RecordingTextWriter();
        var client = new AcpLaneClient(new AcpPeer(new PushTextReader(), output, new AcpRunEventMapper("self-test", "lane")));

        try
        {
            await client.NewSessionAsync("relative/path").ConfigureAwait(false);
            return false;
        }
        catch (AgentPlaneException error)
        {
            return error.Code == AgentPlaneErrorCodes.SessionCwdNotAbsolute && output.Lines.Count == 0;
        }
    }

    // ------------------------------------------------------------------ the live round-trip

    /// <summary>
    /// Drives the real pinned adapter: <c>initialize</c> (asserting the echoed version) →
    /// <c>session/new</c> with an absolute cwd → a prompt, until a <c>tool.call</c> event arrives.
    /// </summary>
    private static async Task<int> Live(string[] args)
    {
        var adapterRoot = Argument(args, "--adapter-root") ?? Path.GetFullPath("spikes/acp-subscription-lane");
        var cwd = Path.GetFullPath(Argument(args, "--cwd") ?? Path.GetTempPath());

        var launch = EngineCatalog.ResolveLaunch("claude-code", adapterRoot);
        Console.Error.WriteLine($"acp-probe: launching {launch.FileName} {string.Join(' ', launch.Arguments)}");

        using var engine = AcpEngineProcess.Start(launch, adapterRoot, d => Console.Error.WriteLine("acp-probe: " + d));
        Console.Error.WriteLine($"acp-probe: pid {engine.ProcessId}");

        var peer = new AcpPeer(
            engine.Output,
            engine.Input,
            new AcpRunEventMapper("live-probe", "lane-live"),
            diagnostics: d => Console.Error.WriteLine("acp-probe: " + d));
        var client = new AcpLaneClient(peer);

        using var deadline = new CancellationTokenSource(TimeSpan.FromMinutes(3));
        var run = peer.RunAsync(deadline.Token);

        var initialize = await client.InitializeAsync(deadline.Token).ConfigureAwait(false);
        Console.Out.WriteLine("INITIALIZE  " + Trim(initialize));

        var sessionId = await client.NewSessionAsync(cwd, cancellationToken: deadline.Token).ConfigureAwait(false);
        Console.Out.WriteLine($"SESSION     {sessionId}   cwd={cwd}");
        Console.Out.WriteLine("AUTH        " + (peer.ObservedAuth is { } a
            ? $"kind={a.Kind} label={a.Label} plan={a.Plan}"
            : "not recorded"));

        var prompt = client.PromptAsync(
            sessionId,
            Argument(args, "--prompt")
                ?? "Run the shell command `git status --short` and report its output. Do nothing else.",
            deadline.Token);

        var kinds = new List<string>();
        var sawToolCall = false;
        await foreach (var observed in peer.Events.Reader.ReadAllAsync(deadline.Token).ConfigureAwait(false))
        {
            kinds.Add(observed.Event.Kind);
            if (observed.Event.Kind == "tool.call" && !sawToolCall)
            {
                sawToolCall = true;
                Console.Out.WriteLine($"TOOL_CALL   seq={observed.Event.Seq} latency={observed.DescribeLatency()}");
                Console.Out.WriteLine("            " + Trim(observed.Event.Body));
            }

            if (prompt.IsCompleted && peer.Events.Reader.Count == 0)
            {
                break;
            }
        }

        try
        {
            Console.Out.WriteLine("PROMPT      " + Trim(await prompt.ConfigureAwait(false)));
        }
        catch (AgentPlaneException error)
        {
            Console.Out.WriteLine($"PROMPT      refused {error.Code}: {error.Message}");
        }

        Console.Out.WriteLine("KINDS       " + string.Join(", ", kinds.Distinct(StringComparer.Ordinal).Order(StringComparer.Ordinal)));
        Console.Out.WriteLine("COUNTERS    " + peer.Counters);
        Console.Out.WriteLine("QUEUE       published=" + peer.Events.Published + " waits=" + peer.Events.BackpressureWaits + " dropped=" + peer.Events.Dropped);

        await deadline.CancelAsync().ConfigureAwait(false);
        try
        {
            await run.ConfigureAwait(false);
        }
        catch (OperationCanceledException)
        {
            // Expected: the deadline is how the probe stops a session it deliberately does not finish.
        }

        return sawToolCall ? 0 : 1;
    }

    private static string Trim(JsonObject value)
    {
        var text = value.ToJsonString();
        return text.Length <= 700 ? text : text[..700] + "...";
    }

    private static string? Argument(string[] args, string name)
    {
        var index = Array.IndexOf(args, name);
        return index >= 0 && index + 1 < args.Length ? args[index + 1] : null;
    }
}
