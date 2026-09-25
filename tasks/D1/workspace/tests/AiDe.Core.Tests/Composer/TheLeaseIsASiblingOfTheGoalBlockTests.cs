using AiDe.Core.AgentPlane;
using AiDe.Core.Presentation.Composer;

namespace AiDe.Core.Tests.Composer;

/// <summary>
/// Ruling 42 and Security <b>C17</b>: the lease is a <b>sibling</b> of the goal block, it is derived
/// rather than typed, it is never empty and never covers everything.
/// </summary>
/// <remarks>
/// <b>The oracle is C17's, not a string match.</b> Comparing against the literal pattern would pass
/// for every other spelling of "everything"; the universal-lease detector cannot be spelled around.
/// </remarks>
public sealed class TheLeaseIsASiblingOfTheGoalBlockTests
{
    [Fact]
    public void TheGoalBlockNamesExactlySixFieldsAndNoneOfThemIsALease()
    {
        Assert.Equal(6, GoalBlockFields.All.Count);
        Assert.DoesNotContain(GoalBlockFields.All, f => f.Contains("lease", StringComparison.OrdinalIgnoreCase));

        // And the composer's own goal-block shape carries no lease member either.
        Assert.DoesNotContain(
            typeof(GoalBlock).GetProperties(),
            p => p.Name.Contains("Lease", StringComparison.OrdinalIgnoreCase));
    }

    [Theory]
    [InlineData("**")]
    [InlineData("**/*")]
    [InlineData("**/**")]
    [InlineData("/**")]
    public void NoSpellingOfEverythingSurvivesTheUniversalLeaseDetector(string everything)
    {
        // The oracle itself, held against the thing it exists to catch: each of these leases DOES
        // cover the probe path, which is why the detector is the control and a comparison against the
        // literal `**` is not.
        Assert.True(new Lease([everything]).Covers(LeaseDerivation.UncoveredProbePath));
    }

    [Fact]
    public void ADerivedLeaseNeverCoversEverything()
    {
        foreach (var draft in new[]
                 {
                     "work on @src/Payments/ and @docs/plan.md",
                     "@src @docs @tests",
                     "@./src/Foo.cs and @/src/Bar.cs",
                     "look at @src/A.cs, @src/A.cs and @src/A.cs",
                 })
        {
            var lease = LeaseDerivation.Derive(draft);

            Assert.False(
                lease.Covers(LeaseDerivation.UncoveredProbePath),
                $"the lease derived from '{draft}' covers everything, so no edit could ever raise a seam");
            Assert.NotEmpty(lease.Exclusive);
        }
    }

    [Fact]
    public void ADirectoryMentionBecomesADirectoryScopeAndAFileMentionStaysAFile()
    {
        var patterns = LeaseDerivation.Patterns("edit @src/Payments and @docs/plan.md and @tests/");

        Assert.Equal(["src/Payments/**", "docs/plan.md", "tests/**"], patterns);

        var lease = new Lease(patterns);
        Assert.True(lease.Covers("src/Payments/Aggregate.cs"));
        Assert.True(lease.Covers("docs/plan.md"));
        Assert.False(lease.Covers("src/Ordering/Order.cs"));
        Assert.False(lease.Covers("docs/other.md"));
    }

    [Fact]
    public void AMentionThatIsNotAPathIsDroppedRatherThanWidened()
    {
        // A wildcard or a traversal in a mention is the one-convenience-at-a-time route to universal.
        Assert.Empty(LeaseDerivation.Patterns("ask @** to do it"));
        Assert.Empty(LeaseDerivation.Patterns("check @../outside/thing.md"));
        Assert.Empty(LeaseDerivation.Patterns("mention @src/*.cs"));
    }

    [Fact]
    public void NothingDerivableRaisesTheLeasesOwnRefusalRatherThanReturningADefault()
    {
        Assert.Empty(LeaseDerivation.Patterns("a prompt that names nothing at all"));

        // THE EXCEPTION FAILING CLOSED IS THE CONTROL. A caller that caught this into a default lease
        // would hand the run a scope that never seams, which is the case LeaseAndSeams refuses.
        var error = Assert.Throws<ArgumentException>(
            () => LeaseDerivation.Derive("a prompt that names nothing at all"));

        Assert.Contains("not a lease", error.Message, StringComparison.Ordinal);
    }

    [Fact]
    public void AnEmptyLeaseIsRefusedByTheTypeItself()
    {
        Assert.Throws<ArgumentException>(() => new Lease([]));
        Assert.Throws<ArgumentException>(() => new Lease(["   "]));
    }

    [Fact]
    public void TheDerivationIsDeterministicAndKeepsFirstAppearanceOrder()
    {
        const string Draft = "@docs/b.md then @src/a and @docs/b.md again, plus @src/a";

        var first = LeaseDerivation.Patterns(Draft);
        Assert.Equal(["docs/b.md", "src/a/**"], first);

        for (var i = 0; i < 10; i++)
        {
            Assert.Equal(first, LeaseDerivation.Patterns(Draft));
        }
    }

    [Fact]
    public void NoOperatorTypedLeaseEditorExistsAnywhereInTheComposer()
    {
        // Refusal (d). The only way a lease comes into being is the derivation above; nothing takes a
        // pattern list from a person.
        var derivation = typeof(LeaseDerivation).GetMethods()
            .Where(m => m.IsPublic && m.DeclaringType == typeof(LeaseDerivation))
            .ToList();

        Assert.All(derivation, m => Assert.All(
            m.GetParameters(),
            p => Assert.Equal(typeof(string), p.ParameterType)));
    }
}
