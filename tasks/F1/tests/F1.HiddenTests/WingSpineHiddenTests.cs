using System.Collections;
using System.Reflection;
using System.Runtime.ExceptionServices;

// F1 hidden tests: the public contract in prompt.md, reached by reflection so that this project builds without the
// agent's library and every test fails at run time until the contract exists. Reference values: oracle/README.md.
public sealed class WingSpineHiddenTests
{
    private const double RelativeTolerance = 1e-9;

    private static Assembly Core()
    {
        try
        {
            return Assembly.Load("CfdBench.Core");
        }
        catch (FileNotFoundException)
        {
            throw new Xunit.Sdk.XunitException("assembly CfdBench.Core not found (src/CfdBench.Core/CfdBench.Core.csproj)");
        }
    }

    private static Type Required(string fullName)
    {
        var type = Core().GetType(fullName);
        Assert.True(type is not null, $"type {fullName} not found");
        return type!;
    }

    private static Type LengthType => Required("CfdBench.Core.Units.Length");
    private static Type AreaType => Required("CfdBench.Core.Units.Area");
    private static Type AngleType => Required("CfdBench.Core.Units.Angle");
    private static Type StationType => Required("CfdBench.Core.Domain.Station");
    private static Type WingType => Required("CfdBench.Core.Domain.Wing");
    private static Type Derivations => Required("CfdBench.Core.Derivations.WingDerivations");

    private static object? Unwrapped(Func<object?> call)
    {
        try
        {
            return call();
        }
        catch (TargetInvocationException e) when (e.InnerException is not null)
        {
            ExceptionDispatchInfo.Capture(e.InnerException).Throw();
            throw;
        }
    }

    private static object Call(Type type, string name, params object?[] args)
    {
        var method = type.GetMethods(BindingFlags.Public | BindingFlags.Static)
            .SingleOrDefault(m => m.Name == name && m.GetParameters().Length == args.Length);
        Assert.True(method is not null, $"public static {type.Name}.{name} with {args.Length} parameter(s) not found");
        var result = Unwrapped(() => method!.Invoke(null, args));
        Assert.NotNull(result);
        return result!;
    }

    private static object Get(object target, string name)
    {
        var property = target.GetType().GetProperty(name, BindingFlags.Public | BindingFlags.Instance);
        Assert.True(property is not null, $"property {target.GetType().Name}.{name} not found");
        var value = property!.GetValue(target);
        Assert.NotNull(value);
        return value!;
    }

    private static object Metres(double m) => Call(LengthType, "FromMetres", m);

    private static object Degrees(double d) => Call(AngleType, "FromDegrees", d);

    private static object Station(double y, double chord, double leadingEdgeX = 0, double twistDegrees = 0, bool millimetres = false)
    {
        object L(double v) => millimetres ? Call(LengthType, "FromMillimetres", v) : Metres(v);
        var ctor = StationType.GetConstructor([LengthType, LengthType, LengthType, AngleType]);
        Assert.True(ctor is not null, "constructor Station(Length, Length, Length, Angle) not found");
        return Unwrapped(() => ctor!.Invoke([L(y), L(leadingEdgeX), L(chord), Degrees(twistDegrees)]))!;
    }

    private static IList StationList(params object[] stations)
    {
        var list = (IList)Activator.CreateInstance(typeof(List<>).MakeGenericType(StationType))!;
        foreach (var s in stations) list.Add(s);
        return list;
    }

    private static object Wing(params object[] stations) => Call(WingType, "Create", StationList(stations));

    private static double InMetres(object length) => (double)Get(length, "Metres");

    private static double Derive(string quantity, object wing)
    {
        var value = Call(Derivations, quantity, wing);
        return value switch
        {
            double d => d,
            _ when value.GetType() == LengthType => (double)Get(value, "Metres"),
            _ when value.GetType() == AreaType => (double)Get(value, "SquareMetres"),
            _ when value.GetType() == AngleType => (double)Get(value, "Degrees"),
            _ => throw new Xunit.Sdk.XunitException($"{quantity} returned {value.GetType().FullName}"),
        };
    }

    private static void Close(double expected, double actual, string what)
    {
        var scale = Math.Max(1.0, Math.Abs(expected));
        Assert.True(Math.Abs(expected - actual) <= RelativeTolerance * scale, $"{what}: expected {expected:R}, got {actual:R}");
    }

    private static void AssertPlanform(object wing, double span, double area, double aspectRatio, double mgc, double mac)
    {
        Close(span, Derive("Span", wing), "span");
        Close(area, Derive("ProjectedArea", wing), "projected area");
        Close(aspectRatio, Derive("AspectRatio", wing), "aspect ratio");
        Close(mgc, Derive("MeanGeometricChord", wing), "mean geometric chord");
        Close(mac, Derive("MeanAerodynamicChord", wing), "mean aerodynamic chord");
    }

