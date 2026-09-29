# D2 oracle evidence

## Pinned base and vendor selection

`git -C C:/projects/ai-de rev-parse 88e0c33f` exited 0, returning
`88e0c33f0b7c419b1e64d87686987374285292d8` — the same commit D1 (the worked pattern) vendors.
`git -C C:/projects/ai-de ls-tree -r --name-only 88e0c33f -- src/AiDe.Core/Extraction/` exited 0
and listed 24 files, confirming the blast radius (`src/AiDe.Core/Extraction/**`) exists at the pin.

The workspace was built the same way as D1's — `git archive --format=zip 88e0c33f... -- <the same
vendored_paths> <the same two :(exclude) pathspecs>` from `C:/projects/ai-de`, extracted into
`tasks/D2/workspace/`. `diff -rq tasks/D1/workspace tasks/D2/workspace` exited 0 with no output:
byte-for-byte identical, 531 files — expected, since D1 and D2 pin the same repo and commit with
the same vendoring rule. `rg -n -F -f bench/pack-markers.txt tasks/D2/workspace tasks/D2/tests
tasks/D2/oracle tasks/D2/prompt.md tasks/D2/task.yaml` returned no matches (`rg` exit 1). A grep for
an operator home-directory path or e-mail address across the same set found one pre-existing hit —
`tasks/D2/workspace/tests/AiDe.Core.Tests/Composer/TheVocabularyIsClosedTests.cs:283`, a fictional
Windows-user-profile-shaped string literal (a `.env` path under a made-up account named "secret")
used as sample fixture data at the pinned commit itself. It is not an operator path: the same
byte-identical line exists in D1's already-`ready` workspace at the same commit, and, being under
`tests/AiDe.Core.Tests/` (a `vendored_paths` entry), `validate_task`'s profile-path scan skips it —
only this non-vendored evidence file would trip that scan by repeating the literal, so it is
described here instead of quoted. No e-mail address was found anywhere in the scanned set.

## Hidden xUnit discrimination through the shared grader

Command: `uv run python tasks/D2/oracle/probe.py`. The probe calls
`harness_bench.grade.correctness.grade` twice. For the reference call, it copies `workspace/` and
overlays only `oracle/reference/src/AiDe.Core/Extraction/ImportOriginRule.cs`. The shared grader
then overlays `tasks/D2/tests/` into its own disposable grading copy. The reference never enters the
agent workspace.

The `task.yaml` oracle command is
`["dotnet", "test", "D2.HiddenTests/D2.HiddenTests.csproj", "-p:RestoreSources=.",
"-p:NuGetAudit=false", "--logger", "trx;LogFileName=d2-hidden.trx", "--results-directory",
"TestResults", "-v:q"]` — invoked directly, no `cmd.exe`, forward-slash path. `NuGet.Config` clears
package sources and names only the grading copy. The grader recorded `dotnet --version` as
`10.0.303` on both calls.

| Grading copy | dotnet exit | Named TRX | xUnit result | `correctness.grade` result |
| --- | ---: | --- | --- | --- |
| Pinned base | 1 | `TestResults/d2-hidden.trx` | 20 failed, 0 passed, 0 skipped | `passed=0`, `partial_credit=0`, `reason=None` |
| Reference overlay | 0 | `TestResults/d2-hidden.trx` | 0 failed, 20 passed, 0 skipped | `passed=1`, `partial_credit=1`, `reason=None` |

Failing test names on the base (all 20; `[Theory]` cases collapsed to the parent test name):

- `ClassifiesRuntimeAndStandardLibraryModulesAsBuiltin` (5 cases)
- `ClassifiesRelativeOrPathShapedSpecifiersAsWorkspaceEvenWhenUnknown` (5 cases)
- `ClassifiesAnExactWorkspaceModuleIdAsWorkspace`
- `DoesNotNormalizeBetweenSpecifierTextAndModuleIdText`
- `ClassifiesUnknownBareSpecifiersAsExternal` (4 cases)
- `BuiltinRuleOutranksWorkspaceMembershipForTheSameSpecifier`
- `RejectsAnUnknownLanguage`
- `RejectsAnEmptySpecifier`
- `RejectsNullArguments`

The base failures are runtime xUnit failures: the hidden test project compiles without the new
`ImportOriginRule`/`ImportOrigin` types (accessed only through reflection, including a
`.ToString()` comparison for the enum so the test project needs no compile-time reference to it),
then each test's `Assert.NotNull(type)`/`Assert.NotNull(method)` reports their absence. The named
TRX is parsed by `correctness.grade`; a build failure before a TRX would be NA and would not
satisfy this evidence — the log confirms `dotnet test` produced the TRX on both runs (`Results
File: ... d2-hidden.trx` on both the base and the reference run).

## Mutation discrimination (this task's own proof, not the shared mutation grader)

Command: `uv run python tasks/D2/oracle/mutants.py`. Each of six named mutants overlays the
reference implementation with one localized text change, then runs the same shared correctness
grader used above.

| Mutant | `passed` | Failing hidden test(s) |
| --- | --- | --- |
| `python-relative-ignored` | 0 | `ClassifiesRelativeOrPathShapedSpecifiersAsWorkspaceEvenWhenUnknown` (python cases) |
| `node-absolute-path-not-relative` | 0 | `ClassifiesRelativeOrPathShapedSpecifiersAsWorkspaceEvenWhenUnknown` (node `/abs/path` case) |
| `builtin-checked-after-workspace` | 0 | `BuiltinRuleOutranksWorkspaceMembershipForTheSameSpecifier` |
| `unknown-language-not-rejected` | 0 | `RejectsAnUnknownLanguage` |
| `empty-specifier-not-rejected` | 0 | `RejectsAnEmptySpecifier` |
| `external-and-workspace-swapped` | 0 | `ClassifiesAnExactWorkspaceModuleIdAsWorkspace`, `ClassifiesUnknownBareSpecifiersAsExternal` (all 4 cases), `DoesNotNormalizeBetweenSpecifierTextAndModuleIdText` |

All six mutants are killed (`passed=0` in every row): `correctness.grade` reports the mutant workspace
as failing, exactly as the pinned base does. Each mutant's failing set is disjoint from every other
mutant's except where one test legitimately guards more than one branch
(`external-and-workspace-swapped` breaks three tests because flipping the final ternary breaks both
the `External` fallback and, incidentally, workspace-id matching's return value), so no hidden test
is redundant with the mutation suite it is meant to guard: each of the 9 named tests is the sole or
joint killer of at least one mutant.

## Reference solution's size and time against the 45-minute budget

The reference implementation is 1 file, 51 lines
(`src/AiDe.Core/Extraction/ImportOriginRule.cs`, one enum plus one static classification method),
reusing the two existing builtin-list lookups (`PythonStandardLibrary.Contains`,
`NodeBuiltinModules.Contains`) rather than authoring new domain data. `dotnet test` itself completes
in well under one second against both the base and the reference (`Duration: 72 ms` / `62 ms` in
the probe's own log) — the oracle's own run time, not an agent's authoring time; it evidences that
grading itself has no material effect on the 45-minute cell budget.

assume: an agent completes this task within the 45-minute budget with wide headroom, on the basis
that D1 (the worked pattern for this same scenario, same repo, same commit, a comparable
single-file pure-function slice using only existing types) fits the same 45-minute budget, and D2's
reference is smaller (51 lines, one file, no records/DTOs to design, no sort/cap/disclosure
logic — a decision-table classification over two already-existing lookups) with tests supplied as
hidden, not authored by the agent. **Confirm:** the first real cell's `duration_seconds` (report row
20) against this task once run in a harness. **Breaks if false:** the budget in `bench/bom.yaml`
(45 min) and `task.yaml` needs raising; not observed with a live agent run in this worktree
(out of scope for a task-authoring session, per the brief's Not-in-scope: "running the task in a
real harness").

## Offline restore

assume: the grading host has the dependencies in its NuGet global packages cache at
`%USERPROFILE%\.nuget\packages` (or `NUGET_PACKAGES` when set). Confirmed on this host: both
`probe.py` calls restored and built with `RestoreSources=.` and `NuGet.Config` naming only the
workspace-local source, with no package registry configured in the grading copy (the same pins
D1/D3/F1 already document; `Directory.Packages.props` is unchanged from D1's workspace). If false on
a different host, restore fails and the grader returns NA.
