---
id: brief-eval-hyg-verify
title: "Brief HYG-VERIFY: the four run-verify-gates failures on main (machine paths, portable text I/O, skill contracts, subprocess UTF-8)"
type: plan
status: proposed
owner: "@timianmalloo"
links:
  - { to: coordination-eval-wave2-e1-briefs, rel: implements }
  - { to: defect-classes, rel: relates-to }
review-by: "2026-10-17"
summary: "Four of the nine pack verify gates fail on main before and after the E1 joins (measured at fec54563: 24 machine paths, 25 text-I/O findings, 1 skill-contract refusal, 5 subprocess calls). Every finding is in a repo-owned file. HYG-VERIFY fixes each red-first against the gate's own output, opts out true fixtures with the gate's own marker, and records the gate defects it finds as findings for the pack. Claude Sonnet, one session, 90 min."
---

# HYG-VERIFY: the four failing verify gates

**Session** `hyg-verify-e1e4` · **branch** `build/eval-hyg-verify` · **harness** Claude Code Agent tool, `model: sonnet` (served `claude-sonnet-5-5`, R-91) · **budget** 70 calls · 120k tokens · 1 session · 90 min · **fallback** a fresh Sonnet session from this brief.

**Why.** `python docs/ai-forward-pack/scripts/run-verify-gates.py` exits 1 on `main`: 4 of 9 gates fail, so the line stops there and nobody reads the other gates' results. The failures were present before the E1 joins and are still present after them.

## Depends on
Nothing. Base on `main` at `fec54563` or later. No track waits on HYG-VERIFY.

## Measured on `main` (Coordinator #14b, tree at `fec54563`, 2026-10-04; each gate run alone, `python docs/ai-forward-pack/scripts/<gate>.py`, exit 1 each)

