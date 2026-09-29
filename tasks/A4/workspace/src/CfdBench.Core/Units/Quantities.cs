namespace CfdBench.Core.Units;

/// <summary>A length, stored in metres. Values may be negative (a coordinate); they are never NaN or infinite.</summary>
public readonly record struct Length
{
    private Length(double metres) => Metres = metres;

    public double Metres { get; }

    public static Length FromMetres(double metres) => new(Finite.Check(metres, nameof(metres)));

    public static Length FromMillimetres(double millimetres) => new(Finite.Check(millimetres, nameof(millimetres)) / 1000.0);
}

/// <summary>An area, stored in square metres.</summary>
public readonly record struct Area
{
    private Area(double squareMetres) => SquareMetres = squareMetres;

    public double SquareMetres { get; }

    public static Area FromSquareMetres(double squareMetres) => new(Finite.Check(squareMetres, nameof(squareMetres)));
}

/// <summary>A plane angle, stored in radians. Sign conventions belong to the quantity that carries it.</summary>
public readonly record struct Angle
{
    private Angle(double radians) => Radians = radians;

    public double Radians { get; }

    public double Degrees => Radians * 180.0 / Math.PI;

    public static Angle FromRadians(double radians) => new(Finite.Check(radians, nameof(radians)));

    public static Angle FromDegrees(double degrees) => new(Finite.Check(degrees, nameof(degrees)) * Math.PI / 180.0);
}

internal static class Finite
{
    public static double Check(double value, string name) =>
        double.IsFinite(value) ? value : throw new ArgumentException($"{name} must be finite, got {value}", name);
}
