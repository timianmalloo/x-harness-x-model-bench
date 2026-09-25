using AiDe.Core.Facts;
using AiDe.Core.Projections;

namespace AiDe.Core.Presentation;

/// <summary>
/// The complete state set for the evidence surface. Loading, Empty and Error are first-class here
/// because they are the states the urge to complete skips — and an unavailable result rendered as a
/// clean empty one is the specific dishonesty this product exists to avoid.
/// </summary>
public enum PaneState
{
    Loading,
    Empty,
    Ready,
    Stale,
    Error,
}

/// <summary>
/// A confidence badge that never relies on colour. Glyph and text carry the meaning; colour is the
/// third signal, so the badge still reads correctly in high-contrast mode and for a colour-blind
/// operator (WCAG 2.2 AA, "not colour alone").
/// </summary>
public sealed record ConfidenceBadge(string Glyph, string Text, string TokenName)
{
    public static ConfidenceBadge For(VerificationStatus status) => status switch
    {
        VerificationStatus.Verified => new ConfidenceBadge("✓", "Verified", "colors.verified"),
        VerificationStatus.Inferred => new ConfidenceBadge("~", "Inferred", "colors.inferred"),
        _ => new ConfidenceBadge("?", "Unverified", "colors.unverified"),
    };

    /// <summary>
    /// The badge for a row whose confidence was never established.
    /// </summary>
    /// <remarks>
    /// <para><b>Not a <see cref="VerificationStatus"/>, deliberately.</b> The three statuses are
    /// claims the extractor made about an assertion. "The projection this row came from does not
    /// carry one" is a different kind of fact, and folding it into <c>Unverified</c> would state an
    /// extractor's finding that no extractor made.</para>
    ///
    /// <para>DESIGN.md's status language names this state: question glyph, the words <i>Not
    /// recorded</i>, <c>{colors.unverified}</c> — <i>"evidence is absent or untrustworthy"</i>. The
    /// design language's own third principle is that absence is a state and never renders as a
    /// clean success.</para>
    /// </remarks>
    public static ConfidenceBadge NotRecorded { get; } =
        new("?", "Not recorded", "colors.unverified");

    /// <summary>What a screen reader announces. Never just the colour name.</summary>
    public string AccessibleName => Text;
}

/// <summary>One row of the accessible evidence list — the permanent keyboard/screen-reader surface.</summary>
/// <param name="Evidence">
/// Why this row matched, when it matched on something other than its own identity — e.g.
/// <c>has_member = + addEventListener()</c>. Null when the id itself matched, where repeating it
/// would be noise.
/// </param>
/// <remarks>
/// The pane lists search results, and a search now matches attribute VALUES as well as identity. A
/// row that came back because one of its members matched is <b>correct</b> and reads as a wrong
/// result until it says so — the same defect fixed on the search surface, found here by enumerating
/// client records rather than by anybody noticing the pane.
/// </remarks>
public sealed record EvidenceRow(
    string NodeId,
    string DisplayLabel,
    string NodeKind,
    ConfidenceBadge Confidence,
    string? Evidence = null)
{
    /// <summary>The one line a list shows: the label, its kind, and why it matched.</summary>
    /// <remarks>
    /// Composed HERE rather than in the pane, so the visible text and the accessible name are built
    /// from the same fields and cannot drift apart — the chip's two rendering paths drifting is what
    /// made the same false claim twice in one surface.
    /// </remarks>
    public string ListLine => Evidence is null
        ? $"{DisplayLabel}  ·  {NodeKind}"
        : $"{DisplayLabel}  ·  {NodeKind}  ·  {Evidence}";

    public string AccessibleName => Evidence is null
        ? $"{DisplayLabel}, {NodeKind}, {Confidence.AccessibleName}"
        : $"{DisplayLabel}, {NodeKind}, matched on {Evidence}, {Confidence.AccessibleName}";
}

/// <summary>One section of the provenance pane, in the spec's fixed evidence order.</summary>
public sealed record ProvenanceSection(string Heading, IReadOnlyList<string> Lines);

