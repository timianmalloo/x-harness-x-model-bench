using CfdBench.Core.Domain;
using CfdBench.Core.Units;

namespace CfdBench.Core.Derivations;

/// <summary>
/// The one producer of each planform quantity. Chord is linear between adjacent stations, so each integral is exact
/// per segment: ∫c dy = Δy (c0 + c1) / 2. Both halves are counted.
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
        return Area.FromSquareMetres(2.0 * HalfIntegral(wing));
    }

    public static double AspectRatio(Wing wing)
    {
        ArgumentNullException.ThrowIfNull(wing);
        var span = Span(wing).Metres;
        return span * span / ProjectedArea(wing).SquareMetres;
    }

    public static Length MeanGeometricChord(Wing wing)
    {
        ArgumentNullException.ThrowIfNull(wing);
        return Length.FromMetres(ProjectedArea(wing).SquareMetres / Span(wing).Metres);
    }

    private static double HalfIntegral(Wing wing)
    {
        var total = 0.0;
        for (var i = 1; i < wing.Stations.Count; i++)
        {
            var (a, b) = (wing.Stations[i - 1], wing.Stations[i]);
            total += (b.SpanPosition.Metres - a.SpanPosition.Metres) * (a.Chord.Metres + b.Chord.Metres) / 2.0;
        }
        return total;
    }
}
