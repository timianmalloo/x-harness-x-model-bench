using System.Globalization;

namespace AiDe.Core.Presentation.Sessions;

/// <summary>How an announcement is processed by an AT: queued after what is being read, or interrupting it.</summary>
public enum Urgency
{
    /// <summary>A status: queued, never cancelling speech (SC9).</summary>
    Status,

    /// <summary>An error, a refusal or a request: interrupts (SC9).</summary>
    Assertive,
}

/// <summary>What kind of thing happened — carried for the notification API's truthful kind (DS-1 deviation 7).</summary>
public enum AnnouncementKind
{
    ItemAdded,
    Completed,
    Aborted,
    Other,
}

/// <summary>One thing to say, with how urgently and why.</summary>
/// <param name="Text">The sentence, in voice.</param>
/// <param name="Urgency">Status or assertive.</param>
/// <param name="Kind">The notification kind.</param>
/// <param name="Ordinal">The turn it is about, or 0 when it is not about one turn.</param>
/// <param name="Transition">The transition that produced it (<c>running→completed</c>), for telemetry — never the text.</param>
public sealed record Announcement(string Text, Urgency Urgency, AnnouncementKind Kind, int Ordinal = 0, string Transition = "");

/// <summary>
/// SC9 as a transition function over consecutive snapshots (DS-1 P6): once per outcome by
/// construction, nothing before catch-up, nothing for history, never for event lines, folds or
/// scrolls — those produce no transition.
/// </summary>
/// <remarks>
/// <para><b>One method, the catch-up rule inside it.</b> A snapshot before catch-up is remembered
/// as nothing and emits nothing; the first caught-up snapshot is remembered and not spoken (history
/// is not news); every later snapshot is diffed per ordinal against the previous one. The control
/// feeds <b>every</b> snapshot in <c>Version</c> order — the render coalesces, the policy does not
/// — so <i>running → waiting → running</i> inside one render window yields both sentences.</para>
///
/// <para><b>A version gap is reported, not hidden.</b> The diff still runs (the net transition is
/// announced); <see cref="Next"/> returns the gap through <see cref="LastVersionGap"/> so the
/// control can record <c>THR-0003</c>. The state the read model hid is not invented.</para>
/// </remarks>
public sealed class ThreadAnnouncementPolicy
{
    private ThreadSnapshot? _previous;

    /// <summary>The <c>(expected, received)</c> versions of the last gap <see cref="Next"/> saw, or null when the last call was contiguous.</summary>
    public (long Expected, long Received)? LastVersionGap { get; private set; }

    /// <summary>The announcements this snapshot produces against the previous one, in ordinal order.</summary>
    public IReadOnlyList<Announcement> Next(ThreadSnapshot snapshot)
    {
        ArgumentNullException.ThrowIfNull(snapshot);

        LastVersionGap = null;

        // THE CATCH-UP RULE, FIRST. A replayed history — forty snapshots before the flag, or a
        // read model pre-loaded with five turns — is never news.
        if (!snapshot.IsCaughtUp)
        {
            _previous = null;
            return [];
        }

        if (_previous is null)
        {
            _previous = snapshot;
            return [];
        }

        var previous = _previous;
        _previous = snapshot;

        if (snapshot.Version != previous.Version + 1)
        {
            LastVersionGap = (previous.Version + 1, snapshot.Version);
        }

        var before = previous.Turns.ToDictionary(t => t.Ordinal);
        var emitted = new List<Announcement>();

        foreach (var turn in snapshot.Turns.OrderBy(t => t.Ordinal))
        {
            before.TryGetValue(turn.Ordinal, out var was);

            if (was is not null && SameEndpoint(was, turn))
            {
                continue;
            }

            if (Transition(was, turn) is { } announcement)
            {
                emitted.Add(announcement);
            }
        }

        return emitted;
    }

    private static bool SameEndpoint(TurnView a, TurnView b) =>
        a.State == b.State
        && string.Equals(a.Waiting?.RequestId, b.Waiting?.RequestId, StringComparison.Ordinal)
        && a.Outcome?.ExitCode == b.Outcome?.ExitCode;

