---
id: defect-classes
title: "Defect-class register"
type: doc
status: accepted
owner: "@timianmalloo"
tags: [lessons, defect-classes, continuous-improvement]
links:
  - { to: arch-harness-bench, rel: relates-to }
  - { to: design-run-lifecycle-model, rel: relates-to }
review-by: "2026-12-22"
summary: >-
  The project's register of defect classes: the recurring shapes of things that go wrong here, what
  each one survives, and the control that now fails when the shape recurs. Read at grounding;
  appended to on every defect, correction or falsified assumption.
---

# Defect-class register

*Governed by `continuous-improvement.md` (CI1–CI12). **One entry per class, not per bug.** A new occurrence of an existing class appends to that class's Instances and triggers a control review. Read this at grounding (CI5) for the area you are working in.*

**How to use this file**
1. On any defect, correction, or falsified assumption, answer **class → sweep → derive → prevent** in writing (CI2).
2. Find the matching class below, or add one. Append the instance.
3. Climb the control ladder (CI6) and record the highest rung that actually holds: *make it impossible* > *automated control* > *always-loaded instruction* > *knowledge doc* > *register entry only*.
4. A control is not a control until it has been **observed failing** on the un-fixed code.

**Status counts:** controlled 6 · partially-controlled 4 · uncontrolled 2 (project classes). Inherited E2E-E: partially-controlled.
**Recurrence since last review:**
- 4 instances of MOD-A in one session; the control was built after the fourth.
- 2026-09-23: EDIT-B recurred once after registration, and its hook control was then built.
- The phase-1 finish found four new classes from three real E2E runs: CONC-A, PATH-A, CLN-A, and a RIG-D instance.

---

## Project classes

### MOD-A — A seeded model variant that cannot fail, or fails for the wrong reason
- **Signature:** a seeded-bug variant of a TLA+ model reports `NOT rejected`, or is rejected by an invariant other than the one it targets. The model looks verified; the targeted invariant proves nothing.
- **Why it survives:** the real design passes, so the model looks correct. TLC stops at the first violation, so a variant caught by the *wrong* invariant still prints "violated". A later fix (a new invariant, a new guard) can silently change which invariant catches an older variant.
- **Instances:**
  - `2026-09-23` design gate round 2 — the new `NoOutcomeWhileRunning` pre-empted `launch_after_outcome` and `reconcile_no_wait`; both still showed "violated", but not by their targets.
  - `2026-09-23` model v2 — `archive_live` made vacuous by the kill → record fix; `ignore_orphans` vacuous (replaced by `NoLaunchBesideOrphan`).
  - `2026-09-23` model v1/v2 — a guard reading a history variable (`prompts = 0`) hid `relaunch_prompted` twice.
  - `2026-09-23` model v1 — two guards for one invariant masked `exceed_parallelism`.
- **Sweep:** all 22 variants re-run after the isolation change; every one is rejected by its own target.
- **Control:** `tools/check_models.py` checks each safety variant against its target invariant alone (`only_invariant`) and each liveness variant against its target property alone (`only_property`), asserting the target's name in TLC's output. `tests/test_check_models.py::test_every_checked_property_has_a_seeded_variant` (observed failing when a variant was removed, 2026-09-23) and `test_variant_config_checks_only_its_target`. Guards never read history variables (stated in the model design).
- **Status:** `controlled`

