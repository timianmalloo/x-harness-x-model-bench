# F1 oracle

F1 is the scenario-6 task: the P0 wing spine from cfd-bench's build phasing plan, built as three coordinated tracks (`domain-model`, `derived-quantities`, `tests`) whose sub-agents run on the models in `task.yaml`'s `model_map`. Nothing in this folder except `workspace/` reaches the agent.

## Status: draft, and why

The skill's `ready` checklist is met: the source is pinned, the hidden tests fail on the base and pass on the reference (`evidence.md`), and `bench validate` prints `ok`. The task stays `draft` because two decisions are open. Each one changes what a cell measures:

- **DR-F1-1, the model map is one map for every harness.** See below.
- **DR-F1-2, no measured harness profile lets a cell start a sub-agent.** See below.

When both are ruled, `ready` is a one-line change in `task.yaml`, plus the `prompt.md` routing table if DR-F1-1 changes the map.

## Source and licence

`source.commit` is `496a0a8ca2fae9026927167a8f3e5da0a53f2233`, the HEAD of the operator's local cfd-bench clone. That repository has no licence file. The operator ruled on 2026-09-25 that cfd-bench is their own nascent repository and that the task proceeds without one. `task.yaml` records this as `source.license`. This ruling replaces R-42 condition 1 for this task.

cfd-bench at that commit holds documents and one Python tool. It has no C# code. So the vendored base is the P0 reading set: the phasing plan that defines P0, the hydrofoil knowledge base (geometry, glossary, constants, section files), the gap register (GAP-04, GAP-08, GAP-09), the backlog (COMMIT-03) and decision 0001. Everything that carries the pack is excluded: `.claude/`, `.github/`, `.agents/`, `docs/ai-forward-pack/`, `AGENTS.md`, `CLAUDE.md`, `docs/audit/`, the docs index, `.gitignore` and `.gitattributes` (the last two name the pack or its merge drivers). The benchmark prompt and grader (`docs/benchmarkprompts/`, `docs/benchmark/`, `tools/grade-benchmarks.py`) are excluded too. They are grading material for a different benchmark.

Disclosure: the vendored Markdown frontmatter carries `owner: "@timianmalloo"`. This is the operator's public GitHub handle, the same one in `source.repo`, and D1's vendored `LICENSE` carries it too. The files are vendored byte for byte (R-42 c3), so it cannot be edited out. No file carries a user-profile path, an e-mail address or a host name (`vendoring_check.py`).

## Correctness: the hidden tests

`tests/F1.HiddenTests/` holds 10 xUnit tests over the public contract in `prompt.md`. The contract has units (`Length`, `Area`, `Angle`), the `Station` value object, the `Wing` aggregate and its invariants, and one producer per derived quantity in `WingDerivations`. The grading copy receives `tests/` only after the model turn.

- The base has no code. So the test project's `ProjectReference` is conditional on `src/CfdBench.Core/CfdBench.Core.csproj` existing, and the tests reach the contract by reflection. The base builds and runs, and every test fails at run time with a named TRX. A compile-only failure would grade NA under DR-G4, not 0.
- `Directory.Build.props`, `Directory.Build.targets` and `Directory.Packages.props` inside `F1.HiddenTests/` isolate the test project from any repository-wide MSBuild files the agent writes. The nearest file of each name wins. The package pins match D1's, so the same host NuGet cache serves both tasks.
- `run.cmd`, the named TRX `f1-hidden.trx`, `NuGet.Config` with only the grading copy as a source, and `-p:RestoreSources=.` follow D1's offline pattern (R-41). No path in the folder names a user profile.

Reference values come from closed forms. One half-wing is mirrored, and chord is linear between stations. Exact fractions were computed with Python `fractions`:

| Case | Stations (y m, c m) | b | S | AR | MGC | MAC |
| --- | --- | --- | --- | --- | --- | --- |
| rectangular | (0, 0.1), (0.5, 0.1) | 1 | 1/10 | 10 | 1/10 | 1/10 |
| tapered, λ = 0.5 | (0, 0.2), (0.6, 0.1) | 6/5 | 9/50 | 8 | 3/20 | 7/45 |
| cranked | (0, 0.25), (0.2, 0.2), (0.5, 0.08) | 1 | 87/500 | 500/87 | 87/500 | 2461/13050 |

Formulas: `S = 2 Σ Δy (c0 + c1) / 2`; `MAC = (2/S) Σ Δy (c0² + c0 c1 + c1²) / 3`. For the tapered case this equals the textbook `(2/3) c_r (1 + λ + λ²)/(1 + λ)` = 0.155…, which was checked. The tolerance is 1e-9, relative to max(1, |expected|). That is loose enough for any exact per-segment formula or quadrature, and tight enough to reject a wrong definition.

The reference in `reference/src/CfdBench.Core/` passes all 10 tests. Six mutants of it are each killed (`mutants.py`, `evidence.md`): half span, MAC computed as MGC, washout sign, root-and-tip-only integration, no defensive copy, and equal span positions allowed. The tests track's own test project is graded by the judge and the drift and process graders, not by these tests.

## DR-F1-1: one model map for every harness (decision request to the Leader)

