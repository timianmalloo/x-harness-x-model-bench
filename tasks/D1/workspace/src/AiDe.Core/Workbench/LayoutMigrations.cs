namespace AiDe.Core.Workbench;

/// <summary>
/// One step up the schema ladder: transforms a layout written at <see cref="FromVersion"/> into the
/// shape the next version expects.
/// </summary>
/// <remarks>
/// Migrations operate on the **DTO**, not the domain model, deliberately. A migration's whole job is
/// to read a shape the current domain model can no longer represent; running it through today's
/// types would defeat the purpose, because those types are exactly what changed.
/// </remarks>
public sealed record LayoutMigration(int FromVersion, Func<LayoutDto, LayoutDto> Apply);

public static class LayoutMigrations
{
    /// <summary>
    /// The shipped migration chain.
    /// </summary>
    /// <remarks>
    /// <para>The mechanism shipped from day one, because a migration hook added after the first
    /// breaking change is added too late for every layout already on disk. Its first entry was a
    /// worked EXAMPLE — a rename that never happened in the product — which meant the chain looked
    /// exercised while doing nothing, and the first real release that added a surface reached
    /// existing users only if they knew to reset their layout. That example now lives in the test
    /// that documents it; this is the real chain.</para>
    /// </remarks>
    public static IReadOnlyList<LayoutMigration> Default { get; } =
    [
        // v1 → v2: the Joins pane was added. Without this, a saved layout simply does not contain it
        // and the feature is invisible to everyone who has ever arranged their workbench — the
        // people most likely to have opinions about it.
        new(1, dto => AddSurfaceBeside(dto, "contexts", new SurfaceDto("joins", "joins", "Joins"))),

        // v2 → v3: the Loomkeeper Board and Leaderboard panes were added beside Sessions. A saved
        // layout arranged before Loomkeeper shipped otherwise never shows them, so the watcher UX is
        // invisible to exactly the operators who arranged their workbench first.
        new(2, dto =>
            AddSurfaceBeside(
                AddSurfaceBeside(dto, "sessions", new SurfaceDto("board", "board", "Board")),
                "sessions",
                new SurfaceDto("leaderboard", "leaderboard", "Leaderboard"))),

        // v3 → v4: the Ledger pane was added beside the Leaderboard — the append-only record of every
        // work episode, the third watcher read after Board and Leaderboard. Same reason as v2→v3: a
        // layout arranged before it shipped otherwise never shows it.
        new(3, dto =>
            AddSurfaceBeside(dto, "leaderboard", new SurfaceDto("ledger", "ledger", "Ledger"))),
    ];

    /// <summary>
    /// Adds a surface into whichever stack already holds <paramref name="anchorSurfaceId"/>.
    /// </summary>
    /// <remarks>
    /// <para><b>Beside an anchor rather than at a fixed path.</b> The saved tree is the user's, not
    /// the default's: a stack id computed from the shipped layout may not exist in theirs at all.</para>
    ///
    /// <para><b>A missing anchor means the migration does nothing.</b> If the user closed the pane
    /// this one belongs beside, they have said something about that area of the workbench, and
    /// re-opening it under a new name is not an upgrade. A surface already present is left alone, so
    /// the step is safe to re-run.</para>
    /// </remarks>
    public static LayoutDto AddSurfaceBeside(LayoutDto dto, string anchorSurfaceId, SurfaceDto surface)
    {
        if (Contains(dto.Root, surface.SurfaceId) || dto.Floating.Any(f => Contains(f, surface.SurfaceId)))
        {
            return dto;
        }

        return new LayoutDto(
            AddIn(dto.Root, anchorSurfaceId, surface),
            [.. dto.Floating.Select(f => AddIn(f, anchorSurfaceId, surface))]);
    }

    private static bool Contains(NodeDto node, string surfaceId) =>
        (node.Surfaces ?? []).Any(s => s.SurfaceId == surfaceId)
        || (node.Children ?? []).Any(c => Contains(c, surfaceId));

    private static NodeDto AddIn(NodeDto node, string anchorSurfaceId, SurfaceDto surface)
    {
        if (node.Kind == "stack")
        {
            var surfaces = node.Surfaces ?? [];
            return surfaces.Any(s => s.SurfaceId == anchorSurfaceId)
                ? node with { Surfaces = [.. surfaces, surface] }
                : node;
        }

        return node with
        {
            Children = node.Children is null
                ? null
                : [.. node.Children.Select(c => AddIn(c, anchorSurfaceId, surface))],
        };
    }

    /// <summary>Rewrites one surface id throughout a layout, preserving its position and tab order.</summary>
    public static LayoutDto RenameSurface(LayoutDto dto, string oldId, string newId) =>
        new(RenameIn(dto.Root, oldId, newId),
            [.. dto.Floating.Select(f => RenameIn(f, oldId, newId))]);

    private static NodeDto RenameIn(NodeDto node, string oldId, string newId) => node with
    {
        Children = node.Children is null ? null : [.. node.Children.Select(c => RenameIn(c, oldId, newId))],
        Surfaces = node.Surfaces is null
            ? null
            : [.. node.Surfaces.Select(s => s.SurfaceId == oldId ? s with { SurfaceId = newId } : s)],
    };

    /// <summary>Drops a surface the current release no longer ships, healing the tree around it.</summary>
    public static LayoutDto RemoveSurface(LayoutDto dto, string surfaceId) =>
        new(RemoveIn(dto.Root, surfaceId) ?? dto.Root,
            [.. dto.Floating.Select(f => RemoveIn(f, surfaceId)).OfType<NodeDto>()]);

    private static NodeDto? RemoveIn(NodeDto node, string surfaceId)
    {
        if (node.Kind == "stack")
        {
            var kept = (node.Surfaces ?? []).Where(s => s.SurfaceId != surfaceId).ToList();
            // A stack with nothing left ceases to exist rather than persisting empty — the same
            // invariant the domain model enforces, applied at the DTO layer where the model cannot.
            return kept.Count == 0 ? null : node with { Surfaces = kept };
        }

        var children = (node.Children ?? []).Select(c => RemoveIn(c, surfaceId)).OfType<NodeDto>().ToList();
        return children.Count switch
        {
            0 => null,
            1 => children[0],
            _ => node with
            {
                Children = children,
                Weights = [.. Enumerable.Repeat(1.0 / children.Count, children.Count)],
            },
        };
    }
}
