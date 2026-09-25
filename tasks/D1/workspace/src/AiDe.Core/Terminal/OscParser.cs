using System.Security.Cryptography;
using System.Text;
using AiDe.Core.Dispatch;

namespace AiDe.Core.Terminal;

/// <summary>Which OSC sequence arrived. Says nothing about whether it was believed.</summary>
public enum OscKind
{
    /// <summary>OSC 133;A — the shell is about to draw a prompt.</summary>
    PromptStart,

    /// <summary>OSC 133;B — the prompt is drawn and the user is typing.</summary>
    CommandStart,

    /// <summary>OSC 133;C — a command started running.</summary>
    CommandExecuted,

    /// <summary>OSC 133;D — a command finished.</summary>
    CommandFinished,

    /// <summary>OSC 52 — a clipboard write. Never performed.</summary>
    Clipboard,

    /// <summary>OSC 8 — a hyperlink. Never actioned.</summary>
    Hyperlink,

    /// <summary>Anything else, including OSC 633.</summary>
    Unrecognized,
}

/// <summary>What the parser did about it.</summary>
public enum OscDisposition
{
    /// <summary>Authenticated by the session nonce; the advisory state claim was taken.</summary>
    Honoured,

    /// <summary>A recognised state claim carrying no nonce, or the wrong one. Discarded.</summary>
    RefusedUnauthenticated,

    /// <summary>A host action we do not implement at all. Discarded regardless of the nonce.</summary>
    RefusedDisabled,

    /// <summary>Recognised as an OSC sequence, but not one we act on.</summary>
    Ignored,

    /// <summary>The payload passed the cap before a terminator arrived, so it was abandoned.</summary>
    Overflowed,
}

/// <summary>One sequence and its outcome. Deliberately carries no payload text.</summary>
/// <remarks>
/// The absent payload is the privacy control, not an omission. This type is what telemetry counts
/// and what a diagnostic view would show, and terminal text may reach neither — so there is nowhere
/// on this record for a byte of the child's output to sit.
/// </remarks>
public readonly record struct OscEvent(OscKind Kind, OscDisposition Disposition);

/// <summary>
/// Reads OSC sequences out of a terminal byte stream and turns the authenticated ones into advisory
/// <see cref="SessionActivity"/> claims.
/// </summary>
/// <remarks>
/// <para><b>Everything here is a claim from an untrusted process.</b> The child in a terminal is
/// often the thing being investigated, and it chooses every byte. So the parser's job is not to
/// interpret OSC faithfully — it is to decide what may be believed. Three rules follow.</para>
///
/// <para><b>1. State claims need the session nonce.</b> OSC 133 is public and widely copied; any
/// process that can print can emit it. The nonce is injected into the shell integration we install,
/// so a claim carrying it came from that integration and a claim without it came from something
/// else. Advisory state still drives what the user sees, and a session reporting <c>Ready</c>
/// mid-command is a lie the UI renders faithfully.</para>
///
/// <para><b>2. Host actions are refused outright, nonce or not</b> (ADR-0005, threat model boundary
/// "terminal output → UI"). OSC 52 writes the clipboard and OSC 8 carries a URI; both are actions
/// taken by <i>us</i> on the child's instruction. Sanitising them would presume we can separate a
/// safe payload from a hostile one when the child chose all of it. There is no clipboard code path
/// here to reach.</para>
///
/// <para><b>3. Nothing is retained.</b> The parser sees every byte the child writes, so anything it
/// keeps is terminal text living outside the bounded, ephemeral output channel the spec confines it
/// to. The payload buffer is cleared at every terminator and never leaves this object.</para>
///
/// <para>OSC state is <b>never agent acceptance</b> (ADR-0007). Nothing here may be read as a user
/// or an agent having agreed to anything; it reports only that a process is or is not working.</para>
///
/// <para>Not thread-safe: one parser belongs to one session's single reader loop.</para>
/// </remarks>
public sealed class OscParser
{
    /// <summary>
    /// Bytes buffered for one sequence before it is abandoned.
    /// </summary>
    /// <remarks>
    /// Without a cap, <c>ESC ]</c> followed by an endless stream costs us one byte per byte of
    /// theirs and the ceiling is whatever the child chooses. Every sequence we honour is well under
    /// 100 bytes; the headroom is for the ones we refuse.
    /// simplify: a flat byte cap rather than a per-kind budget; ceiling 1 KiB; upgrade trigger = a
    /// sequence we need to honour does not fit.
    /// </remarks>
    public const int MaxPayloadBytes = 1024;

