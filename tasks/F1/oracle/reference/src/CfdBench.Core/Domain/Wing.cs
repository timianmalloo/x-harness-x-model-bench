using CfdBench.Core.Units;

namespace CfdBench.Core.Domain;

/// <summary>
/// One station of a half-wing: its distance from the centreline, its leading-edge x (positive aft), its chord and its
/// twist (incidence, positive nose-up). A value object; the wing's invariants are checked by <see cref="Wing.Create"/>.
/// </summary>
public readonly record struct Station(Length SpanPosition, Length LeadingEdgeX, Length Chord, Angle Twist);

/// <summary>
/// The wing aggregate: a symmetric wing described by the stations of one half, root first. Invariant: at least two
/// stations, the root on the centreline, span positions strictly increasing, every chord strictly positive.
/// It stores stations only; every derived quantity has one producer in <c>Derivations.WingDerivations</c>.
/// </summary>
public sealed class Wing
{
    private Wing(Station[] stations) => Stations = Array.AsReadOnly(stations);

    public IReadOnlyList<Station> Stations { get; }

    public static Wing Create(IReadOnlyList<Station> stations)
    {
        ArgumentNullException.ThrowIfNull(stations);
        var copy = stations.ToArray();
        if (copy.Length < 2)
            throw new ArgumentException("a wing needs at least two stations (root and tip)", nameof(stations));
        if (copy[0].SpanPosition.Metres != 0.0)
            throw new ArgumentException("the first station is the root and must lie on the centreline", nameof(stations));
        for (var i = 0; i < copy.Length; i++)
        {
            if (!(copy[i].Chord.Metres > 0.0))
                throw new ArgumentException($"station {i}: chord must be strictly positive", nameof(stations));
            if (i > 0 && !(copy[i].SpanPosition.Metres > copy[i - 1].SpanPosition.Metres))
                throw new ArgumentException($"station {i}: span positions must strictly increase", nameof(stations));
        }
        return new Wing(copy);
    }
}
