using System;

namespace CfdBench.Core.Estimation;

/// <summary>
/// P1 estimator slice: the closed-form pre-simulation chain that turns a wing definition, a 2D section
/// polar point, an operating condition and a fluid into L/D, Cl/Cd, required angle of attack and
/// cavitation margin. Every step below is one named, published closed form. No simulation, no UI, no
/// file I/O; the whole chain is meant to run in microseconds. DTIC experimental validation of the
/// resulting numbers is out of scope for this slice.
///
/// The chain, in order:
///
/// 1. Three-dimensional lift-curve slope (Helmbold, 1942), for a finite unswept wing in incompressible
///    flow, per radian:
///      CL_alpha = 2*pi*AspectRatio / (2 + sqrt(AspectRatio^2 + 4))
///
/// 2. Target 3D lift coefficient from force balance: the wing must support WeightNewtons at
///    SpeedMetresPerSecond:
///      CL = WeightNewtons / (0.5 * FluidDensityKgPerM3 * SpeedMetresPerSecond^2 * ProjectedAreaM2)
///
/// 3. Required angle of attack, measured from the zero-lift line (the Helmbold slope already relates CL
///    to angle measured that way), radians converted to degrees:
///      RequiredAngleOfAttackDegrees = degrees(CL / CL_alpha)
///
/// 4. Reynolds number, chord-based, using the mean geometric chord of a rectangular-equivalent planform
///    (MeanChordMetres = sqrt(ProjectedAreaM2 / AspectRatio), since AspectRatio = Span^2 / Area and
///    Area = Span * MeanChord):
///      Re = SpeedMetresPerSecond * MeanChordMetres / FluidKinematicViscosityM2PerS
///
/// 5. Skin friction, the ITTC 1957 model-ship correlation line:
///      Cf = 0.075 / (log10(Re) - 2)^2
///
/// 6. Form factor (Hoerner) and parasitic drag, with S_wet/S_ref = 2.06 for a thin wing:
///      (1 + k) = 1 + 2*ThicknessChordRatio + 60*ThicknessChordRatio^4
///      ParasiticDragCoefficient = (1 + k) * Cf * 2.06
///
/// 7. Induced drag (lifting line), where SpanEfficiency is the Oswald span efficiency factor
///    (e = 1 is the elliptical-loading limit):
///      InducedDragCoefficient = CL^2 / (pi * SpanEfficiency * AspectRatio)
///
/// 8. Assemble the 3D wing totals:
///      DragCoefficient = ParasiticDragCoefficient + InducedDragCoefficient
///      LiftDragRatio   = CL / DragCoefficient
///
/// 9. Cavitation number at depth DepthMetres, and the section's incipient cavitation number from its
///    minimum pressure coefficient:
///      sigma          = (p0 - VapourPressurePascal) / (0.5 * FluidDensityKgPerM3 * SpeedMetresPerSecond^2)
///                       where p0 = AtmosphericPressurePascal + FluidDensityKgPerM3 * 9.80665 * DepthMetres
///      sigma_i        = -SectionMinimumPressureCoefficient      (incipient cavitation occurs when sigma
///                                                                 falls to sigma_i)
///      CavitationMargin = sigma - sigma_i   (positive: the operating point is clear of cavitation at
///                                             this speed and depth; zero or negative: cavitating)
///
/// 10. Section-only (2D) lift-to-drag, an unmodified echo of the input polar point, reported alongside
///     the assembled 3D LiftDragRatio so the cost of the 3D induced-drag correction is visible:
///       SectionLiftDragRatio = SectionLiftCoefficient / SectionDragCoefficient
///
/// Source: cfd-bench docs/knowledge/cfd-hydrofoil-simulation/estimation-methods.md (Helmbold, ITTC 1957,
/// Hoerner form factor, lifting-line induced drag, the cavitation critical-speed rule) and
/// data-and-constants.md (Re, sigma, CL/CD definitions), at commit 496a0a8ca2fae9026927167a8f3e5da0a53f2233.
/// </summary>
public static class WingEstimator
{
    public static WingEstimateResult Estimate(WingEstimateInputs inputs)
    {
        throw new NotImplementedException();
    }
}

/// <summary>Inputs to the P1 estimator chain. All quantities are SI unless the name says otherwise.</summary>
public readonly record struct WingEstimateInputs(
    double AspectRatio,
    double ProjectedAreaM2,
    double ThicknessChordRatio,
    double SpanEfficiency,
    double SectionLiftCoefficient,
    double SectionDragCoefficient,
    double SectionMinimumPressureCoefficient,
    double SpeedMetresPerSecond,
    double WeightNewtons,
    double FluidDensityKgPerM3,
    double FluidKinematicViscosityM2PerS,
    double VapourPressurePascal,
    double AtmosphericPressurePascal,
    double DepthMetres);

/// <summary>Every intermediate and final quantity the chain produces, in the order it is computed.</summary>
public readonly record struct WingEstimateResult(
    double LiftCurveSlopePerRadian,
    double LiftCoefficient,
    double RequiredAngleOfAttackDegrees,
    double ReynoldsNumber,
    double SkinFrictionCoefficient,
    double FormFactor,
    double ParasiticDragCoefficient,
    double InducedDragCoefficient,
    double DragCoefficient,
    double LiftDragRatio,
    double SectionLiftDragRatio,
    double CavitationNumber,
    double IncipientCavitationNumber,
    double CavitationMargin);
