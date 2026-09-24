---
id: "rulings-register"
title: "Owner rulings"
type: decision-note
status: accepted
owner: "@timianmalloo"
phase: "Phase 1 · walking skeleton"
tags: [rulings, register, coordination]
links:
  - { to: coordination-phase1-finish, rel: relates-to }
review-by: "2027-03-22"
summary: >-
  The append-only register of Owner rulings (class `register`, union-merged). Each entry records the ruling verbatim
  or its chosen option, who ruled, when, and what it decided.
---

# Owner rulings

Append only. One entry per ruling. Newest last.

## R-1 · 2026-09-24 · Owner (Tim Mallalieu) · sub-agent harnesses and seats

> "use grok, and agy for sub agent tasks · use the Owner (fable), Coordinator (opus 5.5), Sub.Agent (right model for the right job and delegate to instances of grok and agy)"

- **Decides:** the sub-agents of `coordination-phase1-finish` run on grok and agy; the Owner seat is Fable, and the Coordinator seat is Opus 5.5.
- **Recorded dissent** (Tech Lead, Simplifier): run the critical-path track on Claude Code, the only harness whose edit boundary is qualified here.
- **Resolution:** the plan keeps R-1 and moves a track to Claude Code only if its harness fails qualification or the track stalls.
- **Also ruled (same message):** grok runs on the Owner's subscription, not an API key. Every grok worker is launched with `XAI_API_KEY` removed; checked: "You are logged in with grok.com".

## R-2 · 2026-09-24 · Owner seat (Fable) · `grading.completed` carries its heads

- **Ruling:** (a) yes, as stated. `verify` checks each segment's own chain and seal, but nothing ties a later `bench grade` pass's scores segment to its `grading.completed`. So a scores segment that was cut and re-sealed, or deleted, is invisible. The runner already computes `heads` for its facts and discards them; recording them is the minimal mechanism.
- **Conditions:**
  - `heads` excludes `events`, since a segment cannot carry its own head.
  - A `grading.completed` without `heads` (the `c44dd2b` golden fixture) verifies with a warning, never an error.
  - A missing or mismatched head is exit 5.

## R-3 · 2026-09-24 · Owner seat (Fable) · `bench-status/1` gains `stop_code` and a `phase`

- **Ruling:** (a) yes, and the schema stays `bench-status/1`. The producer (`status.py`) and the only consumer (`skills/start-benchmark/SKILL.md`) live in this repo and move in one change, and nothing stores a status document.
- **Conditions:**
  - `stop_code` is null unless `run.launch_stopped` was recorded.
  - `phase` is a closed enum (`starting`, `running`).
  - The skill's field list and reading rules update in the same commit.
  - If a status document is ever stored or consumed outside the repo, that change bumps the schema to `/2`.

## R-4 · 2026-09-24 · Owner seat (Fable) · sub-agents fall back to Claude Code

- **Ruling:** (a) apply R-1's recorded fallback now, for every track. Both qualification failures were measured on this host (run `qualify-1`):
  - grok 1.0.30: ACP `protocol_error` on the first prompt, 0 turns. The runner's compatibility path targets grok 1.0.34.
  - agy 1.2.3: a native permission denial on the first turn in `accept-edits` mode, 0 turns.

  Option (b), upgrading grok, would alter the operator's machine unattended; option (c), waiting, forfeits the deadline.
- **Conditions:**
  - The Coordinator records each move with the measured evidence.
  - Nobody widens agy's permission mode or upgrades grok while the human is offline. Both are listed as next steps for the human, and R-1 stands for re-qualification when they return.

## R-5 · 2026-09-24 · Owner seat (Fable) · N5: disclose, flag and keep the strict xfail

- **Ruling:** (a) keep `xfail(strict)`, record the contamination in the Proof Pack, and flag Codex cells `user-config exposed (N5)`.
- **Reasoning:** three independent attempts fail identically:
  - a per-cell `USERPROFILE`/`HOME`;
  - Codex's `skip_host_skill_discovery` flag;
  - a third party's four-flag set on 0.154.

  So a fourth guess is not evidence. The leak is one skill and is identical for pack on and off, so pack comparisons stay valid, and only Codex-against-Claude harness comparisons carry a disclosed confound.