- **Facts.** The design freezes `model_map` as a flat `{role: model}` in the plan's task record (seam S3, `plan.py:147-150`). The validity view allows a served model that the map names (`views.py:434-437`). The prompt is identical for every combo (tasks/README.md). A Claude Code cell can serve only Anthropic models, and a Codex cell only OpenAI models. The Codex recording advertises `gpt-6-astra`, `gpt-6-sol` and `gpt-6-luna` (`tests/fixtures/acp/recordings/codex-x1.jsonl`). US-21's `not_applicable (routing unsupported)` is specified but not built (no match in `src/`).
- **Proposal in the folder now (assume:).** `domain-model: claude-opus-5-5`, `derived-quantities: claude-sonnet-5`, `tests: claude-sonnet-5`. The strongest model takes the aggregate and conventions. The workhorse takes the formula producers and the tests. This follows the operator's own cfd-bench guidance for delegates (vary the model within one vendor for cost and fit). `claude-haiku-4-5` is avoided on purpose: it is Claude Code's auxiliary model (`claude-code.yaml:24`), so a served Haiku call could not be told apart from title generation. **Confirm:** the Leader's ruling. **Breaks if false:** a Codex cell given this prompt cannot comply, and it would be scored on a routing it cannot perform.
- **Options.** (a) Anthropic-only: F1 runs on Claude Code cells only, and the other combos are excluded by the plan with the reason given. This needs a BOM or plan note, and US-21 is unbuilt. (b) A vendor-keyed routing table in `prompt.md` (identical text for every combo), with role keys qualified per vendor in the flat map, such as `domain-model@openai: gpt-6-astra`. It works with today's `views._mapped` (it reads values only). The coordination grader must parse the keys, and the Leader picks the OpenAI models. (c) A schema change to a per-vendor map. That is `src/**`, owned elsewhere.
- **Default if not ruled:** (a).

## DR-F1-2: sub-agents are out of profile on every measured harness (decision request to the Leader)

- **Facts, observed in this worktree.** Claude Code's settings allowlist has no `Agent` (`bench/profiles/claude-code.yaml:17`), and `tests/test_allowlist_classes.py:48-52` lists `Agent` as `OUT_OF_PROFILE`. The reader classes any tool not in `TOOL_CLASSES` as `other` (`telemetry/claude_code.py:32-35`, `:90`). Under R-45 item 2, one executed `other` call makes the cell `invalid (out-of-profile tool called)`. Copilot's `task`, `write_agent`, `read_agent` and `list_agents` are out of profile (R-45). Codex's sub-agent mechanism was not examined in this slice.
- **Consequence.** As profiled, an F1 cell either never delegates (so model-map adherence is trivially 0) or delegates and is invalid. Neither measures scenario 6.
- **Request.** A per-scenario tool allowance for scenario-6 cells: `Agent` on Claude Code, and the Codex equivalent once it is identified. It needs its own class and a red-first allowlist test. This belongs to the profile owner. It is not in this track's paths.

## Coordination grader notes (for `grade/coordination.py`, not built)

- **Model-map adherence.** For each role in `model_map`, find the sub-agent session the coordinator started for that track, and compare its served model with the map, by base id (R-32). Adherence = roles whose every served call matches ÷ 3. The coordinator's own calls are on the cell pin and are not a role. The prompt asks the agent to record any substitution. A recorded, justified substitution is a disclosed deviation: it scores 0 for that role, and the judge reads the disclosure. A silent one also scores 0, and it is MAST 1.2 evidence (see below). A cell that starts no sub-agent scores 0 on all three roles, and it cannot be graded until DR-F1-2 is ruled.
- **Per-agent attribution.** Each changed file under `src/` and `tests/` should be written by the sub-agent that owns its path in the `prompt.md` table. The owned paths are disjoint. A file written by the coordinator or by a non-owner is an attribution miss.
- **Intent-log completeness** (pack=on only; source P). Intents recorded ÷ actions taken, with orphan actions listed. For F1 the expected intents are: the plan or tracks, one delegation per track naming its model, every cross-track change request and its decision, and the integration step. With pack=off there is no intent log: NA by design, never 0.
- **Seams.** The contract in `prompt.md` is the only planned seam. A track that edits another track's paths without a recorded request is a contention event.

## MAST coding notes (for the judge)

assume: the 14 MAST modes below are named from the MAST paper (Cemri et al., arXiv 2503.13657) as recalled, not re-read in this session. **Confirm:** the judge rubric quotes the paper's taxonomy table verbatim. **Breaks if false:** the codes below need renumbering. The anchors say what each mode looks like in an F1 transcript.

| Class | Mode | F1 anchor |
| --- | --- | --- |
| Specification | 1.1 disobey task specification | The contract changed (names, namespaces, project path), or UI, file format or export was added |
| | 1.2 disobey role specification | The coordinator wrote track code; a sub-agent wrote outside its owned paths; a role ran on an unmapped model with no disclosure |
| | 1.3 step repetition | The same delegation or build was re-issued with no new information |
| | 1.4 loss of conversation history | A track redoes or contradicts a decision already recorded |
| | 1.5 unaware of termination conditions | Work continued after all tracks were green, or stopped with a track unfinished |
| Inter-agent | 2.1 conversation reset | A sub-agent was restarted and lost its brief |
| | 2.2 fail to ask for clarification | A track guessed a convention the contract leaves to `domain-model` instead of raising a request |
| | 2.3 task derailment | Work on out-of-scope P1+ content (estimator, polars, loft splines) |
| | 2.4 information withholding | A track changed a shared type without telling the dependent tracks |
| | 2.5 ignored other agent's input | A raised seam request was never answered, or its answer was not applied |
| | 2.6 reasoning-action mismatch | A stated plan (for example "tests first") differs from the recorded order |
| Verification | 3.1 premature termination | Completion claimed with the build red or a track missing |
| | 3.2 no or incomplete verification | No integrated `dotnet test` run over all tracks' output before completion |
| | 3.3 incorrect verification | Tests that pass on a wrong definition (for example MAC = S/b), or tolerances that cannot fail |

## Later waves

A mutation grader should reuse `mutants.py`'s six mutants as its seed set. Protocol conformance (S-14) reads the pack=on coordination ledger.
