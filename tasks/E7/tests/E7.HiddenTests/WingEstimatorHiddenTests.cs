using System;
using System.Collections.Generic;
using CfdBench.Core.Estimation;

namespace E7.HiddenTests;

/// <summary>
/// Hidden tests for the P1 estimator slice (<see cref="WingEstimator.Estimate"/>). Four regression cases
/// reproduce specific rows of the worked table in cfd-bench's estimation-methods.md (surf foiling at 7 kn,
/// wing foiling at 20 kn, SUP/downwind at 10 kn, windsurf/race at 28 kn) to a tight relative tolerance;
/// the rest are property tests (limiting cases, monotonicity, dimensional/table-value checks) and
/// argument-validation tests. Nothing here is reachable from workspace/.
/// </summary>
public class WingEstimatorHiddenTests
{
    // ITTC seawater at 15 degC (data-and-constants.md), shared by every regression case.
    private const double SeawaterDensity = 1026.0210;
    private const double SeawaterKinematicViscosity = 1.1892e-6;
    private const double SeawaterVapourPressure = 1670.9;
    private const double AtmosphericPressure = 101325.0;
    private const double StandardGravity = 9.80665;
    private const double KnotsToMetresPerSecond = 0.514444;
    private const double RiderPlusGearMassKg = 95.0;
    private const double RelativeTolerance = 1e-5;

    private static double WeightNewtons() => RiderPlusGearMassKg * StandardGravity;

    private static WingEstimateInputs Baseline(double aspectRatio, double areaM2, double speedKnots) => new(
        AspectRatio: aspectRatio,
        ProjectedAreaM2: areaM2,
        ThicknessChordRatio: 0.11,
        SpanEfficiency: 0.85,
        SectionLiftCoefficient: 0.3,
        SectionDragCoefficient: 0.012,
        SectionMinimumPressureCoefficient: -1.0,
        SpeedMetresPerSecond: speedKnots * KnotsToMetresPerSecond,
        WeightNewtons: WeightNewtons(),
        FluidDensityKgPerM3: SeawaterDensity,
        FluidKinematicViscosityM2PerS: SeawaterKinematicViscosity,
        VapourPressurePascal: SeawaterVapourPressure,
        AtmosphericPressurePascal: AtmosphericPressure,
        DepthMetres: 0.45);

    private static void AssertClose(double expected, double actual, string what)
    {
        var tolerance = Math.Max(Math.Abs(expected) * RelativeTolerance, 1e-9);
        Assert.True(Math.Abs(expected - actual) <= tolerance,
            $"{what}: expected {expected}, got {actual} (tolerance {tolerance})");
    }

    // --- Regression: exact reproduction of estimation-methods.md's worked table -----------------------

    [Fact]
    public void SurfFoiling7Knots_MatchesTheWorkedTable()
    {
        var r = WingEstimator.Estimate(Baseline(aspectRatio: 5.0, areaM2: 0.18, speedKnots: 7));
        AssertClose(574556.17458394, r.ReynoldsNumber, nameof(r.ReynoldsNumber));
        AssertClose(0.77798859, r.LiftCoefficient, nameof(r.LiftCoefficient));
        AssertClose(10.4786704, r.RequiredAngleOfAttackDegrees, nameof(r.RequiredAngleOfAttackDegrees));
        AssertClose(0.0134333, r.ParasiticDragCoefficient, nameof(r.ParasiticDragCoefficient));
        AssertClose(0.04533229, r.InducedDragCoefficient, nameof(r.InducedDragCoefficient));
        AssertClose(13.23884565, r.LiftDragRatio, nameof(r.LiftDragRatio));
        AssertClose(15.66007445, r.CavitationNumber, nameof(r.CavitationNumber));
    }

