using System.Text;

namespace AiDe.Core.Terminal;

/// <summary>
/// Turns a session's output bytes into screen state: the display half of reading a terminal stream.
/// </summary>
/// <remarks>
/// <para><b>Separate from <see cref="OscParser"/>, and the two are not redundant.</b> That one reads
/// the stream for <i>authenticated state claims</i> and is a security control whose value depends on
/// staying small enough to reason about. This one reads the same bytes for <i>what to draw</i>. Two
/// passes cost nothing worth counting — S3 measured a scanner at 2361× the architecture's 1 MiB/s
/// budget — and merging them would put display concerns inside the control. What this parser owes
/// OSC is to <b>skip</b> it, so a window-title or clipboard sequence never lands on screen as text
/// the user reads as program output.</para>
///
/// <para><b>Every byte is hostile input</b> (D2). The child chooses all of it, so truncated,
/// over-long and nonsensical sequences are the normal case. Nothing here throws and nothing here
/// grows without a bound: an exception or an allocation reachable by printing is a denial of service
/// written in escape codes.</para>
///
/// <para><b>Decoding is incremental.</b> UTF-8 characters and escape sequences both get split by
/// read boundaries, which are chosen by the pipe rather than the child. A parser that decoded each
/// chunk independently passes every test written as one string and produces replacement characters
/// against a real 4 KiB read.</para>
///
/// <para>Not thread-safe: one parser belongs to one session's reader.</para>
/// </remarks>
public sealed class VtParser
{
    /// <summary>
    /// Parameters kept for one sequence before the rest are dropped.
    /// </summary>
    /// <remarks>
    /// No real sequence uses more than a handful. The cap exists so that <c>ESC [</c> followed by a
    /// million semicolons costs a fixed amount rather than one allocation per semicolon.
    /// </remarks>
    private const int MaxParameters = 32;

    /// <summary>Bounds a single parameter so a long digit run cannot overflow or allocate.</summary>
    private const int MaxParameterValue = 1_000_000;

    private readonly TerminalScreen _screen;
    private readonly Decoder _decoder = Encoding.UTF8.GetDecoder();
    private readonly char[] _decoded = new char[4096];
    private readonly int[] _parameters = new int[MaxParameters];

    private State _state = State.Ground;
    private int _parameterCount;
    private bool _parameterStarted;
    private bool _privateSequence;

    public VtParser(TerminalScreen screen) => _screen = screen ?? throw new ArgumentNullException(nameof(screen));

    /// <summary>Feeds one chunk of session output through the parser.</summary>
    public void Consume(ReadOnlySpan<byte> bytes)
    {
        // Decoded in a loop against a fixed buffer rather than in one call. Consume takes a span of
        // any length, and a chunk that decodes to more characters than the buffer holds makes the
        // single-call form THROW — which, since the bytes come from the child process, would be a
        // crash reachable by printing enough text.
        //
        // flush: false — a chunk may end mid-character, and the decoder carries the remainder into
        // the next call rather than emitting a replacement for it.
        while (!bytes.IsEmpty)
        {
            _decoder.Convert(
                bytes, _decoded, flush: false,
                out var bytesUsed, out var charsUsed, out _);

            for (var i = 0; i < charsUsed; i++)
            {
                Step(_decoded[i]);
            }

            if (bytesUsed == 0 && charsUsed == 0)
            {
                break; // No progress possible: the remainder is an incomplete character.
            }

            bytes = bytes[bytesUsed..];
        }
    }

    private void Step(char c)
    {
        switch (_state)
        {
            case State.Ground:
                Ground(c);
                break;

            case State.Escape:
                Escape(c);
                break;

            case State.CsiParameters:
                CsiParameter(c);
                break;

            case State.OscString:
                OscString(c);
                break;

            case State.OscEscape:
                // Only ESC \ ends the string; anything else was part of it.
                _state = c == '\\' ? State.Ground : State.OscString;
                break;

            case State.SkipOne:
                // Charset designators and similar two-byte escapes: consume the argument and drop it.
                _state = State.Ground;
                break;
        }
    }

    private void Ground(char c)
    {
        switch (c)
        {
            case '':
                _state = State.Escape;
                break;

            case '\r':
                _screen.CarriageReturn();
                break;

            case '\n':
                _screen.LineFeed();
                break;

            case '\b':
                _screen.Backspace();
                break;

            case '\t':
                _screen.Tab();
                break;

            case '':
                // The bell is audible-only and we do not ring it; drawing it would put a stray glyph
                // on screen every time a shell completed with an error.
                break;

            case '':
                BeginCsi();
                break;

            case '':
                _state = State.OscString;
                break;

            default:
                // Remaining C0 controls are consumed rather than drawn: they have no glyph, and
                // rendering them produces the boxes that make a terminal look broken.
                if (!char.IsControl(c))
                {
                    _screen.Write(c);
                }

                break;
        }
    }

