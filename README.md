# x-harness-x-model-bench

Cross-harness, cross-model benchmarking for coding agents, with the [AI-Forward pack](https://github.com/timianmalloo/ai-forward) as an experimental factor.

Every run is one cell of a `harness × model × pack` grid, so three questions come from one result set:

| Comparison | Held fixed | Varied |
| --- | --- | --- |
| Harness effect | model | harness (e.g. GPT-6 Sol in Codex CLI vs Copilot CLI) |
| Model effect | harness family | model (e.g. Opus 5.5 in Claude Code vs GPT-6 Sol in Codex) |
| Pack effect | harness + model | ai-forward pack on / off |

A coordinator session runs a fixed bill of materials (22 tasks across six lifecycle scenarios, from an ambiguous prompt to multi-agent execution) in isolated per-cell workspaces. Python graders score each run, and the results come out as a CLI table, an HTML report with kiviat overlays, and two AI-written summaries.

**Status: scaffold.** The inputs, task contract, plan expansion and validation work. Running, grading and reporting are specified but not built. See [the spec backlog](docs/specs/README.md).

## Start here

| Read | For |
| --- | --- |
| [`docs/proposals/cross-harness-benchmarking-proposal.md`](docs/proposals/cross-harness-benchmarking-proposal.md) | The design: scenarios, BOM, architecture, metrics, grading, reporting, validity |
| [`docs/proposals/harness-bench-report-mockup.html`](docs/proposals/harness-bench-report-mockup.html) | The report layout target (synthetic numbers) |
| [`docs/notes/proposal-grounding-findings.md`](docs/notes/proposal-grounding-findings.md) | Open seams found while scaffolding. F1 (worker isolation) blocks the runner |
| [`docs/specs/README.md`](docs/specs/README.md) | Ordered spec backlog, each unit mapped to a pack skill and a proposal phase |
| [`tasks/README.md`](tasks/README.md) | The task folder contract |

## Layout

```
bench/                 declarative inputs
  bom.yaml             22 tasks, 6 scenarios, smoke flags, budgets
  matrix.example.yaml  target shape of a compiled matrix (combos, packs, reps, judges)
  metrics.yaml         7 areas, every metric with source, direction, grader, weight
  prices.yaml          dated list prices (empty until read from provider pages)
tasks/<ID>/            one folder per BOM task; _template/ is the copy source
src/harness_bench/
  cli.py               bench validate | plan | run | grade | report | teardown
  config.py            input validation
  plan.py              matrix x BOM -> ordered cells -> coord-run/1 batches
  adapters/            one per harness (Claude Code, Codex, Copilot)
  runner/              bootstrap (pack on/off), coord-run/1 contracts, archive
  grade/               one module per metric family, telemetry readers, judge
  report/              CLI table and HTML
  scripted_user/       clarification responder for scenario 1
skills/                this repo's skills (source); synced to .claude/ and .agents/
  start-benchmark/     the only way a run starts
  new-bench-task/      author a task folder to the contract
tools/sync-skills.py   copy skills/ to every harness surface
tests/                 pytest
```

The AI-Forward pack (revision 92) is installed in `.claude/`, `.github/`, `.grok/`, `.agents/` and `docs/ai-forward-pack/`. Those are managed by the pack's `pack-apply.py`; update them with `/updatepack`, not by hand.

## Use

Requires Python 3.12+ and [uv](https://docs.astral.sh/uv/).

```sh
uv sync
uv run bench validate          # check bench/*.yaml and every task folder
uv run bench plan              # expand the example matrix into cells and batches
uv run pytest
```

`bench plan` on the example matrix prints 144 smoke cells in 18 coord-run/1 contracts. `bench run`, `grade`, `report` and `teardown` exit 2 and name the spec that builds them.

To start a real run, open a Claude Code or Codex session in this repo and run `/start-benchmark` (Codex: `$start-benchmark`) with the matrix in prose. It stops at the first stage that is not built.

After editing anything in `skills/`, run `python tools/sync-skills.py`. A test fails if the copies drift.

## License

[Apache-2.0](LICENSE).
