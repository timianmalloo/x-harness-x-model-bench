---
id: coordination-finish-harness-bench-run
title: "Run record - coordination-finish-harness-bench"
type: doc
status: draft
owner: "@timianmalloo"
phase: "Phase 2 · smoke on all harnesses"
tags: [coordination, run-record, planned-vs-actual]
links:
  - { to: coordination-finish-harness-bench, rel: relates-to }
review-by: "2026-10-08"
summary: >-
  What happened when the finish-harness-bench plan was executed: qualifications, gate rounds, dispatches, slice
  joins, capture windows and planned against actual per track.
---

# Run record: coordination-finish-harness-bench

## Setup (Leader `coord-opus-cq`, 2026-09-24)

| step | result (measured) |
| --- | --- |
| Codex qualification | `qualify-codex-1` (default mode; its escalations were approved by Codex's own model reviewer) and `qualify-codex-2` (`agent-full-access`, selected). See `coordination-phase1-finish-run.md` (commit `e22ca74`) |
| Owner rulings | R-7, R-8, R-9 by the Owner seat (Fable): 44 tool calls, 465 s, 137,703 subagent tokens (as reported). Commit `0a64b0c` |
| Compile | raw `al-01M3AKF5D9FSZ2BE0ARDZCXNKQ` → compiled `al-01M3AKF6FZSG1RCB5FB5MR3C76`, dispatchable. One refusal first: the raw prompt named a forbidden construct, so it was rephrased and recompiled |
| Layer | `req-01M38KX8…` expired with its recorded fallback; `coord doctor` requests ok |
| W0-QUAL (`qualify-6`) | **Grok 1.0.41, no model pin:** `ready_for_review` in 101 s, 1 turn, 0 permission requests, 5 compatibility responses; ACP `selected_model: grok-4.7`. **Agy 1.2.10, no model pin, `accept-edits`:** `ready_for_review` in 75 s, 1 turn, 0 native denials; the conversation store shows executor `gemini-3.8-flash-high` and 17 generations on `gemini-3.8-flash`. Both commits touched only `docs/notes/qualify-worker.md`. The branches were qualification-only and were deleted |
| Stage 8 gate | round 1: Test Architect BLOCK, Tech Lead PASS WITH CONDITIONS, Simplifier BLOCK. Version 2 applied every finding or recorded a rationale. Round 2: Test Architect and Simplifier cleared their vetoes. Spend as reported: Test Architect 14 + 4 calls; Tech Lead 15 calls; Simplifier 25 + 5 calls |

## Correction

The 31-row to-do list said row 11 (power request) was "not built". It was built and wired in phase 1 (`host.py:89`; `engine.py:216/258`). The Simplifier found this at the gate, and the Leader verified it. Row 11 is closed by citation.

## Tracks: planned against actual

Wave 1, 2026-09-24/25. The times are committer times of the joins on `main` (local clock). A session duration is the closing audit entry's measured `duration_seconds`, where one exists. "planned" is the plan's harness column.

| track | planned harness | actual harness · model | budget | actual | joined (`main`) | exit evidence verified by the Leader |
| --- | --- | --- | --- | --- | --- | --- |
| W1-COP-D | Claude Opus 5.5 | as planned | 150 calls · 2 h | 4 design rounds: 1495 + 458 + 795 + 178 s (≈ 49 min) | `2e9cc3b` 15:38 (squash; REG-A) | design rev 3.1; ADR-0006 Amendment 1; scrubbed fixtures |
| W1-ACP | Claude Opus 5.5 | as planned | 260 calls · 4 h | not recorded as one duration | `124af8e` 15:50 | 11 reds re-run; Codex review F2 fixed red-first; `driver.json` 5/5 killed |
| W1-PACK (-2) | Claude Opus 5.5 | as planned, upstream | 150 calls · 2 h | revisions 94 and 95 (`df3baf2`) | ai-forward `origin/main` | runner limits (R-11), `protocol_error` detail, the hooks under `pwsh`. Pulled in here by `/updatepack` 93 → 95 |
| W1-HOST | Grok (`grok-4.7`, default) | slices 1–3 Grok (unpinned); slice 4 Claude Sonnet 5 (R-29, after a Grok `protocol_error`) | ≤ 3 slices | 4 slices; slice 4 took 221 s | `2b5743b` 14:42 · `7d73ada` 15:05 · `c57cbcb` 15:18 · `6cf7755` 15:28 | reds re-run; Test Architect veto cleared (`2f8c645`) |
| W1-TOOLB | Agy (`gemini-3.8-flash`, default) | Claude Sonnet 5 (R-10, after Agy's `native_tool_error`); follow-up Claude | ≤ 2 slices | 1 + a follow-up | `f141610` 15:05 · `a9f8bbc` 16:07 | red re-run; Codex review CLEAR; no-summary → `error` (CLN-B tool side) |
| W1-COP-R | Grok (default) | Claude Sonnet 5 (R-29: Grok held for new runner tracks) | ≤ 2 slices | 1233 s + a join-fix round | `791dba2` 16:31 | Codex review BLOCK and Test Architect BLOCK fixed; `copilot_reader.json` 21/21 |
| W1-COP-I | Codex `gpt-6-sol` | Codex `gpt-6-sol` (slices 1–5, 6a, 6b), plus loop-backs: fix (Claude Sonnet), L2 (Claude Opus), R-32 (Claude Sonnet, 1605 s), R-34 (Claude Opus, 773 s) | ≤ 5 slices × 55 min | 7 Codex slices + 4 Claude loop-backs | `b7ce26e` 16:02 … `da14061` 19:34 | the claim table in `docs/proof/phase2.md` (Join: W1-COP-I); Test Architect 47/47 kills at `da14061` |
| W1-CAP2 | Leader seam | Claude subagent (2 phases: 679 + 1129 s) | — | 30 min | `dc15d99` 18:15 | Copilot recording in D5/D7; rev-95 pack-on fixture swap |
| Wave-1 exit | Leader | Leader | 6 cells | 147 s | `4724248` 19:41 | `e2e-wave1-1790303859`: 6/6 valid, all assertions (`docs/proof/wave1-e2e-last.json`) |

**Planned against actual.**
- **Two of three runner harnesses were replaced mid-wave.** Agy (W1-TOOLB) failed on a runner limit (R-10). Grok finished 3 of 4 slices, then hit a `protocol_error` with no detail recorded (R-29). Both limits were fixed upstream in revision 95, and the re-qualification is `qualify-7`. Codex ran every W1-COP-I slice to a commit, with no R-4 fallback.
- **Loop-backs: 4 unplanned, against a reserve of 2.** Two came from served-model and tool-id facts that only a live cell showed: the `[1m]` tag (R-32) and `PowerShell` (R-34). The other two came from review findings (6a, 6b).
- **Negative runs on the way to the exit:**
  - `e2e-wave1-1790299304`: model mismatch, fixed by R-32;
  - `e2e-wave1-1790302505`: US-14 failed on `PowerShell`, fixed by R-34.
- **Leader misses, now registered:** SUITE-A, REG-A, GATE-B, CLN-B, COORD-B (`docs/lessons/defect-classes.md`).
- **Wave-1 close, 2026-09-25:**
  - **`/updatepack` 93 → 95** (`65075f2`, joined at `51ffb68`). Source: the revision-95 checkout `df3baf2`. Result: 14 UPDATE, 2 MERGE, 0 CONFLICT; pack-doctor 0 FAIL; offline suite 817 passed.
  - **`qualify-codex-3`**, the R-33 pin (`CODEX_CONFIG` model `gpt-6-sol`, effort `high`): `ready_for_review` in 68.5 s. The rollout's `turn_context` shows `gpt-6-sol`, effort `high`, `approval_policy: never`, `danger-full-access`. The operator's `~/.codex/config.toml` sets the same model and effort, so the run confirms the served model but cannot tell the pin from the default.
  - **Codex ownership hook: not qualified.** `qualify-codex-4` forced `apply_patch` on a path leased to the Owner, and the patch was **applied**; no ledger decision carries `hook_host: codex`. `qualify-codex-5` placed three marker hooks (`UserPromptSubmit`, `PreToolUse` `apply_patch` and `exec`), and none fired. Two measured facts:
    - codex-cli 0.156 on `gpt-6-sol` runs in code mode: every action is one `exec` call, with `tools.apply_patch` and `tools.exec_command` nested inside it.
    - Hook trust is stored per source path and hash (`[hooks.state]` in `~/.codex/config.toml`).
    - The three runs put the hook only in the worker tree. The launch reference says discovery in a linked worktree comes from the primary checkout (RIG-D instance).
    - **Next, operator-gated:** add the emitter's entry to the primary's `.codex/hooks.json`, and the operator reviews it through native `/hooks`. Then one run measures whether `PreToolUse` `apply_patch` fires for a nested `tools.apply_patch`.
    - Until then ownership for Codex is enforced only at the git pre-commit floor: in `qualify-codex-4` the leased file was written but not committed. Capabilities stay `observed-only`.
  - **`qualify-7`, models stipulated:**
    - **Grok 1.0.41** (`-m grok-4.7 --reasoning-effort high`): `ready_for_review` in 79 s, 1 turn; ACP `selected_model: grok-4.7`; no `protocol_error`. `grok models` reports `XAI_API_KEY` authentication in the operator's environment (disclosed; unchanged).
    - **Agy 1.2.10** (`--model gemini-3.8-flash-high`, the id `agy models` lists; `gemini-3.8-flash` is not an accepted id): `ready_for_review` in 68 s, 0 denials. `executor_metadata` shows `gemini-3.8-flash-high`, and `gen_metadata` shows 18 generations on `gemini-3.8-flash`.
    - Both pins equal the operator default, so the same limit applies as for Codex. The R-11 Agy hold and the R-29 Grok hold lift for new runner tracks.
  - **R-35/R-36(a)** (Claude Sonnet 5, 69 tool calls, 647 s): joined at `6e7ae50`. The Leader tightened two tests at the join (TEST-A).
- **Also done:** the A9 host-sleep probe (`docs/notes/spike-a9-host-sleep.md`); A3 partial (host credentials unchanged across two runs); the R-36 connector comparison (the same 8 account tools pack-on and pack-off).

## Wave 2 (version 4, 2026-09-25): planned against actual so far

Times are Leader-measured: the runner's `duration_seconds` and the subagent's `duration_ms`. "Leader re-run" is the join rule: every red is re-run in a throwaway tree.

| track | harness · model (stipulated) | runs | joined | evidence verified by the Leader |
| --- | --- | --- | --- | --- |
| W2-TASKS-d (C1) | Grok `grok-4.7` | 1 slice, 562 s, 4.35 MB output | `3c9c906` | base exit 1 (10 tests: 2 failures, 8 errors), reference exit 0; `bench validate` ok. ProjDevBench `9af6f408` has no LICENSE file, only a README "MIT License" line (disclosed in `task.yaml`) |
| W2-TASKS-a (A1) | Claude Opus 5.5 | 69 calls, 1,107 s | `c9960ed` | base 43/43 fail, reference 43 OK; held-out matcher set of 38 (15 near-misses). The LiveCodeBench dataset card says only "cc" (disclosed in `NOTICE.md`) |
| W2-TASKS-b slice 1 (dotnet runner, R-41) | Codex `gpt-6-sol` | 1,505 s, 2.96 MB | `2f7726f` | reds: 3 and 11 failed; `correctness.json` 3/3. **Deviation:** no cross-vendor reviewer added its own 3 mutants at this join |
| W2-CANARY slices 1–2 (R-36/R-43 count) | Grok `grok-4.7` | 720 s (deadline hit, red committed), then 458 s | `da46176` | red: 3 failed. Leader join fix: a broad `OSError` catch removed (it returned partial rows unflagged); `canary.json` 3/3 |
| W2-STOP-D (row-10 design) | Claude Opus 5.5 | 110 calls, 2,720 s | `7c2be61` | Test Architect and Simplifier: BLOCK, then PASS WITH CONDITIONS; TLA refinement spiked (22/22 variants rejected). Decisions R-48..R-50 |
| W2-VIEWS | Claude Opus 5.5 | 211 + 105 calls, 2,373 + 1,195 s | pending join | 7 reds re-run (9/4/8/5/2/7/1). Data & Persistence Architect: CONDITIONS. Codex review: CONDITION F1 (its 3 mutants killed). Loop-back closed all 7 conditions. Decision R-47 |
| R-45/R-46 profile seam | Codex `gpt-6-sol` | 703 s, 6.26 MB | `1308e0f` | red: 7 failed; `profile_classes.json` 4/4; suite 846 passed, 1 skipped (awaiting the recut) |
| W2-TASKS-b slice 2 (D1) | Codex `gpt-6-sol` | 1,538 s, 2.83 MB | `6a45bf1` | through `correctness.grade`: base 0/5, reference 5/5, offline restore. **Defect found after the join:** `run.cmd` hard-codes the operator's profile path. TASKS-b slice 3 fixes it at the grader, and W2-VALIDATE adds a path scan. The username is in the pushed history, which is not rewritten |
| W2-USER-D (design + S-04/S-04b) | Claude Opus 5.5 + AI Systems Engineer | 3 phases, about 2,120 s | `55151ea` | 17 probe turns run by the Leader; the Copilot stdio rejection was read from Copilot's own log. Decisions R-51..R-53 |
| W2-TASKS-e (E6) | Agy `gemini-3.8-flash-high` | 1,194 s, 0.41 MB, 0 denials | joins through TASKS-b slice 3 | MultiPL-E `3025a53`: "BSD 3-Clause with Machine Learning Restriction" (no training use; evaluation allowed; notice copied) |

**Also measured in this wave:**
- **Copilot and Codex profiles vs ADR-0004 (R-45, R-46).** Copilot advertised `web_search`, `web_fetch` and GitHub-MCP tools as "safe", so they ran with no permission callback. Codex's promised `web_search = "disabled"` was never seeded. Whether wave-1 cells used these tools is **not recorded**. The profiles are fixed; the recut and the qualification cells are pending (run `qual-r45-1`).
- **Correction: the docs-index gap was the Leader's miss, not a pack defect.** An earlier line here said the `coord-regen` merge driver dropped two new docs. Having read the driver (`coord-core.py` `cmd_merge_derived`), it resolves a derived file to "ours" by design and records a regeneration as owed; the join must then run `coord regen`. The Leader never did, so both `docs/docs-index.js` (hand-fixed at `82dcfcc`) and `docs/audit/audit-data.js` (stale until 2026-09-24 23:35) drifted. Registered as REG-B.
- **B1 and F1 wait on the operator:** cfd-bench has no LICENSE at `496a0a8` (R-42 condition 1).
- **R-51 condition 2: measured, and it fails as the profile stands.** Probe `copilot-probe-copilot-config-profile-flags-20260925T050838Z`: Copilot 1.0.89-1 on `main`'s profile (R-45 flags) plus `--additional-mcp-config`. Copilot started the scripted-user server (`initialize`, `tools/list`), then told the model "Disabled tools: list_agents, read_agent, scripted_user-ask_user, sql, task, web_fetch, write_agent". 0 calls; the model reported the tool unavailable.
  - This confirms R-45's `assume:`: `--available-tools` filters MCP ids too.
  - It also shows the fixed profile disabling `web_fetch`.
  - **Consequence for W2-USER-W:** a `scripted_user: true` Copilot cell appends `scripted_user-ask_user` to `--available-tools`. That needs one confirming turn before the live A1 cell (R-51 condition 2 stays open until then).
- **R-57 gates for night 1, all met on 2026-09-24 (PDT):**
  1. Codex re-qualification `requal-codex-1`: valid, no MCP call, "no web tool available"; `apps = false` in the cell's `config.toml`; Higgsfield appears only in the pack's own skill text (23 mentions before, 2 after).
  2. Claude re-qualification `requal-claude-1`: `account_connector_tools` 0 (8 before). `WebFetch` was refused and shows as the HB-VAL-009 warning on a valid cell.
  3. The per-cell finding is in `bench report` (W2-VIEWS-FU, `7365b5f`).
  4. Copilot `skill` is class read (`6d145dc`).
  5. Every slice ran on a stipulated model.
- **Night 1 window (R-9 rule 7):**
  - Run `row15-d1-1` started 23:24 PDT: D1 × {copilot-sol, codex-sol, cc-opus} × pack {on, off} × 1 = 6 cells, parallelism 2, envelope 10,800 s, pack revision 95.
  - Workers active by vendor during the run: none (Anthropic, OpenAI, GitHub, xAI and Google all idle); the Leader session polls only.
  - Planned end: by 02:24 PDT. The actual end and the headroom result go in `docs/notes/row15-headroom.md`.
- **CANARY slice 3 (Grok) ended at its 720 s deadline with no commit.** Under R-4 and R-44 condition 2 the remainder moved to Claude Sonnet (W2-CLAUDE-PROFILE, joined `75c620e`).
- **W2-HARBOR (row 9, spike A6): stopped and parked, not re-dispatched.** The Claude Opus agent drafted an exfiltration-style probe for the US-48 canary step. A safety classifier then refused its tool calls for the rest of its session, and its hand-back arrived marked unreviewed. The one file it left, `bench/harbor/canary.py`, contained an HTTP listener on all interfaces, so nothing was kept: the tree was removed, with no commit and no container created.
  - Per the standing rule, the Leader does not re-dispatch work around a classifier refusal.
  - Row 9 stays **not passed**. E1 stays deferred and E6 keeps the smoke slot (R-40, already ruled).
  - The spike's canary design is a question for the operator: US-48 is withdrawn for authored tasks (ADR-0013) and applies only to Harbor containers.
  - The unreviewed report's other claims (Harbor 0.23.0 installs without a key; Harbor's own agents need provider keys, so Harbor would be a task format only) are recorded as **Inferred**, not Verified.
- **R-19 cosmic-ray window deferred.** It would hold the host for hours with no runner slice allowed, and STOP-I (Codex) is the smoke run's critical path. R-19 condition 1's "next night not used by a benchmark run" applies.
- **The OpenAI allowance ran out (2026-09-25, about 01:47 PDT).** Two Codex slices, W2-STOP-I slice 4 (568 s, which had committed a red and a green) and W3-GRADE-CORE slice 1 (42 s, 0 turns), ended `remote_error`. Codex's own rollout says: "You've hit your usage limit … try again at Sep 29th, 2026 1:03 PM."
  - This **measures R-9's `assume:`**: one rolling allowance per login is shared by workers and cells. The wave-2/3 Codex worker slices, 13 of them over about 12 h of this session, consumed it.
  - **Consequences until Sep 29 or new credits:** every `codex-sol` bench cell (a third of the smoke matrix), the `gpt-6-sol` judge (R-58) and every Codex worker track are blocked.
  - Under R-4 and R-44 condition 2, the two slices moved to Claude Opus: `w2-stopi-4c`, continuing from the recovered commits `b3baf80`/`0f24e77`, and `w3-core-1c`.
  - The Leader then force-removed the `w2-stopi-4` tree without reading its counts (CLN-C). The commits were recovered; the uncommitted tail was lost.
  - Cost is not recorded per slice (subscriptions; `cost: not recorded` in every runner row). That is the IO gap that let this arrive unforecast.
- **The Grok R-11 datum:** 3 slices measured 3.1–4.35 MB each over 7.6–12 min, far under 16 MiB.

## Wave 3 (version 5, 2026-09-25): planned against actual so far

Every Codex track ran on Claude under R-4: the OpenAI allowance is out until 2026-09-29. "Leader re-run" is the join rule: each red is re-run in a throwaway tree.

| track | harness · model (stipulated) | joined | evidence verified by the Leader, and the Leader's join fixes |
| --- | --- | --- | --- |
| GR-CLAR l1 | Agy `gemini-3.8-flash-high` | `38e0a11` | red re-run; the real A1 cells match the design. Join fixes, red first: no guessed annotated id when the set is missing; ratios are Decimals at scale 4 |
| GR-PROC p1–p3 | Grok `grok-4.7` | `7358c11`, then p2, then `f2ac1f3` | every slice hit the 720 s deadline after its red commit; the Leader verified and committed each green. Real gate runs match the design. Join fix: the three process ratios get scale 4 |
| GR-CODE c1 | Claude Opus 5.5 | `d7cbe11` | 4 reds re-run; correctness 25/25 and grade 34/34 killed; the TRX spike note. Decision R-71 (the broken-ProjectReference seed is retired) |
| GW-I s1 | Claude Opus 5.5 + Fable security review | `620f5fb` | 12 reds re-run. Review: PASS WITH CONDITIONS. Join fixes, red first: the pinned model must be served (F1); `.gitignore` gains `cache/` |
| GW-CP + the R-63 spike | Claude Sonnet 5; live turns by the Leader | `620f5fb`, `ac44295` | turn 1 in R-63's shape failed: 17 tools advertised, `powershell` ran unapproved, the ancestor canaries loaded. Turn 2 (`--no-custom-instructions --available-tools none`) met every criterion. Decision R-70. Join fix: the Copilot reader keeps a measured empty tools list as `[]` |
| COST phase 2 | Claude Sonnet 5 | `c57fd6d` | its red failed at collection, not on an assertion (disclosed). Join fix, red first: the cache percentages are Decimals at scale 4; a whole percent read 100 for every harness |
| GW-I s2 | Claude Opus 5.5 | `c57fd6d` | 11 reds re-run; gateway 67/67 killed; the Copilot builder carries turn 2's shape |
| STOP-I s5, s6 | Claude Opus 5.5, then Sonnet 5 | `7fb3b61`, `cff61d6` | 19 reds re-run; 165/165 mutants killed; check_models full. Test Architect (Fable): BLOCK, then PASS WITH CONDITIONS after the join fixes. R21-3 stays Flagged until a Copilot capture window |
| CORE s2 | Claude Opus 5.5 | `5289e91` | 7 reds re-run; grade 68/68 killed. The Leader measured the six cost counts for the gate by a scratch re-grade |
| GW-I s3 | Claude Opus 5.5 | `0d288c0` | 4 reds re-run; judge 28/28 killed; conflict in runner.py resolved as the union |

**Also in wave 3:**
- **A pack defect, fixed downstream and committed upstream.** Grok 1.0.41 sends a `workflows-reload` watcher frame inside `session/prompt`, which the transport refused (`protocol_error` 3.8 s in, 0 turns). The fix is local at `b68574b` and committed upstream at `3b7940d` on ai-forward branch `fix/grok-workflows-reload` (91 transport tests OK under WSL). The auto-mode classifier refused the upstream push twice, the second time after the operator's instruction; the push waits for the operator.
- **A tool defect.** `mutate_check`'s FAILED pattern stopped at the first space, so a parametrized case id with spaces could never count as a kill. Fixed red first.
- **Defect class SEED-A:** a tool's behaviour asserted from its documentation or a belief, not measured. Two instances: the dotnet seed and the Copilot empty allowlist.
- **About 16 mutants in other mutation files have stale find text** (reported by GW-I s3). A sweep slice is next.

**Operator decisions, 2026-09-25 (verbatim intent):**
1. cfd-bench: "I have not added a license file yet AND its just MY OWN repo so far, very nacent so proceed without blocking on a license". B1 and F1 are released: B1 is authored on Grok, F1 on Claude Opus. **Correction:** R-42's reasoning line "cfd-bench has an MIT LICENSE" was wrong. No licence file exists at any cfd-bench commit (checked: `git ls-files` and the working tree).
2. "commit and push": the upstream commit landed; the push was refused by the classifier (above).
3. "you close this out - you dont need me to address these". The Leader closes the carried operator items:
   - **Codex hook `/hooks` review:** closed as not blocking. 13 Codex worker slices ran with the hook in place, and Codex is unavailable until 2026-09-29. The Leader does not write the Codex hook trust store itself. If Codex refuses the hook at the reset, the refusal is recorded and the hook-less path is taken.
   - **The ChatGPT connector activity log (R-55):** closed by the measured control. `apps = false` is in every Codex cell's config, and `requal-codex-1` measured no MCP call. The account log itself is visible only to the account owner.
   - **The 30 calibration labels (R-58: HUMAN):** the operator will not label them, so R-58's labelling condition goes back to the Owner seat for a re-ruling before W3-CAL is dispatched.
   - **Informational, no action:** Grok authenticates with `XAI_API_KEY` (disclosed); row 9 (Harbor) stays parked; the Anthropic allowance remains a risk.

**R-74 qualification, run `qual-r74` (2026-09-25; Q6 × {cc-opus, copilot-sol}, pack on, revision 95):** both cells completed and are valid, and `pass_at_1` is 1 for both.
- **Claude Code 2.1.282:** one `Agent` call (class `delegate`, ok). The sub-agent served `claude-sonnet-5`, so routing is supported: `ANTHROPIC_MODEL` did not force the sub-agent onto the pin. Its record was at `home/projects/<cwd>/<session>/subagents/agent-<id>.jsonl`, which confirms S6's `subagent_glob` assume. There were 0 executed `other` rows.
- **Copilot 1.0.89-1:** one `task` call (class `delegate`, ok), and the sub-agent served `gpt-6-luna`, so routing is supported.
- **Codex:** not measured, because the operator reserves Codex for benchmark runs. No Codex allowance exists, so under R-74 a run that includes `codex-sol` banners F1 as `not run (delegation not qualified on codex)`.
- **Codex 0.156.0 (runs `qual-r74-codex-1`, then `qual-r74-codex-2`; one short cell each, the operator's go-ahead):** The first cell measured `spawn_agent` and `wait_agent`. The spawned agent wrote its own rollout and served `gpt-6-luna`; the cell was invalid, because both tools were out of profile. The allowance was built from that measurement (the Grok slice joined above). With it, the second cell is valid and passes: 2 `delegate` calls, and model calls on both `gpt-6-sol` and `gpt-6-luna`, so routing is supported. **All three harnesses are qualified, so F1 runs on every combo in the smoke run.**

## Backlog

| Id | Task | Asked | Status |
| --- | --- | --- | --- |
| CI-OPT | Analyze every test and CI suite and optimize for clock time and spend (operator, 2026-09-26: "clock-time and spend-time are both barriers to iterative execution and throughput"). **#1** a clear separation of one-time checks (a characterization graded twice, a seed that proves a tool's behaviour, a freeze's golden export) from continuous ones (every push, every join), so a one-time proof is recorded once and never re-paid per gate. **#2** bring down the slow ring's total time. **#3** find where we are excessive or can be more efficient: the join rule's re-runs, the batch gate, duplicated runs. **#4** consolidate and simplify (operator, 2026-09-26: "more tests does not mean better coverage"): find redundant coverage (several tests that fail for the same mutant and nothing else), and ceremony that adds a test without adding a failure it alone catches; merge or delete them. The evidence is the mutation kill matrix: a test that kills no mutant another test does not also kill is a consolidation candidate, and a behaviour no test kills is a gap. The mantra, for every slice from here: a test earns its place by a failure only it catches. Method: profile first (CE, IO): per-test durations from the rings, per-step times of a join, then cut by measurement; cheaper is never weaker (no muted step, the Test Architect's veto on coverage). | 2026-09-26 | open; baseline below |

**CI-OPT baseline (measured 2026-09-26 unless marked):**
- Default ring: 1766 passed, 31 deselected, 1036 s (17.3 min), on main before the R-75 push.
- Slow ring: 22 passed, 1775 deselected, 44,954 s wall (12.5 h). The System log shows Modern Standby from about 20:37 to 03:39 and 03:39 to 07:32 (Kernel-Power 506/507/566), about 10.9 h, so the active time is about 1.6 h (**Inferred** from the log arithmetic; CI-OPT measures it per test with `--durations=0`). Two findings: a long ring does not hold the machine awake (a gate that sleeps is not a measurement), and 22 tests take about 95 active minutes.
- c6b-3 slow tests alone: 2 passed in 1548 s (25.8 min); the D1 characterization grades 6 cells twice through Stryker.NET, and each Stryker run first executes the 2681 vendored `AiDe.Core.Tests` tests (about 2 min, from the Stryker log).
- A red re-run at a join re-runs the whole touched test file in a fresh tree: 93–107 s for `test_grade_mutation.py`.
- Inferred, to be measured: the twice-equal characterizations are a one-time determinism proof paid on every slow ring (#1); the join re-runs whole files where the red's own tests would do (#3).
