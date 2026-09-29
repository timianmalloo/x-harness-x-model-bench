using AiDe.Core.AgentPlane;

namespace AiDe.Core.Presentation.Sessions;

/// <summary>
/// Where a lane's <c>permission.request</c> becomes visible to the operator, and the recorded
/// ordinals that make "it surfaced in time" checkable (R16 b3).
/// </summary>
/// <remarks>
/// <para><b>An ordinal, never a duration.</b> R16 b3 says "within one event cycle", which is not a
/// quantity — there is no clock reading that distinguishes a correct implementation from a lucky
/// one, and a <c>&lt; N ms</c> assertion is a wall-clock budget assertion that
/// <c>tools/verify-perf-assertions.py</c> refuses (DC-107). The observable this type records
/// instead is: <b>the request was raised here before the session document dequeued the next
/// event</b>. Both moments are counted, so the claim is arithmetic.</para>
///
/// <para><b>The snapshot is what makes the claim provable.</b> "Raised before the next event" is a
/// statement about two moments, and a surface that only kept the request could testify to one of
/// them. <see cref="DispatchedWhenRaised"/> samples the document's dispatch count at the instant of
/// the raise, which puts both on one timeline with no clock and no sleep — the idiom
/// <c>AiDe.Core.Tests.AgentPlane.RecordingTextWriter</c> already uses for the same shape of claim.</para>
///
/// <para><b>Not recorded, never a plausible zero.</b> Before any request arrives the two ordinals
/// are <see cref="NotRaised"/> (-1), which no real ordinal can be, rather than 0 — which would read
/// as "raised before the first event" (IO12).</para>
/// </remarks>
public sealed class SessionPermissionSurface
{
    /// <summary>What both ordinals read before anything has been raised. Never a real ordinal.</summary>
    public const long NotRaised = -1;

    /// <summary>Whether a request is currently showing.</summary>
    public bool IsRaised { get; private set; }

    /// <summary>What the request says, or null when none is showing.</summary>
    public string? Prompt { get; private set; }

    /// <summary>The <see cref="RunEvent.Seq"/> of the event that raised it.</summary>
    public long RaisedAtOrdinal { get; private set; } = NotRaised;

    /// <summary>
    /// How many events the session document had dispatched at the instant of the raise. Compared
    /// against the permission event's own position, this is the whole of R16 b3's claim.
    /// </summary>
    public long DispatchedWhenRaised { get; private set; } = NotRaised;

    /// <summary>Raised whenever a request appears, so a view can show it without polling.</summary>
    public event Action? Changed;

    /// <summary>Shows a request, recording both ordinals.</summary>
    /// <param name="evt">The <c>permission.request</c> event.</param>
    /// <param name="dispatchedSoFar">The document's dispatch count, sampled by the caller at this instant.</param>
    public void Raise(RunEvent evt, long dispatchedSoFar)
    {
        ArgumentNullException.ThrowIfNull(evt);

        IsRaised = true;
        Prompt = Describe(evt);
        RaisedAtOrdinal = evt.Seq;
        DispatchedWhenRaised = dispatchedSoFar;
        Changed?.Invoke();
    }

    /// <summary>Clears the request once the operator has answered it.</summary>
    /// <remarks>
    /// The two ordinals are deliberately <b>kept</b>: they are the record of what happened, and a
    /// control that erases its own evidence when the overlay closes cannot be asked about it after.
    /// </remarks>
    public void Clear()
    {
        IsRaised = false;
        Prompt = null;
        Changed?.Invoke();
    }

    private static string Describe(RunEvent evt)
    {
        if (evt.Body.TryGetPropertyValue("title", out var title)
            && title?.GetValue<string>() is { Length: > 0 } text)
        {
            return text;
        }

        return $"{evt.AgentId} is asking for permission.";
    }
}
