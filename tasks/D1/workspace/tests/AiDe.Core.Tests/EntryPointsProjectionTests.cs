using System.Text.Json;
using AiDe.Core.Ipc;
using AiDe.Core.Projections;

namespace AiDe.Core.Tests;

/// <summary>UV-0 D-1 listing: has_type nodes as unclassified; never silent-drop.</summary>
public sealed class EntryPointsProjectionTests
{
    [Fact]
    public void Catalog_NamesEntryPointsDistinctFromSolutionTree()
    {
        Assert.Equal("entry-points", WorkspaceOperations.EntryPoints);
        Assert.NotEqual(WorkspaceOperations.SolutionTree, WorkspaceOperations.EntryPoints);
    }

    [Fact]
    public void QueryJson_HasOnlyMaxRowsOnTheWire()
    {
        var json = JsonSerializer.Serialize(new EntryPointsQuery(), WorkspaceOperations.Wire);
        Assert.Contains("maxRows", json, StringComparison.Ordinal);
        Assert.DoesNotContain("observation", json, StringComparison.OrdinalIgnoreCase);
    }

    [Fact]
    public void HasTypeNodes_AreUnclassified_NeverSilentDrop()
    {
        using var workspace = TestWorkspace.Create();
        workspace.CommitSnapshot(
            "fixture", 1, "rev-1",
            TestWorkspace.Assertion("Api.Orders", "has_type", "class"),
            TestWorkspace.Assertion("Cli.Program", "has_type", "class"));
        var projections = new ProjectionService(workspace.Store, Path.GetDirectoryName(workspace.DatabasePath)!);
        var result = projections.EntryPoints(new EntryPointsQuery());
        Assert.Equal(2, result.Rows.Count);
        Assert.Equal(EntryPointKind.Api, result.Rows.Single(r => r.NodeId == "Api.Orders").Kind);
        Assert.Equal(EntryPointKind.Cli, result.Rows.Single(r => r.NodeId == "Cli.Program").Kind);
        Assert.Null(result.Rows.Single(r => r.NodeId == "Api.Orders").UnclassifiedReason);
        Assert.Equal(0, result.OmittedByCap);
    }

    [Fact]
    public void Cap_DisclosesOmittedCount()
    {
        using var workspace = TestWorkspace.Create();
        workspace.CommitSnapshot(
            "fixture", 1, "rev-1",
            TestWorkspace.Assertion("A", "has_type", "class"),
            TestWorkspace.Assertion("B", "has_type", "class"));
        var projections = new ProjectionService(workspace.Store, Path.GetDirectoryName(workspace.DatabasePath)!);
        var capped = projections.EntryPoints(new EntryPointsQuery(MaxRows: 1));
        Assert.Single(capped.Rows);
        Assert.Equal(1, capped.OmittedByCap);
        Assert.Contains("Omitted", capped.Disclosures[0], StringComparison.Ordinal);
    }

    [Fact]
    public void KindFromDisplay_ApiUxCli_ElseUnclassified()
    {
        Assert.Equal(EntryPointKind.Api, EntryPointsListing.KindFromDisplay("Orders.OrdersController"));
        Assert.Equal(EntryPointKind.Cli, EntryPointsListing.KindFromDisplay("App.Program"));
        Assert.Equal(EntryPointKind.Cli, EntryPointsListing.KindFromDisplay("App.Program.Main"));
        Assert.Equal(EntryPointKind.Ux, EntryPointsListing.KindFromDisplay("Shell.MainWindow"));
        Assert.Equal(EntryPointKind.Unclassified, EntryPointsListing.KindFromDisplay("Domain.Order"));
    }

    [Fact]
    public void HasMember_MainIsCli_WithoutGraphNodeId()
    {
        using var workspace = TestWorkspace.Create();
        workspace.CommitSnapshot(
            "fixture", 1, "rev-1",
            TestWorkspace.Assertion("App.Program", "has_type", "class"),
            TestWorkspace.Assertion("App.Program", "has_member", "Main"));
        var projections = new ProjectionService(workspace.Store, Path.GetDirectoryName(workspace.DatabasePath)!);
        var result = projections.EntryPoints(new EntryPointsQuery());
        var main = Assert.Single(result.Rows, r => r.Display.EndsWith(".Main", StringComparison.Ordinal));
        Assert.Equal(EntryPointKind.Cli, main.Kind);
        Assert.Null(main.NodeId);
    }

    [Fact]
    public void Listing_DoesNotCarryE1ObservationIds()
    {
        var json = JsonSerializer.Serialize(
            new EntryPointRow(EntryPointKind.Unclassified, "T", "T", "classifier-not-admitted"),
            WorkspaceOperations.Wire);
        Assert.DoesNotContain("observation", json, StringComparison.OrdinalIgnoreCase);
        Assert.DoesNotContain("sequence", json, StringComparison.OrdinalIgnoreCase);
    }
}
