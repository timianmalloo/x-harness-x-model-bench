# P0 wing spine — architecture note

This note fixes the architecture for the first slice of the hydrofoil design tool's Phase 0
("conventions and spine"): a `Wing` aggregate and the planform quantities derived from it. It is
the contract you build against. The public shape below is already declared in the workspace as
stubs; your job is to fill in their bodies so the hidden tests pass.

## Bounded context

Wing planform geometry. Pure domain code: no UI, no file format, no solver, no geometry export.

## Ubiquitous language

- **Station** — one cross-section of a half-wing, at a distance from the centreline, with a chord.
  A value object (`CfdBench.Core.Domain.Station`, already implemented).
- **Wing** — the aggregate. A symmetric wing described by the stations of one half, root first.
  Bounded by the invariants below. Already declared in
  `src/CfdBench.Core/Domain/Wing.cs` as a stub — implement `Create` and back `Stations` with the
  aggregate's own defensive copy of the input.
- **Length**, **Area** — value objects in `CfdBench.Core.Units` (already implemented). Units live
  in the type system, not in comments or bare `double`s.
- **WingDerivations** — a stateless domain service: one producer per planform quantity, each a
  pure function of a `Wing`. Already declared in `src/CfdBench.Core/Derivations/WingDerivations.cs`
  as a stub — implement the four producers. Derive, don't store: no quantity here is cached on the
  aggregate.

## Wing aggregate invariants (enforced by `Wing.Create`)

1. At least two stations (root and tip).
2. The first station is the root and lies on the centreline: `SpanPosition.Metres == 0`.
3. Span positions strictly increase from station to station.
4. Every chord is strictly positive.
5. The aggregate keeps its own copy of the stations, in the order given — a caller mutating the
   list passed to `Create` afterwards must not change the wing.

A violated invariant throws `ArgumentException` (a null `stations` argument throws
`ArgumentNullException`).

## Derived quantities (the four producers)

A wing is symmetric about its centreline; the stations describe one half. Chord varies linearly
with span position between adjacent stations, so each segment's contribution is exact:
`∫ c dy = Δy (c0 + c1) / 2` over that segment.

- **Span `b`** — tip to tip, both halves: twice the tip station's span position.
- **Projected area `S`** — the planform area of both halves: twice the sum of each segment's
  trapezoid, `Δy (c0 + c1) / 2`.
- **Aspect ratio** — `b² / S`.
- **Mean geometric chord** — `S / b`.

Every producer rejects a null `Wing` argument with `ArgumentNullException`.

## What is already given (do not change its public contract)

- `src/CfdBench.Core/Units/Quantities.cs` — `Length` and `Area`. Each factory rejects a NaN or
  infinite value with `ArgumentException`.
- `src/CfdBench.Core/Domain/Station.cs` — the `Station` value object.

## What you implement

- `src/CfdBench.Core/Domain/Wing.cs` — `Wing.Create` and the backing storage for `Stations`.
- `src/CfdBench.Core/Derivations/WingDerivations.cs` — `Span`, `ProjectedArea`, `AspectRatio`,
  `MeanGeometricChord`.

The whole task fits a 40-minute budget.
