namespace AiDe.Core.Dispatch;

/// <summary>Whether a session can be given a prompt right now.</summary>
/// <remarks>
/// Deliberately three-valued. "Not ready" and "we cannot tell" are different situations with
/// different correct responses, and collapsing them is how a prompt gets sent into a dialog box.
/// </remarks>
public enum SessionReadiness
{
    /// <summary>
    /// Nothing reports readiness for this session, so it cannot be established.
    /// </summary>
    /// <remarks>
    /// The default, and the one that matters. An agent CLI showing a first-run trust gate,
    /// authenticating, mid-response, or genuinely idle all look identical from outside — a running
    /// process attached to a pty. Measured: a prompt dispatched into Claude Code's trust gate was
    /// consumed by that dialog, where the same Enter that submits a prompt confirms "No, exit"
    /// (<c>spikes/agent-dispatch</c>).
    /// </remarks>
    Unknown,

    /// <summary>Readiness is reported and the session is waiting for input.</summary>
    Ready,

    /// <summary>Readiness is reported and the session is busy or gone.</summary>
    NotReady,
}

/// <summary>How a session's readiness was established. Not all evidence is equal.</summary>
public enum ReadinessEvidence
{
    /// <summary>Nothing reports it.</summary>
    None,

    /// <summary>
    /// OSC 133 signed with the session nonce — the session's own authenticated claim.
    /// </summary>
    ShellIntegrationNonce,

    /// <summary>
    /// A configured marker was seen in the session's output.
    /// </summary>
    /// <remarks>
    /// <b>Weaker than the nonce, and deliberately named so.</b> Output is forgeable in principle,
    /// and a pattern can match a line that merely mentions the prompt. It is accepted because the
    /// alternative measured in <c>spikes/agent-dispatch</c> is that an agent can only ever be
    /// refused — a correct refusal that is also a dead end. ADR-0007's bar for claiming the agent
    /// ACCEPTED a prompt is unchanged and still unmet; this establishes only that it is listening.
    /// </remarks>
    ObservedPattern,
}

/// <summary>
/// Establishes whether a session is ready for a prompt, from evidence rather than from hope.
/// </summary>
/// <remarks>
/// <para><b>ADR-0007 already requires readiness evidence</b> before an adapter may claim agent
/// acceptance. What was missing was the other half: what to do when there is none. Until this, a
/// prompt was written and reported <c>PtyWriteAccepted</c> regardless — which is true about the
/// bytes and misleading about the outcome.</para>
///
/// <para><b>Shell integration is the only readiness evidence that exists today.</b> OSC 133 with the
/// session nonce is what makes <see cref="SessionActivity.Ready"/> a claim rather than a guess; a
/// session without it has an activity value derived from output timing, which is not the same thing
/// and must not be treated as one.</para>
/// </remarks>
public static class SessionReadinessPolicy
{
    /// <summary>
    /// Readiness for <paramref name="session"/>, given whether its shell integration is active.
    /// </summary>
    /// <param name="hasReadinessEvidence">
    /// True only when something authenticates the session's own claim about its state — today, the
    /// OSC 133 nonce. Derived output timing does not count: a quiet agent mid-thought looks exactly
    /// like an idle one.
    /// </param>
    public static SessionReadiness Evaluate(ITerminalSession session, bool hasReadinessEvidence) =>
        Evaluate(session, hasReadinessEvidence ? ReadinessEvidence.ShellIntegrationNonce : ReadinessEvidence.None);

    /// <summary>Readiness for <paramref name="session"/>, given what kind of evidence exists.</summary>
    public static SessionReadiness Evaluate(ITerminalSession session, ReadinessEvidence evidence)
    {
        ArgumentNullException.ThrowIfNull(session);

        // Checked BEFORE the evidence kind: a session that has ended is not "unknown", whatever its
        // integration reports, and saying so is more useful than saying nothing.
        if (session.Activity == SessionActivity.Ended) return SessionReadiness.NotReady;

        if (evidence == ReadinessEvidence.None) return SessionReadiness.Unknown;

        return session.Activity switch
        {
            SessionActivity.Ready => SessionReadiness.Ready,
            SessionActivity.Starting or SessionActivity.Busy => SessionReadiness.NotReady,
            _ => SessionReadiness.NotReady,
        };
    }

    /// <summary>The sentence a user is shown when a dispatch is refused.</summary>
    /// <remarks>
    /// Each case says what would change it. "Not ready" resolves by waiting; "unknown" does not, and
    /// telling a user to wait for something that will never happen is worse than telling them why.
    /// </remarks>
    public static string Explain(SessionReadiness readiness) => readiness switch
    {
        SessionReadiness.Ready => "The session is ready.",

        SessionReadiness.NotReady =>
            "The session is busy or has ended. Wait for it to return to a prompt and try again.",

        _ =>
            "This session does not report when it is ready for input, so a prompt could be consumed " +
            "by whatever it is currently showing — a sign-in, a confirmation, or a reply in progress. " +
            "Type into the terminal directly, or use a session with shell integration.",
    };
}
