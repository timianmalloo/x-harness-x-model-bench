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

**Status counts:** controlled 7 · partially-controlled 5 · uncontrolled 2 (project classes). Inherited E2E-E: partially-controlled.
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
  - `2026-09-25`, the Leader: `qualify-codex-3`..`5` placed the Codex hook in the worker tree's `.codex/hooks.json` only. The pack's own launch reference (`execute-with-coordination/reference/launch.md`, "Codex requires native review…") says Codex discovers project hooks in a linked worktree from the **primary** checkout, and that each definition needs native `/hooks` trust review. The reference was read only after three runs. The runs still measured real facts (0 of 3 marker hooks fired, and a leased path was written through code-mode `tools.apply_patch`), but not the question they were meant to answer.
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
  - `2026-09-25`, the repo-local `PreToolUse:Bash` hook in `.claude/settings.json` ran `tools/heredoc_guard.py` relative to the session's cwd. The Leader ran `cd .git/coord-runs/qualify-7`, the cwd stuck, and every Bash call was then refused ("can't open file …\qualify-7\tools\heredoc_guard.py"). The fix anchors the path at `${CLAUDE_PROJECT_DIR:-.}`: run from `C:\` with the variable set, it still refused a Python heredoc (exit 2) and allowed `ls`. Unset, it falls back to the old relative path. `assume:` Claude Code sets `CLAUDE_PROJECT_DIR` for hook commands. It is not set in the Bash tool's own shell. Confirm by one Bash call from a cwd outside the root after the next session start. If it is false, the hook falls back and fails the same way from outside the root.
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
- **Wave-1 close (2026-09-25):**
  - `C:/Projects/bench-test` held 8 leftovers besides the two kept negative E2E runs:
    - two `base` uuid folders (14:29 and 17:11, the times of killed pytest runs: SUITE-A and the GATE-B hang);
    - two `hs-*` handshake homes from the SUITE-A real-cell run (`tests/test_profiles.py:386`);
    - four Leader probe files and folders.
  - A killed process runs no teardown, so the fixture fix cannot reach these. The Leader removed all of them at the wave close, and the folder is empty.
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

### REG-A: a squash merge drops lines from an append-only register
- **Signature:** `git merge --squash` resolves a `register`-class file (`docs/audit/*.jsonl`, `docs/notes/rulings.md`) as an ordinary text merge, not through the `coord-register` union driver. Lines appended on `main` after the branch point are silently removed from the staged result.
- **Why it survives:** the merge reports "Automatic merge went well"; the lost lines are the newest ones, so nobody reads them at the time; the derived audit view is regenerated from whatever was staged.
- **Instances:**
  - `2026-09-24`, the W1-COP-D join: a squash merge was needed to keep an unscrubbed fixture blob out of `main` (R-30 c3). The staged `audit-log.jsonl` deleted 2 entries of `main`'s (the Codex W1-ACP review compile). The Leader caught it in `git diff --cached --numstat` (a non-zero deletion count on a register) before committing.
- **Sweep:** the only squash merge in this plan so far; every other join is `--no-ff`, which runs the registered driver.
- **Control:** at any squash join, rebuild each register as the union of `HEAD`'s lines plus the staged new lines (the Leader's `union_register.py` step), then assert `git diff --cached --numstat -- <register>` shows 0 deletions before committing. Not yet a test or gate. The upgrade trigger is a second squash join, at which point it becomes a join-gate check.
- **Status:** `observed` (the procedure is followed by the Leader; no automated gate yet)

