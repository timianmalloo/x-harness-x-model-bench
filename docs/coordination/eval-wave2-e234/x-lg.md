---
id: brief-eval-x-lg
title: "Brief X-LG: the no-guessing and simplicity graders (E4 build)"
type: plan
status: proposed
owner: "@timianmalloo"
links:
  - { to: coordination-eval-wave2-e234-briefs, rel: implements }
  - { to: design-eval-property-tasks, rel: depends-on }
  - { to: design-eval-seam-contracts, rel: depends-on }
review-by: "2026-10-17"
summary: "X-LG builds grade/noguess.py (hallucinated_symbol_errors, R-97; verified_before_use NA not built) and grade/diffstats.py (size_vs_reference, new_abstractions, new_dependencies, the outside-radius scope clause) on Agy gemini-3.8-flash-high in three turns, after E1's hub files, X-J2a and X-LB0 join."
---

# X-LG: property graders

> **Waits on joins:** X-F, X-D2, X-A1a (E1 writers of `grade/runner.py`, `errors.py`, `identity.py`, `grade/_changes.py`), **X-J2a** (`_changes` four functions), **X-LB0** (SR-L5: `property.hidden_tests`, `write_section`, `procs.run` for the resolver child). W1-L has passed its gate.

**Harness** Agy, `gemini-3.8-flash-high` · **contract** `x-lg.contract.json` (LGa; LGb, LGc reuse it with the suffix) · **deadline** 3,300 s per dispatch · **budget** 180 calls · 180k · 3 dispatches · 3 h · **fallback** a Sonnet follow-on in the same tree (R-87 Option 1).

**Design:** W1-L §3, §5.1, §7.0-7.2, §8.1, §15, **Erratum 1**; R-97; W0 rev 6.6 §7 (the `verified_before_use` NA writer R6-9; the simplicity-primary clauses with rev 6.6's names), §9 (`noguess.py`, `diffstats.py`: grade), §11 (HB-RDY-009 reserved for X-LG, R6-18), §13.

## Owned paths (E4 hub owner)
`grade/noguess.py` and its resolver child, `grade/diffstats.py`, `grade/_changes.py` (E4), `grade/runner.py` (E4), `errors.py` (E4), `identity.py` (E4), the two `STRATEGIES` lines in `grade/property.py` (W1-L §3), their tests.

## Turns
- **LGa, registry first:** `errors.py` E4 rows (HB-RDY-009's code path, now built); `identity.CLASSES` for the new modules; skeletons that return an out-of-range value with their `STRATEGIES` lines (W1-L K1-K4).
- **LGb, `noguess`:** `hallucinated_symbol_errors` by the static resolver (`python -S` child, `sys.path` = the vendored path only), typed receivers (W1-L §7.1); a resolver failure is NA with its reason, never 0; `verified_before_use` NA `not built` for every no-guessing cell (R6-9), with its test.
- **LGc, `diffstats`:** `size_vs_reference`, `new_abstractions`, `new_dependencies` over the whole non-test tree, the `outside_radius_lines` clause (`clause: scope`); EV-6: no line counted twice with `scope_creep`, never reading `drift`'s row.

## Acceptance items
1. **Mutants (W0 rev 6.6 §7):** "drop clause (b)" is killed by `launderlines`; "drop clause (a)" by `launderclass` (fixtures from X-SM's folders, or a synthetic tree with the same shape until X-SM joins).
2. One definition of each count (`_changes`), imported, never re-implemented (DM7).
3. The campaign plan's exit evidence for X-LG; the Wave 1 testability floor.

## Exit
E1 README §3 join gate per dispatch, plus the gate ring and stamp renewal (the Leader). Served model from Agy's `cli.log`. Report per E1 README §4.
