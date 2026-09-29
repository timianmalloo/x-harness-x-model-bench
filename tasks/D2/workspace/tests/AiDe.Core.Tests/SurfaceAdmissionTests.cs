using AiDe.Core.Workbench;

namespace AiDe.Core.Tests;

/// <summary>
/// The Perspective Layout aggregate's invariant, enforced by the host's layout service at open,
/// restore and reset (ADR-0031 rule 3; ADR-0032 rule 2; US-C3 b1, US-C9). A host never contains a
/// surface of a kind its perspective does not admit, and a one-instance kind appears at most once —
/// whatever path tried to place it.
/// </summary>
/// <remarks>
/// Every service here is constructed the way the shell constructs it — <c>new
/// ZoneBackedLayoutService(admission)</c> — never the tree <c>LayoutService</c> (DC-135). The rules
/// are hand-built rows rather than the App's kind table so the Core test needs no App reference;
/// the App-side tests (<c>PerspectiveLayoutSlotTests</c>) run the same service over the product's rows.
/// </remarks>
public sealed class SurfaceAdmissionTests
{
    private static readonly Perspective Coding = PerspectiveSet.Coding;
    private static readonly Perspective Architecture = PerspectiveSet.Architecture;

    /// <summary>A small table in §A7's shape: terminal and sessions for Coding, canvas and view for Architecture, codeviewer shared; view and sessions one-instance.</summary>
    private static SurfaceAdmission For(Perspective perspective) => new(perspective, new Dictionary<string, KindRule>(StringComparer.Ordinal)
    {
        ["terminal"] = new([Coding], OneInstance: false),
        ["sessions"] = new([Coding], OneInstance: true),
        ["canvas"] = new([Architecture], OneInstance: true),
        ["view"] = new([Architecture], OneInstance: true),
        ["sequence"] = new([Architecture], OneInstance: false),
        ["codeviewer"] = new([Coding, Architecture], OneInstance: false),
    });

    // US-C3 b1 — a command path: any AddSurface of a kind the perspective does not admit is refused
    // with a stable code, and the host does not contain it afterwards.
    [Fact]
    public void AddSurface_OfAKindThePerspectiveDoesNotAdmit_IsRefusedAndReported()
    {
        var host = new ZoneBackedLayoutService(For(Coding), WorkbenchLayout.Empty());

        var result = host.Apply(new LayoutOperation.AddSurface(
            ZonesToTree.CenterStackId, new Surface("seq-1", "sequence", "Sequence diagram")));

        Assert.False(result.Applied);
        Assert.Equal(SurfaceAdmission.RefusalCode, result.RefusalCode);
        Assert.Contains("Architecture", result.Announcement, StringComparison.Ordinal);  // names the perspective that admits it
        Assert.DoesNotContain(host.Zones.AllSurfaces(), s => s.Kind == "sequence");
    }

    // The one-instance rule at OPEN: a second surface of a one-instance kind is refused with the
    // first named and a stable code; the host still holds exactly one.
    [Fact]
    public void AddSurface_OfASecondOneInstanceSurface_IsRefusedWithTheFirstNamed()
    {
        var host = new ZoneBackedLayoutService(For(Coding), WorkbenchLayout.Empty());
        Assert.True(host.Apply(new LayoutOperation.AddSurface(ZonesToTree.LeftStackId, new Surface("s-1", "sessions", "Sessions"))).Applied);

        var second = host.Apply(new LayoutOperation.AddSurface(ZonesToTree.CenterStackId, new Surface("s-2", "sessions", "Sessions")));

        Assert.False(second.Applied);
        Assert.Equal(SurfaceAdmission.OneInstanceCode, second.RefusalCode);
        Assert.Contains("already open", second.Announcement, StringComparison.Ordinal);
        Assert.Single(host.Zones.AllSurfaces(), s => s.Kind == "sessions");
    }

    [Fact]
    public void AddSurface_OfAnAdmittedKind_IsAppliedAsBefore()
    {
        var host = new ZoneBackedLayoutService(For(Coding), WorkbenchLayout.Empty());

        var result = host.Apply(new LayoutOperation.AddSurface(
            ZonesToTree.BottomStackId, new Surface("t-1", "terminal", "Terminal")));

        Assert.True(result.Applied);
        Assert.Equal(ZoneId.Bottom, host.Zones.FindZoneOf("t-1"));
    }

