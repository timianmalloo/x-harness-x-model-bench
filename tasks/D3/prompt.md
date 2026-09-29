# P0 wing spine from a given architecture

Implement the `Wing` aggregate and its derived planform quantities against the given architecture.
Read `docs/architecture-note.md` first: it fixes the bounded context, the aggregate's invariants,
and the definitions and formulas for the derived quantities. The public contract is already
declared in the workspace as stubs; fill in their bodies.

Given, already implemented — do not change their public contract:

- `src/CfdBench.Core/Units/Quantities.cs` — `Length` and `Area`.
- `src/CfdBench.Core/Domain/Station.cs` — the `Station` value object.

To implement:

- `src/CfdBench.Core/Domain/Wing.cs` — `Wing.Create(IReadOnlyList<Station> stations)` and the
  backing storage for `Stations`. Enforce the invariants in the architecture note: at least two
  stations, the first on the centreline, span positions strictly increasing, every chord strictly
  positive, and the aggregate keeps its own copy of the stations in the order given. A violated
  invariant throws `ArgumentException`; a null `stations` argument throws `ArgumentNullException`.
- `src/CfdBench.Core/Derivations/WingDerivations.cs` — the four producers, each a pure function of
  a `Wing`, each rejecting a null argument with `ArgumentNullException`:
  - `Length Span(Wing wing)`
  - `Area ProjectedArea(Wing wing)`
  - `double AspectRatio(Wing wing)`
  - `Length MeanGeometricChord(Wing wing)`

Pure domain code: no UI, no file format, no solver, no geometry export. The whole task fits a
40-minute budget.
