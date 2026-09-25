using System.Diagnostics;
using AiDe.Core;
using AiDe.Core.Facts;
using AiDe.Core.Mcp;
using AiDe.Core.Projections;

namespace AiDe.Core.Tests;

/// <summary>
/// Instrumentation-over-inference: these read the emitted values back rather than asserting that
/// instrumentation "exists". A span nobody has ever observed is a claim, not a measurement.
/// They also enforce the privacy floor outward — no path, prompt or source text may appear in a tag.
/// </summary>
public sealed class TelemetryTests : IDisposable
{
    private readonly FixtureRepository _fixture = FixtureRepository.Create();
    private readonly string _dataDirectory =
        Path.Combine(Path.GetTempPath(), "aide-telemetry", Guid.NewGuid().ToString("N"));
    private readonly List<Activity> _captured = [];
    private readonly ActivityListener _listener;

    public TelemetryTests()
    {
        _listener = new ActivityListener
        {
            ShouldListenTo = source => source.Name.StartsWith("aide.", StringComparison.Ordinal),
            Sample = (ref ActivityCreationOptions<ActivityContext> _) => ActivitySamplingResult.AllDataAndRecorded,
            ActivityStopped = activity => _captured.Add(activity),
        };
        ActivitySource.AddActivityListener(_listener);
    }

    [Fact]
    public async Task IngestionAndProjection_EmitTheirNamedSpansWithReadableAttributes()
    {
        using var core = WorkspaceCore.Open("ws-1", _fixture.Root, _dataDirectory);
        await core.RefreshScopeAsync("fixture", "rev-1");
        core.Projections.Describe("Order", 50);

        var ingestion = Assert.Single(_captured, a => a.OperationName == "aide.ingestion.scope");
        Assert.Equal("fixture", ingestion.GetTagItem("scope.id"));
        Assert.Equal("rev-1", ingestion.GetTagItem("artifact.revision"));

        // The reader that produced the facts is its own axis, not a suffix on the revision. Without
        // it an operator cannot tell a graph built by this build from one built by the last, which
        // is the question behind "why is the Knowledge count still 0".
        Assert.Equal(
            AiDe.Core.Extraction.ScopeFingerprints.ExtractorGeneration,
            ingestion.GetTagItem("extractor.generation"));
        Assert.Equal("committed", ingestion.GetTagItem("outcome"));

        Assert.Contains(_captured, a => a.OperationName == "aide.projection.query");
    }

    [Fact]
    public async Task Dispatch_EmitsItsOutcomeSoAnOperatorCanAnswerDidItFail()
    {
        using var core = WorkspaceCore.Open("ws-1", _fixture.Root, _dataDirectory);
        await core.RefreshScopeAsync("fixture", "rev-1");

        var session = new FixtureTerminalSession("session-1", 1);
        await core.Dispatch.DispatchAsync(
            new Core.Dispatch.DispatchCommand(
                "ws-1", core.Store.CoreEpoch, new CallerPrincipal("shell", CallerKind.Shell),
                "cmd-telemetry", "draft-1", 1, "body", "session-1", 1),
            session);

        var span = Assert.Single(_captured, a => a.OperationName == "aide.terminal.session");
        Assert.Equal(nameof(DispatchState.PtyWriteAccepted), span.GetTagItem("outcome"));
    }

    /// <summary>
    /// The MCP span records the tool, the declared processing class, and the decision.
    /// </summary>
    /// <remarks>
    /// <para>The expected authorization changed to <c>Allow</c> under ADR-0022, which withdrew the
    /// processing-class gate: an agent in AI-DE holds a terminal in the workspace and can read the
    /// same files directly, so the gate constrained the polite interface while the impolite one
    /// stood open.</para>
    ///
    /// <para><b>The class is still on the span, and that is the point.</b> It has stopped being a
    /// control INPUT and remains an observation — what the session declared about itself. Dropping it
    /// would lose the only record of that claim, and the day a remote or sandboxed agent appears
    /// (ADR-0022's named residual risk) this attribute is where the evidence will already be.</para>
    ///
    /// <para>Renamed: the old name promised a denied error code it never asserted.</para>
    /// </remarks>
    [Fact]
    public async Task McpSpan_RecordsTheToolTheDeclaredClassAndTheDecision()
    {
        using var core = WorkspaceCore.Open("ws-1", _fixture.Root, _dataDirectory);
        await core.RefreshScopeAsync("fixture", "rev-1");

        core.Mcp.Describe(
            new McpCallerContext("ws-1", "s", SessionProcessingClass.ExternalProcessing,
                new CallerPrincipal("agent", CallerKind.McpClient)),
            "Order", 50);

        var span = Assert.Single(_captured, a => a.OperationName == "aide.mcp.request");
        Assert.Equal("describe", span.GetTagItem("tool"));
        Assert.Equal(nameof(SessionProcessingClass.ExternalProcessing), span.GetTagItem("session.processing_class"));
        Assert.Equal(nameof(ToolAuthorization.Allow), span.GetTagItem("authorization"));
    }

    // P1-PRIV — the allowlist enforced outward: a seeded secret must not reach any span attribute.
    [Fact]
    public async Task NoSpanAttribute_CarriesAPathPromptOrSourceText()
    {
        const string seededSecret = "SEEDED-SECRET-b3f1a9";
        using var core = WorkspaceCore.Open("ws-1", _fixture.Root, _dataDirectory);
        await core.RefreshScopeAsync("fixture", "rev-1");

        var session = new FixtureTerminalSession("session-1", 1);
        await core.Dispatch.DispatchAsync(
            new Core.Dispatch.DispatchCommand(
                "ws-1", core.Store.CoreEpoch, new CallerPrincipal("shell", CallerKind.Shell),
                "cmd-secret", "draft-1", 1, $"please review {seededSecret}", "session-1", 1),
            session);
        core.Projections.Describe("Order", 50);
        core.Projections.SolutionTree(new SolutionTreeQuery());
        core.Projections.EntryPoints(new EntryPointsQuery());

        foreach (var activity in _captured)
        {
            foreach (var (key, value) in activity.Tags)
            {
                var rendered = value ?? string.Empty;
                Assert.DoesNotContain(seededSecret, rendered, StringComparison.Ordinal);
                Assert.DoesNotContain(_fixture.Root, rendered, StringComparison.OrdinalIgnoreCase);
                Assert.False(key.Contains("prompt", StringComparison.OrdinalIgnoreCase));
                Assert.False(key.Contains("path", StringComparison.OrdinalIgnoreCase));
            }
        }
    }

    public void Dispose()
    {
        _listener.Dispose();
        _fixture.Dispose();
        try
        {
            Directory.Delete(_dataDirectory, recursive: true);
        }
        catch (IOException)
        {
            // Leaked temp state must never fail a run.
        }
    }
}