/// <summary>
/// The Phase-1 evidence surface: a filterable list plus a provenance pane.
/// </summary>
/// <remarks>
/// This is not a fallback for a graph canvas — it is the accessibility equivalent the spec requires
/// to exist permanently, exposing the same selected-node identity, provenance, navigation actions and
/// result-limit state as the Phase-2 canvas will.
/// </remarks>
public sealed class EvidencePaneViewModel(IWorkspaceQueries queries)
{
    private IReadOnlyList<EvidenceRow> _allRows = [];

    public PaneState State { get; private set; } = PaneState.Loading;

    public IReadOnlyList<EvidenceRow> Rows { get; private set; } = [];

    public string? SelectedNodeId { get; private set; }

    public IReadOnlyList<ProvenanceSection> Provenance { get; private set; } = [];

    /// <summary>
    /// The selected row's provenance as ONE muted line for the row itself (Ruling 94): confidence ·
    /// origin · extractor and version · rev, one entry per distinct triple among the node's
    /// neighbours, or <c>not recorded</c> when it has none. Derived from the same
    /// <see cref="Provenance"/> section a full describe renders — one definition of the fields,
    /// two readers (DM7). Null until a row is selected.
    /// </summary>
    public string? SelectedDetailLine { get; private set; }

    /// <summary>The one string the operator reads when something is off. Always states evidence, never reassurance.</summary>
    public string StatusMessage { get; private set; } = "Loading evidence…";

    public string? SourceRevision { get; private set; }

    /// <summary>Announced through a live region, so state changes reach a screen reader without motion.</summary>
    public string LiveAnnouncement { get; private set; } = string.Empty;

    public async Task LoadAsync(string searchTerm = "", CancellationToken cancellationToken = default)
    {
        State = PaneState.Loading;
        StatusMessage = "Loading evidence…";

        try
        {
            // MaxSearchResultsCeiling, not MaxNeighborsCeiling. Fifty is the NEIGHBOUR bound — how
            // much of one node's neighbourhood a projection will return — and ProjectionService's
            // own remarks record this exact mistake being found and fixed, which is where
            // MaxSearchResultsCeiling came from. That sweep reached Contexts and Joins and missed
            // this pane, so the surface whose job is listing evidence stopped at fifty rows and
            // called it "50 item(s)".
            var result = await queries.FindAsync(
                searchTerm, ProjectionService.MaxSearchResultsCeiling, cancellationToken);
            SourceRevision = result.SourceRevision;

            _allRows = [.. result.Matches.Select(m => new EvidenceRow(
                m.NodeId, m.DisplayLabel, m.NodeKind,
                // NOT Verified. This read `ConfidenceBadge.For(VerificationStatus.Verified)` —
                // unconditional, for every row, in a product whose design language states by name
                // that an inferred edge rendered identically to an extracted one is
                // GRAPH-PROVENANCE-LAUNDERED. The badge is never drawn on this surface, so the
                // false claim survived only in the ACCESSIBLE NAME: a confidence invented for
                // screen-reader users and for nobody else.
                //
                // A search match carries no verification status — FindMatch has an Authorship
                // origin and no VerificationStatus — so the honest render is the absence. When the
                // query grows a real status, this becomes ConfidenceBadge.For(that status); until
                // then, synthesising one is the defect.
                ConfidenceBadge.NotRecorded,
                // Only when the match was NOT on the id — otherwise the row would repeat itself.
                m.MatchedOn == Store.NodeMatchKind.Attribute ? m.Evidence : null))];

            Rows = _allRows;

            if (Rows.Count == 0)
            {
                State = PaneState.Empty;
                StatusMessage = "No evidence yet — this workspace has no committed snapshot.";
            }
            else
            {
                State = PaneState.Ready;

                // A bounded read must never look complete. "20,000 results" and "≥ 20,000 results
                // (capped)" are different claims, and rendering them identically is the surface
                // inventing the completeness the read could not establish — the same failure class
                // as provenance laundering (DESIGN.md, the bounded-read rule).
                var capped = result.Bounds.OmittedNodes > 0 || result.Bounds.ByteCapped;

                StatusMessage = capped
                    ? $"≥ {Rows.Count} item(s) (capped) · rev {SourceRevision}"
                    : $"{Rows.Count} item(s) · rev {SourceRevision}";
            }
        }
        catch (Exception ex) when (ex is not OperationCanceledException)
        {
            // Degrade to an explicit failed state that keeps the last known rows visible; never
            // present an unreadable source as an empty success.
            State = PaneState.Error;
            StatusMessage = "Evidence unavailable — the workspace store could not be read.";
        }

        LiveAnnouncement = StatusMessage;
    }

