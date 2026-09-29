using System.Globalization;

namespace AiDe.Core.Presentation.Sessions;

/// <summary>
/// The session thread's read model — the fold the session document renders and never a second
/// store (DS-1 P3; <c>DESIGN.md</c> SC1 <i>derived, never a second store</i>).
/// </summary>
/// <remarks>
/// <para><b>The snapshot travels in the event.</b> <see cref="Changed"/> carries the
/// <see cref="ThreadSnapshot"/> it announces; a subscriber never reads <see cref="Current"/> back at
/// apply time, because two raises before one apply would read one state and lose a transition
/// (the Test Architect's pass-1 Blocker on DS-1).</para>
///
/// <para><b>The catch-up boundary is the read model's.</b> While a history is being replayed it
/// publishes snapshots with <see cref="ThreadSnapshot.IsCaughtUp"/> false at any cadence; the first
/// caught-up snapshot is the folded history; after it, <see cref="Changed"/> is raised exactly once
/// per applied event with <see cref="ThreadSnapshot.Version"/> incremented by one, raises
/// serialized. <c>TheReadModelPublishesOneSnapshotPerAppliedEventTests</c> proves it on the
/// run-channel implementer; CV-2's twin proves it on the envelope-backed one.</para>
/// </remarks>
public interface ISessionThread
{
    /// <summary>The latest published snapshot — an immutable reference, safe to read from any thread.</summary>
    ThreadSnapshot Current { get; }

    /// <summary>Raised with the snapshot it announces. May be raised off the UI thread.</summary>
    event Action<ThreadSnapshot>? Changed;
}

/// <summary>The read model's state after one applied event. Version 0 is the folded history at catch-up.</summary>
public sealed record ThreadSnapshot(IReadOnlyList<TurnView> Turns, long Version, bool IsCaughtUp)
{
    /// <summary>The in-flight turn (Ruling 77: at most one) — derived, never a member.</summary>
    public TurnView? InFlight => Turns.LastOrDefault(t => t.State is TurnState.Running or TurnState.Waiting);

    /// <summary>The queued turn (Ruling 95: exactly one or none) — derived, never a member.</summary>
    public TurnView? Queued => Turns.LastOrDefault(t => t.State == TurnState.Queued);

    /// <summary>
    /// The turn the queued one waits behind: the in-flight turn while one runs or waits, else the
    /// last turn that ran — the one whose Stop or failure left the queued turn waiting for the
    /// operator (Ruling 95: <i>b1 stopped; b2 is waiting</i>). Null with nothing queued.
    /// </summary>
    public TurnView? QueuedBehind =>
        Queued is null ? null : InFlight ?? Turns.LastOrDefault(t => t.State is not (TurnState.Queued or TurnState.Cancelled));

    /// <summary>
    /// Whether the queued turn waits on the operator rather than on a run (Ruling 95): nothing is in
    /// flight and the turn before it ended <c>Stopped</c> or <c>Failed</c> — the drain never sends
    /// after those, so <i>Send now</i> is the operator's. Derived from the turns, so the instant
    /// between a Completed conclusion and the drain's start never reads as waiting-on-you.
    /// </summary>
    public bool QueuedAwaitsYou =>
        Queued is not null && InFlight is null && QueuedBehind is { State: TurnState.Stopped or TurnState.Failed };
}

/// <summary>The one encoding of a turn's lifecycle (DM7): the state decides which of Outcome / Waiting exists.</summary>
public enum TurnState
{
    Running,
    Waiting,
    Completed,
    Answered,
    Failed,
    Stopped,

    /// <summary>A <c>submitted</c> with no <c>consumed</c> (ADR-0034): an explicit negative, never an absent row.</summary>
    NotRecorded,

    /// <summary>
    /// Compiled and submitted, waiting to be sent after the turn in flight (Ruling 95's <i>Wait</i>):
    /// exactly the bytes that will be sent, no run yet. Exactly one per session.
    /// </summary>
    Queued,

    /// <summary>
    /// A queued turn the operator cancelled before it was sent (Ruling 95): terminal, so the
    /// append-only stream keeps its row and its envelope gets its <c>consumed</c>; its words went
    /// back to the editor. Never ran, so it carries no counts.
    /// </summary>
    Cancelled,
}

