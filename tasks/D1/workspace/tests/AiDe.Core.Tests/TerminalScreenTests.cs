using AiDe.Core.Terminal;

namespace AiDe.Core.Tests;

/// <summary>
/// The screen model — what a terminal *is* once the bytes have been interpreted.
/// </summary>
/// <remarks>
/// <para>Kept free of WPF entirely. A grid of styled cells with a cursor is a data structure, and
/// putting it behind a rendering framework would make every rule below testable only by drawing
/// pixels and reading them back. The renderer's job is to draw this; deciding what it contains is
/// this type's job alone.</para>
///
/// <para><b>Scrolling, not scrollback.</b> When the cursor passes the last row the screen shifts up
/// and the top row is discarded. History is a separate feature with its own memory budget, and
/// pretending a viewport is history would put an unbounded buffer behind an innocuous-looking
/// property.</para>
/// </remarks>
public sealed class TerminalScreenTests
{
    private static TerminalScreen Screen(int columns = 10, int rows = 4) => new(columns, rows);

    private static string RowText(TerminalScreen screen, int row) =>
        string.Concat(Enumerable.Range(0, screen.Columns).Select(c => screen[row, c].Character));

    // ---- the empty screen ---------------------------------------------------

    [Fact]
    public void ANewScreen_IsBlank_WithTheCursorHome()
    {
        var screen = Screen();

        Assert.Equal(0, screen.CursorRow);
        Assert.Equal(0, screen.CursorColumn);
        Assert.All(
            Enumerable.Range(0, screen.Rows),
            r => Assert.Equal(new string(' ', screen.Columns), RowText(screen, r)));
    }

    [Fact]
    public void ScreenDimensions_MustBePositive()
    {
        Assert.Throws<ArgumentOutOfRangeException>(() => new TerminalScreen(0, 4));
        Assert.Throws<ArgumentOutOfRangeException>(() => new TerminalScreen(10, 0));
    }

    // ---- writing ------------------------------------------------------------

    [Fact]
    public void Writing_PlacesCharactersAndAdvancesTheCursor()
    {
        var screen = Screen();

        screen.Write("hi");

        Assert.Equal("hi        ", RowText(screen, 0));
        Assert.Equal(2, screen.CursorColumn);
        Assert.Equal(0, screen.CursorRow);
    }

    [Fact]
    public void WritingPastTheLastColumn_WrapsToTheNextRow()
    {
        var screen = Screen(columns: 3, rows: 3);

        screen.Write("abcd");

        Assert.Equal("abc", RowText(screen, 0));
        Assert.Equal("d  ", RowText(screen, 1));
        Assert.Equal(1, screen.CursorRow);
    }

    [Fact]
    public void WritingPastTheLastRow_ScrollsAndDiscardsTheTopRow()
    {
        // The discard is the contract. A viewport that silently grew would be a memory leak wearing
        // the costume of a scrollback feature.
        var screen = Screen(columns: 3, rows: 2);

        screen.Write("abc");
        screen.LineFeed();
        screen.CarriageReturn();
        screen.Write("def");
        screen.LineFeed();
        screen.CarriageReturn();
        screen.Write("ghi");

        Assert.Equal("def", RowText(screen, 0));
        Assert.Equal("ghi", RowText(screen, 1));
        Assert.Equal(2, screen.Rows);
    }

    // ---- the C0 controls a terminal cannot do without ------------------------

    [Fact]
    public void CarriageReturn_ReturnsToColumnZero_WithoutChangingTheRow()
    {
        var screen = Screen();
        screen.Write("hello");

        screen.CarriageReturn();

        Assert.Equal(0, screen.CursorColumn);
        Assert.Equal(0, screen.CursorRow);
        Assert.Equal("hello     ", RowText(screen, 0));
    }

    [Fact]
    public void LineFeed_MovesDownAndKeepsTheColumn()
    {
        // Column-preserving is correct: the shell pairs LF with CR when it wants column zero, and a
        // terminal that moved the column itself would break every prompt that does not.
        var screen = Screen();
        screen.Write("abc");

        screen.LineFeed();

        Assert.Equal(1, screen.CursorRow);
        Assert.Equal(3, screen.CursorColumn);
    }

