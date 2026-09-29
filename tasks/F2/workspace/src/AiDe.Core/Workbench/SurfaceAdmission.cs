using System.Collections.Immutable;

namespace AiDe.Core.Workbench;

/// <summary>One kind's admission row: which perspectives admit it, and whether a host holds at most one.</summary>
public sealed record KindRule(IReadOnlyList<Perspective> Perspectives, bool OneInstance);

/// <summary>Why a surface was dropped from a host's arrangement (ADR-0032 rule 2).</summary>
public enum DropReason
{
    /// <summary>The perspective's allow-list does not admit the surface's kind.</summary>
    KindNotAdmitted,

    /// <summary>A second surface of a one-instance kind; the first was kept.</summary>
    DuplicateOneInstance,
}

/// <summary>A surface the admission filter removed, with the reason and the perspective that admits its kind (null for a duplicate, or a kind no perspective admits).</summary>
public sealed record DroppedSurface(Surface Surface, DropReason Reason, Perspective? AdmittedBy);

/// <summary>What <see cref="SurfaceAdmission.Filter"/> produced: the admitted arrangement and every drop.</summary>
public sealed record AdmissionFilter(WorkbenchLayout Layout, IReadOnlyList<DroppedSurface> Dropped);

/// <summary>
/// The Perspective Layout aggregate's invariant as data (ADR-0030 rule 2; ADR-0031 rule 3;
/// ADR-0032 rule 2): the kinds one host perspective admits, which of them are one-instance, and
/// — for the report — which perspective admits a kind this host refuses.
/// </summary>
/// <remarks>
/// <para><b>Enforced by the host's layout service, never by the store.</b> The store filters by
/// <i>availability</i> and stays perspective-blind so one class serves every slot; admissibility
/// is the host's invariant and is applied wherever the host's arrangement is set — an add, a
/// restore, a reset (ADR-0032, alternatives).</para>
///
/// <para><b>Rows, not a switch.</b> The rules are the App's kind table (its <c>Perspectives</c> and
/// <c>Instances</c> columns) handed down as data, so a kind added as a row is admitted, refused and
/// reported with no edit here.</para>
/// </remarks>
public sealed class SurfaceAdmission
{
    /// <summary>The stable code a host's service refuses an inadmissible surface with (ADR-0031 rule 3; US-C3 b1). Beside <see cref="LayoutErrorCodes"/>' family, named here because the rule is this type's.</summary>
    public const string RefusalCode = "AIDE-LAYOUT-KIND-NOT-ADMITTED";

    /// <summary>The stable code a host's service refuses a second surface of a one-instance kind with.</summary>
    public const string OneInstanceCode = "AIDE-LAYOUT-ONE-INSTANCE";

    private readonly IReadOnlyDictionary<string, KindRule> _rules;

    public SurfaceAdmission(Perspective perspective, IReadOnlyDictionary<string, KindRule> rules)
    {
        Perspective = perspective ?? throw new ArgumentNullException(nameof(perspective));
        _rules = rules ?? throw new ArgumentNullException(nameof(rules));
    }

    private SurfaceAdmission()
    {
        Perspective = PerspectiveSet.Initial;
        _rules = ImmutableDictionary<string, KindRule>.Empty;
        IsUnrestricted = true;
    }

    /// <summary>
    /// Admits every kind, any number of times — the behaviour every caller had before perspectives
    /// (the legacy tree path, and every test that constructs a bare service). Never the shell's.
    /// </summary>
    public static SurfaceAdmission Unrestricted { get; } = new();

    /// <summary>The perspective whose host this admission guards.</summary>
    public Perspective Perspective { get; }

    /// <summary>True for <see cref="Unrestricted"/> only.</summary>
    public bool IsUnrestricted { get; }

    /// <summary>Whether this host admits a surface of <paramref name="kind"/>.</summary>
    public bool Admits(string kind) =>
        IsUnrestricted || (_rules.TryGetValue(kind, out var rule) && rule.Perspectives.Contains(Perspective));