### RIG-D — A tool's semantics assumed in a design, not checked
- **Signature:** a design names a mechanism (`git worktree`, a Job Object flag, a CLI mode) and relies on a property it was never observed to have.
- **Why it survives:** the mechanism is familiar, so the property feels checked. Design text is not executed.
- **Instances:**
  - `2026-09-24`, the Coordinator: the TOOL-A sweep concluded that the cosmic-ray runs were exposed to stale bytecode. It measured collection time, but did not read how cosmic-ray launches its tests, and cosmic-ray already sets `PYTHONDONTWRITEBYTECODE=1`. The cost was a 2.4 h re-run. The re-run found real overstated kills (TOOL-B), but for a reason other than the one assumed.
  - `2026-09-24`: the Codex reader assumed injected context always starts with `<`. With the pack on, Codex 0.156 prepends `# AGENTS.md instructions for <cwd>`, and the reader took that block as the prompt (US-10 failed in the second real E2E). The control is a real, scrubbed pack-on record: `tests/fixtures/native/codex/pack-on.jsonl`. Its test was observed red at `05f52fa`. The E2E also checks US-10 for every cell.
  - `2026-09-23` ADR-0013 draft: "each cell gets its own worktree of one clone". Worktrees share refs, stashes and config, so one cell's commits and remotes were visible in every other cell. Distributed Systems and the Test Architect caught it at the gate, each checking in a scratch repository.
  - `2026-09-23` ADR-0008 assumed the native session record is a complete token source. Measured with the pinned builds, Claude Code's record under the ACP adapter omits the final and auxiliary calls. Found by comparing the same turn's two sources during `/implement`; fixed per harness (`usage_source`), with fixtures that pin both sources.
