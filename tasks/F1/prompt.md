# P0 wing spine as three coordinated tracks

This repository holds the research and planning documents for a hydrofoil design tool (`docs/`). It has no code yet. Build the first slice of Phase 0, "conventions and spine" (`docs/proposals/build-phasing-plan.html`, section 03): define a wing and get its span, area, aspect ratio and mean chords out of it, with tests that prove they are right. Units live in the type system, not in comments. Pure domain code: no UI, no file format, no solver, no geometry export.

## Tracks and model routing

Run the work as three coordinated tracks. You coordinate: plan the tracks, start one sub-agent per track on the model named below, arbitrate between them, and integrate the result. Do not author track work yourself.

| Track | Owns | Model |
| --- | --- | --- |
| `domain-model` | `src/CfdBench.Core/CfdBench.Core.csproj`, `src/CfdBench.Core/Units/**`, `src/CfdBench.Core/Domain/**` | `claude-opus-5-5` |
| `derived-quantities` | `src/CfdBench.Core/Derivations/**` | `claude-sonnet-5` |
| `tests` | `tests/**` | `claude-sonnet-5` |

No two tracks write the same file. The public contract below is the seam between the tracks, so `derived-quantities` and `tests` can start against it before `domain-model` finishes. A track that needs a change outside its own paths asks you; you decide and record the decision. If a sub-agent cannot be started on its named model, say so when it happens, run it on the nearest model you can, and record which model each track actually used. Never substitute silently.

## Public contract

One class library, `src/CfdBench.Core/CfdBench.Core.csproj`, targeting `net10.0`, with the assembly name `CfdBench.Core`.

`CfdBench.Core.Units` (track `domain-model`):

- `Length`: `static Length FromMetres(double)`, `static Length FromMillimetres(double)`, property `double Metres`.
- `Area`: `static Area FromSquareMetres(double)`, property `double SquareMetres`.
- `Angle`: `static Angle FromDegrees(double)`, `static Angle FromRadians(double)`, properties `double Degrees` and `double Radians`.
- Every factory rejects a NaN or infinite value with `ArgumentException`.

`CfdBench.Core.Domain` (track `domain-model`):

- `Station`, constructed as `new Station(Length spanPosition, Length leadingEdgeX, Length chord, Angle twist)`, with properties `SpanPosition`, `LeadingEdgeX`, `Chord` and `Twist`.
- `Wing`: `static Wing Create(IReadOnlyList<Station> stations)` and property `IReadOnlyList<Station> Stations`.

`CfdBench.Core.Derivations.WingDerivations` (track `derived-quantities`), a static class with one producer per quantity:

- `Length Span(Wing wing)`
- `Area ProjectedArea(Wing wing)`
- `double AspectRatio(Wing wing)`
- `Length MeanGeometricChord(Wing wing)`
- `Length MeanAerodynamicChord(Wing wing)`
- `Angle Washout(Wing wing)`

Every public method rejects a null argument with `ArgumentNullException`.

## Conventions

- A wing is symmetric about its centreline. Its stations describe one half, from the root outward. `SpanPosition` is the distance from the centreline. The first station is the root, at span position zero, and span positions strictly increase.
- `LeadingEdgeX` is positive aft. `Chord` is strictly positive. `Twist` is the station's incidence, positive nose-up.
- Between adjacent stations, chord varies linearly with span position.
- `Wing.Create` rejects fewer than two stations, a first station off the centreline, span positions that do not strictly increase, and a chord that is not strictly positive, each with `ArgumentException`. The wing keeps its own copy of the stations, in the order given.

## Definitions

- Span `b`: tip to tip, both halves: twice the tip station's span position.
- Projected area `S`: the planform area of both halves, the integral of chord over span. Chord is not foreshortened by twist, and sweep does not change it.
- Aspect ratio: `b² / S`.
- Mean geometric chord: `S / b`.
- Mean aerodynamic chord: `(2 / S) ∫ c(y)² dy` over one half-span.
- Washout: root twist minus tip twist, positive when the tip is nose-down relative to the root.

## Tests

The `tests` track adds an xUnit project, `tests/CfdBench.Core.Tests/`, that proves each definition against analytic reference cases, for example a rectangular wing and a linearly tapered wing, with stated tolerances. Use the package versions `Microsoft.NET.Test.Sdk` 17.14.1, `xunit` 2.9.3 and `xunit.runner.visualstudio` 3.1.4.

The whole task fits a 60-minute budget, coordination included.