- **Conditions:**
  1. The flag appears in the report header of every run with a Codex cell, and on each Codex row or cell in the harness-comparison view. The leaked skill (`microsoft-foundry`) is named as the evidence.
  2. The `xfail` reason cites `docs/notes/spike-n5-codex-skill-roots.md`.
  3. N5 reopens on any of these:
     - the Windows known-folder probe (the note's "cheapest next probe") lands;
     - Codex's version changes;
     - a second leaked item appears in the canary;
     - the strict xfail goes green (a fix to verify).
  4. No ADR-0013 amendment.
- **Coordinator's implementation note:** the report names the spike note and the canary as the evidence. The leaked skill's name, which is specific to this operator's profile, is recorded in the Proof Pack rather than hard-coded in the report source.

## R-6 · 2026-09-24 · Owner seat (Fable) · R-5 re-review: N4 (pack-on/off claim) and N5 (skill name)

- **Ruling:**
  - **N4: amend R-5's reasoning by reference.** The sentence "the leak is identical for pack on and off, so pack comparisons stay valid" is **Inferred**, not Verified. It must not be stated as fact anywhere. The pack-seeded probe is a **named, dated next step, not a merge gate**.
  - **N5: accept the Coordinator's implementation** of condition 1.
- **Reasoning:**
  - **N4:**
    - The canary's probe is always a bare cell (`test_us13_canary.py:59-60`: `seed_home` and an empty pack argument), so pack-on was never measured.
    - The inference rests on a mechanism: the leak is `~/.agents/skills`, resolved from the operator's `USERPROFILE`, a path the pack does not touch. That is a model. The `<recommended_plugins>` block seen only in the pack-on Codex context is one observed difference between the two contexts, and its source is unverified.
    - So the claim keeps its model, gains its label, and names the probe that would confirm or break it.
    - The merge is not blocked. The report already flags every Codex cell, pack on or off, so no unflagged comparison reaches a reader. The probe is one extra canary turn, and the benchmark is wanted today.
  - **N5:**
    - The report is an operator-independent surface. An operator's skill name belongs in the run's proof record, not in source.
    - `report/__init__.py` names the note and the canary, and `docs/proof/phase1.md` Claim 5 names `microsoft-foundry`. That satisfies condition 1's intent: the evidence is findable from the flag.
    - One gap: the canary prints leaked *classes* only (`sorted(leaked.values())`). The name in the Proof Pack was transcribed by hand from a pytest introspection line; the measurement did not emit it (IO: emitted on the normal path).
- **Conditions:**
  1. Before merge, `docs/proof/phase1.md` Claim 5 splits its confidence:
     - the leak's existence is **Verified**;
     - pack-invariance is **Inferred**. The model: the leak path is profile-resolved and pack-independent. The probe: run the US-13 canary with the pack seeded into the probe cell, pack on and pack off, and compare the leaked sets;
     - `<recommended_plugins>` is **Flagged** (source unverified, seen pack-on only).

     Any other surface that repeats the pack-invariance claim carries the same label.
  2. The pack-seeded probe joins the human's list beside "N5 review (2)". **R-5 reopens** if either of these happens (add both to R-5 condition 3 by reference):
     - a pack-on leaked set differs from the pack-off set;
     - `<recommended_plugins>` turns out to have a pack-dependent source.
  3. The canary's `Leaked` message and its printed summary name the leaked items (the canary keys), not only their classes. Then the Proof Pack's skill name is copied from a measurement.
  4. R-5 condition 1 is read as: the flag names where the evidence is (the note and the canary), and the run's Proof Pack names the observed item. No skill name goes in report source.

## R-7 · 2026-09-24 · Owner seat (Fable) · DR-1: task sources for rows 7 and 21

- **Ruling:** per source, checked from this host on 2026-09-24 (`git ls-remote`, local clones, the upstream README or paper):

  | Source | Tasks | Ruling | Evidence |
  | --- | --- | --- | --- |
  | ClarifyCodeBench | A1, A2, A3 | **reachable as is** | `github.com/fangz-cs/ClarifyCodeBench` `main` `5e2d5b5`; the data is in-repo (`data/ClarifyCodeBench.jsonl`, 419 tasks); code and annotations MIT; problems and tests under LiveCodeBench's licence. |
  | cfd-bench | A4, B1, D3, E7, F1 | **reachable as is** (operator-authored, local clones) | `C:\projects\cfd-bench` `496a0a8`, clean, docs and tools only (no `src/`); the C# solutions are `C:\projects\CFD-Bench-ClaudeCode` `66afa11` and `C:\projects\CFD-Bench-GHCP` `2ffd1c8`, both clean. |
  | ai-de | A5, B2, D1, D2, F2 | **reachable as is** (operator-authored, local clone) | `C:\projects\ai-de` `88e0c33f`, 2 uncommitted paths; .NET SDK 10.0.303 on the host. |
  | SpecBench | B3 | **operator-authored substitute** | The paper's only URL, `github.com/kevins981/SpecBench`, returns "Repository not found" (exit 128). |
  | ProjDevBench | C1 | **reachable as is for the prompt; the grader is ours** | `github.com/zsworld6/projdevbench` `main` `9af6f40`, MIT, problems in-repo. Grading needs an account and API token on the external judge ACMOJ (`acm.sjtu.edu.cn/OnlineJudge`, HTTP 200); no local test runner. |
  | ArchBench | C2 | **operator-authored substitute** | CLI `github.com/sa4s-serc/archbench-cli` `main` `be4f389` and web `github.com/sa4s-serc/archbench` are reachable, but the platform ships five tasks (ADR generation, serverless component, dynamic service, traceability link recovery, microservice generation) and **no requirement-to-architecture task** (paper 2603.17833, "not yet implemented"); its inference stage calls provider APIs with keys. |
  | Terminal-Bench 2.0 | E1, E2, E3 | **reachable as is, gated by row 9** (spike A6) | `github.com/harbor-framework/terminal-bench-2` and `github.com/laude-institute/harbor` reachable; Docker Desktop installed and its engine running (29.8.0, linux, 24 CPUs, 18.9 GB); `docker` is not on the shells' PATH and `harbor` is not pip-installed. |
  | SWE-bench Verified | E4, E5 | **reachable as is, gated by row 9** | `github.com/SWE-bench/SWE-bench` reachable; the task.yaml source is the Harbor dataset, so the same gate. Wave 5 only. |
  | MultiPL-E | E6 | **reachable as is** | `github.com/nuprl/MultiPL-E` `main` `3025a53`; runs natively on the host's .NET SDK. |

  Nothing is deferred. Owner ruling 5 and ADR-0012 stand: every task above may run on the operator's subscriptions.
- **Reasoning:**
  - A substitute is ruled only where the upstream cannot supply what the BOM row needs: SpecBench has no reachable repository, and ArchBench has no task of the kind C2 names. In both, the proposal already said "borrow the grading pattern; tasks are ours" (proposal §scenarios 2 and 3), so a substitute is the proposal's own fallback, not a new design.
  - ProjDevBench's grader is an external online judge behind a third-party account. A grade that depends on a remote service breaks US-26 (grading is a pure function of the archive), ADR-0013 ("grading runs natively"), and re-grade determinism. The problem statements are MIT and in-repo, so C1 keeps the upstream requirements and gets a locally authored oracle (tests plus the architecture rubric the task.yaml already names).
  - ArchBench's inference pipeline is API-keyed, which owner decision 1 (subscriptions only) excludes; only its hybrid-grading idea (structural checks plus a judge) is reused, as the proposal intended.
  - The three Harbor-backed sources are reachable, but the engine that runs them (Docker Desktop plus Harbor) is not proven on this host. That is exactly row 9, so the ruling gates on it rather than pre-judging it.
  - The operator's own repos are used from their local clones; a bench-owned local clone at a pinned commit is the task source (ADR-0013 decision 1), so GitHub access is not needed to author or run them.
- **Conditions:**
  1. Every task pins `source.commit` to a commit that exists in the named repository. ai-de's dirty working tree is never a base: pin `88e0c33f` or a later committed revision.
  2. B3 (substitute): a scenario-2 primer-to-spec task authored from `ai-forward` (`C:\projects\ai-forward` `ca032f0`), graded with SpecBench's checklist pattern (rubric items plus verifier scripts). `bench/bom.yaml` changes `source` to `authored` and notes "SpecBench repository unreachable 2026-09-24". The URL is re-checked once before wave 5; if it becomes reachable, that is a BOM v0.3 change, never a swap inside a grid.
  3. C1: prompt and requirements from ProjDevBench at a pinned commit (MIT); the hidden tests and the architecture rubric are authored locally; ACMOJ is not used. `graders` in `tasks/C1/task.yaml` stays as listed. An ACMOJ account is **not** required; it is offered to the human as an optional later upgrade (a second, upstream-comparable score), not requested.
  4. C2 (substitute): a requirement-to-architecture task authored from ai-de or cfd-bench documents, graded by structural checks plus the judge (ArchBench's hybrid pattern). `bench/bom.yaml` changes `source` to `authored` and notes "ArchBench ships no requirement-to-architecture task (2026-09-24)". Any ArchBench dataset reused as input carries its licence check in the task folder.
  5. E1: if row 9 has not passed by the wave-2 join, E1 is **deferred** for the smoke run (not substituted; the E-tasks are the calibration baseline) and E6 takes the scenario-5 smoke slot (`smoke: true` in the BOM for that run), since it needs no container. The report names the swap.
  6. A1–A3: `/new-bench-task` verifies that the chosen tasks' LiveCodeBench tests run natively on this host before marking `ready`; the licence note goes in the task folder.
  7. The `/new-bench-task` run for each task records the ls-remote or local-clone evidence above in its audit entry, so the reachability is measured at authoring time, not inherited from this ruling.

## R-8 · 2026-09-24 · Owner seat (Fable) · DR-2: the anchor for a deleted grading pass is the committed audit log

- **Ruling:** the anchor is **a git-committed, append-only index of grading-pass heads, kept as entries in the bench repo's own audit log** (`docs/audit/audit-log.jsonl`, written only through `audit-log.py`). Every grading pass, in-run or from `bench grade`, appends one `kind: grading-pass` entry after its seal, carrying `run_id`, `grading_id`, the catalog version, and the sealed head of **every** segment it wrote, including `events`. `bench verify` reads the anchor entries for the run and fails (exit 5) when an anchored pass, or an anchored head, is missing from the ledger. This amends ADR-0006 ("Sealed segments"); the implementation goes through `/design-slice`.
- **Reasoning:**
  - Residual 7a is a tail deletion: the newest pass can be removed whole and the ledger stays internally consistent. No record inside the run can detect the loss of the run's newest record, so the anchor must be outside the run and outside the deleter's reach.
  - The three directions weighed:
    - **Chained pass-to-pass heads** (each pass records the previous passes' heads): detects deletion of any earlier pass, never of the latest one, which is the pass that gets deleted. Rejected as the sole mechanism; the anchor entry already gives the same cross-pass record.
    - **A sibling index beside `runs/`**: same filesystem, deletable in the same act, and its own tail has the same weakness. Rejected.
    - **Accept and disclose**: residual 7a says a run graded more than once is only as trustworthy as its filesystem. Phase 3 re-grades the smoke archive by design and the full grid re-grades after judge fixes, so every run of value will be graded more than once. Rejected.
    - **A git-committed index**: history the deleter does not control, pushed with the Leader's commits. The repo already has one append-only, committed, single-writer index with the Audit Mandate behind it: the audit log. Reuse-in-codebase beats a new file and a new writer (Solution-Selection Ladder).
  - What the anchor stores is a commitment (heads), never a score; the scores stay derived from the ledger (DM7, derive don't store).
  - The trade-off accepted: the anchor is as strong as its commit. Between the pass and the next commit, deletion of both is possible; `verify` reports that state instead of hiding it (condition 4).
- **Conditions:**
  1. ADR-0006 gains an "External anchor" paragraph under "Physical form and integrity", with this ruling as evidence. R-2 stands: `heads` inside `grading.completed` still excludes `events`; the anchor entry, being external, includes it.
  2. The audit entry is written by the grading pass as its last action, after `segment.sealed`, through `audit-log.py` only. If the write fails, the pass reports `anchor: not recorded` on its normal output and exits non-zero on that step; it never guesses.
  3. `bench verify` resolves the audit log from the bench repo root (`--anchor <path>` overrides it, for tests). A missing anchored pass or a head mismatch is a new HB-LED code at exit 5, numbered at design time. A run with no anchor entry at all (ledgers from before this ruling) verifies with a warning, `anchor: not recorded`, never an error.
  4. An anchor entry not yet in a commit (`git status` shows the audit log modified) is reported as `anchor: uncommitted`, a warning. The Leader's commit cadence closes it; the report header states the anchor state of every graded run.
  5. Tamper tests before the slice closes: delete a later pass whole (exit 5); delete its anchor entry too (warning `anchor: not recorded` for that pass, plus a count mismatch against `grading.completed` rows, exit 5); an older ledger with no anchors (warning only).
  6. Deleting a run entirely is out of scope: US-41's "archive absent" and the audit log's run entries already show it.

## R-9 · 2026-09-24 · Owner seat (Fable) · DR-4: machine time and overlap policy for benchmark runs

- **Ruling:** the Leader applies these rules without asking the human.
  1. **Vendor exclusivity.** While a run is `running`, no coordination worker or Claude subagent runs on a vendor login that a cell of the run uses: Anthropic (Claude Code cells), OpenAI (Codex cells), GitHub (Copilot cells). Grok (xAI) and Agy (Google) tracks may overlap, up to the wave's fan-out cap. The one exception is the Leader session itself, which stays up to drive `/start-benchmark` and polls `bench status` only: no subagent fan-out and no authoring during a run.
  2. **Smoke run (wave 2): the overnight window, 22:00–07:00 operator-local** (PDT, UTC−7; `docs/architecture.md` phase 2 fixes 07:00 as the read-out). Sizing: the spec's example is 48 cells, 8 h 40 min at parallelism 4 (`docs/specs/harness-bench.md:904`), but `plan.py:30` caps phase-1 parallelism at 2, which makes it 16 h 20 min and misses the window. So the smoke run goes at parallelism 4 only after row 15 has measured D1 at parallelism ≥ 2 and the cap is raised on that evidence; otherwise it is split into two runs by combo pair, one per night, each with its own report.
  3. **Full grid (wave 5): a declared exclusive block, not an overnight window.** 576 cells at the spec's four combos (ADR-0006's ceiling); Σ budgets = 24 (combo × pack × rep) sets × 900 min (the BOM's 24 task budgets summed) = 21,600 min, about 91 h of cell execution at parallelism 4, grading extra. It runs as nightly 22:00–07:00 segments joined by resume (row 23), or continuously over a weekend; rule 1 holds for the whole block. Rows 21–27 are complete before it starts, so little coordination work is displaced.
  4. **Day hours (07:00–22:00):** only X1 and qualification runs of ≤ 4 cells, under rule 1. Wave 0 and wave 1 X1 runs are allowed at any hour.
  5. **Contention control.** A cell `failed (provider)` (HB-CELL-108: 408, 429, 5xx, overload) during any overlap is attributed to the overlap in the run record. Two such cells in one run tighten rule 1 to full exclusivity (no worker of any vendor) for the rest of that run and the next run. The report's validity banner already shows failed cells; nothing is re-run silently.
  6. **Host and power.** The run's power request (row 11) keeps the host awake; nobody sleeps the host inside a window. The human's A9 sleep probe (row 30) is scheduled outside run windows.
  7. **Record.** Each window goes in the run record: planned and actual start and end, cells, parallelism, and the workers active by vendor. That is the measurement rule 5 and the next revision of this ruling read.
- **Reasoning:**
  - Measured on this host at 13:52 PDT: 24 logical CPUs, 127.4 GB RAM (103.5 GB free), 1,193 GB free on `C:`, with 10 claude, 1 codex, 2 copilot, 1 grok, 1 agy and 14 node processes resident at about 4.2 GB working set in total. CPU, memory and disk are not the binding constraint for parallelism 4 beside five workers; risk A5 stays a measurement (row 15), not a reason to serialise.
  - The binding constraint is the per-vendor subscription allowance, which is unmeasured here: no run ledger exists yet (`C:\projects\bench-cells` is absent), and cost is `NA` by decision (subscriptions only). `assume:` each vendor's subscription applies one rolling usage allowance per login, shared by every session on it, cells and workers alike; **confirm:** a 429 or overload classified `failed (provider)` in a cell while a same-vendor worker was active, or the vendor's published plan terms; **breaks:** if allowances are per session, rule 1 is over-strict and costs wall clock, never validity.
  - A same-vendor worker during a run confounds the measurement twice: it competes for the allowance (a `failed (provider)` cell), and it changes wall time on cells that do not fail. Grok and Agy share no login with any benchmark cell, so they cost only host resources, which are in surplus.
  - The overnight window is the architecture's own phase-2 demo ("P1 runs the smoke BOM overnight; at 07:00 `bench status` explains every non-completed cell"). The full grid cannot fit any overnight window at the BOM's budgets, so it needs resume, which is why row 23 precedes row 25.
- **Conditions:**
  1. Row 15's measurement (peak memory and CPU time on D1 at parallelism ≥ 2) is the trigger to change any parallelism figure here; until then, 2 is the cap and 4 is the target.
  2. The first `failed (provider)` cell observed under overlap converts the `assume:` above into a measured claim; the Leader records it in `docs/lessons/defect-classes.md` as a class and attaches the ledger rows.
  3. Any change to the windows or the vendor rule is a new ruling, not an edit to this one.
