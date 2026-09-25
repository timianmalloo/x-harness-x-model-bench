using AiDe.Core.Workbench;

namespace AiDe.Core.Tests.Workbench;

/// <summary>
/// ADR-0030 rule 1 / falsifying test 1 <b>as amended by Ruling 84</b>: the Perspective set is a
/// closed Core row set — four rows in the order Coding · Explore · Architecture · Coordination, each
/// with a body, a bound single-stroke gesture spelled from its rail digit, and a catalog command
/// derived from the row — and the routing order for an inadmissible kind-open is
/// Architecture · Coding · Coordination.
/// </summary>
/// <remarks>
/// These are data invariants, so each was seen red by MUTATION before it was trusted (the record,
/// with the mutation ids, is <c>docs/proof/perspective-registry.md</c>): a row appended; the
/// Explore row given a <c>DockHost</c> body; a perspective's command filtered out of the catalog's
/// derivation; the routing order reversed. Ruling 84's fourth row was seen red the ordinary way —
/// this test asserted four rows against the three-row set (<c>docs/proof/coordination-perspective.md</c>).
/// </remarks>
public sealed class PerspectiveSetTests
{
    // US-C1 as amended (Ruling 84): exactly four, in rail order, each with a bound single-stroke
    // gesture spelled from its Order and carried by its catalog command; a FIFTH entry is the
    // falsifier. Tests is reserved with no row (Ruling 54).
    [Fact]
    public void All_HasExactlyFourRows_CodingExploreArchitectureCoordination_EachWithABoundGesture()
    {
        Assert.Equal(["coding", "explore", "architecture", "coordination"], PerspectiveSet.All.Select(p => p.Id));
        Assert.Equal(["Coding", "Explore", "Architecture", "Coordination"], PerspectiveSet.All.Select(p => p.Title));
        Assert.Equal([1, 2, 3, 4], PerspectiveSet.All.Select(p => p.Order));
        Assert.Equal(["Ctrl+1", "Ctrl+2", "Ctrl+3", "Ctrl+4"], PerspectiveSet.All.Select(p => p.Gesture));
        Assert.DoesNotContain(PerspectiveSet.All, p => p.Id.Contains("test", StringComparison.OrdinalIgnoreCase));
        Assert.Same(PerspectiveSet.Coding, PerspectiveSet.Initial);

        foreach (var perspective in PerspectiveSet.All)
        {
            // The gesture is bound, not merely printed: the catalog row derived from this one carries
            // it verbatim, and `KeyGestures.For` (App) binds Ctrl+<Order> from the same digit — the
            // rail's tooltip test reads that side.
            var command = Assert.Single(WorkbenchCommandCatalog.All, c => c.Id == perspective.CommandId);
            Assert.Equal($"Ctrl+{perspective.Order}", command.Gesture);
        }

        Assert.Equal("perspective.coordination", PerspectiveSet.All[3].CommandId);
        Assert.Equal(PerspectiveBody.DockHost, PerspectiveSet.All[3].Body);
    }

    // Ruling 52d / Ruling 84: Explore's body is one full-window surface; Coding, Architecture and
    // Coordination are hosts.
    [Fact]
    public void TheBodiesAreThreeHostsAndOneFullWindowSurface()
    {
        Assert.Equal(PerspectiveBody.DockHost, PerspectiveSet.Coding.Body);
        Assert.Equal(PerspectiveBody.FullWindow, PerspectiveSet.Explore.Body);
        Assert.Equal(PerspectiveBody.DockHost, PerspectiveSet.Architecture.Body);
        Assert.Equal(PerspectiveBody.DockHost, PerspectiveSet.All.Single(p => p.Id == "coordination").Body);
    }

    // ADR-0030 rule 1: the three perspective commands are DERIVED into the catalog from the rows, so
    // the catalog cannot list a perspective the set lacks — and `shell.toggleExplorer` is gone.
    [Fact]
    public void EveryRowHasACatalogCommand_DerivedFromIt_AndTheToggleIsGone()
    {
        foreach (var perspective in PerspectiveSet.All)
        {
            var command = Assert.Single(WorkbenchCommandCatalog.All, c => c.Id == perspective.CommandId);

            Assert.EndsWith(" perspective", command.Title, StringComparison.Ordinal);   // the accessible name ends in "perspective" (US-C1)
            Assert.Equal("_View", command.Menu);                                        // the View menu's radio group (§B3 rule 1)
            Assert.Equal(CommandScope.Global, command.Scope);                 // offered in every perspective
            Assert.Same(perspective, PerspectiveSet.ByCommandId(command.Id));
        }

        Assert.Equal(
            PerspectiveSet.All.Count,
            WorkbenchCommandCatalog.All.Count(c => c.Id.StartsWith("perspective.", StringComparison.Ordinal)));
        Assert.DoesNotContain(WorkbenchCommandCatalog.All, c => c.Id == "shell.toggleExplorer");
    }

    // US-C10: Ctrl+1/2/3/4 (D1's decision; Ruling 84's fourth), spelled from the rail digit so the
    // string and the binding cannot disagree; no other catalog command announces a digit gesture.
    [Fact]
    public void ThePerspectiveGesturesAreCtrlPlusTheRailDigit_AndNothingElseUsesThem()
    {
        Assert.Equal(["Ctrl+1", "Ctrl+2", "Ctrl+3", "Ctrl+4"], PerspectiveSet.All.Select(p => p.Gesture));

        var digitGestures = WorkbenchCommandCatalog.All
            .Where(c => c.Gesture.Length == 6 && c.Gesture.StartsWith("Ctrl+", StringComparison.Ordinal) && char.IsDigit(c.Gesture[^1]))
            .Select(c => c.Id)
            .ToList();

        Assert.Equal(PerspectiveSet.All.Select(p => p.CommandId), digitGestures);
    }

    // US-C3: the reading host wins a shared kind, so Architecture is tried before Coding; Explore is
    // never a routing target (it admits no docked kind). Coordination is a routing target too
    // (Ruling 84: the drop report names it, a Loomkeeper open from Coding lands there); it shares
    // no kind with either, so it is appended and the two existing positions are unchanged.
    [Fact]
    public void TheRoutingOrderIsArchitectureThenCodingThenCoordination()
    {
        Assert.Equal(["architecture", "coding", "coordination"], PerspectiveSet.RoutingOrder.Select(p => p.Id));
        Assert.DoesNotContain(PerspectiveSet.Explore, PerspectiveSet.RoutingOrder);
        Assert.All(PerspectiveSet.RoutingOrder, p => Assert.Equal(PerspectiveBody.DockHost, p.Body));
    }

    [Fact]
    public void TheCommandLookupReturnsNullForAnUnknownId_NotAThrowOrADefault()
    {
        Assert.Null(PerspectiveSet.ByCommandId("perspective.tests"));
        Assert.Null(PerspectiveSet.ByCommandId(string.Empty));
        Assert.Same(PerspectiveSet.Architecture, PerspectiveSet.ByCommandId("perspective.architecture"));
    }
}