### REG-B: a derived artifact merged but never regenerated
- **Signature:** a join merges a branch that changed a derived file (`docs/docs-index.js`, `docs/audit/audit-data.js`). The `coord-regen` driver resolves the file to "ours" by design and records a regeneration as owed, but nobody runs `coord regen`. The derived view silently misses the branch's entries.
- **Why it survives:** the merge reports success, and the owed regeneration is written to a list nobody reads. `docs-graph validate` catches index drift, but nothing catches a stale audit view.
- **Instances:** `2026-09-24/25`, every wave-2 join. The index missed two USER-D docs (found by validate, `82dcfcc`). The audit view was stale until the Leader ran `coord regen` at 23:35.
  - `2026-09-25`, a direct Leader commit with no merge (`ed9f247`, the spec's R10 row). `docs/specs/harness-bench.html` is derived from the markdown, but `coord-regen` fires only on a merge. The Leader pushed the docs-only commit without the suite, and `tests/test_docs_html_in_sync.py` went red on `main`. The W3-EGRESS author found it in their tree's full suite. Fixed by re-rendering (`python tools/render-doc-html.py`).
- **Sweep:** all merges since the wave-2 dispatch. `coord regen` regenerated both files; nothing else was owed. Direct commits: only `ed9f247` changed a rendered source.
- **Control:** every join runs `coord regen` after the merge, then `docs-graph validate`, before the suite. **After the second instance:** every Leader push, a docs-only one included, follows a full-suite run on that exact commit, and the push is refused if `regen_owed` is non-empty. For now this is a Leader procedure. The upgrade trigger is a third instance: a pre-push hook.
- **Status:** `observed` (Leader procedure)

### GATE-B: a push not gated on the suite that precedes it
- **Signature:** a join command chains `pytest …; …; git push` with `;`. When the suite hangs, fails or is killed, the push still runs, and an unverified commit reaches the remote.
- **Why it survives:** on a green suite the chain looks identical to a gated one; only a failure shows the difference.
- **Instances:**
  - `2026-09-24`, the W1-COP-I slice-2 join: the suite hung at about 15% (not reproduced; the engine tests alone passed in 88 s, and the full re-run passed 747 in 163 s). The Leader killed it, and the chained `git push` then pushed `075d3c5` before any suite had completed on it. The later full run on the same commit was green, so no broken code reached the remote.
  - `2026-09-25`, the STOP-I slice-1 join: a second instance of the same shape, one step earlier. `git merge` failed ("Merge with strategy ort failed": two uncommitted audit lines blocked it), and the chain went on. The regen commit that followed (`6d9d994`) was labelled "after the STOP-I join", and the suite ran on the **old** `main` and read green (955). The Leader caught it from the missing merge line before any push, then merged properly (`299c465`: 967 passed).
  - `2026-09-25`, the B1 freeze commit: a third instance, in a targeted check. The Leader ran `pytest tests/test_config.py tests/test_tasks.py | tail -1`. The second file does not exist, so pytest printed "no tests ran" and exited 4, and no exit status was read. The freeze entry broke `test_grade_runner.py`'s pinned task list (`00d6bde`). W3-CAL's full suite caught it before any push, and it was fixed at the GR-CODE c2 join.
- **Sweep:** every Leader join command since the plan started used the same `pytest …; tail; ruff; push` shape.
- **Control:**
  - At a join, the push is its own command, run only after the suite's exit code has been read as 0 in an earlier step (`pytest … > log; echo "exit=$?"`, then a separate push).
  - **After the second instance:** the merge also reports its own exit (`git merge …; echo "merge=$?"`), and nothing else runs until it reads 0. The Leader commits its own pending audit and ledger lines before any merge.
  - A fourth instance on 2026-09-25, at the W3-GW-I follow-up a join. A `python script && pytest …; …; git commit` chain ran the commit after the script's assertion failed, because `&&` bound only the first pair. The commit carried two stale mutants that the next step caught (not pushed; fixed in the next commit). A fifth, related shape the same day: the Leader ran `mutate_check` and edited `backend.py` in the primary checkout while the full gate ran there, so that gate's result was void; it was re-run. The rule: one step per command at a join, or `set -e` for the chain; never a source edit or mutation run in a checkout whose suite is running.
  - The upgrade trigger for a hook is a third instance. **It fired (the B1 freeze, 2026-09-25).** The rule, extended: every pytest the Leader runs reads its exit code, and a "no tests ran" result (exit 4 or 5) is a failure, never a pass. The hook that refuses a bare `pytest … | tail` is the next step. `tools/heredoc_guard.py` already refuses a gate behind a pipe (E2E-E / CT27), but it did not match this shape.
- **Status:** `observed` (Leader procedure, third instance; hook upgrade owed)

### CLN-B: a joined tree removed while a reviewer still reads it
- **Signature:** the Leader cleans up a merged worktree while a review of that track is still running, and the reviewer's run depends on a file in that tree, such as its `.venv` interpreter. The reviewer's tool then fails in the middle of the run.
- **Why it survives:** `coord worktree cleanup` checks that a tree is clean, merged and not held by a live session. A reviewer reading the tree from outside holds no session there, so the tree looks free.
- **Instances:**
  - `2026-09-24`: after the W1-ACP join, the Leader removed `phase2-acp-transcript` while the Test Architect's veto read-back ran `mutate_check` with that tree's `.venv`. The run printed "4 not killed". A re-run with `main`'s `.venv` killed all 5. The false result was safe (exit 1), but it exposed that `mutate_check` reports `survived` instead of `error` when there is no pytest output (fix: W1-TOOLB follow-up `w1-toolb-no-summary`).
- **Sweep:** every cleanup the Leader runs after a join while reviewers or read-backs of that track are live.
- **Control:** the Leader cleans up a track's tree only after every review and read-back of that track has handed back. Reviewers are briefed to use a throwaway `git worktree add --detach` tree, never the branch checkout. The tool-side half is the `mutate_check` no-summary → `error` fix.
- **Status:** `observed` (Leader procedure; the tool-side fix is in flight)

### PERM-A: a per-platform tool id missing from a class allowlist
- **Signature:** a profile allows a capability *class* (shell; file read and edit) by listing tool *ids*, but lists only the ids known on one platform or one build. On another platform, or a newer pinned build, the harness exposes a further id in the same class. The first call to it is refused as out of profile, and one arm silently loses a capability the other arms keep.
- **Why it survives:** the allowlist was written from the ids seen when it was written (2.1.274), and nothing compared it with the ids the pinned build actually offers. The refusal is correct behaviour for an unlisted tool, so every control upstream of US-14 stays green. It surfaces only when a model happens to pick the new id, which here needed the pack's instructions to name it.
- **Instances:**
  - `2026-09-25`, run `e2e-wave1-1790302505`, cell `17efb75ce2d5fc6d` (cc-opus, pack on, Claude Code 2.1.282, win32): the model called `PowerShell` once. It was not in `[Bash, Edit, Write, Read, Glob, Grep]`, so the driver refused it. Permission requests were `[0,1,0,0,0,0]` and US-14 failed (R-34).
- **Sweep:** the Claude Code profile (fixed, R-34). The pinned 2.1.282 build also offers `NotebookEdit` as a deferred tool; R-35 ruled it in-class (file edit, a `.ipynb`) and it is in the allowlist and the class-coverage test's "file edit" set. R-45 found a different Copilot failure: broad `--allow-tool` kinds left out-of-class tools callable without a permission callback (PERM-B below). Codex's separate web-search gap is covered by R-46.
- **Control:** `tests/test_allowlist_classes.py`. The allowlist must contain every class id in the tool list that the pinned build wrote to its own native record (`tests/fixtures/native/claude-code/tools-2.1.282-win32.jsonl`, cut from the cell above). An id the build advertises that is not classified fails the test. A native test fails when the installed pin is not the fixture's build or platform, so a pin bump forces a recut, and a new id then turns the test red. It was observed red at `39a16d8` (`{'PowerShell'}` missing). The negative fixture `tests/fixtures/ledger/r34-cc-opus-pack-on-powershell-denied.json` is kept as the negative control.
- **Status:** `partially-controlled`. Recutting the fixture needs one real cell's native record: only an authenticated session writes the list, because an unauthenticated `claude -p` init omits `PowerShell`. The recut is therefore a manual step at a pin bump, forced by the native test.

### PERM-B: a tool that runs without a permission callback is invisible to a permission-count control
- **Signature:** a harness advertises an out-of-profile tool as safe. Calling it never requests permission, so a zero-denial or zero-permission count appears valid while the agent has a wider capability set.
- **Why it survives:** the driver can refuse only callbacks it receives. Copilot's committed pack-on checkpoint advertised 21 ids as safe, including web and GitHub MCP tools; R-45 found that the old profile named broad tool kinds rather than the allowed ids. R-46 found that Codex's profile omitted its promised web-search setting and its reader ignored `web_search_call`.
- **Instances (2026-09-25, run `qual-r45-1`; R-55, R-56):**
  - **Codex:** the account's app connectors (`apps` feature, on by default) reached a cell as the `codex_apps` MCP server. The model called `higgsfield.create_website`, which has write semantics; the call failed at the connector. In code mode the call sits inside `exec`, so it left no tool row.
  - **Claude Code:** 8 `mcp__claude_ai_*` account connector tools were advertised to the cell through the copied login. `ToolSearch` ran with no callback.
- **Sweep:** Copilot and Codex profiles and readers are fixed in the R-45/R-46 seam slice and the apps slice (`features.apps = false`, a nested MCP item recorded as class `other`). Claude Code seeds `disableClaudeAiConnectors: true`. Re-qualification: `requal-codex-1` made no MCP call, and `requal-claude-1` advertised 0 connectors. `WebFetch` was refused by callback (Verified, R-56); `WebSearch` remains Inferred.
- **Control:**
  - `tests/test_allowlist_classes.py` compares Copilot's explicit allowlist with every id in the pinned build's own checkpoint, and runs the fixed-profile test on the fixture recut from `qual-r45-1`.
  - `tests/test_profiles.py` checks Copilot's flags, Codex's `web_search` and `apps` settings, and Claude's `disableClaudeAiConnectors`.
  - The telemetry tests require Copilot's `tools_advertised`, a Codex `web_search_call` row and a nested MCP row.
  - **Per cell (W2-VIEWS-FU):** an executed class-`other` call, or an out-of-class advertised Copilot tool, makes the cell `invalid (out-of-profile tool called)` (HB-VAL-008). A refused call is the HB-VAL-009 warning. `tests/test_telemetry_copilot.py` holds the reader's class table to the profile's `--available-tools` list.
- **Status:** `controlled` for Copilot, Codex and Claude Code on the pinned builds. A pin bump re-runs the class tests; a new id or tool fails them.

### WIN-A: a transient Windows refusal of a folder rename fails a build
- **Signature:** `os.replace(tmp, dest)` at `workspace._land` raises `PermissionError: [WinError 5] Access is denied` while another process briefly holds a handle inside the freshly built folder (antivirus, or the git process that just exited). The build fails, although the same rename succeeds moments later.
- **Why it survives:** it is timing-dependent, and every re-run passes. So each occurrence was written off as a flake.
- **Instances (2026-09-25):**
  - The W2-TASKS-a author's first full suite.
  - The W2-TASKS-b slice-1 author's first full suite.
  - The Leader's suite after the W3-GRADE-CORE join (`test_pack_markers_have_a_real_builder_positive_control`, at `.../tools/pack/.ca032f007b33.*.tmp`).
  - The same path runs in production for every task source and pack checkout, so a real run could fail a cell for it.
- **Sweep:** the other `os.replace` sites that rename a folder (not a file) in `src/`: `_land` is the only one; the ledger's `os.replace` calls rename files.
- **Control:** `_land` retries a `PermissionError` with a bounded backoff (`RENAME_BACKOFF`, about 1.55 s in total), then raises. `tests/test_workspace.py::test_a_transient_windows_rename_refusal_is_retried` was observed red (the refusal was not retried) and is now green; `test_a_rename_refusal_that_never_clears_still_raises` guards the bound. `tests/mutations/workspace.json` holds both mutants, and the two race mutants were re-pointed at the new branch.
- **Status:** `controlled`

### CLN-C: a worktree force-removed in the same command as the check that should have stopped it
- **Signature:** the Leader prints a tree's dirty-file and unmerged-commit counts, then runs `git worktree remove --force` and `git branch -D` in the same command, so the counts are never read before the removal.
- **Why it survives:** the Leader expected an empty tree (0 turns reported), and the check looked like a guard even though nothing gated on it. `--force` and `-D` override exactly the refusals that would have caught it.
- **Instances:** `2026-09-25`, after the Codex usage limit. `w2-stopi-4` showed `3` dirty files and `2` commits ahead, and was removed anyway. The two commits were recovered from the object store (`git branch w2-stopi-4 0f24e77`). The three uncommitted files, the slice's in-progress tail, were lost.
- **Sweep:** every removal this session went through `cleanup_merged.sh` or `coord worktree cleanup` (both HOLD a dirty or unmerged tree), except the HARBOR tree (untracked, inspected first) and this one.
- **Control:** the Leader never runs `git worktree remove --force` or `git branch -D` directly. A failed or partial slice's tree is kept until its commits are on a named branch and its dirty files are inspected, and removal goes through the holding scripts. For now this is a Leader procedure. The upgrade trigger is a second instance: a wrapper that refuses `--force` on an unmerged branch.
- **Second instance, 2026-09-25 (the R21-3 capture):** the Leader removed a throwaway detached tree (`pre-s3`, made to run a test on an old commit) with `git worktree remove --force`, the control's own forbidden command. Nothing was lost: it held one copied test file and no commits, and the test's output lived outside it. The rule stays as written: a throwaway tree is removed plainly, or through `cleanup_merged.sh`, after its untracked files are named. **Hook upgrade trigger:** a third instance.
- **Status:** `observed` (Leader procedure; second instance)

### VEND-A: a vendored file the host repository's ignore rules drop
- **Signature:** a task base is vendored byte for byte into `tasks/<ID>/workspace/`, but a path in it matches this repository's `.gitignore` (`dist/`, `build/`). The file exists on the author's disk, so every check there passes; a clean checkout lacks it.
- **Why it survives:** the author's tree is not a clean checkout. `git add tasks/<ID>` silently skips ignored files, and the author's own full suite reads the untracked file from disk.
- **Instances:**
  - `2026-09-25`, the D1 join: `tests/AiDe.Core.Tests/fixtures/first-use/standin-adapter/dist/index.js` (ignored by `.gitignore:8` `dist/`) was never committed. The Leader's full suite on `main`, which runs after the merge, found it: `test_d1_workspace_matches_pinned_git_archive_byte_for_byte` failed on the file set.
- **Sweep:** `git ls-files -o --exclude-standard tasks/` is empty. The ignore patterns that can match a vendored tree are `dist/` and `build/`; `bin/` and `obj/` are refused by the validator (W2-VALIDATE).
- **Control:**
  - `.gitignore` re-includes `dist/` and `build/` under `tasks/*/workspace/**`, so the class cannot recur for task bases.
  - The byte test compares the pinned archive against the checkout.
  - The Leader runs the suite on the merged `main`, not only in the author's tree.
- **Status:** `controlled`

### COORD-B: a worker's message or seam request not read by the Leader
- **Signature:** a worker sends `coord mail` or raises a `coord request` (a seam grant, a blocker). The Leader reads only the worker's final hand-back (the runner result or the subagent report). The request expires without a ruling, and the worker takes its fallback. The work stalls, or a fix lands outside its owner.
- **Why it survives:** the runner result says `ready_for_review` and carries the commit receipts. Nothing in it says a request was raised and left open. The fallback is correct behaviour, so every gate stays green.
- **Instances:**
  - `2026-09-25`, W1-COP-I slice 5: `worker-codex-copi5` raised `req-01M3B110FQ1RQS4W2HRVTKN17B` (a `plan.py` seam: the bool `defaultDisabled` that canonical JSON forbids) and mailed the Leader three times. The request expired without a ruling. The fix went to a Claude Sonnet loop-back (`33bbf40` → `0baaa96`) only after the Leader read the mail. At first the Leader also wrongly reported that the request never reached the primary.
- **Sweep:** every worker hand-back in this plan. The other mail on record (slices 1, 2 and 5) was informational and needed no ruling. Why the pack's `mail-doorbell` hook, wired in `.claude/settings.json`, did not surface the request in the Leader's session was not diagnosed.
- **Control:** at every hand-back, the Leader runs `coord mail read` and `coord request list` before it reviews the result, and rules on or closes each open request. For now this is a Leader procedure. The upgrade trigger is a second instance: the join gate would then refuse while a request from that worker is open.
- **Status:** `observed` (Leader procedure)

### TEST-A: a whole-output substring check that later output satisfies
- **Signature:** a test asserts that a common phrase appears anywhere in a rendered page or CLI output (`"not recorded" in doc`), and it means one specific element. A later feature prints the same phrase elsewhere. The element can then break, and the test still passes.
- **Why it survives:** the test was correct when it was written. The feature that makes it vacuous changes another part of the page and touches no test. Only a mutant of the original element shows the test has stopped proving anything.
- **Instances:**
  - `2026-09-25`, the R-35/R-36(a) join: `report.json`'s mutant "a missing header fact rendered empty" survived on `main`. `test_the_header_shows_recorded_facts_and_not_recorded_for_the_rest` asserted `"not recorded" in doc`, and later columns (the `calls_per_cell` Measure, 6b; the context-window fact, R-32) print that phrase too. The fix pins the assertion to `<dt>Defender real-time exclusion</dt><dd>not recorded</dd>` (`60643a3`); `report.json` is 22/22 killed.
  - The same join, a close relative: the R-36 connector-name guard read only `report/__init__.py`, so a name seeded in `cli_table.py` passed. It now reads every report module (`a8d0833`), and the seeded name fails it.
  - `2026-09-25`, spike S-04: the probe's "tool in the native record" check matched the bare word `ask_user`. The prompt contains that word, so Codex's A1 rollout read `true` from the user message alone. It now requires the harness's qualified id (`mcp__scripted_user__ask_user` or `mcp.scripted_user.ask_user`). A prompt-only fixture in `probe_selftest.py` fails the old check (observed red) and passes the new one.
- **Sweep:** every `"not recorded"`, `"not graded"` or `"unranked"` assertion in `tests/`. The others are scoped to a header row or a table row.
- **Control:** the named-test mutation sets (`tools/mutate_check.py`, TOOL-B). A vacuous assertion shows up as a surviving mutant once the set is re-run. Tests that check one element assert on that element's markup, not on the whole page. The upgrade trigger is a second instance: the join gate would then re-run every mutation set of the modules a track touched.
- **Status:** `observed` (the mutation sets catch it once they are re-run)

### OUT-A: a saved measurement reported as a failure because printing it failed
- **Signature:** a tool saves its result file and then prints the same result to stdout. The text holds a character the console cannot encode: a Windows pipe defaults to cp1252, and model text carries `−` or emoji. The print raises, and the exit status turns non-zero. The caller reads the exit code as the measurement, although the saved file says the opposite.
- **Why it survives:** offline tests use ASCII fixtures, and an interactive terminal is often UTF-8. Only a real model's text on a redirected Windows pipe hits it. The saved file is correct, so nothing that reads the file fails.
- **Instances:**
  - `2026-09-25`, spike S-04 (W2-USER-D): `probe_turn.py` printed its summary with `ensure_ascii=False`. It raised `UnicodeEncodeError` in 3 of 11 Leader runs. For `claude-code a1` the exit was 1 although the turn called `ask_user`, and the Leader's exit-code summary reported "not called". The saved summary was right.
- **Sweep:** `print(json.dumps(..., ensure_ascii=False))` or a `stdout.write` of the same across `src/`, `tools/`, `tests/`: no other instance (grep, 2026-09-25). The other S-04 scripts print with `ensure_ascii=True`.
- **Control:** `probe_selftest.py` `test_emit_on_a_legacy_console` runs `emit` under `PYTHONIOENCODING=cp1252` with a `−` and an emoji and requires exit 0. It was observed red on the old `emit` (2 failures), then green. The rule: stdout carries JSON escapes (`ensure_ascii=True`); files are written in UTF-8.
- **Status:** `controlled` for the probe (the self-test is run by hand before a probe run); the upgrade trigger is a second instance, in a tool whose output a gate reads.
- **Second instance, on the decode side (2026-09-25, W2-USER-M): the upgrade trigger fired.** `tools/mutate_check.py` read pytest's output with `text=True`, which uses the locale codec (cp1252). A failing test whose message held U+3041 (UTF-8 bytes include `0x81`) crashed the tool with `UnicodeDecodeError`, then `TypeError`. `mutate_check` is a gate. **Control:** `subprocess.run(..., encoding="utf-8", errors="replace")`, with `tests/test_mutate_check.py::test_non_ascii_test_output_is_decoded_as_utf8_not_the_locale` in the default suite, observed red (the exact crash), then green. The rule, extended: child output is decoded as UTF-8 explicitly, never by the locale. **Sweep:** `text=True` without `encoding=` in `src/`, `tools/` and `tests/` is a next step, done by grep at the next join.

---

### STOP-A: a deadline requested on an exceptional loop branch but never serviced
- **Signature:** the engine sets a cancel event and `kill_deadline`, but the loop branch entered after a ledger failure does not call `_check_kills`. A child that ignores cancel remains alive after the grace.
- **Instances:** 2026-09-25, W2-STOP-I slice 3. The first full suite failed `test_after_the_ledger_breaks_no_worker_blocks_forever` at its 30 s bound. The normal branch called `on_tick`; the broken-ledger branch called `_kill_all` repeatedly without checking the deadlines. Final review then found that `a.terminated` prevented a second attempt while a failed termination left the job active; `test_hard_kill_retries_until_the_job_is_empty` was red before the guard changed.
- **Sweep:** the normal, broken-ledger and host-suspend paths in `Engine.run` were checked. The normal branch calls `on_tick`; the broken branch now calls `_check_kills(clock())`; host suspension requests a kill through `_kill_all` and the next tick checks it.
- **Derived rule:** every path that requests a bounded cancel must keep servicing its hard deadline until the job is confirmed empty. A broken ledger or an unsuccessful first terminate cannot disable process cleanup.
- **Control:** `tests/test_engine.py::test_after_the_ledger_breaks_no_worker_blocks_forever` was observed failing on the branch regression and passes after the fix. `test_hard_kill_retries_until_the_job_is_empty` was red on the one-attempt guard and green after it was removed. `test_engine_kill_deadline_uses_one_injected_clock` checks the floor for timeout, host suspension and stop; the `kill before the grace ends` mutant in `tests/mutations/stop.json` is killed.
- **Status:** `controlled`

---

### GATE-RUN-A: a read-only gate run written by a concurrent build or git command
- **Signature:** an archived benchmark run, which is write-once by design and whose bytes `bench verify` checks against `archive_files`, is written by a process that treats it as a working tree: a `dotnet build` or restore run in place, or a git command that refreshes `.git/index`. The run's integrity breaks silently until a gate-run test or `bench verify` reads it.
- **Instances:**
  - `2026-09-25` 11:09–11:10 PDT: about 1,900 `bin/obj` files across all six `row15-d1-1` cells were rewritten or created, while an Agy slice (rigor), a Grok slice (Stryker spike) and the Leader's default ring all ran. The rigor code builds only in copies, so the writer is **Inferred**: an exploratory command by one of the workers. The Leader restored from the scratch copy before capturing the restore metadata that would have named it. It was caught by `test_the_d1_gate_cells_conform_and_the_archive_is_unchanged`. 273 files were restored and 1,605 created files removed, each by its `archive_files` row hash.
  - `2026-09-25` 01:25 PDT: `.git/index` of cells `35af…` and `c3d4…` changed after archiving (the same mtime is in the scratch copy made later). The original bytes are not recoverable, so `bench verify row15-d1-1` stays at exit 5 with these two findings (Flagged).
- **Why it survives:** W3-GATE-RUNS made every worktree's tests read the primary checkout's real runs, which is right for coverage, but the folders are writable by any process of the user. A run's archive looks like a normal working tree to a build tool.
- **Control:**
  - Every batch gate runs `bench verify` on both gate runs; a new finding blocks the push.
  - Every brief says to run no build, restore or git command under `runs/`.
  - Tried and reverted: an OS-level deny of write on the archive folders (`icacls /deny (W,D,DC)`) also broke reads (`PermissionError` in `bench verify`).
- **Status:** `partially-controlled` (a check and a rule, not a prevention); the upgrade is an in-process guard that refuses a `procs.run` whose cwd is under a gate run.

---

### TRUTH-A: a ground-truth quantity whose human source is unavailable, re-sourced from a model under the human name
- **Signature:** a measure defined against human labels (calibration agreement, a labelled question set) loses its human source. The labels are then produced by a model, and the report keeps the human name. It is a sibling of the plausible-wrong-number class: the value looks measured, but it measures model-model agreement.
- **Instances:** `2026-09-25`, DR-CAL-1. The operator declined to label the 30 calibration items (R-58 had made them HUMAN). R-72 rejected model-authored labels and ruled the human half NOT_RECORDED `no human labels (operator declined 2026-09-25)`. Caught before any label was written.
- **Sweep:** the scripted-user matcher's labelled question set (spec `:457`) is the one other human-labelled set; its provenance is checked at the next GR-CLAR change. A model-labelled set is disclosed under its own name or NOT_RECORDED.
- **Control:** R-72 condition 3's test (`intended_score` is never read as a label) lands with W3-CAL and GW-I s5. The header rule: a row's name states its source.
- **Status:** `open` until those tests land.

---

### SEED-A: a tool's behaviour asserted from its documentation or a belief, not measured
- **Signature:** a design seed or a launch shape states what a CLI or build tool will do (a flag's effect, an exit code) from its `--help` text or from expectation. The first live measurement shows it does something else. The belief already sat in a design or a builder as if verified.
- **Instances:**
  - `2026-09-25`, W3-GR-CODE c1: the graders design's seed "a broken `ProjectReference` in a D1 test project → `build_and_suite_clean` 0". Measured, it is `warning MSB9008` and `dotnet build` exits 0, so it scores 1 (R-71).
  - `2026-09-25`, the R-63 Copilot judge spike, turn 1: "an empty `--available-tools` denies every tool". R-45 had verified that the flag exists, not what an empty variadic does. Measured, it filtered nothing: 17 tools advertised, and `powershell` ran without approval (R-70; `docs/notes/spike-gw-headless.md`).
- **Why it survives:** "Verified" was attached to the flag's presence in `--help`, then carried over to its behaviour. A seed that is only a sentence in a design has no test until a slice builds one.
- **Derived rule:** a seed or launch shape cites the measurement that produced its value (a spike note line or a captured record). Otherwise it is marked `assume:` with what confirms it, and the first slice that builds it measures it before depending on it.
- **Control:** the probe self-test pins the measured Copilot argv (`the allowlist names no real tool`, `custom instructions off`), and the gateway mutant "bare --available-tools" is killed (`tests/mutations/gateway.json`). The probe's `qualified` gate fails any turn whose record advertises a tool, so a flag that stops working on a new build fails the next qualification rather than a cell. For the dotnet seed, the metric-level test row "exit 0 + MSB9008 → 1" lands with the GR-CODE c2 join (R-71 condition).
- **Status:** `controlled` for the Copilot shape; `open` for the seed row until the GR-CODE c2 join.

---

### PERM-C: a scenario's required capability denied by the profile every scenario shares
- **Signature:** one tool profile serves every scenario, and it denies a capability that one scenario's measures are defined over. That scenario then measures nothing. Or it measures an agent that works around the denial, and the workaround is scored as the treatment. It is a sibling of PERM-A: there, an id is missing from a class; here, a whole class is missing for one scenario.
- **Instances:** `2026-09-25`, DR-F1-2 (R-74). F1's `model_map_adherence` and `per_agent_attribution` are defined over sub-agent sessions (`tasks/F1/oracle/README.md:57-58`). Claude Code's `Agent` and Copilot's `task`, `write_agent`, `read_agent` and `list_agents` were out of profile on every cell (`test_allowlist_classes.py:48-52`, `:68-69`), so a delegating F1 cell would read `invalid (out-of-profile tool called)`. Caught before any F1 cell ran.
- **Why it survives:** the profile is written once from ADR-0004's classes, and the allowlist tests check it against the build's ids, not against what each scenario needs. A scenario is added to the BOM without anyone reading its metrics against the profile.
- **Sweep:** scenario 1's `scripted_user` is the other scenario-conditional profile addition. It already follows the per-cell shape (`profiles.py` argv, R-51 c1). Scenario 7's toolchain is a workspace fact, not a tool profile (`bom.yaml:49-51`). No other scenario's metric names a tool class the profile denies.
- **Control:** the scenario-parameterised allowlist tests in `tests/test_allowlist_classes.py`. A scenario-6 cell's allowlist is exactly the classes plus the delegate ids; every other scenario's names no delegate id. `tests/test_delegate.py` checks that every other cell is seeded and launched byte for byte as before. The scenario rule has one emitter, `views._out_of_profile` (`tests/test_views.py`, R-74 c2). Mutants: `tests/mutations/scenario6.json`.
- **Status:** `controlled` offline. The allowance on each harness still waits for its R-74 c6 qualification turn.

### MAP-A: a treatment parameter authored in one vendor's ids and applied to every combo
- **Signature:** a per-task parameter that names models (a role → model map) is written in one vendor's ids. The same text reaches every combo, so a cell of another vendor either cannot follow it or is scored against a routing it cannot perform. A value-only resolver also admits the other vendor's ids as allowed served models in every cell. It is a sibling of PERM-A.
- **Instances:** `2026-09-25`, DR-F1-1 (R-73). The F1 draft map (`0f8cc9f`, `task.yaml:28-31`) had Anthropic ids only, with bare role keys. `views._mapped` folded every value into one allowance (`views.py:436-437`), so a Codex cell serving `claude-sonnet-5` read `valid`. Red at `12d9990`.
- **Why it survives:** the map was authored against the one harness whose models the author knew. The served-model check read values and ignored whose they were.
- **Sweep:** `model_map` is the only per-role parameter in `bench-task/1` (`config.py`). `auxiliary_models` is already per harness (`profiles.py`). No other task field names a model.
- **Control:** keys are `<role>@<vendor>`, and the vendor is a profile fact (`bench/profiles/*.yaml` `vendor:`). `config.model_map_problems` refuses a bare key, an undeclared vendor, a missing role for any declared vendor, and an auxiliary-model value (from draft on). `plan.resolved_model_map` is the one resolver, and `tests/test_model_map.py` asserts that no second `@` parser exists. `bench plan` refuses a scenario-6 cell whose every role equals its pin. Mutants: `tests/mutations/scenario6.json`.
- **Status:** `partially-controlled`. The check that a harness of the vendor serves the value is not built, because no committed per-harness served list exists (R-73 c1).

### SPIKE-A: a grader precondition adopted from a spike whose fixture lacked the real task's shape (new test project vs. edited vendored suite)
- **Signature:** a grader refuses the run on a precondition taken from a spike. The spike's fixture was a new test project. The frozen task edits a vendored suite whose baseline is already red. The precondition then fails on every cell of that task, before the cell's own change is measured. Sibling of MOD-A: the check looks verified, and it fails for a reason other than the one the metric is about.
- **Why it survives:** the spike exited the way the design wanted, on a tree that did not have the task's shape. The flag was copied into the grader as if that exit had been measured on the task.
- **Instances:** `2026-09-25`, DR-MUT-1 (R-75). `--break-on-initial-test-failure` came from the c6a spike (`docs/notes/spike-gr-code-stryker.md:93`), a new project `D1.HiddenTests` with no vendored test. D1 edits `AiDe.Core.Tests` in a vendored subset with no `AiDe.sln` and no `docs/`, so 74–75 tests are red before any mutant. With the flag, every real D1 cell was NA `mutation run failed: 1`. On D1 gate cell `c3d40fa1377ba0dc`, Stryker 4.16.0 without the flag logged 75 failing tests, exited 0, and scored 0.8095 twice.
- **Sweep:** at the join, the other D1 graders that run the vendored tree (`build_and_suite_clean`, `static_analysis_delta`) are checked for the same green-baseline belief.
- **Control:** every grader spike names the frozen task tree it ran on, or the design's `simplify:` names the task that reaches its ceiling. `mutation_score`'s `simplify:` now names D1 (R-75). `tests/test_grade_mutation.py::test_stryker_config_json_pinned_timeout_and_command_args` asserts the flag is absent. The seeded red baseline is `test_d1_reference_plus_seed_or_no_compute_one_always_failing_scores_zero`.
- **Status:** `observed`

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
