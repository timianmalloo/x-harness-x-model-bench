---
id: "adr-0024-combo-settings-and-served-read-back"
title: "ADR-0024: Combo settings (effort, context) are frozen plan facts, applied by the profile and read back from the harness's own record as a validity gate"
type: adr
status: draft
owner: "@timianmalloo"
phase: "Lean re-run at equal reasoning (operator 2026-10-11)"
tags: [benchmark, settings, reasoning-effort, context-window, validity, serve-a, readiness]
links:
  - { to: arch-lean-rerun, rel: refines }
  - { to: adr-0006-results-data-model, rel: depends-on }
  - { to: adr-0017-engine-identity-and-freeze, rel: depends-on }
  - { to: adr-0022-lean-benchmark-two-batch-runs, rel: depends-on }
review-by: "2027-04-11"
summary: >-
  bench-matrix/3 combos carry effort and context. Both are frozen on every cell, applied only through the
  profile's declared settings, and refused at plan time when the profile does not support the value. A profile
  also declares what its "default" serves. Each reader returns the settings the harness actually served, from its
  own record, and every pinned or declared value is judged: a mismatch invalidates the cell (HB-VAL-010), and a
  value no record carries is a warning (HB-VAL-011). A twelve-plus-cell readiness probe on a real property task runs
  the same check after the last code join and before batch 1. bench-matrix/2 files still load, as "default".
review-suggested:
  - { by: arch-lean-rerun, on: 2026-10-11, reason: "lean re-run amendment: bench-matrix/3 settings, served read-back (HB-VAL-010/011), Grok and agy cells, catalog 0.8 drift split, cost-compare report (ADR-0024..0027)" }
---

# ADR-0024: Combo settings are frozen plan facts, applied by the profile, and read back as a validity gate

- **Status:** Proposed (revised at the gate, 2026-10-11: council findings 1, 8, 9, 10, 18, 20, 24)
- **Date:** 2026-10-11
- **Deciders:** @timianmalloo (Rulings 117, 118); authored by the Leader seat (Claude Code, Opus).
- **Context:** `docs/architecture-lean-rerun.md`; the prompt's R-SETTINGS, R-SERVED, R-PROBE; SERVE-A
  (`docs/lessons/defect-classes.md:852`).

## Context

- The 2026-10-10 lean run compared Codex at effort low with Copilot at medium on the same model, because no profile
  set effort (Verified: `bench/profiles/*.yaml` has no effort key; `harness-cost-comparison.html` §2).
- Combo keys other than `id`, `harness` and `model` pass validation silently (`config.py:129-136`, Verified). An
  `effort:` line added to today's matrix would do nothing and say nothing.
- A setting is honoured, or not, inside the harness. The 2026-10-11 spikes found flags accepted and ignored:
  Copilot's `--context long_context` under ACP (served 272,000 on 1.0.89-1 and 1.0.92-4; Ruling 118); codex-acp's
  override of `model_reasoning_summary`; Grok's argv `-m` (SERVE-A, R-103). Checking argv proves nothing, and
  neither does trusting what "default" serves.

## Decision

1. **`bench-matrix/3`.** A combo is `{id, harness, model, effort, context}`; both new keys are required, and an
   unknown combo key is refused (in /3 only, so /2 files are unaffected). `effort` is a string on the vendor's
   scale. `context` is an integer token count or `"default"`. A `/2` file loads with both `"default"`.
2. **Frozen on every cell.** `plan.Cell` gains `effort` and `context`. `cell_id` includes them only when either is
   not `"default"`, so every existing plan's cell ids are unchanged (RECID-A). Two batches with different settings
   cannot be pooled: the ring hash of the matrix file already fails fast (`plan.py:580`, HB-PLN-003), and
   `board.pool_check`'s cell tuple (`board.py:824`, today `(task, combo, arm, model)`) gains effort and context,
   with a test.
