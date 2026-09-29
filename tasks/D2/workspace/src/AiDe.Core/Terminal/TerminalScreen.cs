namespace AiDe.Core.Terminal;

/// <summary>How a cell's colour is specified.</summary>
public enum TerminalColorKind
{
    /// <summary>The renderer's own foreground or background. Not a palette entry.</summary>
    Default,

    /// <summary>An index into the 256-colour palette. 0–15 are the ANSI colours.</summary>
    Indexed,

    /// <summary>A direct 24-bit colour.</summary>
    Rgb,
}

/// <summary>
/// A cell colour, as the wire expresses it.
/// </summary>
/// <remarks>
/// Deliberately not a rendering type. Keeping the model in *terminal* terms — "palette index 4",
/// not "this shade of blue" — is what lets the theme decide what index 4 looks like, and what keeps
/// the whole screen model free of a UI framework. <see cref="Default"/> is a distinct case rather
/// than a magic index because "whatever the theme's foreground is" is not a colour.
/// </remarks>
public readonly record struct TerminalColor(TerminalColorKind Kind, int Index, byte R, byte G, byte B)
{
    public static TerminalColor Default => new(TerminalColorKind.Default, 0, 0, 0, 0);

    public static TerminalColor FromIndex(int index) =>
        new(TerminalColorKind.Indexed, Math.Clamp(index, 0, 255), 0, 0, 0);

    public static TerminalColor FromRgb(byte r, byte g, byte b) =>
        new(TerminalColorKind.Rgb, 0, r, g, b);
}

/// <summary>Non-colour styling carried by a cell.</summary>
[Flags]
public enum CellAttributes
{
    None = 0,
    Bold = 1 << 0,
    Underline = 1 << 1,

    /// <summary>Foreground and background swap at draw time. Used for selections and cursors.</summary>
    Inverse = 1 << 2,
}

/// <summary>One character cell.</summary>
public readonly record struct TerminalCell(
    char Character,
    TerminalColor Foreground,
    TerminalColor Background,
    CellAttributes Attributes)
{
    public static TerminalCell Blank => new(' ', TerminalColor.Default, TerminalColor.Default, CellAttributes.None);
}

/// <summary>The style subsequent writes are drawn in — the terminal's current pen.</summary>
public readonly record struct TerminalPen(
    TerminalColor Foreground,
    TerminalColor Background,
    CellAttributes Attributes)
{
    public static TerminalPen Default => new(TerminalColor.Default, TerminalColor.Default, CellAttributes.None);
}

/// <summary>How much of a line or screen an erase covers.</summary>
public enum EraseExtent
{
    /// <summary>From the cursor to the end, inclusive.</summary>
    ToEnd,

    /// <summary>From the start to the cursor, inclusive.</summary>
    ToStart,

    /// <summary>Everything.</summary>
    All,
}

/// <summary>How the child wants pointer events reported.</summary>
public enum MouseTracking
{
    /// <summary>No mouse reporting — the pointer is the shell's own (select/copy).</summary>
    None,

    /// <summary>Button press and release only (xterm <c>?1000</c>).</summary>
    Normal,

    /// <summary>Press/release plus motion while a button is held (xterm <c>?1002</c>).</summary>
    ButtonMotion,

    /// <summary>Press/release plus all pointer motion (xterm <c>?1003</c>).</summary>
    AnyMotion,
}

/// <summary>
/// What a terminal is, once the bytes have been interpreted: a grid of styled cells and a cursor.
/// </summary>
/// <remarks>
/// <para><b>No WPF, by design.</b> Every rule here — wrapping, scrolling, what an erase covers,
/// where the cursor lands — is a data-structure question. Behind a rendering framework each one
/// would be testable only by drawing pixels and reading them back, and the rules would be verified
/// approximately or not at all. The renderer draws this; deciding what it contains is this type's
/// job.</para>
///
/// <para><b>Scrolling, not scrollback.</b> When the cursor passes the last row the grid shifts up
/// and the top row is discarded. History is a separate feature with its own memory budget, and
/// growing this buffer to provide it would put an unbounded allocation behind an innocuous property
/// — with the child process choosing how much.
/// simplify: viewport only; ceiling is one screen; upgrade trigger = scrollback becomes a
/// requirement, at which point it arrives as a bounded ring beside this, not inside it.</para>
///
/// <para><b>Nothing here throws on bad input.</b> Every coordinate is clamped — including the
/// indexer, not only the mutators — because the values arrive in escape sequences written by an
/// untrusted process and an exception reachable by printing is a denial of service. A read is as
/// reachable from that output as a write (the renderer reads the cursor cell every frame), so it
/// honours the same clamp.</para>
///
/// <para>One screen belongs to one session's parser, which writes it on the pump thread while the
/// renderer reads it on the UI thread. They coordinate through <see cref="SyncRoot"/>: a mutation
/// is made under the lock, and a frame is drawn under the lock, so neither observes the other
/// half-applied. See <see cref="SyncRoot"/> for why the dirty flag alone is not enough.</para>
/// </remarks>
public sealed class TerminalScreen
{
    private const int TabStop = 8;

