---
id: brief-eval-tool-gsm-first
title: "Brief TOOL-GSM-FIRST: a --first mode for the Grok served-model reader (R-103 condition 3)"
type: plan
status: proposed
owner: "@timianmalloo"
links:
  - { to: coordination-eval-wave2-e1-briefs, rel: implements }
  - { to: brief-eval-tool-gsm-b, rel: depends-on }
  - { to: rulings-register, rel: depends-on }
review-by: "2026-10-17"
summary: "tools/grok_served_model.py gains --first: read the first assistant row's model_id from chat_history.jsonl and exit at once, non-zero on a non-grok-4.7 id, so the Leader can kill a drifted Grok turn inside 120 s (R-103 c3). Lands before X-H1a's dispatch. Claude Sonnet, one short session."
---

# TOOL-GSM-FIRST: the first-response read

**Session** `x-gsmf-e1e4` · **branch** `build/eval-grok-served-model-first` · **harness** Claude Code Agent tool, `model: sonnet` (served `claude-sonnet-5-5`, R-91) · **budget** 40 calls · 60k · 1 session · 45 min · **fallback** a fresh Sonnet session from this brief.

**Why** (R-103 condition 3, `docs/notes/rulings.md`): a Grok turn whose first response is not `grok-4.7*` is killed inside 120 s and retried once. The served id is in the first `assistant` row of `chat_history.jsonl`, written seconds after the prompt. Until this mode exists the Leader reads that row by hand. It must land **before X-H1a's dispatch**. Class **SERVE-A** (`docs/lessons/defect-classes.md`).

## Owned paths
`tools/grok_served_model.py`, `tests/test_grok_served_model.py`, new fixture folders under `tests/fixtures/grok_sessions/`. Not yours: `coord-runner.py`, `.tools/coord/runner-leader.sh` (the Leader wires the call), the defect register.

## Depends on
TOOL-GSM and TOOL-GSM-B joined ✓. Nothing else.

## Work (red first; E1 README §2)
1. **`--first`**: with a session dir (or `--tree`/`--session`), read `chat_history.jsonl` row by row and stop at the **first** `assistant` row. Print one line: `first response: <model_id> (row <n>)`, plus the row's own time field if the row has one (`assume:` the schema has a time field; confirm by reading a fixture row; if it has none, print the file's mtime and say so). Exit **0** when the id starts with the pin, **1** when it does not or the row has no id (`FAIL: pin <pin>; first response <id>`), **2** "not recorded" when the file is missing or holds no assistant row yet. It never reads `usage.json` or `summary.json` and never reads past the first assistant row.
2. **`--wait <seconds>`** (default 0, only with `--first`): while the result would be exit 2, re-read every 2 s until the wait ends; then the same exit codes. This makes the Leader's 120 s read one line (`--first --wait 120`). The poll is bounded by `--wait`; no other loop.
3. The default (join) mode is unchanged byte for byte: every existing test passes untouched.

## Tests
- **Red fixture (R-103 c3):** a session whose first assistant row is `grok-4.6-build` → `--first` exits 1 and names it. Red first: the skeleton commit accepts `--first` and returns 0, so the test fails on the exit-code assertion.
- First row `grok-4.7-build`, a later row `grok-4.6-build` → `--first` exits 0 (the first read is the fast kill, not the proof; the join mode on the same fixture exits 1). This pins the scope R-103 gives each mode.
- No assistant row yet (a user row only) → exit 2; with `--wait 3` and a fixture thread that appends a `grok-4.7-build` row after 1 s → exit 0. Event-driven: the test waits on the tool's exit, not on a sleep (TIME-B's scan stays green without a new allowlist entry; if you need one, give it a reason).
- A missing file → 2. A first row with no `model_id` → 1.
- Mutants in `tests/mutations/` for this tool if a set exists, else a new `grok_served_model.json`: "the first row's id is not checked", "reads past the first row".

## Acceptance items
1. The four tests above, red then green (SHA, node, failing assertion).
2. One live read against a real session store: `python tools/grok_served_model.py --first <the X-B1a session dir>` prints `grok-4.6-build` and exits 1; against `…-build-eval-x-g1b`'s session, exits 0. Paste both outputs in the report (R-103's table names both sessions).
3. The module docstring documents `--first` and `--wait` and their exit codes.

## Exit
E1 README §3 join gate. Report per E1 README §4.
