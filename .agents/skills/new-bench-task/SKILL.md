---
name: new-bench-task
description: Author or advance one benchmark task folder (tasks/<ID>/) from stub to draft to ready — prompt, workspace base commit, hidden tests, oracle, blast radius, for scenario 1 the annotated clarifications, and for scenario 7 the pinned formal toolchain, hashed statements and bug-seeded variants — against the task contract in tasks/README.md. Use when building the BOM v0 tasks, starting with the smoke six (A1, B1, C1, D1, E1, F1).
runs_as: either
---

# /new-bench-task — author a BOM task to the contract

**Contract:** `tasks/README.md`. **Template:** `tasks/_template/`. **BOM entry:** `bench/bom.yaml`. **Source detail:** the task's row in the proposal's "Authored task inventory" or "Public benchmark inventory".

## Grounding (first action)

1. Read the task's `task.yaml` and its BOM row. The BOM owns `scenario` and `budget_minutes`; the task file must agree.
2. Open the source repo at the base commit you intend to pin. For authored tasks that is cfd-bench or ai-de; check the paths in `blast_radius` exist there. For public tasks, name the exact upstream instance id.
3. Mark the run start: `python docs/ai-forward-pack/scripts/audit-log.py start --session <id>`.

## Stages

1. **Prompt.** Write `prompt.md`: the exact text every combo receives. No harness-specific wording. For scenario 1 the prompt is deliberately underspecified; do not fix it.
2. **Workspace.** Pin `source.repo` and `source.commit`. List in `workspace/` only what the agent may see (stubs, public tests, docs). The pack=on/off step happens at bootstrap, not here.
3. **Oracle.** Hidden tests in `tests/`. Rubrics, reference spec and (scenario 1) `oracle/clarifications.yaml` in `oracle/`. For numeric tasks, give reference values with their derivation. Nothing here may be reachable from the workspace.
4. **Graders.** List the shared graders in `task.yaml`. Add `grade.py` only for what the shared graders cannot measure.
5. **Prove the oracle discriminates.** Run the hidden tests against the base commit (they must fail) and against a reference solution (they must pass). For scenario 7: the reference model or proof must pass on the real code and fail on every bug-seeded variant. Record both results in the task's `oracle/README.md`. An oracle that passes the base commit measures nothing.
6. **Advance status** to `draft` or `ready` and run `uv run bench validate`. It must print `ok`.

## Rules

- The task must fit its budget with headroom. coord-run/1 caps a worker at 3600 seconds.
- Scenario 6 tasks declare a `model_map`; scenario 1 tasks set `scripted_user: true`.
- Scenario 7 tasks (formalize and find bugs) declare `formal:` and list the `formal` grader. Pin the toolchain (Lean via `elan`, TLA+ tools and JDK). Hash any given statements or properties into `formal.statement_hash`. Ship at least one bug-seeded variant and a reproducing test for each seeded bug: a model or proof that also accepts the variant proves nothing. Take the properties from the source project's own docs and tests, not from your reading of its code. No Mathlib in BOM v0.
- No real secrets, customer data or private repo content in a public task folder. TheTerrace is out of scope for BOM v0.

## Definition of done

- [ ] `bench validate` prints `ok` with the task at its new status.
- [ ] Oracle shown to fail on the base commit and pass on a reference solution (for `ready`).
- [ ] Source repo and commit pinned (for `ready`).

**Audit (last action).** `python docs/ai-forward-pack/scripts/audit-log.py append --shortname "new-bench-task-<ID>" --session "<id>" --skill new-bench-task --kind command --prompt "<the request, verbatim>" --summary "<task id, new status, oracle evidence>"`.
