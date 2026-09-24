---
id: "findings-t8-reader-and-paths"
title: "Findings → tests: track T8 reader-and-paths"
type: proof-pack
status: accepted
owner: "@timianmalloo"
phase: "Phase 1 · walking skeleton"
tags: [proof, findings, red-first, T8, telemetry, cli]
links:
  - { to: coordination-phase1-finish, rel: relates-to }
review-by: "2026-12-22"
summary: >-
  Two loop-back defects found by the real E2E. T8-1: the Codex reader took the pack-on cell's injected
  AGENTS.md instructions block as the prompt (US-10). T8-2: a relative --tools-dir left the pack root
  relative, so pack-apply.py was looked up under the cell working copy and never found (HB-CELL-113).
  Red 05f52fa / 62c38ba, fixed in 9ddbe38, with both t8.json mutations killed.
---

# T8: reader-and-paths (two loop-back defects)

**The Coordinator transcribed this file** from the track's report, because the harness refused the track's write. **The Coordinator also checked the evidence directly:**
- Both red SHAs were re-run in throwaway worktrees and failed as reported. `05f52fa` failed at `tests/test_telemetry.py:67` with the AssertionError. `62c38ba` failed at `tests/test_cli.py:215` with the AttributeError.
- `tests/mutations/t8.json` was re-run: every mutation was killed.
- The fixture was scanned for operator identifiers and secret shapes. There were no identifier hits. The two secret-pattern hits are `task-discipline`, a false positive.

## Defect 1: the Codex reader takes the pack's AGENTS.md block as the prompt (US-10)

### Symptom

The Coordinator measured this on a real run (`C:/Projects/bench-test/repro-us10b/runs/r1`). With the pack on, the first user message of the Codex 0.156 cell has three content parts:
- `<recommended_plugins>...`;
- a text that begins `# AGENTS.md instructions for <cwd>\n\n<INSTRUCTIONS>\n...\n</INSTRUCTIONS>`;
- `<environment_context>...`.

`first_user_text` in `telemetry/codex.py` skipped the `<tagged>` parts but not the AGENTS.md part. So it returned the ~26 KB instructions block instead of the next user message, which is the real prompt. The E2E's US-10 check (prompt hash == the plan's `prompt_sha256`) then failed for the Codex pack-on cell.

### Root cause

The skip predicate was `t.lstrip().startswith("<")`. The AGENTS.md block starts with `#`, so the reader never saw it as injected context. It was the only text part that did not start with `<`, so the reader took it as the whole message's text.

### Fix

`src/harness_bench/telemetry/codex.py` gets a new predicate, `_is_injected_context(text)`. It recognizes two forms: a `<tagged>` block, and text that starts with `# AGENTS.md instructions for `. That second form is the exact observed shape; no other injected form is guessed.

`first_user_text` is set only when at least one text part is not injected context. It is built only from those parts. This is the same shape as before, generalized. When every part of a user message is injected context, the reader skips the whole message and uses the next user message (the real prompt). This matches the observed record.

### Fixture

`tests/fixtures/native/codex/pack-on.jsonl` is a real Codex 0.156.0 rollout record from the Coordinator's US-10b repro, scrubbed:
- the operator's home path became `C:\Users\operator`;
- the run-specific cell path became `C:\cells\cell`.

These are the same generic forms `ok.jsonl` already uses. The record held no operator name or email. Provenance is in `tests/fixtures/native/codex/provenance.json`, which follows the pattern of `tests/fixtures/acp/provenance.json`.

## Defect 2: a relative `--tools-dir` breaks the pack install (HB-CELL-113)

### Symptom

`bench --tools-dir .tools/harness run ...` failed a pack-on cell with `HB-CELL-113`. The run looked for `pack-apply.py` at `<cell ws>\.tools\pack\...\pack-apply.py`.

### Root cause

`cli.cmd_plan` and `cli._workspace_builder` derive the pack root as `Path(args.tools_dir).parent / "pack"`. With a relative `--tools-dir`, that root stays relative. `workspace.install_pack` runs `pack-apply.py` with `cwd=str(ws)`, so the subprocess's working directory is the cell's working copy, not the process's. The relative script path therefore resolved under `ws`, where the script does not exist, no matter where `bench` was launched.

### Fix

`src/harness_bench/cli.py` gets a new `_resolve_paths(args)`. It resolves every path argument (`--root`, `--runs`, `--cells-root`, `--tools-dir`, `--pack-source`, `--matrix`) to an absolute path once, with `Path(value).resolve()`. `main()` calls it right after it fills in the `--runs` default. Every path derived later is then absolute, whatever a subprocess's `cwd` is.

## Proof

- **Red T8-1:** `05f52fa`, `test(T8-1): codex first_user_text skips the AGENTS.md instructions block (red)`. `tests/test_telemetry.py::test_codex_first_user_text_skips_the_agents_md_instructions_block` failed at `tests/test_telemetry.py:67`: `AssertionError: assert '# AGENTS.md ...INSTRUCTIONS>' == 'Implement th...pendencies.\n'`. The Coordinator re-ran it.
- **Red T8-2:** `62c38ba`, `test(T8-2): a relative --tools-dir must still resolve pack-apply to absolute (red)`. `tests/test_cli.py::test_a_relative_tools_dir_resolves_absolute_and_the_pack_on_build_succeeds` failed at `tests/test_cli.py:215`: `AttributeError: module 'harness_bench.cli' has no attribute '_resolve_paths'`. The Coordinator re-ran it.
- **Green:** `9ddbe38`. Both red tests pass, and the full suite is green.
- **Mutation:** `tests/mutations/t8.json` has 2 entries. `uv run python tools/mutate_check.py tests/mutations/t8.json` killed both; the Coordinator re-ran it.
  - "T8-1 codex first_user_text stops skipping the AGENTS.md instructions block" is killed by the new US-10 fixture test.
  - "T8-2 cli._resolve_paths stops resolving path arguments to absolute" is killed by the new relative-`--tools-dir` test.
- **Gates (track-reported):**
  - `uv run pytest -q -p no:cacheprovider -m "not credentials"`: 501 passed, 5 deselected (126.27 s).
  - `uv run ruff check src tests tools`: all checks passed.

  The join's recount re-measures both.
