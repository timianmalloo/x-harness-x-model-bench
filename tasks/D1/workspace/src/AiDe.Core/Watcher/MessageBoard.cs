namespace AiDe.Core.Watcher;

/// <summary>
/// The kinds of Message Board entry (spec US-4). The first four are top-level posts; Reply and
/// Acknowledgement reference a parent message and cannot create an orphan thread.
/// </summary>
public enum BoardMessageKind { Question, Decision, Breadcrumb, KnowledgeCandidate, Reply, Acknowledgement }

/// <summary>
/// One append event on a repository's Message Board (spec line 233). The envelope, order, and thread
/// references are append-only; only a policy redaction may null the <see cref="Content"/> and set
/// <see cref="Tombstoned"/>, leaving the immutable envelope (spec line 210). <see cref="Content"/> is
/// <b>quarantined untrusted data</b> - it can never instruct a grader (US-4 #4); grader-injection
/// shapes are additionally <see cref="InjectionFlagged"/> (US-4 #5).
/// </summary>
public sealed record BoardMessage(
    string MessageId,
    string RepositoryKey,
    BoardMessageKind Kind,
    string AuthorSessionId,
    TrustClassification AuthorTrust,
    string? ParentMessageId,
    string? Content,
    bool Quarantined,
    bool InjectionFlagged,
    bool Tombstoned,
    DateTimeOffset RecordedAt,
    int Seq);

/// <summary>
/// A deterministic scanner for grader/learning-promoter injection shapes in untrusted board content
/// (US-4 #5). It is a <b>flag</b>, not a safety boundary: the invariance guarantee (an injection
/// fixture never changes a score) comes from the scorer consuming typed deterministic signals rather
/// than board text (slice 5), not from perfect detection here. A small pattern list, deliberately not
/// an ML classifier (Simplifier).
/// </summary>
public static class GraderInjectionScanner
{
    private static readonly string[] Shapes =
    [
        "score 100", "score: 100", "give it 100", "score 4", "give a 4",
        "ignore the rubric", "ignore previous", "ignore all previous", "disregard the rubric",
        "promote this lesson", "promote this", "override the floor", "bypass the floor",
    ];

    public static bool LooksLikeInjection(string? content)
    {
        if (string.IsNullOrEmpty(content))
        {
            return false;
        }

        foreach (var shape in Shapes)
        {
            if (content.Contains(shape, StringComparison.OrdinalIgnoreCase))
            {
                return true;
            }
        }

        return false;
    }
}

/// <summary>The per-repository, append-only Message Board (spec US-4).</summary>
public interface IMessageBoard
{
    BoardMessage Post(string repositoryKey, string sessionId, SessionCapability capability, BoardMessageKind kind, string content);
    BoardMessage Reply(string repositoryKey, string sessionId, SessionCapability capability, string parentMessageId, string content);
    BoardMessage Acknowledge(string repositoryKey, string sessionId, SessionCapability capability, string parentMessageId);
    void Redact(string messageId);
}

/// <summary>
/// The default in-process Message Board. Every write is capability-verified (only the authenticated
/// session posts as itself - LK-0001 on a forged capability); the message carries the session's own
/// trust as provenance (US-4 #1). A reply/acknowledgement must reference an existing parent <b>in the
/// same repository</b> or it is rejected as an orphan (US-4 #2). Content is stored quarantined and
/// injection-flagged (US-4 #4/#5). A policy redaction tombstones the payload (US-4 #6).
/// </summary>
public sealed class MessageBoardService : IMessageBoard
{
    private readonly IWatcherObservationStore _store;
    private readonly ITrustedRegistrar _registrar;
    private readonly TimeProvider _time;
    private readonly Func<string> _newMessageId;
    private readonly object _gate = new();

    public MessageBoardService(
        IWatcherObservationStore store,
        ITrustedRegistrar registrar,
        TimeProvider time,
        Func<string>? newMessageId = null)
    {
        ArgumentNullException.ThrowIfNull(store);
        ArgumentNullException.ThrowIfNull(registrar);
        ArgumentNullException.ThrowIfNull(time);
        _store = store;
        _registrar = registrar;
        _time = time;
        _newMessageId = newMessageId ?? (() => Guid.NewGuid().ToString("n"));
    }

    public BoardMessage Post(string repositoryKey, string sessionId, SessionCapability capability, BoardMessageKind kind, string content)
    {
        if (kind is BoardMessageKind.Reply or BoardMessageKind.Acknowledgement)
        {
            throw new WatcherException(WatcherErrorCodes.InvalidBinding,
                $"A {kind} references a parent - use Reply/Acknowledge, not Post.");
        }

        return Append(repositoryKey, sessionId, capability, kind, parentMessageId: null, content);
    }

    public BoardMessage Reply(string repositoryKey, string sessionId, SessionCapability capability, string parentMessageId, string content)
        => Append(repositoryKey, sessionId, capability, BoardMessageKind.Reply, RequireParent(repositoryKey, parentMessageId), content);

    public BoardMessage Acknowledge(string repositoryKey, string sessionId, SessionCapability capability, string parentMessageId)
        => Append(repositoryKey, sessionId, capability, BoardMessageKind.Acknowledgement, RequireParent(repositoryKey, parentMessageId), content: null);

    public void Redact(string messageId)
    {
        ArgumentException.ThrowIfNullOrEmpty(messageId);
        _store.RedactBoardMessage(messageId);
    }

    private BoardMessage Append(
        string repositoryKey, string sessionId, SessionCapability capability,
        BoardMessageKind kind, string? parentMessageId, string? content)
    {
        ArgumentException.ThrowIfNullOrEmpty(repositoryKey);
        ArgumentException.ThrowIfNullOrEmpty(sessionId);
        RequireCapability(sessionId, capability);

        lock (_gate)
        {
            var trust = _store.FindSession(sessionId)?.Binding.Trust ?? TrustClassification.Asserted;
            var message = new BoardMessage(
                _newMessageId(), repositoryKey, kind, sessionId, trust, parentMessageId,
                content,
                Quarantined: true, // all board content is untrusted data (Confused Deputy mitigation)
                InjectionFlagged: GraderInjectionScanner.LooksLikeInjection(content),
                Tombstoned: false,
                _time.GetUtcNow(),
                Seq: _store.BoardMessages(repositoryKey).Count + 1);
            _store.AppendBoardMessage(message);
            return message;
        }
    }

    private string RequireParent(string repositoryKey, string parentMessageId)
    {
        ArgumentException.ThrowIfNullOrEmpty(parentMessageId);
        var parent = _store.FindBoardMessage(parentMessageId);

        // A reply/ack must reference an existing parent in THIS repository - never an orphan, never a
        // cross-repository thread (US-4 #2).
        if (parent is null || !string.Equals(parent.RepositoryKey, repositoryKey, StringComparison.Ordinal))
        {
            throw new WatcherException(WatcherErrorCodes.InvalidBinding,
                $"No parent message '{parentMessageId}' exists in repository '{repositoryKey}'; an orphan thread is refused.");
        }

        return parentMessageId;
    }

    private void RequireCapability(string sessionId, SessionCapability capability)
    {
        ArgumentNullException.ThrowIfNull(capability);
        if (!_registrar.Verify(sessionId, capability))
        {
            throw new WatcherException(
                WatcherErrorCodes.ForgeryRejected,
                "The presented session capability did not match the session's current capability.");
        }
    }
}
