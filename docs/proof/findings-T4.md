---
id: findings-t4
title: "T4 surfaces -- findings, red SHAs, and mutation results"
type: proof
status: accepted
owner: "@timianmalloo"
phase: "Phase 1 - walking skeleton"
tags: [proof, coordination, t4, mutation]
links:
  - { to: coordination-phase1-finish, rel: relates-to }
review-by: "2026-10-08"
summary: >-
  T4 surfaces' findings-to-tests map for the coordination plan's exit list, each with its red SHA
  and failing line, plus the mutation-check result for tests/mutations/{status,report,cli}.json.
---

# T4 surfaces: findings, red SHAs, mutation results

Branch `track/t4-surfaces`, based on `e5ee302`. Every commit below sets `AGENT_SESSION=T4`.

## Findings to tests to red SHA

### T4-1: exact-value credential scan (HB-SEC-001)

`report/html.py`'s shape regexes did not check for a real, known credential value, only a
credential shape. A rotated token that leaked into the report was only caught if it happened
to match one of the four hard-coded provider shapes.

- Finding: no exact-value check; a rotated token found only in an archived cell home (no longer
  the host's live credential) was invisible to the scan.
- Tests: `tests/test_report.py::test_a_rotated_token_found_only_in_an_archived_home_is_refused`,
  `::test_the_rotated_tokens_base64_and_url_encoded_forms_are_also_refused`,
  `::test_a_clean_report_still_writes_when_credential_values_are_supplied`,
  `tests/test_cli.py::test_report_refuses_when_the_hosts_credential_value_leaks_into_the_report`.
- Red SHA: `3c6db136e77bbd3b12d03d585a009da707b0da74`.
- Failing line: `html.write(run_dir, view, values)` raised `TypeError: write() takes 2
  positional arguments but 3 were given` (the third argument did not exist yet).
- Fix: `7c88077596ab04c0399fd89d5dc1e6568fc4fe4d` (new `report/credentials.py`; `html.scan`/`write`
  accept `credential_values`; `cli.cmd_report` wires host files + archived homes).
- Never-print rule: every test uses `FAKE_ROTATED_TOKEN`, a planted fake; `tests/test_cli.py`'s
  autouse `_no_real_credential_home` fixture redirects `USERPROFILE`/`HOME` so no test in that
  file ever reads the operator's real `~/.claude`/`~/.codex` credential files.

### T4-2: two cell-id definitions (`bench plan --json` vs the frozen plan)

`cmd_plan`'s `--json` path expanded cells without `task_versions`, so `Cell.id` hashed the bare
task id instead of the real `task_version_hash(...)` the frozen plan uses -- the Simplifier's
"two cell-id definitions."

- Test: `tests/test_cli.py::test_plan_json_ids_equal_the_frozen_plans_cell_ids`.
- Red SHA: `e15ae6704e03865f4d7195fbb3a6e4e2993fb487`.
- Failing line: `assert json_ids == {c["cell_id"] for c in frozen["cells"]}` raised
  `AssertionError` (four ids differed).
- Fix: `fa9b5bfbe834270448272b8a8e2dda320ff65a2d`.

### T4-3: status budgets measured from `attempt.process_started`, not `cell.prompt_sent`

`status.build`'s `elapsed_s`/`killing` math used `attempt.process_started`, but the engine's own
`_check_budgets` measures from `prompt_mono` (set at `cell.prompt_sent`). A cell mid-handshake
was shown with an inflated elapsed time, and could show `killing` before its real budget clock
had even started.

- Test: `tests/test_status.py::test_a_running_cells_budget_is_measured_from_prompt_sent_not_process_started`.
- Red SHA: `887aecfe10c777f8b497099d0a5deb4ddb4b0997`.
- Failing line: `assert s.running[0].elapsed_s == 60` raised `AssertionError: assert 120 == 60`.
- Fix: `91822fd36412cff1fc8cd19596928a5bc723b5bb`.

### T4-4: `bench-status/1` gains `stop_code` and `phase` (ruling R-3)

- Tests: `tests/test_status.py::test_phase_is_starting_before_any_cell_process_has_started`,
  `::test_phase_is_running_once_a_cell_process_has_started`,
  `::test_stop_code_is_set_only_when_run_launch_stopped_was_recorded`.
- Red SHA: `e55f119350c34d454ce0d4d684e435024669cb00`.
- Failing line: `assert s.phase == "starting"` raised `AttributeError: 'Status' object has no
  attribute 'phase'` (and the equivalent for `stop_code`).
- Fix: `d08254a169fef20a4c2f36345902242722a4641b`; skill doc + synced copies in `8aff8b1`
  (`skills/start-benchmark/SKILL.md`, `.claude/skills/...`, `.agents/skills/...`,
  `python tools/sync-skills.py`; `tests/test_skills_in_sync.py` green).

### T4-5: plan ids/labels not validated against the status regexes

Nothing stopped a combo id containing a character outside `bench-status/1`'s `LABEL` pattern
from reaching a frozen plan, so `bench status` could later be asked to emit a document its own
strict parser would reject.

- Test: `tests/test_plan.py::test_a_combo_id_that_breaks_the_status_label_regex_is_refused_at_plan_time`.
- Red SHA: `83f52de62ddf3877218cebb6685c54b34a81c24e`.
- Failing line: `with pytest.raises(BenchError) as e:` raised `Failed: DID NOT RAISE BenchError`.
- Fix: `c281e2d7f82176f3bc381c4fe228d0d77ca9b0e4` (`CELL_ID`/`LABEL` moved to `config.py`, the one
  definition; `plan.build_plan` validates every cell against them).

### T4-6, T4-7: UI-state and `--json`-under-a-tty coverage

Not defects: `report/html.py`'s "No cells in this run." and the incomplete-run never-started
banner were already correct, and `bench status --json` was already stdout-only plain JSON under
a real tty (it never touches `rich`). Closed as coverage gaps, not red-first findings.

- Tests (all green on first run, commit `b23279a`): `tests/test_report.py::test_no_cells_in_this_run`,
  `::test_the_incomplete_run_banner_counts_cells_that_never_started`,
  `tests/test_cli.py::test_status_json_is_plain_even_under_a_tty`.

### T4-8 (Simplifier): the plan.json check and the stop rule each exist once

- The known-run check (`(run_dir / "plan.json").is_file()`) was defined independently in both
  `cli._run_dir` and `status.build`. Consolidated into `status.require_known`, called by both.
  Refactor commit `798b39a4f8be653aa81b2c125b70257652cbf57e`; behavior-preserving (covered by
  the existing status/cli suites), no red test.
- The stop rule (deriving `stop_code` from `run.launch_stopped`) is new in this track (T4-4) and
  was written once, in `status.build`; it is not duplicated in `report/**` or elsewhere in the
  files T4 owns.
- Residual observation (not fixed, out of the stated scope of "the shape regex in
  `report/html.py`"): `cli_table.render` prints a cell's label to stdout before `html.write`'s
  credential scan runs, so a credential value that leaked into a label would reach the CLI
  table's stdout even on a run whose `report.html` write is correctly refused. Flagged for the
  Coordinator/Security lens; not in T4's exit list.

### T4-9: N5 "user-config exposed" flag (Coordinator seam request, ruling R-5)

- Tests: `tests/test_report.py::test_the_header_flags_a_run_with_a_codex_cell_and_names_the_evidence`,
  `::test_the_header_has_no_flag_when_the_run_has_no_codex_cell`,
  `::test_the_leaderboard_and_cells_table_flag_only_the_codex_rows`,
  `::test_the_cli_table_prints_the_flag_as_ascii_after_the_table_when_a_codex_cell_is_present`,
  `::test_the_cli_table_has_no_flag_when_no_codex_cell`.
- Red SHA: `cac9b0d0e859fbac1572a679c851f2b3ecc6179e`.
- Failing line: `assert N5_FLAG in doc` raised `AssertionError` (three of the five tests; the
  two "no flag" tests were already green, since no code path could yet add a flag).
- Fix: `f90d27c3c9a1017af07a60095fd4aa953a77015c` (`report.has_codex_cell`/`flag_if_codex` are
  the one definition in `report/__init__.py`; used by `html.py`'s header, leaderboard rows and
  cells table, and by `cli_table.py`'s one ASCII line after the table). No operator path or
  skill name is named in source; only the flag text and the evidence citation
  (`docs/notes/spike-n5-codex-skill-roots.md`, the US-13 canary).

## Mutation result

`uv run python tools/mutate_check.py tests/mutations/<file>.json` (Windows note: `mutate_check.py`
uses `sys.executable`, which must be the `uv`-managed interpreter -- run it via `uv run python`,
never bare `python`, or it cannot import `harness_bench`):

- `tests/mutations/status.json`: 12/12 killed.
- `tests/mutations/report.json`: 21/21 killed.
- `tests/mutations/cli.json`: 11/11 killed.

`tests/mutations/plan.json` does not exist and is not in T4's owned mutation files; T4-2 and
T4-5's guards in `plan.py` are proven by their red/green test pairs only.

## Not done / residual risk

- The `cli_table.render` stdout-leak observation under T4-8 above.
- No CLI-level test exercises `bench report`'s N5 flag through the full ledger/grading path
  (only through hand-built `RunView`s and one credential-scan CLI integration test); the
  html.py/cli_table.py unit tests cover the rendering logic directly.