    [Fact]
    public void UnitsConvertAndRejectNonFiniteValues()
    {
        Close(0.25, InMetres(Call(LengthType, "FromMillimetres", 250.0)), "250 mm");
        Close(2.5, (double)Get(Call(AreaType, "FromSquareMetres", 2.5), "SquareMetres"), "2.5 m^2");
        Close(Math.PI, (double)Get(Degrees(180.0), "Radians"), "180 degrees");
        Close(90.0, (double)Get(Call(AngleType, "FromRadians", Math.PI / 2), "Degrees"), "pi/2 radians");
        Assert.ThrowsAny<ArgumentException>(() => Metres(double.NaN));
        Assert.ThrowsAny<ArgumentException>(() => Call(LengthType, "FromMillimetres", double.PositiveInfinity));
        Assert.ThrowsAny<ArgumentException>(() => Call(AreaType, "FromSquareMetres", double.NaN));
        Assert.ThrowsAny<ArgumentException>(() => Degrees(double.NegativeInfinity));
        Assert.ThrowsAny<ArgumentException>(() => Call(AngleType, "FromRadians", double.NaN));
    }

    [Fact]
    public void RectangularWingMatchesItsClosedForms()
    {
        var wing = Wing(Station(0.0, 0.1), Station(0.5, 0.1));
        AssertPlanform(wing, span: 1.0, area: 0.1, aspectRatio: 10.0, mgc: 0.1, mac: 0.1);
    }

    [Fact]
    public void TaperedWingMatchesItsClosedForms()
    {
        var wing = Wing(Station(0.0, 0.2), Station(0.6, 0.1));
        AssertPlanform(wing, span: 1.2, area: 0.18, aspectRatio: 8.0, mgc: 0.15, mac: 7.0 / 45.0);
    }

    [Fact]
    public void CrankedWingIntegratesEverySegment()
    {
        var wing = Wing(Station(0.0, 0.25), Station(0.2, 0.2), Station(0.5, 0.08));
        AssertPlanform(wing, span: 1.0, area: 0.174, aspectRatio: 500.0 / 87.0, mgc: 0.174, mac: 2461.0 / 13050.0);
    }

    [Fact]
    public void SweepAndTwistDoNotChangeThePlanformQuantities()
    {
        var wing = Wing(Station(0.0, 0.2, leadingEdgeX: 0.0, twistDegrees: 3.0), Station(0.6, 0.1, leadingEdgeX: 0.15, twistDegrees: -4.0));
        AssertPlanform(wing, span: 1.2, area: 0.18, aspectRatio: 8.0, mgc: 0.15, mac: 7.0 / 45.0);
    }

    [Fact]
    public void MillimetreStationsGiveTheSameQuantities()
    {
        var wing = Wing(Station(0.0, 200.0, millimetres: true), Station(600.0, 100.0, millimetres: true));
        AssertPlanform(wing, span: 1.2, area: 0.18, aspectRatio: 8.0, mgc: 0.15, mac: 7.0 / 45.0);
    }

    [Fact]
    public void WashoutIsRootTwistMinusTipTwist()
    {
        var washedOut = Wing(Station(0.0, 0.2, twistDegrees: 2.0), Station(0.3, 0.15, twistDegrees: 5.0), Station(0.6, 0.1, twistDegrees: -1.0));
        Close(3.0, Derive("Washout", washedOut), "washout, tip nose-down");
        var washedIn = Wing(Station(0.0, 0.2, twistDegrees: -1.0), Station(0.6, 0.1, twistDegrees: 1.5));
        Close(-2.5, Derive("Washout", washedIn), "washout, tip nose-up");
    }

    [Fact]
    public void CreateRejectsAnInvalidStationList()
    {
        Assert.ThrowsAny<ArgumentNullException>(() => Call(WingType, "Create", [null]));
        Assert.ThrowsAny<ArgumentException>(() => Wing());
        Assert.ThrowsAny<ArgumentException>(() => Wing(Station(0.0, 0.1)));
        Assert.ThrowsAny<ArgumentException>(() => Wing(Station(0.05, 0.1), Station(0.5, 0.1)));
        Assert.ThrowsAny<ArgumentException>(() => Wing(Station(0.0, 0.1), Station(0.3, 0.1), Station(0.3, 0.08)));
        Assert.ThrowsAny<ArgumentException>(() => Wing(Station(0.0, 0.1), Station(0.4, 0.1), Station(0.2, 0.08)));
        Assert.ThrowsAny<ArgumentException>(() => Wing(Station(0.0, 0.1), Station(0.5, 0.0)));
        Assert.ThrowsAny<ArgumentException>(() => Wing(Station(0.0, -0.1), Station(0.5, 0.1)));
    }

    [Fact]
    public void WingKeepsItsOwnCopyOfTheStationsInOrder()
    {
        var list = StationList(Station(0.0, 0.2), Station(0.25, 0.15), Station(0.6, 0.1));
        var wing = Call(WingType, "Create", list);
        list.RemoveAt(2);
        list.Add(Station(0.9, 0.05));
        var kept = ((IEnumerable)Get(wing, "Stations")).Cast<object>().Select(s => InMetres(Get(s, "SpanPosition"))).ToList();
        Assert.Equal([0.0, 0.25, 0.6], kept);
        Close(1.2, Derive("Span", wing), "span after the caller's list changed");
    }

    [Fact]
    public void EveryDerivationRejectsANullWing()
    {
        foreach (var quantity in new[] { "Span", "ProjectedArea", "AspectRatio", "MeanGeometricChord", "MeanAerodynamicChord", "Washout" })
            Assert.ThrowsAny<ArgumentNullException>(() => Call(Derivations, quantity, [null]));
    }
}