3. **Applied only by the profile.** A profile gains a `settings:` block. For each setting it names:
   - the supported values (effort levels; context values);
   - how the value is applied: a placeholder (`{effort}`, `{context_tokens}`) in `command`, `files` or `env`;
     `model_id` (the value is part of the model id); or `none` (no knob);
   - **`default_serves`:** the value the harness serves when the combo asks for `"default"`, or `null` when no
     record shows it.

   A plan asking for an unsupported value is refused at plan time with a new HB-PRE code naming the combo, the
   setting and the supported values. For `model_id` settings the plan checks consistency (`[1m]` ⇔ 1,000,000;
   agy `-high` ⇔ effort `high`). Per-harness application (Verified in the spikes):

   | harness | effort | context | `default_serves` (context) |
   | --- | --- | --- | --- |
   | claude-code | env `CLAUDE_CODE_EFFORT_LEVEL={effort}` | `model_id` (`[1m]` = 1,000,000) | 200,000 (Inferred; probe confirms) |
   | codex | `config.toml` `model_reasoning_effort = "{effort}"` | `config.toml` `model_context_window = {context_tokens}` | 272,000 |
   | copilot | argv `--reasoning-effort {effort}` | argv `--context long_context` for `922000`, in `-p` mode (ADR-0028, Ruling 120; under ACP it is ignored) | 272,000 |
   | grok | argv `--reasoning-effort {effort}` on `grok agent`, before `stdio` | `none` | 256,000 |
   | agy | `model_id` (`-high`) | `none` | `null` (not recorded) |

   The profile file is in the engine identity (`identity.py:219`); the values are in the plan.
4. **Read back, per cell, and judged.** Each reader returns `ServedSettings` (architecture, *Contracts*) from the
   harness's own record. The grading pass writes `served` rows (ADR-0026). The *expected* value is the pin, or
   `default_serves` for `"default"`. `views._validity` then decides:
   - **model:** HB-VAL-002 keeps its input, every `model_calls` model (`views.py:542`), and gains `model_served`
     as a second input. Old runs, which have no `served` rows, judge exactly as before. A served alias is equal
     only by an exact-match table inside `profiles.model_allowed` (§5);
   - **effort or context recorded and different from the expected value:** **HB-VAL-010** (invalidating);
   - **expected value pinned or declared, and no source records it:** **HB-VAL-011** (warning; the report shows
     `not recorded`); with `default_serves: null`, the row is recorded as `not recorded` and nothing is judged;
   - **two sources disagree:** both rows are kept, and any recorded value that differs from the expected one is
     HB-VAL-010.

   Sources (Verified 2026-10-11): Claude Code assistant `.effort`, `attachment.identity.modelId`, ACP
   `usage_update.size`; Codex `turn_context.effort`, `turn_context.model`, `task_started.model_context_window`,
   judged against the pin × the cell's own catalog effective percent (`models_cache.json`, the field that gives 95%),
   with the percent's source recorded; Copilot `session.start.{selectedModel, reasoningEffort, contextTier}`, ACP
   `usage_update.size`, the debug log's response `model` as `model_api`; Grok `chat_history.jsonl` `model_id`,
   `reasoning_effort`, `signals.json` `contextWindowTokens`; agy `init.model`.