    // ADR-0032 rule 2 (the restore path): an arrangement carrying inadmissible kinds restores with
    // exactly the admitted surfaces, and every drop is reported by surface, reason and the
    // perspective that admits it. A canvas surviving in Coding fails; a crash fails.
    [Fact]
    public void RestoreZones_DropsInadmissibleKinds_AndReportsEachWithTheAdmittingPerspective()
    {
        var host = new ZoneBackedLayoutService(For(Coding), WorkbenchLayout.Empty());
        var saved = WorkbenchLayout.Empty()
            .WithZone(new ZoneState(ZoneId.Center, new ZoneStack(
            [
                new Surface("graph", "canvas", "Graph"),
                new Surface("t-1", "terminal", "Terminal"),
                new Surface("cv-1", "codeviewer", "Code viewer"),
            ]), 1.0, Collapsed: false))
            .WithZone(new ZoneState(ZoneId.Left, new ZoneStack(
            [
                new Surface("domain", "view", "Domain"),
                new Surface("sessions", "sessions", "Sessions"),
            ]), ZoneState.DefaultExtent, Collapsed: false));

        var report = host.RestoreZones(saved);

        Assert.Equal(["t-1", "cv-1"], host.Zones.Zone(ZoneId.Center).Surfaces().Select(s => s.SurfaceId).ToList());
        Assert.Equal(["sessions"], host.Zones.Zone(ZoneId.Left).Surfaces().Select(s => s.SurfaceId).ToList());
        Assert.Equal(2, report.Dropped.Count);
        Assert.All(report.Dropped, d => Assert.Equal(DropReason.KindNotAdmitted, d.Reason));
        Assert.All(report.Dropped, d => Assert.Same(Architecture, d.AdmittedBy));
        Assert.Equal(["domain", "graph"], report.Dropped.Select(d => d.Surface.SurfaceId).ToList());   // zone order: Left before Center
        Assert.False(report.DefaultApplied);
    }

    // ADR-0032 test 3 — two surfaces of a one-instance kind with distinct ids: the first is kept, the
    // second dropped and reported as a duplicate, not as inadmissible.
    [Fact]
    public void RestoreZones_KeepsTheFirstOfAOneInstanceKind_AndReportsTheSecond()
    {
        var host = new ZoneBackedLayoutService(For(Architecture), WorkbenchLayout.Empty());
        var saved = WorkbenchLayout.Empty()
            .WithZone(new ZoneState(ZoneId.Left, new ZoneStack([new Surface("explore", "view", "Explore")]), ZoneState.DefaultExtent, Collapsed: false))
            .WithZone(new ZoneState(ZoneId.Center, new ZoneStack([new Surface("domain", "view", "Domain")]), 1.0, Collapsed: false));

        var report = host.RestoreZones(saved);

        var views = host.Zones.AllSurfaces().Where(s => s.Kind == "view").ToList();
        Assert.Single(views);
        Assert.Equal("explore", views[0].SurfaceId);           // the first in zone order (Left before Center)
        var dropped = Assert.Single(report.Dropped);
        Assert.Equal("domain", dropped.Surface.SurfaceId);
        Assert.Equal(DropReason.DuplicateOneInstance, dropped.Reason);
    }

    // ADR-0032 test 2 — every surface inadmissible: the perspective's default is applied and the
    // report says so. An empty host with four empty zones fails.
    [Fact]
    public void RestoreZones_WithNothingAdmissible_AppliesTheDefaultAndSaysSo()
    {
        var host = new ZoneBackedLayoutService(For(Architecture));
        var saved = WorkbenchLayout.Empty()
            .WithZone(new ZoneState(ZoneId.Bottom, new ZoneStack([new Surface("t-1", "terminal", "Terminal")]), 0.3, Collapsed: false));

        var report = host.RestoreZones(saved);

        Assert.True(report.DefaultApplied);
        Assert.Single(report.Dropped);
        Assert.NotEmpty(host.Zones.AllSurfaces());                                   // not four empty zones
        Assert.All(host.Zones.AllSurfaces(), s => Assert.True(host.Admission.Admits(s.Kind)));
    }

    // The default and the reset are filtered by the same rule: a reset can never bring an
    // inadmissible kind back into the host.
    [Fact]
    public void TheDefaultAndResetToDefault_HoldOnlyAdmittedKinds()
    {
        var host = new ZoneBackedLayoutService(For(Coding));

        Assert.NotEmpty(host.Zones.AllSurfaces());
        Assert.All(host.Zones.AllSurfaces(), s => Assert.True(host.Admission.Admits(s.Kind), $"{s.Kind} is not admitted in Coding"));

        host.Apply(new LayoutOperation.ResetToDefault());

        Assert.All(host.Zones.AllSurfaces(), s => Assert.True(host.Admission.Admits(s.Kind), $"{s.Kind} came back on reset"));
        Assert.Contains(host.Zones.AllSurfaces(), s => s.Kind == "terminal");
    }

    // The unrestricted admission is today's behaviour for every existing caller — nothing is
    // dropped, nothing refused — so the legacy tests and the tree path are untouched.
    [Fact]
    public void AnUnrestrictedService_BehavesAsBefore()
    {
        var host = new ZoneBackedLayoutService();

        var report = host.RestoreZones(WorkbenchLayout.Default());

        Assert.Empty(report.Dropped);
        Assert.Same(SurfaceAdmission.Unrestricted, host.Admission);
        Assert.True(host.Apply(new LayoutOperation.AddSurface(
            ZonesToTree.CenterStackId, new Surface("seq-1", "sequence", "Sequence"))).Applied);
    }

    [Fact]
    public void AdmittedBy_NamesTheFirstPerspectiveInRoutingOrder_ThatAdmitsTheKind()
    {
        var coding = For(Coding);

        Assert.Same(Architecture, coding.AdmittedBy("canvas"));
        Assert.Same(Architecture, coding.AdmittedBy("codeviewer"));   // shared: Architecture first in RoutingOrder
        Assert.Null(coding.AdmittedBy("nosuchkind"));
        Assert.True(coding.Admits("codeviewer"));
        Assert.False(coding.Admits("canvas"));
    }
}