    [Fact]
    public void WingFoiling20Knots_MatchesTheWorkedTable()
    {
        var r = WingEstimator.Estimate(Baseline(aspectRatio: 7.0, areaM2: 0.14, speedKnots: 20));
        AssertClose(1223568.25072564, r.ReynoldsNumber, nameof(r.ReynoldsNumber));
        AssertClose(0.1225332, r.LiftCoefficient, nameof(r.LiftCoefficient));
        AssertClose(1.48132936, r.RequiredAngleOfAttackDegrees, nameof(r.RequiredAngleOfAttackDegrees));
        AssertClose(0.01136217, r.ParasiticDragCoefficient, nameof(r.ParasiticDragCoefficient));
        AssertClose(0.00080323, r.InducedDragCoefficient, nameof(r.InducedDragCoefficient));
        AssertClose(10.0722655, r.LiftDragRatio, nameof(r.LiftDragRatio));
        AssertClose(1.91835912, r.CavitationNumber, nameof(r.CavitationNumber));
    }

    [Fact]
    public void SupDownwind10Knots_MatchesTheWorkedTable()
    {
        var r = WingEstimator.Estimate(Baseline(aspectRatio: 10.5, areaM2: 0.11, speedKnots: 10));
        AssertClose(442776.84245514, r.ReynoldsNumber, nameof(r.ReynoldsNumber));
        AssertClose(0.6238054, r.LiftCoefficient, nameof(r.LiftCoefficient));
        AssertClose(6.87420426, r.RequiredAngleOfAttackDegrees, nameof(r.RequiredAngleOfAttackDegrees));
        AssertClose(0.01427996, r.ParasiticDragCoefficient, nameof(r.ParasiticDragCoefficient));
        AssertClose(0.01387842, r.InducedDragCoefficient, nameof(r.InducedDragCoefficient));
        AssertClose(22.15345462, r.LiftDragRatio, nameof(r.LiftDragRatio));
        AssertClose(7.67343648, r.CavitationNumber, nameof(r.CavitationNumber));
        // sigma_i = 1.0 (Cp_min = -1.0) < sigma: comfortably clear of cavitation.
        AssertClose(6.67343648, r.CavitationMargin, nameof(r.CavitationMargin));
    }

    [Fact]
    public void WindsurfRace28Knots_MatchesTheWorkedTableAndCavitates()
    {
        var r = WingEstimator.Estimate(Baseline(aspectRatio: 12.0, areaM2: 0.08, speedKnots: 28));
        AssertClose(988998.44249966, r.ReynoldsNumber, nameof(r.ReynoldsNumber));
        AssertClose(0.10940465, r.LiftCoefficient, nameof(r.LiftCoefficient));
        AssertClose(1.17768721, r.RequiredAngleOfAttackDegrees, nameof(r.RequiredAngleOfAttackDegrees));
        AssertClose(0.01189401, r.ParasiticDragCoefficient, nameof(r.ParasiticDragCoefficient));
        AssertClose(0.00037353, r.InducedDragCoefficient, nameof(r.InducedDragCoefficient));
        AssertClose(8.91822756, r.LiftDragRatio, nameof(r.LiftDragRatio));
        AssertClose(0.97875465, r.CavitationNumber, nameof(r.CavitationNumber));
        // sigma (0.979) < sigma_i (1.0): the margin is negative -- this operating point is cavitating.
        AssertClose(-0.02124535, r.CavitationMargin, nameof(r.CavitationMargin));
        Assert.True(r.CavitationMargin < 0, "windsurf/race at 28 kn must read as cavitating (margin < 0)");
    }

    // --- Limiting cases and published-table checks (estimation-methods.md, "Consequences") -------------

    [Fact]
    public void Helmbold_ApproachesTwoPiAsAspectRatioGrowsWithoutBound()
    {
        var r = WingEstimator.Estimate(Baseline(aspectRatio: 1.0e6, areaM2: 1.0, speedKnots: 10));
        Assert.True(Math.Abs(r.LiftCurveSlopePerRadian - (2.0 * Math.PI)) < 1e-4,
            $"CL_alpha at AR=1e6 should approach 2*pi; got {r.LiftCurveSlopePerRadian}");
    }

