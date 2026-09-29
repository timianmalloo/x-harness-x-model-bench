using System.Reflection;
using AiDe.Core.Presentation;
using AiDe.Core.Projections;

namespace AiDe.Core.Tests;

/// <summary>
/// A field Core measures must reach the client record, or be listed as deliberately dropped.
/// </summary>
/// <remarks>
/// <para><b>The third way to lose the truth.</b> Two were already known: the bound was dropped (a
/// surface renders the payload and not its <c>Truncated</c>), and the payload was never asked for
/// (DC-073 — a stand-in rendered while the real query sat uncalled). This is the third: <b>the field
/// was dropped in transit</b>, between a producer record and the client record built from it.</para>
///
/// <para><b>The instance.</b> <c>GraphNode</c> was widened with an authoritative <c>IsKnowledge</c>
/// precisely to end the Knowledge chip reading 0 — <c>node_kind</c> is the one dimension that
/// separates knowledge from source, because <c>has_type</c> is emitted by six extractors and says
/// nothing about which half of the graph a node is in (INV-0004). The flag was then dropped where
/// <c>CanvasNode</c> is built, so the page fell back to guessing from a fixed list of spellings —
/// <c>knowledge|doc|adr|design|note|proof</c> — which cannot match a repository whose knowledge
/// kinds are <c>spec</c>, <c>investigation</c> and <c>glossary</c>. The chip read 0 again, by a
/// third mechanism, after being fixed twice.</para>
///
/// <para><b>Why the other controls could not catch it.</b> A behavioural harness that hands a
/// payload to a surface and reads the rendered tree passes here: the surface faithfully rendered
/// everything it was given, and the loss happened one boundary upstream. Each of the three failures
/// hides from the others' test, which is why there are three controls and not one.</para>
///
/// <para><b>Not a ban — a list where the unasked question gets asked.</b> Some fields genuinely
/// should not cross: <c>Degree</c> is a graph statistic the canvas does not draw. Naming one costs a
/// line; leaving one unnamed costs a flag nobody notices is missing.</para>
/// </remarks>
public sealed class FieldsSurviveTheClientBoundaryTests
{
    /// <summary>A producer record, the client record built from it, and what may be dropped.</summary>
    private sealed record Boundary(
        Type Producer, Type Client, Dictionary<string, string> DeliberatelyDropped);

    private static readonly Boundary[] Boundaries =
    [
        new(typeof(GraphNode), typeof(CanvasNode), new()
        {
            ["Degree"] =
                "A graph statistic used to rank what to keep, not to draw. The canvas sizes by "
                + "Count, which is the number of nodes a group stands for.",
            ["IsExternal"] =
                "Reaches the canvas as part of Kind (`group-external`) rather than as its own "
                + "field, because the page colours by kind.",
        }),

        // WIDENED 2026-09-01, deliberately, after the design session found its own guard reporting
        // clean over a namespace it was not scanning — R4 one layer up. The way they found it was by
        // widening the scope and watching it go red, not by reasoning about whether it was complete.
        // This list had exactly one pair, hand-written by me, and "the pairs I thought of" is the
        // same shape of blind spot.
        new(typeof(GraphEdge), typeof(CanvasEdge), new()
        {
            // GraphEdge.Status is VerificationStatus; CanvasEdge.Status is its string form. The name
            // survives, so the check passes on it — worth saying out loud that this control compares
            // NAMES and would not have noticed a type change that lost meaning.
        }),

        // WIDENED AGAIN 2026-09-01. The list held the three NODE-level pairs and not the container
        // pair, so `WorkspaceGraph.KnowledgeDeclared` — added the same hour, precisely so a surface
        // could show a denominator — crossed nothing and this control said nothing. A hand-listed
        // set is the hole it exists to catch, and it caught me twice in one day.
        new(typeof(WorkspaceGraph), typeof(CanvasGraph), new()
        {
            // Nodes and Edges keep their NAMES across the boundary (the element type changes, which
            // this control cannot see — that is what the element-level pairs below are for). Listing
            // them as dropped was wrong, and the stale-allowance test said so.
            ["SourceRevision"] =
                "The canvas draws what it was given and does not display a revision. Recorded rather "
                + "than carried, so the decision is visible if a surface ever needs it.",
        }),

        // FOUND BY THE ENUMERATION, 2026-09-01. Five client records were paired with nothing, so no
        // assertion here could see a field dropped on the way into them.
        new(typeof(FindMatch), typeof(Presentation.EvidenceRow), new()
        {
            ["MatchedOn"] =
                "Folded into Evidence: the row carries the reason only when the match was NOT on the "
                + "id, so the kind is implied by the field's presence.",
            ["Authorship"] =
                "Every match is a repository artifact today; the pane has no agent-authored rows to "
                + "distinguish. Revisit when agents can write.",
        }),

        new(typeof(GraphCluster), typeof(CanvasNode), new()
        {
            ["NodeCount"] = "Crosses as CanvasNode.Count — renamed at the boundary, which is exactly "
                + "the rename this control cannot follow. Named here so the gap is recorded rather "
                + "than passing silently.",
            ["IsExternal"] = "Folded into Kind (`group-external`), as for GraphNode.",

            // FOUND BY THE WIDENING, and it is a decision rather than a defect — but it had never
            // been written down anywhere, which is the whole point of the list. The canvas sizes a
            // group by how many NODES it stands for, because that is the honesty claim
            // `CanvasNode.Count` exists to make: a dot standing for 240 types is only honest while
            // the 240 is on it. How densely those 240 are connected to each other is a different
            // and weaker claim, and drawing it would need a second visual channel the overview does
            // not have. Revisit if the overview ever gains one.
            ["InternalEdges"] = "The overview sizes a group by node count, not by internal density; "
                + "there is no second visual channel to carry it.",
        }),
    ];

