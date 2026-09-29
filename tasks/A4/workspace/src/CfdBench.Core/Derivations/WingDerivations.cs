using CfdBench.Core.Domain;
using CfdBench.Core.Units;

namespace CfdBench.Core.Derivations;

/// <summary>
/// The one producer of each planform quantity. Chord is linear between adjacent stations, so each integral is exact
/// per segment: ∫c dy = Δy (c0 + c1) / 2 and ∫c² dy = Δy (c0² + c0 c1 + c1²) / 3. Both halves are counted.
/// </summary>
public static class WingDerivations
{
    public static Length Span(Wing wing)
    {
        ArgumentNullException.ThrowIfNull(wing);
        return Length.FromMetres(2.0 * wing.Stations[^1].SpanPosition.Metres);
    }

    public static Area ProjectedArea(Wing wing)
    {
        ArgumentNullException.ThrowIfNull(wing);
        return Area.FromSquareMetres(2.0 * HalfIntegral(wing, (c0, c1) => (c0 + c1) / 2.0));
    }

    public static double AspectRatio(Wing wing)
    {
        var span = Span(wing).Metres;
        return span * span / ProjectedArea(wing).SquareMetres;
    }

    public static Length MeanGeometricChord(Wing wing) => Length.FromMetres(ProjectedArea(wing).SquareMetres / Span(wing).Metres);

    public static Length MeanAerodynamicChord(Wing wing)
    {
        var area = ProjectedArea(wing).SquareMetres;
        return Length.FromMetres(2.0 * HalfIntegral(wing, (c0, c1) => (c0 * c0 + c0 * c1 + c1 * c1) / 3.0) / area);
    }

    public static Angle Washout(Wing wing)
    {
        ArgumentNullException.ThrowIfNull(wing);
        return Angle.FromRadians(wing.Stations[0].Twist.Radians - wing.Stations[^1].Twist.Radians);
    }

    private static double HalfIntegral(Wing wing, Func<double, double, double> meanOverSegment)
    {
        var total = 0.0;
        for (var i = 1; i < wing.Stations.Count; i++)
        {
            var (a, b) = (wing.Stations[i - 1], wing.Stations[i]);
            total += (b.SpanPosition.Metres - a.SpanPosition.Metres) * meanOverSegment(a.Chord.Metres, b.Chord.Metres);
        }
        return total;
    }
}
