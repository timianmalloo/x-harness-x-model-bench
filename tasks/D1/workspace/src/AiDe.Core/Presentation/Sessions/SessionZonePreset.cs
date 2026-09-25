namespace AiDe.Core.Presentation.Sessions;

/// <summary>
/// The paired-zone preset a session document opens in (A2, A4.4): composer zone and canvas zone,
/// splitter between.
/// </summary>
/// <remarks>
/// <para><b>New construction.</b> No "preset" concept existed in this repository before this node —
/// <c>TerminalColorScheme.Presets</c> is a palette table and is unrelated. This is deliberately a
/// <b>value</b>, not a layout operation: A2 says "the layout is a preset, not a new window type",
/// so the paired zone is a property of the one dock document a session renders as, and docking,
/// zones and persistence keep behaving exactly as they do for every other surface.</para>
///
/// <para><b>The weight is the composer's.</b> One number rather than two, because two would let a
/// saved pair sum to something other than one and leave the splitter somewhere neither zone asked
/// for. The canvas takes the remainder.</para>
/// </remarks>
/// <param name="ComposerZoneId">The composer half's stable id — persisted, so it never changes.</param>
/// <param name="CanvasZoneId">The canvas half's stable id.</param>
/// <param name="Orientation">How the two sit relative to each other.</param>
/// <param name="ComposerWeight">The composer's share of the pair, strictly between 0 and 1.</param>
public sealed record SessionZonePreset(
    string ComposerZoneId,
    string CanvasZoneId,
    AiDe.Core.Workbench.Orientation Orientation,
    double ComposerWeight)
{
    /// <summary>The narrowest either half may be squeezed to. A zone with no width is a zone that vanished.</summary>
    public const double MinimumWeight = 0.15;

    /// <summary>
    /// The preset A2 names: composer left, canvas right, splitter between.
    /// </summary>
    /// <remarks>
    /// 0.42 rather than 0.5: the mockups put the wider half on the output canvas, which is where a
    /// running session's attention is, while the composer stays wide enough for a goal block.
    /// </remarks>
    public static SessionZonePreset PairedZone { get; } =
        new("composer", "canvas", AiDe.Core.Workbench.Orientation.Horizontal, 0.42);

    /// <summary>The canvas half's share — the remainder, so the pair always sums to one.</summary>
    public double CanvasWeight => 1.0 - ComposerWeight;

    /// <summary>The same preset with the splitter moved, clamped so neither half can vanish.</summary>
    public SessionZonePreset WithComposerWeight(double weight) =>
        this with { ComposerWeight = Math.Clamp(weight, MinimumWeight, 1.0 - MinimumWeight) };
}
