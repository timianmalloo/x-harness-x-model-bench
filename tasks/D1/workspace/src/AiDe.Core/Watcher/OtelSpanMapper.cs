namespace AiDe.Core.Watcher;

/// <summary>
/// Transport-neutral harness span. An OTLP receiver or an in-process <c>ActivityListener</c>
/// constructs this, so the mapper is coupled to no single transport (spike S1: the mapping is the
/// contract, not the wire).
/// </summary>
public sealed record HarnessSpan(
    string TraceId,
    string SpanId,
    string OperationName,
    IReadOnlyDictionary<string, string?> Attributes);

/// <summary>A harness registration / session-start event, as a bag of attributes.</summary>
public sealed record HarnessRegistration(IReadOnlyDictionary<string, string?> Attributes);

/// <summary>
/// The pinned OpenTelemetry / GenAI attribute snapshot the ingest wire consumes. The GenAI keys are
/// marked <b>Development</b> upstream, so a change here is a contract change guarded by a regression
/// test (Testing Strategy A6) rather than silent drift (spike S1 finding 5).
/// </summary>
public static class OtelAttributes
{
    public const string SessionId = "session.id";
    public const string ServiceName = "service.name";          // -> Harness name
    public const string ServiceVersion = "service.version";
    public const string GenAiModel = "gen_ai.request.model";   // -> Model name
    public const string GenAiModelVersion = "gen_ai.model.version";
    public const string RepoPath = "repo.canonical_path";
    public const string RepoDisplay = "repo.display_name";
    public const string WorktreeBranch = "worktree.branch";
    public const string WorktreePath = "worktree.path";
    public const string TerminalId = "terminal.id";
    public const string AgentName = "agent.name";
}

/// <summary>
/// Maps harness telemetry into the watcher domain. Pure, deterministic, stateless.
///
/// Pattern: Anti-Corruption Layer + Adapter (DDD) - it is the one seam that keeps the preview
/// OTel/GenAI vocabulary out of the domain, so upstream schema churn changes only this type and its
/// regression test. It treats a span's <c>session.id</c> as a claim, never authority: the wire binds
/// spans to the capability issued at registration (ADR-0020 trusted-registrar-harness-model-identity), so the mapper mints no trust.
/// </summary>
public static class OtelSpanMapper
{
    /// <summary>
    /// Maps an OTel span to an <see cref="ObservedSpan"/>. <paramref name="recordedAt"/> is stamped by
    /// the wire at ingest, never trusted from the span (clock-skew prevention). Throws
    /// <see cref="WatcherException"/> (LK-0004) when the span carries no <c>session.id</c>.
    /// </summary>
    public static ObservedSpan MapSpan(HarnessSpan span, DateTimeOffset recordedAt)
    {
        ArgumentNullException.ThrowIfNull(span);
        var sessionId = Value(span.Attributes, OtelAttributes.SessionId)
            ?? throw Malformed($"span carries no '{OtelAttributes.SessionId}' attribute");
        return new ObservedSpan(sessionId, span.TraceId, span.SpanId, span.OperationName, recordedAt);
    }

    /// <summary>
    /// Maps a registration event to a <see cref="SessionBinding"/>. Harness and model are absent when
    /// their attributes are absent (rendered Not Recorded, spec US-13); trust is <c>Verified</c> only
    /// when the harness names itself via <c>service.name</c>, else <c>Asserted</c> (ADR-0020 trusted-registrar-harness-model-identity). Throws
    /// LK-0004 when a required identity attribute is missing.
    /// </summary>
    public static SessionBinding MapRegistration(HarnessRegistration registration)
    {
        ArgumentNullException.ThrowIfNull(registration);
        var attrs = registration.Attributes;

        var repo = new RepositoryIdentity(
            Required(attrs, OtelAttributes.RepoPath),
            Required(attrs, OtelAttributes.RepoDisplay));

        var harnessName = Value(attrs, OtelAttributes.ServiceName);
        var modelName = Value(attrs, OtelAttributes.GenAiModel);

        return new SessionBinding(
            repo,
            new WorktreeIdentity(repo, Required(attrs, OtelAttributes.WorktreeBranch), Required(attrs, OtelAttributes.WorktreePath)),
            new TerminalIdentity(Required(attrs, OtelAttributes.TerminalId)),
            new AgentIdentity(Required(attrs, OtelAttributes.AgentName)),
            harnessName is null ? null : new HarnessIdentity(harnessName, Value(attrs, OtelAttributes.ServiceVersion) ?? "unknown"),
            modelName is null ? null : new ModelIdentity(modelName, Value(attrs, OtelAttributes.GenAiModelVersion) ?? "unknown"),
            harnessName is null ? TrustClassification.Asserted : TrustClassification.Verified);
    }

    private static string? Value(IReadOnlyDictionary<string, string?> attrs, string key)
        => attrs.TryGetValue(key, out var v) && !string.IsNullOrWhiteSpace(v) ? v : null;

    private static string Required(IReadOnlyDictionary<string, string?> attrs, string key)
        => Value(attrs, key) ?? throw Malformed($"registration missing required attribute '{key}'");

    private static WatcherException Malformed(string detail)
        => new(WatcherErrorCodes.MalformedEvent, $"Harness event could not be mapped: {detail}.");
}