    private void Escape(char c)
    {
        switch (c)
        {
            case '[':
                BeginCsi();
                break;

            case ']':
                _state = State.OscString;
                break;

            case '(':
            case ')':
            case '*':
            case '+':
                _state = State.SkipOne;
                break;

            case '':
                // A second ESC restarts rather than being treated as an argument.
                break;

            default:
                _state = State.Ground;
                break;
        }
    }

    private void BeginCsi()
    {
        _parameterCount = 0;
        _parameterStarted = false;
        _privateSequence = false;
        Array.Clear(_parameters);
        _state = State.CsiParameters;
    }

    private void CsiParameter(char c)
    {
        if (c is >= '0' and <= '9')
        {
            if (_parameterCount < MaxParameters)
            {
                if (!_parameterStarted)
                {
                    _parameterCount++;
                    _parameterStarted = true;
                }

                var index = _parameterCount - 1;

                // Saturating rather than wrapping: a value this large is nonsense whatever it is,
                // and the screen clamps it anyway. Multiplying without the guard is where an
                // overflow would turn a huge row number negative.
                _parameters[index] = Math.Min(
                    (_parameters[index] * 10) + (c - '0'), MaxParameterValue);
            }

            return;
        }

        if (c == ';')
        {
            if (_parameterCount < MaxParameters && !_parameterStarted)
            {
                _parameterCount++; // An omitted parameter is present and zero: `ESC [ ; 5 H`.
            }

            _parameterStarted = false;
            return;
        }

        if (c is >= '<' and <= '?')
        {
            // Private-use introducers (DEC modes and friends). Recorded so the whole sequence can be
            // ignored as a unit rather than half-applied.
            _privateSequence = true;
            return;
        }

        if (c is >= ' ' and <= '/')
        {
            return; // Intermediate bytes; none of the sequences we act on use them.
        }

        Dispatch(c);
        _state = State.Ground;
    }

    private void OscString(char c)
    {
        // Skipped, not interpreted. OscParser handles the sequences that carry meaning; here the
        // only requirement is that none of this reaches the screen as text.
        if (c == '' || c == '')
        {
            _state = State.Ground;
        }
        else if (c == '')
        {
            _state = State.OscEscape;
        }
    }

    private void Dispatch(char final)
    {
        if (_privateSequence)
        {
            // DEC private modes. Only the ones that change how INPUT must be encoded (or that a common
            // TUI depends on) are acted on; the rest are ignored as a unit, because acting on some and
            // not others is how a terminal ends up in a state no program asked for. `h` sets, `l` resets.
            if (final is 'h' or 'l')
            {
                var count = Math.Max(_parameterCount, 1);
                for (var i = 0; i < count; i++)
                {
                    DispatchPrivateMode(Parameter(i, 0), set: final == 'h');
                }
            }

            return;
        }

        switch (final)
        {
            case 'H':
            case 'f':
                _screen.MoveCursor(Parameter(0, 1) - 1, Parameter(1, 1) - 1);
                break;

            case 'A':
                _screen.MoveCursor(_screen.CursorRow - Parameter(0, 1), _screen.CursorColumn);
                break;

            case 'B':
                _screen.MoveCursor(_screen.CursorRow + Parameter(0, 1), _screen.CursorColumn);
                break;

            case 'C':
                _screen.MoveCursor(_screen.CursorRow, _screen.CursorColumn + Parameter(0, 1));
                break;

            case 'D':
                _screen.MoveCursor(_screen.CursorRow, _screen.CursorColumn - Parameter(0, 1));
                break;

            case 'G':
                _screen.MoveCursor(_screen.CursorRow, Parameter(0, 1) - 1);
                break;

            case 'd':
                _screen.MoveCursor(Parameter(0, 1) - 1, _screen.CursorColumn);
                break;

            case 'J':
                _screen.EraseInDisplay(Extent(Parameter(0, 0)));
                break;

            case 'K':
                _screen.EraseInLine(Extent(Parameter(0, 0)));
                break;

            case 'X':
                _screen.EraseCharacters(Parameter(0, 1));
                break;

            case '@':
                _screen.InsertCharacters(Parameter(0, 1));
                break;

            case 'P':
                _screen.DeleteCharacters(Parameter(0, 1));
                break;

            case 'm':
                ApplyGraphicRendition();
                break;

            default:
                // Unknown finals are dropped. A terminal that guessed would apply an effect no
                // program requested, which is worse than a missing one.
                break;
        }
    }

