---
id: plan-eval-x-te9
title: "X-TE9: strict bench validate and pass_rule_problems"
type: doc
owner: "@timianmalloo"
status: proposed
summary: "X-TE9 execution record: K1 cmd_validate prints readiness.problems, K2 readiness.pass_rule_problems."
tags: [evaluation, coordination, execution-graph]
links:
  - {to: design-eval-seam-contracts, rel: depends-on}
review-by: "2026-10-20"
---

Goal: strict `bench validate` (K1) and `readiness.pass_rule_problems` (K2) on build/eval-x-te9.
Done when K1 and K2 are green and the R-104 gate passes. Not in scope: config.py, grade/formal.py,
records, task folders, X-LB1 and X-K2b lines. Tier T1; fan-out 0. Compiled contract
al-01M48WS58RSYV2QVZFFG88ATPZ; session x-te9-e1e4.

## K1 (part 1)

Red 1a4fa6dc, green bf7a2d23, closing entry adfaef4d. `cmd_validate` prints `readiness.problems`;
`validate --campaign <id>`; only `x ` lines fail. Three T-E9 markers removed.

## K2 (part 2)

- Red 85974a58: three tests in tests/test_readiness.py fail with `AttributeError: ... no attribute 'pass_rule_problems'`.
- Green 5aa73a71: `readiness.pass_rule_problems(root, task_id)` returns one HB-RDY-005 failure per
  `formal.pass_rule.all_of` id outside `runner.applicable(...)["formal"]` (the set `formal.pass_at_1` checks in
  its order 2); `[]` with no pass rule. `problems()` calls it for every non-stub property task and, for a task
  with no property block (G2), runs that branch only.
- No mutation find in tests/mutations moved (no find text touches the changed readiness.py lines).

## Gates

Recorded in the closing audit entry and the hand-back report.