    private const byte Escape = 0x1B;
    private const byte Bell = 0x07;
    private const byte OscIntroducer7Bit = (byte)']';
    private const byte StringTerminator7Bit = (byte)'\\';
    private const byte OscIntroducer8Bit = 0x9D;
    private const byte StringTerminator8Bit = 0x9C;

    private const string NoncePrefix = "nonce=";

    private readonly byte[] _nonce;
    private readonly byte[] _payload = new byte[MaxPayloadBytes];

    private State _state = State.Ground;
    private int _length;

    /// <param name="sessionNonce">
    /// The secret shared with this session's injected shell integration. Must be non-empty: a parser
    /// with no nonce would have nothing to check claims against, and failing open there would make
    /// the control absent exactly when nonce generation had gone wrong.
    /// </param>
    public OscParser(string sessionNonce)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(sessionNonce);
        _nonce = Encoding.ASCII.GetBytes(sessionNonce);
    }

    /// <summary>Bytes currently held for an in-flight sequence. Zero whenever none is in flight.</summary>
    /// <remarks>Exists so the retention bound is observable rather than merely intended.</remarks>
    public int PendingPayloadBytes => _state is State.Payload or State.PayloadEscape ? _length : 0;

    /// <summary>A fresh session nonce: 128 random bits, hex encoded.</summary>
    public static string NewNonce() => Convert.ToHexString(RandomNumberGenerator.GetBytes(16)).ToLowerInvariant();

    /// <summary>
    /// Feeds one chunk of session output through the scanner.
    /// </summary>
    /// <param name="bytes">Output exactly as read; never modified and never copied out.</param>
    /// <param name="events">Appended to, one entry per complete or abandoned sequence.</param>
    /// <returns>
    /// The last authenticated activity claim in this chunk, or <c>null</c> if there was none. Last
    /// rather than first because a chunk may hold a whole command's worth of sequences, and the
    /// state the session should end up in is the one the shell said most recently.
    /// </returns>
    public SessionActivity? Consume(ReadOnlySpan<byte> bytes, List<OscEvent> events)
    {
        ArgumentNullException.ThrowIfNull(events);

        SessionActivity? claim = null;

        foreach (var b in bytes)
        {
            switch (_state)
            {
                case State.Ground:
                    if (b == Escape)
                    {
                        _state = State.Escape;
                    }
                    else if (b == OscIntroducer8Bit)
                    {
                        Begin();
                    }

                    break;

                case State.Escape:
                    // ESC ESC is a child that started an escape and thought better of it; staying
                    // here keeps the second one live rather than consuming the introducer after it.
                    _state = b switch
                    {
                        OscIntroducer7Bit => Begin(),
                        Escape => State.Escape,
                        _ => State.Ground,
                    };

                    break;

                case State.Payload:
                    if (b is Bell or StringTerminator8Bit)
                    {
                        claim = Complete(events) ?? claim;
                    }
                    else if (b == Escape)
                    {
                        _state = State.PayloadEscape;
                    }
                    else if (_length < MaxPayloadBytes)
                    {
                        _payload[_length++] = b;
                    }
                    else
                    {
                        // Abandon, but keep scanning for the real terminator: dropping straight back
                        // to Ground would read the rest of this payload as ordinary output and any
                        // sequence inside it as genuine.
                        events.Add(new OscEvent(OscKind.Unrecognized, OscDisposition.Overflowed));
                        _length = 0;
                        _state = State.Discard;
                    }

                    break;

                case State.PayloadEscape:
                    if (b == StringTerminator7Bit)
                    {
                        claim = Complete(events) ?? claim;
                    }
                    else if (b == Escape)
                    {
                        _state = State.PayloadEscape;
                    }
                    else
                    {
                        // ESC followed by anything else aborts the string. Discarding what we have is
                        // the safe reading: a truncated payload is not a claim.
                        _length = 0;
                        _state = State.Ground;
                    }

                    break;

                case State.Discard:
                    if (b is Bell or StringTerminator8Bit)
                    {
                        _state = State.Ground;
                    }
                    else if (b == Escape)
                    {
                        _state = State.DiscardEscape;
                    }

                    break;

                case State.DiscardEscape:
                    _state = b switch
                    {
                        StringTerminator7Bit => State.Ground,
                        Escape => State.DiscardEscape,
                        _ => State.Discard,
                    };

                    break;
            }
        }

        return claim;
    }

    private State Begin()
    {
        _length = 0;
        return _state = State.Payload;
    }

    /// <summary>Classifies a finished payload, records the outcome, and clears the buffer.</summary>
    private SessionActivity? Complete(List<OscEvent> events)
    {
        var payload = _payload.AsSpan(0, _length);

        var command = Field(payload, 0);
        SessionActivity? claim = null;
        OscEvent result;

        if (Same(command, "52"))
        {
            result = new OscEvent(OscKind.Clipboard, OscDisposition.RefusedDisabled);
        }
        else if (Same(command, "8"))
        {
            result = new OscEvent(OscKind.Hyperlink, OscDisposition.RefusedDisabled);
        }
        else if (Same(command, "133"))
        {
            var token = Field(payload, 1);
            var kind = Classify(token, out var claimed);

            if (kind == OscKind.Unrecognized)
            {
                result = new OscEvent(OscKind.Unrecognized, OscDisposition.Ignored);
            }
            else if (Authenticated(payload))
            {
                claim = claimed;
                result = new OscEvent(kind, OscDisposition.Honoured);
            }
            else
            {
                result = new OscEvent(kind, OscDisposition.RefusedUnauthenticated);
            }
        }
        else
        {
            result = new OscEvent(OscKind.Unrecognized, OscDisposition.Ignored);
        }

        events.Add(result);

        // Cleared here rather than at the next Begin: between sequences the buffer would otherwise
        // still hold the last payload, which is retention however briefly it lasts.
        _payload.AsSpan(0, _length).Clear();
        _length = 0;
        _state = State.Ground;

        return claim;
    }

    private static OscKind Classify(ReadOnlySpan<byte> token, out SessionActivity claimed)
    {
        // A drawn prompt and a typed-but-unsubmitted command are both "waiting on the user", which
        // is what Ready means here. Only C says work is actually running.
        if (Same(token, "A"))
        {
            claimed = SessionActivity.Ready;
            return OscKind.PromptStart;
        }

        if (Same(token, "B"))
        {
            claimed = SessionActivity.Ready;
            return OscKind.CommandStart;
        }

        if (Same(token, "C"))
        {
            claimed = SessionActivity.Busy;
            return OscKind.CommandExecuted;
        }

        if (Same(token, "D"))
        {
            claimed = SessionActivity.Ready;
            return OscKind.CommandFinished;
        }

        claimed = SessionActivity.Starting;
        return OscKind.Unrecognized;
    }

    /// <summary>Does any field carry <c>nonce=</c> with this session's value?</summary>
    private bool Authenticated(ReadOnlySpan<byte> payload)
    {
        for (var index = 1; ; index++)
        {
            var field = Field(payload, index);
            if (field.IsEmpty && index > 1 && Field(payload, index - 1).IsEmpty)
            {
                return false; // Ran off the end: two empty fields in a row means no more separators.
            }

            if (field.Length > NoncePrefix.Length && Same(field[..NoncePrefix.Length], NoncePrefix))
            {
                var candidate = field[NoncePrefix.Length..];

                // Length-checked before the comparison, and fixed-time within it. The length is not
                // a secret; the value is, and a byte-at-a-time comparison would let the child learn
                // it one position per attempt.
                return candidate.Length == _nonce.Length
                    && CryptographicOperations.FixedTimeEquals(candidate, _nonce);
            }

            if (index > 32)
            {
                return false; // A payload this segmented is not one of ours.
            }
        }
    }

    /// <summary>The <paramref name="index"/>th <c>;</c>-separated field, or empty if absent.</summary>
    private static ReadOnlySpan<byte> Field(ReadOnlySpan<byte> payload, int index)
    {
        var start = 0;

        for (var seen = 0; seen < index; seen++)
        {
            var next = payload[start..].IndexOf((byte)';');
            if (next < 0)
            {
                return default;
            }

            start += next + 1;
        }

        var end = payload[start..].IndexOf((byte)';');
        return end < 0 ? payload[start..] : payload.Slice(start, end);
    }

    private static bool Same(ReadOnlySpan<byte> bytes, string ascii)
    {
        if (bytes.Length != ascii.Length)
        {
            return false;
        }

        for (var i = 0; i < ascii.Length; i++)
        {
            if (bytes[i] != (byte)ascii[i])
            {
                return false;
            }
        }

        return true;
    }

    private enum State
    {
        Ground,
        Escape,
        Payload,
        PayloadEscape,
        Discard,
        DiscardEscape,
    }
}