    private void DispatchPrivateMode(int mode, bool set)
    {
        switch (mode)
        {
            case 1:
                // DECCKM — application cursor keys. The one mode that changes INPUT encoding, so
                // ignoring it leaves the arrows dead in a full-screen TUI (smoke 9-2).
                _screen.SetApplicationCursorKeys(set);
                break;

            case 2004:
                // Bracketed paste. Ignoring it makes a pasted multi-line prompt run line-by-line.
                _screen.SetBracketedPaste(set);
                break;

            case 47:
                // Alternate screen (legacy) — no cursor save, no clear.
                if (set) { _screen.EnterAltScreen(saveCursor: false, clear: false); }
                else { _screen.LeaveAltScreen(restoreCursor: false); }

                break;

            case 1047:
                // Alternate screen — clear on entry, no cursor save.
                if (set) { _screen.EnterAltScreen(saveCursor: false, clear: true); }
                else { _screen.LeaveAltScreen(restoreCursor: false); }

                break;

            case 1049:
                // Alternate screen (modern) — save cursor + clear on entry, restore cursor on exit.
                // The one a full-screen TUI uses; without it the TUI overwrites the shell scrollback.
                if (set) { _screen.EnterAltScreen(saveCursor: true, clear: true); }
                else { _screen.LeaveAltScreen(restoreCursor: true); }

                break;

            case 1000:
                _screen.SetMouseMode(set ? MouseTracking.Normal : MouseTracking.None);
                break;

            case 1002:
                _screen.SetMouseMode(set ? MouseTracking.ButtonMotion : MouseTracking.None);
                break;

            case 1003:
                _screen.SetMouseMode(set ? MouseTracking.AnyMotion : MouseTracking.None);
                break;

            case 1006:
                _screen.SetMouseSgr(set);
                break;

            default:
                // Unhandled private mode — ignored as a unit (a half-applied mode is worse than none).
                break;
        }
    }

    private static EraseExtent Extent(int parameter) => parameter switch
    {
        1 => EraseExtent.ToStart,
        2 or 3 => EraseExtent.All,
        _ => EraseExtent.ToEnd,
    };

    private void ApplyGraphicRendition()
    {
        if (_parameterCount == 0)
        {
            _screen.Pen = TerminalPen.Default; // A bare `ESC [ m` means reset.
            return;
        }

        var pen = _screen.Pen;

        for (var i = 0; i < _parameterCount; i++)
        {
            var code = _parameters[i];

            switch (code)
            {
                case 0:
                    pen = TerminalPen.Default;
                    break;

                case 1:
                    pen = pen with { Attributes = pen.Attributes | CellAttributes.Bold };
                    break;

                case 4:
                    pen = pen with { Attributes = pen.Attributes | CellAttributes.Underline };
                    break;

                case 7:
                    pen = pen with { Attributes = pen.Attributes | CellAttributes.Inverse };
                    break;

                case 22:
                    pen = pen with { Attributes = pen.Attributes & ~CellAttributes.Bold };
                    break;

                case 24:
                    pen = pen with { Attributes = pen.Attributes & ~CellAttributes.Underline };
                    break;

                case 27:
                    pen = pen with { Attributes = pen.Attributes & ~CellAttributes.Inverse };
                    break;

                case >= 30 and <= 37:
                    pen = pen with { Foreground = TerminalColor.FromIndex(code - 30) };
                    break;

                case 38:
                    pen = pen with { Foreground = ExtendedColour(ref i) ?? pen.Foreground };
                    break;

                case 39:
                    pen = pen with { Foreground = TerminalColor.Default };
                    break;

                case >= 40 and <= 47:
                    pen = pen with { Background = TerminalColor.FromIndex(code - 40) };
                    break;

                case 48:
                    pen = pen with { Background = ExtendedColour(ref i) ?? pen.Background };
                    break;

                case 49:
                    pen = pen with { Background = TerminalColor.Default };
                    break;

                case >= 90 and <= 97:
                    pen = pen with { Foreground = TerminalColor.FromIndex(code - 90 + 8) };
                    break;

                case >= 100 and <= 107:
                    pen = pen with { Background = TerminalColor.FromIndex(code - 100 + 8) };
                    break;
            }
        }

        _screen.Pen = pen;
    }

    /// <summary>Reads the <c>5;n</c> or <c>2;r;g;b</c> argument that follows a 38 or 48.</summary>
    /// <remarks>
    /// Advances <paramref name="i"/> past what it consumed. A truncated form — <c>38;5</c> with the
    /// index missing, which a hostile or merely interrupted stream produces — yields null and leaves
    /// the pen alone, rather than reading whatever parameter happens to come next.
    /// </remarks>
    private TerminalColor? ExtendedColour(ref int i)
    {
        if (i + 1 >= _parameterCount)
        {
            return null;
        }

        var form = _parameters[i + 1];

        if (form == 5 && i + 2 < _parameterCount)
        {
            i += 2;
            return TerminalColor.FromIndex(_parameters[i]);
        }

        if (form == 2 && i + 4 < _parameterCount)
        {
            var r = (byte)Math.Clamp(_parameters[i + 2], 0, 255);
            var g = (byte)Math.Clamp(_parameters[i + 3], 0, 255);
            var b = (byte)Math.Clamp(_parameters[i + 4], 0, 255);
            i += 4;
            return TerminalColor.FromRgb(r, g, b);
        }

        return null;
    }

    private int Parameter(int index, int fallback) =>
        index < _parameterCount && _parameters[index] != 0 ? _parameters[index] : fallback;

    private enum State
    {
        Ground,
        Escape,
        CsiParameters,
        OscString,
        OscEscape,
        SkipOne,
    }
}
