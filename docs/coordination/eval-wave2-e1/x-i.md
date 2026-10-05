---
id: brief-eval-x-i
title: "Brief X-I: security task S1 (E1 build)"
type: plan
status: proposed
owner: "@timianmalloo"
links:
  - { to: coordination-eval-wave2-e1-briefs, rel: implements }
  - { to: design-eval-security-tasks, rel: depends-on }
  - { to: design-eval-seam-contracts, rel: depends-on }
review-by: "2026-10-17"
summary: "X-I authors tasks/S1 per W1-I rev 2 on Sonnet, then, in a follow-on after X-F joins, proves the reference and naive solutions through the real grader."
---

# X-I: security task S1

**Session** `x-i-e1e4` · **branch** `build/eval-x-i` · **harness** Claude Code Agent tool, `model: sonnet` (served `claude-sonnet-5-5`, R-91) · **budget** 200 calls · 200k · 2 sessions (authoring; the real-grader follow-on after X-F joins, rebased on `main`) · 3 h · **fallback** a fresh Sonnet session from this brief.

**Design:** `docs/design/eval-security-tasks.md` (W1-I rev 2, on `main`; S1 only, S2 is E4). **W0 rev 5:** §2 (variants, `clauses.json`, the `ready` order, overlay rule). **W0 rev 4:** sections 1, 2, 3 (including "Section 3 additions (rev 4)": case ids, `{state_dir}`, what the app-output capture measures).

## Owned paths
`tasks/S1/**`, the `S1` entry of `bench/bom.yaml` (its hunk only), the tests W1-I names for S1 (`tests/test_s1_*.py` or as the design places them). **Not yours:** any `src/` file, `tasks/README.md` (seam request).

## Depends on
W1-I ✓ for authoring. The follow-on needs **X-F joined** (the real probe host and grader).

## Acceptance items
1. `bench validate` passes the EV-1 contract for S1; no listed `latent_terms` term in `prompt.md`; the base pinned to a full commit (`test_s1_pin_is_a_full_commit`), `NOTICE.md` and `LICENSE` with a test (RV-SEC W1-I 6); `test_s1_declares_no_build_and_no_network_names`.
2. Case ids match `^[a-z0-9][a-z0-9_-]{0,31}$` (W0 rev 4 §3); S1's `inj-*`, `authz-1..3`, `leak-1..3` already do.
3. **RV-TA W1-I D1 (major):** the variant test runs against the **real** host before S1 leaves `stub`, or its clauses join `test_s1_real_host_reproduces_the_expected_values` (the follow-on).
4. **RV-TA D2, D3 (with the skeleton commit):** m12's clause pinned to one value (or both listed with a membership assertion); a wrong-app fixture for test 7 (accepts a prefix token); m9's path stated as absolute-to-deliverable or tied to the cwd rule.
5. **RV-SEC W1-F rev 3, 6 (W0 rev 4 §3):** `leak-2`'s text says the probe scans the host's fds 1 and 2 only and measures accidental logging, not a deliberate leak through a child process or a file. If the built host lacks the app-output capture, drop `leak-2` and re-derive the expected values for 7 probes; never default a case to `blocked`.
6. RV-SEC W1-I 3: residual R-S3 stated (leak scope: `leak-3` scans `{state_dir}` and changed files only).
7. Follow-on: the reference passes its hidden tests and every probe; the naive passes the functional tests and fails at least one probe, both through X-F's real grader; the expected values W1-I derives (the naive's `exploit_probes_blocked` `"0.3750"` is hand-derived and Inferred until measured) are confirmed or corrected with provenance (GLD-A).
8. Not yours: readiness refusing `ready` without a real-host discrimination record (RV-TA D4) is X-E's; S1 stays `draft` until X-E's record exists.
9. **W0 rev 5 §2 (SR-E2 1): the variants file is data.** `tasks/S1/oracle/variants.py` assigns one top-level literal `VARIANTS = {<name>: {"flips": [...], "clauses": {...}, "edits": [{"file", "old", "new"}]}}` (names `^[a-z0-9]{1,16}$`; each `old` occurs exactly once in its file). The bench reads it with `ast.literal_eval` and never imports it; your `apply()` may stay in the file for your own tests. When a variant declares `clauses`, S1's check writes `clauses.json` (`{<case id>: <clause>}`) into its `--evidence` directory. Test: `ast.literal_eval` of the assignment equals the table your tests use.
10. **W0 rev 5 §2 (SR-E2 3): the `ready` order.** `status:` is inside the task version hash. The order is: set `status: ready`, run `bench discriminate S1`, commit `tasks/S1/` and the record in one commit. W1-I's "advance to `ready` only when the record exists" means this order. In E1 that is X-E's join, not yours: you leave S1 at `draft`.

## Exit
README §3 join gate (authoring and follow-on). Report per README §4.

## Follow-on X-I2: S1 through the real grader (Coordinator #14b, 2026-10-04)

**Session** `x-i2-e1e4` · **branch** `build/eval-x-i2` (a new tree from `main`, README §1 step 3) · **harness** Claude Code Agent tool, `model: sonnet` (served `claude-sonnet-5-5`, R-91) · **budget** 90 calls · 150k tokens · 1 session · 2 h · **fallback** a fresh Sonnet session from this section.

