---
id: brief-eval-x-d1-followon
title: "X-D1 follow-on: turn the partial D1 green under the rev 6.4 rulings (Sonnet, same tree)"
type: plan
status: proposed
owner: "@timianmalloo"
links:
  - { to: brief-eval-x-d, rel: implements }
  - { to: coordination-eval-wave2-e1-briefs, rel: implements }
  - { to: design-eval-identity, rel: depends-on }
  - { to: design-eval-seam-contracts, rel: depends-on }
review-by: "2026-10-17"
summary: "X-D1 on Codex ended partial at 3cea81d9 with ten assertion-red tests. This Sonnet follow-on, in the same tree, implements the two direction scans in tests/import_graph.py and the two-place catalog_hash hunk in grade/runner.py (W0 rev 6.4, R6.4a and R6.4b), then runs the join gate."
---

# X-D1 follow-on (README §5: a partial end gets a Sonnet follow-on in the same tree)

**Harness** Claude Code sub-agent · **model** `model: sonnet` (served `claude-sonnet-5-5`, R-91; read it back and put it on your report's first line) · **session** `x-d1f-e1e4` · **tree** `C:\Projects\x-harness-x-model-bench-build-eval-x-d1` · **branch** `build/eval-x-d1` (do not create another) · **budget** 60 calls · 80k tokens · 45 min wall.

Read `README.md` (this folder), `x-d.md` (D1 section and acceptance items 2, 5), W1-D `docs/design/eval-identity.md` §3.1 (with *Erratum 1*), §8 and §12 (T-12..T-12d), and W0 rev 6.4 (`docs/design/eval-seam-contracts.md`, rows R6.4a and R6.4b of the rev-6 change table). Where they differ, this file wins, then `x-d.md`, then W0, then W1-D.

## State you start from (measured by the Coordinator, 2026-10-03)
- Red `0274cd37` (registry seed and assertion-red guards), then partial `3cea81d9`. Base `f82a816c` (W0 rev 5). `main` has not touched any D1-owned path since that base.
- `uv run pytest -q tests/test_identity.py tests/test_architecture.py` on `3cea81d9`: **10 failed, 36 passed**, every failure an `AssertionError`:
  - `test_import_violations_red_fixtures` ×6 (the six import forms), `test_allowed_pair_and_cli_are_silent`, `test_stale_allowed_pair_fails`, `test_real_tree_edges_equal_the_allowlist`: the two scans in `tests/import_graph.py` are stubs that return `[]`.
  - `test_catalog_component_equals_runner_catalog_hash`: `runner.catalog_hash is identity.catalog_hash` is false, because `grade/runner.py:108-112` still defines its own copy.

## The rulings you build to (W0 rev 6.4)
- **R6.4a.** `import_violations(root, classes, allowed, exempt)` and `stale_allowed(root, classes, allowed)` live in `tests/import_graph.py`, beside the resolver (`imports`, `aliases`), with W1-D §3.1's signatures. `identity.py` keeps `CLASSES`, `PLANNED`, `RUN_IMPORTS_GRADE_ALLOWED`, `catalog_hash`, `unclassed`, `stale`. Production code never imports `tests/`.
- **R6.4a (process).** Audit entries go through `python docs/ai-forward-pack/scripts/audit-log.py` (register files, union-merged). Write **no** proof file: your README §4 report is the evidence.
- **R6.4b.** In `src/harness_bench/grade/runner.py`: delete lines 108-112 (the `def catalog_hash`); line 60 becomes `from harness_bench.plan import file_hash, load_confirmed, task_version_hash`; add `from harness_bench.identity import catalog_hash` among the top-level imports. No `noqa`, no shim. Edit nothing else in that file (X-F owns it). Do not edit the callers of `runner.catalog_hash` (`composites.py`, `tools/freeze_catalog.py`, tests): the name stays a module attribute.

## What remains (three commits, named paths only)
1. **`git merge --no-ff main`** (a real merge, never a rebase), so the gate measures the tree the Leader merges. Stop and report on any conflict in a path you do not own.
2. **Green: the direction scans** (`tests/import_graph.py` only). `import_violations` walks every file under `src/harness_bench/` whose class is `run` and that is not in `exempt` (`cli.py`), resolves every import with `imports(rel, tree)` (module level, inside a function, relative, `import … as`, `from harness_bench import grade`, under `if TYPE_CHECKING:`), maps each target to a `src/` path, and returns sorted `(importer, imported)` pairs whose target class is `grade` and that are not keys of `allowed`. Map a target to the module file **or** the package `__init__.py` (`from harness_bench import grade` targets `grade/__init__.py`); a name imported from a module (`harness_bench.grade.x.y`) maps to `grade/x.py`. `stale_allowed` returns the sorted keys of `allowed` that the same scan (with no allowlist) no longer finds. Turns the nine scan tests green; the real-tree test must find **exactly** the three `config.py` pairs. If it finds a fourth, do not add it: that is a decision request (R-94 condition 3), so raise `request add --to coord-opus-e1e4` and report.
3. **Green: the catalog move** (`src/harness_bench/grade/runner.py`, R6.4b only). Turns `test_catalog_component_equals_runner_catalog_hash` green. `tests/test_catalog_version.py`, `test_freeze_catalog.py`, `test_grade_runner.py` and `test_check_regrade.py` must stay green unchanged.

Each commit message names the red nodes it turns green and ends with `Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>`. Prefix every commit and coord call with `AGENT_SESSION=x-d1f-e1e4`.

**Mutants (testability floor).** Run by hand and record each in your report, with the test that kills it: (a) the resolver ignores a function-body import (T-12's named mutant); (b) `stale_allowed` returns `[]` (T-12c); (c) `exempt` is ignored (`cli.py` is flagged). A survivor is a missing test: add it before the green commit.

**Not in this follow-on.** The four rev-6 registry texts (HB-CMP-004, HB-CMP-010, HB-RDY-011, HB-RDY-009 reserved) land in D2's first commit (`x-d.md`). Nothing from D2.

## Join gate (in the tree, on your final commit, each command on its own line, read each exit status)
```
uv run ruff check src tests tools
Remove-Item Env:HB_CLAUDE_OAUTH_TOKEN -ErrorAction SilentlyContinue
uv run pytest -q
uv run python tools/mutate_check.py --touched main
python docs/ai-forward-pack/scripts/docs-graph.py validate
```
(Bash: `env -u HB_CLAUDE_OAUTH_TOKEN uv run pytest -q`.) `mutate_check` must run under `uv run` (class MUT-C: under the global interpreter every mutant reports `error`). Every mutant killed, or a recorded reason per survivor. The Coordinator re-runs red `0274cd37` at the join.

## Report (README §4, at most 12 lines)
Served model id first · merge SHA and green SHAs · the ten red nodes and the commit that turned each green · each gate command's exit status · the three hand mutants and their killers · seam requests raised · defect-class text · budget used · what remains (expected: nothing for D1).