/// <summary>One decoration row of the turn's envelope: <c>class · tier · lease · shape · template</c>, each with its source and reason.</summary>
/// <param name="Name">The decoration's name: <c>class</c>, <c>tier</c>, <c>lease</c>, <c>shape</c>, <c>template</c>.</param>
/// <param name="Value">The current value, as the decoration line shows it.</param>
/// <param name="Source">Where it came from: session-default · operator · rule · derived · mechanical · projection · called · submitted.</param>
/// <param name="Reason">Why, in a sentence the provenance disclosure shows.</param>
public sealed record DecorationRow(string Name, string Value, string Source, string Reason);

/// <summary>Tokens and requests a run consumed (Ruling 78). Absent usage is a null <see cref="Spend"/>, never zero.</summary>
public sealed record Spend(long In, long Cached, long Out, int Requests)
{
    /// <summary>Tokens in + out — the one number the header sums.</summary>
    public long Tokens => In + Out;
}

/// <summary>The reply side's outcome line. The word derives from <see cref="TurnView.State"/> (+ <see cref="ExitCode"/>).</summary>
/// <param name="Lane">The lane that answered: <c>conductor</c> for a T0 answer, else the engine id.</param>
/// <param name="ExitCode">The lane's exit code on a failure, when it reported one.</param>
/// <param name="Edits">Files touched, when the run reported them.</param>
/// <param name="Spend">The measured spend, or null — <i>not recorded</i>, never 0.</param>
/// <param name="Duration">Run start → outcome, when both were observed.</param>
/// <param name="EventCount">The run's <c>RunEvent</c> count.</param>
public sealed record OutcomeView(string Lane, int? ExitCode, int? Edits, Spend? Spend, TimeSpan? Duration, int EventCount);

/// <summary>One line of a turn's run — not <c>ConsoleRow</c>: that row has no timestamp and no origin.</summary>
/// <param name="At">Receipt time.</param>
/// <param name="Lane">The lane's display name.</param>
/// <param name="Kind">The event kind, verbatim.</param>
/// <param name="Text">What to show — plain text, never markup.</param>
/// <param name="Origin"><c>run</c>, or <c>compile</c> for a <c>compile.*</c> event shown under its envelope's turn.</param>
/// <param name="Tool">What a <c>tool.call</c> / <c>tool.result</c> frame stated (Ruling 82); null for every other kind.</param>
public sealed record EventLine(DateTimeOffset At, string Lane, string Kind, string Text, string Origin, ToolFacts? Tool = null);

/// <summary>Every act an operator can request on a turn — one channel (DS-1 §Contracts).</summary>
public enum TurnActionKind
{
    Stop,
    Deny,
    AllowOnce,
    AllowThisTurn,
    OpenSessionSettings,
    SendAgain,
    OpenLog,
    UseAsNextDraft,
    OpenConsoleAt,

    /// <summary>Drops a queued turn (Ruling 95): its words return to the editor; editing is cancel-and-redraft, never in place.</summary>
    Cancel,

    /// <summary>Sends a queued turn now (Ruling 95) — offered only when it waits on the operator after a Stop or a failure.</summary>
    SendNow,
}

/// <summary>A permission or cap request the turn is waiting on (SC7). Deny first.</summary>
public sealed record WaitingRequest(string RequestId, string Kind, string Text, IReadOnlyList<TurnActionKind> Actions);

