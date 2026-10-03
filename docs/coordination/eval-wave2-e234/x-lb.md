---
id: brief-eval-x-lb
title: "Brief X-LB: SR-L5 property additions (LB0) and the loopback fake harness (LB1, BLOCKED on SP-LB) (E4 build)"
type: plan
status: proposed
owner: "@timianmalloo"
links:
  - { to: coordination-eval-wave2-e234-briefs, rel: implements }
  - { to: design-eval-property-tasks, rel: depends-on }
  - { to: design-eval-seam-contracts, rel: depends-on }
review-by: "2026-10-17"
summary: "X-LB is the E4 owner of grade/property.py and bench_check.py. LB0 lands SR-L5's four small additions (needed by X-J2b and X-LG) after X-F joins; LB1 builds the loopback fake behind the PropertyCheck contract once the operator's SP-LB run passes. Claude Sonnet, security-adjacent."
---

# X-LB: property additions and the loopback fake

**Harness** Claude Code sub-agent · `model: sonnet` (served `claude-sonnet-5-5`, R-91) · **sessions** `x-lb0-e1e4`, `x-lb1-e1e4` · **branches** `build/eval-x-lb0`, `build/eval-x-lb1` · **budget** 160 calls · 180k · 2 sessions · 2.5 h · Security & Identity reviews the join (hard veto on the listener and the handle list).

**Design:** W1-F `docs/design/eval-property-grader.md`; W1-L §3 (SR-L5's list), §4 (seam 3: `bench_check.listen()`), §9.1; W0 rev 6.6 §3 (the E4 listener: `127.0.0.1`, `SO_EXCLUSIVEADDRUSE`; R6-17), §10 (D3, G4, G5 still hold), §11 (HB-CHK-005); `docs/notes/spike-s-lb-loopback.md` (once run).

## Owned paths (E4 hub owner, W0 §13)
`grade/property.py`, `grade/bench_check.py`, `tests/test_property_loopback.py` (new), `tests/test_property_grader.py` (the E4 tests).

## LB0: SR-L5 (after X-F joins; **not** blocked on SP-LB)
SR-L5 (`req-01M41MWN4RJHW0XPG2R5X1QHSM`) is an E4 follow-on of this file's E4 owner (E1 README §8). Its first consumer is X-J2b (E2), so it lands as soon as X-F has joined: `property.hidden_tests(inp, tree, label, overlay=None)`, `property.write_section`, W1-F §5.7's check-less sentence, and `procs.run` with `_env.grading_env` for a child (the NG resolver). Each with a red test; G4 and G5 stay green.

## LB1: the loopback fake (**BLOCKED** until the operator's SP-LB run passes and merges)
1. EV-3 parallel-port isolation; hang-is-measured; listeners bind the literal `127.0.0.1` and assert `getsockname` (HB-CHK-005 otherwise).
2. **RV-TA W1-L R2-4 (W0 rev 6.6 R6.6c):** an RS-shaped fixture task (one fault case, reference and naive) runs through `bench discriminate` with the loopback check and gets a record. This confirms "RS needs no new discriminate code" (Inferred until then); if it cannot, raise a request.
3. If SP-LB shows a firewall prompt or rule for the loopback bind, stop and report: ADR-0018 §3's `assume:` is false and the E4 loopback half needs an Owner ruling.

## Exit
E1 README §3 join gate per session, plus the gate ring and stamp renewal (a `grade/` file, the Leader). Report per E1 README §4.
