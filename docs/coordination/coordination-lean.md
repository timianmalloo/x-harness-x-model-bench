---
id: coordination-lean
title: "Coordination plan - the lean pack benchmark (build, join, run, report)"
type: plan
status: proposed
owner: "@timianmalloo"
tags: [coordination, worktrees, parallelism, lean-benchmark]
links:
  - { to: arch-lean-benchmark, rel: implements }
  - { to: spec-lean-pack-benchmark, rel: implements }
  - { to: prompt-lean-benchmark, rel: depends-on }
  - { to: coordination-finish, rel: relates-to }
review-by: "2026-10-23"
summary: >-
  Nine tracks in two dispatch waves (six at the cap), plus a Leader-held serial spine of carry-over joins, the batch
  gate, readiness on the gated head and the two-batch run. The work splits at the LeanSummary contract, which is
  fixed in code first. Every derived and register artifact needs no coordination, and every authored file has one
  owner at a time. Five tracks were struck. The plan was revised after an adversary gate (one veto, cleared by
  change).
---

# Coordination plan: the lean pack benchmark

*Written 2026-10-09 by the Leader seat (Claude Code, `claude-opus-5-5`, session `lean-leader-1`) at `954b9e9d`.
Revised the same day after the adversary gate (see the gate record). Sources:
- `docs/coordination/lean-benchmark-prompt.md` (seats, routing, rules 1-8, the plan-output fields);
- the spec;
- `docs/architecture-lean-benchmark.md` with ADR-0022 and ADR-0023;
- the strategy §5;
- the defect register.

Durations and budgets are **Inferred** from the finish run's analogues unless marked.*

## Layer state

| check | result | meaning |
| --- | --- | --- |
| `coord doctor` registry | ok - 11 pattern(s) | `.agents/artifacts.yml` is installed and classifies the derived and register files below (read 2026-10-09) |
| `coord doctor` merge driver | effective - coord-regen, coord-register declared and registered | installed **once, in the primary**. Every worktree inherits it through the shared `.git/config`. Never run `coord install` in a tree; run `coord doctor` in each tree to read it back |
| `coord doctor` leader | released (epoch 19) | this run pins **epoch 20** first |
| `coord doctor` requests | 123, 0 open | no decision request is pending |
| `coord doctor` lease overlap | none (0 live leases) | no claims |
| `coord session list` | 3 active: `leader-fin-push`, `leader-fin-docs`, `leader-fin-push2` | stale sessions of the finish Leader, holding three clean, merged trees. The Leader ends them at step 1 and removes the trees |
| harness edit boundary (spikes, not measured here) | claude: enforcing (S5); copilot: historical | Grok and Agy have no edit-boundary spike: **observed-only**. The commit floor enforces for every harness |
| `pack-doctor` | 0 FAIL, 3 WARN (`python3` alias; Copilot settings; stale doc nodes) | use `python`, never `python3` |
| `pack-doctor` doorbells | not recorded | hand-back is by the runner's exit and the session ledger |
| F-PACK | `verify-bundle` 18/18 on `e1f8ad5e` (Leader re-run, 427 s); pushed to ai-forward `fix/xh-finish-upstream`, read back | the pack-on arm binds `C:/Projects/ai-forward@e1f8ad5e9e3d42acbbbffbde0702deed8699c019` |
| `run-verify-gates.py` on `main` | 1 of 9 failed (`verify-portable-text-io.py`: 3 sites) | re-measured by the Leader. After S1 joins X-FLAKE's `tools/load_repro.py`, the gate shows **5** sites (the gate's measurement on the flake3 tree) |
| `bench validate` on `main` | exit 1: 9 × HB-RDY-002, 1 × HB-RDY-001 (S2) | measured by the Leader. Readiness records are stale by design (ADR-0022 §6, amended); L-READY's pass criterion accounts for it |

## Artifact classes

| path / pattern | class | mechanism | coordination needed |
| --- | --- | --- | --- |
| `docs/docs-index.js` | derived | `docs-graph.py derive` (registry) | **no**: regenerated at each join |
| `docs/audit/audit-data.js`, `docs/audit/index.html` | derived | `audit-log.py ... render` (registry) | **no** |
| `docs/audit/audit-log.jsonl`, `docs/audit/change-log.jsonl` | register | union merge (registry) | **no**: append only |
| `.agents/log/*.jsonl` | register | union merge (registry) | **no**. Never edited (rule 4, LOGTEAR-A) |
| `docs/specs/harness-bench.html`; skill copies under `.claude/skills/**`, `.agents/skills/**` | derived | `render-doc-html.py`, `sync-skills.py` (registry) | **no**; no track edits their sources |
| `bench/discrimination/<task>/**` | authored, create-once data | `bench discriminate` writes it; the engine identity does not hash it | Leader only (L-READY). Not added to the registry: one writer |
| `docs/notes/rulings.md` | authored, one writer | the Owner (`owner-fable`) rules into it | the Owner only |
| `docs/lessons/defect-classes.md` | authored, one writer | tracks **hand back** class text in their report; only a Coordinator edits the file | Coordinator only |
| every other path a track names below | authored | one owner per file at a time (Tracks) | the only real contention |

## Tracks

**Why pay the multiplier.** An orchestrator-worker shape costs roughly **15×** the tokens of one session (GO6). Each
track's justification is named in the detail table:
- **independence**: no data, decision or resource edge;
- **isolation**: a destructive or long job kept out of the tree being written;
- **context hygiene**: a fresh context for an unrelated job;
- **machine time**: the Leader's runs and suites.