    private TerminalCell[] _cells;

    // The alternate screen buffer (ADR-free; xterm ?1049/?47/?1047). While the alt screen is active,
    // this holds the MAIN buffer; while it is not, it holds the last alt buffer (or null). A full-screen
    // TUI draws on the alt screen and the shell's scrollback is restored untouched on exit — without it,
    // the TUI's output overwrites the shell history ("it's just a terminal / see the output", smoke 9-2).
    private TerminalCell[]? _inactiveCells;
    private int _savedCursorRow;
    private int _savedCursorColumn;

    public TerminalScreen(int columns, int rows)
    {
        ArgumentOutOfRangeException.ThrowIfLessThan(columns, 1);
        ArgumentOutOfRangeException.ThrowIfLessThan(rows, 1);

        Columns = columns;
        Rows = rows;
        _cells = NewGrid(columns, rows, TerminalCell.Blank);
    }

    public int Columns { get; private set; }

    public int Rows { get; private set; }

    public int CursorRow { get; private set; }

    public int CursorColumn { get; private set; }

    /// <summary>The style applied to subsequent writes and erases.</summary>
    public TerminalPen Pen { get; set; } = TerminalPen.Default;

    /// <summary>
    /// Has anything changed since <see cref="ClearDirty"/>?
    /// </summary>
    /// <remarks>
    /// The renderer presents on a timer to coalesce a fast producer into frames. Without this flag
    /// it would redraw a motionless screen at frame rate forever — the cost the coalescing policy
    /// exists to avoid, paid continuously instead of never.
    /// </remarks>
    public bool IsDirty { get; private set; } = true;

    public TerminalCell this[int row, int column] =>
        _cells[(Math.Clamp(row, 0, Rows - 1) * Columns) + Math.Clamp(column, 0, Columns - 1)];

    /// <summary>
    /// The monitor that coordinates mutation and reads across threads.
    /// </summary>
    /// <remarks>
    /// The parser writes this screen on the session's pump thread while the renderer reads it on the
    /// UI thread (the two differ by three orders of magnitude in rate, so marshalling every write to
    /// the UI thread is not affordable — see the surface). "Joined only by the dirty flag" is not a
    /// synchronization primitive: a <see cref="Resize"/> swaps <c>_cells</c> and updates
    /// <see cref="Columns"/> as two separate writes, and a reader that observes the new column count
    /// against the old array indexes past its end. A writer holds this lock across a mutation; the
    /// renderer holds it across a whole frame, so a frame never sees a half-applied change.
    /// </remarks>
    public object SyncRoot { get; } = new();

    /// <summary>
    /// Whether the child has enabled <b>application cursor key mode</b> (DECCKM, <c>ESC [ ? 1 h</c>).
    /// </summary>
    /// <remarks>
    /// A full-screen TUI (Claude Code's menus, vim, less) turns this on and then expects the cursor
    /// keys as <b>SS3</b> (<c>ESC O A</c>) rather than CSI (<c>ESC [ A</c>). A terminal that ignores
    /// the mode and always sends CSI leaves the arrows dead in exactly those programs — the reported
    /// "arrow keys don't work in the Claude Code session" (smoke 9-2). Input encoding is the reader
    /// of this flag (<see cref="TerminalInput"/>); the parser is its writer.
    /// </remarks>
    public bool ApplicationCursorKeys { get; private set; }

    /// <summary>Sets or clears application cursor key mode (DECCKM). Display is unaffected, so no repaint.</summary>
    public void SetApplicationCursorKeys(bool enabled) => ApplicationCursorKeys = enabled;

