namespace CfdBench.Core.Units;

/// <summary>A length, stored in metres. Values may be negative (a coordinate); they are never NaN or infinite.
/// Given: part of the fixed architecture (docs/architecture-note.md). Do not change its public contract.</summary>
public readonly record struct Length
{
    private Length(double metres) => Metres = metres;

    public double Metres { get; }

    public static Length FromMetres(double metres) => new(Finite.Check(metres, nameof(metres)));
}

/// <summary>An area, stored in square metres.
/// Given: part of the fixed architecture (docs/architecture-note.md). Do not change its public contract.</summary>
public readonly record struct Area
{
    private Area(double squareMetres) => SquareMetres = squareMetres;

    public double SquareMetres { get; }

    public static Area FromSquareMetres(double squareMetres) => new(Finite.Check(squareMetres, nameof(squareMetres)));
}

internal static class Finite
{
    public static double Check(double value, string name) =>
        double.IsFinite(value) ? value : throw new ArgumentException($"{name} must be finite, got {value}", name);
}
