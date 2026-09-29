using System.Diagnostics;
using System.Runtime.Versioning;
using System.Text.RegularExpressions;
using AiDe.Core.Ipc;
using AiDe.Core.Projections;

namespace AiDe.Core.Tests;

/// <summary>
/// `P2-PRIV-02` and the control that keeps the privacy net from developing holes.
/// </summary>
/// <remarks>
/// <para><b>A seeded secret is the only honest way to assert an absence.</b> Reading the code and
/// concluding "nothing writes the payload to a span" is an inference; putting a unique string into
/// the payload and searching every emitted attribute for it is a measurement. The distinction
/// matters most here, because the thing being asserted is that something did <i>not</i> happen.</para>
///
/// <para><b>The net had a hole when this was written.</b> `TelemetryTests` enforces the privacy
/// floor over sources whose name starts with <c>aide.</c>, and every source added with the process
/// split was named <c>AiDe.Core.*</c> — outside it. The IPC boundary, the terminal runtime and the
/// upgrade coordinator were emitting spans that no privacy assertion could see. Renaming them closed
/// it; <see cref="EveryActivitySource_IsUnderTheAideNamespace"/> is what stops it reopening.</para>
/// </remarks>
[SupportedOSPlatform("windows")]
[Trait("Platform", "Windows")]
public sealed class PrivacyMarkerTests : IDisposable
{
    /// <summary>Unique enough that a match cannot be coincidence.</summary>
    private const string Secret = "SEEDED-SECRET-9f41c07be2";

    private readonly List<Activity> _captured = [];
    private readonly ActivityListener _listener;

    public PrivacyMarkerTests()
    {
        _listener = new ActivityListener
        {
            // Everything, deliberately — a listener scoped to a prefix is how the previous hole was
            // created. If a source escapes the naming convention, the test below fails; if one
            // escapes THIS listener, nothing would.
            ShouldListenTo = _ => true,
            Sample = (ref ActivityCreationOptions<ActivityContext> _) => ActivitySamplingResult.AllDataAndRecorded,
            ActivityStopped = activity =>
            {
                lock (_captured)
                {
                    _captured.Add(activity);
                }
            },
        };

        ActivitySource.AddActivityListener(_listener);
    }

    private IReadOnlyList<Activity> Captured
    {
        get
        {
            lock (_captured)
            {
                return [.. _captured];
            }
        }
    }

    // ---- the control that keeps the net whole --------------------------------

    [Fact]
    public void EveryActivitySource_IsUnderTheAideNamespace()
    {
        // The privacy assertions in TelemetryTests listen by prefix. A source named outside it is
        // not merely inconsistent — it is invisible to the control, which is how the process split's
        // spans went unwatched for four commits.
        //
        // Checked against the source text rather than by reflection, because a source that is never
        // constructed in a test run does not exist to reflect over — and an unexercised emitter is
        // exactly the one that would slip out.
        var offenders = new List<string>();
        var found = 0;

        // BOTH spellings. Every source in this codebase is written target-typed —
        // `ActivitySource X = new("name")` — and an earlier version of this test matched only
        // `new ActivitySource("name")`, so it scanned nothing at all and passed. Mutation caught
        // it: renaming a source out of the namespace failed no test (DC-015).
        var patterns = new[]
        {
            @"new\s+ActivitySource\(\s*""([^""]+)""",
            @"ActivitySource\s+\w+\s*=\s*new\(\s*""([^""]+)""",
        };

        foreach (var file in Directory.EnumerateFiles(SourceRoot(), "*.cs", SearchOption.AllDirectories))
        {
            var text = File.ReadAllText(file);

            foreach (var pattern in patterns)
            {
                foreach (Match match in Regex.Matches(text, pattern, RegexOptions.None, TimeSpan.FromSeconds(5)))
                {
                    found++;
                    var name = match.Groups[1].Value;

                    if (!name.StartsWith("aide.", StringComparison.Ordinal))
                    {
                        offenders.Add($"{Path.GetFileName(file)}: {name}");
                    }
                }
            }
        }

        // Non-vacuity, and it is the whole reason this test can be trusted: a scan that matches
        // nothing satisfies every assertion about what it found.
        Assert.True(
            found >= 8,
            $"the scan matched only {found} ActivitySource declarations; it is not seeing them");

        Assert.True(
            offenders.Count == 0,
            "every ActivitySource must be named under 'aide.' so the privacy assertions can see it:\n  "
            + string.Join("\n  ", offenders));
    }

