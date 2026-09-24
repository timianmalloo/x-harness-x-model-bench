---
id: review-w1-acp-codex
title: "W1-ACP cross-vendor join review"
type: decision-note
status: proposed
owner: "@timianmalloo"
tags: [coordination, review, acp]
links:
  - { to: coordination-finish-harness-bench, rel: relates-to }
review-by: "2026-10-24"
summary: >-
  Codex review of W1-ACP at 48e4150: the recorded replay, model setter, nullable last update,
  and ruled engine scope pass focused checks; a 400 plus api_error classification conflicts with R-23.
---

# W1-ACP join review — Codex

**Verdict: CONDITION.** The requested replay, setter, nullable timing, and engine-scope behavior is present and the focused baseline is green. Before clearing R-23, resolve F2: an ordinary HTTP 400 with `errorKind: api_error` is classified as provider failure (HB-CELL-108), though R-23 says an ordinary 4xx is model unavailable (HB-CELL-116). The shared classifier needs a ruling-consistent precedence and a regression test, or an Owner ruling narrowing R-23. This note reviews `git diff 62d8b0c..48e4150` on `phase2-acp-transcript` at `48e4150`; the branch checkout was read only.

## Findings

| ID | Evidence and judgment |
| --- | --- |
| F1 — recorded replay | **Yes, for the committed recordings.** `tests/fixtures/acp/replay_agent.py:21-34` reconstructs each recorded `to_client` line from its text or base64 bytes and newline bit; `:43-49` sends the initial segment and releases later segments when client lines arrive. It does not construct an `initialize` or `session/new` reply. `tests/test_driver.py:218-232` compares all received agent bytes with the recording and all sent client bytes with the recorded client stream (substituting only live `<CWD>`); `:285-288` runs this on each recording. The one-byte `session/new` mutation is detected at `tests/test_driver.py:317-334`, closing the D5 negative control from `docs/proof/phase1.md:195`. This proves fidelity to the committed, scrubbed transcript, not to an independently recaptured vendor stream. |
| F2 — shared error classifier | **Conditional.** The driver preserves the JSON-RPC error object (`src/harness_bench/driver.py:109-112,182-185`), gives authentication text precedence, extracts the measured `API Error: NNN` form and `data.errorKind`, and calls `normalize.classify` (`:188-213`). The engine's native-record path calls that same function (`src/harness_bench/engine.py:456-463`), meeting R-23's one-classifier rule (`docs/notes/rulings.md:321-327`). The recorded 400/`invalid_request` becomes HB-CELL-116, while 429 and 529 become HB-CELL-108 and auth text becomes blocked auth (`tests/test_driver.py:239-274`). **Discrepancy:** `normalize.classify` tests the broad `api_error` provider type before returning model unavailable (`src/harness_bench/telemetry/normalize.py:23-24,75-82`). A direct call on the unmodified target with `{"code":-32603,"message":"Internal error: API Error: 400 bad model","data":{"errorKind":"api_error"}}` returned `HB-CELL-108`; changing only `errorKind` to `invalid_request` returned `HB-CELL-116`. R-23 says 408, 429, 5xx or overload type is provider, and any other 4xx is HB-CELL-116 (`docs/notes/rulings.md:323`). The checked adapter-status form is explicitly bounded in `src/harness_bench/driver.py:193-196`; other status encodings were not established by the recording. |
| F3 — model pin and refusal | **Yes.** `src/harness_bench/driver.py:229-241` performs `initialize`, `session/new`, optional `session/set_model`, then optional `session/set_mode`; the setter uses the created session id and requested model id. A setter error returns `Cause.model_unavailable` before the barrier and prompt (`:237-239,254-258`). The ordered methods and parameters are asserted at `tests/test_driver.py:580-586`; refusal, including auth-like wording, is asserted to be HB-CELL-116 with no `session/prompt` at `:589-597`. The engine passes the plan model only when the typed launcher flag is true (`src/harness_bench/engine.py:61-67,414-416`; `tests/test_driver.py:499-513`), as amended by R-30 (`docs/notes/rulings.md:398-406`). |
| F4 — last update | **Yes.** The default is `None` (`src/harness_bench/driver.py:97-102`), and only a consumed `session/update` after `turn_start` sets elapsed time (`:177-181,254-255`). The recorded update and derived no-update cases assert a bounded value and `None`, respectively (`tests/test_driver.py:337-352`). The engine already reads this field with a null fallback (`src/harness_bench/engine.py:369-374`). No zero is synthesized when there is no update. |
| F5 — engine scope | **Yes.** The entire `engine.py` diff adds typed `Launcher` fields `set_model` and `credential_kind` (`src/harness_bench/engine.py:61-67`), a shared `TurnResult` so `attempt.session_opened` records `agent_version` (`:399-416`), launcher-reported `credential_kind` and conditional `model=` at the call site (`:409-416`), and nullable verbatim `acp_usage` on `attempt.process_ended` (`:423-426`). These are the four ruled concerns in R-13, R-24, R-28 and R-30 (`docs/notes/rulings.md:224-231,329-336,374-382,398-406`). The event values are checked at `tests/test_driver.py:516-538`. No unrelated engine hunk appears in `git diff 62d8b0c..48e4150 -- src/harness_bench/engine.py`. |

## Independent mutation probes

I created a detached throwaway worktree at `48e4150`, edited only `src/harness_bench/driver.py`, restored it to `HEAD` between mutants, and removed the worktree after the probes. The unmodified baseline for `uv run pytest -q -p no:cacheprovider tests/test_driver.py tests/test_acp_record.py` was **58 passed**. I ran that same command for each mutant. These are review mutations, separate from the branch's own tests.

| Mutant, one at a time | Focused result | Named killing test |
| --- | --- | --- |
| M1, `src/harness_bench/driver.py:239`: setter refusal `Cause.model_unavailable` → `Cause.adapter_crash` | **Killed:** 2 failed, 56 passed | `tests/test_driver.py::test_a_refused_model_setter_is_model_unavailable_and_the_prompt_is_never_sent[copilot-32602]` (also `[auth-words]`; assertion at `tests/test_driver.py:596-597`). |
| M2, `src/harness_bench/driver.py:213`: replace shared `normalize.classify(...)` call with unconditional `Cause.model_unavailable` | **Killed:** 3 failed, 55 passed | `tests/test_driver.py::test_a_prompt_error_is_classified_by_its_status_and_type[rate-limit]` (also `[overloaded]` and `test_the_prompt_error_path_calls_the_native_record_classifier`; assertions at `tests/test_driver.py:247-274`). |
| M3, `src/harness_bench/driver.py:101`: default `last_update_seconds` to `0.0` | **Killed:** 1 failed, 57 passed | `tests/test_driver.py::test_last_update_is_null_never_zero_with_no_session_update` (`tests/test_driver.py:345-352`). |

The focused command excludes the full suite and `tests/e2e`. No live vendor capture was made in this review. The remaining join decision is F2; the three probes show that existing tests detect these particular regressions, not every classifier input shape.
