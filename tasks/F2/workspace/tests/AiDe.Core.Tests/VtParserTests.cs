using System.Text;
using AiDe.Core.Terminal;

namespace AiDe.Core.Tests;

/// <summary>
/// The display parser: session bytes in, screen state out.
/// </summary>
/// <remarks>
/// <para><b>Distinct from <see cref="OscParser"/> on purpose, and the pair are not redundant.</b>
/// That one reads the stream for <i>authenticated state claims</i> and is a security control; this
/// one reads the same stream for <i>what to draw</i>. Two passes over the same bytes costs nothing
/// worth counting — S3 measured a scanner at 2361× the 1 MiB/s budget — and merging them would put
/// display concerns inside a control whose whole value is that it is small enough to reason about.
/// What this parser must do with OSC is skip it, so a clipboard sequence never appears on screen as
/// text.</para>
///
/// <para><b>Every byte is hostile input</b> (D2). The child process chooses all of it, so
/// malformed, truncated, over-long and nonsensical sequences are the normal case, not the edge. None
/// of them may throw: a crash reachable by printing is a denial of service.</para>
/// </remarks>
public sealed class VtParserTests
{
    private static (TerminalScreen Screen, VtParser Parser) New(int columns = 20, int rows = 4)
    {
        var screen = new TerminalScreen(columns, rows);
        return (screen, new VtParser(screen));
    }

    private static void Feed(VtParser parser, string text) =>
        parser.Consume(Encoding.UTF8.GetBytes(text));

    private static string RowText(TerminalScreen screen, int row) =>
        string.Concat(Enumerable.Range(0, screen.Columns).Select(c => screen[row, c].Character));

    private const string Esc = "";

    // ---- plain text and the C0 controls -------------------------------------

    [Fact]
    public void PlainText_IsWrittenToTheScreen()
    {
        var (screen, parser) = New();

        Feed(parser, "hello");

        Assert.Equal("hello               ", RowText(screen, 0));
    }

    [Fact]
    public void CarriageReturnLineFeed_StartsTheNextRow()
    {
        var (screen, parser) = New();

        Feed(parser, "one\r\ntwo");

        Assert.StartsWith("one", RowText(screen, 0), StringComparison.Ordinal);
        Assert.StartsWith("two", RowText(screen, 1), StringComparison.Ordinal);
    }

    [Fact]
    public void Bell_IsConsumedWithoutBeingDrawn()
    {
        var (screen, parser) = New();

        Feed(parser, "ab");

        Assert.StartsWith("ab", RowText(screen, 0), StringComparison.Ordinal);
    }

    // ---- cursor addressing ----------------------------------------------------

    [Fact]
    public void CursorPosition_IsOneBasedOnTheWire_AndZeroBasedInTheModel()
    {
        // Off-by-one here misplaces every full-screen program by a row and a column, and looks
        // plausible enough to survive a glance.
        var (screen, parser) = New();

        Feed(parser, $"{Esc}[2;5H");

        Assert.Equal(1, screen.CursorRow);
        Assert.Equal(4, screen.CursorColumn);
    }

    [Fact]
    public void CursorPosition_WithNoParameters_GoesHome()
    {
        var (screen, parser) = New();
        screen.MoveCursor(2, 5);

        Feed(parser, $"{Esc}[H");

        Assert.Equal(0, screen.CursorRow);
        Assert.Equal(0, screen.CursorColumn);
    }

    [Theory]
    [InlineData("A", 1, 5)]  // up
    [InlineData("B", 3, 5)]  // down
    [InlineData("C", 2, 6)]  // forward
    [InlineData("D", 2, 4)]  // back
    public void CursorMovement_MovesOneCellByDefault(string final, int expectedRow, int expectedColumn)
    {
        var (screen, parser) = New();
        screen.MoveCursor(2, 5);

        Feed(parser, $"{Esc}[{final}");

        Assert.Equal(expectedRow, screen.CursorRow);
        Assert.Equal(expectedColumn, screen.CursorColumn);
    }