    /// <summary>The total transition table (DS-1 §SC9). A cell not listed is no announcement.</summary>
    private static Announcement? Transition(TurnView? was, TurnView now)
    {
        var from = was?.State;
        var label = (from is null ? "new" : from.Value.ToString().ToLowerInvariant()) + "→" + now.State.ToString().ToLowerInvariant();

        // A terminal state never moves again; the stream forbids it (THR-0003 on the record, no announcement).
        if (was is not null && TurnView.IsTerminal(was.State))
        {
            return null;
        }

        return now.State switch
        {
            // A queued turn that starts is accepted NOW (Ruling 95): the send happened at the
            // drain, and the operator hears what they would have heard had they pressed Send.
            TurnState.Running when was is null || was.State == TurnState.Queued => Accepted(now, label),
            TurnState.Running => Status(now, "Turn " + now.DisplayOrdinal + " continues.", AnnouncementKind.Completed, label),

            TurnState.Queued when was is null => Status(
                now, "Turn " + now.DisplayOrdinal + " queued; it sends after the turn in flight.", AnnouncementKind.ItemAdded, label),

            TurnState.Cancelled => Status(
                now, "Turn " + now.DisplayOrdinal + " " + LowerFirst(TurnCopy.ReasonSentence(now)), AnnouncementKind.Aborted, label),

            TurnState.Waiting when was is null => Accepted(now, label),
            TurnState.Waiting => new Announcement(
                "Turn " + now.DisplayOrdinal + " is waiting for you: " + now.Waiting!.Text + " " + ActionsSentence(now.Waiting.Actions),
                Urgency.Assertive, AnnouncementKind.Other, now.Ordinal, label),

            TurnState.Completed or TurnState.Answered => Status(
                now,
                "Turn " + now.DisplayOrdinal + " " + TurnCopy.OutcomeWord(now) + ": " + string.Join(", ", SpokenCounts(now.Outcome!)) + ".",
                AnnouncementKind.Completed, label),

            TurnState.Failed => new Announcement(
                "Turn " + now.DisplayOrdinal + ": " + LowerFirst(TurnCopy.ReasonSentence(now)),
                Urgency.Assertive, AnnouncementKind.Aborted, now.Ordinal, label),

            TurnState.Stopped => Status(
                now, "Turn " + now.DisplayOrdinal + " " + LowerFirst(TurnCopy.ReasonSentence(now)), AnnouncementKind.Aborted, label),

            TurnState.NotRecorded => Status(now, "Turn " + now.DisplayOrdinal + ": outcome not recorded.", AnnouncementKind.Other, label),

            _ => null,
        };
    }

    private static Announcement Accepted(TurnView now, string label)
    {
        // SC9: the shape, the tier AND the class are spoken at the send — each only when the
        // decoration line carries it (a row that is absent is not invented as a word).
        var shape = now.Decorations.FirstOrDefault(d => d.Name == "shape")?.Value ?? "message";
        var tier = now.Decorations.FirstOrDefault(d => d.Name == "tier")?.Value;
        var cls = now.Decorations.FirstOrDefault(d => d.Name == "class")?.Value;
        var text = $"Turn {now.DisplayOrdinal} accepted as a {shape}"
            + (tier is null ? string.Empty : $", tier {tier}")
            + (cls is null ? string.Empty : $", class {cls}")
            + ".";
        return new Announcement(text, Urgency.Status, AnnouncementKind.ItemAdded, now.Ordinal, label);
    }

    private static Announcement Status(TurnView now, string text, AnnouncementKind kind, string label) =>
        new(text, Urgency.Status, kind, now.Ordinal, label);

    private static IEnumerable<string> SpokenCounts(OutcomeView outcome)
    {
        if (outcome.Edits is { } edits)
        {
            yield return TurnCopy.EditsText(edits);
        }

        yield return TurnCopy.SpendText(outcome.Spend);

        if (outcome.Duration is { } duration)
        {
            yield return TurnCopy.SpokenDuration(duration);
        }
    }

    private static string ActionsSentence(IReadOnlyList<TurnActionKind> actions)
    {
        var words = actions.Select(ActionWord).ToList();
        return words.Count switch
        {
            0 => string.Empty,
            1 => words[0] + ".",
            2 => words[0] + " or " + LowerFirst(words[1]) + ".",
            _ => string.Join(", ", words.Take(words.Count - 1)) + ", or " + LowerFirst(words[^1]) + ".",
        };
    }

    /// <summary>The action's button name (SC7/SC10): one vocabulary for the button, the menu and the sentence.</summary>
    public static string ActionWord(TurnActionKind action) => action switch
    {
        TurnActionKind.Stop => "Stop this turn",
        TurnActionKind.Deny => "Deny",
        TurnActionKind.AllowOnce => "Allow once",
        TurnActionKind.AllowThisTurn => "Allow this turn",
        TurnActionKind.OpenSessionSettings => "Open session settings",
        TurnActionKind.SendAgain => "Send again as a new turn",
        TurnActionKind.OpenLog => "Open the log",
        TurnActionKind.UseAsNextDraft => "Use as the next draft",
        TurnActionKind.OpenConsoleAt => "Open the Console at this turn",
        TurnActionKind.Cancel => "Cancel",
        TurnActionKind.SendNow => "Send now",
        _ => throw new ArgumentOutOfRangeException(nameof(action), action, "unknown turn action"),
    };

    private static string LowerFirst(string sentence) =>
        sentence.Length == 0 ? sentence : char.ToLower(sentence[0], CultureInfo.InvariantCulture) + sentence[1..];
}
