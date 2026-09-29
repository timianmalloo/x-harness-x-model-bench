using CfdBench.Core.Domain;
using CfdBench.Core.Units;

namespace CfdBench.Core.Derivations;

/// <summary>
/// One producer per planform quantity. STUB — not yet implemented.
/// Definitions and formulas: docs/architecture-note.md, "Derived quantities".
/// </summary>
public static class WingDerivations
{
    public static Length Span(Wing wing) => throw new NotImplementedException();

    public static Area ProjectedArea(Wing wing) => throw new NotImplementedException();

    public static double AspectRatio(Wing wing) => throw new NotImplementedException();

    public static Length MeanGeometricChord(Wing wing) => throw new NotImplementedException();
}
