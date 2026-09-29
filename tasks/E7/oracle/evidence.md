# E7 oracle evidence

## Pinned base and vendor selection

`git ls-remote https://github.com/timianmalloo/cfd-bench.git HEAD` exited 0, returning
`496a0a8ca2fae9026927167a8f3e5da0a53f2233` — confirming this is both F1's pin and the repo's current
`HEAD`, so no newer commit exists to require. A shallow clone of that commit
(`git clone --depth 1`) was taken; `git rev-parse HEAD` inside it returned the same hash.
`find src -maxdepth 3` inside the clone returned nothing: the repository carries no source code at
this commit. `diff --strip-trailing-cr` between the clone's
`docs/knowledge/cfd-hydrofoil-simulation/estimation-methods.md` and `data-and-constants.md` and the
copies already vendored under `tasks/F1/workspace/docs/knowledge/cfd-hydrofoil-simulation/` printed
no differences beyond line endings: content identical.

## Formula verification against the source document's own worked table

A verification script (Python, ephemeral, not shipped with this task) implemented every formula
named in `prompt.md` / `oracle/README.md` and ran it against all 12 rows of
`estimation-methods.md`'s "The chain executed" table (4 disciplines x 3 speeds each). Every
computed value matched the table's own displayed precision for `Re`, `CL`, `α_eff` (required angle
of attack), `CD_0`, `CD_i`, `L/D` and `σ`:

```
surf     7kn  Re=    574556(exp     574556)  CL=0.778(exp 0.778)  a=10.48(exp 10.5)  CD0=0.0134(exp 0.0134)  CDi=0.0453(exp 0.0454)  LD=13.2(exp 13.2)  sigma=15.7(exp 15.7)
surf    10kn  Re=    820795(exp     820795)  CL=0.381(exp 0.381)  a=5.13(exp 5.1)   CD0=0.0124(exp 0.0124)  CDi=0.0109(exp 0.0109)  LD=16.4(exp 16.4)  sigma=7.7(exp 7.7)
surf    13kn  Re=   1067033(exp    1067033)  CL=0.226(exp 0.226)  a=3.04(exp 3.0)   CD0=0.0117(exp 0.0117)  CDi=0.0038(exp 0.0038)  LD=14.5(exp 14.5)  sigma=4.5(exp 4.5)
wing    10kn  Re=    611784(exp     611784)  CL=0.490(exp 0.49)   a=5.93(exp 5.9)   CD0=0.0132(exp 0.0132)  CDi=0.0129(exp 0.0129)  LD=18.8(exp 18.8)  sigma=7.7(exp 7.7)
wing    15kn  Re=    917676(exp     917676)  CL=0.218(exp 0.218)  a=2.63(exp 2.6)   CD0=0.0121(exp 0.0121)  CDi=0.0025(exp 0.0025)  LD=14.9(exp 14.9)  sigma=3.4(exp 3.4)
wing    20kn  Re=   1223568(exp    1223568)  CL=0.123(exp 0.123)  a=1.48(exp 1.5)   CD0=0.0114(exp 0.0114)  CDi=0.0008(exp 0.0008)  LD=10.1(exp 10.1)  sigma=1.9(exp 1.9)
sup     10kn  Re=    442777(exp     442777)  CL=0.624(exp 0.624)  a=6.87(exp 6.9)   CD0=0.0143(exp 0.0143)  CDi=0.0139(exp 0.0139)  LD=22.2(exp 22.2)  sigma=7.7(exp 7.7)
sup     14kn  Re=    619888(exp     619888)  CL=0.318(exp 0.318)  a=3.51(exp 3.5)   CD0=0.0132(exp 0.0132)  CDi=0.0036(exp 0.0036)  LD=18.9(exp 18.9)  sigma=3.9(exp 3.9)
sup     18kn  Re=    796998(exp     796998)  CL=0.193(exp 0.193)  a=2.12(exp 2.1)   CD0=0.0125(exp 0.0125)  CDi=0.0013(exp 0.0013)  LD=14.0(exp 14.0)  sigma=2.4(exp 2.4)
wind    16kn  Re=    565142(exp     565142)  CL=0.335(exp 0.335)  a=3.61(exp 3.6)   CD0=0.0135(exp 0.0135)  CDi=0.0035(exp 0.0035)  LD=19.7(exp 19.7)  sigma=3.0(exp 3.0)
wind    22kn  Re=    777070(exp     777070)  CL=0.177(exp 0.177)  a=1.91(exp 1.9)   CD0=0.0125(exp 0.0125)  CDi=0.0010(exp 0.001)   LD=13.1(exp 13.1)  sigma=1.6(exp 1.6)
wind    28kn  Re=    988998(exp     988998)  CL=0.109(exp 0.109)  a=1.18(exp 1.2)   CD0=0.0119(exp 0.0119)  CDi=0.0004(exp 0.0004)  LD=8.9(exp 8.9)   sigma=1.0(exp 1.0)
```