    /// <summary>
    /// Client records that are deliberately not paired with a producer, and why.
    /// </summary>
    /// <remarks>
    /// The pair list is maintained by hand and cannot be derived — the mapping is not a naming rule
    /// (<c>GraphCluster</c> and <c>GraphNode</c> both become <c>CanvasNode</c>). What CAN be
    /// enumerated is the other half: every record on the client side. So the list nobody can derive
    /// is checked against a set nobody can forget, and "a client record I never listed" stops being
    /// possible. It is the compiler's trick — enumerate the space, force a decision on each — applied
    /// where there is no compiler.
    /// </remarks>
    private static readonly Dictionary<string, string> UnpairedClientRecords = new(StringComparer.Ordinal)
    {
        ["ConfidenceBadge"] = "A rendering of one assertion's status, not a projection of a record.",
        ["ProvenanceSection"] = "Groups EvidenceRow for display; carries no producer field of its own.",
        ["LivenessBadge"] = "Derived from a timestamp comparison, not carried across a boundary.",
        ["WatcherSessionSnapshot"] = "Assembled from several watcher queries; no single producer record.",
        ["WatcherSessionRow"] =
            "Built from WatcherSessionSnapshot, which is itself a client record — a client-to-client "
            + "projection, not a producer boundary.",
        ["WatcherBoardRow"] =
            "A display projection of BoardMessage owned by the watcher work. Pairing it means "
            + "writing that owner's reasons for a dozen dropped ids and keys, which is their "
            + "judgement rather than mine — named here so it is a known debt, not an oversight.",
        ["WatcherLeaderboardRow"] = "Same: a display projection of ScoredEpisode, same owner.",
        ["WatcherDaydreamRow"] =
            "A display projection of DaydreamCandidate, which is itself FOLDED from observations and "
            + "events rather than carried across a boundary — so there is no producer record whose "
            + "fields could be dropped on the way in. Every field here is either derived by "
            + "DaydreamFold (state, confidence, the block reason) or composed for reading (the "
            + "pattern label, the stage). The assertion that matters for this one is that the fold "
            + "is right, and that is DaydreamCandidateTests.",
        ["WorkspaceDiagnostics"] =
            "Assembled from environment probes (installed versions, incidents, MCP tools) rather "
            + "than projected from a producer record.",
    };