    /// <summary>
    /// Whether the child has enabled <b>bracketed paste</b> (<c>ESC [ ? 2004 h</c>). When on, pasted
    /// text is wrapped in <c>ESC [ 200~ … ESC [ 201~</c> so the program can tell a paste from typing and
    /// does not run each pasted line as it arrives — the behaviour Claude Code and every modern shell
    /// rely on for a multi-line prompt.
    /// </summary>
    public bool BracketedPaste { get; private set; }

    /// <summary>Sets or clears bracketed paste mode. Display is unaffected, so no repaint.</summary>
    public void SetBracketedPaste(bool enabled) => BracketedPaste = enabled;

    /// <summary>Whether the alternate screen buffer is currently active (a full-screen TUI is drawing).</summary>
    public bool AltScreen { get; private set; }

    /// <summary>How the child wants mouse events reported (xterm <c>?1000</c>/<c>?1002</c>/<c>?1003</c>).</summary>
    public MouseTracking MouseMode { get; private set; }

    /// <summary>Whether the child asked for SGR extended mouse encoding (<c>?1006</c>) — the modern form.</summary>
    public bool MouseSgr { get; private set; }

    /// <summary>Sets the mouse tracking level (or turns it off). Display is unaffected.</summary>
    public void SetMouseMode(MouseTracking mode) => MouseMode = mode;

    /// <summary>Sets or clears SGR extended mouse encoding.</summary>
    public void SetMouseSgr(bool enabled) => MouseSgr = enabled;

    /// <summary>
    /// Switches to the alternate screen buffer (xterm <c>?1049h</c>/<c>?47h</c>/<c>?1047h</c>). The main
    /// buffer is set aside untouched and restored on <see cref="LeaveAltScreen"/>, so a TUI never
    /// scribbles on the shell's scrollback. <paramref name="saveCursor"/> (the <c>?1049</c> variant)
    /// remembers the cursor to restore on exit; <paramref name="clear"/> blanks the alt buffer on entry.
    /// </summary>
    public void EnterAltScreen(bool saveCursor, bool clear)
    {
        if (AltScreen)
        {
            if (clear) { FillRows(0, Rows - 1); IsDirty = true; }
            return;
        }

        if (saveCursor)
        {
            _savedCursorRow = CursorRow;
            _savedCursorColumn = CursorColumn;
        }

        var main = _cells;
        // Reuse the prior alt buffer only if it still fits the current grid; otherwise start fresh.
        _cells = _inactiveCells is { } prior && prior.Length == main.Length
            ? prior
            : NewGrid(Columns, Rows, TerminalCell.Blank);
        _inactiveCells = main;
        AltScreen = true;

        if (clear) { FillRows(0, Rows - 1); }
        IsDirty = true;
    }

    /// <summary>
    /// Switches back to the main screen buffer (xterm <c>?1049l</c>/<c>?47l</c>/<c>?1047l</c>), restoring
    /// the shell's scrollback exactly. <paramref name="restoreCursor"/> (the <c>?1049</c> variant) puts
    /// the cursor back where it was when the alt screen was entered.
    /// </summary>
    public void LeaveAltScreen(bool restoreCursor)
    {
        if (!AltScreen) { return; }

        var alt = _cells;
        // The saved main buffer must still fit; a resize while in the alt screen makes it stale, in
        // which case a fresh cleared main is the safe degrade rather than an out-of-bounds restore.
        _cells = _inactiveCells is { } main && main.Length == alt.Length
            ? main
            : NewGrid(Columns, Rows, TerminalCell.Blank);
        _inactiveCells = alt;
        AltScreen = false;

        if (restoreCursor)
        {
            CursorRow = Math.Clamp(_savedCursorRow, 0, Rows - 1);
            CursorColumn = Math.Clamp(_savedCursorColumn, 0, Columns - 1);
        }

        IsDirty = true;
    }

    /// <summary>
    /// The cell under the cursor, or <c>null</c> when the cursor is not on a real cell. The cursor
    /// legitimately sits off the grid at the <b>pending-wrap</b> column (<c>CursorColumn == Columns</c>,
    /// held after writing the last column until the next write wraps), and can be left outside the grid
    /// by other sequences. The renderer MUST read the character-under-cursor through this, never through
    /// the raw indexer: an out-of-bounds index in <c>OnRender</c> throws on the WPF UI thread, which is
    /// unhandled and terminates the whole application (DC-061).
    /// </summary>
    public TerminalCell? CellUnderCursor() =>
        CursorRow >= 0 && CursorRow < Rows && CursorColumn >= 0 && CursorColumn < Columns
            ? _cells[(CursorRow * Columns) + CursorColumn]
            : null;

