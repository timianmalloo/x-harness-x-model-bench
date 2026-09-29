# F2 oracle evidence

## Pinned base and vendor selection

`git -C C:/projects/ai-de rev-parse 88e0c33f` exited 0 and returned
`88e0c33f0b7c419b1e64d87686987374285292d8` — the same commit D1 (the worked pattern for this
feature) and D2 vendor. `git -C C:/projects/ai-de ls-tree -r --name-only 88e0c33f --
src/AiDe.Core/Projections/` exited 0 and listed 13 files, none named `EvidenceCensusProjection.cs`,
confirming both that `blast_radius` (`src/AiDe.Core/Projections/**`) exists at the pin and that the
feature is genuinely absent from the base (the discrimination proof below observes this at build
time too).

`tasks/F2/workspace/` was built by copying `tasks/D1/workspace/` (`cp -r`), not by a fresh
`git archive`, since D1 and D2 already proved that commit's vendored set is identical for both
tasks and F2 pins the same commit for the same reason (the feature under test is D1's). Verified
independently for F2: `find tasks/F2/workspace -type f | wc -l` → 531; workspace size 5,272,935
bytes; `diff -rq tasks/F2/workspace tasks/D1/workspace` exits 0 with no output. Same two exclusions
as D1/D2 (`DreamCorpusReader.cs` and its test — the AI-Forward Pack marker in their source
comments). `rg -n -F -f bench/pack-markers.txt tasks/F2/workspace tasks/F2/tests tasks/F2/oracle
tasks/F2/prompt.md tasks/F2/task.yaml` returned no matches (`rg` exit 1).

## Hidden xUnit discrimination through the shared grader

Command: `uv run python tasks/F2/oracle/probe.py`.

```
base: passed=0 partial=0 reason=None
$ dotnet --version
exit 0
10.0.303
$ dotnet test F2.HiddenTests/F2.HiddenTests.csproj -p:RestoreSources=. -p:NuGetAudit=false --logger trx;LogFileName=f2-hidden.trx --results-directory TestResults -v:q
exit 1
Failed!  - Failed:     5, Passed:     0, Skipped:     0, Total:     5, Duration: 26 ms - F2.HiddenTests.dll (net10.0)
[xUnit.net]     EvidenceCensusHiddenTests.EmptySnapshotStillCarriesItsRevision [FAIL]
[xUnit.net]     EvidenceCensusHiddenTests.CapsBucketsButKeepsFullTotalsAndDisclosesOmissions [FAIL]
[xUnit.net]     EvidenceCensusHiddenTests.CountsEveryInputWithoutCollapsingOriginOrVerificationStatus [FAIL]
[xUnit.net]     EvidenceCensusHiddenTests.SortsByCountThenOrdinalPredicateThenEnumValues [FAIL]
[xUnit.net]     EvidenceCensusHiddenTests.RejectsNullInputs [FAIL]

reference: passed=1 partial=1 reason=None
$ dotnet --version
exit 0
10.0.303
$ dotnet test F2.HiddenTests/F2.HiddenTests.csproj -p:RestoreSources=. -p:NuGetAudit=false --logger trx;LogFileName=f2-hidden.trx --results-directory TestResults -v:q
exit 0
Passed!  - Failed:     0, Passed:     5, Skipped:     0, Total:     5, Duration: 31 ms - F2.HiddenTests.dll (net10.0)
```

(First run of the probe failed the *reference* build with `CS0246: The type or namespace name
'EvidenceOrigin' could not be found` in `EvidenceCensusContract.cs` — the split-file reference was
missing `using AiDe.Core.Facts;`, since D1's original single-file reference had it at the top of the
one file that used both the using directive and the types. Fixed by adding the `using` to
`EvidenceCensusContract.cs`; the transcript above is the corrected re-run.)

| Grading copy | dotnet exit | Named TRX | xUnit result | `correctness.grade` result |
| --- | ---: | --- | --- | --- |
| Pinned base | 1 | `TestResults/f2-hidden.trx` | 5 failed, 0 passed, 0 skipped | `passed=0`, `partial_credit=0`, `reason=None` |
| Reference overlay | 0 | `TestResults/f2-hidden.trx` | 0 failed, 5 passed, 0 skipped | `passed=1`, `partial_credit=1`, `reason=None` |

The base failures are runtime xUnit failures: the hidden test project compiles without the new
projection (reflection reports the absent types/members), then the named TRX is parsed by
`correctness.grade`. A build failure before a TRX would be NA under DR-G4, not a 0; this task's base
is a runtime failure, which is a 0, and its reference build succeeds and produces the same named
TRX.

## Mutation discrimination (this task's own proof, not the shared mutation grader)

Command: `uv run python tasks/F2/oracle/mutants.py`. Each of six named mutants overlays the
reference implementation with one localized text change, then runs the same shared correctness
grader used above.

```
ascending-count-sort: passed=0 partial=0.6 reason=None failed=['EvidenceCensusHiddenTests.CountsEveryInputWithoutCollapsingOriginOrVerificationStatus', 'EvidenceCensusHiddenTests.SortsByCountThenOrdinalPredicateThenEnumValues']
cap-unclamped: passed=0 partial=0.8 reason=None failed=['EvidenceCensusHiddenTests.CapsBucketsButKeepsFullTotalsAndDisclosesOmissions']
status-ignored-in-grouping: passed=0 partial=0.8 reason=None failed=['EvidenceCensusHiddenTests.CountsEveryInputWithoutCollapsingOriginOrVerificationStatus']
null-query-check-removed: passed=0 partial=0.8 reason=None failed=['EvidenceCensusHiddenTests.RejectsNullInputs']
revision-not-preserved: passed=0 partial=0.8 reason=None failed=['EvidenceCensusHiddenTests.EmptySnapshotStillCarriesItsRevision']
no-disclosure-ever: passed=0 partial=0.8 reason=None failed=['EvidenceCensusHiddenTests.CapsBucketsButKeepsFullTotalsAndDisclosesOmissions']
```

All six mutants are killed (`passed=0` in every row); between them every one of the 5 hidden tests
is the sole or joint killer of at least one mutant (`oracle/README.md`'s table).

**Two earlier mutant attempts, dropped, not reported as evidence:**

- A first `status-ignored-in-grouping` attempt (`.GroupBy(a => (a.Predicate, a.Origin,
  VerificationStatus.Verified))`, without a `Status:` element name) failed to build:
  `status-ignored-in-grouping: passed=None partial=None reason='named TRX result file missing'`.
  C#'s tuple-element-name inference names an element from a member access (`a.Status` → `Status`)
  but not from a static-member literal (`VerificationStatus.Verified` infers `Verified`), so
  `group.Key.Status` in the unchanged `.Select(...)` no longer compiled. Fixed by naming the tuple
  element explicitly (`Status: VerificationStatus.Verified`).
- A first mutant removing `ArgumentNullException.ThrowIfNull(assertions)` (rather than `query`) was
  run and observed **not** to discriminate: `null-check-removed: passed=1 partial=1 reason=None
  failed=[]`. `Enumerable.GroupBy`'s own BCL implementation already throws `ArgumentNullException`
  for a `null` source, so the reference's own explicit check on `assertions` is redundant with that
  guard for this exact code shape, and `RejectsNullInputs`' assertions-argument case cannot tell the
  two apart. Replaced with a mutant on the `query` null check instead (`query.MaxRows` has no such
  BCL backstop — a `null` `query` there throws `NullReferenceException`, which
  `Assert.IsType<ArgumentNullException>` correctly rejects), confirmed above as
  `null-query-check-removed`.

## Reference solution's size and time against the 60-minute budget

`wc -l tasks/F2/oracle/reference/src/AiDe.Core/Projections/EvidenceCensusContract.cs
tasks/F2/oracle/reference/src/AiDe.Core/Projections/EvidenceCensusProjection.cs`: 19 + 30 = 49 lines
total across the two reference files. `dotnet test` duration in the probe's own log: 31 ms
(reference) / 26 ms (base) — the oracle's own run time, not an agent's authoring time.

## Offline restore

Confirmed on this host: both `probe.py` calls (and all six `mutants.py` calls) restored and built
with `RestoreSources=.` and `tests/NuGet.Config` naming only the workspace-local source, with no
package registry configured in the grading copy — the same pins D1/D2/D3/F1 already document.

## bench validate

`uv run bench validate` → `ok: bom, metrics, example matrix and every task folder are valid`.