    [Fact]
    public void Backspace_MovesLeftWithoutErasing()
    {
        // Erasing here would double-erase: a shell deleting a character sends BS, space, BS.
        var screen = Screen();
        screen.Write("abc");

        screen.Backspace();

        Assert.Equal(2, screen.CursorColumn);
        Assert.Equal("abc       ", RowText(screen, 0));
    }

    [Fact]
    public void Backspace_AtColumnZero_StaysPut()
    {
        var screen = Screen();

        screen.Backspace();

        Assert.Equal(0, screen.CursorColumn);
        Assert.Equal(0, screen.CursorRow);
    }

    [Fact]
    public void Tab_MovesToTheNextEightColumnStop()
    {
        var screen = Screen(columns: 20, rows: 2);
        screen.Write("ab");

        screen.Tab();

        Assert.Equal(8, screen.CursorColumn);
    }

    [Fact]
    public void Tab_AtTheLastStop_StopsAtTheFinalColumn()
    {
        var screen = Screen(columns: 10, rows: 2);
        screen.MoveCursor(0, 9);

        screen.Tab();

        Assert.Equal(9, screen.CursorColumn);
    }

    // ---- cursor addressing ---------------------------------------------------

    [Fact]
    public void MoveCursor_ClampsToTheScreen()
    {
        // A program that addresses off-screen gets clamped, never an exception: the bytes come from
        // an untrusted process, and a crash would be a denial of service by escape sequence.
        var screen = Screen(columns: 10, rows: 4);

        screen.MoveCursor(99, 99);

        Assert.Equal(3, screen.CursorRow);
        Assert.Equal(9, screen.CursorColumn);

        screen.MoveCursor(-5, -5);

        Assert.Equal(0, screen.CursorRow);
        Assert.Equal(0, screen.CursorColumn);
    }

    // ---- erasing --------------------------------------------------------------

    [Fact]
    public void EraseInLine_ToEnd_ClearsFromTheCursorOnward()
    {
        var screen = Screen();
        screen.Write("abcdefghij");
        screen.MoveCursor(0, 3);

        screen.EraseInLine(EraseExtent.ToEnd);

        Assert.Equal("abc       ", RowText(screen, 0));
    }

    [Fact]
    public void EraseInLine_ToStart_ClearsUpToAndIncludingTheCursor()
    {
        var screen = Screen();
        screen.Write("abcdefghij");
        screen.MoveCursor(0, 3);

        screen.EraseInLine(EraseExtent.ToStart);

        Assert.Equal("    efghij", RowText(screen, 0));
    }

    [Fact]
    public void EraseInLine_All_ClearsTheRow_AndLeavesTheCursor()
    {
        var screen = Screen();
        screen.Write("abcdefghij");
        screen.MoveCursor(0, 3);

        screen.EraseInLine(EraseExtent.All);

        Assert.Equal("          ", RowText(screen, 0));
        Assert.Equal(3, screen.CursorColumn);
    }

    [Fact]
    public void EraseInDisplay_All_ClearsEveryRow()
    {
        var screen = Screen(columns: 4, rows: 3);
        screen.Write("aaaa");
        screen.LineFeed();
        screen.CarriageReturn();
        screen.Write("bbbb");

        screen.EraseInDisplay(EraseExtent.All);

        Assert.All(
            Enumerable.Range(0, 3),
            r => Assert.Equal("    ", RowText(screen, r)));
    }

    [Fact]
    public void EraseInDisplay_ToEnd_KeepsEverythingBeforeTheCursor()
    {
        var screen = Screen(columns: 4, rows: 3);
        screen.Write("aaaa");
        screen.LineFeed();
        screen.CarriageReturn();
        screen.Write("bbbb");
        screen.MoveCursor(1, 2);

        screen.EraseInDisplay(EraseExtent.ToEnd);

        Assert.Equal("aaaa", RowText(screen, 0));
        Assert.Equal("bb  ", RowText(screen, 1));
        Assert.Equal("    ", RowText(screen, 2));
    }