5. **Model aliases, exact only.** `profiles.model_allowed` gains a per-profile table: Grok `grok-4.7` ↔
   `grok-4.7-build` (R-103's accepted form; a prefix rule would admit `grok-4.7-build-fast`); Copilot
   `gpt-5.6-sol-fast` ↔ API `gpt-5.6-sol` (the debug log's response model, Verified). One definition, used by
   HB-VAL-002 and the probe.
6. **The readiness probe (R-PROBE).** Run only after the last `src/` and profile join, so its evidence belongs to
   the batch's engine identity (RECID-A); earlier probes are development evidence. A `/3` matrix with the six combos
   × both arms on one real property task, plus the two-turn RW1 for agy, one repetition, through the ordinary
   `bench run` and grading. `tools/served_check.py <run>` is a thin wrapper over the views. It exits 1 when any
   cell has HB-VAL-002/010, or HB-VAL-011 on a pinned value, or no `reasoning` row other than `omitted` where the
   harness can show text, or a pack-on cell with 0 instruction-file `prompt_parts`, or a pack-off cell with any.
   For a harness whose instruction-file source turns out absent (Claude Code's is Flagged, ADR-0026 §1), the
   instruction-file clauses report `not recorded` for that harness instead of failing; the pack-off guarantee then
   rests on HB-PRE-009 (no instruction file in the base tree), HB-PRE-002 (none above the cells root) and the fresh
   cell home, and the run report names the residual. It also runs the credential and real-store checks (ADR-0025
   §7, §8). It runs before the token approval.
   **Profile decisions come before the last join**, so the formal probe never changes a profile hash (RECID-A). A
   development probe decides them: whether Codex `show_raw_agent_reasoning` adds text (kept only if it does), and
   whether Copilot's debug log carries an `Authorization` or bearer-token shape (if it does, the profile drops
   `--log-level debug` and Copilot's per-request rows are `not recorded: per-session totals only`, as in the last
   run, unless the operator rules otherwise).
7. **Requested-only settings.** Settings the bench asks for to make reasoning visible (Codex
   `model_reasoning_summary = "detailed"`, Claude's thinking display, Codex `show_raw_agent_reasoning`) are
   recorded as requested and served, never judged. codex-acp 1.12.0 serves `auto` whatever the config says
   (Verified). `show_raw_agent_reasoning` is decided by the development probe (§6).

## Consequences

- Every cell states the settings it ran on, with the record field that showed it.
- A harness that ignores a setting, including what its default serves, is found by the probe before any batch, and
  by every cell after it.
- Copilot and Grok run at smaller windows than Claude Code and Codex. The report states each served window beside
  that combo's numbers.
- Old runs keep their cell ids, their validity and their renders.

## Alternatives considered

- **One profile file per combo.** Rejected: six near-identical profiles, and nothing ties the constant to the plan.
- **Free-form per-combo `argv`/`env` overrides.** Rejected: the profile could not refuse an unsupported value.
- **Judge only at the probe.** Rejected: SERVE-A drifts between sessions on one argv (R-103).
- **Leave "default" unjudged.** Rejected at the gate (finding 1): it is SERVE-A's root, the setting checked where
  it is written.
- **HB-VAL-002 reads only `model_served`.** Rejected at the gate (finding 9): old runs would change validity on
  re-render.

## Amendment 1 (accepted 2026-10-14): an optional `transport` combo key

Owner decision, plan row A3 of `docs/plans/benchmark-instrumentation-2026-10-14.md`: the Copilot transport control
(ACP against `copilot -p`, ADR-0028) is a combo option, not a hand-swapped profile.

- A `/3` combo is `{id, harness, model, effort, context}` plus an optional `transport`, a non-empty string. Every
  other unknown key is still refused.
- The value must name a launch the profile declares under `transports:` (today only Copilot's `acp`); any other
  value is refused at plan time (HB-PRE-010). `transport: acp` is refused at any context but `default`, because ACP
  serves 272,000 whatever the flag says (measured 2026-10-14, as in this ADR's context).
- `plan.Cell` freezes `transport`. It joins the cell id only when set, so existing cell ids are unchanged (RECID-A).
- The judging follows the cell's combo, not the harness alone: `views._prompt_mode` is false for an ACP combo, so
  HB-VAL-005 cross-checks the ACP turn total; the report pages label the cell `acp`.
- Verified on a real 2-cell run (`w12-transport-a3`, task X1, gpt-6.1-sol, default context): both cells valid; the ACP
  turn total equals the reader's model-call sums.
