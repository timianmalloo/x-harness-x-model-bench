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

## Follow-on X-I4: payload ids as the `inj` clauses (F4; Coordinator #23, 2026-10-05)

**Session** `x-i4-e1e4` · **branch** `build/eval-x-i4`, a new tree from the integration head: from the primary run `python docs/ai-forward-pack/scripts/coord-core.py worktree new --branch build/eval-x-i4 --session x-i4-e1e4 --base integrate/e1e4-17` and record the base SHA (`f58d63b0` or a later integration head) · **harness** Claude Code Agent tool, `model: sonnet` (served `claude-sonnet-5-5`; the served id is the report's first line, R-91) · **budget** 100 calls · 200k tokens · 1 session · 2 h · **fallback** a fresh Sonnet session from this section. Never `EnterWorktree`; never `checkout`/`switch` in the primary; `AGENT_SESSION=x-i4-e1e4` inline on every commit and coord call.

**Why (Coordinator #19 (c), README §8).** F4 is X-I2's leave-one-out table: ten S1 payloads that no candidate needs alone. A drop is decided by a discrimination record over a check that names the payloads that exploited each `inj` probe. Today `inj_1` and `inj_3` return on the first payload that hits and record only a letter (`"a"`, `"b"`, `"body"`; `tasks/S1/oracle/check/check.py:86-104`). So no record can tell `{B2}` from `{B2, B3}`. X-I4 makes the check record the ids, the variants' `clauses` follow, and S1 gets a new task version. Then the Leader runs `discriminate` over the edited check (the J2 record run). That run is not yours.

**Depends on** (check each with `git merge-base --is-ancestor <sha> HEAD` on your base, not `main`; stop and report the one that is missing): X-I3 `6afdf6f7` (variants as data); X-I2 `8a27ba5b` (the leave-one-out table in `oracle/evidence.md`); X-E `041f8692` (the evidence readers) and `852fdf7c` (`readiness.property_evidence` egress-scans `clauses.json` before it parses it: #19's precondition for the record run, met on the line). Coordinator #23 checked all four on `f58d63b0`.

**State on the base (Coordinator #23 opened each at `f58d63b0`).**
- **The check writes no `clauses.json`.** `check()` writes only `s1-probes.json` into `ctx.evidence`. Item 9 above says the check writes `clauses.json` when a variant declares `clauses`, and every S1 variant does. So today every S1 variant fails X-E's discrimination: `discriminate._variant_record` (`src/harness_bench/discriminate.py:207-209`) adds "clauses are declared but the check wrote no clauses.json". X-I4 closes that too.
- **X-E's reader, on the line (not yours).** `readiness.property_evidence(run_dir, pointer)` (`src/harness_bench/readiness.py:600-628`) reads `<property.json dir>/check/clauses.json`, the check's evidence directory (`grade/property.py:420`, `evid = inp.out_dir / "check"`). It refuses a file over 64 KiB, egress-scans the text, then requires a `{str: str}` object. `discriminate._variant_record` (`:211-212`) records a flipped case's declared clause only when the observed string equals it exactly (else `"(differs)"`). `readiness.variant_failures` check (4) (`readiness.py:156`) then compares the record with the declared `clauses`. A declared clause is at most `MAX_CLAUSE_CHARS` (`readiness._check_variant`).
- **Payload ids** are defined in prose only (`oracle/evidence.md:117-118`): `A0..A3` and `B0..B4` are `INJ_A` and `INJ_B` by index, and `C0..C3` are `INJ_3`.
- **The four `inj` variants** are `m1`, `m12`, `m13` (`inj-1`) and `m8` (`inj-3`). X-I2's scratch run (a copy of `check.py` that recorded every hit, not committed) reports m1 `A0, B2, B3`, m12 `B2, B3`, m13 `B2` and m8 `C0` (`evidence.md`, the candidate table). These are **Reported, not re-run**: you measure them (FIXT-A). The six partial fixes in that table are not variants, so the record will cover the four variants only.

**The clause carrier (W0 §2; ruled here, no request needed).** W0 §2 maps a probe to one clause: `clauses.json` is `{<case id>: <clause>}`, and X-E's reader requires a string value. The id set fits that as **one string per probe**: the ids of every payload that exploited the probe, in `check.py` order, joined by `,` with no spaces (`"A0,B2,B3"`, `"C0"`). That is one clause value, so no reader, W0 or `src/` change is needed. A payload string is never a clause value: evidence holds ids, never bodies (`check.py:5`). **Seam route:** if one string cannot carry the set (X-E's reader refuses it, the egress scan withholds it, or a value is over `MAX_CLAUSE_CHARS`), send `python docs/ai-forward-pack/scripts/coord-core.py request add --to coord-opus-e1e4 --deadline default --fallback "<…>" "<ask>"`. The fallback is "the first exploiting id only, one id per probe; the report names each probe where more than one payload hit". Build the fallback in its own commit that names the request id, and finish green (README §2).

### Owned paths
`tasks/S1/**` and `tests/test_security_tasks.py`. **Not yours:** every `src/` file (X-E's `readiness.py` and `discriminate.py`, the grader), `tests/test_discriminate.py`, `tests/test_readiness.py`, and `tests/mutations/*`. A line in another owner's file is a seam request (README §2).

### Acceptance items (X-I4)
- **I4-1. One definition of a payload id.** Derive each id from its tuple and index in `check.py` (`A{i}` for `INJ_A`, `B{i}` for `INJ_B`, `C{i}` for `INJ_3`). Never write a second table of ids. `inj_1` and `inj_3` try **every** payload, with no return on the first hit. Each returns the joined ids, or `None` when no payload hits. Outcomes do not change: a probe is `exploited` exactly when at least one payload hits. The other six probes keep their clause texts. The reference and naive values in `task.yaml`'s `expected` block do not change, and neither do their provenance comments.
- **I4-2. `clauses.json`.** `check()` writes `clauses.json` into `ctx.evidence`: `{case id: clause}` for every `exploited` case. Build it from the same `evidence` dict that `s1-probes.json` is written from, so the two files have one source. Write it on every run, and write `{}` when nothing is exploited: the check does not know which variant it grades.
- **I4-3. The variants follow.** In `oracle/variants.py`, m1, m12 and m13 get their measured `inj-1` string, and m8 its measured `inj-3` string. Measure each through the real host. The existing variant test pins it (`tests/test_security_tasks.py:457` compares each probe's observed clause with the declared `clauses`). Never copy a value from the table. If a measured string differs from X-I2's reported one, write a trace for that probe in `evidence.md`.
- **I4-4. Through the real grader and X-E's reader (the join test).** New test `test_s1_clauses_json_carries_payload_ids_through_grade_cell`. Grade the reference, and m13's overlay, through `prop.grade_cell`, built the way X-I2's F1 test builds its input (`tests/test_security_tasks.py:604-607`). Then read each cell with X-E's `readiness.property_evidence` on that cell's `property.json`, and assert that `clauses` equals `{}` for the reference and m13's declared `clauses` for m13. This test is the line X-E's reader sits on: if the evidence directory moves or the shape changes, it goes red.
- **I4-5. A new task version.** `plan.task_version_hash(tasks/S1)` moves with the edit; there is no version field to bump (`readiness.record_key`). In `evidence.md`, add a section titled "F4 carrier (X-I4)". It gives the change, the measured string per variant beside X-I2's reported one, the old and new task version hashes, the base and commit, and the line "keep or drop is not decided here". If a test outside your owned paths pins the old hash, raise a seam request and build the fallback per README §2.
- **I4-6. No drop and no flip.** Drop no payload. Edit no `expected` value. Leave `status: draft`. Keep or drop per payload comes from the record of the Leader's run. A payload `P` is needed alone when some variant's clause is exactly `P`. A drop is a later S1 version, and the Coordinator routes it when the record exists. S1 does not go `ready` while F4 is open (#15, #19).

### Red first (README §2)
Commit a skeleton first: the check writes `clauses.json` with today's letters, and the id helper has its final signature. Then commit the reds: I4-4, and a unit test that m1's overlay through the real host yields all three ids for `inj-1`. Each fails on an assertion, never on `FileNotFoundError`, `ImportError` or `KeyError`. Then commit the green. For each red commit, report the SHA, the node and the failing assertion line.

### Gate (R-104: own files and own mutations only; the whole suite is the Leader's)
Run each command on its own line and read its exit status:
```
uv run ruff check tests/test_security_tasks.py
uv run pytest -q tests/test_security_tasks.py tests/test_discriminate.py tests/test_readiness.py
python docs/ai-forward-pack/scripts/docs-graph.py validate
```
- `tasks/` is outside the repo's ruff gate (`ruff check src tests tools`), and `tasks/S1` has four findings on the base. Do not lint or reformat task files: a reformat moves the task version for no reason.
- X-E's two test files run because their real-host trials read S1's evidence.
- **Own mutations:** no `tests/mutations/*.json` names `tasks/S1` (checked on `f58d63b0`), and no ledger is in your owned paths. So run two hand mutants once each and report them; do not commit them. (m-a) Restore the early return in `inj_1`: I4-3's m1 test must fail. (m-b) Delete the `clauses.json` write: I4-4 must fail. After each mutant, `git diff --exit-code tasks/S1` must print nothing.
- A skip because the upstream base cannot be reached is reported as not run, never as a pass.

### Then (not yours)
1. The Leader joins X-I4.
2. The Leader runs `bench discriminate S1` over the edited check (the J2 record run, #19).
3. The record gives each `inj` variant its id string, and the keep or drop lines for the ten payloads are written from it.

**Report:** README §4 (at most 12 lines). Add the measured string per variant beside X-I2's reported one, and the old and new task version hashes.