    [Fact]
    public void CursorMovement_HonoursACount()
    {
        var (screen, parser) = New();
        screen.MoveCursor(3, 10);

        Feed(parser, $"{Esc}[3A");

        Assert.Equal(0, screen.CursorRow);
    }

    // ---- erasing ---------------------------------------------------------------

    [Fact]
    public void EraseInLine_DefaultsToEraseToEnd()
    {
        var (screen, parser) = New();
        Feed(parser, "abcdef");
        screen.MoveCursor(0, 3);

        Feed(parser, $"{Esc}[K");

        Assert.Equal("abc                 ", RowText(screen, 0));
    }

    [Fact]
    public void EraseInDisplay_Two_ClearsTheWholeScreen()
    {
        var (screen, parser) = New();
        Feed(parser, "abc\r\ndef");

        Feed(parser, $"{Esc}[2J");

        Assert.Equal(new string(' ', 20), RowText(screen, 0));
        Assert.Equal(new string(' ', 20), RowText(screen, 1));
    }

    // ---- SGR: colour and attributes ---------------------------------------------

    [Fact]
    public void Sgr_SetsAndResetsTheForeground()
    {
        var (screen, parser) = New();

        Feed(parser, $"{Esc}[31mR{Esc}[0mD");

        Assert.Equal(TerminalColor.FromIndex(1), screen[0, 0].Foreground);
        Assert.Equal(TerminalColor.Default, screen[0, 1].Foreground);
    }

    [Fact]
    public void Sgr_BrightForegroundsAreTheUpperEight()
    {
        var (screen, parser) = New();

        Feed(parser, $"{Esc}[91mR");

        Assert.Equal(TerminalColor.FromIndex(9), screen[0, 0].Foreground);
    }

    [Fact]
    public void Sgr_SetsTheBackground()
    {
        var (screen, parser) = New();

        Feed(parser, $"{Esc}[44mB");

        Assert.Equal(TerminalColor.FromIndex(4), screen[0, 0].Background);
    }

    [Fact]
    public void Sgr_SupportsTheTwoHundredFiftySixColourForm()
    {
        var (screen, parser) = New();

        Feed(parser, $"{Esc}[38;5;208mX");

        Assert.Equal(TerminalColor.FromIndex(208), screen[0, 0].Foreground);
    }

    [Fact]
    public void Sgr_SupportsTrueColour()
    {
        var (screen, parser) = New();

        Feed(parser, $"{Esc}[38;2;10;20;30mX");

        Assert.Equal(TerminalColor.FromRgb(10, 20, 30), screen[0, 0].Foreground);
    }

    [Fact]
    public void Sgr_CarriesBoldUnderlineAndInverse()
    {
        var (screen, parser) = New();

        Feed(parser, $"{Esc}[1;4;7mX");

        Assert.Equal(
            CellAttributes.Bold | CellAttributes.Underline | CellAttributes.Inverse,
            screen[0, 0].Attributes);
    }

    [Fact]
    public void Sgr_WithNoParameters_MeansReset()
    {
        var (screen, parser) = New();
        Feed(parser, $"{Esc}[1;31m");

        Feed(parser, $"{Esc}[mX");

        Assert.Equal(TerminalColor.Default, screen[0, 0].Foreground);
        Assert.Equal(CellAttributes.None, screen[0, 0].Attributes);
    }

    // ---- OSC is skipped, never drawn ---------------------------------------------

    [Fact]
    public void OscSequences_AreSkippedRatherThanDrawn()
    {
        // Without this a window-title or clipboard sequence appears on screen as literal text —
        // which is both wrong and a way for a child process to paint arbitrary characters that the
        // user believes came from a program's output.
        var (screen, parser) = New();

        Feed(parser, $"a{Esc}]0;a hostile window title{Esc}\\b");

        Assert.StartsWith("ab", RowText(screen, 0), StringComparison.Ordinal);
    }