    // ---- styling ---------------------------------------------------------------

    [Fact]
    public void WrittenCells_CarryTheCurrentPenStyle()
    {
        var screen = Screen();
        screen.Pen = screen.Pen with
        {
            Foreground = TerminalColor.FromIndex(1),
            Attributes = CellAttributes.Bold,
        };

        screen.Write("x");

        var cell = screen[0, 0];
        Assert.Equal(TerminalColor.FromIndex(1), cell.Foreground);
        Assert.Equal(CellAttributes.Bold, cell.Attributes);
    }

    [Fact]
    public void ErasedCells_TakeTheCurrentBackground_NotTheDefault()
    {
        // A program that sets a background and clears the line expects the cleared region painted in
        // that background — this is how full-screen tools paint their canvas.
        var screen = Screen();
        screen.Pen = screen.Pen with { Background = TerminalColor.FromIndex(4) };

        screen.EraseInLine(EraseExtent.All);

        Assert.Equal(TerminalColor.FromIndex(4), screen[0, 0].Background);
    }

    // ---- resize -----------------------------------------------------------------

    [Fact]
    public void Resize_KeepsTheContentThatStillFits()
    {
        var screen = Screen(columns: 6, rows: 3);
        screen.Write("hello");

        screen.Resize(10, 5);

        Assert.Equal(10, screen.Columns);
        Assert.Equal(5, screen.Rows);
        Assert.Equal("hello     ", RowText(screen, 0));
    }

    [Fact]
    public void Resize_ClampsTheCursorIntoTheNewBounds()
    {
        var screen = Screen(columns: 10, rows: 5);
        screen.MoveCursor(4, 9);

        screen.Resize(4, 2);

        Assert.Equal(1, screen.CursorRow);
        Assert.Equal(3, screen.CursorColumn);
    }

    [Fact]
    public void Resize_ToTheSameSize_IsANoOp()
    {
        var screen = Screen(columns: 6, rows: 3);
        screen.Write("hello");

        screen.Resize(6, 3);

        Assert.Equal("hello ", RowText(screen, 0));
    }

    // ---- change tracking ----------------------------------------------------------

    [Fact]
    public void TheScreen_ReportsWhenItHasChanged_SoTheRendererNeedNotDiff()
    {
        // The renderer redraws on a timer; without this it would redraw a still screen 60 times a
        // second, which is the cost the coalescing policy exists to avoid.
        var screen = Screen();
        screen.ClearDirty();

        Assert.False(screen.IsDirty);

        screen.Write("a");

        Assert.True(screen.IsDirty);
    }

    // ---- cursor-under-render safety (regression: DC-061) --------------------
    // A focused terminal renders a cursor block AND redraws the character under it. The character
    // read used the raw indexer at (CursorRow, CursorColumn), but the cursor legitimately sits at
    // the pending-wrap column (CursorColumn == Columns) after writing the last column, and at the
    // bottom row that indexes exactly _cells.Length -> IndexOutOfRangeException, unhandled on the WPF
    // UI thread -> the whole application is terminated. Agent CLIs that draw a full-width status line
    // at the bottom hit this constantly. CellUnderCursor() is the safe read the renderer must use.

    [Fact]
    public void CellUnderCursor_InBounds_ReturnsTheCell()
    {
        var screen = Screen(columns: 4, rows: 2);
        screen.Write("hi"); // cursor now at (0, 2), still in bounds

        var cell = screen.CellUnderCursor();

        Assert.NotNull(cell);
        Assert.Equal(' ', cell!.Value.Character); // the not-yet-written cell under the cursor
    }

    [Fact]
    public void CellUnderCursor_AtPendingWrapOnTheBottomRow_IsNull_NotThrowing()
    {
        // Reproduce the crash scenario deterministically: fill the last row so the cursor is left at
        // the pending-wrap column (== Columns) on the bottom row. The raw indexer here is
        // _cells[Rows*Columns] - one past the end. CellUnderCursor must return null, never throw.
        var screen = Screen(columns: 4, rows: 2);
        screen.Write("row0");     // fills row 0, cursor wraps to (1, 0)
        screen.Write("row1");     // fills row 1, cursor left at pending-wrap (1, 4 == Columns)

        Assert.Equal(1, screen.CursorRow);
        Assert.Equal(screen.Columns, screen.CursorColumn); // pending wrap on the bottom row

        var cell = screen.CellUnderCursor(); // must NOT throw

        Assert.Null(cell);
    }

