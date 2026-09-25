---
id: "design-phase3-cost"
title: "Design: the cell-grain cost and efficiency metrics (phase 3, row 16, W3-COST phase 2)"
type: design
status: draft
owner: "@timianmalloo"
phase: "Phase 3 · grading and judges (wave 3: row 16, W3-COST)"
tags: [benchmark, grading, metrics, cost, tokens, cache, determinism]
links:
  - { to: design-phase3-graders, rel: refines }
  - { to: spec-harness-bench, rel: implements }
  - { to: arch-harness-bench, rel: implements }
  - { to: adr-0006-results-data-model, rel: depends-on }
  - { to: adr-0008-telemetry, rel: depends-on }
review-by: "2027-03-25"
summary: >-
  Seam C-1: `grade/runner.py`'s inline `_cost` (cost_usd only) moves verbatim into `grade/cost.py`'s
  `grade_cell(inp)`, registered in `runner.GRADERS["cost"]`. Six cell-grain metrics are decided: cost_usd
  (unchanged) plus five new ones -- tokens_per_minute, output_tokens_per_turn, cache_hit_ratio,
  cache_write_amplification, context_growth (peak) and compactions -- each defined only from
  `normalize.totals` and the existing view measures `views.busy_ms`, `views.calls_per_cell` and
  `views.model_call` (DM7: one definition per quantity). `compactions` has no recorded signal on any
  harness today, so it is unconditionally NA, never 0 (US-27).
---

# Design: the cell-grain cost and efficiency metrics (W3-COST phase 2)

**Status:** draft. **Author:** W3-COST phase 2 (Claude Sonnet 5). **Grounded at:** the worktree HEAD when this slice
started (`w3-cost-2`, from `main` at `2b9dde6`).

Confidence labels: **Verified** (observed in this session: a file opened, a command run), **Inferred** (reasoned,
not observed), **Decision** (this design's own call, within the authority `docs/design/phase3-graders.md`'s Cost
section gives W3-COST: "COST's design decides the rest of the cell-grain metrics under DM7").

## Responsibility

One responsibility, delegated by `docs/design/phase3-graders.md`'s Cost section (seam C-1): turn one archived
cell's token usage into `cost_usd` and five efficiency scores. Kind (`score`) and class (additive /
non-additive) for all six are already fixed by that section; this design decides each metric's concrete
definition, its inputs, and its NA-reason vocabulary.

Not in scope (per the graders design and this slice's brief): `bench/metrics.yaml` catalog edits (the six ids,
their `source`/`better`/`grader`/`kind`/`weight` are already present at `0.4.dev`; only `scale` is left to the
Leader, since a `Decimal` value for a metric with no catalog `scale` is refused by the runner, HB-GRD-003 --
seam C-1's scope note above); `bench/prices.yaml`; the derived-only metrics (`cost_of_pass`, `tokens_per_solved`,
`tokens_by_type`, `wall_clock_split`, `turns_and_tool_calls`, `coordinator_overhead`), which stay view-only
(DM7); `views.py` itself (read and reused, never edited); the judge, correctness and process graders.

## Grounding

| # | Fact | Evidence | Label |
| --- | --- | --- | --- |
| G1 | `runner.py`'s `_cost` computed only `cost_usd`; the docstring already named this slice as its mover. | `grade/runner.py:56-57` (pre-edit) | Verified |
| G2 | The catalog (`0.4.dev`) already lists all six `cost` metrics as `kind: score`, `grader: cost`, with a `weight`, but **no `scale`** on the five new ones (only `cost_usd` has `scale: 6`). The runner refuses a `Decimal` score for a metric with no catalog scale (`HB-GRD-003`, `ValueError`). | `bench/metrics.yaml` (areas.cost.metrics); `grade/runner.py::_run_grader` | Verified |
| G3 | No event, tool-call or model-call field anywhere in the ledger schema names a context compaction. `grep -rn "compact" src/` outside `ledger.py`'s unrelated "compact separators" docstring returns nothing. | this session's search | Verified |
| G4 | `turn_usage` rows are written once per model per cell, already summed across every turn of that cell before the ledger sees them (`engine.py::_usage_per_model`, called once at cell end from the ACP result's final `_meta.quota`). No per-turn or per-request boundary survives for an `acp_turn` harness. | `engine.py:502-504`, `:684-691` | Verified |
| G5 | For an `acp_turn` harness (Claude Code), the native record "misses the final and auxiliary calls" -- its own `model_calls` extraction is a partial call list, not just a partial usage field. `views._model_time` therefore returns NA unconditionally for `acp_turn`, regardless of whether calls exist. `views._cell_view` does **not** apply the same source gate to `calls_per_cell`. | `telemetry/normalize.py:4-6` (docstring); `views.py:226-233` (`_model_time`); `views.py:451` (`calls_per_cell` called unconditionally) | Verified |
| G6 | `normalize.totals(source, ex, usage)` already switches its reader by `source`: `ex.model_calls` for `native_record`, the (already-summed) `turn_usage` list for `acp_turn`. So a **total** (a sum) is reliable for both sources; a **per-call** reading (a span, a peak, a request count) is reliable only where the native record is known complete. | `telemetry/normalize.py:79-86` | Verified |
| G7 | The runner's completeness check (`_check_complete`, HB-GRD-004) fails the whole pass if a grader returns a key outside its applicable set. A grader must return exactly `inp.metrics`' keys (or a subset; the runner backfills a missing one as `not built`) -- never an extra key the catalog does not currently ask for. | `grade/runner.py::_run_grader`, `::_check_complete` | Verified |

## The six metrics

Every metric NA's with a reason, never 0 (US-27). None reads or writes anything outside `CellInput` (the
per-cell parameter object; design: `phase3-graders.md`, "Exposed: the per-cell grader input").

