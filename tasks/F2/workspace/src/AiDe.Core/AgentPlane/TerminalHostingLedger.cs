using System.Diagnostics;

namespace AiDe.Core.AgentPlane;

/// <summary>
/// Counts terminal-host constructions while it is open — the positive oracle behind spec R1's
/// "zero terminal hosting" claim.
/// </summary>
/// <remarks>
/// <para><b>An absence claim with no oracle is not evidence.</b> "No terminal was hosted" is
/// unfalsifiable as prose: it reads identically whether the plane avoided the terminal stack or
/// whether nobody looked. This makes it a number, so the claim is <c>== 0</c> against a counter that
/// can be shown going to 1.</para>
///
/// <para><b>It listens rather than instruments, and that is the point.</b>
/// <c>ConPtyTerminalSession.StartAsync</c> already opens a <c>terminal.start</c> activity on the
/// <c>aide.terminal.runtime</c> source, unconditionally, before it touches interop — so the
/// measurement rides the emission that is already on the normal path (IO2) and
/// <c>src/AiDe.Core/Terminal/</c> gains not one line. That matters twice: R4-core requires the
/// terminal stack to gain callers rather than semantics, and a counter added inside the thing being
/// measured is one an edit to that thing can remove without any test noticing.</para>
///
/// <para><b>It counts the attempt, not the success.</b> The activity opens before the pseudo console
/// exists, so a construction that then fails still counts. A lane that tried to host a terminal and
/// failed did not achieve "zero terminal hosting"; it achieved a broken terminal.</para>
///
/// <para><b>Scoped, because an <see cref="ActivityListener"/> is process-global.</b> The count
/// belongs to a run, so the ledger is a disposable window over one. Two overlapping ledgers each see
/// every start in the process, which is correct for a claim of the form "none happened anywhere
/// while this ran".</para>
/// </remarks>
public sealed class TerminalHostingLedger : IDisposable
{
    /// <summary>The activity source <c>ConPtyTerminalSession</c> publishes on. Observed, not assumed.</summary>
    public const string TerminalActivitySource = "aide.terminal.runtime";

    /// <summary>The activity name it opens for one construction.</summary>
    public const string TerminalStartActivity = "terminal.start";

    /// <summary>
    /// The activity name it opens once per session when the session ends — by its child's exit, by
    /// disposal, or by a construction that failed after the start was counted (INV-0010).
    /// </summary>
    public const string TerminalStopActivity = "terminal.stop";

    private readonly ActivityListener _listener;
    private long _constructions;
    private long _completions;

    private TerminalHostingLedger()
    {
        _listener = new ActivityListener
        {
            ShouldListenTo = source => string.Equals(source.Name, TerminalActivitySource, StringComparison.Ordinal),

            // AllDataAndRecorded rather than PropagationData: a sampler that declines leaves
            // StartActivity returning null, and the construction would then be invisible to the very
            // counter that exists to see it.
            Sample = (ref ActivityCreationOptions<ActivityContext> _) => ActivitySamplingResult.AllDataAndRecorded,
            ActivityStarted = activity =>
            {
                if (string.Equals(activity.OperationName, TerminalStartActivity, StringComparison.Ordinal))
                {
                    Interlocked.Increment(ref _constructions);
                }
                else if (string.Equals(activity.OperationName, TerminalStopActivity, StringComparison.Ordinal))
                {
                    Interlocked.Increment(ref _completions);
                }
            },
        };

        ActivitySource.AddActivityListener(_listener);
    }

    /// <summary>How many terminal hosts were constructed since this ledger opened.</summary>
    public long Constructions => Interlocked.Read(ref _constructions);

    /// <summary>
    /// How many sessions ended since this ledger opened. <c>Constructions − Completions</c> is the
    /// number of hosts the runtime still holds — the census-time invariant INV-0010 could not check.
    /// </summary>
    public long Completions => Interlocked.Read(ref _completions);

    /// <summary>Opens a ledger. Counting starts here and stops at <see cref="Dispose"/>.</summary>
    public static TerminalHostingLedger Open() => new();

    public void Dispose() => _listener.Dispose();
}