    [Fact]
    public void Resize_Shrink_ClampsTheCursor_SoASubsequentWriteAndReadDoNotThrow()
    {
        // The sibling: Resize copied cells but did not clamp the cursor, so a stale cursor after a
        // shrink could index out of bounds in Write and in the renderer. Drive the cursor to the far
        // corner, then shrink; the cursor must land within the new bounds.
        var screen = Screen(columns: 10, rows: 6);
        screen.MoveCursor(5, 9); // bottom-right of the old grid

        screen.Resize(columns: 4, rows: 3);

        Assert.True(screen.CursorRow < screen.Rows, $"CursorRow {screen.CursorRow} must be < {screen.Rows}");
        Assert.True(screen.CursorColumn < screen.Columns, $"CursorColumn {screen.CursorColumn} must be < {screen.Columns}");

        // A write and a cursor read at the clamped position must not throw.
        var ex = Record.Exception(() => { screen.Write("x"); _ = screen.CellUnderCursor(); });
        Assert.Null(ex);
    }

    // ---- in-place line editing: the sequences a TUI redraws with (#16) -------

    [Fact]
    public void EraseCharacters_ClearsASpanInPlace_WithoutShiftingTheRest()
    {
        var screen = Screen(columns: 10);
        screen.Write("abcdefghij");
        screen.MoveCursor(0, 2);

        screen.EraseCharacters(3); // erase c,d,e in place

        Assert.Equal("ab   fghij", RowText(screen, 0)); // fghij did NOT move left
    }

    [Fact]
    public void DeleteCharacters_ShiftsTheRestLeft_AndBlanksTheTail()
    {
        var screen = Screen(columns: 10);
        screen.Write("abcdefghij");
        screen.MoveCursor(0, 2);

        screen.DeleteCharacters(3); // delete c,d,e; fghij shifts left

        Assert.Equal("abfghij   ", RowText(screen, 0));
    }

    [Fact]
    public void InsertCharacters_ShiftsTheRestRight_AndOpensBlanks()
    {
        var screen = Screen(columns: 10);
        screen.Write("abcdefghij");
        screen.MoveCursor(0, 2);

        screen.InsertCharacters(2); // open 2 blanks at col 2; cd..ij shift right, hij fall off

        Assert.Equal("ab  cdefgh", RowText(screen, 0));
    }

    [Fact]
    public void EraseCharacters_PastTheEnd_ClampsToTheLineWidth()
    {
        var screen = Screen(columns: 6);
        screen.Write("abcdef");
        screen.MoveCursor(0, 4);

        screen.EraseCharacters(100); // more than remains

        Assert.Equal("abcd  ", RowText(screen, 0));
    }

    // ---- alternate screen buffer: a TUI never scribbles on the shell scrollback (T-T4) ----

    [Fact]
    public void AltScreen_PreservesTheMainBuffer_AndRestoresItOnLeave()
    {
        var screen = Screen(columns: 10, rows: 3);
        screen.Write("main");
        screen.MoveCursor(0, 4);
        Assert.Equal("main      ", RowText(screen, 0));

        screen.EnterAltScreen(saveCursor: true, clear: true);
        Assert.True(screen.AltScreen);
        Assert.Equal("          ", RowText(screen, 0)); // the alt buffer starts blank
        screen.MoveCursor(1, 0);
        screen.Write("alt");
        Assert.Equal("alt       ", RowText(screen, 1));

        screen.LeaveAltScreen(restoreCursor: true);
        Assert.False(screen.AltScreen);
        Assert.Equal("main      ", RowText(screen, 0)); // the shell's screen is back, untouched
        Assert.Equal(0, screen.CursorRow);
        Assert.Equal(4, screen.CursorColumn);           // and the cursor is where it was
    }