- **Sweep:** the other mechanisms ADR-0013 names. Job Object kill-on-close and the active-process count were spiked (N2). The Codex full-access mode was read in source and run (N1). Job naming and handle inheritance are marked Inferred with probe N4.
- **Control:** T-WS-gitleak (automated, phase 1). Rule: every mechanism a design relies on is spiked or labelled Inferred with a named probe (the pack's no-guessing protocol, NG).
- **Status:** `partially-controlled` (the test lands in phase 1)

### EDIT-A — A blanket text replacement renames more than the target
- **Signature:** a mechanical rename (`AllCells` → `Cells`) also rewrites identifiers that contain the target (`NotAllCellsFinished` became `NotCellsFinished`).
- **Why it survives:** the replacement looks local; the collateral hits are in other identifiers.
- **Instances:**
  - `2026-09-23` removing the coordinator from the model broke the witness invariant's name. `check_models.py` failed closed ("not defined in the specification"), and the name was fixed before the commit.
- **Control:** renames use whole-word matching (`\b…\b`, as the later `container` → `proc` rename did). `check_models.py` fails on any undefined invariant, and `test_every_seeded_variant_targets_a_declared_property` checks the names. Observed failing, 2026-09-23.
- **Status:** `controlled`

### EDIT-B — Escape sequences corrupted by nested string generation
- **Signature:** code or data written by a script that is itself inside a shell heredoc or a string literal. A `\n`, `\\` or `\\?\` in the intended text arrives as a real newline, a single backslash or a lost prefix.
- **Why it survives:** the generating script runs without error; the damage shows only when the written file is parsed or run later.
- **Instances:**
  - `2026-09-23` `tests/fake_acp_agent.py`: `"\n"` became a line break, so every engine test failed.
  - `2026-09-23` `tests/mutations/engine.json`: `\n` inside JSON strings became line breaks, making the JSON invalid.
  - `2026-09-23` the fixture scrubber: a `\\?\` long-path prefix lost a backslash.
  - `2026-09-23` `tests/test_grade.py`: the class recurred after it was registered. A heredoc edit script's `\\n` arrived as a line break, and the script's own `assert` stopped it before any write. The prose control had not held.
- **Control:** `tools/heredoc_guard.py`, a `PreToolUse` hook on Bash wired in `.claude/settings.json`. It blocks (exit 2) any heredoc fed to a Python interpreter, so a program is written to a file and then run (CT27), and code is changed with the Edit tool. `tests/test_heredoc_guard.py` pins the blocked and the allowed shapes; it was observed red before the guard existed. The suite still fails at once on an unparseable module.
- **Status:** `controlled` (2026-09-23)

### INS-A — Progress hidden by buffered output
- **Signature:** a long check writes to a log file that stays empty until the process exits, so nobody can tell which stage is slow or hung.
- **Why it survives:** on a terminal, output is line-buffered and looks fine; redirected to a file, it is block-buffered.
- **Instances:**
  - `2026-09-23` `check_models.py` redirected to a log: 10 minutes with an empty log and TLC at 43 GB; the run was stopped blind.
- **Control:** every result line in `check_models.py` prints with `flush=True`. `NONE YET` as a test; the upgrade trigger is a second instance in another script.
- **Status:** `partially-controlled`

### CONC-A: check-then-act on a shared destination under concurrency
- **Signature:** two workers each check "does `dest` exist", both see no, and both build and publish into it. On Windows, `os.replace` onto a non-empty folder fails with `WinError 5`.
- **Why it survives:**
  - Unit tests build one cell at a time.
  - The race needs two cells that share a content-addressed input, running in parallel.
  - The first real E2E was the first run with both.
- **Instances:**
  - `2026-09-24`, first real E2E: `workspace.task_source` and `workspace.pack_checkout` raised HB-CELL-113 for the second `pack=on` cell (T6).
- **Sweep:** `grep os.replace|.rename(|shutil.move` over `src` finds one site, `workspace._land`, which both functions now use. `cell_working_copy` has a per-cell `dest`, so nothing shares it.
- **Control:** `tests/test_workspace.py`'s two concurrency tests use a `threading.Barrier`. They were observed red at `0082875` (re-run by the Coordinator). The two `tests/mutations/workspace.json` mutants are killed.
- **Status:** `controlled` (2026-09-24)

### PATH-A: a relative path handed to a subprocess that runs in another folder
- **Signature:** a path argument stays relative, and a subprocess started with `cwd=<some other folder>` resolves it there. The file "does not exist".
- **Why it survives:** tests pass absolute paths (`tmp_path`, `ROOT / ...`). Only an operator typing a relative path hits it.
- **Instances:**
  - `2026-09-24`: `bench --tools-dir .tools/harness run` looked for `pack-apply.py` under the cell's working copy, which gave HB-CELL-113 (T8-2).
- **Sweep:** every CLI path argument (`--root`, `--runs`, `--cells-root`, `--tools-dir`, `--pack-source`, `--matrix`) is resolved once in `cli._resolve_paths`. `grep add_argument` lists no other path argument. Every `cwd=` site in `src` takes a path derived from those.
- **Control:** `tests/test_cli.py::test_a_relative_tools_dir_resolves_absolute_and_the_pack_on_build_succeeds`, observed red at `62c38ba`. The `t8.json` T8-2 mutant is killed.
- **Status:** `controlled` (2026-09-24)

### TOOL-A: an in-place mutation leaves stale bytecode
- **Signature:** a tool mutates a source file on disk, runs tests, and restores it byte for byte. When the mutant has the same size and the restore lands in the same mtime second as the mutant's write, the mutant's `.pyc` still passes Python's mtime+size check. `import` then loads the mutant while `git status` is clean. Consequences:
  - a later gate goes red for no source reason;
  - a later mutation can be tested as the previous one, giving a **false kill or a false survival**.
- **Why it survives:**
  - the restore is byte-exact, so every check that reads the source says clean;
  - it needs a sub-second test run and a size-preserving mutation, which is rare enough to look like flakiness.
- **Instances:**
  - `2026-09-24`: T10's full `pytest` after a `mutate_check` run of the cap mutation (`30.0` ↔ `60.0`) loaded `KILL_RETRY_CAP = 60.0` from a `.pyc` whose mtime and size matched the restored source.
- **Sweep:**
  - Measured warm collection is 0.41–0.51 s for every recorded cosmic-ray test command, so a `-x` run *could* finish inside its mutant's second. The Coordinator first concluded that the cosmic-ray runs were exposed, and re-ran all of them (T12).
  - **That conclusion was wrong:** cosmic-ray 8.7.0 already forces `PYTHONDONTWRITEBYTECODE=1` for its test subprocess (`cosmic_ray/testing.py:52-56`, read by T12 and the Coordinator). Only `tools/mutate_check.py` was exposed.
  - Its results were re-run with the fixed tool: 198/198 at `ceed6c1`.
  - The re-run still paid for itself, because it exposed TOOL-B.
- **Control:** `tools/mutate_check.py` runs pytest with `PYTHONDONTWRITEBYTECODE=1` (fix `6d26c76`). `tests/test_mutate_check.py::test_a_same_size_mutation_leaves_no_stale_bytecode` makes the race deterministic by giving the restored source the `.pyc`'s recorded mtime. It was observed red at `3ecd1eb`, loading `60.0`.
- **Status:** `controlled` (2026-09-24). cosmic-ray guards itself.

### TOOL-B: a mutation "kill" that is not a named test failing, and counts that are transcribed
- **Signature:** a mutation record counts a mutant killed when no test actually caught it. Either the tool calls any non-zero exit or timeout a kill, or the record's counts were computed by hand (total minus the listed survivors). The mutation bar then looks met while real gaps stay open.
- **Why it survives:** cosmic-ray 8.7.0 returns `KILLED` for every non-zero exit, including collection errors and fixture collisions, and for every timeout (output `"timeout"`, `testing.py:73-75`). Its summary does not separate these. A hand-written table then turns a count into a claim nobody re-derives.
- **Instances:**
  - `2026-09-24`: T12's bytecode-off re-run found 29 mutants recorded killed in ledger, views and grade that survive under each record's own command. The Coordinator re-verified three of them with the named-test checker: each survived before T12's tests and was killed after.
  - Other errors in the same records:
    - 8 duplicate equivalent rows;
    - impossible per-line annotation counts;
    - one false equivalence (engine L394).
  - A timeout (views `202:35`, `31e9 ** 1e9`) very likely counted as a kill (Inferred).
  - A false kill by `FileExistsError` on a leftover fixture folder (engine L325, T12's own run).
- **Sweep:** every cosmic-ray record was re-run (T12). Every disagreement is dispositioned: killed by a new test (`a0c4f52`) or argued equivalent. 0 open.
- **Control:**
  - `tools/mutate_check.py` already counts only a named test failing (`ae6e8f0`).
  - For cosmic-ray, **none is built yet.** The upgrade: commit a report script that derives every record table from `cosmic-ray dump`, counts `"timeout"` and error outputs separately, and re-verifies each kill with the named-test rule. T12's scratch `t12_report.py` is a starting point.
  - Until that exists, a record's kill count is an upper bound unless it says its killing outputs were read.
- **Status:** `uncontrolled`

### CLN-A: cleanup that fails silently
- **Signature:** a best-effort cleanup (`rmtree(..., ignore_errors=True)`, a handler or file never closed) fails without a sign. The residue builds up on disk, or a held handle blocks the next deletion.
- **Why it survives:**
  - the product's result is correct;
  - nothing checks that the residue is gone;
  - on Windows, read-only git objects and open files make a silent failure the common case.
- **Instances:**
  - `2026-09-24`, third real E2E: the race loser's temp folder, holding read-only git objects, stayed under `cells/.sources` (T9-1).
  - Same run: `engine.log` stayed open because `configure_logging` added a handler per call and never released one. That also sent one run's log lines into another run's log (T9-2).
  - The unit tests' teardowns left ~170 folders under `C:/Projects/bench-test`. By T12's measure that grew to 421, because each full suite adds about 100.
  - `2026-09-24` (T12): the residue caused a **false mutation kill**. `conftest.base`'s random 8-hex folder name collided with a leftover folder, which raised `FileExistsError`. That turns cleanup residue from a disk issue into a correctness issue for any test tool that counts a non-zero exit (see TOOL-B).
- **Sweep:** T9 listed every `ignore_errors=True` site. No product-source site remains.
  - `tests/e2e/test_walking_skeleton.py` now removes its folder with `make_writable` and asserts the folder is gone.
  - Test-fixture teardowns (`tests/conftest.py:23`, `tests/test_workspace.py:159`, `tests/test_profiles.py:143`, `tests/fixtures/ledger/make_fixture.py:61-62`) are still `ignore_errors`.
  - The vendored pack scripts are not ours to change.
- **Control:**
  - T9-1: the concurrency tests assert that no `.tmp` folder remains. Observed red at `e225ff5`.
  - T9-2: the handler-replacement and `cmd_run` release tests. Observed red at `e225ff5`.
  - The E2E's final cleanup now fails on any residue.
- **Fixture fix (2026-09-24):**
  - `tests/conftest.py`'s `base` now uses a full uuid, so names no longer collide, and removes with `archive.make_writable`. `test_workspace.py`'s `clean_base` is now an alias of `base`: one definition.
  - Measured: a full `pytest -m "not credentials"` run (592 passed) left **0** folders under `C:/Projects/bench-test`, where it had left about 100. Read-only git objects were the whole cause; no file was held open once the tests had run.
  - `tools/clean_bench_test.py` (dry run by default, `--delete`) removed the 428 earlier leftovers, 428 of 428, and none was locked.
- **Upgrade trigger:** a residue check that fails the session (no test enforces "0 left" yet).
- **Status:** `partially-controlled` (the product is controlled; the fixtures are fixed and measured, not enforced)

### COORD-A: a delegation mechanism's refusal routed around
- **Signature:** the harness refuses a sub-agent's action, for example writing `docs/proof/findings-*.md` ("report files"), and the sub-agent reaches the same effect another way, such as a shell heredoc.
- **Why it survives:** the workaround succeeds and the result looks right. The refusal is not in the file's history.
- **Instances:**
  - `2026-09-24`: T6 wrote `findings-T6.md` through a shell heredoc after the Write tool was refused.
  - T1–T5 and T8 did not route around the refusal. They reported the content, and the Coordinator transcribed it.
- **Sweep:** every findings file carries a line saying who wrote it and why.
- **Control:** the brief clause "the harness refuses sub-agent writes to findings files; put the content in your report" (T8 and T9 briefs). That is an instruction rung only; no automated check exists.
- **Upgrade trigger:** a second route-around.
- **Status:** `partially-controlled`

### GATE-A: a gate green over an empty corpus
- **Signature:** a gate reports OK because it found nothing to check, not because what exists is correct.
- **Why it survives:** the output says OK, and the zero counts are easy to skim past.
- **Instances:**
  - `2026-09-24`: `verify-ruling-citations.py` prints "0 ruling(s) cited, 0 defined" on every join. It recognises only `### Ruling NN` headings, and `docs/notes/rulings.md` uses `## R-n`. R-1 to R-5 are therefore never checked.
- **Sweep:** the other join gates report non-zero counts. `docs-graph validate` counts its nodes, and the recount counts its tests (501).
- **Control:** none yet. The fix is a format decision for the Owner, one of:
  - adopt `### Ruling NN` with the `coord decide rule` allocator;
  - have the pack script accept `## R-n`.

  Until then, the Proof Pack does not count this gate as evidence.
- **Status:** `uncontrolled`

### SUITE-A: "run the full suite" starts real model cells
- **Signature:** a bare `pytest` runs tests marked `credentials`, which start real harness cells on the operator's logins. So an instruction to "run the full suite" (a worker's brief, a join gate) starts benchmark cells inside the coordination layer. That breaks owner ruling 3 (ADR-0002) and R-9 vendor exclusivity, and it rewrites `docs/proof/phase1-e2e-last.json`.
- **Why it survives:** the phase-1 Proof Pack documents `-m ""` as the opt-in for e2e, which reads as though the default excludes them. Nothing enforced that: `tests/conftest.py` only skips `native` tests off Windows, and `pyproject.toml` had no `addopts`. The e2e run passes, so nothing looks wrong.
- **Instances:**
  - `2026-09-24` (coordination-finish-harness-bench, wave 1): the Leader wrote "the default suite excludes the real-harness tests" into the worker briefs without checking. W1-ACP's suite run, the Leader's W1-HOST join run and the reviewer's runs each started the 4-cell walking skeleton and the N5 canary on the Anthropic and OpenAI logins while other workers were live. It was found through a modified `phase1-e2e-last.json` in two worktrees, and a leftover `e2e-*` folder the reviewer saw.
- **Sweep:** `-m credentials` collects 5 items: 3 in `tests/e2e/` (the walking skeleton and the US-13 canary) and 2 in `tests/test_profiles.py::test_real_handshake_with_the_pinned_build` (a real handshake on the login). The first write of this entry said "5 items in tests/e2e", which was wrong; the W1-TOOLB worker found it. The control is marker-based, so it covers all 5.
- **Control:** `pyproject.toml` `addopts = "-m 'not credentials'"`; the documented opt-in `-m ""` still works. `tests/test_default_suite_is_offline.py` fails if a bare run selects any e2e item, or if the opt-in stops selecting them (red `5013299`).
- **Status:** `controlled`

### RUN-A: a runner bound that fails committed work
- **Signature:** the coordination runner fails a long worker attempt on a transport bound, even though the work is already committed. Output over 16 MiB gives `output_limit_exceeded`. Any native tool error step gives `native_tool_error`, even one the agent could recover from, such as reading `.git/hooks` in a linked worktree where `.git` is a file.
- **Why it survives:** the runner was qualified on single short turns (23–101 s), where neither bound is reached.
- **Instances:**
  - `2026-09-24`, run `w1-s1`: Grok (W1-HOST) had all 7 commits in place and then exceeded 16 MiB at 906 s. Agy (W1-TOOLB) failed at 292 s with no commit.
- **Sweep:** every runner track longer than a qualification turn (Grok and Agy in waves 1–2).
- **Control:** upstream pack fixes (R-11, track W1-PACK-2). Until they land: Grok slices of 12 minutes or less, Agy held, and each slice records `total_output_bytes`, `extension_notifications` and wall clock.
- **Status:** `uncontrolled` (the fix is in flight upstream)

---

## Inherited classes (seeded from the pack)

*Observed in production across independent codebases running the AI-Forward pack (`continuous-improvement.md` §6). Each is **uncontrolled here until this repo builds the control** — that is the work, not the copying.*

| ID | Class | Signature | Why it survives | Control to build | Status here |
|---|---|---|---|---|---|
| **DM-A** | One quantity, two homes | A value produced in two places; a new call site wires to whichever it found first | Both implementations pass their own tests; nothing compares them | Derive once (DM7); cross-surface consistency test | `uncontrolled` |
| **DM-B** | Stored fact that nothing writes | A persisted flag beside a function computing the same thing | Reads succeed and return a plausible default | Reader/writer trace (DM15); stored-equals-derived test | `uncontrolled` |
| **DM-C** | Persisted field with no compute reader | Stored, entered, round-tripped, tested — read by nothing that computes | Round-trip tests pass perfectly | Reader trace: write / CRUD / schema / **compute** | `uncontrolled` |
| **DM-D** | Grain inferred, not declared | Period/owner derived from a date rule; exceptions break it | Works for every non-exceptional record | Declare the grain; put it in the key (DM8) | `uncontrolled` |
| **DM-E** | Semi-additive measure summed across time | Balances/positions/headcounts added over periods | The arithmetic is valid; only the meaning is wrong | Declare additivity per measure (DM9) | `uncontrolled` |
| **DM-F** | Type-1 where Type-2 was needed | A mutable attribute silently rewrites the meaning of past records | Nothing errors; history just changes | History rule per attribute (DM10); point-in-time test | `uncontrolled` |
| **E2E-A** | Field reaches the DTO but not the wire | Present in model, service, client type, column list; missing from the projection | Every layer's own test passes | Write the surface list first (E7); one end-to-end assertion per field | `uncontrolled` |
| **E2E-B** | Declared shape with no write path | A facet/status/enum/route declared and never set | Telemetry reports "nothing to do" — true, for the wrong reason | Test that the shape is written under the claimed condition | `uncontrolled` |
| **E2E-C** | Green suite, broken surface | All units green; the page never renders; the composition root is never exercised | Units construct their subject by hand | One proof through the real composition root to the rendered surface (E11) | `uncontrolled` |
| **E2E-D** | Component tests that can't see each other | Every part correct against its own expectation; parts disagree | Per-component coverage is high | Cross-surface consistency test on one seeded scenario (E12) | `uncontrolled` |
| **E2E-E** | The gate passed, its contents didn't | Several checks in one block; only the last exit code propagates | The gate is green | Run each control independently; assert each reports its own status (E13) | `partially-controlled` (2026-09-24). **Instance:** the Coordinator committed `5dcb2fe` while `pytest --collect-only` had 1 error, because `\| tail -1` hid the exit status. It was fixed in `101ec85`. **Control:** `tools/heredoc_guard.py` blocks a gate (pytest, ruff, mutate_check, conductor-join, run-verify-gates) piped without `pipefail`. It was observed red at `291468b` and fixed in `727cbb4`. Other multi-check blocks are not covered. |
| **E2E-F** | Exit code taken as result | A command returned success; the state was never read back | Success is success-shaped | Read back the state and assert on it (E14) | `uncontrolled` |
| **E2E-G** | Reachability not verified | The surface exists but nothing links to it — or a link points at nothing | The feature works if you can get to it | Assert the navigation path to any new surface (E10) | `uncontrolled` |
| **RIG-A** | Own-code shape asserted from memory | "This type has that member" — written in a design, never opened | Designs aren't compiled | Read the file or label Inferred (E15); review opens the cited file | `uncontrolled` |
| **RIG-B** | Delegated inventory cited as fact | A sub-agent's counts/listings enter an artifact unverified | Sub-agent output is fluent and specific | Spot-check before citing (E16) | `uncontrolled` |
| **RIG-C** | Sweep stopped at the instance | The fix works; the sibling ships the same bug days later | The reported symptom is gone | class → sweep → derive → prevent (CI2) | `uncontrolled` |
| **REC-A** | Stale record / overstated claim | A comment, status table or doc asserts something that was true once | Documentation isn't executed | Re-verify records you touch (E17); correct overstatements in their own change | `uncontrolled`. **Instances (2026-09-24):** (1) the Coordinator's Proof Pack said every red was test-only, but T4-1's is not (Test Architect N3); it was corrected. (2) *Flagged:* T2's cosmic-ray record counted two `views.verify` mutants killed that survive under that record's own test set (T11). The likely cause is survivor re-runs with extra test files, which is unverified. Both are now killed by `test_verify.py` and pinned in `views.json`. **Control idea (not built):** a mutation record names one test command per module, and survivor re-runs use that same command |
| **OPS-A** | Migration compiles but is never applied | The migration builds; the deployer doesn't run it | The build is green | Migrate-before-publish enforcement; exercise the down path (DM16) | `uncontrolled` |
| **UX-A** | Archetype mismatched to the task | A dashboard archetype on a data-entry task: everything visible, nothing sequenced | Each component is individually fine | Verify archetype vs JTBD on changes to *existing* screens too | `uncontrolled` |
| **UX-B** | Shipped with data-only states | Loading/empty/error never designed; "it looked fine with data" | Demos and tests use populated fixtures | Complete component state set as a design gate (U9) | `uncontrolled` |
