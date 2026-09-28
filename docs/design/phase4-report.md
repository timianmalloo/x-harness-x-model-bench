---
id: "design-phase4-report"
title: "Design: the full HTML report and its two AI summaries (phase 4, wave 4 row 20)"
type: design
status: draft
owner: "@timianmalloo"
phase: "Phase 4 · statistics and full report (wave 4: row 20)"
tags: [benchmark, report, ui, accessibility, summaries, egress, csp, offline, uncertainty]
links:
  - { to: spec-harness-bench, rel: implements }
  - { to: arch-harness-bench, rel: implements }
  - { to: design-phase4-statistics, rel: depends-on }
  - { to: design-phase3-gateway-judges, rel: depends-on }
  - { to: adr-0005-egress-control, rel: depends-on }
  - { to: adr-0009-model-gateway, rel: depends-on }
  - { to: adr-0012-proportionate-security, rel: depends-on }
  - { to: coordination-finish-harness-bench, rel: relates-to }
  - { to: defect-classes, rel: relates-to }
review-by: "2027-03-28"
summary: >-
  Row 20: the eleven-section, self-contained, offline HTML report (US-40, US-41, US-43, US-51) and the two AI
  summaries (US-42). The report is a pure projection of the views and the statistics board, pre-rendered as HTML
  and inline SVG, with one hashed script for sort, filters and popovers under a CSP that blocks every other
  script. The only new stored fact is the summary record. The design fixes the archetype, tokens (colour-blind-safe
  categorical, PuOr diverging, viridis heatmap, all contrast-measured), every section's states, the summaries'
  claim-check contract, the EGRESS s2 sequencing, the test plan for UIA-1..15, and ten red-first slices (R0-R9).
  Nine decision requests (DR-R-1..9) carry recommended defaults. Mockup: docs/design/mockups/phase4-report.html.
---

# Design: the full report and its summaries (phase 4, wave 4 row 20)

**Tier:** T2. **Skills:** `/design-slice` (contracts, data, failure modes, tests) and `/ui-design` in **create**
mode (direction, system, mockup, rubric). **Mockup:** [`mockups/phase4-report.html`](mockups/phase4-report.html)
(self-contained, opens over `file://`, review harness included). **Scope:** design and mockup only. Nothing in
`src/` changes here. EGRESS s2 and the full grid (wave 5) are out of scope.

## 1. Grounding (the facts this design stands on)

Each fact was observed in this session unless it is labelled otherwise.

| # | Fact | Source | Label |
| --- | --- | --- | --- |
| G1 | The renderer is a static, no-JavaScript, light-only page with six sections: `header`, `validity`, `leaderboard`, `pack-effect`, `runs` (titled "Cells"), `comparison`. It has no CSP, no About disclosure, no charts and no summaries. | `src/harness_bench/report/html.py:1-11, 436-440` | Verified |
| G2 | Page text is escaped by `_e()` (`html.escape`, quote=True) at each call site; escaping is per call, not by construction. | `html.py:64-65` | Verified |
| G3 | Before writing, the page is scanned for credential shapes and exact credential values; a hit refuses the write (`HB-SEC-001`). This is not `egress.check`: it does not look for operator email, username, home path or canaries. | `html.py:443-462` | Verified |
| G4 | `board.Board` carries rows (pass@1 and gated `Interval`, pass@k, pass^k, tokens, wall, cost `Measure`, rank, rank reason, footnote) and the pack effect. It carries **no per-area composite per row**, no scenario breakdown and no frontier data. | `src/harness_bench/board.py:40-123` | Verified |
| G5 | **Defect (F-1).** `_build_pack_effect` reads `c.scores[<area id>]` for area measures and never calls `composites.area`, so every area row is NA. `compare()` does call `compute_area`. The statistics design specifies per-area deltas with the reason `not computed (no <area> score in pack=<arm>)`. | `board.py:391-422` vs `board.py:576-589`; `docs/design/phase4-statistics.md:322-336` | Verified |
| G6 | smoke-1 as rendered: 36 cells, combos `copilot-sol`, `codex-sol`, `cc-opus`, packs on and off, tasks A1 B1 C1 D1 E6 F1, k = 1. Every leaderboard row is `1=`. Gated composite 44.5 to 93.0. Cost is NA on every row (`no price list entry for gpt-6-sol` / `…claude-haiku-4-5-20251001`). 2 cells are `invalid (benchmark) HB-CELL-116`. Pack-effect pass@1 deltas: cc-opus −0.33 [−0.67, 0.00], codex-sol +0.00 [−0.60, 0.60], copilot-sol −0.33 [−0.67, 0.00], all `no detectable effect`. Every area row reads `not computed (no valid cell with a value)` (F-1). | `runs/smoke-1/report.html` (read only) | Verified |
| G7 | `egress.check(payload, *, destination, operator, secrets=(), canaries=(), token_prefixes=()) -> Verdict`; `Verdict.release(backend)` never passes a withheld payload to the backend. | `src/harness_bench/egress.py:86-90, 224-225` | Verified |
| G8 | The gateway has one request template (`judge-request/2`), one output schema (`verdict-set.v1.json`), nonce-fenced delimited data for agent text, a write-once verdict store, and two backends: `ReplayBackend` (tests) and `Headless` (live CLI). There is **no summary template, schema, store fact or claim checker** anywhere in `src/`. | Sub-agent sweep with citations (`gateway/request.py:24-44, 77-91`; `backend.py:145-160, 198-244`; `store.py:32`); spot-checked `egress.py` | Inferred (sub-agent), spot-checked |
| G9 | EGRESS s2 is "live in a Leader day window: US-46 c2 and US-47 c3". It joins after GW-I. s1 (offline gate, fake backend, a lint making the gate the only path to a backend) is built. | `docs/coordination/coordination-finish-harness-bench.md:235, 245` | Verified |
| G10 | The repository has no browser test tooling (no Playwright, Selenium or axe). Node and npx are installed on the workstation. | `pyproject.toml:18-20`; `where npx` | Verified |
| G11 | The spec fixes the IA (11 sections, in order), the state table, the copy, the Archetype Signature and UIA-1..15. | `docs/specs/harness-bench.md:749-775, 966-1126` | Verified |

## 2. Direction (in words, before any pixel)

**Who and how they arrive.** P3, a reader without the pack's context, opens a file someone sent them. They want
to know who is ahead and whether the pack helped, and they are suspicious of benchmark claims. P1, the operator,
opens the same file after a run to check what went wrong and what to rerun.

**Job-to-be-done.** "Tell me who is ahead, how sure we are, and let me check any number."

**Archetype.** B3 Telemetry Bento Box, with the spec's seven recorded deviations (spec `:966-981`):
`TelemetryBento { Type:DSS; Arch:SPA; Layout:SingleColumnReport*; Density:Compact; Nav:AnchorIndex*;
Viewport:FluidResponsive; Input:PrecisionPointer+Keyboard*; Color:Neutral+Categorical*;
Type:Sans+TabularNumerics*; Depth:Flat; Sync:StaticSnapshot*; Persistence:SelfContainedFile*; Feedback:Instant;
Motion:None; Pacing:Freeform; Transition:HardCut; A11y:WCAG_2.2_AA; }`. **Verified against the task shape:** the
task is reading and comparing, which is parallel, so a report archetype fits. The only entry is the Runs filter and
the global toggles, which are instant and never serial. G5's uncertainty-first result grammar is adopted for every
estimate. No deviation is added by this design.

**Three qualities and their opposites.** *Precise* (not approximate), *candid* (not salesy), *calm* (not
decorated). A fourth, from the smoke data: *honest about ties*. When every row is `1=`, the page must say "the
data cannot separate these" before it shows any order.

