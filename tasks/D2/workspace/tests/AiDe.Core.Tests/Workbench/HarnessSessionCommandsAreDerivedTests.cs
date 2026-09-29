using AiDe.Core.Terminal;
using AiDe.Core.Workbench;

namespace AiDe.Core.Tests.Workbench;

/// <summary>
/// The "New … session" commands are derived from the readiness profiles, not listed beside them.
/// </summary>
/// <remarks>
/// <para><b>What this replaces.</b> A single <c>terminal.newAgent</c> opened whichever agent was
/// first on <c>PATH</c>. It could not report which harness it had started — and a session's harness
/// cannot be supplied afterwards, because a second coordination register for a known session
/// DISCARDS its attributes rather than merging them
/// (<c>CoordinationContractTests.Apply_DuplicateRegister_DiscardsTheSecondAttributes_ItDoesNotMerge</c>,
/// observed). So the harness must be known at launch, which is what choosing the entry supplies.</para>
///
/// <para><b>Why derived rather than listed.</b> The catalog, the menu and the controller all need to
/// agree about which harnesses exist. Three hand-maintained lists kept in step by memory is the
/// defect shape this repository has hit repeatedly; one source and three readers cannot drift.</para>
/// </remarks>
public sealed class HarnessSessionCommandsAreDerivedTests
{
    [Fact]
    public void EveryLaunchableProfileHasExactlyOneCommand()
    {
        var launchable = AgentReadinessProfiles.BuiltIn.All.Where(p => p.Launchable).ToList();

        // Not vacuous: if no profile were launchable, every assertion below would hold over nothing.
        Assert.NotEmpty(launchable);

        foreach (var profile in launchable)
        {
            var command = Assert.Single(
                WorkbenchCommandCatalog.All, c => c.Id == profile.CommandId);

            Assert.Contains(profile.DisplayName!, command.Title, StringComparison.Ordinal);
            Assert.Equal(profile.Gesture, command.Gesture);
            // Entry verbs live in File in every perspective (Addendum C US-C11; PS-M1).
            Assert.Equal("_File", command.Menu);
        }
    }

    [Fact]
    public void NoCommandExistsForAProfileThatCannotBeLaunched()
    {
        var launchableIds = AgentReadinessProfiles.BuiltIn.All
            .Where(p => p.Launchable)
            .Select(p => p.CommandId)
            .ToHashSet(StringComparer.Ordinal);

        var derived = WorkbenchCommandCatalog.All
            .Where(c => c.Id.StartsWith("terminal.new.", StringComparison.Ordinal))
            .Select(c => c.Id);

        Assert.All(derived, id => Assert.Contains(id, launchableIds));
    }

    /// <summary>
    /// The generic entry is gone, and gone from the catalog rather than only from the menu.
    /// </summary>
    /// <remarks>
    /// DC-068: a workbench command lives in three coupled places, and removing it from two leaves
    /// the menu and the palette disagreeing. This asserts the catalog, which is the one the palette
    /// reads; <c>MainMenuTests.TheMenuCoversEveryCatalogCommand</c> asserts the menu against it.
    /// </remarks>
    [Fact]
    public void TheGenericAgentTerminalCommandIsGone()
    {
        Assert.DoesNotContain(WorkbenchCommandCatalog.All, c => c.Id == "terminal.newAgent");
    }

    [Fact]
    public void EveryDerivedCommandDeclaresAGesture_BecauseTheCatalogRequiresOne()
    {
        var derived = WorkbenchCommandCatalog.All
            .Where(c => c.Id.StartsWith("terminal.new.", StringComparison.Ordinal))
            .ToList();

        Assert.NotEmpty(derived);
        Assert.All(derived, c => Assert.False(string.IsNullOrWhiteSpace(c.Gesture), c.Id));

        // Two harnesses must not share a chord: the second would be unreachable and the collision
        // is silent, since nothing about a duplicate gesture fails on its own.
        var gestures = derived.Select(c => c.Gesture).ToList();
        Assert.Equal(gestures.Count, gestures.Distinct(StringComparer.OrdinalIgnoreCase).Count());
    }
}
