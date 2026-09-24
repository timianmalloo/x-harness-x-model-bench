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

## R-10 · 2026-09-24 · Owner seat (Fable) · DR-A: W1-TOOLB moves to Claude Code; W1-HOST's slice is joined

- **Ruling:**
  - **W1-TOOLB: (a).** The track moves to a Claude Code subagent (Sonnet 5, T1) now, per R-4. No Agy retry.
  - **W1-HOST: yes, join the slice.** The transport failure (`output_limit_exceeded` at 906 s, 526 extension notifications) came after the work; the work is in git (7 commits: 3 red→green pairs plus the leftovers test) and the Leader re-ran all 3 reds in throwaway trees. The join gate the plan sets (full suite green, cited reds re-run) is the acceptance criterion; the runner envelope is not.
- **Reasoning:**
  - The plan's R-4 trigger fired as written: "a slice that ends with no commit … moves the track to Claude Code by Owner ruling" (`docs/coordination/coordination-finish-harness-bench.md:86`). W1-TOOLB ended at 0 turns, no commit, tree clean.
  - Option (b) is a second guess. The failure is a runner rule, not a brief defect: "Other native error steps fail. No later prompt is sent" (`reference/launch.md:244`). A brief that forbids reading `.git` avoids the one observed path; any `view_file` on a path that does not exist fails the attempt the same way, so the class stays open. The same reference says a different policy "needs explicit Owner selection and a new qualified attempt, never an automatic retry" (`launch.md:239`); this ruling is that selection, and it selects Claude Code.
  - W1-HOST's evidence does not depend on the runner's envelope. Commits are the artifact the join reads (plan line 86: "each slice … ends at a commit and a hand-back"); the hand-back is the only part missing, and the Leader can reconstruct it from the commits, labelled as such.
- **Conditions:**
  1. W1-TOOLB's Claude subagent is dispatched under R-9 rule 1: no benchmark run may be `running` while it works (wave 1 has only X1 and qualification runs; the Leader schedules around them).
  2. The run record for W1-TOOLB carries the measured evidence: Agy 1.2.10, `gemini-3.8-flash`, `native_tool_error` at 292 s, the `view_file` on `<worktree>/.git/hooks/pre-commit`, and the rule at `launch.md:244`. R-4's record rule applies.
  3. W1-HOST's join review completes as planned (Test Architect hard veto on observed exit evidence). Only committed work is joined; nothing uncommitted in the worktree crosses. The run record labels the slice `output_limit_exceeded` with the 7 commit SHAs and the three red re-run results; the hand-back is marked "reconstructed by the Leader from the commits"; tool count "not recorded" (plan line 86).
  4. Any W1-HOST item the review finds missing (the brief listed four reds; the report says three pairs plus the leftovers test) goes to the next slice, under R-11's Grok rules, or to Claude Code if the review finds the slice incomplete in substance.

## R-11 · 2026-09-24 · Owner seat (Fable) · DR-B: two runner limits go upstream; Grok continues under slice rules, Agy is held