    /// <summary>Marks the view stale without discarding it — the last successful revision still renders.</summary>
    public void MarkStale(string reason)
    {
        State = PaneState.Stale;
        StatusMessage = $"Graph is stale — {reason}. Viewing last successful snapshot.";
        LiveAnnouncement = StatusMessage;
    }

    public void Filter(string term)
    {
        Rows = string.IsNullOrWhiteSpace(term)
            ? _allRows
            : [.. _allRows.Where(r => r.DisplayLabel.Contains(term, StringComparison.OrdinalIgnoreCase))];

        if (Rows.Count == 0 && _allRows.Count > 0)
        {
            StatusMessage = $"No items match “{term}”.";
            LiveAnnouncement = StatusMessage;
        }
    }

    /// <summary>
    /// Selects a node and builds its provenance in the spec's fixed order:
    /// what it is → confidence/provenance → related nodes → source location → actions.
    /// </summary>
    public async Task SelectAsync(string nodeId, CancellationToken cancellationToken = default)
    {
        SelectedNodeId = nodeId;
        var describe = await queries.DescribeAsync(
            nodeId, ProjectionService.MaxNeighborsCeiling, cancellationToken);

        var sections = new List<ProvenanceSection>
        {
            new("What it is", [$"{describe.Node.DisplayLabel} ({describe.Node.NodeKind})"]),
        };

        ProvenanceSection confidence;
        if (describe.Neighbors.Count == 0)
        {
            confidence = new ProvenanceSection("Confidence and provenance", ["not recorded"]);
            sections.Add(confidence);
            sections.Add(new ProvenanceSection("Related nodes", ["No related evidence recorded."]));
            sections.Add(new ProvenanceSection("Source", ["not recorded"]));
        }
        else
        {
            // Base, not stamped: the stored revision carries the extractor generation (SourceRevision);
            // what a person is shown is the revision they named — the same rule the status line follows.
            confidence = new ProvenanceSection("Confidence and provenance",
                [.. describe.Neighbors.Select(n =>
                    $"{ConfidenceBadge.For(n.Status).Glyph} {ConfidenceBadge.For(n.Status).Text} · " +
                    $"{n.Origin} · {n.Provenance.ExtractorId} {n.Provenance.ExtractorVersion} · rev {Extraction.SourceRevision.Base(n.ArtifactRevision)}")]);
            sections.Add(confidence);

            sections.Add(new ProvenanceSection("Related nodes",
                [.. describe.Neighbors.Select(n => $"{n.Subject} —{n.Predicate}→ {n.Object}")]));

            sections.Add(new ProvenanceSection("Source",
                [.. describe.Neighbors
                    .Select(n => $"{n.Provenance.ArtifactPathId}:{n.Provenance.SourceLocation ?? "not recorded"}")
                    .Distinct(StringComparer.Ordinal)]));
        }

        // The limit state is part of the evidence, not a footnote: a truncated neighbourhood that
        // does not say so is indistinguishable from a complete one.
        if (describe.Bounds.OmittedEdges > 0 || describe.Bounds.ByteCapped)
        {
            sections.Add(new ProvenanceSection("Result limits",
                [$"Showing {describe.Bounds.ReturnedEdges} of " +
                 $"{describe.Bounds.ReturnedEdges + describe.Bounds.OmittedEdges} — " +
                 $"{describe.Bounds.OmittedEdges} omitted."]));
        }

        Provenance = sections;
        // The row's own line: the confidence section's distinct entries joined — read back from
        // the section, never composed a second time from the neighbours.
        SelectedDetailLine = string.Join(" ; ", confidence.Lines.Distinct(StringComparer.Ordinal));
        LiveAnnouncement = $"Selected {describe.Node.DisplayLabel}. {sections.Count} provenance sections.";
    }

    /// <summary>Empty-pane copy, shown before anything is selected — spec §C4, verbatim (US-C6).</summary>
    public static string EmptySelectionMessage => "Select an evidence row to see its provenance.";
}
