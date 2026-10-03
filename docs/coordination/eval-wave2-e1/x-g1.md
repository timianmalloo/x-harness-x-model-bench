---
id: brief-eval-x-g1
title: "Brief X-G1: catalog 0.7.dev, the eleven property metrics (E1 build)"
type: plan
status: proposed
owner: "@timianmalloo"
links:
  - { to: coordination-eval-wave2-e1-briefs, rel: implements }
  - { to: design-eval-catalog-0-7, rel: depends-on }
  - { to: design-eval-seam-contracts, rel: depends-on }
review-by: "2026-10-17"
summary: "X-G1 adds the eleven 0.7.dev metrics with property tags and pass_at_1's also_graded_by to bench/metrics.yaml (W1-G rev 2, R-90, R-95) on Grok grok-4.7 high, one turn red and green."
---

# X-G1: catalog 0.7.dev

**Harness** Grok via `coord-runner` (Leader, R-87), `grok-4.7`, `--reasoning-effort high`, `XAI_API_KEY` removed · **contract** `x-g1.contract.json` · **deadline** 1,200 s · **dispatch** one turn, red then green · **budget** 40 calls · 100k · 1 · 0.7 h · **fallback** the green follow-on as Claude Sonnet (`model: sonnet`, served `claude-sonnet-5-5`) in the same tree (R-92 is the Owner review).

**Design:** `docs/design/eval-catalog-0-7.md` (W1-G rev 2, on `main`). **W0 rev 4:** section 7 (the table of eleven ids, kind, better, scale, `property:` tag; R-95's owner rule).

## Owned paths
`bench/metrics.yaml` (E1 owner), `tests/test_catalog_version.py`, `docs/adr/0019-catalog-0-7-property-metrics.md` (only the item-3 note, by R-95 condition 4). **Not yours:** `grade/property.py` (X-F; never create it), `config.py` (X-A1's validation checks), `grade/runner.py` (X-F builds the owner clause and T-R3..T-R6), `bench/catalog-freeze.yaml` (Leader, R-86).

## Depends on
**X-F0 joined** (`grade/property.py` exists; `validate_repo` refuses a metric whose grader has no module, `config.py:158`). R-95 ✓.

## Work
- `version: "0.7.dev"`; the eleven metrics of W0 §7 with weight 0, source D, the anchors and areas W1-G fixes (R-79 forms), each property-specific one tagged `property: <name>`; `property_check_pass` untagged.
- `pass_at_1` gains `also_graded_by: [formal]` (R-95). In the same commit, ADR-0019's item-3 note changes from "provisional on the request" to "R-95: `also_graded_by: [formal]`".
- Every 0.6 metric's definition is unchanged except that one key; the US-4 control stays green.

## Acceptance items
1. Red first: `tests/test_catalog_version.py` asserts the eleven ids with their kind, better, scale and tag (W1-G's T-C nodes), red today by assertion.
2. The eleven metrics validate under `0.7.dev` (R-90); `bench validate` exit 0 on the joined tree.
3. **RV-TA W1-G R2-2:** the design's §11 note that T-P4/T-P6 carry the `n_recorded` sweep proof is the author's; you do not edit the design. X-G3 (E3) owns T-U1b (RV-TA R2-1).
4. T-R3..T-R6 are X-F's (W0 rev 4 §7); do not write them.

## Exit
README §3 join gate; `python tools/grok_served_model.py <session dir>` exits 0 (the first Grok dispatch: if TOOL-GSM has not joined yet, the Leader reads the same fields by hand, as Q0b did, and records them). Report per README §4.