- **Ruling:**
  1. **Both are pack defects; both are fixed upstream**, red-first, in `C:\projects\ai-forward`, committed and pushed as a pack revision, then applied here by `/updatepack` (per the operator's standing instruction, plan line 176). They go in **a second pack track, W1-PACK-2** (Claude Opus subagent, T1), dispatched when W1-PACK commits, not folded into the in-flight W1-PACK (its budget is 150 calls · 2 h and its scope is gated; adding two runner changes to a live track is the scope growth the Simplifier already blocked once).
     - **Fix 1 (output bound):** an output bound must never fail an attempt whose work is committed. The 16 MiB ceiling (`coord-runner.py:366`) stays a host protection, but overflow is spilled to a file or truncated with a count, the envelope records `output_truncated`, and the attempt fails only on its deadline, its turn cap or a real error. Extension notifications are the progress stream; they are counted separately (the result already records `extension_notifications`) and must not be what ends a working attempt.
     - **Fix 2 (native tool errors):** only the native permission-error step and `denied_actions` block an attempt (the runner already distinguishes them, `launch.md:243`). Other native tool-error steps are recorded as counts and the prompt continues; a cap on consecutive native errors is the loop breaker, and its firing is a defect signal, not a termination argument.
     - Fixtures: the Grok transport counts from `w1-s1` (906 s, 526 notifications, 16 MiB) and the Agy conversation-store step (`view_file` on a nonexistent `.git/hooks/pre-commit`). The runner bytes change, so `qualify-codex-3` and a Grok/Agy re-qualification follow `/updatepack`, as the plan already orders (line 145).
  2. **Grok continues** on W1-COP-R and W2-CANARY until the fix lands, under slice rules: a slice is ≤ 12 min wall clock; the brief forbids verbose output (`pytest -q --tb=short`, targeted test files, no full-suite runs, no printing of large files); the agent commits at every green, so a transport failure never loses work (W1-HOST's own lesson); the runner's `output_limit` is set to its maximum. A slice that ends with no commit, or a second `output_limit_exceeded` under these rules, moves the track to Claude Code (R-4).
  3. **Agy is held** for runner tracks until fix 2 is applied locally and Agy re-qualifies. Its failure mode is a class a brief cannot close (any read of a nonexistent path ends the attempt). R-1 stands for re-qualification; W1-TOOLB is already moved (R-10).
- **Reasoning:**
  - Neither failure is a harness defect. Grok delivered a complete slice and Agy's error was recoverable by the agent; the runner ended both. A rule that turns working attempts into failures is a control that fails when it should not, and the pack's own doctrine fixes that upstream, not around it.
  - The 12-minute slice for Grok is a circuit breaker derived from the one measurement here (16 MiB at 906 s on a test-heavy slice), at about 80% of the observed time to the ceiling. **It is Inferred**: the byte rate is workload-dependent, so the brief's output rules matter more than the minutes. `assume:` a slice under the output rules stays well under 16 MiB in 12 min; **confirm:** `total_output_bytes` in the next Grok result; **breaks:** a second `output_limit_exceeded`, which moves the track (item 2).
  - Holding Grok would idle the harness that just produced a joinable slice; holding Agy costs nothing now, since its only wave-1 track has moved.
- **Conditions:**
  1. Both fixes are recorded in `docs/lessons/defect-classes.md` as a class (a runner bound that fails a working attempt), with the two run records as instances, and the upstream tests as the control.
  2. Each Grok slice's result records `total_output_bytes`, `extension_notifications` and wall clock in the run record, so the 12-minute figure is replaced by a measured one at the wave-1 join.
  3. `/updatepack` timing is unchanged: after the wave-1 merge, then `qualify-codex-3`, then the Grok and Agy re-qualification before any wave-2 dispatch on them.
  4. If W1-PACK-2 has not landed by the wave-2 dispatch, W2-CANARY stays on Grok under item 2; no wave-2 track is dispatched to Agy.

## R-12 · 2026-09-24 · Owner seat (Fable) · Q1, Q2: pin `@github/copilot` 1.0.89-1 with auto-update off

- **Ruling:** pin **1.0.89-1**, and set **`COPILOT_AUTO_UPDATE=false`** in the profile environment as part of the launch shape.
- **Reasoning:**
  - 1.0.89-1 is the build the capture measured (ACP in a per-cell home, `set_model` accepting `gpt-6-sol` and refusing unknown ids with -32602) and the build installed on this host (`copilot --version`: 1.0.89-1). 1.0.88 (npm `latest`, published 2026-09-22) was not measured here; pinning it would trade an observed build for an inferred one.
  - 1.0.89-1 is on npm (`npm view @github/copilot@1.0.89-1`: 1.0.89-1, published 2026-09-23) under the prerelease channel, whose tag has since moved to 1.0.89-3. A prerelease is a version like any other once the lockfile pins it and `tools.py` hashes it at every cell start (US-12).
  - Auto-update is exactly the silent build change US-12 forbids; the phase-1 record already has Claude Code updating itself mid-session (ADR-0013, "Pinned harness builds").
- **Conditions:**
  1. The report header names the build and marks it `prerelease`.
  2. If the profile qualification suite (ADR-0011) fails on 1.0.89-1, the fallback is the newest build that passes it, chosen by W1-COP-I and recorded with the failing evidence; never `latest` by tag.
  3. `COPILOT_AUTO_UPDATE=false` is asserted by `tests/test_profiles.py` as data in the profile, and its effect is observed once: the build hash is identical at the first and last cell of the wave-1 X1 run.

## R-13 · 2026-09-24 · Owner seat (Fable) · Q3, Q9: the two `engine.py` lines go to W1-ACP

- **Ruling:** yes. The one call-site line (`model=` passed to `run_turn` when the launcher sets `set_model`) and the `credential_kind` wording ("nothing copied" for Copilot) go to **W1-ACP**, in its step (f), as the only caller of its driver change. The plan's ownership table gains the row: `engine.py` — wave-1 owner W1-ACP, **those two lines only**; W2-STOP owns it from wave 2.
- **Reasoning:** the line exists only because the driver gains `model=`; splitting caller and callee across tracks makes the driver change untestable end to end at W1-ACP's own join (E7 surface list). W2-STOP does not exist yet, and the Leader authors no track work.
- **Conditions:**
  1. The `getattr(launcher, "set_model", False)` default stands as designed (`simplify:` one call site; upgrade trigger: a second per-launcher option moves it to the `Launcher` Protocol).
  2. `credential_kind` becomes a value the launcher reports, not a string the engine assumes: Copilot reports `subscription login (credential store)`; Claude and Codex keep `subscription login (copied)`. A test asserts each.
  3. W1-ACP's `git diff` scope for `engine.py` is those two hunks; anything else in `engine.py` is a seam request.

## R-14 · 2026-09-24 · Owner seat (Fable) · Q4: no `trustedFolders` seeding; the treatment stays as measured

- **Ruling:** **no.** The per-cell `config.json` does not mark the working copy trusted. "Pack on" for Copilot is what the capture measured: 21 instruction files loaded and 8 pack hooks run under ACP in a per-cell home without it.
- **Reasoning:** the design's concern (R6: hooks may not run under Copilot ACP) was a reading of the pack's reference; the capture is the measurement and it contradicts it. Seeding trust would widen the treatment beyond what the other harnesses get and change the meaning of pack on for one harness only (US-14 symmetry).
- **Conditions:**
  1. The wave-1 report records the pack-on counts per Copilot cell: instruction files loaded, `hook.start`, `skill.invoked`. If `skill.invoked` is 0 in every pack-on cell while a Claude Code pack-on cell shows skills, that is a disclosed treatment difference, not a reason to seed trust; it reopens this ruling with the counts as evidence.
  2. The 528,166-token pack-on turn against 59,501 pack-off is recorded in the design's capture section as the measured cost of the treatment on Copilot.

## R-15 · 2026-09-24 · Owner seat (Fable) · Q5, Q6: "not recorded" validity is a wave-2 row; AI units are a wave-3 row

- **Ruling:**
  - **Q5:** yes, a new validity state for an unreadable native record (a `HB-VAL` code, `views.py`), for all harnesses, as a **wave-2 row** drawn at the wave-1 join. Not wave 1: `views.py` has no wave-1 owner and the defect pre-dates Copilot (`views.py:237` returns `invalid (no model call)` for every unreadable store).
  - **Q6:** AI units (`total_nano_aiu`) become a Canonical measure in a **wave-3 row** (graders and catalog), with a catalog version bump. Wave 1 keeps them in the sample's provenance only, as designed.
- **Reasoning:** an unreadable record is "not recorded", never a plausible wrong label (IO: degrade to not recorded). A new measure is a new column, additive per call, keyed like tokens; it needs the catalog version because the report's cost section reads the catalog (DM: declare the grain, then the column).
- **Conditions:**
  1. Q5's state is distinct from `invalid (no model call)`: the latter stays for a readable record with no call.
  2. Q6 stores the native value; no second definition of tokens is derived from it (the design's "derive, don't store" note stands).

## R-16 · 2026-09-24 · Owner seat (Fable) · Q7, Q8: the Copilot canary branch and `bench/pack-markers.txt` go to W1-COP-I

- **Ruling:**
  - **Q7:** W1-COP-I authors the Copilot branch of `tests/e2e/test_us13_canary.py` (control home seeded with an instruction file, a skill and a `settings.json` model; the probe shows none). The Leader runs it in a capture window under R-9 rule 1. If no window occurs before the wave-1 exit, the report states "Copilot user-config isolation: not measured" on every Copilot cell, as the plan allows (line 111); the test still lands.
  - **Q8:** W1-COP-I creates `bench/pack-markers.txt` seeded with `AI-Forward Pack`, `Agent Knowledge Pack`, `Rigor Protocol`.
- **Reasoning:** W1-COP-I owns the isolation surface the canary tests (`cell_env` drops, `workspace.py`) and the US-9 scan that reads the marker file. The three markers are verified by the design's dry run: 76, 66 and 138 pack-on files, 0 pack-off (pack `ca032f0`, revision 92).
- **Conditions:**
  1. The scan carries a positive control (the pack-on copy must match at least one marker) so a scan that cannot fire is void.
  2. The marker list is re-verified when the pack revision changes (`/updatepack` after the wave-1 merge): a marker that no longer matches any pack-on file is removed, and the change is recorded.

## R-17 · 2026-09-24 · Owner seat (Fable) · NEW-1: bump the pinned Claude Code build in W1-COP-I

- **Ruling:** yes. W1-COP-I (owner of `bench/tools/package*.json`) bumps the pinned Claude Code to **2.1.282** (`@anthropic-ai/claude-agent-sdk` 0.3.282, npm `latest` on 2026-09-24, with whatever `@agentclientprotocol/claude-agent-acp` release pairs with it) before the wave-1 exit. If the profile qualification suite fails on 2.1.282, the pin is **2.1.281**, the build installed and used on this host today (`claude --version`: 2.1.281). The user's choice of `claude-opus-5-5` stands; the pinned 2.1.274 cannot serve it ("version 2.1.280 or newer is required", measured).
- **Reasoning:** a pin exists so the report names the measured build, not so the build never moves. The operator asked for Opus 5.5 in Claude Code; the only way to measure that is a build that serves it. Both candidate builds are one qualification run away from being evidence.
- **Conditions:**
  1. The profile qualification suite (ADR-0011, risk A8) runs on the new build before any wave-1 X1 run; its result is in the run record.
  2. The phase-1 X1 run (cc-sonnet on 2.1.274) is **not comparable** with the wave-1 X1 run. The wave-1 run is the new baseline. The wave-1 report says so in its header, and `bench compare` (row 24) refuses or flags a comparison across harness builds (a test asserts which).
  3. `bench plan` refuses a model the pinned build cannot serve, where the profile can know it; where it cannot, R-18's cause is the detection.

## R-18 · 2026-09-24 · Owner seat (Fable) · NEW-2: an unsupported-model refusal is `failed (model unavailable)` on every harness

- **Ruling:** yes. HB-CELL-116 `failed (model unavailable)` (attribution `benchmark`) is the cause whenever the model named in the plan cannot be served: a refused `session/set_model` (Copilot, -32602), a provider or CLI rejection of the model id (Claude Code 2.1.274 on `claude-opus-5-5`), or an "unsupported model" 400 in the native record. **W1-ACP** maps the driver-side forms (the adapter error and the transport-level rejection before any call); **W1-COP-I** adds the Copilot setter form in `errors.py` and its tests.
- **Reasoning:** the code already exists (`errors.py:24`, since `818f646`) and `normalize.classify` already returns it for a non-provider error in the native record (`normalize.py:82`). The gap is the path where the rejection never reaches a native record: the driver sees an adapter error and the engine's precedence falls through to the driver cause, `adapter_crash` (`engine.py:451`). A plan defect labelled as a harness crash mis-attributes the failure and would count against the harness in the report.
- **Conditions:**
  1. Red-first, with the measured w1 record (the 2.1.274 rejection) as the fixture for the driver path and a fake agent that errors `set_model` for the setter path.
  2. `adapter_crash` (HB-CELL-105) keeps its meaning: the adapter exited or the pipe closed with no classifiable error text. A classifier that needs the error text degrades to `adapter_crash` with the text in `detail`, never to `model_unavailable` by guess.
  3. The report's validity banner attributes HB-CELL-116 to the benchmark (the plan), not to the harness; the phase-2 proof carries one such cell as evidence.

## R-19 · 2026-09-24 · Owner seat (Fable) · NEW-3: accept the TOOL-B control's unit-level proof; the phase-1 count is Flagged; the re-run is a named window

- **Ruling:** option (c) now, with a named later window. W1-TOOLB's exit is met by the control's unit-level proof (the three seeded cases: a collection error, a timeout and an exit-2 run are each NOT a named kill). The phase-1 figure 2267 is recorded in `docs/proof/phase2.md` as **"not re-derivable (Flagged): the phase-1 cosmic-ray session databases were not kept"**. The re-run is a named window, not now.
- **Reasoning:**
  - Nothing survives to re-derive from: no `*.sqlite` under the primary checkout or the phase-1 worktrees, and the round-2 condition "keep the cosmic-ray session databases as evidence" (`docs/proof/phase1.md:251`) was not met. That is a defect of evidence retention, and a re-run would not restore the phase-1 count: the code has moved, so the mutant set differs, and the result would be a new count beside 2267, not a re-derivation of it.
  - A full cosmic-ray run costs hours of CPU on the host but no vendor login, so it does not break R-9 rule 1. It does compete with runner slices and the Leader for the host, so it is scheduled, not started.
- **Conditions:**
  1. **The window:** the first day-hours slot after the wave-1 merge with no benchmark run live and no runner slice active, or the next night not used by a benchmark run. The Leader runs cosmic-ray over the merged `main`'s phase-1 modules with the control, stores the session database with its sha256 in the run record (W1-TOOLB's own exit condition), and writes the **new** kill count and the re-derived named-kill count side by side in `docs/proof/phase2.md`. 2267 stays Flagged.
  2. No mutation-bar claim is made in any phase-2 artifact until that window has run (the round-2 condition, unchanged).
  3. Defect class: "evidence named as a condition was not retained" is recorded in `docs/lessons/defect-classes.md`; the control is that every mutation run stores its database and hash in the run record before the proof cites the count.
