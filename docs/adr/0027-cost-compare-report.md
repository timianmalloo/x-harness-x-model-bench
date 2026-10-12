---
id: "adr-0027-cost-compare-report"
title: "ADR-0027: bench report --cost-compare generates the harness cost comparison from run records alone, with a self-contained golden"
type: adr
status: draft
owner: "@timianmalloo"
phase: "Lean re-run at equal reasoning (operator 2026-10-11)"
tags: [benchmark, report, cost, kiviat, golden, gold-a]
links:
  - { to: arch-lean-rerun, rel: refines }
  - { to: adr-0026-per-cell-anatomy-facts-catalog-0-8, rel: depends-on }
  - { to: adr-0023-lean-summary-over-verdicts, rel: relates-to }
review-by: "2027-04-11"
summary: >-
  A new pure module, report/cost_compare.py, builds the cost-comparison page from one or more RunViews and the
  existing report derivations; the CLI writes it with --out and opens it in Chrome through the pack's own render-markdown lookup.
  It keeps the hand-built page's five sections, adds reasoning, context curves, prompt composition, tool phases,
  time anatomy, the drift split and a 12-series kiviat normalised over all series. No number is hand-filled. Its
  golden runs on a fixture whose bench inputs are its own, so a pin bump never reddens it (GOLD-A).
review-suggested:
  - { by: arch-lean-rerun, on: 2026-10-11, reason: "lean re-run amendment: bench-matrix/3 settings, served read-back (HB-VAL-010/011), Grok and agy cells, catalog 0.8 drift split, cost-compare report (ADR-0024..0027)" }
---

# ADR-0027: `bench report --cost-compare`

- **Status:** Proposed
- **Date:** 2026-10-11
- **Deciders:** @timianmalloo; authored by the Leader seat (Claude Code, Opus).
- **Context:** the prompt's R-REPORT; `docs/coordination/harness-cost-comparison.html` (hand-built, 2026-10-10);
  GOLD-A (`docs/lessons/defect-classes.md:667`); LBU-5.

## Context

- The 2026-10-10 page was hand-built from the bench's reader plus hand classification (its footer). It cannot be
  re-run, and two of its classifications (drift, prompt composition) were the page author's.
- `report/html.py` assembles `report.html` per run; LBU-5 requires every non-lean report to stay byte-identical
  (Verified, `tests/goldens/report-nonlean-arms.html`).
- That golden's fixture copies the live `bench/` inputs (`tests/archived_runs.py:84-100`), so the 2026-10-10 Codex
  pin bump turned it red with `html.py` unchanged (GOLD-A, Verified).
- `render-markdown.py` has `open_in_chrome(path, env=None, finder=…, launch=…)`, which skips under `AF_NO_OPEN` or
  `CI` and returns `"not opened: <why>"` (`render-markdown.py:202-238`, Verified).

## Decision

1. **A separate output, not a `report.html` section.** `bench report --cost-compare RUN [RUN …] --out PATH
   [--open]` writes one page. `report.html`'s rendering is untouched; its catalog-version line moves once, at the
   0.8 freeze (§5).
2. **Pure build, then render.** `report/cost_compare.py` (class `grade`): `build(views) -> CostCompare` and
   `render(CostCompare) -> str`. Every number comes from the views and the report derivations ADR-0026 §4 extends. Classifications are
   the graders' and those derivations' stated rules, never the page's.
3. **Sections.** The current five, with section 2 showing requested and served effort and context per combo, and
   the served window beside every per-combo number where it differs from 1M. Then:
   - reasoning: tokens per cell and per request, visible characters, source kind per harness, and at most three
     short excerpts per harness (each ≤ 280 characters, passed through the existing egress and credential scans);
     the line "equal setting is not proven equal depth";
   - the per-request context curve per combo (median cell, with the min–max band);
   - prompt composition per combo, from `prompt_parts`;
   - tool phases (explore · edit · verify · other) and bytes returned;
   - time anatomy (model · tool · hook · idle) for every combo, `not recorded` where it is;
   - drift three ways plus attention drift, with the out-of-scope paths listed;
   - the kiviat: one checkbox per series (6 combos × 2 arms = 12); each axis normalised over **all** series, so
     toggling never rescales; axes token economy, speed, request economy, tool-call economy, clean cells, edit
     orientation, read orientation, hidden checks passed.
4. **Opening.** `--open` calls `open_in_chrome` from `docs/ai-forward-pack/scripts/render-markdown.py`, loaded by
   path (`importlib.util.spec_from_file_location`, as `tests/test_coord_transport_grok_session_new.py` loads a pack
   script), **from `cli.py` only**. Its launcher spawns Chrome with `subprocess.Popen` (`render-markdown.py:221-223`),
   so `test_architecture`'s subprocess rule names this one call site explicitly, with a test that no other module
   reaches it; a `procs` job-contained launch is not used, because it would kill Chrome. It prints the returned
   status (`opened`, or `not opened: <why>`; skipped under `AF_NO_OPEN` or `CI`). If the module cannot be loaded,
   the status is `not opened: render-markdown.py not loadable (<error>)`. No second Chrome lookup is written.
5. **Goldens (GOLD-A control), sequenced first.** `tests/goldens/cost-compare.html` is rendered from a fixture root
   that carries its own `bench/` (metrics, profiles, tool pins) and its own tasks, so a live pin, profile or catalog
   change cannot move it. A second test asserts the fixture root reads nothing from the repository's `bench/`. The
   existing `report-nonlean-arms.html` golden moves onto the same pattern **before** any profile or catalog 0.8
   edit lands, because today its fixture copies the live `metrics.yaml` and profiles (`archived_runs.py:93-96`) and
   prints `loaded: 0.7`. That returns GOLD-A to `controlled`. "LBU-5 by construction" holds for `html.py`'s
   rendering; the catalog-version line moves once, by the 0.8 freeze, and the re-capture says so.
6. **Egress, fail-closed.** The page is committed and pushed, and it carries reasoning excerpts.
   - `--cost-compare` refuses to write without `BENCH_OPERATOR_EMAIL` (today the scan degrades to `partial: email
     not supplied`, `report/html.py:59`); the operator's address and the account ids the probe reads from the
     records are the scan's literals.
   - Excerpts additionally pass an email-shape and UUID-shape filter; a matching excerpt is dropped and counted,
     never redacted in place.
   - Only derived numbers and excerpts are published. The raw records (Copilot's debug log, agy's `.db`, Grok's
     session files) stay under the git-ignored `runs/` and are never published. The development probe scans one
     debug log for `Authorization` and bearer-token shapes; a hit drops Copilot's debug logging before the last
     join (ADR-0024 §6).
7. **Tokens only.** No price, no USD (Ruling 115). A test refuses `$`, `USD` and `cost_usd` in the rendered page.

## Consequences

- The page can be regenerated for any set of runs, and the next run's page needs no hand work.
- Older runs render with `not recorded (stream absent)` in every new section, which is honest, not empty.
- The report depends on a pack script for opening only; a failure to load it never fails the report.

## Alternatives considered

- **A new section in `report.html`.** Rejected: it would move every two-arm report's bytes (LBU-5), and the page is
  cross-run by nature.
- **A copy of the Chrome lookup in the bench.** Rejected: a second definition that drifts; the pack's function takes
  its finder and launcher as parameters, so it is testable as it is.
- **Keep the hand-built page and update it by hand.** Rejected by the prompt (no hand-filled numbers).