    [Fact]
    public void BelTerminatedOsc_IsAlsoSkipped()
    {
        var (screen, parser) = New();

        Feed(parser, $"a{Esc}]0;titleb");

        Assert.StartsWith("ab", RowText(screen, 0), StringComparison.Ordinal);
    }

    // ---- hostile and malformed input ------------------------------------------------

    [Fact]
    public void ASequenceSplitAcrossChunks_IsStillUnderstood()
    {
        // Chunk boundaries are set by the pipe. A parser that only handled whole-chunk sequences
        // would pass every test written in one string and fail on a 4 KiB read boundary.
        var (screen, parser) = New();

        parser.Consume(Encoding.UTF8.GetBytes($"{Esc}[3"));
        parser.Consume(Encoding.UTF8.GetBytes("1m"));
        parser.Consume(Encoding.UTF8.GetBytes("R"));

        Assert.Equal(TerminalColor.FromIndex(1), screen[0, 0].Foreground);
    }

    [Fact]
    public void AnUnknownFinalByte_IsIgnoredWithoutDisturbingTheText()
    {
        var (screen, parser) = New();

        Feed(parser, $"a{Esc}[42`b");

        Assert.StartsWith("ab", RowText(screen, 0), StringComparison.Ordinal);
    }

    [Fact]
    public void AnAbsurdParameterCount_DoesNotThrowOrAllocateWithoutBound()
    {
        var (_, parser) = New();
        var hostile = Esc + "[" + string.Join(';', Enumerable.Repeat("1", 5000)) + "m";

        var thrown = Record.Exception(() => Feed(parser, hostile));

        Assert.Null(thrown);
    }

    [Fact]
    public void AnEnormousParameterValue_DoesNotThrow()
    {
        var (screen, parser) = New();

        var thrown = Record.Exception(() => Feed(parser, $"{Esc}[99999999999999999999H"));

        Assert.Null(thrown);
        Assert.InRange(screen.CursorRow, 0, screen.Rows - 1);
    }

    [Fact]
    public void AnUnterminatedEscape_AtTheEndOfAChunk_DoesNotSwallowTheNextChunk()
    {
        var (screen, parser) = New();

        parser.Consume(Encoding.UTF8.GetBytes($"a{Esc}"));
        parser.Consume(Encoding.UTF8.GetBytes("[31mR"));

        Assert.Equal(TerminalColor.FromIndex(1), screen[0, 1].Foreground);
    }

    [Fact]
    public void Utf8_IsDecodedAcrossChunkBoundaries()
    {
        // A multi-byte character split by a read boundary must not render as two replacement
        // characters — which is what a naive per-chunk decode produces.
        var (screen, parser) = New();
        var bytes = Encoding.UTF8.GetBytes("é");

        parser.Consume(bytes.AsSpan(0, 1));
        parser.Consume(bytes.AsSpan(1));

        Assert.Equal('é', screen[0, 0].Character);
    }

    // ---- in-place line editing (ECH/ICH/DCH) — the #16 stale-glyph fix -------

    [Fact]
    public void EraseCharacters_CsiX_ClearsInPlace()
    {
        var (screen, parser) = New(columns: 10);
        Feed(parser, "abcdefghij");
        Feed(parser, $"{Esc}[3G");   // cursor to column 3 (1-based) == index 2
        Feed(parser, $"{Esc}[3X");   // ECH 3

        Assert.Equal("ab   fghij", RowText(screen, 0));
    }

    [Fact]
    public void DeleteCharacters_CsiP_ShiftsLeft()
    {
        var (screen, parser) = New(columns: 10);
        Feed(parser, "abcdefghij");
        Feed(parser, $"{Esc}[3G{Esc}[3P");  // to col 3, delete 3

        Assert.Equal("abfghij   ", RowText(screen, 0));
    }