/// <summary>
/// One accepted turn of one session, identified by its ordinal — the read model's grain (DS-1 §Data
/// model). Every field is a projection of the envelope fold joined to the run channel.
/// </summary>
public sealed record TurnView
{
    public TurnView(
        int ordinal,
        string envelopeId,
        string sourceText,
        IReadOnlyList<DecorationRow> decorations,
        TurnState state,
        OutcomeView? outcome,
        WaitingRequest? waiting,
        IReadOnlyList<EventLine> events,
        string sentBytes,
        DateTimeOffset at)
    {
        ArgumentOutOfRangeException.ThrowIfLessThan(ordinal, 1);
        ArgumentNullException.ThrowIfNull(envelopeId);
        ArgumentNullException.ThrowIfNull(sourceText);
        ArgumentNullException.ThrowIfNull(decorations);
        ArgumentNullException.ThrowIfNull(events);
        ArgumentNullException.ThrowIfNull(sentBytes);

        // THE ONE ENCODING OF THE LIFECYCLE (DM7): the state decides which of Outcome / Waiting
        // exists, so a reader can never find a "completed" turn with no outcome or a waiting turn
        // with nothing to answer.
        if ((waiting is not null) != (state == TurnState.Waiting))
        {
            throw new ArgumentException("Waiting ⇔ State == Waiting", nameof(waiting));
        }

        if ((outcome is not null) != IsTerminal(state))
        {
            throw new ArgumentException("Outcome ⇔ a terminal state; Running, Waiting, Queued and NotRecorded carry none", nameof(outcome));
        }

        Ordinal = ordinal;
        EnvelopeId = envelopeId;
        SourceText = sourceText;
        Decorations = decorations;
        State = state;
        Outcome = outcome;
        Waiting = waiting;
        Events = events;
        Rows = Coalesce.Rows(events);
        Items = ConversationItems.Of(Rows, live: state is TurnState.Running or TurnState.Waiting);
        SentBytes = sentBytes;
        At = at;
    }

    /// <summary><c>b&lt;n&gt;</c>, dense, 1-based.</summary>
    public int Ordinal { get; }

    /// <summary>The envelope's id — the provenance disclosure's <c>envelope</c> row.</summary>
    public string EnvelopeId { get; }

    /// <summary>What the operator typed, verbatim; rendered as plain text.</summary>
    public string SourceText { get; }

    /// <summary><c>class · tier · lease[] · shape · template</c>, each with its source and reason.</summary>
    public IReadOnlyList<DecorationRow> Decorations { get; }

    public TurnState State { get; }

    /// <summary>Terminal states only.</summary>
    public OutcomeView? Outcome { get; }

    /// <summary>Waiting only.</summary>
    public WaitingRequest? Waiting { get; }

    /// <summary>The run's lines, in order — the wire grain, untouched (the mapper drops nothing; <i>Open the log</i> reaches them).</summary>
    public IReadOnlyList<EventLine> Events { get; }

    /// <summary>
    /// <c>Coalesce(Events)</c> — the message grain (Ruling 81), derived once per snapshot from
    /// <see cref="Events"/> and never written by anything else: the one fold the thread's reply
    /// side renders and the Console split unfolds (DM7: one derivation, two readers).
    /// </summary>
    public IReadOnlyList<TurnRow> Rows { get; }

    /// <summary>
    /// The conversation over <see cref="Rows"/> (Ruling 82): prose · reasoning · tool call+result ·
    /// event, in event order — derived once per snapshot beside <see cref="Rows"/>, never stored.
    /// The thread's reply side renders the items and folds the events; the outcome line is last.
    /// </summary>
    public IReadOnlyList<ConversationItem> Items { get; }

    /// <summary>Exactly the sent bytes — the compiled prompt disclosure shows this and nothing else.</summary>
    public string SentBytes { get; }

    /// <summary>Accept time.</summary>
    public DateTimeOffset At { get; }

    /// <summary>Whether <paramref name="state"/> carries an outcome.</summary>
    public static bool IsTerminal(TurnState state) =>
        state is TurnState.Completed or TurnState.Answered or TurnState.Failed or TurnState.Stopped or TurnState.Cancelled;

    /// <summary>The display ordinal: <c>b17</c>.</summary>
    public string DisplayOrdinal => "b" + Ordinal.ToString(CultureInfo.InvariantCulture);
}

/// <summary>
/// The words every surface derives from a turn — one derivation each (DM7), so the outcome line,
/// the jump list, the UIA name and the announcement policy can never disagree on what a turn says.
/// </summary>
public static class TurnCopy
{
    /// <summary>The first this many characters of the words make the item's name (SC10; deviation 3).</summary>
    public const int NameWords = 120;

    /// <summary>The outcome word (SC7): <i>answered · completed · running · lane exited 1 · stopped by you · waiting for you · outcome not recorded</i>.</summary>
    public static string OutcomeWord(TurnState state, int? exitCode) => state switch
    {
        TurnState.Running => "running",
        TurnState.Waiting => "waiting for you",
        TurnState.Completed => "completed",
        TurnState.Answered => "answered",
        TurnState.Failed => exitCode is { } code
            ? string.Create(CultureInfo.InvariantCulture, $"lane exited {code}")
            : "failed",
        TurnState.Stopped => "stopped by you",
        TurnState.NotRecorded => "outcome not recorded",
        TurnState.Queued => "queued",
        TurnState.Cancelled => "cancelled by you",
        _ => throw new ArgumentOutOfRangeException(nameof(state), state, "unknown turn state"),
    };

