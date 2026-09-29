using AiDe.Core.Projections;

namespace AiDe.Core.Tests;

// The class-diagram surface fills each type's UML member compartment from
// DescribeResult.Members (attributes + operations) and shows the real declared
// count via MembersDeclared. These pin that extraction.
public sealed class ClassMemberProjectionTests
{
    [Fact]
    public void Describe_ReturnsATypesDeclaredMembers_ForTheClassDiagramCompartment()
    {
        using var ws = TestWorkspace.Create();
        ws.CommitSnapshot(
            "fixture", 1, "rev-1",
            TestWorkspace.Assertion("Shop.Order", "has_type", "class"),
            TestWorkspace.Assertion("Shop.Order", "has_member", "+ Id : int"),
            TestWorkspace.Assertion("Shop.Order", "has_member", "# Describe(int) : string"),
            TestWorkspace.Assertion("Shop.Order", "depends_on", "Shop.Customer"));

        var projections = new ProjectionService(ws.Store);
        var described = projections.Describe("Shop.Order", 10);

        Assert.NotNull(described.Members);
        Assert.Contains("+ Id : int", described.Members!);
        Assert.Contains("# Describe(int) : string", described.Members!);
        Assert.Equal(2, described.MembersDeclared);
    }

    [Fact]
    public void Describe_ReportsTheRealDeclaredCount_WhenTheExtractorTruncatedMembers()
    {
        using var ws = TestWorkspace.Create();
        ws.CommitSnapshot(
            "fixture", 1, "rev-1",
            TestWorkspace.Assertion("Shop.Big", "has_type", "class"),
            TestWorkspace.Assertion("Shop.Big", "has_member", "+ First : int"),
            TestWorkspace.Assertion("Shop.Big", "members_truncated", "68"));

        var projections = new ProjectionService(ws.Store);
        var described = projections.Describe("Shop.Big", 10);

        Assert.Single(described.Members!);
        Assert.Equal(68, described.MembersDeclared); // the declared total, not the read count
    }

    [Fact]
    public void Describe_ReturnsNoMembers_ForATypeThatDeclaresNone()
    {
        using var ws = TestWorkspace.Create();
        ws.CommitSnapshot(
            "fixture", 1, "rev-1",
            TestWorkspace.Assertion("Shop.Marker", "has_type", "interface"),
            TestWorkspace.Assertion("Shop.Marker", "depends_on", "Shop.Order"));

        var projections = new ProjectionService(ws.Store);
        var described = projections.Describe("Shop.Marker", 10);

        Assert.Empty(described.Members ?? System.Array.Empty<string>());
        Assert.Equal(0, described.MembersDeclared);
    }
}