    public void ClearDirty() => IsDirty = false;

    /// <summary>Writes text at the cursor, wrapping and scrolling as needed.</summary>
    public void Write(string text)
    {
        ArgumentNullException.ThrowIfNull(text);

        foreach (var c in text)
        {
            Write(c);
        }
    }

    /// <summary>Writes one character at the cursor.</summary>
    public void Write(char character)
    {
        if (CursorColumn >= Columns)
        {
            CursorColumn = 0;
            LineFeed();
        }

        _cells[(CursorRow * Columns) + CursorColumn] =
            new TerminalCell(character, Pen.Foreground, Pen.Background, Pen.Attributes);

        CursorColumn++;
        IsDirty = true;
    }

    public void CarriageReturn()
    {
        CursorColumn = 0;
        IsDirty = true;
    }

    /// <summary>
    /// Moves down one row, scrolling when already at the bottom. The column is unchanged.
    /// </summary>
    /// <remarks>
    /// Column-preserving is correct even though it looks like an omission: a shell that wants column
    /// zero sends CR with the LF, and a terminal that moved the column itself would break every
    /// program that relies on the distinction.
    /// </remarks>
    public void LineFeed()
    {
        if (CursorRow < Rows - 1)
        {
            CursorRow++;
        }
        else
        {
            ScrollUp();
        }

        IsDirty = true;
    }

    /// <summary>Moves left one cell without erasing.</summary>
    /// <remarks>
    /// Erasing here would delete twice: a shell removing a character sends BS, space, BS, and a
    /// destructive backspace would consume the character before the space arrived to do it.
    /// </remarks>
    public void Backspace()
    {
        if (CursorColumn > 0)
        {
            CursorColumn--;
            IsDirty = true;
        }
    }

    /// <summary>Moves to the next eight-column tab stop, stopping at the last column.</summary>
    public void Tab()
    {
        var next = ((CursorColumn / TabStop) + 1) * TabStop;
        CursorColumn = Math.Min(next, Columns - 1);
        IsDirty = true;
    }

    /// <summary>Places the cursor, clamped into the screen.</summary>
    public void MoveCursor(int row, int column)
    {
        CursorRow = Math.Clamp(row, 0, Rows - 1);
        CursorColumn = Math.Clamp(column, 0, Columns - 1);
        IsDirty = true;
    }

    public void EraseInLine(EraseExtent extent)
    {
        var (from, to) = extent switch
        {
            EraseExtent.ToEnd => (CursorColumn, Columns - 1),
            EraseExtent.ToStart => (0, CursorColumn),
            _ => (0, Columns - 1),
        };

        for (var column = from; column <= to; column++)
        {
            _cells[(CursorRow * Columns) + column] = Erased();
        }

        IsDirty = true;
    }

    public void EraseInDisplay(EraseExtent extent)
    {
        switch (extent)
        {
            case EraseExtent.ToEnd:
                EraseInLine(EraseExtent.ToEnd);
                FillRows(CursorRow + 1, Rows - 1);
                break;

            case EraseExtent.ToStart:
                EraseInLine(EraseExtent.ToStart);
                FillRows(0, CursorRow - 1);
                break;

            default:
                FillRows(0, Rows - 1);
                break;
        }

        IsDirty = true;
    }

    /// <summary>
    /// Erases <paramref name="count"/> cells from the cursor <b>in place</b>, without shifting the
    /// rest of the line (ECH, <c>CSI n X</c>).
    /// </summary>
    /// <remarks>
    /// A TUI (Claude Code, less, a shell's line editor) clears a span this way when it repaints a
    /// line. Dropping it — as an unhandled final was — leaves the old glyphs in the grid, and the
    /// full-repaint renderer then faithfully draws them: the "characters painted without proper
    /// refresh" report (smoke 9-1 #16). Erases to the current background, like every other erase.
    /// </remarks>
    public void EraseCharacters(int count)
    {
        var to = Math.Min(CursorColumn + Math.Max(count, 1), Columns);
        for (var column = CursorColumn; column < to; column++)
        {
            _cells[(CursorRow * Columns) + column] = Erased();
        }

        IsDirty = true;
    }

