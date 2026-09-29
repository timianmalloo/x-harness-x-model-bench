# D3 oracle

D3 is the scenario-4 task: the P0 wing spine from a given architecture (`docs/architecture-note.md`
plus interface stubs), a single agent implementing the `Wing` aggregate and its four planform
producers within a 40-minute budget. Nothing in this folder except `workspace/` reaches the agent.

## Source and licence

`source.commit` is `496a0a8ca2fae9026927167a8f3e5da0a53f2233`, the same cfd-bench commit F1 pins —
the pattern task sharing this repo. At that commit cfd-bench holds documents and one Python tool;
it has no C# code (F1's `oracle/README.md`). So, unlike D1 (which vendors ai-de's existing code
byte for byte), D3's workspace is authored net-new content: an architecture note and C# interface
stubs that fix the P0 wing spine contract, referencing the pinned commit for provenance rather than
vendoring bytes from it. `task.yaml` carries no `vendored_paths` for this reason, and
`oracle/vendoring_check.py` does not apply here (there is nothing in cfd-bench to check workspace
bytes against). `source.license` repeats the operator's 2026-09-25 ruling that cfd-bench is their
own repository and proceeds without a licence file (the same ruling F1 records).

The workspace itself is scanned for pack markers, forbidden paths and user-profile/e-mail leakage
the same way as D1/F1: `rg -n -F -f bench/pack-markers.txt tasks/D3/workspace` (no matches, `rg`
exit 1) and a manual read of every file (six files: one architecture note, one `.csproj`, four
`.cs` files, all authored fresh in this worktree, none containing a path under a user profile or an
e-mail address).

## Correctness: the hidden tests

`tests/D3.HiddenTests/` holds 6 xUnit tests over the contract in `prompt.md` /
`docs/architecture-note.md`. Unlike D1/F1, the base workspace already declares `CfdBench.Core`
with `Wing` and `WingDerivations` as stubs (`NotImplementedException` bodies), so the hidden test
project references it unconditionally and the base **builds**; every behavioural test then fails
at run time when it calls a stub. A compile-only failure would grade NA under DR-G4, not 0 — this
task's base is a runtime failure, which is a 0.

Reference values come from the same closed forms F1 already verified with Python `fractions`
(`S = 2 Σ Δy (c0 + c1) / 2`), restricted to the four quantities D3's row names (span, projected
area, aspect ratio, mean geometric chord — no mean aerodynamic chord, no washout, since D3 has no
`Angle`/twist in its architecture):

| Case | Stations (y m, c m) | b | S | AR | MGC |
| --- | --- | --- | --- | --- | --- |
| rectangular | (0, 0.1), (0.5, 0.1) | 1 | 1/10 | 10 | 1/10 |
| tapered, λ = 0.5 | (0, 0.2), (0.6, 0.1) | 6/5 | 9/50 | 8 | 3/20 |
| cranked | (0, 0.25), (0.2, 0.2), (0.5, 0.08) | 1 | 87/500 | 500/87 | 87/500 |

Tolerance: 1e-9, relative to max(1, |expected|) — the same as F1.

The reference in `reference/src/CfdBench.Core/` (only `Domain/Wing.cs` and
`Derivations/WingDerivations.cs`: `Units/Quantities.cs` and `Domain/Station.cs` are given,
unchanged, already correct in `workspace/`) passes all 6 tests. Six mutants of it are each killed
(`mutants.py`, `evidence.md`): span without doubling, area by max-chord instead of mean-chord,
aspect ratio without squaring the span, mean chord inverted, no defensive copy of the station list,
and equal span positions allowed.

## What is not built in this slice

Later waves: mutation grading (the shared grader, not this task's own `mutants.py`, which is only
the discrimination proof) should reuse the six mutants above as a seed set; the rigor and
architecture graders are not built.

## Offline restore

assume: the grading host's NuGet global packages folder (`%USERPROFILE%\.nuget\packages`, or
`NUGET_PACKAGES` when set) holds `Microsoft.NET.Test.Sdk` 17.14.1, `xunit` 2.9.3,
`xunit.runner.visualstudio` 3.1.4 and their dependencies — the same pins D1 and F1 use, so the same
host cache serves all three tasks. **Confirm:** both probe calls restored from `RestoreSources=.`
on this host with no NuGet source configured (observed, `evidence.md`). **Breaks if false:** on a
fresh grading host, restore fails and the grader returns NA
`infrastructure failure before build: restore`; seeding that cache is a harness setup step, as for
D1/F1.

## macOS (ADR-0013 Amendment 1)

assume: this task runs natively on macOS unchanged — the workspace is portable C#/.NET (net10.0,
no Windows-only API), and the only Windows-specific piece is the oracle's `cmd.exe /c
D3.HiddenTests\run.cmd` wrapper and its backslash path, mirroring D1/F1 exactly. **Confirm:** run
`dotnet test tasks/D3/tests/D3.HiddenTests -p:RestoreSources=. -p:NuGetAudit=false` directly on a
macOS host with the same NuGet cache pins seeded, and observe the same 0/6 on the base and 6/6 on
the reference. **Breaks if false:** the oracle command needs a POSIX-shell variant before D3 can
run on macOS, the same open item ADR-0013 Amendment 1 records for the engine as a whole. Not
measured here (no macOS host in this worktree).