### cost_usd (unchanged; seam C-1)

**Definition, kind, class, NA reasons:** unchanged from phase 1 (`docs/design/phase3-graders.md`, Cost section:
"today's NA reasons", `runner.py:161-173` pre-move). `grade/cost.py::_cost_usd(inp, source)` is that function,
moved verbatim: same four early-NA branches in the same order (price list changed; native-record read failure;
`HB-TEL-001` missing fields; native-record unreadable), then `cost_usd(totals, prices, run_date)` (the existing
pure pricing function, also unchanged). Byte-equal on `tests/fixtures/ledger/**` and on the nine gate cells
(Done-when).

### tokens_per_minute (Decision; non-additive, a rate)

**Definition:** total tokens for the cell (every bucket, every model, via `normalize.totals`) divided by
model-busy-minutes. Busy time is `views.busy_ms(model_calls, positive=True)` on the extraction's model-call
spans -- the same reader `views.py` uses for `model_ms` (DM7: one definition of "model busy time from spans").
Rounded to the nearest integer (`ROUND_HALF_UP`); the catalog carries no `scale` for this metric (G2), so the
score is an `int`, never a `Decimal`.

**NA reasons, in order:**
1. the shared totals reason (below) when totals cannot be trusted;
2. `"the native record misses calls (token source acp_turn)"` when `source == "acp_turn"` -- mirroring
   `views._model_time`'s own unconditional gate (G5): the record that would carry the spans is known partial for
   this harness, so a busy-time denominator from it is never reported as measured, even when some calls are
   present;
3. `"no model call time recorded"` when `busy_ms` itself cannot establish a span (no calls, or a call missing a
   start/end).

### output_tokens_per_turn (Decision; non-additive, a rate)