    /// <summary>
    /// Inserts <paramref name="count"/> blank cells at the cursor, shifting the rest of the line right
    /// and dropping what falls off the end (ICH, <c>CSI n @</c>).
    /// </summary>
    /// <remarks>Typing into the middle of an existing line uses this; ignoring it overwrites instead of inserting.</remarks>
    public void InsertCharacters(int count)
    {
        var n = Math.Clamp(count, 1, Columns - CursorColumn);
        var rowStart = CursorRow * Columns;
        for (var column = Columns - 1; column >= CursorColumn + n; column--)
        {
            _cells[rowStart + column] = _cells[rowStart + column - n];
        }

        for (var column = CursorColumn; column < CursorColumn + n; column++)
        {
            _cells[rowStart + column] = Erased();
        }

        IsDirty = true;
    }

    /// <summary>
    /// Deletes <paramref name="count"/> cells at the cursor, shifting the rest of the line left and
    /// blanking the tail (DCH, <c>CSI n P</c>).
    /// </summary>
    /// <remarks>Deleting a character mid-line uses this; ignoring it leaves the deleted glyph on screen.</remarks>
    public void DeleteCharacters(int count)
    {
        var n = Math.Clamp(count, 1, Columns - CursorColumn);
        var rowStart = CursorRow * Columns;
        for (var column = CursorColumn; column < Columns - n; column++)
        {
            _cells[rowStart + column] = _cells[rowStart + column + n];
        }

        for (var column = Columns - n; column < Columns; column++)
        {
            _cells[rowStart + column] = Erased();
        }

        IsDirty = true;
    }

    /// <summary>Resizes the grid, keeping the content that still fits.</summary>
    /// <remarks>
    /// Content is preserved by position rather than reflowed. Reflowing is what a user expects when
    /// narrowing a window over wrapped prose, and it needs a record of which line breaks were
    /// *wrapped* versus *written* — which this model does not keep, and inventing it here would be
    /// guessing at where text belongs.
    /// simplify: truncate rather than reflow; ceiling is a resize losing off-screen content;
    /// upgrade trigger = the model gains wrapped-line provenance.
    /// </remarks>
    public void Resize(int columns, int rows)
    {
        ArgumentOutOfRangeException.ThrowIfLessThan(columns, 1);
        ArgumentOutOfRangeException.ThrowIfLessThan(rows, 1);

        if (columns == Columns && rows == Rows)
        {
            return;
        }

        var replacement = NewGrid(columns, rows, TerminalCell.Blank);

        for (var row = 0; row < Math.Min(rows, Rows); row++)
        {
            for (var column = 0; column < Math.Min(columns, Columns); column++)
            {
                replacement[(row * columns) + column] = _cells[(row * Columns) + column];
            }
        }

        _cells = replacement;
        Columns = columns;
        Rows = rows;

        CursorRow = Math.Clamp(CursorRow, 0, rows - 1);
        CursorColumn = Math.Clamp(CursorColumn, 0, columns - 1);
        IsDirty = true;
    }

    private void ScrollUp()
    {
        Array.Copy(_cells, Columns, _cells, 0, (Rows - 1) * Columns);

        for (var column = 0; column < Columns; column++)
        {
            _cells[((Rows - 1) * Columns) + column] = Erased();
        }
    }

    private void FillRows(int from, int to)
    {
        for (var row = Math.Max(from, 0); row <= Math.Min(to, Rows - 1); row++)
        {
            for (var column = 0; column < Columns; column++)
            {
                _cells[(row * Columns) + column] = Erased();
            }
        }
    }

    /// <summary>
    /// A blank cell in the <i>current</i> background, which is how full-screen programs paint.
    /// </summary>
    /// <remarks>
    /// Erasing to the default background instead would make "set a background, clear the screen" —
    /// the first thing every full-screen tool does — paint nothing.
    /// </remarks>
    private TerminalCell Erased() =>
        new(' ', TerminalColor.Default, Pen.Background, CellAttributes.None);

    private static TerminalCell[] NewGrid(int columns, int rows, TerminalCell fill)
    {
        var cells = new TerminalCell[columns * rows];
        Array.Fill(cells, fill);
        return cells;
    }
}
