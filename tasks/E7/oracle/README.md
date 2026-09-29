# E7 oracle

E7 is the scenario-5 task: implement the P1 estimator slice — the closed-form chain that turns a
wing definition, a 2D section polar point and an operating condition into L/D, Cl/Cd, required
angle of attack and cavitation margin — within a 45-minute budget. Nothing in this folder except
`workspace/` reaches the agent.

## Source, pin and why no code is vendored

`source.commit` is `496a0a8ca2fae9026927167a8f3e5da0a53f2233` — the same cfd-bench commit F1 (the
pattern task for this repo) pins. `git ls-remote https://github.com/timianmalloo/cfd-bench.git HEAD`
(run 2026-09-29) returned this same commit as `HEAD`, so it is also the newest commit on the
default branch: no newer commit is required, and none is possible without the upstream repo
advancing past the pin F1 already established. A fresh `git clone --depth 1` of that commit was
diffed (`diff --strip-trailing-cr`) against the copies already vendored into `tasks/F1/workspace/`:
`docs/knowledge/cfd-hydrofoil-simulation/estimation-methods.md` and `data-and-constants.md` are
byte-identical modulo line endings, confirming the vendored text is the pin's actual content, not a
paraphrase.

At this commit the repository holds **no `src/` directory at all** (`find src` returns nothing) —
P1 is pre-code, exactly as the proposal's design rule states: "no measured data exists, so the
oracle is a reference implementation we write from the formulas the phasing plan names." There is
therefore nothing to vendor into `workspace/`: the pin identifies the two knowledge documents the
formulas and constants are sourced from, not a code snapshot. `workspace/` instead holds a fresh,
self-authored stub (`WingEstimator.Estimate` throwing `NotImplementedException`) with the two
record types (`WingEstimateInputs`, `WingEstimateResult`) already defined, matching the shape
`prompt.md` names.

## Formulas and their derivation