**Definition:** output tokens (from `normalize.totals`) divided by turns, where a turn count is
`views.calls_per_cell` (Sigma of each model-call row's `requests` field) -- the one definition of a turn count this
catalog already has (G7's counterpart: `calls_per_cell`'s own docstring, "requests in a recorded extraction").
**Decision:** unlike `tokens_per_minute`, this is *not* additionally gated on `source == "acp_turn"`: `views.py`
itself calls `calls_per_cell` unconditionally on source (G5), so gating here would invent a stricter rule than
the measure it reuses already carries. Rounded to the nearest integer (no catalog `scale`, G2).

**NA reasons:** the shared totals reason; else `calls_per_cell`'s own reason (`"not recorded"`, when there are no
calls or any call's `requests` is 0), propagated verbatim.

### cache_hit_ratio (Decision; non-additive, a percentage)

**Definition:** `cache_read / (uncached_input + cache_read) * 100`, rounded to the nearest integer.
`cache_write` is excluded from the denominator: a write is neither a hit nor a miss, so it does not belong in a
hit-rate's population.

**NA reasons:** the shared totals reason; else `"no input tokens recorded"` when `uncached_input + cache_read ==
0` (e.g. a cell whose only usage was cache writes and output).

### cache_write_amplification (Decision; non-additive, a percentage)

**Definition:** `cache_write / cache_read * 100`, rounded to the nearest integer -- tokens (re)written to cache
per 100 tokens later read back from it. A value above 100 means the cell wrote more than it ever benefited from
reading; a value near 0 means writes were rare relative to reads.

**NA reasons:** the shared totals reason; else `"no cache activity recorded"` when both buckets are 0; else
`"no cache reads recorded"` when there were writes but no reads (amplification is undefined with nothing to
divide by).

### context_growth (peak) (Decision; non-additive, an integer token count)

**Scope, per this slice's brief:** only the "peak" sub-definition (the catalog's own note also lists "slope,
turns to 50% window"; those are not built here and are left to a future slice).

**Definition:** the largest single call's context size -- `max(uncached_input + cache_read + cache_write)` over
the cell's model-call rows -- the biggest prompt this cell ever sent in one call.

**NA reasons:** the shared totals reason; else `"the native record misses calls (token source acp_turn)"` when
`source == "acp_turn"`. **Decision, and why this is stricter than `output_tokens_per_turn`:** a peak is a `max`,
not a sum or a count. A sum or a count under-reports gracefully when an entry is missing (it is simply smaller
than the truth, and the existing `calls_per_cell` measure already accepts that risk, G5). A `max` computed over
an incomplete set can silently and arbitrarily understate the true peak whenever the single largest call happens
to be one of the calls the acp_turn record misses -- there is no way to tell, from the visible calls alone,
whether the true peak was captured. So this metric follows `tokens_per_minute`'s stricter, `_model_time`-style
gate rather than `calls_per_cell`'s looser one.

### compactions (checked, not assumed; additive, an integer count)

**Definition:** unconditionally NA. **Why, and how this was checked rather than assumed:** `grep -rn "compact"`
across `src/harness_bench/` (this session) returns exactly one hit, `ledger.py`'s docstring "compact separators"
(JSON formatting, unrelated). No event kind, tool-call field, model-call field or turn-usage field anywhere in
the ledger schema (ADR-0006, `telemetry/__init__.py`, `engine.py`'s `FACTS`) records a context-compaction
occurrence, on any harness. There is therefore no recorded data this grader could read to produce a non-zero
value, and per US-27 a metric that cannot be defined from recorded data is NA with a reason, never 0. The reason
is fixed: `"no compaction signal recorded by any harness"`.

**NA reasons:** always, unconditionally, the one reason above. **Upgrade trigger (recorded, not open-ended):** a
harness adapter starts recording a compaction event or field (e.g. an ACP session-management notification, or a
native-record marker); at that point this grader reads it and the class (additive: a count, summed meaningfully
across cells) becomes real. Until then the constant NA is the correct, evidence-based value -- not a placeholder
guess.

## The shared totals reader

`_totals_or_na(inp, source)` is one function, used by every metric except `cost_usd` (which keeps its own,
byte-verbatim copy of the same four checks plus its price-list check, to guarantee the move changes nothing).
It mirrors `_cost_usd`'s own record-reliability gate minus the price-list branch (that branch is cost_usd's
alone: the other five metrics need no price list): native-record read failure -> the unreadable reason;
`ex.missing` -> `HB-TEL-001 native-record fields missing: <fields>`; native-record unreadable ->
that reason; otherwise `normalize.totals(source, ex, turn_usage)`, NA `"no usage recorded"` when empty. This is
the one place these five metrics ask "can I trust this cell's usage at all", so cost_usd and every efficiency
metric agree on when usage is trustworthy, even though only `cost_usd` additionally needs a price list.

## Why int, not Decimal

The catalog (`0.4.dev`) declares no `scale` for any of the five new metrics (G2). The runner raises `HB-GRD-003`
(`ValueError`) for a `Decimal` score on a metric with no catalog scale. Adding a `scale` field is a
`bench/metrics.yaml` edit, out of this slice's scope (the Leader's call at the join, per the graders design's
Cost section: "propose them in the design; the Leader edits the catalog at the join"). Every value this module
computes is therefore rounded to the nearest `int` (`ROUND_HALF_UP` on a `Decimal` intermediate -- never a float,
per ADR-0006) before it becomes a `Score`. Ratios are expressed as integer percentages (0-100, or above 100 for
`cache_write_amplification`); `tokens_per_minute` and `output_tokens_per_turn` are integer rates;
`context_growth` and `compactions` are natively integer counts.

## Mutation coverage

`tests/mutations/cost.json` (new, this slice) names one mutant per branch of the five new metrics and their
shared totals reader. `tests/mutations/grade.json`'s three mutants that targeted the moved `_cost` logic (the
`HB-TEL-001` guard, the price-list guard, the acp_turn `source` read) are repointed from `grade/runner.py` to
`grade/cost.py` at their new, exact text -- same tests, same behaviour, since the move is verbatim; `grade.json`
stays all killed.
