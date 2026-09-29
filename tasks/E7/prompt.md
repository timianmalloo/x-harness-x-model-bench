# P1 Estimator Slice

Implement `WingEstimator.Estimate` in `src/CfdBench.Core/Estimation/WingEstimator.cs`. It is the
closed-form pre-simulation chain for a 3D hydrofoil wing: given a wing's geometry, a 2D section
polar point and an operating condition, compute the 3D lift-to-drag ratio, the section's own
lift-to-drag ratio, the angle of attack required to fly at the given speed, and the cavitation
margin at the given speed and depth. No simulation, no file I/O, no UI — every step is a published
closed form and the whole chain should run in microseconds.

The two record types (`WingEstimateInputs`, `WingEstimateResult`) are already defined in the file;
do not change their shape. Replace the `throw new NotImplementedException();` body of `Estimate`
with the chain below, and validate every input first: on an invalid input, throw
`ArgumentOutOfRangeException`.

## Inputs

- `AspectRatio` — the wing's aspect ratio, must be positive.
- `ProjectedAreaM2` — the wing's projected planform area, in square metres, must be positive.
- `ThicknessChordRatio` — the section's thickness-to-chord ratio, must be strictly between 0 and 1.
- `SpanEfficiency` — the Oswald span efficiency factor, must be in the range (0, 1]; 1 is the
  elliptical-loading limit.
- `SectionLiftCoefficient`, `SectionDragCoefficient` — the 2D section's own lift and drag
  coefficients at the operating angle of attack and Reynolds number (e.g. from an XFOIL polar).
  `SectionDragCoefficient` must be positive.
- `SectionMinimumPressureCoefficient` — the section's `Cp_min` at that operating point (typically
  negative).
- `SpeedMetresPerSecond` — the wing's forward speed through the fluid, must be positive.
- `WeightNewtons` — the force, in newtons, the wing must support at that speed, must not be
  negative.
- `FluidDensityKgPerM3`, `FluidKinematicViscosityM2PerS` — the fluid's density and kinematic
  viscosity, both must be positive.
- `VapourPressurePascal` — the fluid's vapour pressure.
- `AtmosphericPressurePascal` — the ambient pressure at the free surface, must be positive.
- `DepthMetres` — the wing's submergence depth, must not be negative.

## The chain

1. **Three-dimensional lift-curve slope — Helmbold (1942).** For a finite unswept wing in
   incompressible flow, per radian:

   ```
   CL_alpha = 2*pi*AspectRatio / (2 + sqrt(AspectRatio^2 + 4))
   ```

2. **Target lift coefficient**, from force balance — the wing must support `WeightNewtons` at
   `SpeedMetresPerSecond`:

   ```
   CL = WeightNewtons / (0.5 * FluidDensityKgPerM3 * SpeedMetresPerSecond^2 * ProjectedAreaM2)
   ```

3. **Required angle of attack**, measured from the zero-lift line, converted from radians to
   degrees:

   ```
   RequiredAngleOfAttackDegrees = degrees(CL / CL_alpha)
   ```

4. **Reynolds number**, chord-based, using the mean geometric chord
   (`MeanChordMetres = sqrt(ProjectedAreaM2 / AspectRatio)`):

   ```
   Re = SpeedMetresPerSecond * MeanChordMetres / FluidKinematicViscosityM2PerS
   ```

5. **Skin friction — the ITTC 1957 model-ship correlation line:**

   ```
   Cf = 0.075 / (log10(Re) - 2)^2
   ```

6. **Form factor — Hoerner — and parasitic drag**, with a wetted-to-reference-area ratio of 2.06
   for a thin wing:

   ```
   (1 + k) = 1 + 2*ThicknessChordRatio + 60*ThicknessChordRatio^4
   ParasiticDragCoefficient = (1 + k) * Cf * 2.06
   ```

7. **Induced drag — lifting line:**

   ```
   InducedDragCoefficient = CL^2 / (pi * SpanEfficiency * AspectRatio)
   ```

8. **Assemble the 3D wing totals:**

   ```
   DragCoefficient = ParasiticDragCoefficient + InducedDragCoefficient
   LiftDragRatio   = CL / DragCoefficient
   ```

9. **Cavitation.** The cavitation number at depth `DepthMetres`:

   ```
   p0    = AtmosphericPressurePascal + FluidDensityKgPerM3 * 9.80665 * DepthMetres
   sigma = (p0 - VapourPressurePascal) / (0.5 * FluidDensityKgPerM3 * SpeedMetresPerSecond^2)
   ```

   Incipient cavitation occurs when `sigma` falls to the section's incipient cavitation number,
   `sigma_i = -SectionMinimumPressureCoefficient`. Report:

   ```
   CavitationNumber           = sigma
   IncipientCavitationNumber  = sigma_i
   CavitationMargin           = sigma - sigma_i
   ```

   A positive `CavitationMargin` means the operating point is clear of cavitation at this speed
   and depth; zero or negative means it is cavitating.

10. **Section-only (2D) lift-to-drag** — an unmodified echo of the input polar point, reported
    alongside the assembled 3D `LiftDragRatio`:

    ```
    SectionLiftDragRatio = SectionLiftCoefficient / SectionDragCoefficient
    ```

Populate every field of `WingEstimateResult`, including `LiftCurveSlopePerRadian`,
`SkinFrictionCoefficient` and `FormFactor` (the intermediate values computed in steps 1, 5 and 6).

DTIC experimental validation of the resulting numbers against towing-tank data is out of scope for
this slice.
