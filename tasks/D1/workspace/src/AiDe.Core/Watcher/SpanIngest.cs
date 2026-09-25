namespace AiDe.Core.Watcher;

/// <summary>The outcome of attempting to ingest one span.</summary>
public enum IngestOutcome
{
    /// <summary>A new span was appended.</summary>
    Accepted,

    /// <summary>The span's content-addressed id was already present; ignored idempotently.</summary>
    DuplicateIgnored,

    /// <summary>The presenting process failed capability verification; nothing was stored.</summary>
    Rejected,
}

/// <summary>
/// Ingests observed spans, verifying the session capability first (so a forged session cannot write
/// facts) and then appending idempotently by content-addressed id (ADR-0006 / ADR-0023 watcher-observation-projection).
/// </summary>
public sealed class SpanIngest
{
    private readonly IWatcherObservationStore _store;
    private readonly ITrustedRegistrar _registrar;

    public SpanIngest(IWatcherObservationStore store, ITrustedRegistrar registrar)
    {
        _store = store;
        _registrar = registrar;
    }

    /// <summary>
    /// Verifies the capability, then appends the span. A redelivered or out-of-order span is safe:
    /// duplicates return <see cref="IngestOutcome.DuplicateIgnored"/>, and facts are order-independent.
    /// </summary>
    public IngestOutcome Ingest(string sessionId, SessionCapability capability, ObservedSpan span)
    {
        ArgumentNullException.ThrowIfNull(capability);
        ArgumentNullException.ThrowIfNull(span);

        if (!_registrar.Verify(sessionId, capability))
        {
            return IngestOutcome.Rejected;
        }

        return _store.TryAppendSpan(span) ? IngestOutcome.Accepted : IngestOutcome.DuplicateIgnored;
    }
}
