---
id: "adr-0029-ai-forward-pack-cost-analysis"
title: "ADR-0029: bench report --pack-cost decomposes pack-on's extra tokens per harness and per pack component, for tuning the pack"
type: adr
status: draft
owner: "@timianmalloo"
phase: "Lean re-run at equal reasoning (operator 2026-10-12)"
tags: [benchmark, report, pack, cost, attribution, tuning]
links:
  - { to: arch-lean-rerun, rel: refines }
  - { to: adr-0026-per-cell-anatomy-facts-catalog-0-8, rel: depends-on }
  - { to: adr-0027-cost-compare-report, rel: relates-to }
  - { to: rulings-register, rel: depends-on }
review-by: "2027-04-12"
summary: >-
  Ruling 121 asks for a second page, for the pack owner: where pack-on's extra tokens go, per harness, and what to
  tune. report/pack_cost.py pairs pack-on with pack-off cells per task and splits the token difference into fixed
  prefix (by pack file), extra requests, on-demand reads of pack files, skill loads, hooks, reasoning and output,
  with the residual shown. Each pack file is mapped to a pack component (always-applied instruction, scoped
  instruction, AGENTS.md/CLAUDE.md, skill, persona, hook, knowledge doc). Rule-based tuning candidates come with
  their measured figures; an optional analyst section, written by an Opus seat and labelled as analysis, is embedded.
---

# ADR-0029: `bench report --pack-cost`, the AI-Forward pack cost analysis

- **Status:** Proposed
- **Date:** 2026-10-12
- **Deciders:** @timianmalloo (Ruling 121); authored by the Leader seat (Claude Code, Opus).
- **Context:** `docs/architecture-lean-rerun.md`; ADR-0026 (the facts it reads); the 2026-10-10 cost page §5, which
  traced Copilot's 9.56x by hand (13 `applyTo: "**"` files, 235k characters, inlined on every request; hooks about
  173 s per cell).

## Context

- Two audiences (Ruling 121): the harness cost comparison (ADR-0027) is for the Copilot team, and this page is for
  the pack owner, who wants to know where the pack's tokens go so the pack can be tuned.
- The facts exist after ADR-0026: `prompt_parts` (path, characters, delivery), per-request `model_calls`,
  `tool_inputs` (paths, bytes returned), `harness_events` (hooks, skill loads, compactions), `reasoning`.
- Harnesses report tokens per request, not per prompt part, so a part's token cost is a model, not a measure.

## Decision

1. **A separate generated page.** `bench report --pack-cost RUN [RUN …] --out PATH [--analysis MD] [--open]`
   writes `docs/coordination/ai-forward-pack-cost.html`. `report/pack_cost.py` (class `grade`) is pure:
   `build(views) -> PackCost`, `render(PackCost, analysis_html | None) -> str`. It defines no derivation of its own:
   tool phases, bytes returned, carry until compaction and the per-request input series come from
   `report/tool_phases.py` and `report/context_growth.py` (ADR-0026 §4), one definition each. Opening, egress and the fail-closed
   operator-email rule are ADR-0027's (§4, §6).
2. **Pairs.** Pack-on and pack-off cells are paired by (harness, task, batch), the lean pairing
   (`verdicts.collect`). Every figure is per harness, as a per-pair median with its range, never pooled across
   harnesses.
3. **The decomposition** of Δ tokens (on − off) per pair, each term from a named fact:

   | term | how it is computed | label |
   | --- | --- | --- |
   | fixed prefix | Δ prefix characters (`prompt_parts`, on − off), by pack file, × the cell's requests, converted at the cell's own tokens-per-character (first request's input tokens ÷ its prefix characters) | **Inferred** (the conversion is a model; stated) |
   | extra requests | Δ requests × pack-off's median per-request input | Verified counts; Inferred per-request base |
   | on-demand pack reads | tool calls whose paths are pack files: bytes returned, and the measured input growth on the next request; carried into later requests until a compaction | Verified where per-request rows exist; `not recorded` for Grok (per-turn totals) |
   | skill loads | skill tool calls and their returned bytes, carried as above | as above |
   | hooks | hook invocations, their time, and any hook output that enters the context | counts and time Verified where recorded; tokens Inferred from bytes |
   | reasoning, output | Δ reasoning tokens, Δ output tokens | Verified where reported |
   | **residual** | Δ total − the sum of the terms above | shown, never hidden or spread |

4. **Pack component map.** The pack's files are the pack-on base tree minus the pack-off base tree, for the bound
   pack revision (a plan fact). They are read at report time through `gitsafe` from the pack source and commit the
   plan's `arms` block records (e.g. `C:/Projects/ai-forward@<sha>`); if that source is not readable, every file is
   `unclassified` with `not recorded: pack source not readable`, and the decomposition still renders. Each file is classed by its path and frontmatter: always-applied instruction
   (`applyTo: "**"`), scoped instruction, `AGENTS.md`/`CLAUDE.md`, skill, persona, hook, knowledge doc, other. The page
   shows each component's attributed tokens per harness, and a top-files table (file, component, harness, tokens per
   cell, requests that carried it, delivery).
5. **Tuning candidates, rule-based, each with its figure.** For example: an always-applied file inlined on every
   request whose attributed tokens per cell exceed a stated share; a knowledge doc read on demand in most cells; a hook
   whose time per cell exceeds a stated share of wall; a skill catalogue whose size is paid on every request. The
   thresholds are constants in the module, shown on the page. A candidate states the harness, the figure and the
   lever (narrow `applyTo`, move to on-demand, merge or drop a hook, shorten a skill description); it never claims an
   effect it did not measure.
6. **Outcome beside cost.** The page's header repeats the lean summary's pack effect on `property_check_pass` per
   harness with its interval and MDE, so the cost is read beside the (possibly undetectable) benefit.
7. **The analyst section.** `--analysis MD` embeds a Markdown file written by an Opus analysis seat at S9
   (`docs/coordination/ai-forward-pack-tuning.md`), rendered under the heading "Analysis (written by an analyst, not
   generated)". Every number it cites must appear in the page's generated tables: `pack_cost` extracts each number
   from the Markdown and refuses to render, listing the unmatched ones, if any is missing (a mechanical check, not a
   read). The Markdown passes `publish`'s scan (credential literals, email, UUID, bearer, `eyJ…` shapes) before it is
   committed, and again as part of the page. Without `--analysis`, the page is complete without that section.
   - **Transport disclosure:** every harness row shows its transport (Copilot `-p` behind the local adapter, Ruling
     120).
   - **Residual named:** if the development probe drops Copilot's debug log (a bearer hit, ADR-0024 §6), Copilot's
     `prompt_parts` and with them its fixed-prefix term are `not recorded`, and the page says so.
8. **Golden.** `tests/goldens/pack-cost.html` on R-GOLD's frozen fixture root, with a fixture pair whose terms sum
   to a known Δ and a planted residual.

## Consequences

- The pack owner gets measured attribution per harness and per file, with each modelled step labelled.
- The Copilot-team page (ADR-0027) stays about harness cost; pack tuning lives here.
- The tokens-per-character conversion makes per-file figures Inferred; per-request totals and the residual stay
  Verified.

## Alternatives considered

- **One page for both audiences.** Rejected by Ruling 121.
- **Attribute by re-tokenising the pack files** with each vendor's tokenizer. Rejected: no vendor tokenizer is
  installed or pinned here, and Claude, OpenAI, xAI and Google tokenizers differ; the cell's own ratio is measured
  per cell.
- **An LLM-written page.** Rejected: the numbers are generated; only the labelled analyst section is written.