| gate | findings | the first few (file:line, the gate's words) |
| --- | --- | --- |
| `verify-no-machine-paths` | **24** | `tests/fixtures/ledger/c44dd2b-no-heads/run/archive/a/attempt-1/home/sessions/2026/09/rollout-2026-09-23-sess-a.jsonl:3` (a captured Codex rollout naming `C:/Users/operator/.agents/skills`); `tests/fixtures/native/codex/ok.jsonl:3`; `tests/test_acp_record.py:161` `home = r"C:\Users\someone\cells\home"`; `tests/test_mutate_check.py:195` (a comment citing a real `C:\Users\<user>\AppData\Local\uv\cache\...` path); `tests/fixtures/native/copilot/scrub_sample.py:166` (`"cells/*/home/config.json"`, a relative glob) |
| `verify-portable-text-io` | **25** | `tools/acp_record.py:363` `write_text(...)` without `newline="\n"`; `tools/acp_record.py:1` prints from a `__main__` entry with no stdio reconfigure guard; `tools/check_models.py:108`; `tools/freeze_catalog.py:45`; `tools/mutate_check.py:289` |
| `verify-skill-contracts` | **1** | `compile missing: new-bench-task — fix: cite CO-S0 in SKILL.md` |
| `verify-subprocess-utf8` | **5** | `tools/check_models.py:110` `run(... text=True)` without `encoding=`; `tools/gate_stamp.py:133`; `tools/spikes/s_lb_loopback.py:43`, `:102` (`Popen`), `:106` |

Re-run all four at your base before your first commit and put your counts beside these in the report (FIXT-A: a count you did not measure is Inferred).

## Ownership, per finding

**Every finding above is in a repo-owned file.** None is in `docs/ai-forward-pack/**`, and none is in a pack-managed copy under `.claude/**`:
- `tools/**` and `tests/**` are this repo's code. The two gates that scan code read `pack/scripts`, `pack/adapters/hooks` and `tools`; this repo has no `pack/` folder, so only `tools/` is read.
- `new-bench-task` is a repo skill, not a pack skill: its source is `skills/new-bench-task/SKILL.md`, and `.claude/skills/new-bench-task/` and `.agents/skills/new-bench-task/` are copies that `python tools/sync-skills.py` writes (its docstring: "The pack's own skills in those folders are owned by pack-apply.py and are never touched here"). Edit the source, run the sync, commit all three. `tests/test_skills_in_sync.py` fails if they drift.

**Rule for anything pack-owned that you find on the way:** never edit a file under `docs/ai-forward-pack/**`, or a pack skill or knowledge copy under `.claude/**`, unless the repo already records a repo-local deviation for that file (the only one today is `docs/notes/deviation-coord-transport-grok-session-new.md`, for `coord_transport.py`). Record it in your report as a **finding for the pack** (file, line, the gate's words, the proposed fix). The Coordinator forwards it. The same applies to a defect in a gate itself.

**Files another track owns.** Before you edit a file, check that no open track's brief lists it as an owned path (E1 README §5 table; E2-E4 README §2 table). Two hold today:
- `tools/spikes/s2_apps.py` and `tools/spikes/s2_probes.py` (3 portable-text-io findings) belong to **X-I-S2** (`docs/coordination/eval-wave2-e234/x-i-s2.md`), which rewrites those probes. Do not edit them. Your exit for that gate allows exactly those 3 findings, and your report names them as X-I-S2's.
- For any other file, a line in another owner's file is a seam request with a fallback (E1 README §2, rev 6.4): build the fix in its own commit that names the request id, and finish green.

## Work (red first: the gate's own output is the red)

Each fix is red-first against the gate itself. Before you edit, record the gate's line for that finding (exit 1 and the `file:line` text). After the fix, record that the line is gone and the count fell by exactly the number you fixed. One commit per gate, in this order. Each message names the gate and the before and after counts.

1. **`verify-skill-contracts` (1).** Cite CO-S0 in `skills/new-bench-task/SKILL.md` in the form the gate accepts: inline in the Grounding stage, or the one-line pointer to `reference/co-s0.md` ("CO-S0, knowledge/agent-coordination.md"). Read how a passing repo skill does it, for example `skills/start-benchmark/SKILL.md`. Then run `python tools/sync-skills.py`. Proof: the gate exits 0, and `uv run pytest -q tests/test_skills_in_sync.py` passes.
2. **`verify-subprocess-utf8` (5).** Add `encoding="utf-8", errors="replace"` to each call. If a call compares or parses the output, keep that behaviour (read the call site first). `tools/spikes/s_lb_loopback.py` is the operator's SP-LB script, which has not run yet. Your change must not alter what it measures. Say so in the commit message.
3. **`verify-portable-text-io` (25; 22 are yours).** Add `newline="\n"` to every text write the gate names. Add the stdio guard from `docs/ai-forward-pack/scripts/pack-doctor.py` (reconfigure stdout and stderr to UTF-8 with `errors="replace"`) at the `__main__` entry of each printing script it names. Copy the guard's exact form; do not invent a new helper. If a script's tests read its output, run them.
4. **`verify-no-machine-paths` (24).** Sort each hit into one of three kinds and handle it as that kind says:
   - **A real machine path:** for example the comment at `tests/test_mutate_check.py:195`. Replace it with the portable token (`%LOCALAPPDATA%`, `~`, or a repo-relative path).
   - **A test input that has to be a machine-shaped path:** the scrubber, redaction and detector tests in `tests/test_acp_record.py`, `tests/test_config.py`, `tests/test_profiles.py`, `tests/test_gateway_headless.py`, `tests/test_pack_improvement.py`, `tests/test_report_summaries.py` and `tests/test_telemetry.py`. Add the gate's opt-out marker `machine-path-ok` on that line, with the reason beside it. The gate's docstring says: "a fixture and the test says why".
   - **A false positive or a line that cannot carry the marker:** `tests/fixtures/native/copilot/scrub_sample.py:166` is a relative glob (`cells/*/home/...`); mark it, and record the pattern's false positive as a finding for the pack. The 8 hits in captured `.jsonl` records (`tests/fixtures/ledger/**`, `tests/fixtures/native/codex/**`) are recorded native sessions. Before you touch one, measure whether any test pins its bytes: grep for its path and for a hash beside it, then run the tests that read it. If adding the marker inside a string value leaves every reader green, do that. Otherwise leave the file unchanged and record a finding for the pack: the gate has no file-level exemption for captured-record fixtures. Do not widen or edit the gate.

## Acceptance items
1. Each of the four gates was run before and after its commit, and the report gives the measured counts (before → after).
2. `verify-skill-contracts`, `verify-subprocess-utf8` and `verify-no-machine-paths` exit 0. The exception is a `.jsonl` hit that is recorded as a finding for the pack, with its reason. `verify-portable-text-io` reports only the 3 `tools/spikes/s2_*` findings that belong to X-I-S2.
3. No behaviour change. The full non-credential suite passes. Every script you guarded or re-encoded keeps its tests green.
4. Nothing under `docs/ai-forward-pack/**` is edited. Every pack-side defect is in the report as a finding for the pack.
5. `python docs/ai-forward-pack/scripts/run-verify-gates.py` is run at the end, and its summary line is in the report. It exits 0 once X-I-S2's 3 findings are gone, and not before.

## Exit
E1 README §3 join gate (`uv run ruff check src tests tools`; the full non-credential suite; `uv run python tools/mutate_check.py --touched main`; `python docs/ai-forward-pack/scripts/docs-graph.py validate`; each on its own line, exit status read). Report per E1 README §4, plus the four before → after counts and the findings for the pack.
