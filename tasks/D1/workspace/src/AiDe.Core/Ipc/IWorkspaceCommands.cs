namespace AiDe.Core.Ipc;

/// <summary>
/// The workspace's write surface, however it is reached.
/// </summary>
/// <remarks>
/// <para><b>Separate from <see cref="Projections.IWorkspaceQueries"/> because reads and writes are
/// not the same kind of thing.</b> A read can be repeated freely; a write bumps a generation and
/// commits a snapshot, carries an idempotency key, and is judged against the epoch fence. Folding
/// them into one interface would put a name on the seam ("queries") that half its members
/// contradict, and would make every read-only consumer hold a handle that can also mutate.</para>
///
/// <para>Both hosting modes satisfy it — the in-process core and the daemon client — for the same
/// reason the read seam exists: ADR-0009 keeps both, and a UI written against one of them is a UI
/// that has to be rewritten to get the other.</para>
/// </remarks>
public interface IWorkspaceCommands
{
    /// <summary>Re-indexes a scope and reports how it went.</summary>
    Task<ScopeRefreshStatus> RefreshScopeAsync(
        string scopeId, string artifactRevision, CancellationToken cancellationToken);

    /// <summary>
    /// Discovers and indexes every C# scope in the workspace — one per (project, target framework).
    /// </summary>
    /// <remarks>
    /// Awaited on the wire rather than started-and-polled, unlike scope refresh: indexing a
    /// repository is the user pressing a button and waiting for a graph, and its own per-scope
    /// budget already bounds how long it can take.
    /// </remarks>
    /// <param name="force">Re-extract every scope even when its inputs are unchanged.</param>
    Task<IndexSummary> IndexSolutionAsync(
        string artifactRevision, CancellationToken cancellationToken, bool force = false);
}

/// <summary>What an index run found, as the shell reports it.</summary>
public sealed record IndexSummary(
    int ScopesFound,
    int ScopesIndexed,
    int Assertions,
    IReadOnlyList<string> Failed,
    IReadOnlyList<string> Disclosures,
    string? Contexts = null,
    int ScopesReused = 0)
{
    /// <summary>One sentence for the announcement channel, including what was NOT seen.</summary>
    public string Describe()
    {
        if (ScopesFound == 0)
        {
            // Even with nothing to index, what was NOT read is the whole answer. A repository full
            // of Python reported "no projects found" and said nothing about the Python.
            var nothing = "No C# projects, Bicep templates or EF migrations found in this workspace.";
            return Disclosures.Count > 0 ? nothing + " " + NotAnalysed() : nothing;
        }

        var text = $"Indexed {ScopesIndexed} of {ScopesFound} scope(s): {Assertions:N0} assertion(s).";

        // Reuse is said out loud. "Indexed 0 of 7" with nothing else would read as a failure, and
        // "7 of 7" would be a true sentence about a run that read nothing — the operator's question
        // after a surprising graph is always whether it actually looked.
        if (ScopesReused > 0)
        {
            text += $" {ScopesReused} scope(s) were unchanged and reused; " +
                    "use Re-index everything to read them again.";
        }
        if (Failed.Count > 0) text += $" {Failed.Count} scope(s) failed and were quarantined.";

        // Disclosures are part of the result, not a footnote — but the STATUS LINE is not where they
        // belong. See NotAnalysed.
        if (Disclosures.Count > 0) text += " " + NotAnalysed();

        // Coverage is reported alongside the count, so "we have contexts" cannot quietly mean
        // "we have contexts for a fraction of the code" (ADR-0016).
        if (!string.IsNullOrWhiteSpace(Contexts)) text += " " + Contexts;
        return text;
    }

    /// <summary>
    /// What was not analysed, as ONE clause — a count and the sharpest example, never the list.
    /// </summary>
    /// <remarks>
    /// <para><b>The status line is a line.</b> This clause used to be every disclosure joined with
    /// commas. Folding them by class took it from 108 to 28, which is a better list and still not a
    /// status message: on a real index it filled roughly four fifths of the window and pushed the
    /// graph into a strip along the top.</para>
    ///
    /// <para><b>Which one to name is the whole design.</b> A count alone ("28 boundaries") tells a
    /// reader nothing about whether to care. So the clause names the disclosure with the largest
    /// count, which is where the most unread repository is — and, because gaps sort before
    /// boundaries when counts tie, prefers a thing the product MEANT to read and could not over a
    /// thing it never intended to read (DC-050).</para>
    ///
    /// <para>The full list is still in the result, unchanged, for a surface that can hold it.</para>
    /// </remarks>
    public string NotAnalysed()
    {
        var folded = Facts.DisclosureSummary.Fold(Disclosures);

        if (folded.Count == 0) return string.Empty;

        // A GAP first, whatever its size, then the largest boundary. A defect somebody can fix
        // outranks the biggest thing the product was never going to read — which is the ordering the
        // register argues for and the status line had backwards.
        var headline = folded
            .OrderBy(d => Facts.DisclosureKinds.KindOf(d) == Facts.DisclosureKind.Gap ? 0 : 1)
            .ThenByDescending(Facts.DisclosureSummary.CountIn)
            .ThenBy(d => d, StringComparer.Ordinal)
            .First();

        var name = headline.Split(' ')[0];

        var gaps = folded.Count(d => Facts.DisclosureKinds.KindOf(d) == Facts.DisclosureKind.Gap);

        if (folded.Count == 1) return $"Not analysed: {name}.";

        // The count that earns the words is the number of GAPS. "27 other boundaries" is a fact
        // about the product; "3 gaps" is a fact about this repository, and only one of them is a
        // reason to open the panel.
        // The GESTURE, not just the name of a place. "See Diagnostics" is an instruction a reader
        // cannot follow without going to look for it; the chord is the difference between a pointer
        // and a direction. Read from the catalog rather than typed here, so a rebinding cannot leave
        // this sentence describing a key that does nothing.
        var how = Workbench.WorkbenchCommandCatalog.All
            .FirstOrDefault(c => c.Id == "workspace.diagnostics") is { Gesture.Length: > 0 } command
                ? $" ({command.Gesture})"
                : string.Empty;

        return gaps > 0
            ? $"Not analysed: {name} — {gaps} gap(s) and {folded.Count - gaps} boundar" +
              $"{(folded.Count - gaps == 1 ? "y" : "ies")}. See Diagnostics{how}."
            : $"Not analysed: {name} and {folded.Count - 1} other boundar" +
              $"{(folded.Count == 2 ? "y" : "ies")} — see Diagnostics{how}.";
    }
}