    /// <summary>The outcome word of a turn.</summary>
    public static string OutcomeWord(TurnView turn)
    {
        ArgumentNullException.ThrowIfNull(turn);
        return OutcomeWord(turn.State, turn.Outcome?.ExitCode);
    }

    /// <summary>The UIA name: <i>b2, Refactor the layout store's…</i> — the ordinal and the first 120 characters, <i>…</i> when truncated.</summary>
    public static string Name(TurnView turn)
    {
        ArgumentNullException.ThrowIfNull(turn);

        var words = turn.SourceText.ReplaceLineEndings(" ").Trim();
        if (words.Length > NameWords)
        {
            words = words[..NameWords].TrimEnd() + "…";
        }

        return words.Length == 0 ? turn.DisplayOrdinal : turn.DisplayOrdinal + ", " + words;
    }

    /// <summary>The decoration line as one string: <i>class free-form · tier T0 · lease src/** · goal block</i> — the item's <c>ItemStatus</c>.</summary>
    public static string DecorationLine(IReadOnlyList<DecorationRow> decorations)
    {
        ArgumentNullException.ThrowIfNull(decorations);

        return string.Join(" · ", decorations.Select(d => d.Name is "shape" ? d.Value : d.Name + " " + d.Value));
    }

    /// <summary>
    /// The reason sentence a failed, stopped, waiting or not-recorded turn carries as its container's
    /// <c>HelpText</c> (SC10); empty for a completed or running turn — one content per property.
    /// </summary>
    public static string ReasonSentence(TurnView turn)
    {
        ArgumentNullException.ThrowIfNull(turn);

        return turn.State switch
        {
            TurnState.Failed => turn.Outcome!.ExitCode is { } code
                ? string.Create(
                    CultureInfo.InvariantCulture,
                    $"The lane exited {code} after {EditsText(turn.Outcome.Edits)}. Send the same turn again as a new turn, or open the log.")
                : $"The lane failed after {EditsText(turn.Outcome.Edits)}. Send the same turn again as a new turn, or open the log.",
            TurnState.Stopped => $"Stopped by you after {EditsText(turn.Outcome!.Edits)}; {SpendText(turn.Outcome.Spend)}. Send the same turn again as a new turn, or open the log.",
            TurnState.Waiting => turn.Waiting!.Text,
            TurnState.NotRecorded => "The outcome was not recorded: the turn was submitted and nothing consumed it.",
            TurnState.Cancelled => "Cancelled before it was sent; its words went back to the editor.",
            _ => string.Empty,
        };
    }

    /// <summary>
    /// The queued turn's sentence (Ruling 95), from the snapshot it sits in — <i>queued — sends after
    /// b1</i> while b1 runs or waits; <i>queued — b1 stopped; Send it or cancel it</i> when it waits
    /// on the operator. One derivation for the row's status, its help text and the composer's line.
    /// </summary>
    public static string QueuedSentence(ThreadSnapshot snapshot)
    {
        ArgumentNullException.ThrowIfNull(snapshot);
        var queued = snapshot.Queued ?? throw new ArgumentException("nothing is queued", nameof(snapshot));
        var behind = snapshot.QueuedBehind;

        if (snapshot.QueuedAwaitsYou)
        {
            return $"{behind!.DisplayOrdinal} {OutcomeWord(behind)}; {queued.DisplayOrdinal} is waiting — Send it or cancel it";
        }

        return behind is null
            ? $"{queued.DisplayOrdinal} queued"
            : $"{queued.DisplayOrdinal} queued — sends after {behind.DisplayOrdinal}";
    }