    [Fact]
    public void EveryClientRecordIsEitherPairedOrNamed()
    {
        // THE HALF THAT CAN BE ENUMERATED. The pairs cannot be derived; the client records can, and
        // an unlisted one is invisible to every assertion in this file. Nine of twelve were unlisted
        // when this was written — including the evidence and watcher rows, which is where bounds
        // live.
        var paired = Boundaries.Select(b => b.Client.Name).ToHashSet(StringComparer.Ordinal);

        var clientRecords = typeof(Presentation.CanvasNode).Assembly.GetTypes()
            .Where(t => t.Namespace == "AiDe.Core.Presentation" && t.IsSealed
                        && t.GetMethod("<Clone>$", BindingFlags.Public | BindingFlags.Instance) is not null)
            .Select(t => t.Name)
            .ToList();

        Assert.True(clientRecords.Count > 5,
            $"only {clientRecords.Count} client record(s) found — the finder has stopped seeing them "
            + "and this test would pass by looking at nothing");

        var unaccounted = clientRecords
            .Where(n => !paired.Contains(n) && !UnpairedClientRecords.ContainsKey(n))
            .Order(StringComparer.Ordinal)
            .ToList();

        Assert.True(unaccounted.Count == 0,
            "these client records are neither paired with a producer nor named as unpaired, so no "
            + "assertion in this file can see a field dropped on the way into them: "
            + string.Join(", ", unaccounted));
    }

    [Fact]
    public void NoRecordIsNamedUnpairedWhileAlsoBeingPaired()
    {
        // The stale-allowance rule, applied to this list too.
        var paired = Boundaries.Select(b => b.Client.Name).ToHashSet(StringComparer.Ordinal);

        var both = UnpairedClientRecords.Keys.Where(paired.Contains).Order(StringComparer.Ordinal);

        Assert.True(!both.Any(),
            "named as unpaired and also paired: " + string.Join(", ", both));
    }

    [Fact]
    public void EveryProducerFieldEitherCrossesOrIsNamed()
    {
        var problems = new List<string>();

        foreach (var boundary in Boundaries)
        {
            var client = Names(boundary.Client);

            foreach (var field in Names(boundary.Producer))
            {
                if (client.Contains(field)) continue;
                if (boundary.DeliberatelyDropped.ContainsKey(field)) continue;

                problems.Add(
                    $"{boundary.Producer.Name}.{field} does not reach {boundary.Client.Name} and is "
                    + "not listed as deliberately dropped. Carry it, or name it in "
                    + "DeliberatelyDropped with the reason — a field measured by Core and lost in "
                    + "transit is invisible, because everything downstream still renders.");
            }
        }

        Assert.True(problems.Count == 0, string.Join("\n", problems));
    }

    [Fact]
    public void NothingIsListedAsDroppedThatActuallyCrosses()
    {
        // A stale allowance is the same defect one level up: it keeps a question alive that nobody
        // has to answer any more, and makes the list longer than the thing it describes.
        var problems = new List<string>();

        foreach (var boundary in Boundaries)
        {
            var client = Names(boundary.Client);

            foreach (var named in boundary.DeliberatelyDropped.Keys)
            {
                if (client.Contains(named))
                {
                    problems.Add(
                        $"{boundary.Producer.Name}.{named} is listed as deliberately dropped but "
                        + $"{boundary.Client.Name} carries it — remove the entry.");
                }
            }
        }

        Assert.True(problems.Count == 0, string.Join("\n", problems));
    }

    [Fact]
    public void TheBoundariesAreRealRecordsWithFields()
    {
        // The DC-016 guard. If Names() stops finding properties — a record becomes a class, a type
        // is renamed — every assertion above passes by comparing two empty sets.
        foreach (var boundary in Boundaries)
        {
            Assert.True(Names(boundary.Producer).Count >= 3,
                $"{boundary.Producer.Name} yielded {Names(boundary.Producer).Count} field(s); this "
                + "test would pass by looking at nothing");

            Assert.True(Names(boundary.Client).Count >= 3,
                $"{boundary.Client.Name} yielded {Names(boundary.Client).Count} field(s)");
        }
    }

    /// <summary>The record's own properties, by name.</summary>
    private static HashSet<string> Names(Type type) =>
    [
        .. type.GetProperties(BindingFlags.Public | BindingFlags.Instance)
            .Where(p => p.Name != "EqualityContract")
            .Select(p => p.Name),
    ];
}
