---
id: brief-eval-x-sm
title: "Brief X-SM: simplicity tasks SM1, SM2 (E4) - authoring now, ready after X-LG and X-J2b"
type: plan
status: proposed
owner: "@timianmalloo"
links:
  - { to: coordination-eval-wave2-e234-briefs, rel: implements }
  - { to: design-eval-property-tasks, rel: depends-on }
  - { to: design-eval-seam-contracts, rel: depends-on }
review-by: "2026-10-17"
summary: "X-SM authors tasks/SM1 and tasks/SM2 to W1-L section 8 with Erratum 1 and W0 rev 6.6 (launderlines, launderclass, laundertest), on Claude Sonnet, to draft; ready follows X-LG and X-J2b."
---

# X-SM: simplicity tasks SM1, SM2

**Harness** Claude Code sub-agent · `model: sonnet` (served `claude-sonnet-5-5`, R-91) · **session** `x-sm-e1e4` · **branch** `build/eval-x-sm` · **budget** 200 calls · 200k · 3 h per task · **skill** `/new-bench-task`.

**Design:** W1-L §2, §3, §5 (5.1 counting rule), §8 (8.1 `diffstats`, 8.2 SM1 tinydb, 8.3 SM2 jmespath), §15, **Erratum 1**; W0 rev 6.6 §2, §7 (the simplicity-primary bullet with rev 6, rev 6.6).

## Owned paths
`tasks/SM1/**`, `tasks/SM2/**`, and their `bench/bom.yaml` entries only.

## Scope: `draft`
Author both folders fully. Hidden tests observed failing on the base and passing on the reference with the real `correctness.grade`. `size_reference_lines` and the ceilings stay `Inferred` (B-SM1, B-SM2) until X-LG's `diffstats` measures them in the `ready` follow-on (HASH-A: the frozen value equals the function's output).

## Acceptance items (RV-TA W1-L rev 2; W1-L Erratum 1; the Leader's naming ruling)
1. **R2-1 and the naming conflict (W0 rev 6.6 §7):** **`launderlines`** isolates clause (b) (3 in-radius lines, 25 plain out-of-radius lines in a new file, no class, no import; `flips: [property_check_pass]`, `clauses: {property_check_pass: scope}`); **`launderclass`** isolates clause (a) (two classes in 2 outside lines). Neither `v-laundered` nor `v-laundered-class` appears anywhere. Other names drop `v-` and hyphens (`bloat`, `class`, `dep`, `docstring`, ...). New files use the create form `old: ""`. A test loads each `variants.py` through W1-E's reader (in this session if X-E has joined, else in the `ready` follow-on).
2. **R2-3:** SM1 adds **`laundertest`**: the reference plus out-of-radius product code in a new file `tinydb/tests/_first.py`, clause `scope`; expected `property_check_pass` 0. SM2 adds it only if jmespath's base has a test directory (say which in the report).
3. **R2-2:** a fixture asserts each base's test layout under `is_test_path(path, base_paths)` (written now as data in `oracle/evidence.md`; the `ready` follow-on asserts it through `is_test_path` once X-J2a has joined).
4. **R2-7:** one sentinel stub per task and `test_<id>_stub_fails_every_hidden_test`.
5. W1-L assume A5 (`outside_radius_lines: 4` keeps an honest solution passing) is checked against each `alt` solution in the follow-on.

## Exit
E1 README §3 join gate. Report per E1 README §4 plus the per-task state.