    /// <summary>Whether a host holds at most one surface of <paramref name="kind"/>.</summary>
    public bool IsOneInstance(string kind) =>
        !IsUnrestricted && _rules.TryGetValue(kind, out var rule) && rule.OneInstance;

    /// <summary>
    /// The perspective that admits <paramref name="kind"/> — the first of
    /// <see cref="PerspectiveSet.RoutingOrder"/> that does — or null for a kind no perspective admits.
    /// What the drop report names, and where a routed open lands (US-C3).
    /// </summary>
    public Perspective? AdmittedBy(string kind) =>
        _rules.TryGetValue(kind, out var rule)
            ? PerspectiveSet.RoutingOrder.FirstOrDefault(p => rule.Perspectives.Contains(p))
            : null;

    /// <summary>
    /// Removes from <paramref name="layout"/> every surface this host does not admit and every
    /// second instance of a one-instance kind, in zone order (Left · Right · Bottom · Center, then
    /// the floating stacks), reporting each drop. A stack left empty becomes an empty zone; a split
    /// left with one child collapses to it. The result satisfies the frame invariant.
    /// </summary>
    public AdmissionFilter Filter(WorkbenchLayout layout)
    {
        ArgumentNullException.ThrowIfNull(layout);

        if (IsUnrestricted)
        {
            return new AdmissionFilter(layout, []);
        }

        var dropped = new List<DroppedSurface>();
        var seenOneInstance = new HashSet<string>(StringComparer.Ordinal);

        bool Keep(Surface s)
        {
            if (!Admits(s.Kind))
            {
                dropped.Add(new DroppedSurface(s, DropReason.KindNotAdmitted, AdmittedBy(s.Kind)));
                return false;
            }

            if (IsOneInstance(s.Kind) && !seenOneInstance.Add(s.Kind))
            {
                dropped.Add(new DroppedSurface(s, DropReason.DuplicateOneInstance, null));
                return false;
            }

            return true;
        }

        var result = layout;
        foreach (var id in Enum.GetValues<ZoneId>())
        {
            var zone = layout.Zone(id);
            result = result.WithZone(zone with { Content = FilterContent(zone.Content, Keep) });
        }

        var floating = layout.Floating
            .Select(f => (Node: f, Kept: f.Surfaces.Where(Keep).ToImmutableList()))
            .Where(x => x.Kept.Count > 0)
            .Select(x => new StackNode(x.Node.Id, x.Kept, x.Node.ActiveIndex, x.Node.State, x.Node.MinWidth, x.Node.MinHeight, x.Node.FloatingBounds))
            .ToImmutableList();

        result = result with { Floating = floating };
        result.AssertInvariant();
        return new AdmissionFilter(result, dropped);
    }

    private static ZoneContent? FilterContent(ZoneContent? content, Func<Surface, bool> keep)
    {
        switch (content)
        {
            case null:
                return null;

            case ZoneStack stack:
                var tabs = stack.Tabs.Where(keep).ToImmutableList();
                if (tabs.Count == 0)
                {
                    return null;
                }

                var active = stack.ActiveIndex >= 0 && stack.ActiveIndex < stack.Tabs.Count
                    ? tabs.IndexOf(stack.Tabs[stack.ActiveIndex])
                    : -1;
                return new ZoneStack(tabs, active >= 0 ? active : Math.Clamp(stack.ActiveIndex, 0, tabs.Count - 1));

            case ZoneSplit split:
                var kept = new List<ZoneContent>();
                var weights = new List<double>();
                for (var i = 0; i < split.Children.Count; i++)
                {
                    var child = FilterContent(split.Children[i], keep);
                    if (child is null)
                    {
                        continue;
                    }

                    kept.Add(child);
                    weights.Add(i < split.Weights.Count ? split.Weights[i] : 1.0 / split.Children.Count);
                }

                return kept.Count switch
                {
                    0 => null,
                    1 => kept[0],
                    _ => new ZoneSplit(split.Orientation, [.. kept], [.. weights]),
                };

            default:
                return content;
        }
    }
}
