# D1 oracle

The grading copy starts from `workspace/` and receives `tests/D1.HiddenTests/` only after the model turn. The xUnit project uses reflection so the base project compiles without the requested projection; each behavioral test fails at runtime until the projection exists. The command in `task.yaml` emits the named `d1-hidden.trx`, which the shared dotnet correctness runner parses.

The projection's grain is one row per exact predicate, evidence origin, and verification status in the supplied snapshot. Counts are additive over input assertions. `SourceRevision` is an identifier for that snapshot; this task neither stores counts nor infers history from a later snapshot. The hidden tests cover grouping, ordering, the cap and disclosure, empty input, and null arguments. The reference implementation is in `oracle/reference/`, outside the model workspace.

Later waves: mutation grading should kill changed grouping, sorting, and cap logic; rigor grading should inspect evidence and assumptions; architecture grading should check that the projection remains read-only in Core. These graders are not implemented in this slice.

assume: the grading host has a NuGet global packages cache at `%USERPROFILE%\.nuget\packages` (or at `NUGET_PACKAGES` when set), containing the exact packages in `Directory.Packages.props` and their transitive dependencies. Confirm by running the named oracle command from a fresh grading copy with `RestoreSources=.` and no network access. If false, offline restore fails before tests and correctness is NA; pre-seeding that cache is a harness setup requirement.