The token figure in each budget is a **context ceiling per dispatch** (the CEIL-A split threshold), not total
spend. Total spend is measured at each hand-back and summed in the run report (IO).

**Pins:**
- Grok `grok-4.7`, effort high. R-103: read the served id with `tools/grok_served_model.py --tree`, with
  `XAI_API_KEY` unset.
- Agy `gemini-3.8-flash-high`.
- Claude sub-agents through the Agent tool, always with an explicit `model`: Opus `claude-opus-5-5`; Haiku latest,
  `claude-haiku-5-5` (2026-10-09).

**Common to every row:**
- leader **epoch 20**;
- **fan-out cap 0** (a worker spawns nothing: FALLBACK-A);
- the decision requests a track raises go to **`owner-fable`**, ruled into `docs/notes/rulings.md`;
- floors (CEIL-A) are taken at the first edit: Grok 88k, Agy about 105k (Inferred, one case), and Opus and Haiku
  measured at the first compile and recorded. The threshold is the floor plus the planned work.

**Common exit evidence (R-104 and the gate's additions):**
- the worker's own tests are red first, on an assertion, and then green;
- the guard list runs on the first and the final commit;
- `uv run python tools/mutate_check.py <own mutation files>` (MUT-C: always under `uv run`);
- **retarget every existing mutation find text the edit moves**, so that `tests/test_mutate_check.py`'s MUT-E check
  (each find occurs exactly once, `:413`) stays green. The owners are in the rows below;
- `uv run ruff check src tests tools` passes;
- `docs-graph.py validate` passes;
- `test_identity.py` passes (every new `src/` file is classed in `identity.CLASSES`);
- `test_arms_guard.py` passes (no new `"on"`, `"off"` or `"pack"` literals: arm ids come from `plan.comparisons`
  and `config.ARM_OFF`);
- the console flag is on every launch the track adds;
- the served id is recorded;
- the windows check runs at hand-back;
- a new defect class is handed back as text, never written to the register;
- no `--no-verify`, `-n` or hooks override, and no rewritten commit.

**The whole suite is the Leader's** (rule 2), before every `src/` or `tests/` join.

| track | owns (authored) | depends on | tier | fan-out cap | budget | exit evidence | harness |
| --- | --- | --- | --- | --- | --- | --- | --- |
| **L-CONTRACT** the `LeanSummary` seam in code | `src/harness_bench/lean.py`: the dataclasses, the `ESTIMATE` constant and the `build` signature only, exactly as `docs/architecture-lean-benchmark.md` *Contracts*, with `build` raising `NotImplementedError("L-SUM-A")`; `lean.py`'s `"grade"` entry in `src/harness_bench/identity.py` `CLASSES`; `tests/test_lean_contract.py` | epoch 20 | T1 | 0 | 25 · measured + 20k · 1 · 0.4 h | `tests/test_lean_contract.py` pins every dataclass's field names and order, and the `ESTIMATE` values, to the architecture's block (red first: the module is absent); `test_identity.py` green; ruff clean. **Joined and pushed before wave 1** | Coordinator #1 (Claude Code, Opus) |
| **L-MATRIX** the lean ring and the pooling check | `bench/rings/lean.yaml`; `config.RING_TAGS` (`src/harness_bench/config.py:41`); the HB-CMP-010 refusal of ring `lean` in `campaign.plan_block` (`src/harness_bench/campaign.py:1170-1176`); in `src/harness_bench/board.py`, the comparability preconditions extracted from `compare` (`:726-795`, codes and messages unchanged) and the pooling check of ADR-0022 §3; `tests/test_lean_ring.py`, `tests/test_lean_pool_check.py` (names checked free); `tests/mutations/lean_ring.json`; the moved finds in `tests/mutations/board.json` (`:124`) and `tests/mutations/campaign.json` | epoch 20 | T1 | 0 | 70 · 88k + 60k · 1-2 · 1.2 h | red 1: `bench plan bench/rings/lean.yaml` exits INVALID with `ring.tag must be one of (...)` today, plus a unit test on `config.validate_matrix`. Red 2: a unit test on `campaign.plan_block(root, "x", {"ring": {"tag": "lean"}})` asserts code **HB-CMP-010** (today it raises another code). Red 3: the pooling check's unit tests, one per rule in ADR-0022 §3, quoted: *"both plans carry ring tag `lean`"*; *"both plans have equal `cells` as a set keyed by `cell_id`, compared on task, combo, arm and model"*; *"both plans have equal `arms` (pack revisions), `builds`, `profiles` and `instruction_lists`"*; *"`parameters` (including `parallelism`) and `envelope_seconds` are shown as differences, never refused"*; a ring-hash difference raises **HB-PLN-003** and every other `compare` precondition raises **HB-STA-002**, as `compare` does. The existing `compare` tests are unchanged and green. **Plan proof** (TEST-E: run without `--json`): two `bench plan bench/rings/lean.yaml --arm on=C:/Projects/ai-forward@e1f8ad5e9e3d42acbbbffbde0702deed8699c019` each exit 0 with **60 cells**: 20 per combo, 30 per arm, 2 per task per combo, every `off` cell with 0 instruction files, and every cell with its pin (`cc-opus` `claude-opus-5-5`, `codex-sol` `gpt-6.1-sol`, `copilot-sol` `gpt-6.1-sol`). Without `--arm`, it refuses and names the unbound role (LB-1) | Grok |
| **L-SUM-A** the lean view and the ratio statistic | `src/harness_bench/lean.py` (`build` and its helpers; the contract may change only **additively**, on the Coordinator's ruling); `src/harness_bench/stats.py` (`paired_ratio` only); `src/harness_bench/views.py` (`run_wall_ns` and the grading-duration helper, names checked free); `tests/test_lean.py`, `tests/test_stats_paired_ratio.py`; `tests/mutations/lean.json`, `tests/mutations/stats_paired_ratio.json`; the moved finds in `tests/mutations/views.json` and `tests/mutations/stats.json` | L-CONTRACT joined | T2 | 0 | 140 · 88k + 120k · 2 · 2.2 h | red first on known pairs: LB-4 (effect, interval and statement against `stats.paired_delta` on the same Obs; `k of 20` and the excluded cells with causes; 0 pairs → `not recorded (0 pairs)`); LB-5 (pooled task key `<combo>/<task>`; the disagreement flag when two intervals lie wholly on opposite sides of 0); LB-6 (counts, `up`/`down`/`same`); LB-7 (ratio of totals; pairs without tokens or with 0 pack-off tokens excluded **and counted**; a missing value never 0); LB-3 (measured beside `ESTIMATE`; infrastructure failures over 20% named with causes; a projected batch-2 run over 2 h and tokens over half the approved budget both computable from the fields); LB-2 (pre-registration timing, both sides); MDE 20 → 0.31, 10 → 0.42, 60 → 0.19, 30 → 0.26. **REUSE-A's control:** the effect interval and the ratio interval at one pair per task with differing tasks each have **nonzero width**. `paired_ratio` matches a hand-computed reference. `stats.paired_delta`'s existing tests are unchanged and green. Grading minutes come from `mono_ns` (`grade/runner.py:263-299`). Mutants killed | Grok |
| **L-SUM-B1** the lean section renderer | `src/harness_bench/report/lean_section.py` and its `"grade"` entry in `identity.CLASSES`; the section's insertion in `src/harness_bench/report/html.py` at the campaign section's slot (`:2259-2266`); `tests/test_lean_section.py`; **a new report golden**, `tests/goldens/report-nonlean-<fixture>.html` (name checked free), captured from an existing two-arm, non-lean fixture run at the J0 head **in B1's first commit, before `html.py` is touched**; `tests/mutations/lean_section.json`; the moved finds in `tests/mutations/report.json` | L-CONTRACT joined | T2 | 0 | 120 · 105k + 100k · 2 · 2.2 h | built from **hand-built `LeanSummary` fixtures** (contract changes reach B1 only at L-SUM-C). Checks: LBU-1 to LBU-4; **LBU-5:** the new golden is byte-equal after the section exists (red is impossible by design; the golden's own first commit is the proof it was captured before the change); LBI-1 (axe-core 0 violations, light and dark, **run**, not skipped); LBI-2 (statements readable with colour and glyphs removed); LBI-3 (`data-interval-lo/hi`, `data-mde`); LBI-4 and LB-6 (0 matches for `better|worse|dominates`, case-insensitive, in the per-property text); LB-5's note text exactly `harnesses disagree: read the per-harness rows`; LB-7 (the exclusion count shown; 0 `$`, `USD` or `cost_usd` labels); the limits note shows each checkpoint value beside its `ESTIMATE` (LB-3); every Part C state (empty, partial, `not recorded`); the MDE band and bars at 3:1 or more against the panel (Part C); the header carries both run ids and plan hashes and the scope line; the ratio is labelled "token ratio of totals (pack-on / pack-off)" with one line naming the pack-improvement median; the section adds at most 30 kB | Agy |
| **L-SUM-C** the CLI, end to end | `src/harness_bench/cli.py` (`report --pool`, `--prereg`; it calls L-MATRIX's pooling check and `lean.build`); `_run_wall_clock` in `report/html.py` rewired to `views.run_wall_ns`, byte-identical (ownership of `html.py` passes from L-SUM-B1 at J1); `tests/test_lean_report_e2e.py`; `tests/mutations/lean_cli.json`; the moved finds in `tests/mutations/report.json` and `tests/mutations/cli.json` | L-MATRIX, L-SUM-A and L-SUM-B1 joined | T1 | 0 | 60 · floor + 50k · 1 · 0.8 h | red first: `bench report <b2> --pool <b1>` on two fixture lean runs is refused today (unknown flag). Green: it renders `2 of 2` with pooled rows; a lean run alone renders `1 of 2` and MDE 0.42; a non-lean run with `--pool` is refused; the pooling check's refusals reach the CLI with their codes (HB-PLN-003, HB-STA-002); `--prereg` sets the status both ways; B1's non-lean golden stays byte-equal after the rewire; any test launch of `bench` carries the console flag | Agy, or Grok if the Agy slot is busy (the Leader's choice at dispatch, recorded) |
| **L-FIX-TEXTIO** the portable-text-io regression | `tools/window_check.py`, `tools/spikes/s_j4_baseline.py`, `tools/load_repro.py` (joined in S1) | S1 joined | T0 | 0 | 20 · measured + 10k · 1 · 0.3 h | red: on the J0 head, `verify-portable-text-io.py` lists **5** sites (3 measured on `main`, plus `load_repro.py:1` and `:74`, measured by the gate on the flake3 tree). Green: the stdio guard from `pack-doctor.py:24-29` at the top of each printing `__main__`, and `newline="\n"` on every `write_text`; `run-verify-gates.py` **9 of 9**; each script still runs (`--help` or a dry run) | Claude Code Agent tool, Haiku (mechanical: the gate's own text is the fix) |
| **L-FIX-RF11** RF-11's surviving mutant | diagnosis first. Then the smallest change among `tests/fixtures/property/misc_apps.py` (where W3b `771b3970` added `CREATE_NO_WINDOW` to the grandchild launch, `:20-21`), `tests/test_property_real_host.py`, and `tests/test_console_windows.py` (an `ALLOWLIST` entry needs its `OWNER_FILES` and `OWNER_TRACKS` updates, `:102-105`). `src/harness_bench/grade/bench_check.py` only through a seam to the Leader | epoch 20 | T1 | 0 | 50 · measured + 50k · 1 · 1 h | the diagnosis is written first and checked by a run with the mutant applied (Inferred: the grandchild's `CREATE_NO_WINDOW` removed the console the test needs). `uv run python tools/mutate_check.py tests/mutations/bench_check.json` reports RF-11 **killed**; `tests/test_console_windows.py` is green; **RF-11 is unchanged** (`git diff --exit-code tests/mutations/bench_check.json`). M14b and M27 (`atomic.json`) are read at S4's `--touched`, not here | Claude Code Agent tool, Opus (judgement: weakening the mutant is the failure mode) |
| **L-DOCS** errata and the pre-registration | dated errata beside the text in `docs/specs/lean-pack-benchmark.md` (LB-1: two 60-cell plans; the NFR Compatibility row: ring tag `lean`); `docs/specs/enterprise-evaluation.md`, `docs/architecture-evaluation-campaign.md` and `docs/coordination/coordination-finish.md` (spine 8, *E5 sizing*, the operator stops), following the spec's supersession table; `docs/plans/strategy-lean-benchmark.md` §4 (the Haiku pin becomes latest); **`docs/notes/lean-preregistration.md`** (LB-2: the question, `property_check_pass`, pack-off vs pack-on, the pair, the exclusion rule, MDE 0.31 and 0.19); the HTML view of each | epoch 20 | T1 | 0 | 40 · measured + 40k · 1 · 0.7 h, then the Coordinator's review and commit | every erratum is dated, sits beside the text it corrects, and cites ADR-0022 or ADR-0023. The pre-registration names all six LB-2 items: a Haiku check against the list, then the Coordinator's read. `render-markdown.py` refreshes every touched view (V19); `docs-graph.py validate` exits 0. **On `origin/main` before batch 1's first cell** (it lands in J1) | Claude Code Agent tool: Haiku drafts; a Coordinator (Opus) reviews and commits |
| **L-READY** readiness on the gated head | `bench/discrimination/NG1/**`, `bench/discrimination/S2/**` (create-once records) | S4 gated and pushed | T0 | 0 | 10 · - · 1 · 0.7 h (Inferred; no judge call) | ADR-0022 §6 (amended), quoted: *"each trial discriminates, and `bench validate` then lists HB-RDY-002 only, for the eight unrefreshed tasks, and no other problem line."* The records are committed and pushed. That sha runs both batches | Leader (machine time, in the integration tree) |

### Track assignment detail

| track | sessions · branches | why this harness and model | why it earns the multiplier | expected seam requests | deadline · termination · fallback | join batch · gate ring |
| --- | --- | --- | --- | --- | --- | --- |
| L-CONTRACT | `c1-lean` · `coord/lean-c1-contract` | a fixed interface every summary track compiles against: a Coordinator's job | **independence**: without it, A's and B1's results change each other's shape (GO5 b) | none | 0.5 h · ends at the pushed commit · the Leader writes it | J0 (alone, before wave 1) · none |
| L-MATRIX | `lmatrix-lean` · `build/lean-l-matrix` | a matrix file, a tuple entry, a refusal and a precondition extraction: two short Grok turns | **independence** (config, campaign and board are its alone) | none | 2 × 2,400 s, R-103 kill and one retry · each ends at a green commit · Opus sub-agent | J1 · none (below) |
| L-SUM-A | `lsuma-lean` · `build/lean-l-sum-a` | pure, test-heavy statistics: Grok's profile in the finish run (X-PROP, X-GSM) | **independence** at the contract | a contract field → the Coordinator rules; A writes it, additively | 2 × 3,300 s · each ends at a commit · Opus sub-agent | J1 |
| L-SUM-B1 | `lsumb1-lean` · `build/lean-l-sum-b1` | a bounded report surface with goldens: Agy's profile (X-WIN's sweep) | **independence** at the contract | an `html.py` slot question → the Coordinator | 2 × 3,300 s · each ends at a commit · Opus sub-agent | J1 |
| L-SUM-C | `lsumc-lean` · `build/lean-l-sum-c` | the integration seam, after its three inputs | **context hygiene**: a fresh context on joined code | none expected | 3,300 s · ends at a green commit · Opus sub-agent | J2 |
| L-FIX-TEXTIO | Agent tool, `isolation: worktree` · `build/lean-fix-textio` | three edits the gate prints: Haiku | **context hygiene** | none | 0.3 h · ends at 9 of 9 · the Leader | J1 |
| L-FIX-RF11 | Agent tool, `isolation: worktree` · `build/lean-fix-rf11` | the shortcut that "fixes" the survivor is weakening the mutant, so judgement is the work: Opus | **context hygiene** and **isolation** (it applies a mutant) | `bench_check.py` → the Leader | 1 h · ends at RF-11 killed, or a written diagnosis with no safe fix → the operator | J1 |
| L-DOCS | Agent tool, `isolation: worktree` · `build/lean-docs` | prose errata against a supersession table: Haiku drafts, an Opus Coordinator reviews | **independence** (docs only) | none | 0.7 h · ends at the Coordinator's commit · the Coordinator writes it | J1 |
| L-READY | the Leader · `integrate/lean-20` | machine time on the gated head | **machine time** | none | 0.7 h · a failed trial → the operator | after S4 |

