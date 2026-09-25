namespace AiDe.Core.Projections;

/// <summary>One message in an interaction: who called whom, and what they called.</summary>
/// <param name="Ordinal">
/// 1-based position in the caller's own sequence. Derived from source position, not stored — a call
/// sequence has exactly one correct order and it is the order it is written in.
/// </param>
/// <param name="Location"><c>line:col</c> of the call site, so a message can be navigated to.</param>
public sealed record InteractionMessage(
    int Ordinal, string From, string To, string Member, string Location);

/// <summary>
/// One caller's outgoing calls in order — the data a UML sequence diagram draws.
/// </summary>
/// <param name="Truncated">
/// True when the caller has more calls than were returned. Said out loud because a sequence diagram
/// that stops early without saying so is confidently incomplete, which is worse than an empty one.
/// </param>
public sealed record InteractionResult(
    string NodeId,
    IReadOnlyList<InteractionMessage> Messages,
    bool Truncated,
    ResultBounds Bounds,
    string SourceRevision);