    [Fact]
    public void InducedDrag_MatchesTheEllipticalResultWhenSpanEfficiencyIsOne()
    {
        // AR=8, e=1, CL=0.5 by construction (S=1 m^2, rho=1000 kg/m^3, V=1 m/s, W=250 N):
        // CD_i = CL^2 / (pi * AR) = 0.25 / (8*pi) = 0.009947183943243459.
        var inputs = new WingEstimateInputs(
            AspectRatio: 8.0,
            ProjectedAreaM2: 1.0,
            ThicknessChordRatio: 0.1,
            SpanEfficiency: 1.0,
            SectionLiftCoefficient: 0.3,
            SectionDragCoefficient: 0.012,
            SectionMinimumPressureCoefficient: -1.0,
            SpeedMetresPerSecond: 1.0,
            WeightNewtons: 250.0,
            FluidDensityKgPerM3: 1000.0,
            FluidKinematicViscosityM2PerS: 1.0e-6,
            VapourPressurePascal: 2339.0,
            AtmosphericPressurePascal: AtmosphericPressure,
            DepthMetres: 0.0);
        var r = WingEstimator.Estimate(inputs);
        AssertClose(0.5, r.LiftCoefficient, nameof(r.LiftCoefficient));
        AssertClose(0.009947183943243459, r.InducedDragCoefficient, nameof(r.InducedDragCoefficient));
    }

    [Fact]
    public void SkinFriction_MatchesThePublishedIttcValueAtReynolds1e7()
    {
        // AR=1, S=1 m^2 => chord = 1 m; V=10 m/s, nu=1e-6 m^2/s => Re = 1e7 exactly.
        // Cf = 0.075 / (log10(1e7) - 2)^2 = 0.075 / 25 = 0.003 (the ITTC 1957 correlation line).
        var inputs = new WingEstimateInputs(
            AspectRatio: 1.0,
            ProjectedAreaM2: 1.0,
            ThicknessChordRatio: 0.1,
            SpanEfficiency: 0.85,
            SectionLiftCoefficient: 0.3,
            SectionDragCoefficient: 0.012,
            SectionMinimumPressureCoefficient: -1.0,
            SpeedMetresPerSecond: 10.0,
            WeightNewtons: 100.0,
            FluidDensityKgPerM3: 1000.0,
            FluidKinematicViscosityM2PerS: 1.0e-6,
            VapourPressurePascal: 2339.0,
            AtmosphericPressurePascal: AtmosphericPressure,
            DepthMetres: 0.0);
        var r = WingEstimator.Estimate(inputs);
        AssertClose(1.0e7, r.ReynoldsNumber, nameof(r.ReynoldsNumber));
        AssertClose(0.003, r.SkinFrictionCoefficient, nameof(r.SkinFrictionCoefficient));
    }

    [Fact]
    public void SectionLiftDragRatio_IsTheUnmodifiedInputPolarRatio()
    {
        var inputs = Baseline(aspectRatio: 7.0, areaM2: 0.14, speedKnots: 10) with
        {
            SectionLiftCoefficient = 0.3,
            SectionDragCoefficient = 0.012,
        };
        var r = WingEstimator.Estimate(inputs);
        AssertClose(25.0, r.SectionLiftDragRatio, nameof(r.SectionLiftDragRatio));
    }

    // --- Monotonicity ------------------------------------------------------------------------------------

    [Fact]
    public void RequiredAngleOfAttack_IncreasesMonotonicallyWithWeight()
    {
        double[] weights = { 400.0, 700.0, 931.63175, 1200.0 };
        var previous = double.NegativeInfinity;
        var previousCl = double.NegativeInfinity;
        foreach (var w in weights)
        {
            var inputs = Baseline(aspectRatio: 5.0, areaM2: 0.18, speedKnots: 7) with { WeightNewtons = w };
            var r = WingEstimator.Estimate(inputs);
            Assert.True(r.LiftCoefficient > previousCl, "CL must increase monotonically with weight");
            Assert.True(r.RequiredAngleOfAttackDegrees > previous, "required alpha must increase monotonically with weight");
            previous = r.RequiredAngleOfAttackDegrees;
            previousCl = r.LiftCoefficient;
        }
    }

