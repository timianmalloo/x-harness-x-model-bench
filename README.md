# x-harness-x-model-bench

Cross-harness, cross-model benchmarking for coding agents, with the [AI-Forward pack](https://github.com/timianmalloo/ai-forward) as an experimental factor.

Every run is one cell of a `harness × model × pack` grid, so three questions come from one result set:

| Comparison | Held fixed | Varied |
| --- | --- | --- |
| Harness effect | model | harness (e.g. GPT-6 Sol in Codex CLI vs Copilot CLI) |
| Model effect | harness family | model (e.g. Opus 5.5 in Claude Code vs GPT-6 Sol in Codex) |
| Pack effect | harness + model | ai-forward pack on / off |

The `bench` engine runs a fixed bill of materials (24 tasks across seven lifecycle scenarios, from an ambiguous prompt through multi-agent execution to formalizing real code in TLA+ and Lean 4). Each cell is one native harness process, driven over ACP, in its own `git clone --local` working copy and its own harness home (ADR-0013). The engine is never a cell, and no cell runs in a coordinator's session. Graders use the strongest mechanical oracle available (proof or model check, then trace conformance, then tests) before two blind judges. Results come out as a CLI table, an HTML report with kiviat overlays, and two AI-written summaries.

**Status: phase 1, the walking skeleton** ([design](docs/design/phase1-walking-skeleton.md)). Claude Code and Codex cells run end to end: plan, run, a hash-chained ledger, archive, grading (hidden tests and cost), views, `bench status`, the CLI table and a static HTML report. Judges, statistics, the scripted user, Copilot and resume are later phases. See [the spec backlog](docs/specs/README.md).

## Start here

| Read | For |
| --- | --- |
| [`docs/proposals/cross-harness-benchmarking-proposal.md`](docs/proposals/cross-harness-benchmarking-proposal.md) | The design: scenarios, BOM, architecture, metrics, grading, reporting, validity |
| [`docs/proposals/harness-bench-report-mockup.html`](docs/proposals/harness-bench-report-mockup.html) | The report layout target (synthetic numbers) |
| [`docs/notes/proposal-grounding-findings.md`](docs/notes/proposal-grounding-findings.md) | Open seams found while scaffolding (F1, worker isolation, is resolved by ADR-0013); F9 records the formal-methods evidence |
| [`docs/specs/README.md`](docs/specs/README.md) | Ordered spec backlog, each unit mapped to a pack skill and a proposal phase |
| [`tasks/README.md`](tasks/README.md) | The task folder contract |

## Layout

```
bench/                 declarative inputs
  bom.yaml             24 tasks, 7 scenarios, smoke flags, budgets
  matrix.example.yaml  target shape of a compiled matrix (combos, packs, reps, judges)
  metrics.yaml         7 areas, every metric with source, direction, grader, weight
  prices.yaml          dated list prices (empty until read from provider pages)
tasks/<ID>/            one folder per BOM task; _template/ is the copy source
models/                TLA+ models of the benchmark itself (run lifecycle, coordination protocol)
src/harness_bench/
  cli.py               bench validate | plan | run | status | grade | report | verify | teardown | tools install
  config.py            input validation
  plan.py              matrix x BOM -> ordered cells -> a frozen, content-addressed plan
  engine.py            the run engine: launch, the ACP turn, kill -> confirm -> record, archive (single ledger writer)
  lifecycle.py         the lifecycle model's guards, replayed against every ledger (conformance)
  ledger.py            hash-chained JSON Lines segments
  procs.py, host.py    Windows Job Objects per process tree; host probes
  driver.py            the ACP cell driver
  profiles.py          harness profiles (bench/profiles/*.yaml) and the real launcher
  workspace.py         each cell's own working copy; pack on/off
  tools.py             the pinned harness builds (bench/tools/package-lock.json)
  archive.py           archive, verify, delete; teardown
  telemetry/           native-record readers and the one normaliser
  grade/               grading passes; correctness (hidden tests) and cost; later-phase stubs
  views.py, status.py  projections over the verified ledger; bench-status/1
  report/              CLI table and HTML
  scripted_user/       clarification responder for scenario 1 (phase 3)
skills/                this repo's skills (source); synced to .claude/ and .agents/
  start-benchmark/     the only way a run starts
  new-bench-task/      author a task folder to the contract
tools/sync-skills.py   copy skills/ to every harness surface
tests/                 pytest
```

The AI-Forward pack (revision 92) is installed in `.claude/`, `.github/`, `.grok/`, `.agents/` and `docs/ai-forward-pack/`. Those are managed by the pack's `pack-apply.py`; update them with `/updatepack`, not by hand.

## Use

Requires Python 3.12+ and [uv](https://docs.astral.sh/uv/).

Windows only in phase 1 (Job Objects). Harness logins are the operator's subscriptions; no API keys.

```sh
uv sync
uv run bench validate                                  # check bench/*.yaml and every task folder
uv run bench tools install                             # the pinned Claude Code, Codex and ACP adapter builds
uv run bench plan --matrix bench/matrix.phase1.yaml --run-id phase1-a --confirm
uv run bench run phase1-a                              # runs every cell, then grades
uv run bench status phase1-a [--json]                  # progress; bench-status/1 with --json
uv run bench report phase1-a                           # CLI table and runs/phase1-a/report.html
uv run bench verify phase1-a                           # ledger chains, seals and archives
uv run bench teardown phase1-a                         # remove archived cells' working copies
uv run pytest
```

Cells live under `--cells-root` (default: `../bench-cells`), which must have no `CLAUDE.md`, `.claude/CLAUDE.md` or `AGENTS.md` above it (HB-PRE-002). Exit codes: 0 ok, 1 invalid input, 2 usage, 3 run incomplete, 4 not built (for example an ungraded report), 5 integrity failure.

To start a real run from prose, open a Claude Code or Codex session in this repo and run `/start-benchmark` (Codex: `$start-benchmark`).

After editing anything in `skills/`, run `python tools/sync-skills.py`. A test fails if the copies drift.

## License

[Apache-2.0](LICENSE).
