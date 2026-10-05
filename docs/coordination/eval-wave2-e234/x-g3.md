---
id: brief-eval-x-g3
title: "Brief X-G3: scenario-7 pass_at_1 under the declared rule and the 0.7 freeze prep (E3 build)"
type: plan
status: proposed
owner: "@timianmalloo"
links:
  - { to: coordination-eval-wave2-e234-briefs, rel: implements }
  - { to: design-eval-catalog-0-7, rel: depends-on }
  - { to: design-eval-seam-contracts, rel: depends-on }
review-by: "2026-10-17"
summary: "X-G3 records scenario-7 pass_at_1 under G2's declared pass rule and prepares the 0.7 fixtures for the US-4 control, on Grok grok-4.7, after X-A3a's _passed fix joins; the Leader then runs freeze_catalog.py (R-86)."
---

# X-G3: scenario-7 `pass_at_1`, 0.7 freeze prep

> **Waits on X-A3a** (the `_passed` fix, serial spine 7) and on the XPORT fix being joined (every Grok dispatch). W1-G has passed its gate.

**Harness** Grok via `coord-runner` (Leader, `env -u XAI_API_KEY`), `grok-4.7`, `--reasoning-effort high` · **contract** `x-g3.contract.json` · **deadline** 2,400 s (catalog-sized, as X-H1; X-G1's 1,200 s retry was killed after its green commit) · **budget** 80 calls · 120k · 3 dispatches · 1.2 h · **fallback** a Sonnet follow-on in the same tree (R-87 Option 1); R-92 is Grok's Owner review.

**Coordinator #33 (2026-10-05, compiled on `integrate/e2e4-18` after the X-A3a merge `8ef425bb`).** (1) **One environment (FPR-A):** the Leader reads the run's fingerprint in the run's own environment (`env -u XAI_API_KEY`), never in a shell that has the key set. (2) **A launch or transport failure before the first prompt (XPORT-A, now also seen in `initialize`):** the follow-on runs as Claude Code Sonnet in the same tree under the same session `x-g3-e1e4`, because the runner refuses a second attempt under the same id; with no commit landed, it does the whole turn from the compile. (3) **Owned paths, completed from W1-G §5, §10 and §11 and W0 §13's test and mutation row:** also `tests/test_catalog_version.py` (`cross_version_problems`, T-U1, T-U1a-d, T-U2) and `tests/mutations/formal.json`. (4) **No `*.export` file under `tests/fixtures/catalog/0.7/`:** `tools/freeze_catalog.py:103-112` writes the four goldens there and removes the folder when a grade fails, and after the freeze `us4_problems` checks (a) and (c) read every `*.export` in it. (5) **The release label is the Leader's:** X-G3 changes no `version:` line; the release label `0.7` and the freeze are the Leader's two commits at the join (R-86 condition 3 shape, W1-G §1; W1-G §5's "X-G3 · E3 (release label)" cell is superseded, because a released version with no golden turns X-G3's own US-4 test red through check (d)).

**Design:** W1-G `docs/design/eval-catalog-0-7.md` (the scenario-7 pass rule for G2, F6-F9, the US-4 control, the correction-record contingency); ADR-0019 items 3, 4, 6; R-86, R-95; W0 rev 6.6 §7 (condition 6 as amended by R-95: `pass_at_1` stays the formal grader's through `also_graded_by: [formal]`; the entry's bytes change in 0.7).

## Owned paths
`grade/formal.py`, `tasks/G2/task.yaml` (the pass rule only), `tests/fixtures/catalog/0.7/**` (no `*.export` file), `tests/test_grade_formal.py`, `tests/test_catalog_version.py` and `tests/mutations/formal.json` (Coordinator #33, item 3). **Not yours:** `bench/catalog-freeze.yaml` (the Leader's, R-86), `bench/metrics.yaml` beyond what W1-G names for E3.

## Acceptance items
1. `pass_at_1` recorded for scenario-7 cells under the declared rule; red first on a fixture G2 cell (W1-G F8: all 12 grid-4 G2 cells have no `pass_at_1` row today).
2. The US-4 control grades the frozen grid-3 and grid-4 fixtures under 0.7 with **every 0.6 value unchanged** (EV-10). Report the before/after golden hashes. A moved golden triggers the W0 §7 rev 3 contingency (T-U5, T-U6, the smallest `corrected_from` record); report it as a stop, not a fix.
3. Grok join (E1 README §3, R-92 c1): `python tools/grok_served_model.py <session dir>` exits 0, or the `chat_history.jsonl` fallback is recorded.
4. **The Leader** runs `python tools/freeze_catalog.py` at the join (R-86); X-G3 does not.

## Exit
E1 README §3 join gate plus the gate ring and stamp renewal (a `grade/` file, the Leader). Report per E1 README §4.
