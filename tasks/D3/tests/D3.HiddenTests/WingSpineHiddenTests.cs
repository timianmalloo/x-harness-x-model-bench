using CfdBench.Core.Derivations;
using CfdBench.Core.Domain;
using CfdBench.Core.Units;

// D3 hidden tests: the four producers plus the Wing aggregate's invariants, against
// docs/architecture-note.md. The base workspace's Wing and WingDerivations are stubs that throw
// NotImplementedException, so every test here fails at run time on the base (a runtime failure,
// not a compile failure — a compile-only failure would grade NA under DR-G4, not 0). Reference
// values: oracle/README.md.
public sealed class WingSpineHiddenTests
{
    private const double RelativeTolerance = 1e-9;

    private static Station S(double y, double chord) => new(Length.FromMetres(y), Length.FromMetres(chord));

    private static void Close(double expected, double actual, string what)
    {
        var scale = Math.Max(1.0, Math.Abs(expected));
        Assert.True(Math.Abs(expected - actual) <= RelativeTolerance * scale, $"{what}: expected {expected:R}, got {actual:R}");
    }

    private static void AssertPlanform(Wing wing, double span, double area, double aspectRatio, double mgc)
    {
        Close(span, WingDerivations.Span(wing).Metres, "span");
        Close(area, WingDerivations.ProjectedArea(wing).SquareMetres, "projected area");
        Close(aspectRatio, WingDerivations.AspectRatio(wing), "aspect ratio");
        Close(mgc, WingDerivations.MeanGeometricChord(wing).Metres, "mean geometric chord");
    }

    [Fact]
    public void RectangularWingMatchesItsClosedForms()
    {
        var wing = Wing.Create([S(0.0, 0.1), S(0.5, 0.1)]);
        AssertPlanform(wing, span: 1.0, area: 0.1, aspectRatio: 10.0, mgc: 0.1);
    }

    [Fact]
    public void TaperedWingMatchesItsClosedForms()
    {
        var wing = Wing.Create([S(0.0, 0.2), S(0.6, 0.1)]);
        AssertPlanform(wing, span: 1.2, area: 0.18, aspectRatio: 8.0, mgc: 0.15);
    }

    [Fact]
    public void CrankedWingIntegratesEverySegment()
    {
        var wing = Wing.Create([S(0.0, 0.25), S(0.2, 0.2), S(0.5, 0.08)]);
        AssertPlanform(wing, span: 1.0, area: 0.174, aspectRatio: 500.0 / 87.0, mgc: 0.174);
    }

    [Fact]
    public void CreateRejectsAnInvalidStationList()
    {
        Assert.Throws<ArgumentNullException>(() => Wing.Create(null!));
        Assert.Throws<ArgumentException>(() => Wing.Create([]));
        Assert.Throws<ArgumentException>(() => Wing.Create([S(0.0, 0.1)]));
        Assert.Throws<ArgumentException>(() => Wing.Create([S(0.05, 0.1), S(0.5, 0.1)]));
        Assert.Throws<ArgumentException>(() => Wing.Create([S(0.0, 0.1), S(0.3, 0.1), S(0.3, 0.08)]));
        Assert.Throws<ArgumentException>(() => Wing.Create([S(0.0, 0.1), S(0.4, 0.1), S(0.2, 0.08)]));
        Assert.Throws<ArgumentException>(() => Wing.Create([S(0.0, 0.1), S(0.5, 0.0)]));
        Assert.Throws<ArgumentException>(() => Wing.Create([S(0.0, -0.1), S(0.5, 0.1)]));
    }

    [Fact]
    public void WingKeepsItsOwnCopyOfTheStationsInOrder()
    {
        var list = new List<Station> { S(0.0, 0.2), S(0.25, 0.15), S(0.6, 0.1) };
        var wing = Wing.Create(list);
        list.RemoveAt(2);
        list.Add(S(0.9, 0.05));
        Assert.Equal([0.0, 0.25, 0.6], wing.Stations.Select(s => s.SpanPosition.Metres));
        Close(1.2, WingDerivations.Span(wing).Metres, "span after the caller's list changed");
    }

    [Fact]
    public void EveryDerivationRejectsANullWing()
    {
        Assert.Throws<ArgumentNullException>(() => WingDerivations.Span(null!));
        Assert.Throws<ArgumentNullException>(() => WingDerivations.ProjectedArea(null!));
        Assert.Throws<ArgumentNullException>(() => WingDerivations.AspectRatio(null!));
        Assert.Throws<ArgumentNullException>(() => WingDerivations.MeanGeometricChord(null!));
    }
}