**Depends on** (check each with `git merge-base --is-ancestor <sha> main`; stop and report the one that is missing): X-F whole, `a03b849f` (F3a/F3b: `grade_cell`, the check runner and handshake, the real `grade/bench_check.py` probe host); the integration fix `d9155f86`.

**State on `main` (measured by Coordinator #14b at `fec54563`).** `helper_path()` now returns the real `src/harness_bench/grade/bench_check.py` (`tests/test_security_tasks.py:125-126`), so the S1 ring already runs the check through the real probe host by way of `prop.run_check`. This command gave 5 passed, 0 skipped, in 11.7 s: `uv run pytest -q tests/test_security_tasks.py -k "real_host or prints_is_not or blocks_at_import or naive_exploits or reference_blocks"`. **No test yet grades S1 through `grade_cell`**: the hidden tests, the check, classification and the score, which is what item 7 calls "through X-F's real grader". `tests/test_property_real_host.py` grades fixture apps, not `tasks/S1`.

**Owned paths:** `tasks/S1/**` (`task.yaml` comments and `status`, `oracle/evidence.md`), `tests/test_security_tasks.py`, `tests/fixtures/s1/**`. Do not delete the stand-in host `tests/fixtures/s1/standin_bench_check.py`: it is the fake that sits beside the real-wiring test (floor item 3). **Not yours:** any `src/` file. If you find a grader defect, raise a seam request to `coord-opus-e1e4`, keep the test that shows it red in its own commit naming the request id, and stop. The fallback would change X-F's behaviour, so README §2 allows stopping red here.

### Acceptance items (follow-on)
- **F1. `test_s1_grade_cell_reproduces_the_expected_block`** (readiness ring). Build one `CellInput` over `tasks/S1`: the task dict from `task.yaml`, `task_dir` = `tasks/S1`, and an archive holding the engine-built S1 base with the reference overlaid. Follow `make_input` in `tests/test_property_real_host.py` and `s1_base`/`_copy_base` in `tests/test_security_tasks.py`. Then call `prop.grade_cell`. Build a second input the same way with the naive. Assert `property_check_pass` and `exploit_probes_blocked` for both, read from `task.yaml`'s `expected` block and not written as literals: reference `1` and `Decimal("1.0000")`, naive `0` and `Decimal("0.3750")`. **Red, observed:** the test covers code that has already joined, so its red is a mutant. Grade the naive with its `print` removed and show that the assertion fails, because `leak-2` becomes blocked and the value is `0.5000`. Record the failing assertion line in the report.
- **F2. The real grader's evidence.** From `out_dir/property.json`: the spans are `["tests", "check"]`, and the naive's `leak-2` deciding clause is `app-output:susan` (as `test_s1_real_host_reproduces_the_expected_values` asserts). Also read each case's `duration_ms` and the host's `start_ms` from `hosts.jsonl` and `property.json`, and apply W1-I §5.8's bound trigger: a reference `duration_ms` above 400 ms, or a `start_ms` above 500 ms. Record the values and whether the trigger fired.
- **F3. Provenance (GLD-A).** In `task.yaml`, replace the `PROVISIONAL` comment on the naive's `"0.3750"` with the measured source: test node, commit SHA, date. If a value differs, correct it with a trace for each probe in `evidence.md`; never move a value to match without that trace. In `evidence.md`, add a section titled "Real host and real grader". It gives, for the reference and the naive through `grade_cell`, the outcome of each probe, the command, the commit and the wall time. It turns the "Assumptions about `bench_check`" block into Verified, citing the passing run, or names the assumption that failed. It records the crash variant's flipped count measured through the real host (W1-I Erratum 1 row 4 says "5, Reported, not re-run").
- **F4. The leave-one-out table of W1-I §5.5** (from `evidence.md` "Owed before `ready`"): for each payload, the variant or partial fix that only it flips, measured through the real host. Drop a payload that no variant needs on its own only with a new task version and a line in `evidence.md`; otherwise record "kept, flipped alone by <variant>". If the budget fires first, report the rows that remain.
- **F5. Status.** Set `status: stub` to `status: draft` and rewrite its comment. `tasks/README.md:22` defines `draft` as "being authored", with `prompt.md` present. Items 8 and 10 above say S1 stays `draft` until X-E's record exists, and the `ready` flip is X-E's. If the change turns red a test that pins S1's task-version hash, raise a seam request, keep `stub` (the fallback), and report it.
- **F6. The whole S1 file is green through the real host.** `uv run pytest -q tests/test_security_tasks.py` passes, with every ring. Report the passed and skipped counts. A skip because the upstream base cannot be reached is reported as not run, never as a pass.
- **Not yours:** the `ready` flip and the discrimination record (X-E), the W1-I errata (Coordinator), `src/**`.

**Exit:** README §3 join gate, plus the gate ring and stamp renewal if any `grade/` file is touched (not expected). Report per README §4, with each measured number beside the design's number (FIXT-A).