/// <summary>The write surface applied by a core in this process.</summary>
/// <remarks>
/// Takes the refresh as a delegate rather than a <see cref="WorkspaceCore"/> so that what the
/// in-process mode reports — a completed count, or a failure with its reason — is decided in one
/// place and testable without a store.
/// </remarks>
public sealed class LocalWorkspaceCommands(
    Func<string, string, CancellationToken, Task<int>> refresh,
    Func<string, bool, CancellationToken, Task<IndexSummary>>? index = null)
    : IWorkspaceCommands
{
    /// <inheritdoc />
    public Task<IndexSummary> IndexSolutionAsync(
        string artifactRevision, CancellationToken cancellationToken, bool force = false) =>
        index is null
            ? Task.FromResult(new IndexSummary(0, 0, 0, [], []))
            : index(artifactRevision, force, cancellationToken);

    public async Task<ScopeRefreshStatus> RefreshScopeAsync(
        string scopeId, string artifactRevision, CancellationToken cancellationToken)
    {
        // The command id is synthesised here because in-process there is no retry to deduplicate:
        // the caller and the work share a stack frame, so a lost reply is not a thing that can
        // happen. Across the boundary it is the idempotency key and it matters a great deal.
        var commandId = Guid.NewGuid().ToString("N");

        try
        {
            var count = await refresh(scopeId, artifactRevision, cancellationToken).ConfigureAwait(false);
            return new ScopeRefreshStatus(
                commandId, scopeId, ScopeRefreshState.Completed, count, null);
        }
        catch (Exception ex) when (ex is not OperationCanceledException)
        {
            // Reported, not thrown, so both hosting modes hand a caller the same shape. Across the
            // boundary a failure arrives as a status; if it arrived here as an exception, every
            // caller would need two ways to learn the same fact.
            return new ScopeRefreshStatus(
                commandId, scopeId, ScopeRefreshState.Failed, 0, ex.Message);
        }
    }
}
