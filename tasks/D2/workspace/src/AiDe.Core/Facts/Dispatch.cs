namespace AiDe.Core.Facts;

/// <summary>
/// The declared downstream processing posture of an agent session. Authorization for every MCP tool
/// call is bound to this (ADR-0011): the transport says who connected, this says where the bytes go next.
/// </summary>
public enum SessionProcessingClass
{
    /// <summary>Processed on this device; no external provider is invoked.</summary>
    LocalOnly,

    /// <summary>May send content to an external provider. Rich transfer is blocked in v1.</summary>
    ExternalProcessing,

    /// <summary>Posture could not be established. Fails closed, exactly like ExternalProcessing.</summary>
    UnknownProcessing,
}

public enum CallerKind
{
    Shell,
    McpClient,
}

/// <summary>
/// A stable principal, server-derived from the authenticated connection and invariant across
/// reconnects and core epochs. Never read from a command payload, and never connection-scoped —
/// a connection-scoped identity would void receipt dedup across the crash window it exists for.
/// </summary>
public sealed record CallerPrincipal(string Id, CallerKind Kind);

/// <summary>
/// The folded state of one dispatch key. <see cref="Pending"/> is durable and written *before* the
/// terminal write; recovery resolves an unresolved attempt to <see cref="DeliveryUnknown"/>.
/// </summary>
public enum DispatchState
{
    /// <summary>Attempt recorded, outcome not yet known. Never a terminal state after recovery.</summary>
    Pending,

    /// <summary>The terminal accepted the bytes. This is NOT agent acceptance (ADR-0007).</summary>
    PtyWriteAccepted,

    Rejected,
    TimedOut,
    Failed,

    /// <summary>
    /// The process died between the attempt and the outcome. Blocks automatic resend: a human must
    /// confirm a new dispatch key (ADR-0006).
    /// </summary>
    DeliveryUnknown,
}

/// <summary>The folded receipt for one dispatch key, derived from its attempt and outcome events.</summary>
public sealed record DispatchReceipt(
    string DispatchKey,
    DispatchState State,
    string SessionId,
    long SessionGeneration,
    string? ErrorCode,
    DateTimeOffset AttemptedAt)
{
    /// <summary>
    /// True when a retry may not re-execute. Every state qualifies once an attempt exists — that is
    /// the point of the write-ahead record.
    /// </summary>
    public bool BlocksReExecution => true;
}

/// <summary>What a terminal write actually proved.</summary>
public enum PtyWriteResult
{
    Accepted,

    /// <summary>The live generation no longer matched the bound one; zero bytes were written.</summary>
    GenerationChanged,

    Failed,
}