    [Fact]
    public void AltScreen_EnterWhileAlreadyInAlt_IsANoOpOnTheMainBuffer()
    {
        var screen = Screen(columns: 6, rows: 2);
        screen.Write("keep");
        screen.EnterAltScreen(saveCursor: true, clear: true);
        screen.EnterAltScreen(saveCursor: true, clear: false); // a second enter must not overwrite the saved main

        screen.LeaveAltScreen(restoreCursor: false);
        Assert.Equal("keep  ", RowText(screen, 0));
    }

    // ---- reads are total: the renderer never crashes the screen (DC-061) -----

    [Fact]
    public void ReadingTheCursorCell_AtDeferredWrapOnTheBottomRow_DoesNotThrow()
    {
        // Write defers the wrap: after filling the last cell of the last row the cursor sits at
        // (Rows-1, Columns) — one column past the grid. The renderer reads screen[CursorRow,
        // CursorColumn] to repaint the glyph under the cursor, so an unbounded indexer throws
        // IndexOutOfRangeException at exactly Rows*Columns. This is the crash the user hit.
        var screen = Screen(columns: 10, rows: 4);
        screen.Write(new string('a', 40));

        Assert.Equal(3, screen.CursorRow);
        Assert.Equal(10, screen.CursorColumn); // deferred wrap: == Columns, one past the last column

        var cell = screen[screen.CursorRow, screen.CursorColumn]; // must not throw
        Assert.Equal('a', cell.Character); // clamped back onto the last real cell
    }

    [Theory]
    [InlineData(-5, -5)]
    [InlineData(100, 100)]
    [InlineData(0, 999)]
    [InlineData(3, 10)]
    public void TheIndexer_ClampsOutOfRangeCoordinates_AndNeverThrows(int row, int column)
    {
        // The type documents "every coordinate is clamped; nothing here throws on bad input" — the
        // mutators honour it but the indexer did not. A read is as reachable from untrusted output
        // as a write, so it must honour the same contract.
        var screen = Screen(10, 4);
        screen.Write("abc");

        var cell = screen[row, column]; // must not throw for any coordinate

        Assert.False(char.IsControl(cell.Character) && cell.Character != '\0');
    }

    // ---- writes and reads coordinate across threads (DC-062) ----------------

    [Fact]
    public async Task ConcurrentWritesAndReads_UnderSyncRoot_DoNotThrow()
    {
        // The pump mutates the screen (Write + the occasional Resize) on one thread while the
        // renderer reads every cell on another. They coordinate through SyncRoot; without it a
        // Resize swapping the cell array against a freshly-read column count indexes past the end.
        // Both sides take the lock, exactly as PumpAsync and OnRender do.
        var screen = new TerminalScreen(20, 8);
        var errors = new System.Collections.Concurrent.ConcurrentQueue<Exception>();
        using var stop = new CancellationTokenSource(TimeSpan.FromMilliseconds(250));

        var writer = Task.Run(() =>
        {
            var rnd = new Random(1);
            try
            {
                while (!stop.IsCancellationRequested)
                {
                    lock (screen.SyncRoot)
                    {
                        screen.Write("x");
                        if (rnd.Next(48) == 0)
                        {
                            screen.Resize(rnd.Next(4, 40), rnd.Next(2, 20));
                        }
                    }
                }
            }
            catch (Exception ex) { errors.Enqueue(ex); }
        });

        var reader = Task.Run(() =>
        {
            try
            {
                while (!stop.IsCancellationRequested)
                {
                    lock (screen.SyncRoot)
                    {
                        for (var r = 0; r < screen.Rows; r++)
                        {
                            for (var c = 0; c < screen.Columns; c++)
                            {
                                _ = screen[r, c].Character;
                            }
                        }

                        _ = screen[screen.CursorRow, screen.CursorColumn].Character;
                    }
                }
            }
            catch (Exception ex) { errors.Enqueue(ex); }
        });

        await Task.WhenAll(writer, reader);

        Assert.Empty(errors);
    }
}