    /// <summary>
    /// The counts with units (TQ2), in order: edits · tokens · duration · events. Edits are named on
    /// every write-capable outcome — <i>edits not recorded</i> when the run reported none — and
    /// omitted on an answered (read-only) turn, where the count has no meaning.
    /// </summary>
    public static IReadOnlyList<string> Counts(TurnView turn)
    {
        ArgumentNullException.ThrowIfNull(turn);
        var outcome = turn.Outcome ?? throw new ArgumentException("counts belong to a terminal turn", nameof(turn));

        // A cancelled turn never ran (Ruling 95): no edits, no spend, no duration, no events —
        // rendering "0 events · tokens not recorded" would describe a run that did not happen.
        if (turn.State == TurnState.Cancelled)
        {
            return ["never sent"];
        }

        var parts = new List<string>();
        if (turn.State != TurnState.Answered)
        {
            parts.Add(EditsText(outcome.Edits));
        }

        parts.Add(SpendText(outcome.Spend));

        if (outcome.Duration is { } duration)
        {
            parts.Add(DurationText(duration));
        }

        parts.Add(EventsText(outcome.EventCount));
        return parts;
    }

    /// <summary><i>3 edits</i> · <i>1 edit</i> · <i>0 edits</i>; <i>edits not recorded</i> for null.</summary>
    public static string EditsText(int? edits) => edits switch
    {
        null => "edits not recorded",
        1 => "1 edit",
        var n => string.Create(CultureInfo.InvariantCulture, $"{n} edits"),
    };

    /// <summary><i>12,400 tokens</i>; <i>tokens not recorded</i> for absent usage (Ruling 78 condition 1) — never 0.</summary>
    public static string SpendText(Spend? spend) =>
        spend is null ? "tokens not recorded" : string.Create(CultureInfo.InvariantCulture, $"{spend.Tokens:N0} tokens");

    /// <summary><i>142 events</i> · <i>1 event</i>.</summary>
    public static string EventsText(int count) =>
        count == 1 ? "1 event" : string.Create(CultureInfo.InvariantCulture, $"{count:N0} events");

    /// <summary><i>4 min 12 s</i> · <i>41 s</i> · <i>1 h 02 min</i>, at one precision.</summary>
    public static string DurationText(TimeSpan duration)
    {
        if (duration < TimeSpan.Zero)
        {
            duration = TimeSpan.Zero;
        }

        if (duration.TotalHours >= 1)
        {
            return string.Create(CultureInfo.InvariantCulture, $"{(int)duration.TotalHours} h {duration.Minutes:00} min");
        }

        if (duration.TotalMinutes >= 1)
        {
            return string.Create(CultureInfo.InvariantCulture, $"{duration.Minutes} min {duration.Seconds:00} s");
        }

        return string.Create(CultureInfo.InvariantCulture, $"{(int)duration.TotalSeconds} s");
    }

    /// <summary>The spoken form of a duration: <i>4 minutes 12 seconds</i> (SC9).</summary>
    public static string SpokenDuration(TimeSpan duration)
    {
        if (duration < TimeSpan.Zero)
        {
            duration = TimeSpan.Zero;
        }

        if (duration.TotalMinutes >= 1)
        {
            return string.Create(CultureInfo.InvariantCulture, $"{(int)duration.TotalMinutes} minutes {duration.Seconds} seconds");
        }

        return string.Create(CultureInfo.InvariantCulture, $"{(int)duration.TotalSeconds} seconds");
    }

    /// <summary>The header's budget state (Ruling 78): <i>12,400 tokens this session · bounded by your subscription</i> / <i>38,900 of 40,000 · cap enforced</i>.</summary>
    public static string SessionSpend(IReadOnlyList<TurnView> turns, long? capTokens)
    {
        ArgumentNullException.ThrowIfNull(turns);

        var measured = turns.Select(t => t.Outcome?.Spend).Where(s => s is not null).ToList();
        var sum = measured.Sum(s => s!.Tokens);
        var unmeasured = turns.Count(t => t.Outcome is not null && t.Outcome.Spend is null);

        var spend = measured.Count == 0
            ? "spend not recorded"
            : unmeasured > 0
                ? string.Create(CultureInfo.InvariantCulture, $"{sum:N0} tokens this session ({unmeasured} not recorded)")
                : string.Create(CultureInfo.InvariantCulture, $"{sum:N0} tokens this session");

        return capTokens is { } cap
            ? string.Create(CultureInfo.InvariantCulture, $"{sum:N0} of {cap:N0} · cap enforced")
            : spend + " · bounded by your subscription";
    }
}
