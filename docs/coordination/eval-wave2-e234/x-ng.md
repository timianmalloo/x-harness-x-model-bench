---
id: brief-eval-x-ng
title: "Brief X-NG: no-guessing tasks NG1, NG2 (E4) - authoring now, ready after X-LG"
type: plan
status: proposed
owner: "@timianmalloo"
links:
  - { to: coordination-eval-wave2-e234-briefs, rel: implements }
  - { to: design-eval-property-tasks, rel: depends-on }
  - { to: design-eval-seam-contracts, rel: depends-on }
review-by: "2026-10-17"
summary: "X-NG authors tasks/NG1 and tasks/NG2 to W1-L section 7 with Erratum 1 and W0 rev 6.6, on Claude Sonnet, to draft; the ready flip follows X-LG's noguess strategy."
---

# X-NG: no-guessing tasks NG1, NG2

**Harness** Claude Code sub-agent · `model: sonnet` (served `claude-sonnet-5-5`, R-91) · **session** `x-ng-e1e4` · **branch** `build/eval-x-ng` · **budget** 200 calls · 200k · 3 h per task · **skill** `/new-bench-task`.

**Design:** W1-L §2, §3, §5, §7 (7.0 pristine vendored library, 7.1 R-97, 7.2 `verified_before_use` not built, 7.3 NG1, 7.4 NG2), §15, **Erratum 1**; W0 rev 6.6 §2, §7 (R-97 bullets); ruling R-97.

## Owned paths
`tasks/NG1/**`, `tasks/NG2/**`, and their `bench/bom.yaml` entries only.

## Scope: `draft`
Author both folders fully, including the pristine `workspace/vendor/<lib>/**`. Hidden tests observed failing on the base and passing on the reference with the real `correctness.grade`, recorded in `oracle/evidence.md`. Stay `draft`: `ready` needs X-LG's `noguess` strategy. Both `expected` roles declare `verified_before_use: {na: "not built"}` (W0 rev 5).

## Acceptance items (RV-TA W1-L rev 2; W1-L Erratum 1)
1. **R2-1:** names to the charset (`hallucinated`, `hallucmember`, `kw`, `default`, `defaultguess`, `vendoredit`, and the rest by dropping `v-` and hyphens); one `VARIANTS` literal; `flips` lists metric ids; `vendoredit` uses the create form `old: ""` on `vendor/<lib>/<file>` (W0 rev 6.6 §2 g). A test loads each `variants.py` through W1-E's reader (in this session if X-E has joined, else in the `ready` follow-on).
2. **R2-2:** a fixture asserts each base's test layout under `is_test_path(path, base_paths)` (written now as data in `oracle/evidence.md`; the `ready` follow-on asserts it through `is_test_path` once X-J2a has joined).
3. **R2-4:** NG1 supplies the **single-turn seeded-disagreement fixture** for W1-L floor item 3: a task copy whose declared `expected` differs from the observed value in one metric, which readiness must refuse with HB-RDY-003 naming the metric and both values (W1-E T-E11/T-E12). It runs in the `ready` follow-on.
4. **R2-7:** one sentinel stub per task and `test_<id>_stub_fails_every_hidden_test`.
5. **R2-8:** one sentence per task, the same rule for NG1 and NG2: the primary is the hidden tests only, **or** `ceilings.hallucinated_symbol_errors: 0`. Put the primary's value in the `hallucinated` row. Say which and why in the report; a choice that changes a verdict's meaning goes to the Coordinator as a request.
6. R-97 condition 4: NG1 naive = 2, `hallucinated` = 1, `kw` = 1 stay Inferred until the follow-on's first strategy run measures them.

## Exit
E1 README §3 join gate. Report per E1 README §4 plus the per-task state.
