---
id: brief-eval-tool-gsm
title: "Brief TOOL-GSM: the Grok served-model reader (R-92 condition 1)"
type: plan
status: proposed
owner: "@timianmalloo"
links:
  - { to: coordination-eval-wave2-e1-briefs, rel: implements }
  - { to: rulings-register, rel: depends-on }
review-by: "2026-10-17"
summary: "A stdlib script that reads one Grok dispatch's session directory and fails unless every response was served by grok-4.7; it must join before the second Grok dispatch (R-92)."
---

# TOOL-GSM: `tools/grok_served_model.py`

**Session** `x-gsm-e1e4` · **branch** `build/eval-grok-served-model` · **harness** Claude Code Agent tool, `model: sonnet` (served `claude-sonnet-5-5`, R-91) · **budget** 40 calls · 80k · 1 session · 0.5 h · **fallback** a fresh Sonnet session. The path is Coordinator-owned (R-92 condition 1); you write it on the Coordinator's behalf.

**Why.** R-92: Q0 served `grok-4.6-build` under `-m grok-4.7`; Q0b served `grok-4.7-build`. The runner checks no served model for Grok (`coord-runner.py:175` is Copilot only). "The served model is read from responses, never from argv or a model list … scripted before the second Grok dispatch … so it is a control, not a habit (CI6)."

## Owned paths
`tools/grok_served_model.py` (new), `tests/test_grok_served_model.py` (new), `tests/fixtures/grok_sessions/**` (new, synthetic).

## What it does
- Input: one session directory, `~/.grok/sessions/<tree>/<session id>/` (positional), or `--tree <worker tree path> --session <id>` resolved the way grok names the folder. **Open the real Q0b directory first** (`~/.grok/sessions/…/01a102c2-a634-7b30-a16c-501a46a91262/`, plan harness table) and read the actual file shapes of `chat_history.jsonl`, `usage.json` and `summary.json`; do not assume them.
- Output (stdout, one block, pasteable into the plan's Tracks row): count per served id from `chat_history.jsonl` `model_id`; the ids in `usage.json`; `summary.json` `current_model_id`.
- Exit 0 iff every response id starts with `grok-4.7` and at least one response was read. Exit 1 when any response id does not (name each id and its count). Exit 2 when a file is missing or unreadable ("not recorded", never a plausible pass, IO). The pin prefix is a module constant `PIN = "grok-4.7"` and a `--pin` flag.
- Stdlib only; reads only; prints no prompt or response text (ids and counts only).

## Acceptance items
1. Red first: tests with synthetic fixtures copied from the real shapes (no user content): all `grok-4.7-build` → 0; one `grok-4.6-build` row among 4.7 rows → 1, naming it; `summary.json` alone says 4.7 but a response row says 4.6 → 1 (responses decide, R-92 c1); empty history → 2; a missing file → 2. A mutant that reads only `summary.json` must fail a test.
2. One real run over the Q0b directory, recorded in your report (expected exit 0, `grok-4.7-build` × 8 in `chat_history`).
3. The plan README §3 line works as written: `python tools/grok_served_model.py <session dir>`.

## Exit
README §3 join gate. Report per README §4.