Every formula in `prompt.md` and `oracle/reference/` is copied verbatim from
`docs/knowledge/cfd-hydrofoil-simulation/estimation-methods.md` (the Helmbold lift-curve slope, the
lifting-line induced-drag formula, the ITTC 1957 skin-friction line, the Hoerner form factor and
`S_wet/S_ref = 2.06`, and the cavitation-number formula with `sigma_i = -Cp_min`) and
`data-and-constants.md` (ITTC seawater properties at 15 degC, `Re = V*c/nu`,
`sigma = (p - p_v)/(0.5*rho*V^2)`, `CL = L/(0.5*rho*V^2*A)`) — each already labelled Verified or
Flagged in those documents with its own citation (Helmbold 1942; ITTC 1957; IHS/Tom Speer for the
cavitation rule; Hoerner's form factor is Flagged there as "standard... but not read from Hoerner's
own text").

**This derivation was checked, not assumed.** `estimation-methods.md` itself carries a worked table
of 12 rows (4 disciplines x 3 speeds) computed by its author from these same formulas. A
verification script (not shipped; ephemeral) implemented every formula above in Python and
reproduced **all 12 rows exactly** — Reynolds number, `CL`, `alpha_eff` (required angle of attack),
`CD_0`, `CD_i`, `L/D` and `sigma` all matched the table to its own displayed precision, given:

- `alpha_required = degrees(CL / CL_alpha)` — the table's own `α_eff` column is exactly this
  quantity (verified numerically for every row; the Helmbold slope is defined relative to the
  zero-lift line, so no separate zero-lift-angle input is needed for this slice), and
- `CL = WeightNewtons / (0.5*rho*V^2*ProjectedAreaM2)`, `WeightNewtons = 95 kg * 9.80665 m/s^2` (the
  doc's stated "rider plus gear 95 kg"), reproducing the table's `CL` column exactly.

Both of these two composite formulas are therefore **Verified by reproduction of the source
document's own numbers**, not merely restated from the prose, which only names the six atomic steps
(Helmbold, lifting-line induced drag, ITTC friction, Hoerner form factor, cavitation critical
speed) and does not spell out how "required alpha" and "the target CL" are assembled from a weight
and a speed. The four hidden-test regression cases (`SurfFoiling7Knots_...`,
`WingFoiling20Knots_...`, `SupDownwind10Knots_...`, `WindsurfRace28Knots_...`) use four of these
same 12 rows verbatim (with `t/c = 0.11`, `e = 0.85`, depth `0.45 m`, exactly as the doc states) as
the primary correctness oracle, at a tight relative tolerance (1e-5).

## Two authored design decisions (not read off the source)

**`Cl/Cd` vs `L/D`.** The proposal's inventory row lists both "L/D" and "Cl/Cd" as separate outputs.
`estimation-methods.md` consistently uses lower-case `Cl`, `Cd` for the 2D section polar (step 1:
"Section data — `Cl`, `Cd`, `Cm`, `Cp_min`") and upper-case `CL`, `CD` for the assembled 3D wing
(step 7: "`CD = CD_0 + CD_i`, `L/D = CL/CD`"). Algebraically `L/D` and the 3D `CL/CD` are the same
number by definition, so reporting both would be the two-definitions-of-one-quantity defect
`domain-and-data-modelling.instructions.md` warns against — unless `Cl/Cd` means the 2D section's
own (unmodified) ratio. **assume:** `SectionLiftDragRatio` (the estimator's `Cl/Cd` output) is the
input polar's own ratio (`SectionLiftCoefficient / SectionDragCoefficient`), reported alongside the
assembled 3D `LiftDragRatio` as a diagnostic of what the induced-drag correction costs, on the basis
of the document's own case convention (checked directly, not inferred from memory: quoted above).
**Confirm:** an authoritative restatement of the E7 inventory row disambiguating the two symbols.
**Breaks if false:** a future revision of this task would need to redefine `SectionLiftDragRatio`
(or drop it) and update the four regression tests' `SectionLiftDragRatio` assertion accordingly; no
other field is affected.

**Cavitation margin.** Neither source document defines "cavitation margin" as a formula; only
`sigma`, `sigma_i` and the practitioner shortcut `V_crit = 14/sqrt(sigma_i)` are given.
**assume:** `CavitationMargin = sigma - sigma_i` (positive: clear of cavitation at this speed and
depth; zero or negative: cavitating) is the definition, chosen because it uses only the two
quantities the source document already derives and Verifies, needs no additional constant, and its
sign is directly checkable (the `WindsurfRace28Knots` regression case is deliberately the one row of
the four, out of the doc's 12, whose `sigma` [0.979] sits below `sigma_i` [1.0] for the illustrative
section used in the hidden tests, giving a negative-margin case the tests assert on explicitly).
**Confirm:** an authoritative restatement of "cavitation margin" from the same source (IHS or an
equivalent). **Breaks if false:** only `CavitationMargin`'s sign convention and the two assertions on
it in `WindsurfRace28Knots_...` and `SupDownwind10Knots_...` would change; `CavitationNumber` and
`IncipientCavitationNumber` (both formula-derived, Verified) are unaffected.

## Correctness: the hidden tests

`tests/E7.HiddenTests/WingEstimatorHiddenTests.cs` holds 23 xUnit test cases (10 `[Fact]`s, one
`[Theory]` with 13 cases):

- **4 exact-value regressions** against `estimation-methods.md`'s own worked table (surf foiling at
  7 kn, wing foiling at 20 kn, SUP/downwind at 10 kn, windsurf/race at 28 kn), asserting
  `ReynoldsNumber`, `LiftCoefficient`, `RequiredAngleOfAttackDegrees`, `ParasiticDragCoefficient`,
  `InducedDragCoefficient`, `LiftDragRatio` and `CavitationNumber` (plus `CavitationMargin`'s sign
  on two of the four) to 1e-5 relative tolerance.
- **Helmbold limiting case:** `CL_alpha` at `AspectRatio = 1e6` must be within `1e-4` of `2*pi`
  (`estimation-methods.md`, "Consequences for the architecture": "Helmbold at AR→∞ must approach
  2π").
- **Elliptical induced drag:** at `SpanEfficiency = 1`, `CD_i` must equal `CL^2/(pi*AspectRatio)`
  exactly for a hand-picked clean case (`CL = 0.5` by construction).
- **ITTC published-table check:** `Cf` at `Re = 1e7` (constructed exactly from `AR = 1`, `S = 1 m^2`,
  `V = 10 m/s`, `nu = 1e-6 m^2/s`) must equal `0.075/(7-2)^2 = 0.003`.
- **`SectionLiftDragRatio`** is the unmodified input ratio.
- **2 monotonicity properties:** required angle of attack and `CL` increase strictly with weight;
  `CL` and `CavitationNumber` decrease strictly with speed.
- **13 argument-validation cases**, one per invalid field (`AspectRatio<=0`, `ProjectedAreaM2<=0`,
  `ThicknessChordRatio` outside `(0,1)` at both ends, `SpanEfficiency` outside `(0,1]` at both ends,
  `SectionDragCoefficient<=0`, `SpeedMetresPerSecond<=0`, `WeightNewtons<0`,
  `FluidDensityKgPerM3<=0`, `FluidKinematicViscosityM2PerS<=0`, `AtmosphericPressurePascal<=0`,
  `DepthMetres<0`), each expecting `ArgumentOutOfRangeException`.

The reference in `oracle/reference/src/CfdBench.Core/Estimation/WingEstimator.cs` (205 lines, one
file) passes all 23. Six named mutants (`mutants.py`, `evidence.md`) are each killed by a disjoint
or partially-overlapping subset of the hidden tests (a mutation to a shared step, e.g. Helmbold or
Hoerner, naturally breaks more than one regression row, exactly as `estimation-methods.md`'s own
"exactly testable" consequence predicts).

## What is not built in this slice

Later waves: mutation grading (the shared grader, not this task's own `mutants.py`, which is only
the discrimination proof); the rigor grader. `grade.py` is not added — the shared `correctness` and
`mutation` graders already cover everything this oracle measures; no task-specific grading logic is
needed, so none is added (a test/grader earns its place only by catching a failure no other check
does).

## Offline restore

assume: the grading host's NuGet global packages folder (`%USERPROFILE%\.nuget\packages`, or
`NUGET_PACKAGES` when set) holds `Microsoft.NET.Test.Sdk`, `xunit`, `xunit.runner.visualstudio` and
their dependencies at the versions `E7.HiddenTests.csproj` pins (17.12.0 / 2.9.2 / 2.8.2) — the same
cache D1/D2/D3/E6/F1 use. **Confirm:** both `probe.py` calls restored from `RestoreSources=.` with
no NuGet source configured (observed on this host, `evidence.md`). **Breaks if false:** on a fresh
grading host, restore fails and the grader returns NA
(`infrastructure failure before build: restore`); seeding that cache is a harness setup step, as for
D1/D2/D3/E6/F1.

## macOS (ADR-0013 Amendment 1)

assume: this task runs natively on macOS unchanged. The workspace is portable C#/.NET (net10.0, no
Windows-only API, no P/Invoke, only `System` and the record types), and — like D2 and unlike
D1/D3/E6/F1's `cmd.exe /c ...\run.cmd` — the oracle command here is
`["dotnet", "test", "E7.HiddenTests/E7.HiddenTests.csproj", ...]`, invoked directly with a
forward-slash path and no shell wrapper, which `harness_bench.grade.correctness.grade` passes to
`procs.run` unshelled on both platforms. **Confirm:** run
`dotnet test tasks/E7/tests/E7.HiddenTests/E7.HiddenTests.csproj -p:RestoreSources=. -p:NuGetAudit=false`
directly on a macOS host with the same NuGet cache pins seeded, from a working copy that also
carries `tasks/E7/tests/NuGet.Config` and `tasks/E7/workspace/src/`, and observe the same 0/23 on
the base and 23/23 on the reference. **Breaks if false:** something in this task's own code is not
macOS-portable, which would be a defect specific to this task rather than the known engine-wide gap
ADR-0013 Amendment 1 records for D1/D3/E6/F1's `cmd.exe` shape. Not measured here (no macOS host in
this worktree).