`Cf@Re=1e7 = 0.075/(log10(1e7)-2)^2 = 0.003` (the ITTC 1957 published table value used directly in
the isolated `SkinFriction_...` hidden test). `CL_alpha` at `AR = 1e6`: `6.283172740821538`, against
`2*pi = 6.283185307179586` (difference `1.26e-5`, well inside the test's `1e-4` tolerance) — the
"Helmbold at AR→∞ must approach 2π" limiting case from `estimation-methods.md`'s own "Consequences"
section.

## Hidden xUnit discrimination through the shared grader

Command: `uv run python tasks/E7/oracle/probe.py`. The probe calls
`harness_bench.grade.correctness.grade` twice: once on `workspace/` (the base stub) and once on a
copy with `oracle/reference/src/CfdBench.Core/Estimation/WingEstimator.cs` overlaid over the
stub. The shared grader then overlays `tasks/E7/tests/` into its own disposable grading copy; the
reference never enters the agent workspace.

The `task.yaml` oracle command is
`["dotnet", "test", "E7.HiddenTests/E7.HiddenTests.csproj", "-p:RestoreSources=.",
"-p:NuGetAudit=false", "--logger", "trx;LogFileName=e7-hidden.trx", "--results-directory",
"TestResults", "-v:q"]` — invoked directly, no `cmd.exe`, forward-slash path. `NuGet.Config` clears
package sources and names only the grading copy. Both calls recorded `dotnet --version` as
`10.0.303`.

| Grading copy | dotnet exit | Named TRX | xUnit result | `correctness.grade` result | Duration |
| --- | ---: | --- | --- | --- | ---: |
| Base (stub) | 1 | `TestResults/e7-hidden.trx` | 23 failed, 0 passed, 0 skipped | `passed=0`, `partial_credit=0`, `reason=None` | 31 ms |
| Reference overlay | 0 | `TestResults/e7-hidden.trx` | 0 failed, 23 passed, 0 skipped | `passed=1`, `partial_credit=1`, `reason=None` | 32 ms |

All 23 hidden tests fail on the base (every field access throws `NotImplementedException`) and all
23 pass on the reference. A build failure before a named TRX would be NA under DR-G4, not a 0; both
runs produced the named TRX, so this is a genuine 0/23 vs 23/23, not an infrastructure gap.

## Mutation discrimination (this task's own proof, not the shared mutation grader)

Command: `uv run python tasks/E7/oracle/mutants.py`. Each of six named mutants overlays the
reference implementation with one localized text change to one named formula or validation guard,
then runs the same shared correctness grader used above.

| Mutant | `passed` | `partial_credit` | Failing hidden test(s) |
| --- | ---: | ---: | --- |
| `helmbold-wrong-constant` | 0 | 19/23 | `SupDownwind10Knots_...`, `WindsurfRace28Knots_...`, `SurfFoiling7Knots_...`, `WingFoiling20Knots_...` |
| `ittc-natural-log-not-log10` | 0 | 18/23 | the same four regressions, plus `SkinFriction_MatchesThePublishedIttcValueAtReynolds1e7` |
| `hoerner-missing-quartic-term` | 0 | 19/23 | the same four regressions (`ParasiticDragCoefficient` off by ~0.7%, well outside the 1e-5 tolerance) |
| `induced-drag-missing-pi` | 0 | 18/23 | the same four regressions, plus `InducedDrag_MatchesTheEllipticalResultWhenSpanEfficiencyIsOne` |
| `cavitation-margin-sign-flipped` | 0 | 21/23 | `SupDownwind10Knots_...`, `WindsurfRace28Knots_...` (the two regressions that assert `CavitationMargin`) |
| `negative-weight-not-rejected` | 0 | 22/23 | `Estimate_RejectsEachInvalidInput(name: "WeightNewtons<0", ...)` |

All six mutants are killed (`passed=0` in every row). Each mutant's failing set traces to the exact
formula step it corrupts: `helmbold-wrong-constant` and `hoerner-missing-quartic-term` are caught
only by the four table regressions (they do not touch the isolated ITTC or elliptical-induced-drag
cases, which use different `AspectRatio`/`ThicknessChordRatio` values chosen precisely to isolate
one step each); `ittc-natural-log-not-log10` and `induced-drag-missing-pi` are additionally caught
by the isolated single-formula test built for that exact step; `cavitation-margin-sign-flipped` is
caught only by the two regressions that assert `CavitationMargin`; `negative-weight-not-rejected` is
caught only by its own argument-validation case. No hidden test is redundant with the mutation suite
it is meant to guard.

## Reference solution's size and time against the 45-minute budget

The reference implementation is 1 file, 205 lines (`src/CfdBench.Core/Estimation/WingEstimator.cs`,
including a 55-line XML-doc header restating the chain, two `readonly record struct` types and one
static method with 13 argument-validation guards and a 10-step formula chain, no external
dependencies). `dotnet test` itself completes in 31-32 ms against both the base and the reference
through the shared grader (`evidence.md` table above) and in 93-96 ms on a cold direct invocation
(build + test, `dotnet test tasks/E7/tests/E7.HiddenTests/E7.HiddenTests.csproj ...` run directly
from this worktree) — the oracle's own run time, not an agent's authoring time; it evidences that
grading itself has no material effect on the 45-minute cell budget.

assume: an agent completes this task within the 45-minute budget with wide headroom, on the basis
that the reference is a single file with no new data structures to design (the two record types are
already given in `workspace/`), a closed-form chain with every formula and every input named
verbatim in `prompt.md`, and 13 straightforward argument-validation guards — comparable in scope to
E6 (a 20-minute batch of 10 HumanEval-C# problems) and smaller in design surface than D1/D2 (which
also fit 45 minutes). **Confirm:** the first real cell's `duration_seconds` (report row 20) against
this task once run in a harness. **Breaks if false:** the budget in `bench/bom.yaml` (45 min) and
`task.yaml` needs raising; not observed with a live agent run in this worktree (out of scope for a
task-authoring session, per the brief's Not-in-scope: "running the task in a real harness").

## Offline restore

Both `probe.py` calls (base and reference) restored and built with `RestoreSources=.` and
`NuGet.Config` naming only the workspace-local source, with no package registry configured in the
grading copy, using the host's NuGet global-packages cache (the same pins D1/D2/D3/E6/F1 already
document). No package source other than `.` was consulted in either run.

## No real secrets, customer data or private content

`tasks/E7/` contains no vendored third-party code (the pinned commit carries none to vendor), no
credentials, no personal data and no content beyond this task's own authored C# and Markdown.
