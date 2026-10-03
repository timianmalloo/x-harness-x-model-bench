---
id: brief-eval-tool-gsm-b
title: "Brief TOOL-GSM-B: the Grok served-model reader on a deadline-killed session"
type: plan
status: proposed
owner: "@timianmalloo"
links:
  - { to: coordination-eval-wave2-e1-briefs, rel: implements }
  - { to: brief-eval-tool-gsm, rel: depends-on }
  - { to: rulings-register, rel: depends-on }
review-by: "2026-10-17"
summary: "tools/grok_served_model.py falls back to the assistant rows of chat_history.jsonl when usage.json is absent, says which file it read, and still exits non-zero when nothing is recorded or the ids disagree with the pin."
---

# TOOL-GSM-B: `tools/grok_served_model.py` on a session with no `usage.json`

**Session** `x-gsmb-e1e4` · **branch** `build/eval-grok-served-model-b` · **harness** Claude Code Agent tool, `model: sonnet` (served `claude-sonnet-5-5`, R-91) · **budget** 30 calls · 60k · 1 session · 0.5 h · **fallback** a fresh Sonnet session. The path is Coordinator-owned (R-92 condition 1); you write it on the Coordinator's behalf. Base: `main` with TOOL-GSM merged (`tools/grok_served_model.py`, `tests/test_grok_served_model.py`, `tests/fixtures/grok_sessions/**`).

**Finding.** On a deadline-killed Grok session, `usage.json` is never written, so `tools/grok_served_model.py` exits 2 "not recorded" (it loads `usage.json` in `check`, so a missing file is `NotRecorded`). Case: X-G1 retry `w2-g1b-e1e4` (red `a08a4060`, green `76deb253`, killed at 1,200 s). The Leader read `grok-4.7-build` x43 from the `assistant` rows of `chat_history.jsonl` by hand. The chat history is the source R-92 already names ("read from responses"); `usage.json` and `summary.json` are only cross-checks. A control that fails on the very session it exists for is not a control.

## Owned paths
`tools/grok_served_model.py`, `tests/test_grok_served_model.py`, `tests/fixtures/grok_sessions/**` (new fixture folders only; do not edit the existing ones).

## The change
- When `usage.json` is absent, read the served ids from the `assistant` rows' `model_id` in `chat_history.jsonl`, and say so. The source line names the file read: for example `source=chat_history (usage.json absent)`. The other lines print as today, with `usage.json models: (absent)`. When `usage.json` is present the output and every exit code stay as they are.
- `summary.json` stays a cross-check: if it is absent too, the line says `(absent)`; it never decides the exit code (R-92 c1: responses decide). **Open a real killed-session directory first** (the `w2-g1b-e1e4` Grok session under `~/.grok/sessions/`, the Leader names the id) and read which files exist; do not assume `summary.json` is there.
- Exit 0 iff at least one response was read and every id starts with the pin. Exit 1 when any id does not (each named with its count) or a response row has no id. Exit 2 ("not recorded") when `chat_history.jsonl` is missing, unreadable or holds no `assistant` row. Never print a plausible id that was not read.
- Stdlib only; reads only; ids and counts only, no prompt or response text.

## Acceptance items (red first)
1. New synthetic fixtures (copied from the real shapes; no user content): `only_chat_history` (only `chat_history.jsonl`, all `grok-4.7-build`); `only_chat_history_mixed` (only `chat_history.jsonl`, one `grok-4.6-build` among 4.7 rows); `neither` (no `chat_history.jsonl`, no `usage.json`).
2. `only_chat_history` → exit 0, stdout contains `source=chat_history`. `only_chat_history_mixed` → exit 1 (non-zero), the 4.6 id and its count named. `neither` → exit 2, stdout starts `not recorded`.
3. The existing test `test_missing_usage_file_exits_2` encoded the old behaviour. Change it, in the red commit, to the new rule (its fixture `missing_usage` now exits 0 or 1 by its history), and say so in the report. Every other existing test stays unedited and green.
4. A mutant "the fallback reads `summary.json` only" must fail a test (`summary_only_47` style: the summary says 4.7, a response says 4.6, usage absent → exit 1).
5. One real run over the `w2-g1b-e1e4` session directory, recorded in your report (expected: exit 0, `grok-4.7-build` x43, `source=chat_history`).

## B2: `tools/mutate_check.py` refuses to run outside the project environment (class MUT-C)

A second, separate red/green pair in the same session (Leader's finding, 2026-10-03). Run with the global interpreter, which has no `harness_bench`, `mutate_check.py` reported all 80 `grade.json` mutants as `error`: an environment failure reported as mutant verdicts. Owned: `tools/mutate_check.py`, `tests/test_mutate_check.py` (or the existing test file for it).
- Before any mutant runs, `mutate_check` imports `harness_bench` in the same interpreter it will use for the tests. On failure it prints one line naming the interpreter (`sys.executable`) and "run it as `uv run python tools/mutate_check.py`", writes no verdict, and exits 2.
- Red first: a test runs `main` with a patched import failure and asserts exit 2, the message, and that no mutant was run (a mutant that removes the pre-check turns it red because verdicts appear).
- Also: if every mutant of a run ends `error`, the summary says "all mutants errored: environment suspected" and exits non-zero, never a per-mutant table alone.

## Exit
README §3 join gate. Report per README §4.