**Named references** (recalled, not re-verified in this session; Inferred):
- Stanford HELM leaderboards: a models x scenarios matrix with drill-down to raw predictions. We take the drill
  path from a number to its evidence, **not** its many-tab navigation.
- Our World in Data charts: every chart has a table view and a named source. We take the chart and table pairing
  and the source line, **not** the animation.
- Edward Tufte's small multiples and range frames: seven radars on one axis order, and whiskers instead of error
  boxes. We take restraint and the shared scale, **not** the sparkline density.
- Print scientific tables (for example, a journal's results table): rules instead of boxes, right-aligned tabular
  figures, the interval printed next to the point. We take the rule-based containment.

**Anti-goals.** No hero number. No three stat tiles. No gradient. No card grid. No medal colours for rank 1. No
order implied where the data shows a tie. No colour as the only carrier of meaning. No web font, no CDN.

**Personality in three moves.**
- **Type:** the system sans stack at 15 px body, with a real scale (13 / 15 / 19 / 26). Numbers use tabular lining
  figures. *Why:* offline (US-40) and dense (TQ1). Hierarchy comes from size and weight, not colour.
- **Colour:** neutral greys for structure. Colour appears only where it encodes data: a combo, an effect's sign, or
  a heatmap value. The focus blue is the only interface accent. *Why:* candid and calm. Colour means data.
- **Space:** a 4 px base (4 / 8 / 16 / 24 / 40). Tight inside a table, generous between sections. Sections are
  separated by a rule and 40 px, not by cards. *Why:* one editorial column, read top to bottom.

**Triggered standards** (`/ui-design` trigger table, SKILL.md:32):
- UI-T1 (expert or quantitative) **fires**: TQ1-TQ12 apply. Uncertainty is shown on screen (TQ5), provenance is in the header (TQ8), and TQ9 is N/A for a static snapshot (spec `:1088`).
- UI-T2 (generated assets) **does not fire**: the report has no imagery.
- UI-T3 (fronts a model) **fires**: the two summaries are model output. This adds three states: wrong-answer (the claim check failed), not-generated, and withheld.
- UI-T4 (native client) **does not fire**: the medium is web over `file://`.

## 3. Design system (tokens)

Primitive values live **only** in one `:root` block per theme. Components reference semantic tokens. A colour,
size or radius literal anywhere else fails UIA-10. Contrast was **measured** with a script over these exact values
(WCAG relative luminance; all pairs pass; `fails 0`).

**Colour: semantic tokens.**

| Token | Light | Dark | Use | Measured contrast (light / dark) |
| --- | --- | --- | --- | --- |
| `--bg` | `#f3f5f7` | `#0e1318` | page | — |
| `--panel` | `#ffffff` | `#151c23` | tables, charts | — |
| `--ink` | `#18212b` | `#e7ecf1` | text | 16.26 / 14.45 on panel; 14.88 / 15.70 on bg |
| `--ink-2` | `#4b5563` | `#aab5c1` | secondary text | 7.56 / 8.25 on panel; 6.91 / 8.97 on bg |
| `--ink-3` | `#7a8491` | `#76818d` | **non-text only** (axis ticks, gridline labels ≥ 3:1) | 3.79 / 4.33 on panel |
| `--rule` | `#d9dee5` | `#2a343f` | decorative dividers | decorative, reported not counted |
| `--rule-strong` | `#767f8b` | `#6c7784` | control boundaries, zero line | 4.05 / 3.77 on panel; 3.71 / 4.10 on bg |
| `--focus` | `#1d5fbf` | `#7fb2ff` | focus ring, pressed state | 6.10 / 7.95 on panel |
| `--na` | `#5f6873` | `#98a3ae` | `NA` / `not recorded` text | 5.65 / 6.70 on panel; 5.17 / 7.28 on bg |
| `--warn` | `#8a5a00` | `#e3b35a` | validity counts text | 5.93 / 8.89 on panel |
| `--bad`, `--bad-bg` | `#9b1c1c` on `#fbeaea` | `#ffb3b3` on `#3a1c1f` | invalid, refused, not published | 7.01 / 9.04 |
| `--c1..--c8` | `#0b63a8 #b35400 #00795a #a3417d #5b4bb0 #7a6400 #b0303a #3d6e8f` | `#5fb0f0 #f0a050 #3fc79a #e58cc0 #a79cf2 #d9c24a #ff8a8f #8fc3e0` | combos, in matrix order | light 5.02-6.82, dark 7.10-9.63 on panel |
| `--div-pos` / `--div-neg` | `#5e3c99` / `#b35806` | `#b2abd2` / `#fdb863` | pack-effect and comparison sign (PuOr ends) | 8.13, 4.87 / 7.89, 9.99 |
| `--heat-0..--heat-9` | viridis 10 stops `#440154 … #fde725` | same | heatmap fill | text: see below |
| `--on-heat-dark` / `--on-heat-light` | `#ffffff` / `#000000` | same | heatmap cell text | ≥ 4.58 on every fill (proof below) |

- **Categorical palette.** It is ordered from the Okabe-Ito hues, darkened for light mode and lightened for dark mode until each passes 3:1 on the panel. Colour-blind separability is *Inferred*, not measured. The guarantee does not rest on colour: every series also carries its **label** and a **marker shape** (circle, square, triangle, diamond, inverted triangle, plus, cross, star, in matrix order), per spec `:1006`. Beyond 8 combos, the colour cycles and the shape plus label carry identity.
- **Pack setting.** Pack on is solid and filled; pack off is dashed and hollow (spec `:1008`).
- **Heatmap text (DR-R-1).** The text colour is whichever of `#000` or `#fff` has the higher contrast with the cell fill. For any fill luminance L, max((1.05)/(L+0.05), (L+0.05)/0.05) ≥ √21 ≈ 4.58 > 4.5. So the rule holds for every fill, measured and proven. The spec's "switch ink" with `--ink` fails: `#21918c` gives 3.82 (white) and 4.25 (`--ink`).

**Type.** `--font: "Segoe UI", system-ui, -apple-system, "Helvetica Neue", Arial, sans-serif`;
`--fs-small 13px`, `--fs 15px`, `--fs-h2 19px`, `--fs-h1 26px`; weights 400 / 600;
`font-variant-numeric: tabular-nums lining-nums` on `.num`.
**Space.** `--s1 4px`, `--s2 8px`, `--s3 16px`, `--s4 24px`, `--s5 40px`. **Shape.** `--radius 4px` (controls
only); `--rule-w 1px`; `--focus-w 2px`; `--target 24px` (2.5.8). **Layout.** `--maxw 1240px`; `--bar-h`
(the sticky bar's measured height, drives `scroll-padding-top`, 2.4.11).

**States (every interactive component).**
- Default.
- Hover: underline or row tint `--bg`.
- Focus: a 2 px `--focus` outline, offset 2 px, never clipped by a scroll container.
- Pressed: `aria-pressed="true"` plus a `--focus` inset bar and a check glyph (not colour alone).
- Disabled: `aria-disabled="true"`, still focusable, with the reason in `aria-describedby` and shown as text (UIA-14).

**Motion.** None. Sort, filter and popovers change instantly. `prefers-reduced-motion` is honoured trivially,
because nothing animates.

**Theme (DR-R-3).** The report follows `prefers-color-scheme`. Both token sets are in the one style block. There
is no in-page toggle.

## 4. Data model (settled first)

The report is a **read model**. It stores nothing except the summary record (a model's output cannot be
re-derived). Everything else is derived at report time from the ledger views (`views.RunView`) and the board
(`board.build`), per ADR-0006 (derive, don't store).

**Aggregates touched.** `Run` (by id, read only). `GradingPass` (the current pass, read only). The new aggregate
**`SummaryRecord`**, whose root is the record and whose one invariant is **published ⇒ every claim resolved**. It
is referenced by `(run_id, pass_id)`.

**Projections added to the board** (derived, rebuildable, all `Interval` or `Measure` with a reason; never 0 for
missing):

| Projection | Grain: one row is exactly one … | Measures (additivity) | Source |
| --- | --- | --- | --- |
| `Board.areas` | (combo, pack, area) of the current pass | area composite point + 95% interval (non-additive) | `composites.area` per valid cell, then `stats.interval` keyed `area|<a>|<combo>|<pack>` |
| `Board.scenarios` | (combo, pack, scenario) | gated composite + interval (non-additive); pass@1 + interval (non-additive rate) | valid cells grouped by the plan's frozen scenario |
| `Board.frontier` | (combo, pack) | pass@1 interval (x-axis partner); cost per task, tokens per solved task, wall per task (means: non-additive; each derived from additive per-cell sums) | board rows + per-cell usage |
| `ContextGrowth` (report-only) | (combo, pack, task, turn index) | median prompt tokens over repetitions (non-additive), min and max band; compaction flag | the cell's current-extraction `model_calls` rows, ordered by native_ordinal (NA `acp_turn` source: the native record misses calls; NA Copilot: the native record gives session totals per model, not per call) |
| Pack effect (fix F-1) | (combo, measure) | on − off delta + interval (non-additive) | as today, but area measures via `composites.area` (as `compare()` does) |

**The one stored fact: `summary_records`** (append-only, in the run's facts folder, written through `ledger`).
- **Grain:** one row is exactly one summary generation attempt, for (run_id, pass_id, kind ∈ {`ranking`, `pack`}, manifest_sha256, model), recorded when the gateway call returns or is refused.
- **Columns:**
  - `manifest` (the list of inputs, each an id and a sha256);
  - `request_sha256`, `template_version`, `schema_sha256`;
  - `outcome` ∈ {`published`, `not_published`, `refused`, `withheld`, `backend_unavailable`};
  - `claims` (the schema-validated answer, only when the outcome is `published` or `not_published`);
  - `failing_claims` (count and ids);
  - `egress` (the verdict record, never the payload).
- **History rule:** append-only. A regenerate appends a new row. The report reads the newest row whose `manifest_sha256` equals the manifest rebuilt from the current pass. A mismatch reads as stale (state S-STALE below).
- **Invariant tests:** attempting to rewrite a row fails, and a `published` row with a failing claim cannot be constructed.

**Change surfaces (E7).** Each must be reached, and each has a test in §12.
- `board.py`: areas, scenarios and frontier; the F-1 fix.
- `board.export`: new keys, as `null` when missing, never 0.
- `report/model.py` (new, the presentation model).
- `report/html_builder.py` (new, safe HTML and SVG).
- `report/html.py`: the section renderers.
- `report/assets/report.js` (new): the script, hashed into the CSP.
- `report/summaries.py` (new): manifest, claim check, record.
- `gateway/request.py` + `gateway/schemas/summary-claims.v1.json`: the summary template and schema.
- `cli.py`: `bench report --summaries`.
- `report/cli_table.py`: area, scenario and summary headline lines, as ASCII (UIA-11).
- Tests and fixtures.
- The glossary terms (spec `:773`).

## 5. Architecture of the renderer (patterns named and justified)

- **Two Step View** (Fowler, PoEAA). Step 1: `report.model.build(view, board, comparison, summaries, archive_present) -> ReportModel`, a frozen dataclass tree that holds every string and number already formatted, every reason, and every `data-interval-*` pair. Step 2: pure renderers turn the model into markup. *Why:* UIA-9 and UIA-13 compare values, and a model makes each comparison a data assertion rather than an HTML scrape. It also lets the CLI table and the HTML read the same formatted strings (one definition per number). *Simplifier check:* this does not add a layer to what exists, because it replaces the ad-hoc formatting now duplicated across `_leaderboard`, `_pack_effect` and `_comparison` (html.py:218-407 repeats the delta/interval formatting three times).
- **Escape by construction.** `html_builder.el(tag, attrs, *children)` escapes every `str` child and every attribute value. Only `Html` (a `str` subclass the builder returns) passes through unescaped. Agent-derived text is always a plain `str`, so it cannot become markup (UIA-15). *Ladder:* stdlib `html.escape` on rung 3. Jinja or markupsafe would be a new dependency past rung 5 and is not justified.
- **Pre-rendered inline SVG.** Charts are drawn at generation time in Python with the same builder, with one mark per (series, cell) at most. There is no chart library. *Why:* the page must be readable with JS off (spec `:988`), have zero requests (US-40) and draw charts synchronously (spec `:1018`).
- **Progressive enhancement with one hashed script.** `report.js` (stdlib-free vanilla, under 12 KB) adds sort, the combo toggles, the pack switch, popovers, the context-growth task selector and the Runs filter. Without JS, every table is in the DOM, every chart shows all series, and every `<details>` works natively.
- **Content Security Policy** (a `<meta http-equiv>` as the first child of `<head>`): `default-src 'none'; script-src 'sha256-<report.js>'; style-src 'sha256-<style block>'; img-src data:; base-uri 'none'; form-action 'none'`. The style has no `style=""` attributes, and the builder refuses a `style` attribute. `assume:` Chromium and Firefox enforce a meta CSP on a `file://` document. Confirmed by: the UIA-15 browser test, which injects an inline script and expects no execution plus a `securitypolicyviolation` event. If false: the CSP line is decorative, and escaping (UIA-15's first half) is the only control. The test fails red in that case, so this cannot pass silently.

## 6. The page, section by section (spec order, US-40 c2)

The page structure, top to bottom:
- A sticky control bar (the combo legend toggles, the pack switch, the section index) sits under the header.
- The header carries direct links to **Leaderboard** and **Pack effect**.
- Focus: `html{scroll-padding-top: var(--bar-h)}`, and each `:target` scrolls clear of the bar (2.4.11).

Unless a section says otherwise, it follows the combo legend and the pack switch (UXA-5). Every number is an
**evidence trigger** (§7).

| # | Section | Default content | States (all rendered by the generator; one fixture each, UIA-9) |
| --- | --- | --- | --- |
| 1 | **Run header** + `▸ About this run` | Run id, BOM, catalog, price-list hash, pack revision, date, git commit. Combos with served models and builds. Judges and agreement. Spend: runs, judges, coordinator (with summary cost). Wall clock. The statistics line (`board.header_row`). Jump links. The existing disclosure rows move into a collapsed `▸ Provenance details` list, so the header stays scannable. | a missing field shows `not recorded`; NA spend shows `NA (<reason>)`, never `$0`; long ids wrap |
| 1a | About this run (US-51) | `<details>`: "This run tests the pack **ai-forward revision <n>**." Then one sentence each for combo, pack on/off, correctness-gated composite, pass@1 / pass^k, interval and not recorded (copy in §9). | collapsed (default) / expanded |
| 2 | **Validity** (US-43) | Counts per exclusion class, each a link to its filtered list: NA costs · invalid · not applicable · timed out · stopped / skipped / never started · withheld · low-confidence matchers · disagreeing judges. Each class with no source in the views reads `<class>: not recorded` (never 0). | all valid: `All <n> cells completed and are valid.`; more than 5 classes: first 5 + `and <k> more`; incomplete run: `The run is incomplete. <k> cells never started.` |
| 3 | **Leaderboard** (focal point) | The caption states the tie first: `Ranked on <measure>. Rows that share a rank cannot be separated by this data.` Columns: rank (`1=` + `(intervals overlap)` on focus) · combo (marker + label + badges) · pack (solid/hollow glyph + text) · gated ± interval bar · pass@1 ± bar · pass^k · cost per pass · tokens per solved · wall per cell · valid cells. Sort buttons sit in the column headers. The first column is sticky. | empty: `No cell completed in this run. Run bench status <run-id> to see why.`; NA: `NA` + reason on focus; unranked row: `—` + footnote; interval: `interval not computed (n < 2)`; overflow: scrolls in its region |
| 4 | **Pack effect** (US-37) | A dot-and-whisker per combo x measure on a shared zero line. The dot takes `--div-pos` or `--div-neg` by sign, or `--ink-2` when the interval crosses 0, and is also labelled `no detectable effect (interval crosses 0)`. The exclusion line always shows. | pack switch not `both`: switch `aria-disabled`, reason `Pack effect needs both settings.`, section unchanged; one pack setting: `This run has one pack setting; no effect to show.`; area NA: `not computed (no <area> score in pack=<arm>)` |
| 5 | **Cost frontier** | Three small scatter plots (pass@1 vs cost per task, vs tokens per solved, vs wall), with x and y whiskers and a Pareto step line. Table alternative below. | all cost NA (smoke-1): the cost panel shows `Cost not recorded for any combo: no price list entry for <models>.` with no axes; the other two panels still draw. NA points are omitted with `<k> combos not plotted: <reason>` under the chart |
| 6 | **Areas** | Seven radars as small multiples (one per combo), fixed axis order from the catalog, 0-100, pack on solid and pack off dashed, with a spread band when k ≥ 2. Table alternative. | an area NA: the axis is drawn hollow with an `NA` tick; all NA: `No area composites for this run: <reason>.` |
| 7 | **Scenarios** | A heatmap of combos x scenarios; each cell shows the composite, `[lo, hi]` and a pass@1 line; viridis with a legend `0 … 100, correctness-gated composite`. | no cells in a scenario: `—` + `no cells in this scenario`; NA: hatched + `not recorded` |
| 8 | **Context growth** | A task selector, then a line per combo (median over reps, min-max band), with compaction markers as ▲ plus text in the table. | task without turns: `No turns recorded for <task>.` (the option stays, with its reason) |
| 9 | **Summaries** (US-42) | Two blocks: `1 Ranking and insights`, `2 Pack observations`. Each shows the AI label, model, manifest (`<details>`), then claims as a list, each ending in its citation links. | see §8: not generated · stale · not published · withheld · refused · published |
| 10 | **Runs** | Filters (task, combo, pack, outcome, validity), then a table of every cell. A row opens its **cell card** (`<details>` inline): fields, scores with evidence, the cause for invalid/blocked/failed/stopped/withheld. | no match: `No cells match this filter.`; archive absent: US-41 copy in place of links; 576 rows, no virtualisation |
| 11 | **Comparison** | Only with `--baseline`: B − A per area and combo, with the same whisker grammar as Pack effect. | not requested: section absent and index entry absent; refused: `Runs not comparable: <each difference>`; replication: `same pack revision (<n>): a replication`; tasks in one run only listed |

**Global controls (UXA-5, UIA-8, UIA-14).**
- **Combo legend.** One toggle button per combo, with `aria-pressed` and the marker and label.
  - Hiding a combo hides its rows, marks and summary citations everywhere, except in Validity (counts never hide).
  - Hiding the last visible combo is refused: the button gets `aria-disabled` with `At least one combo must stay visible.`
- **Pack switch.** A three-button group: `both` / `on` / `off`.
  - A setting the run lacks is `aria-disabled` with `This run has pack <x> only.`
  - Inside Pack effect, the section shows `Pack effect needs both settings.` whenever the switch is not `both`.
- **Filter state.** It is held as classes on `<main>` (`hide-c2`, `pack-on`), so CSS does the hiding, one class write per change. This keeps a redraw under 100 ms at 576 cells.

## 7. Evidence, offline (US-41)

- **Triggers.** Every displayed score is a `<button class="ev">` holding the formatted value. Activation (click, Enter or Space) opens a popover. Focus or hover shows it, it stays while hovered, and Esc closes it and returns focus (1.4.13). The popover shows the raw value, unit, catalog version and evidence pointer, plus an **Open artifact** link and **Show cells** (Runs filtered, UXA-3: two activations).
- **Links.** Pointers are run-relative (`grading/<pass>/<cell>/correctness/oracle.log`, G6). `report.html` is written at the run's root, so a relative `href` opens the artifact over `file://` with no network request.
- **Archive absent (DR-R-2).** Presence is decided **at generation time** (`archive/` exists beside the report). When absent, the link is replaced by `This copy doesn't include the run archive. Evidence path: <pointer>.` and the rest works. *Residual risk:* a report generated with the archive and then copied alone shows a link the browser cannot open. The pointer text stays visible, so the reader still has the path. No offline, CSP-safe runtime probe for a local file exists (`connect-src 'none'`; file fetches are blocked in Chromium).
- **Without JS.** Each trigger is also an in-page link to the cell's row in Runs (`#cell-<id>`), where the pointer is visible text.

## 8. The AI summaries (US-42): contract

**Inputs, strictly from recorded results.**

| Kind | Manifest (each entry: id + sha256) | Never included |
| --- | --- | --- |
| 1 Ranking and insights | `board.export(board)` bytes (the canonical statistics export), the validity counts, the header facts. Nothing else. | transcripts, diffs, agent text |
| 2 Pack observations | the pack-effect part of the export; the sampled `pack=on` transcript excerpts (DR-R-4), each passed through `egress.check` individually and then fenced as delimited data (gateway nonce fences, G8) | unsampled transcripts; any excerpt whose verdict is withheld (it is dropped, and the manifest lists it as `withheld: sensitive content`) |

**Call path (no new path to a model).**
1. `summaries.manifest(pass) -> Manifest`.
2. `request.render_summary(kind, manifest) -> Rendered`: template `summary-request/1`; the task text instructs claims only, each with refs.
3. `egress.check(rendered.text, destination=<model id>, operator=…)`.
4. `.release(backend)` through the gateway pipeline, tool-less (US-46), with output validated against `summary-claims.v1.json`.
5. `claim_check(answer, results) -> CheckResult`.
6. Append a `summary_records` row.
7. The report reads it.

Egress s1's lint (the gate is the only path to a backend) covers the new call site. `bench report --summaries`
is the only trigger. It refuses while any run is live, as judge calls do (DR-R-5).

**The claim check (pure, offline, deterministic).**
- **Shape.** Every sentence or bullet is a schema `claim` with:
  - `text`;
  - `kind` ∈ {`effect`, `no_effect`, `observation`, `suggestion`};
  - at least one `ref` (a cell id, a run id, or a metric reference `board:<combo>|<pack>|<measure>` / `pack:<combo>|<measure>` / `cmp:<combo>|<pack>|<measure>`).
  The schema rejects a claim without refs.
- **Resolution.** Every ref resolves in the current pass's results.
- **Numbers.** Extraction regex: `[-+−]?\d+(?:[.,]\d+)*%?`.
  - Exempt numerals are a closed list: the `95` of "95%", the repetition count `k`, `n` of an interval, and digits inside a ref or cell id.
  - Every other number must equal a cited value's point, `lo` or `hi` after rounding that value to the report's displayed precision: rates 2 decimals, composites and area deltas 1 decimal, tokens integer, USD 2 decimals (phase4-statistics `:375`).
  - A percentage `p%` is read as the rate `p/100` at 2 decimals.
  - The sign must match after rounding. The Unicode minus `−` and the ASCII hyphen `-` are equivalent.
  - A count ("2 combos", "36 cells") must equal a count in the cited result set (the rows or cells the refs name).
  - Anything else fails.
- **The zero rule (mechanical).**
  - A `kind=effect` or `kind=suggestion` claim with any cited `pack:` or `cmp:` ref whose `no_detectable_effect` is True **fails**.
  - A `kind=no_effect` claim whose cited interval does **not** cross zero **fails** (the mirror).
  - Any claim (including `kind=observation`) that cites a `pack:` or `cmp:` ref must print that ref's `[lo, hi]` in its text, and the number check then verifies both bounds. Otherwise it fails. So relabelling an effect as an observation cannot state a bare point.
  - So "no detectable effect on cc-opus [−0.67, 0.00]" is a valid `no_effect` claim, and "the pack lowered cc-opus's pass@1" is a failing `effect` claim.
- **Suggestions.** A `kind=suggestion` claim (summary 2) must cite a metric ref and at least one cell or run id, and its text must contain the effect with its interval.
- Any failing claim means the whole summary is `not_published`, and the record lists each failing claim id with its rule.

**The manifest check (US-42 c1), independent of `summaries.manifest()`.** The test does not compare the manifest
with itself:
1. It extracts each nonce-fenced data segment from the **captured** request payload (the bytes the backend received).
2. It recomputes sha256 over each segment, and over `board.export(board)` rebuilt from the ledger.
3. It compares the result with the recorded manifest.
4. Two mutation tests must refuse:
   - one export byte changed after the manifest was built;
   - a payload segment absent from the manifest.

**How a published summary renders.** Each claim is a list item with its text, then its citations. A run id is a
link that opens Runs filtered to that cell or range (UXA-6). A metric reference opens its evidence popover. An
interval is printed as `[lo, hi]` beside its number. A `no detectable effect` row can appear only as a
`no_effect` claim, never as an effect or a suggestion (the zero rule above).

**States (copy from the spec where it has one).**

| State | When | Rendered text |
| --- | --- | --- |
| S-NONE | no record for this pass | `Summary not generated: no summary was requested for this results pass. Generate with bench report <run-id> --summaries.` |
| S-WAIT | the live backend is unavailable (before EGRESS s2 and the live gateway; see sequencing) | `Summary not generated: the summarizer backend is not available (backend_unavailable).` |
| S-STALE | the newest record's manifest ≠ the current pass | `Summary not generated: the results changed since the summary was written. Regenerate with bench report <run-id> --summaries.` |
| S-NOTPUB | claim check failed | `Not published: <n> claims did not resolve. Regenerate the summaries with bench report.` |
| S-WITHHELD | the request payload failed egress | `Summary not generated: withheld: sensitive content.` |
| S-REFUSED | schema-invalid or refused answer | `Summary not generated: the model's answer did not match the claims schema.` |
| S-PUB | published | the label `Written by <model id> from the results store. Every claim links to its runs.`, then the manifest (`<details>`), then the claims |

**Sequencing against EGRESS s2 (the dependency).**
- Slices R0-R7 need **no** live model call and **no** EGRESS s2.
  - They use egress s1 (built) and the gateway's `ReplayBackend`. The captured request is the replay key, so "the captured request payload's hashes match the manifest" (US-42 c1) is testable offline.
  - The report ships with S-NONE / S-WAIT states.
- **R8 alone** needs EGRESS s2 (US-46 c2/c3, US-47 c3 live) and the gateway's live `Headless` backend. It runs in the Leader's day window after both join, and it is the only slice that spends money.
- Until R8 lands, a report can never show a summary it could not have checked: S-PUB is reachable only through `claim_check`, which is built in R7.

## 9. Copy (load-bearing strings; the spec's strings are quoted verbatim)

- NA: `not recorded — <reason>`
- Tie: `2= (intervals overlap)`
- No effect: `no detectable effect (interval crosses 0)`
- Withheld: `withheld: sensitive content`
- Archive absent: `This copy doesn't include the run archive. Evidence path: <pointer>.`
- Empty run: `No cell completed in this run. Run bench status <run-id> to see why.`
- Judges disagree: `judges disagree by <n> steps — both verdicts shown, not scored`
- All tied (new, leaderboard caption): `All <n> rows share rank 1: their intervals overlap, so this run cannot separate them.`
- About this run (new, one sentence each):
  - **combo**: "A combo is one harness, at one build, driving one model."
  - **pack on / pack off**: "Pack on runs the task with the AI-Forward Pack installed in the workspace; pack off runs the same task without it."
  - **correctness-gated composite**: "The correctness-gated composite is the mean of the area scores (0-100) a cell recorded, set to 0 when its hidden tests fail."
  - **pass@1 / pass^k**: "pass@1 is the share of cells whose hidden tests pass; pass^k is the share of tasks passed in all k repetitions."
  - **interval**: "An interval is the 95% bootstrap range of a value over tasks and repetitions; overlapping intervals mean the data cannot tell the values apart."
  - **not recorded**: "Not recorded means the value could not be measured, and it is never counted as 0."

## 10. Security (UIA-15) and privacy

**STRIDE-lite.**

| Boundary | Threat | Disposition |
| --- | --- | --- |
| Agent text → report DOM (embedded, in the cell card only: the clarifying-question text, the judge rationale, and at most 40 lines of test output, each after egress; diffs and transcripts are linked, not embedded) | Tampering / EoP: `<script>` or `onerror` in that text | Mitigate: escape by construction (§5). The builder refuses `on*` and `style` attributes and `javascript:` hrefs. CSP blocks inline scripts. Tests: the injection fixture (UIA-15) and a builder property test (hypothesis: `str` never yields a tag). |
| Agent text → summarizer | Tampering: an injection steers claims | Mitigate: tool-less call, delimited data, schema output, and the claim check (a steered claim still must resolve). Test: US-46 c3 (R8, live) plus an offline replay variant (R7). |
| Report → reader (publication) | Information disclosure: a key, canary, email or home path in the file | Mitigate: `egress.check` per embedded excerpt; a hit renders `withheld: sensitive content` (US-47 c2). The page-level scan stays as the backstop (HB-SEC-001). Test: planted canary fixture, absent from the file (US-47 c3, offline part). DR-R-6. |
| Relative evidence href | Spoofing: a pointer that escapes the run folder (`../`) | Mitigate: pointers are validated as run-relative, with no `..` and no scheme, before an `href` is emitted; otherwise the pointer is text only. Test: a fixture pointer `../../x`. |
| Summary cost | DoS / spend | Mitigate: explicit `--summaries` only; one call per kind per manifest (the cache key is the manifest hash); cost is shown in coordinator overhead (U15a). |

**Privacy (LINDDUN-lite).** Personal data: the operator's identity (in credentials, paths and transcripts).
- *Disclosure:* mitigated by egress on every excerpt and on each summary request.
- *Identifiability:* evidence pointers are run-relative, so no home path is emitted.
- *Unawareness:* the header names what went to which vendor (the summary model, with call counts).
- Retention is unchanged: archives stay local and are never embedded (spec NFR Privacy).

## 11. Performance budget (U17; the spec's numbers)

- File ≤ 5 MB for 576 cells.
- `performance.mark('report-ready')` ≤ 2 s after navigation start.
- A filter change repaints ≤ 100 ms.
- Each is the median of 5 cold headless runs.
- Design levers:
  - SVG at most one mark per (series, cell);
  - filtering by CSS class on `<main>`, not per-node JS;
  - no per-token data;
  - transcripts linked, not embedded.
- The generator emits a `report.built` structured event: bytes, section count, cells, marks, duration per section in ms. The measurement is on by default (IO).

## 12. Test plan (red-first; every UIA and US mapped)

Rings:
- **unit** (every push): pure model, builder, claim check.
- **browser** (at readiness): Playwright plus a vendored axe-core, both new dev-only dependencies (DR-R-9), against HTML generated from fixtures.

Fixture runs are built to induce every state:
- `all-valid`, `smoke-like` (every class from G6);
- `empty` (0 completed), `one-pack`, `no-archive`;
- `injection` (`<script>`, `onerror`, a `../` pointer, a planted canary);
- `576-cell` (performance);
- `two-runs` and `two-runs-refused`;
- `no-anchors` (primary falls back to pass@1);
- `many-classes`: 7 exclusion classes, including disagreeing judges, low-confidence matchers, withheld and stopped, so the `and <k> more` form and every UIA-9 validity row can execute;
- `stale-summary`: a summary record, then a regrade;
- the summary-state inducers for UIA-9:
  - S-WAIT: a `ReplayBackend` key that answers unavailable;
  - S-REFUSED: a schema-invalid answer;
  - S-WITHHELD: a canary planted in the request's source data;
  - S-NOTPUB: an answer with one unresolved number;
- `live-run`: a run in state `running`, for DR-R-5's refusal.

**Cardinality floor (applies to every "every X" row below).** Each test first asserts that the count of X in the
DOM equals the count of X in the `ReportModel` for its fixture, and that this count is > 0. Only then does it
check the property. So an absent element can never satisfy the test. Gate-type tests (UIA-10, UIA-12) also carry
a **negative control**: one planted colour literal gives ≥ 1 finding, and one perturbed token gives a failing
pair.

| Item | Test (ring) | Red-first assertion |
| --- | --- | --- |
| UIA-1 / US-40 c1 | offline load (browser) | one test, all conjuncts: the `report-ready` mark fired, network requests = 0, console errors = 0, all 11 section ids present (10 without a baseline) |
| US-40 c2 | section order (unit) | section ids in the IA order |
| UIA-2 | axe WCAG 2.2 AA, `emulateMedia` light and dark (browser) | 0 violations each |
| UIA-3 | 320 px viewport (browser) | `scrollWidth ≤ 320` |
| UIA-4 | numeric cells (unit on DOM) | every `.num` has tabular-nums, is right-aligned, and has a unit in the cell or `th` |
| UIA-5 | intervals (unit) | every composite, pass rate, effect and delta element, including SVG marks, has both `data-interval-*` or a reason text; never `0` for missing |
| UIA-6 | palette source scan (unit) | the heatmap tokens equal the viridis stops; the diverging tokens are PuOr; no `jet`/`rainbow`/red-green pairs in the source |
| UIA-7 / US-27 | NA surface (unit + browser) | no NOT_RECORDED renders as `0`, `0%` or `$0`; the reason is reachable by focus |
| UIA-8 | keyboard script (browser) | sort, isolate, pack switch, popover open plus Esc, cell card and back; the focus ring is visible and not under the bar at each step |
| UIA-9 / UX-B | state matrix (unit) | one DOM assertion per (component, state) pair of spec `:1022-1042` plus §8's summary states |
| UIA-10 | `ui-craft-gate.py` on the generated page (unit ring, as a gate) | 0 off-token findings |
| UIA-11 | CLI plain (unit) | `NO_COLOR=1` and a redirected stdout give ASCII-only output with ties, NA and invalid marks |
| UIA-12 | token contrast (unit) | the §3 pairs computed from the style block, both modes |
| UIA-13 | chart = table (unit) | each chart's data-attributes equal its table's cells (values, units, intervals, evidence ids) |
| UIA-14 | disabled controls (browser) | on `one-pack`, at least 2 disabled controls (the pack switch and, after hiding all but one combo, the last combo toggle); each is focusable, has `aria-disabled`, and its `aria-describedby` resolves to visible text (never `title`) |
| UIA-15 / US-40 c3 | injection (unit + browser) | text is inert; an injected inline script does not run and raises `securitypolicyviolation` |
| US-41 | evidence (unit + browser) | the popover fields; a relative href present with the archive; the exact copy without it |
| US-42 c1 | manifest (unit, replay backend) | the independent recomputation in §8, plus its two mutation refusals |
| US-42 c2 | summary 2 manifest (unit) | it lists each sampled transcript; each excerpt appears nonce-fenced in the captured payload; a planted-canary excerpt is dropped and listed `withheld: sensitive content` |
| US-42 c3 | numbers (unit, table-driven) | `0.67` vs cited 0.667 passes; `0.68` fails; `44.5` vs cited 44.53 passes; a number equal only to an uncited result fails; an uncited count ("2 combos") fails; `67%` vs cited 0.67 passes; `−0.33` vs cited −0.33 passes; `0.33` vs cited −0.33 fails; `-0.33` (hyphen) vs cited −0.33 passes; one failing claim gives `not_published` |
| US-42 c4 / US-37 c2 | zero rule (unit, 5 cases) | `effect` on a crossing interval fails; `effect` on a clear interval passes; `no_effect` on a crossing interval passes; `no_effect` on a clear interval fails; an `observation` citing a `pack:` ref without its `[lo, hi]` fails |
| UXA-4 | excluded values (unit) | on `many-classes`, every NA, invalid, not-applicable, stopped, timed-out and withheld value differs in text from a measured value in every section, and its reason is in an `aria-describedby` target or the adjacent text |
| UXA-6 | summary links (browser) | activating a run id in a published summary shows Runs with only that cell's row visible |
| UXA-7 | `--summaries` refusals (unit) | on `live-run`, the refusal names the run id, the cause (a run is live) and the action (wait, or stop it) |
| US-43 no source | banner (unit) | a class with no source in the views reads `<class>: not recorded`, never `0` |
| §13 degrades | one test each | `no-anchors`: the header says `ranked on pass@1 (…)` and the areas read NA with the reason; JS off (browser, `javaScriptEnabled=false`): every series is in the DOM and `<details>` opens; `stale-summary`: S-STALE copy; withheld request: the replay backend records **0** calls |
| US-43 | banner (unit) | each class count and link; the one-line all-valid form |
| US-51 | About (unit) | the pack and revision named; the six definitions present |
| UXA-3 | 1280x800 (browser) | the first leaderboard row is in the viewport at load; evidence is 2 activations away |
| UXA-5 | filters (browser) | every section follows the legend; Pack effect shows the disabled reason |
| UXA-8 | empty run (unit) | header, banner and the empty copy; no `<svg>` with axes |
| Perf | 576-cell (unit + browser, readiness) | fails hard on the deterministic parts from `report.built`: bytes ≤ 5 MB and marks ≤ one per (series, cell); the timings (ready ≤ 2 s, filter ≤ 100 ms, medians of 5) are recorded at readiness and gate only there |
| F-1 | pack-effect areas (unit) | on a fixture with anchors, the `correctness` delta is a number, not `not computed (no valid cell with a value)`; negative: an area missing in one arm gives `not computed (no <area> score in pack=<arm>)` |

The Proof Pack and the manual NVDA and keyboard pass remain carried conditions at `/implement` (spec gate `:1176`).

## 13. Failure modes

| Mode | Disposition |
| --- | --- |
| A board measure is NA | Detect: the reason is rendered; never 0 (UIA-7). |
| No anchors for the pass | Degrade: primary = pass@1, and the header says why (board `primary_reason`). |
| Archive moved after generation | Accept: residual risk in §7; the pointer stays visible. |
| The summary backend is down or the model refuses | Degrade: S-WAIT / S-REFUSED; the report still builds. |
| Results regraded after a summary | Detect: S-STALE by manifest hash. |
| Egress hit on an excerpt or a summary | Prevent: withheld, and nothing is sent (US-47 c2). |
| A 576-cell page is too heavy | Detect: the perf test at readiness, plus the `report.built` bytes and ms. |
| JS disabled | Degrade: every table and chart shows all series; `<details>` works natively. |
| CSP not enforced on `file://` | Detect: the UIA-15 browser test fails red (the `assume:` in §5). |
| Unknown exclusion-class source | Degrade: the class shows `not recorded`. |

## 14. Mockup and rubric critique (ui-design Stage 4)

**Mockup:** `docs/design/mockups/phase4-report.html`.
- It is one file with no network reference: 0 `http(s)` references, 0 `fetch`/XHR and 0 `style=""` attributes, counted by a script.
- Its script passes `node --check`.
- The leaderboard, pack effect and frontier data are smoke-1's recorded values (G6). Areas, scenarios and context growth are marked *illustrative*, because smoke-1 has no area composites until R0.

**Review harness:**
- Viewport: 1280 / 768 / 320 frame.
- Theme: light / dark.
- Reduced motion.
- States: smoke-1, empty run, one pack setting, archive absent, summary published, comparison refused.
- An in-page audit that measures the page box first (DC-200), then 17 token contrast pairs, then 24 px targets.

**Measurements (DX23; headless Chrome `--dump-dom`, this session).**

| Measure | Value |
| --- | --- |
| Tables populated by the script | leaderboard 6 rows, pack effect 4, frontier 6, areas 6, context growth 3 |
| In-page audit, light + default | `0 contrast fail · 0 target(s) < 24 px` |
| In-page audit, dark + archive absent | `0 contrast fail · 0 target(s) < 24 px` |
| Reflow | scrollWidth 497 ≤ innerWidth 512. Headless Chrome will not size below 512, so **320 px is not measured here**; the UIA-3 Playwright test owns it. |
| Distinct type sizes | 4 (13 / 15 / 19 / 26) |
| Interface accent colours | 1 (`--focus`); every other colour encodes data |
| Focal points | 1 (the leaderboard, preceded by the tie sentence) |

**Craft detector (`ui-craft-gate.py --a11y-obligation`).** It is available and was run twice.
- Final run: **7 Minor** findings, all `cramped-padding` on the `.region` table wrappers.
- 0 accessibility findings and 0 off-token findings.
- Disposition: **accepted as a deliberate choice**. The dense table padding is the TQ1 compact-density decision in §2. The UX & Accessibility lens concurred that it hides no target-size or contrast problem, since the interactive elements carry `min-height: var(--target)` on their own.
- A clean detector run is a floor, not a verdict (CD13).

**Rubric, structure before surface (DX24).** Severity: 4 Blocker · 3 Major · 2 Minor · 1 Nit.

| # | Location | Dimension | Sev | Evidence | Fix | Status | Conf. |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | Leaderboard | 11 Archetype fit / 17 focal point | 3 | smoke-1 has every row `1=`; a sorted table alone implies an order the data does not support | a tie sentence above the table, and the caption names the ranking measure | fixed in the design and the mockup | Verified |
| 2 | Pack effect, Areas | 12 State completeness | 3 | F-1: every area row is NA on real data | R0 (DR-R-7) | slice | Verified |
| 3 | Frontier, Areas, Context growth | 14 Accessibility (1.1.1, 1.3.1) | 4 | no table alternative (UX gate) | a collapsed `<details>` table per chart | fixed | Verified |
| 4 | Legend toggles, pack switch | 14 Accessibility (UIA-14) | 3 | the disabled reason was a `title` | visible `#bar-reason` text plus `aria-describedby` | fixed | Verified |
| 5 | Frontier, Context growth | 14 Accessibility (1.4.1) | 3 | series identified by colour only | the legend's marker shape per combo and a dash per line | fixed | Verified |
| 6 | Sticky bar | 14 Accessibility (2.4.11) | 3 | static `--bar-h: 88px`, while the bar wraps | a `ResizeObserver` sets `--bar-h` from the bar's height | fixed; the 320 and 768 px check is in UIA-8 | Inferred |
| 7 | Popover | 3 User control | 1 | stayed open after the mouse left | hide on mouse-out unless focused | fixed | Verified |
| 8 | Cost frontier, cost panel | 12 State completeness | 2 | all cost is NA in smoke-1 | a sentence in place of empty axes (UXA-8) | in the design and the mockup | Verified |
| 9 | Links in tables and the bar | 14 Accessibility (2.5.8) | 2 | 16, then 2, targets under 24 px were measured | `min-height: var(--target)` on the bar, table and claim links and on `select`; inline sentence links are exempt | fixed; now 0 | Verified |

**Generic-tells self-check (DX3):**
- no gradient;
- no card grid (rules and space contain);
- no three stat tiles;
- a real type scale;
- real data, including NA and ties;
- no emoji;
- the hard states come first (the empty, one-pack and archive-absent states exist in the harness);
- one editorial column, off-centre focal emphasis by the tie sentence;
- motion is none, by decision (B3).

**Ranked plan.**
- Must fix: R0 (F-1).
- Should fix next: measure 320 px reflow and the sticky-bar focus with Playwright (UIA-3, UIA-8).
- Worth doing: a quantile dotplot option for the pack effect (spec `:1079`).
- **Highest improvement-to-effort change:** R0. It turns 21 NA pack-effect rows and 3 empty radars into numbers on data that already exists.

## 15. Implementation slices (dependency order; each one worker slice)

| Slice | Content | Depends on | Red-first test |
| --- | --- | --- | --- |
| R0 | board: fix F-1 (areas via `composites.area`, the phase4-statistics reason string); add `areas`, `scenarios`, `frontier` projections; extend `export` with `null`-for-missing | — | `test_pack_effect_area_delta_is_computed_with_anchors` (red on the current code: every area row is NA), plus the one-arm negative; R0 re-runs the catalog-0.5 freeze gate (ENV-B) and states the result |
| R1 | `html_builder` (escape by construction, SVG helpers), `report.model`, page shell: tokens (both themes), CSP with hashes, section order, index and jump links | — (parallel with R0) | `test_builder_refuses_on_attributes` (hypothesis: no `str` input yields a tag or an `on*`/`style` attribute) plus `test_csp_meta_is_first_head_child_with_script_hash` |
| R2 | Header, About this run, Validity banner | R1 | `test_validity_banner_counts_each_exclusion_class` plus `test_about_defines_six_terms` |
| R3 | Leaderboard (interval bars, ties caption, NA focus), evidence popover markup, Runs table and cell card | R0, R1 | `test_injection_fixture_renders_inert`: `&lt;script&gt;` and `onerror` appear as text inside `#cell-<id>`, and the only `<script>` element is the hashed one; plus `test_every_interval_element_has_bounds_or_reason` (UIA-5, with the cardinality floor) and `test_archive_absent_copy` |
| R4 | `report.js`: sort, combo toggles, pack switch, popovers, Runs filter; browser ring set up (DR-R-9) | R3 | `test_keyboard_path` (UIA-8) plus `test_offline_zero_requests` (UIA-1) |
| R5 | Pack effect and Comparison whisker charts with tables | R0, R3 | `test_crossing_zero_uses_neutral_mark_and_label` plus UIA-6 palette scan |
| R6 | Cost frontier, Areas radars, Scenarios heatmap, Context growth, each with a table alternative | R0, R4 | `test_chart_equals_table` (UIA-13) plus `test_empty_run_draws_no_axes` (UXA-8) |
| R7 | Summaries offline: manifest, `summary-request/1`, `summary-claims.v1.json`, `claim_check`, `summary_records` fact, section states, `bench report --summaries` with `ReplayBackend` only | R1, R3, egress s1, gateway s1 | `test_zero_rule_matrix` (5 cases), `test_number_precision_table`, `test_manifest_recomputed_from_captured_payload` (+ 2 mutations), `test_summaries_refuse_while_run_live` (fixture `live-run`) |
| R8 | Summaries live: `Headless` backend wiring; US-46 c3 planted-injection transcript; US-47 c3 canary absent | R7, **EGRESS s2**, GW-I live | `test_live_injection_does_not_change_claim_set` (Leader day window) |
| R9 | Publication egress per excerpt (DR-R-6); 576-cell performance and axe light/dark at readiness; two P3 readers (row 20 gate) | R6, R7 | `test_planted_canary_absent_from_report` plus `test_perf_576_cells` |

**Critical path:** R1 → R3 → R4 → R6 → R9. R0 runs in parallel with R1, and R7 in parallel with R4-R6. R8 sits
off the critical path, gated only by EGRESS s2.

## 16. Decision requests (each with a recommended default)

| DR | Conflict or gap | Recommended default |
| --- | --- | --- |
| DR-R-1 | Spec `:1009`: heatmap "cell text switches ink … to keep 4.5:1". With `--ink` this is not achievable on viridis mid-stops (`#21918c`: 3.82 white, 4.25 ink; measured). | Heatmap text uses `#000`/`#fff` tokens (`--on-heat-*`), whichever contrasts more. This is proven ≥ 4.58:1 on any fill. |
| DR-R-2 | US-41 archive-absent copy vs a file copied after generation: an offline, CSP-safe page cannot probe a local file. | Decide at generation time. The pointer text is always visible. The residual risk is accepted and stated. |
| DR-R-3 | UIA-2 needs light and dark; the current report is light-only; the spec names no toggle. | Follow `prefers-color-scheme`; no toggle, no stored preference. |
| DR-R-4 | US-42 c2: "each sampled `pack=on` transcript", with no sampling rule. | Deterministic: per combo, the `pack=on` cells discordant with their paired `pack=off` cell on pass@1, at most 2 per combo, by cell id. Excerpts ≤ 8,000 characters each (the final assistant turn and the test output), each egress-checked. |
| DR-R-5 | The summaries' trigger is unspecified (spec `:1107` says only "a `bench report` option"). | `bench report <run> --summaries`, which refuses while a run is live. The default `bench report` makes no model call. |
| DR-R-6 | US-47 names report publication, but today's page scan (G3) does not check operator identity or canaries; US-47 c2 wants section-level withholding. | `egress.check` on each embedded agent-derived excerpt and each summary. A hit withholds that item. The whole-page `HB-SEC-001` refusal stays as the backstop. |
| DR-R-7 | F-1 lives in `board.py` (row 19's file) but blocks rows 20's Areas and Pack-effect tests. | Fix in R0 under row 20, with row 19's reason string (phase4-statistics `:336`), and register the class (code diverging from its own design's reason text) at the fix. |
| DR-R-8 | The spec's section 10 label is "Runs", but the current page titles it "Cells", and "Cells" matches the glossary term *cell*. | Keep the IA label **Runs** as the section and nav name. The table caption says "Every cell of the run". |
| DR-R-9 | UIA-1/2/3/8/14/15 need a real browser; the repository has none. | Add `playwright` (dev dependency, pinned) and a vendored, pinned `axe-core` file under `tests/vendor/` with its licence (MPL-2.0), in a `browser` pytest marker ring run at readiness, not on every push. |

## 17. Gate record

**Round 1 (2026-09-28).** Both lenses returned **BLOCK**.
- **Test Architect** (claude-fable-5-1, hard veto) raised 7 veto items:
  1. no cardinality floor on the "every X" DOM checks;
  2. R1's injection test was vacuous at R1;
  3. the zero rule was not mechanical, and it refused honest `no_effect` claims;
  4. the manifest test was tautological;
  5. the precision rule had no extraction rule or negative tests;
  6. five §13 degrades had no test or fixture;
  7. UXA-4/6/7, the US-42 c2 negatives and US-43's no-source row were unmapped.
  Advisories: the F-1 negative plus a freeze re-run (ENV-B); negative controls for the gate-type tests; perf failing only on deterministic parts; the `report-ready` conjunct; the `live-run` fixture.
  The lens **confirmed F-1 from the code** (`board.py:391-422` vs `:579, :589`).
- **UX & Accessibility** (claude-sonnet-5, accessibility hard veto) raised 1 Blocker and 3 Majors:
  - Blocker: 3 charts lacked table alternatives;
  - Majors: the disabled reason in `title`; colour-only series; the static `--bar-h`.
  - Minors: the popover on mouse-out, and `--ink` on `--bg` unrecorded.
  It accepted the 7 detector findings.

**Resolution (by the author, in this document and the mockup; the veto holders did not re-review in this session):**
- Test Architect items 1-7 are folded into §8 (the claim kinds, the numeric extraction and exempt list, the zero rule and its mirror, the independent manifest recomputation plus 2 mutations), §10 (which agent text is embedded), §12 (new fixtures, the cardinality floor, 9 new rows) and §15 (the R1 and R3 red-first tests reassigned; R0 and R7 tests renamed). All advisories are applied.
- The UX findings are fixed in the mockup and recorded as rubric rows 3-7 and 9 in §14. `--ink` on `--bg` was measured (14.88 / 15.70) and added to §3.

**Round 2 (2026-09-28).**
- **Test Architect: PASS-WITH-CONDITIONS; veto cleared at the design gate** (by the lens, not the author). It left three conditions, all applied after round 2:
  - an `observation` citing a `pack:` or `cmp:` ref must print `[lo, hi]` (the 5th zero-rule case);
  - the sign must match (with the hyphen/minus equivalence rows);
  - the named inducers for S-WAIT, S-REFUSED, S-WITHHELD and S-NOTPUB.
- **UX & Accessibility: BLOCK on one Major.** Every disabled control pointed `aria-describedby` at one shared `#bar-reason` node, so with two controls disabled at once, the earlier one announced the other's reason. This fails the design's own UIA-14 scenario.
  - Fixed: each control gets its own reason node, `reason-<combo>` or `reason-pack-<setting>`, inside `#bar-reasons`.
  - Measured in headless Chrome with the `one-pack` state and the last combo hidden: 3 controls disabled at once, and each resolves to its own reason (`reason-c3` → `At least one combo must stay visible.`, `reason-pack-both` and `reason-pack-on` → `This run has pack off only.`).
  - **Round 3: PASS; accessibility veto cleared for the design stage** (by the lens, not the author). The lens verified the per-control nodes at script lines 288-289.
  - Carried to implementation: a real 320 px UIA-3 pass, colour-blind separability through UIA-2 and UIA-12, and axe plus NVDA (UIA-2, UIA-8).

`GATE design-slice + ui-design · 2026-09-28 · Test Architect (claude-fable-5-1), UX & Accessibility (claude-sonnet-5) · verdict: PASS (Test Architect round 2 with 3 conditions, applied; UX round 3) · authors did not clear their own vetoes`

**Round-1 status, kept for the record:** the vetoes were not cleared. The author does not clear its own vetoes. Round 2 re-reviewed each lens against:
- the Test Architect's predicate: "items 1-7 folded with named tests, failing inputs and fixtures; R1 and R3 reassigned";
- the UX predicate: "chart table alternatives present; UIA-14 semantics; not colour alone".

**Carried to `/implement`:**
- the Proof Pack;
- the manual NVDA and keyboard pass (spec `:1176`);
- the 320 px reflow and sticky-focus measurement (UIA-3, UIA-8).

**Residual risk:**
- colour-blind separability of the palette is Inferred, and shape plus label carry identity;
- a report copied after generation shows dead evidence links (DR-R-2);
- live summary behaviour is untested until R8 (EGRESS s2);
- CSP on `file://` rests on the UIA-15 browser test.
- `assume:` a CSSOM write (`element.style.setProperty`, used for `--bar-h`) is not blocked by a `style-src` hash CSP, because CSP governs parsed style attributes and elements, not CSSOM calls. Confirmed by: the UIA-8 browser test under the production CSP. If false: `--bar-h` stays at its token default, and the sticky bar can hide focus at narrow widths; UIA-8 fails red.