    [Fact]
    public void TheSourcesThisSuiteCoversAreActuallyEmitting()
    {
        // Non-vacuity. Every assertion below is an absence, and an absence over an empty set is free
        // — so this establishes that the paths under test emit at all before anything claims they
        // emit nothing sensitive.
        var endpoint = Endpoint(out var workspace);
        endpoint.OpenWorkspace(Open(workspace), Peer());

        Assert.NotEmpty(Captured);
    }

    // ---- P2-PRIV-02: the daemon's own telemetry ------------------------------

    [Fact]
    public void ASecretInAnIpcPayload_ReachesNoSpanAttribute()
    {
        // The daemon is a new process with its own log and span stream, and its requests carry
        // caller-chosen payloads. A span that echoed the payload for debugging would put a search
        // term — which in this product is repository content — into telemetry.
        var endpoint = Endpoint(out var workspace);
        var opened = endpoint.OpenWorkspace(Open(workspace), Peer());
        Assert.True(opened.Ok, opened.Reason);

        var capability = opened.Payload.As<IpcOpenResult>()!.Capability;

        var response = endpoint.Invoke(
            new IpcRequest(
                // A plain command id: the id is legitimately recorded, and seeding it here would
                // assert the wrong thing. The PAYLOAD is what this case is about.
                IpcVersion.Current, WorkspaceOperations.Find, "cmd-payload", workspace, 1,
                capability, IpcPayloadTestExtensions.Json($"{{\"term\":\"{Secret}\",\"maxResults\":5}}")),
            Peer());

        Assert.True(response.Ok, response.Reason);
        AssertNoSpanCarries(Secret);
    }

    [Fact]
    public void ASecretInACommandId_ReachesNoSpanAttribute()
    {
        // The command id IS recorded on spans — it is the idempotency key an operator correlates by.
        // So it must never be a place a caller can smuggle content: this asserts the recorded value
        // is the id and nothing else rides along with it.
        var endpoint = Endpoint(out var workspace);
        var opened = endpoint.OpenWorkspace(Open(workspace), Peer());
        var capability = opened.Payload.As<IpcOpenResult>()!.Capability;

        endpoint.Invoke(
            new IpcRequest(
                IpcVersion.Current, WorkspaceOperations.Find, Secret, workspace, 1,
                capability, IpcPayloadTestExtensions.Json("{\"term\":\"x\",\"maxResults\":1}")),
            Peer());

        // The id is deliberately EXEMPT from the absence rule — it is the correlation key. What must
        // not happen is the secret appearing anywhere else, which is what a leak would look like.
        var elsewhere = Captured
            .SelectMany(a => a.Tags)
            .Where(t => !string.Equals(t.Key, "command.id", StringComparison.Ordinal))
            .Where(t => (t.Value ?? string.Empty).Contains(Secret, StringComparison.Ordinal))
            .Select(t => t.Key)
            .ToList();

        Assert.True(elsewhere.Count == 0, $"the secret reached: {string.Join(", ", elsewhere)}");
    }

    [Fact]
    public void ACapabilityToken_NeverReachesASpanAttribute()
    {
        // The token is the authority. A span carrying it turns every telemetry sink into a place
        // that authority can be read out of.
        var endpoint = Endpoint(out var workspace);
        var opened = endpoint.OpenWorkspace(Open(workspace), Peer());
        var capability = opened.Payload.As<IpcOpenResult>()!.Capability;

        endpoint.Invoke(
            new IpcRequest(
                IpcVersion.Current, WorkspaceOperations.Find, "cmd-1", workspace, 1,
                capability, IpcPayloadTestExtensions.Json("{\"term\":\"x\",\"maxResults\":1}")),
            Peer());

        AssertNoSpanCarries(capability);
    }

