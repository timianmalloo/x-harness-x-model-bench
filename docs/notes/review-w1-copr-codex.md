---
id: review-w1-copr-codex
title: "W1-COP-R cross-vendor join review"
type: decision-note
status: accepted
owner: "@timianmalloo"
tags: [coordination, review, copilot, telemetry]
links:
  - { to: coordination-finish-harness-bench, rel: relates-to }
review-by: "2026-10-08"
summary: >-
  Codex review of W1-COP-R at f266f09: the main Copilot extraction rules pass the focused
  suite, but a toolCallId pairing mutant survives and a successful tool call can carry a
  non-null outcome_code. Block the join until both are covered and the latter is fixed.
---

# W1-COP-R join review — Codex

**Verdict: BLOCK.** I reviewed `git diff 2e9cc3b..f266f09` on `w1-copilot-reader` at `f266f09`, reading its checkout without editing it. The baseline focused command passed **58 tests**. The reader implements the principal model, version, prompt, and denial rules, but F1 leaves the required `toolCallId` correlation without a killing test, and F2 violates the amended ledger's null-on-success rule. The coordination plan requires all three reviewer mutants to be killed before join (`docs/coordination/coordination-finish-harness-bench.md:90`); one survived. Add an overlapping, out-of-order completion test that kills M1; make a successful completion's `outcome_code` null and test that case. Re-run the same focused command and mutants before clearing this review.

## Findings against the design and rulings

| ID | Evidence and judgment |
| --- | --- |
| F1 — correlation test gap, blocking | **Implementation yes; proof incomplete.** Starts are stored by `toolCallId` and completions pop that same id (`src/harness_bench/telemetry/copilot.py:81-92`), as section 4.4 requires. The committed fixture test asserts outcome counts and classes (`tests/test_telemetry_copilot.py:124-130`), but M1 below changed the pop to first-in-first-out and **all 58 tests still passed**. A synthetic overlap with starts A, B and completions B, A showed the original pairing `A→end-A, B→end-B`; the mutant produced `A→end-B` and left B open. The contract needs a regression test for that event order. |
| F2 — successful outcome code, blocking | `ToolCall.outcome_code` is documented as null on success (`src/harness_bench/telemetry/__init__.py:46-53`; `docs/adr/0006-append-only-run-ledger-and-derived-results.md:89`). The reader copies `data.error.code` regardless of `data.success` (`src/harness_bench/telemetry/copilot.py:89-92`). An independent synthetic read with `success: true` and `error.code: "stale"` returned a successful `ToolCall` with `outcome_code="stale"`. The committed off fixture has no such error object, so `tests/test_telemetry_copilot.py:124-128` passes. |
| F3 — model grain and buckets | **Yes.** Each new `session.shutdown` replaces the saved one; only the last is read, sorted by model key, with its line number shared by all models (`src/harness_bench/telemetry/copilot.py:103,120-139`). `requests` comes from `requests.count`, uncached input from `tokenDetails.input.tokenCount`, and reasoning stays a separate component of output (`:124-138`). The arithmetic mismatch is flagged. Golden samples assert requests 5/6 and buckets, a two-model sample asserts two rows at one ordinal, and a two-shutdown sample asserts the last wins (`tests/test_telemetry_copilot.py:77-100,236-242,253-260`). The fixture's ACP totals are 59,501/528,166 (`tests/fixtures/native/copilot/provenance.json`, `facts.off.acp_prompt_usage` and `facts.on.acp_prompt_usage`); the golden cross-check excludes reasoning (`tests/test_telemetry_copilot.py:95-100`). |
| F4 — version gate | **Yes for model rows and hook counts.** Unsupported or absent `session.start.data.version` appends `HB-TEL-001 events.version` and returns before model rows and hook counts are set (`src/harness_bench/telemetry/copilot.py:70-74,109-114`; `tests/test_telemetry_copilot.py:194-206`). This is the design's specified NOT_RECORDED behavior for those measures (`docs/design/phase2-copilot-profile.md:199-202`). Tool rows and first-user text are parsed before the gate and can remain populated; the design does not explicitly gate those fields. Consumers must not treat an unsupported event version as proof of a valid Copilot cell. |
| F5 — prompt and US-14 | **Yes for this reader's contract.** The first `user.message` without a top-level `agentId` supplies `data.content`, never transformed content (`src/harness_bench/telemetry/copilot.py:75-80`; `tests/test_telemetry_copilot.py:135-164`). `us14_valid` accepts ledger-row dictionaries and requires both zero `outcome_code=="denied"` rows and at least one `ok==1` row (`src/harness_bench/telemetry/copilot.py:144-150`; `tests/test_telemetry_copilot.py:265-276`). `normalize.tool_call_rows` emits those columns (`src/harness_bench/telemetry/normalize.py:92-95`). ACP permission-request count is a separate part of US-14's eventual exit assertion (`docs/design/phase2-copilot-profile.md:390`); this helper does not take that count. |
| F6 — Claude Code and Codex compatibility | **Yes at the changed surfaces.** Neither reader file changed in `2e9cc3b..f266f09`. Their model rows inherit `requests=1`, their tool rows `outcome_code=None`, and their hook fields `None` from the new defaults (`src/harness_bench/telemetry/__init__.py:42,53,86-87`). The normaliser adds the two columns without changing existing bucket expressions (`src/harness_bench/telemetry/normalize.py:85-95`). Focused tests assert their `requests` defaults and Claude's hook defaults (`tests/test_telemetry_copilot.py:103-121`). This is source-diff and focused-test evidence; I did not perform a byte-for-byte comparison of all prior ledger rows. |

## Independent mutation probes

I created a detached throwaway worktree at `f266f09`, edited only `src/harness_bench/telemetry/copilot.py` there, and restored that file to `HEAD` between mutants. The unmodified baseline and **each** mutant ran `uv run pytest -q -p no:cacheprovider tests/test_telemetry_copilot.py tests/test_telemetry.py`. These three mutations are my own and are separate from `tests/mutations/copilot_reader.json`.

| Mutant, applied alone | Result | Named killing test |
| --- | --- | --- |
| M1, line 88: `open_tools.pop(tool_call_id)` → `open_tools.pop(next(iter(open_tools)))` | **Survived:** 58 passed. The out-of-order synthetic probe showed wrong pairing and an unmatched B. | **Survived**; no named test killed it. |
| M2, line 92: replace `as_str(error.get("code"))` with `None` | **Killed:** 1 failed, 57 passed. | `tests/test_telemetry_copilot.py::test_off_tool_calls_succeed_and_on_rev92_are_all_denied` (line 128). |
| M3, line 150: change US-14's `and` to `or` | **Killed:** 1 failed, 57 passed. | `tests/test_telemetry_copilot.py::test_us14_no_tool_calls_at_all_is_not_valid_by_default` (line 276). |

Only the focused telemetry tests ran. No full suite, E2E test, live vendor capture, push, or edit to the reader branch was part of this review.
