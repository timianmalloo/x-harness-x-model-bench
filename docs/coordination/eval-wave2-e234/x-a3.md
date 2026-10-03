---
id: brief-eval-x-a3
title: "Brief X-A3: three arms, rings, comparison readers and the _passed fix (E3 build)"
type: plan
status: proposed
owner: "@timianmalloo"
links:
  - { to: coordination-eval-wave2-e234-briefs, rel: implements }
  - { to: design-eval-arms, rel: depends-on }
  - { to: design-eval-catalog-0-7, rel: depends-on }
  - { to: design-eval-seam-contracts, rel: depends-on }
review-by: "2026-10-17"
summary: "X-A3 lands ADR-0019 item 4's _passed fix first (X-G3 waits on it), then three-arm plans, rings and the comparison-pair readers of W1-A's E3 half, on Agy gemini-3.8-flash-high in three turns."
---

# X-A3: three arms, rings, readers, the `_passed` fix

> **Waits on E1 joins:** X-A1b (`plan.py`, `config.py`, the G1 pins) and X-H2 (`report/html.py` section 3 and its three `plan_pack` header reads). Both designs (W1-A rev 2, W1-G) have passed their gates.

**Harness** Agy, `gemini-3.8-flash-high` · **contract** `x-a3.contract.json` (A3a; A3b, A3c reuse it with the suffix) · **deadline** 3,300 s per dispatch · **budget** 240 calls · 200k · 3 dispatches · 3.5 h · **fallback** a Sonnet follow-on in the same tree (R-87 Option 1).

**Design:** W1-A `docs/design/eval-arms.md` §3.3, §3.4, §3.8 (the ratchet and literal sites), §5 and §5.1 (every on/off literal site, the E3 rows); W1-G `docs/design/eval-catalog-0-7.md` (F6-F10; item 4); ADR-0014 §5, ADR-0019 item 4; W0 rev 6.6 §5, §10 (G1: X-A3 lowers every count except `plan.py`'s to zero), §11 (HB-PLN-003), §13.

## Owned paths (E3 hub owner)
`board.py`, `report/pack_improvement.py`, `report/html.py` (E3), `report/summaries.py`, `report/cli_table.py`, `report/context_growth.py`, `views.py` (the `CellView.pack` rename only), `plan.py` (E3), `config.py` (E3), `bench/rings/pack-regression.yaml` (new), `tests/test_arms_guard.py` (the pins), their tests and goldens.

## Turns
- **A3a, first and alone (serial spine 7):** ADR-0019 item 4: a missing `pass_at_1` is NOT_RECORDED, never a failure (`pack_improvement._passed`; `board.py:480` per F10). Red: a fixture cell with no `pass_at_1` row read as a failure today. Name the defect class "absence read as failure" in the report (the Coordinator registers it). Ask the Leader to join A3a at once: X-G3 waits on it.
- **A3b:** three-arm plans; EV-17 launch balance under 5 %; rings as `bench-matrix/2` files; EV-15: a comparison of two ring hashes is refused, naming the differences (HB-PLN-003); HB-PLN-005 retired when the last `plan_pack` legacy site moves.
- **A3c:** the board and the pack section per comparison pair; legacy goldens unchanged; every W1-A §5.1 E3 literal site migrated; `CellView.pack` renamed; the G1 allowlist narrowed to `plan.py` (equality pins lowered in the same commit).

## Acceptance items
1. The campaign plan's exit evidence for X-A3, each by a named test.
2. W1-G F7: the `_passed` fix moves no committed 0.6 golden; if a golden hash moves, stop and report (it triggers X-G3's correction-record contingency, W0 §7 rev 3).
3. The Wave 1 testability floor; mutants per adjacent rule pair.

## Exit
E1 README §3 join gate per dispatch, plus the gate ring and stamp renewal if a `grade/` file is touched (the Leader). Served model from Agy's `cli.log`. Report per E1 README §4.