**Gate ring:** none for any row. The stamp inputs are `src/harness_bench/grade/**`, `tasks/D1`,
`bench/metrics.yaml` and `bench/regrade-baseline-0.3.yaml` (`tools/gate_stamp.py:4-9`), and no lean track touches
them. The ring runs once only if L-FIX-RF11's seam opens `grade/bench_check.py`. **The stamped tier does run at
S4**, because `stats.py` is a stamped-tier input (`tools/gate_stamp.py:34`), and S4 renews `stamped-stamp.yaml`.

**Harness capability, as verified here:**
- **Claude Agent tool:** edit boundary `enforced` (spike S5, `coord doctor`).
- **Grok and Agy through `coord-runner`:** `observed-only`. The re-read hooks are installed (`pack-doctor`), and no
  edit-boundary spike exists for either. The commit floor enforces.
- **Doorbells:** not recorded for any harness.
- **Codex, Sonnet and Copilot:** not workers in this run (the prompt; operator 2026-10-09).

## Serial spine

| item | why it cannot be parallel | who owns it |
| --- | --- | --- |
| S0. Pin epoch 20 (`coord leader pin`, renewed in a loop). End the three stale `leader-fin-*` sessions and remove their trees. Create `integrate/lean-20`. Re-check "latest" for the cell pins (Opus, Sol), and ask the operator before changing one | every row carries the epoch, and a stale session's hold blocks cleanup (WT) | Leader |
| S1. J-CARRY: join X-ALARMCWD (`build/fin-x-alarmcwd` `8a87de4d`), then X-FLAKE (`build/fin-x-flake3` `e79489ba`, plus the turn-1 and turn-2 audit commits on `build/fin-x-flake2` `1e19ef24`, which contains `dc1aee54`), each after a full-suite pre-check on its branch | two `src/`/`tests/` joins into one integration tree: the recount of one is the base of the next (GO5 c) | Leader |
| S2. L-CONTRACT joined and pushed (J0) | until `LeanSummary` exists in code, A's and B1's results change each other's shape (GO5 b) | Coordinator #1, then the Leader's join |
| S3. J2 (L-SUM-C) after J1 | L-SUM-C reads all three inputs (data edges) | Leader |
| S4. The batch gate, then push: the full suite; `run-verify-gates.py` 9 of 9; `mutate_check --touched <J0 base>` (it includes `campaign.json`'s 176 mutants, and M14b and M27 must read `host-limited`); the **stamped tier** and the renewal of `stamped-stamp.yaml`; ruff; `docs-graph validate` | one gated sha is the engine identity of both batches (ADR-0022 §5) | Leader |
| S5. L-READY on the gated head; its records committed and pushed | readiness is checked against the engine that runs (ADR-0022 §6) | Leader |
| S6. The operator approves about 127M tokens (Inferred), asked once. Batch 1: `bench plan --confirm`, then `bench run`, which grades at its end. Then the checkpoint. **LB-3's rules, quoted:** *"Given batch 1's projected batch-2 run time exceeds 2 h, or its tokens exceed the approved budget's half When the checkpoint is read Then batch 2 does not start without P1's explicit go."* *"Given a harness whose batch-1 cells failed for an infrastructure cause (auth, rate limit) on more than 20% of its cells When the checkpoint is read Then it is named, with the cause, before batch 2."* | batch 2's go depends on batch 1's measured numbers | Leader; operator |
| S7. Batch 2 from the same matrix at the same sha. Its commit and `identity_hash` are recorded and compared with batch 1's; unequal is a stop | the checkpoint gates it; one tree, unedited between batches | Leader |
| S8. `bench report <b2> --pool <b1> --prereg docs/notes/lean-preregistration.md`; the run report (md + html), with Opus's analysis; push. **Exit evidence, LB-8's seven items:** the per-harness and pooled results; both MDEs and the clustering caveat (0.31 to 0.42); the checkpoint numbers; total tokens per harness and arm; the engine identity; the pack revision (`e1f8ad5e`); whether the result was pre-registered | it reads both batches | Leader; Opus sub-agent (analysis) |

**Critical path (Inferred; re-estimated at the gate):**

| step | duration (Inferred) | notes |
| --- | --- | --- |
| S0 | 0.2 h | |
| S1 ∥ S2 | 0.9 h | two full-suite pre-checks; one full suite measured 1,036 s for 1,766 tests, and the suite is now about 4.2k tests |
| wave 1 | 2.2 h | L-SUM-A and L-SUM-B1 are the long poles |
| J1 | 1.8 h | four `src/`/`tests/` pre-checks at about 25 min each (Inferred) |
| L-SUM-C | 0.8 h | |
| J2 + S4 | 1.5 h | the full suite, the stamped tier, and `--touched` mutation including `campaign.json`'s 176 |
| S5 | 0.7 h | |
| S6 | operator, then 2.3 h for batch 1 | |
| checkpoint | 0.25 h | |
| S7 | 2.3 h | |
| S8 | 0.8 h | |
| **total** | **about 13.8 h** | about 4.9 h is the run itself |

## Seams

| from -> to | the request | resolved by |
| --- | --- | --- |
| L-SUM-A -> Coordinator | the contract needs a field | the Coordinator rules; **A writes it, additively only**; B1 consumes it at L-SUM-C (no mid-wave edge into B1) |
| L-SUM-B1 -> Coordinator | the campaign slot's insertion point (`report/html.py:2259-2266`) does not fit | the Coordinator rules; L-SUM-C inherits the answer |
| L-FIX-RF11 -> Leader | the fix needs `src/harness_bench/grade/bench_check.py` | the Leader grants a bounded edit (the gate ring then runs once at S4), or sends it to the operator if RF-11 would weaken |
| L-DOCS -> L-SUM-C | the pre-registration path | fixed here: `docs/notes/lean-preregistration.md` |
| any track -> Coordinator | a new defect class | handed back as text; the Coordinator writes the register |
| any track -> `owner-fable` | a product or scope question | `coord decide request --to owner-fable`; ruled into `docs/notes/rulings.md` |

**Shared guards, shown jointly satisfiable (GO14a):**
- **The console-window guard** (`tests/test_console_windows.py`):
  - root `tools/` and `tests/` (`ROOTS`, `:14`), recursive;
  - tokens: `subprocess.run|Popen|call|check_call|check_output` without a `creationflags` keyword (`:16`), plus
    `os.system` (`:17`, `:111-118`);
  - allowlist: the per-file `ALLOWLIST` (`:37`), with `OWNER_FILES` and `OWNER_TRACKS` (`:102-105`);
  - owner: L-FIX-RF11. The guard checks only that the keyword is present (`:87`). Every other track that adds a
    launch under `tools/` or `tests/` passes `creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)` and uses no
    `os.system`, so it needs no allowlist entry. Only L-SUM-C's e2e test is expected to add one.
- **The portable-text-io gate** (`verify-portable-text-io.py`):
  - root `pack/scripts`, `pack/adapters/hooks` and `tools` (`:52`);
  - rules: printing `__main__` modules need `.reconfigure(`, and text writes need `newline="\n"`;
  - owner: L-FIX-TEXTIO owns all five hits. No other track adds a script under `tools/`; one that does carries the
    guard.
- **`test_identity.py`** (every `src/harness_bench` file classed, `:103-106`): L-CONTRACT adds `lean.py`, and
  L-SUM-B1 adds `report/lean_section.py`. They are sequential (J0, then wave 1), and no other track adds a `src/`
  file.
- **`test_arms_guard.py`** (`"on"`/`"off"` literals pinned per file, `:26`, `:96-97`): no track adds such a literal,
  because arm ids come from `plan.comparisons` and `config.ARM_OFF`. So its pins hold without an owner.
- **MUT-E** (`test_mutate_check.py:413`): each track retargets the finds its edit moves:
  - L-MATRIX: `board.json`, `campaign.json`;
  - L-SUM-A: `views.json`, `stats.json`;
  - L-SUM-B1: `report.json` (B1's hunks);
  - L-SUM-C: `report.json` (the `_run_wall_clock` call site, `:139`), `cli.json`.
  `report.json` has two owners in sequence, never concurrently.
- **The report goldens:** L-SUM-B1 adds the non-lean golden before it touches `html.py`. L-SUM-C asserts against it
  and edits none.
- **`report/html.py`:** owned by L-SUM-B1 until J1, then by L-SUM-C. Sequential.

## Struck tracks

| track | why it was not worth its multiplier |
| --- | --- |
| L-RECORDS (refresh the ten readiness records) | ADR-0022 §6: the lean path does not need them. L-READY's two trials on the gated head cover the base trees that changed |
| one L-SUMMARY track | about one floor cheaper, but about 5 h serial, and its turns would split on the floor anyway (CEIL-A). The split at a fixed contract buys genuine independence |
| a separate pre-registration formatting track | folded into L-DOCS: a Haiku check against six named items, in the same dispatch |
| a separate `--campaign` refusal track | folded into L-MATRIX. Its cost is recorded: it pulls `campaign.json`'s 176 mutants into S4 |
| X-FLAKE turn 4 | none needed: turn 3 is green (`e79489ba`, 0 of 3 failed at N=3). It joins in S1 |

## Order of operations

| # | action | cost | why now |
| --- | --- | --- | --- |
| 1 | S0 | 0.2 h | every row carries the epoch |
| 2 | Coordinator #1 (Opus): write L-CONTRACT; compile the six wave-1 briefs (compiled mode, replayed through the runner's check; TEST-E: each proof command run once by its author) | 0.7 h, in parallel with step 3 | until the contract lands, the summary halves are not independent |
| 3 | S1: J-CARRY | 0.9 h, in parallel with step 2 | it clears the carry-over, and L-FIX-TEXTIO's red includes `load_repro.py` |
| 4 | J0: join L-CONTRACT; push; fast-forward the primary | 0.1 h | the wave-1 base |
| 5 | Wave 1, at the cap of 6 (Grok ≤ 2, Agy ≤ 2): L-MATRIX (Grok), L-SUM-A (Grok), L-SUM-B1 (Agy), L-FIX-TEXTIO (Haiku), L-FIX-RF11 (Opus), L-DOCS (Haiku, then a Coordinator). The health check runs at every dispatch | 2.2 h | the parallel half |
| 6 | J1: join each returning track after its full-suite pre-check and the join recount (one `--continue` retry, then a loop-back fix track on Opus); push | 1.8 h | the pre-registration and the fixes land |
| 7 | L-SUM-C | 0.8 h | after its three inputs |
| 8 | J2; S4, the batch gate; push | 1.5 h | one gated sha |
| 9 | S5: L-READY; commit and push its records | 0.7 h | readiness against the engine that runs |
| 10 | **Operator:** approve about 127M tokens (Inferred), asked once | operator | before any cell |
| 11 | S6 batch 1 → checkpoint → S7 batch 2 | about 4.9 h | the run |
| 12 | S8: the report and the run report; push | 0.8 h | the answer |
| 13 | Close: `coord worktree cleanup` (report, then `--remove` on the operator's go); the closing audit entries; the scratch roots (`C:\tf\<track>`) listed for deletion | 0.2 h | WT cleanup |

**Operator actions and their timing:**
- **Token approval** at step 10.
- **Worktree removal** at step 13.
- **A failed L-READY trial**, if any.
- **A newer Opus or Sol id** at step 1, if one is served.
- Already done: the pack-on revision (F-PACK pushed, `e1f8ad5e`) and the drill task's deletion (operator, 2026-10-09).

## Status

| | |
| --- | --- |
| **Completed** | the plan: 9 tracks (2 waves plus Leader machine time), the serial spine, the seams and their guards, 5 struck tracks; the gate run and its findings resolved |
| **Remaining** | `/execute-with-coordination` steps 1-13 |
| **Best next action** | step 1 (S0), with Coordinator #1 on L-CONTRACT |

## Errata (Coordinator #64, 2026-10-09)

*Applied by Coordinator #64 (Claude Code, `claude-opus-5-5`, session `c64-lean`) on `coord/lean-c64` at `47721f98`,
from the Leader's owed-docs list for J1. The rows above are not rewritten. Each erratum names the text it corrects and
its source. Register entries for the same run are in `docs/lessons/defect-classes.md`, *Coordinator #64 entries*.*

1. **Coordinator #62's nine proposals** (source: `docs/coordination/coordinator-log/c62.md`, *Errata proposals* and
   *TEST-E observations*, measured at `7ad2d5ff` + `c878d32d`):
   - **L-MATRIX's red 1 and plan proof** (Tracks row): `bench plan bench/rings/lean.yaml` exits 2 (`unrecognized
     arguments`). The form is `bench plan --matrix bench/rings/lean.yaml --arm on=...`, with `--tools-dir`, `--runs`
     and `--cells-root` before `plan`. Red 1 is `lean.yaml` committed with tag `lean` before the `RING_TAGS` entry.
   - **"every `off` cell with 0 instruction files"** (the same row): `bench plan` prints no per-cell instruction
     counts. They are read from a `--confirm`ed plan.json's `instruction_lists`, in the worker's scratch.
   - **L-FIX-TEXTIO's guard citation** (Tracks row, gate record): the stdio guard is `pack-doctor.py:25-30`, not
     `:24-29`.
   - **L-FIX-TEXTIO's "each script still runs (`--help` or a dry run)"**: `tools/spikes/s_j4_baseline.py` has no
     argument parser, and running it launches three ACP adapters with model calls. It is checked with
     `python -m py_compile`; the other two scripts with `--help`.
   - **L-CONTRACT's session and branch** (detail row): it ran as `c62-lean` on `coord/lean-c62`, not `c1-lean` on
     `coord/lean-c1-contract`. It joined by merge `bd9beb8f` (join entry `al-01M4HA3KXEEDQRB1DB5W2F6EQR`).
   - **`campaign.json`'s mutant count** (S4, the critical path, *Struck tracks*, the gate record): **191** at
     `7ad2d5ff` (the JSON list's length), not 176.
   - **The Agent-tool rows' sessions** (detail rows): `lfixtextio-lean`, `lfixrf11-lean` and `ldocs-lean`.
   - **A contract field change** (Seams, row 1; L-SUM-A's row): an additive field also moves
     `tests/test_lean_contract.py`'s pin, which is L-CONTRACT's file. L-SUM-A updates that pin under the
     Coordinator's ruling only.
   - **L-DOCS's "the HTML view of each"** (Tracks row): `docs/specs/enterprise-evaluation.md` and
     `docs/architecture-evaluation-campaign.md` had no view. L-DOCS created both, plus the new
     `docs/notes/lean-preregistration.html` (merge `415bc4cc`, checked by `git show --stat`).
2. **The Agent-tool tracks' trees** (detail rows L-FIX-TEXTIO, L-FIX-RF11, L-DOCS; Order step 5): they ran in
   Leader-made coord trees on named branches (`build/lean-fix-textio`, `build/lean-fix-rf11`, `build/lean-docs`), not
   in the Agent tool's `isolation: worktree`. Source: the Leader's owed-docs list, item 2; the three branches exist
   (`git branch --list '*lean*'`).
3. **L-FIX-RF11's guard list** (a brief error in Coordinator #62's compile): it named `tests/test_lean_contract.py`,
   which is absent at the track's base `7ad2d5ff` (`git cat-file -e 7ad2d5ff:tests/test_lean_contract.py` exit 128,
   run by Coordinator #64). Source: the L-FIX-RF11 hand-back (`build/lean-fix-rf11`, `ffca855d`).
4. **L-FIX-TEXTIO's red** (Tracks row; *Layer state* row `run-verify-gates.py`): the red was **5**
   `verify-portable-text-io` sites **plus 2** `verify-subprocess-utf8` sites (`tools/load_repro.py:56`, `:66`). The
   second gate failed only once S1 joined `load_repro.py`, so "9 of 9" was unreachable from the stated red. Fixed by
   `77d43d78`. Source: the L-FIX-TEXTIO hand-back. The class is in the register (RED-ONE-GATE-A).
5. **Measured floors** (*Common to every row*: "Grok 88k, Agy about 105k"): this run measured, at the first edit,
   for briefs of about 75 kB: **Grok 117k** (L-MATRIX turn 1: 102,821 before M1, 116,990 at the first edit; split
   before M1, `8d75b5a3`), **Agy 166k** (L-SUM-B1 turn 1: 166,041 at the first edit, 191,659 after B0 `7d134d4a`;
   split after B0, `e62dc830`), **Opus Coordinator 137k** (c62.md: 137,174), **Haiku about 99k** and **Opus worker
   about 109k** (the Leader's measurements). A floor scales with the brief's size, so a fixed per-harness floor is
   wrong. Both splits took the plan's fallback (Opus sub-agent: `lmatrix2-lean` on `build/lean-l-matrix2`,
   `lsumb12-lean` on `build/lean-l-sum-b1-2`). Source: the Leader's owed-docs list, items 10-11; CEIL-A.
6. **Planned vs actual: J1's pre-check** (rule 2; Order step 6, "each returning track after its full-suite
   pre-check"): the Leader replaced the per-branch pre-checks with **one** full suite on a combined candidate (the J0
   head plus every returned branch, a superset of each branch), then one recount per join. A Leader deviation.
   Source: the Leader's owed-docs list, item 14; the J1 batch `batch/lean-j1` (`432c48df`), merged as `4c826f58` on
   `integrate/lean-20`.
7. **L-SUM-C's contract from L-MATRIX** (L-SUM-C's row: "it calls L-MATRIX's pooling check"):
   `board.pool_check(pool: RunView, view: RunView) -> tuple[str, ...]`, where `pool` is batch 1. It raises
   HB-PLN-003 (ring hash) or HB-STA-002 (every other precondition, named), and returns the shown-not-refused
   differences (`parameters`, `envelope_seconds`). `board.check_comparable(base, view, extra=())` is `compare`'s
   extracted precondition. Both signatures read at `build/lean-l-matrix2` (`board.py:729`, `:812`). Source: L-MATRIX
   turn 2's closing entry `al-01M4H974B08QX8SH1PY4AKC8WN` (`b2a9d39f`).
8. **Planned vs actual: L-SUM-B1's B4** (Common exit evidence: "red first, on an assertion"): B4 had no red; B1-B3
   already satisfied it. B5's mutants falsified it instead (`tests/mutations/lean_section.json`, 25 mutants, every one
   killed, `1d033470`). A RED-C deviation, accepted by the Leader. Source: L-SUM-B1 turn 2's closing entry
   `al-01M4H991Q8TMFW2GHYG2ZGPP04` (`e9234a4b`).

## Gate record

*Adversary gate, 2026-10-09: an Opus sub-agent with the Simplifier, Test Architect and Tech Lead lenses, reading the
code at `954b9e9d` and running `bench validate` and `verify-portable-text-io.py`. The author re-ran `bench validate`
(exit 1: 9 × HB-RDY-002, 1 × HB-RDY-001) before accepting the readiness findings.*

| lens | finding | resolution |
| --- | --- | --- |
| Test Architect | **VETO 1:** L-MATRIX's red was false. `bench validate` does not read rings, and `--campaign` with `lean` does not succeed today | new reds: `bench plan` INVALID with `config.validate_matrix`'s message; `plan_block` asserts HB-CMP-010. ADR-0022's claim amended |
| Test Architect | **VETO 2:** no report golden exists, so "goldens byte-identical" could not fail | B1 captures a non-lean report golden in its first commit, before touching `html.py`; B1 and C assert against it |
| Test Architect | **VETO 3:** `bench validate` exit 0 is unreachable, and the trials write records | L-READY moved to the gated head; pass = HB-RDY-002 only for the eight unrefreshed tasks; records committed. ADR-0022 §6 amended |
| Test Architect | L-FIX-RF11 owned the wrong file; M14b and M27 are not in `bench_check.json` | `misc_apps.py` owned; "exactly one of" dropped; M14b and M27 read at S4 |
| Test Architect | L-FIX-TEXTIO's scope excluded `load_repro.py` (5 sites at its base) | owned; red is 5 sites; the guard cited as `pack-doctor.py:24-29` |
| Test Architect | L-SUM-C's codes (HB-PLN-003 for ring hash) and a paraphrased drift list | ADR-0022 §3 quoted in L-MATRIX's row; codes as `compare`; ADR amended |
| Test Architect | spec items unowned: LB-3 estimates and stop rules, LB-8, LB-1's unbound refusal, LB-5's note text, LB-7's count, Part C contrast | `ESTIMATE` in the contract; LB-3 quoted in S6; LB-8 in S8; the rest placed in L-MATRIX and B1 |
| Test Architect | L-CONTRACT's evidence was weak | `tests/test_lean_contract.py` pins fields and estimates |
| Tech Lead | `test_identity.py` and `test_arms_guard.py` were unowned guards | identity entries owned (L-CONTRACT, B1); no new arm literals (common rule); both in *Shared guards* |
| Tech Lead | moved mutation finds had no owner (MUT-E) | a common exit item, with owners per file |
| Tech Lead | multi-writer files (the contract mid-wave; the defect register) | additive-only contract changes by A; register written by the Coordinator only |
| Tech Lead | the critical path was understated; the stamped tier was missing | re-estimated at about 13.8 h; the stamped tier named in S4 |
| Tech Lead | no HTML twin, no multiplier statement, budget token semantics, `os.system` missing | all four added |
| Simplifier | move the board extraction and the pooling check off L-SUM-C into wave 1 | adopted: L-MATRIX owns them; L-SUM-C shrinks to CLI wiring, the rewire and the e2e test |
| Simplifier | the `campaign.py` refusal costs 176 mutants at S4 | kept (ADR-0022 §3a); the cost is recorded |
| Simplifier | fold L-FIX-TEXTIO into L-FIX-RF11 | declined: the prompt makes each fix its own small track, and Haiku is cheaper than Opus for it |

**Verdicts:**
- Test Architect: the veto is cleared by change, not by argument. Every veto item has new exit evidence that can
  fail for its stated reason.
- Simplifier: pass.
- Tech Lead (casting vote on count): keep 9 tracks.
