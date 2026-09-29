# B2 oracle evidence

Grading copy matches `src/harness_bench/grade/correctness.py`: the tree under test, then `tests/test_b2_hidden.py` overlaid, cwd = that copy. The reference spec stays in `oracle/reference/` and is not in `workspace/`.

The vendored primer/context is `workspace/docs/architecture.md`. It is the `git show <commit>:docs/architecture.md` blob at `88e0c33f0b7c419b1e64d87686987374285292d8` (`git -C C:\projects\ai-de rev-parse HEAD`, 2026-09-18; same pin as D1/D2, which vendor the same ai-de commit for their own slices). 1279 lines, sha256 `62e13cac0ca2cfe5eb93879e785c48a690d0458e0fa4bdf698e68bda5b888875`, UTF-8 with LF endings (no `.gitattributes` override needed, unlike B1's CRLF HTML blob). `workspace/LICENSE` is the same commit's MIT license text, matching D1/D2's license record.

Run for all four cases below: `python -m unittest -v test_b2_hidden` with `test_b2_hidden.py` copied alongside a `docs/specs/freshness-prober.md` (or none, for the base case).

## Fail on the base workspace

Command (cwd = copy of `tasks/B2/workspace` plus `tests/test_b2_hidden.py`; `workspace/` has no `docs/specs/`):

```
python -m unittest -v test_b2_hidden
```

Exit code: **1**

Summary: `Ran 4 tests` / `FAILED (failures=4)`

Failing names (all four — the spec file itself is missing):

- `test_spec_file_present` (FAIL) — `docs/specs/freshness-prober.md` is missing
- `test_spec_required_sections` (FAIL) — same
- `test_comparison_source_is_the_repository_not_the_daemon` (FAIL) — same
- `test_prober_does_not_repair_the_drift_itself` (FAIL) — same

## Pass on the reference

Command (cwd = copy of `tasks/B2/oracle/reference/` plus `tests/test_b2_hidden.py`):

```
python -m unittest -v test_b2_hidden
```

Exit code: **0**

Summary: `Ran 4 tests` / `OK`. No failing names.

## Content-check discrimination: one plausible wrong answer per check

Two fixtures, each a complete, structurally-passing spec (all 7 headings present and non-empty) that is wrong on exactly one decided fact. Quoted in full in `README.md`. Not committed — evidence is this run record.

**Wrong answer 1** (self-referential comparison — compares against "the daemon's last known state" instead of the repository):

```
python -m unittest -v test_b2_hidden
```

Exit code: **1**. Summary: `Ran 4 tests` / `FAILED (failures=1)`.

- `test_spec_file_present` ... ok
- `test_spec_required_sections` ... ok
- `test_prober_does_not_repair_the_drift_itself` ... ok
- `test_comparison_source_is_the_repository_not_the_daemon` (FAIL) — "spec does not state the repository (not the daemon's own last-event view) is the comparison source"

**Wrong answer 2** (the prober re-runs extraction itself to fix the drift):

```
python -m unittest -v test_b2_hidden
```

Exit code: **1**. Summary: `Ran 4 tests` / `FAILED (failures=1)`.

- `test_spec_file_present` ... ok
- `test_spec_required_sections` ... ok
- `test_comparison_source_is_the_repository_not_the_daemon` ... ok
- `test_prober_does_not_repair_the_drift_itself` (FAIL) — "spec does not state that the prober itself never repairs/fixes the drift"

Each content check fails on the one wrong answer that gets its fact wrong, and only that one — confirming the checks are independent and each is load-bearing, not a keyword any on-topic text would satisfy.

## Status

`ready`. The skill checklist holds: source repo and commit are pinned (same ai-de commit as D1/D2), `prompt.md` is present, `workspace/` holds the primer context (`docs/architecture.md`, `LICENSE`), `tests/` and `oracle/` are non-empty, and the hidden tests fail on the base workspace and pass on the reference spec, with the two content checks each individually discriminating against a plausible wrong answer.