    [Fact]
    public void LiftCoefficientAndCavitationNumber_DecreaseMonotonicallyWithSpeed()
    {
        double[] speedsKnots = { 5.0, 10.0, 15.0, 20.0 };
        var previousCl = double.PositiveInfinity;
        var previousSigma = double.PositiveInfinity;
        foreach (var speedKnots in speedsKnots)
        {
            var r = WingEstimator.Estimate(Baseline(aspectRatio: 7.0, areaM2: 0.14, speedKnots: speedKnots));
            Assert.True(r.LiftCoefficient < previousCl, "CL must fall as speed rises (fixed weight)");
            Assert.True(r.CavitationNumber < previousSigma, "cavitation number must fall as speed rises");
            previousCl = r.LiftCoefficient;
            previousSigma = r.CavitationNumber;
        }
    }

    // --- Argument validation ------------------------------------------------------------------------------

    public static IEnumerable<object[]> InvalidInputMutations()
    {
        yield return new object[] { "AspectRatio<=0", (Func<WingEstimateInputs, WingEstimateInputs>)(i => i with { AspectRatio = 0.0 }) };
        yield return new object[] { "ProjectedAreaM2<=0", (Func<WingEstimateInputs, WingEstimateInputs>)(i => i with { ProjectedAreaM2 = -1.0 }) };
        yield return new object[] { "ThicknessChordRatio<=0", (Func<WingEstimateInputs, WingEstimateInputs>)(i => i with { ThicknessChordRatio = 0.0 }) };
        yield return new object[] { "ThicknessChordRatio>=1", (Func<WingEstimateInputs, WingEstimateInputs>)(i => i with { ThicknessChordRatio = 1.0 }) };
        yield return new object[] { "SpanEfficiency<=0", (Func<WingEstimateInputs, WingEstimateInputs>)(i => i with { SpanEfficiency = 0.0 }) };
        yield return new object[] { "SpanEfficiency>1", (Func<WingEstimateInputs, WingEstimateInputs>)(i => i with { SpanEfficiency = 1.5 }) };
        yield return new object[] { "SectionDragCoefficient<=0", (Func<WingEstimateInputs, WingEstimateInputs>)(i => i with { SectionDragCoefficient = 0.0 }) };
        yield return new object[] { "SpeedMetresPerSecond<=0", (Func<WingEstimateInputs, WingEstimateInputs>)(i => i with { SpeedMetresPerSecond = 0.0 }) };
        yield return new object[] { "WeightNewtons<0", (Func<WingEstimateInputs, WingEstimateInputs>)(i => i with { WeightNewtons = -1.0 }) };
        yield return new object[] { "FluidDensityKgPerM3<=0", (Func<WingEstimateInputs, WingEstimateInputs>)(i => i with { FluidDensityKgPerM3 = 0.0 }) };
        yield return new object[] { "FluidKinematicViscosityM2PerS<=0", (Func<WingEstimateInputs, WingEstimateInputs>)(i => i with { FluidKinematicViscosityM2PerS = 0.0 }) };
        yield return new object[] { "AtmosphericPressurePascal<=0", (Func<WingEstimateInputs, WingEstimateInputs>)(i => i with { AtmosphericPressurePascal = 0.0 }) };
        yield return new object[] { "DepthMetres<0", (Func<WingEstimateInputs, WingEstimateInputs>)(i => i with { DepthMetres = -0.1 }) };
    }

    [Theory]
    [MemberData(nameof(InvalidInputMutations))]
    public void Estimate_RejectsEachInvalidInput(string name, Func<WingEstimateInputs, WingEstimateInputs> mutate)
    {
        var inputs = mutate(Baseline(aspectRatio: 5.0, areaM2: 0.18, speedKnots: 7));
        Assert.Throws<ArgumentOutOfRangeException>(() => WingEstimator.Estimate(inputs));
    }
}
