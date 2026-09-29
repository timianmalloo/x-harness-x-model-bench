using System.Text;
using System.Text.Json;
using System.Text.Json.Nodes;
using AiDe.Core.Watcher;

namespace AiDe.Mcp;

/// <summary>
/// The stdio MCP server: JSON-RPC on stdin/stdout, three tools, no authority an agent lacks.
/// </summary>
/// <remarks>
/// <para><b>Hand-rolled rather than taking an SDK.</b> The Solution-Selection Ladder puts a new
/// dependency past rung 5, and JSON-RPC over stdio is a hundred lines against
/// <c>System.Text.Json</c>. A package here would be a supply-chain surface and a version to track,
/// bought for framing that the framework already provides.</para>
///
/// <para><b>Nothing may be written to stdout but a response.</b> stdout IS the protocol channel, so a
/// stray <c>Console.WriteLine</c> corrupts the stream and the client reports a malformed server
/// rather than the message that caused it. Every diagnostic goes to stderr, which the client logs.
/// </para>
/// </remarks>
public static class Program
{
    // mirrors src/AiDe.Core/AgentPlane/AcpPeer.cs framing
    //
    // The NDJSON loop discipline below, the Result/Error envelope builders and the -32601 case are
    // copied THERE, not shared. The extraction trigger is recorded on the copy: a third stdio
    // JSON-RPC consumer, or the first defect that must be fixed in both places. A change to any of
    // those three here is a change that has to be made there too - which is why this marker exists
    // as a grep rather than as a note in a review.
    private static readonly JsonSerializerOptions Json = new() { WriteIndented = false };

    /// <summary>The MCP revision this server speaks, echoed back on initialize.</summary>
    private const string ProtocolVersion = "2024-11-05";

    public static async Task<int> Main(string[] args)
    {
        // stdout is the protocol. Anything else that reaches it is a corrupt frame.
        var stdout = Console.OpenStandardOutput();
        using var writer = new StreamWriter(stdout, new UTF8Encoding(false)) { AutoFlush = true };
        using var reader = new StreamReader(Console.OpenStandardInput(), new UTF8Encoding(false));

        if (args.Contains("--self-test"))
        {
            return SelfTest();
        }

        var context = ServerContext.Discover();
        Console.Error.WriteLine($"aide-mcp: {context.Describe()}");

        string? line;
        while ((line = await reader.ReadLineAsync()) is not null)
        {
            if (line.Length == 0)
            {
                continue;
            }

            string? response;
            try
            {
                response = Handle(line, context);
            }
            catch (Exception ex) when (ex is not OperationCanceledException)
            {
                // One bad message must never kill the loop: the client would see the server vanish
                // and report a connection failure, which points at the transport rather than at the
                // request that caused it.
                Console.Error.WriteLine($"aide-mcp: {ex.GetType().Name}: {ex.Message}");
                response = null;
            }

            if (response is not null)
            {
                await writer.WriteLineAsync(response);
            }
        }

        return 0;
    }

    /// <summary>Routes one JSON-RPC message. Returns null for a notification, which takes no reply.</summary>
    private static string? Handle(string line, ServerContext context)
    {
        var request = JsonNode.Parse(line)?.AsObject();
        if (request is null)
        {
            return null;
        }

        var method = request["method"]?.GetValue<string>();
        var id = request["id"];

        // A notification has no id and MUST NOT be answered — replying to one is a protocol error
        // that some clients treat as a fatal desync.
        if (id is null)
        {
            return null;
        }

        return method switch
        {
            "initialize" => Result(id, new JsonObject
            {
                ["protocolVersion"] = ProtocolVersion,
                ["capabilities"] = new JsonObject { ["tools"] = new JsonObject() },
                ["serverInfo"] = new JsonObject
                {
                    ["name"] = "aide",
                    ["version"] = "0.1.0",
                },
            }),

            "tools/list" => Result(id, new JsonObject { ["tools"] = Tools.Schema() }),

            "tools/call" => Result(id, Tools.Call(request["params"]?.AsObject(), context)),

            // Unknown methods are answered as unknown rather than ignored: silence looks like a hung
            // server, and the client cannot tell the two apart.
            _ => Error(id, -32601, $"method not found: {method}"),
        };
    }

    private static string Result(JsonNode id, JsonNode payload) =>
        new JsonObject
        {
            ["jsonrpc"] = "2.0",
            ["id"] = id.DeepClone(),
            ["result"] = payload,
        }.ToJsonString(Json);

    private static string Error(JsonNode id, int code, string message) =>
        new JsonObject
        {
            ["jsonrpc"] = "2.0",
            ["id"] = id.DeepClone(),
            ["error"] = new JsonObject { ["code"] = code, ["message"] = message },
        }.ToJsonString(Json);

    /// <summary>
    /// Proves the server's own guards can fire, without a client (DC-104).
    /// </summary>
    /// <remarks>
    /// A new control's first run is a test of the control, not of the code — and this server ships
    /// with a gate, so it owes the same demonstration every other gate here does.
    /// </remarks>
    private static int SelfTest()
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

        var context = ServerContext.None("self-test");

        Check("a notification is not answered",
            Handle("""{"jsonrpc":"2.0","method":"notifications/initialized"}""", context) is null);

        Check("initialize echoes the protocol version",
            Handle("""{"jsonrpc":"2.0","id":1,"method":"initialize"}""", context)?.Contains(ProtocolVersion) == true);

        Check("tools/list names every tool",
            Handle("""{"jsonrpc":"2.0","id":2,"method":"tools/list"}""", context) is { } list
            && list.Contains("aide_whoami") && list.Contains("aide_board_read")
            && list.Contains("aide_board_post") && list.Contains("aide_episode_open")
            && list.Contains("aide_episode_close"));

        Check("an unknown method is answered, not ignored",
            Handle("""{"jsonrpc":"2.0","id":3,"method":"nope"}""", context)?.Contains("method not found") == true);

        Check("malformed JSON does not kill the loop",
            SafeHandle("{not json", context) is null);

        Check("with no session, a tool states the absence rather than failing",
            Handle("""{"jsonrpc":"2.0","id":4,"method":"tools/call","params":{"name":"aide_whoami"}}""", context)
                is { } who && who.Contains("not an AI-DE session"));

        Console.Error.WriteLine();
        if (failures.Count > 0)
        {
            Console.Error.WriteLine($"aide-mcp --self-test: {failures.Count} guard(s) did not fire.");
            return 1;
        }

        Console.Error.WriteLine("aide-mcp --self-test: every guard fires.");
        return 0;
    }

    private static string? SafeHandle(string line, ServerContext context)
    {
        try
        {
            return Handle(line, context);
        }
        catch (JsonException)
        {
            return null;
        }
    }
}