    [Fact]
    public async Task ASecretInARefreshPayload_ReachesNoSpanAttribute()
    {
        // Ingestion is the write path, and the scope id and revision it carries come from a caller.
        var refresh = new ScopeRefreshService((_, _, _) => Task.FromResult(3));
        var endpoint = Endpoint(out var workspace);
        refresh.Register(endpoint);

        var opened = endpoint.OpenWorkspace(Open(workspace), Peer());
        var capability = opened.Payload.As<IpcOpenResult>()!.Capability;

        endpoint.Invoke(
            new IpcRequest(
                IpcVersion.Current, ScopeRefreshService.Operations.Refresh, "cmd-1", workspace, 1,
                capability, IpcPayloadTestExtensions.Json(
                    $"{{\"scopeId\":\"{Secret}\",\"artifactRevision\":\"{Secret}\"}}")),
            Peer());

        await Task.Delay(200);

        // The scope id IS a legitimate span attribute — an operator needs to know which scope was
        // refreshed. What this pins is that it is the only place it appears, so a scope id is never
        // silently copied into another field where a redaction rule would not look for it.
        var unexpected = Captured
            .SelectMany(a => a.Tags)
            .Where(t => !string.Equals(t.Key, "scope.id", StringComparison.Ordinal))
            .Where(t => (t.Value ?? string.Empty).Contains(Secret, StringComparison.Ordinal))
            .Select(t => $"{t.Key}={t.Value}")
            .ToList();

        Assert.True(unexpected.Count == 0, $"the secret reached: {string.Join(", ", unexpected)}");
    }

    [Fact]
    public void ARejectedRequest_DoesNotEchoTheRejectedPayload()
    {
        // The failure path is where payloads most often leak: a rejection is tempting to make
        // "helpful" by quoting what was refused, and a refused request is exactly the one whose
        // contents nobody has validated.
        var endpoint = Endpoint(out var workspace);

        endpoint.Invoke(
            new IpcRequest(
                IpcVersion.Current, WorkspaceOperations.Find, "cmd-1", workspace, 1,
                Secret, IpcPayloadTestExtensions.Json($"{{\"term\":\"{Secret}\"}}")),
            Peer());

        AssertNoSpanCarries(Secret);
    }

    // ---- helpers --------------------------------------------------------------

    private void AssertNoSpanCarries(string secret)
    {
        var leaks = Captured
            .SelectMany(a => a.Tags.Select(t => (a.OperationName, t.Key, t.Value)))
            .Where(t => (t.Value ?? string.Empty).Contains(secret, StringComparison.Ordinal))
            .Select(t => $"{t.OperationName}/{t.Key}")
            .ToList();

        Assert.True(leaks.Count == 0, $"the seeded secret reached: {string.Join(", ", leaks)}");
    }

    private static DaemonEndpoint Endpoint(out string workspace)
    {
        workspace = $"ws-{Guid.NewGuid():N}";
        var endpoint = new DaemonEndpoint(workspace, new CapabilityRegistry(), _ => 1);
        WorkspaceOperations.Register(endpoint, new ProjectionService(TestWorkspace.Create().Store));
        return endpoint;
    }

    private static IpcRequest Open(string workspace) =>
        new(IpcVersion.Current, "open", "cmd-open", workspace, 1, null, null);

    private static IpcPeer Peer() => new("S-1-5-21-owner", 4242, "conn-a");

    private static string SourceRoot()
    {
        var directory = new DirectoryInfo(AppContext.BaseDirectory);

        while (directory is not null && !File.Exists(Path.Combine(directory.FullName, "AiDe.sln")))
        {
            directory = directory.Parent;
        }

        Assert.NotNull(directory);
        return Path.Combine(directory!.FullName, "src");
    }

    public void Dispose() => _listener.Dispose();
}
