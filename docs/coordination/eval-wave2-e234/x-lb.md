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

**LB0 dispatch (Coordinator #14b, 2026-10-04).** **Session** `x-lb0-e1e4` · **branch** `build/eval-x-lb0` · `model: sonnet` · **budget** 70 calls · 100k tokens · 1 session · 75 min. **Depends on:** all of X-F has joined (`a03b849f`) and the integration fix `d9155f86` (check each with `git merge-base --is-ancestor <sha> main`). What each item means on `main` today:
- `property.hidden_tests(inp, tree, label, overlay=None)`: today the hidden-test phase is inside `_hidden_check` (`grade/property.py:377`), which calls `correctness.grade` (W1-F §5.2 phase 1). Factor out that phase so a check-less helper can call it, with `overlay` copied over the grading copy before the tests run (W1-L §7.0, the pristine `vendor/<lib>` case). `_hidden_check`'s scores and `property.json` must stay byte-equal for `security`. Prove it with the existing `tests/test_property_grade_cell.py` and `tests/test_property_real_host.py`, unchanged and green.
- `property.write_section(...)`: writes one `strategy.<name>` object into the single `property.json` (W1-L §3, line 132; RV-SIM 10, RV-PAT 4).
- **The check-less sentence of W1-F §5.7.** One sentence in `docs/design/eval-property-grader.md` §5.7, granted to LB0 for that sentence only: the check-less helpers compute `property_check_pass` themselves, from the hidden tests (Kleene) and then every ceiling clause, and may only narrow W0's predicate.
- `procs.run` with `_env.grading_env` for a child. Both exist: `procs.run` at `procs.py:507` and `grading_env` at `grade/_env.py:21`. The addition is that a check-less helper's child (the NG resolver, W1-L line 239) can be started through them. `procs.py` and `tests/test_architecture.py` (R-60's allowlist, W1-F G6) are not LB0's paths. If the reach needs a line in either, raise a seam request and build that line in its own commit naming the request id (E1 README §2).
- **Not LB0's:** the three `STRATEGIES` entries. `STRATEGIES["rework"]` belongs to X-J2 and the two others to X-LG; each lands with its helper module.

## LB1: the loopback fake (**BLOCKED** until the operator's SP-LB run passes and merges)

**Unblocked (Coordinator #44, 2026-10-06):** the operator accepted SP-LB for this host ("B-2 / SP-LB closed: accepted for this host"; ADR-0018 Amendment 2); item 3's stop did not occur. Compile `al-01M48WS5VMEBVXJABRJRCZ5JFZ` (session `x-lb1-e1e4`). It also carries SHAPE-A sweep row 5 (the `check.clauses`/`check.hosts` pointers); row 4 is not LB1's.
1. EV-3 parallel-port isolation; hang-is-measured; listeners bind the literal `127.0.0.1` and assert `getsockname` (HB-CHK-005 otherwise).
2. **RV-TA W1-L R2-4 (W0 rev 6.6 R6.6c):** an RS-shaped fixture task (one fault case, reference and naive) runs through `bench discriminate` with the loopback check and gets a record. This confirms "RS needs no new discriminate code" (Inferred until then); if it cannot, raise a request.
3. If SP-LB shows a firewall prompt or rule for the loopback bind, stop and report: ADR-0018 §3's `assume:` is false and the E4 loopback half needs an Owner ruling.

## Exit
E1 README §3 join gate per session, plus the gate ring and stamp renewal (a `grade/` file, the Leader). Report per E1 README §4.