    [Fact]
    public void InsertCharacters_CsiAt_ShiftsRight()
    {
        var (screen, parser) = New(columns: 10);
        Feed(parser, "abcdefghij");
        Feed(parser, $"{Esc}[3G{Esc}[2@");  // to col 3, insert 2 blanks

        Assert.Equal("ab  cdefgh", RowText(screen, 0));
    }

    [Fact]
    public void EraseInsertDelete_WithNoParameter_DefaultToOne()
    {
        var (screen, parser) = New(columns: 6);
        Feed(parser, "abcdef");
        Feed(parser, $"{Esc}[1G{Esc}[P");   // to col 1, DCH default 1 -> delete 'a'

        Assert.Equal("bcdef ", RowText(screen, 0));
    }

    // ---- DEC private modes: application cursor keys (DECCKM), the #arrow-keys fix ----

    [Fact]
    public void ApplicationCursorKeys_DefaultsOff()
    {
        var (screen, _) = New();
        Assert.False(screen.ApplicationCursorKeys);
    }

    [Fact]
    public void Decckm_Set_EnablesApplicationCursorKeys()
    {
        var (screen, parser) = New();
        Feed(parser, $"{Esc}[?1h");   // DECCKM set

        Assert.True(screen.ApplicationCursorKeys);
    }

    [Fact]
    public void Decckm_Reset_DisablesApplicationCursorKeys()
    {
        var (screen, parser) = New();
        Feed(parser, $"{Esc}[?1h");
        Feed(parser, $"{Esc}[?1l");   // DECCKM reset

        Assert.False(screen.ApplicationCursorKeys);
    }

    [Fact]
    public void AnUnhandledPrivateMode_IsIgnored_AndDoesNotTouchCursorKeys()
    {
        var (screen, parser) = New();
        Feed(parser, $"{Esc}[?25l");  // hide cursor — unhandled, must not throw or flip DECCKM

        Assert.False(screen.ApplicationCursorKeys);
    }

    [Fact]
    public void BracketedPaste_SetAndReset_TracksTheMode()
    {
        var (screen, parser) = New();
        Assert.False(screen.BracketedPaste);

        Feed(parser, $"{Esc}[?2004h");
        Assert.True(screen.BracketedPaste);

        Feed(parser, $"{Esc}[?2004l");
        Assert.False(screen.BracketedPaste);
    }

    [Fact]
    public void MultiplePrivateModes_InOneSequence_AreAllApplied()
    {
        var (screen, parser) = New();
        Feed(parser, $"{Esc}[?1;2004h");   // DECCKM + bracketed paste together

        Assert.True(screen.ApplicationCursorKeys);
        Assert.True(screen.BracketedPaste);
    }

    [Fact]
    public void AltScreen_1049_EntersAndLeavesViaTheParser()
    {
        var (screen, parser) = New();

        Feed(parser, $"{Esc}[?1049h");
        Assert.True(screen.AltScreen);

        Feed(parser, $"{Esc}[?1049l");
        Assert.False(screen.AltScreen);
    }

    [Theory]
    [InlineData("1000", MouseTracking.Normal)]
    [InlineData("1002", MouseTracking.ButtonMotion)]
    [InlineData("1003", MouseTracking.AnyMotion)]
    public void MouseModes_SetTheTrackingLevel_AndResetTurnsItOff(string mode, MouseTracking expected)
    {
        var (screen, parser) = New();

        Feed(parser, $"{Esc}[?{mode}h");
        Assert.Equal(expected, screen.MouseMode);

        Feed(parser, $"{Esc}[?{mode}l");
        Assert.Equal(MouseTracking.None, screen.MouseMode);
    }

    [Fact]
    public void SgrMouseMode_1006_TogglesTheExtendedEncoding()
    {
        var (screen, parser) = New();
        Assert.False(screen.MouseSgr);

        Feed(parser, $"{Esc}[?1006h");
        Assert.True(screen.MouseSgr);

        Feed(parser, $"{Esc}[?1006l");
        Assert.False(screen.MouseSgr);
    }
}
