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

## R-20 · 2026-09-24 · Owner seat (Fable) · Q10: no `model_calls` grain deviation; Copilot's per-model aggregate is a `turn_usage` fact under a third token-source rule

- **Ruling:** the grain deviation is **rejected**. `model_calls` stays "one model request" (ADR-0006), and Copilot writes **no** `model_calls` rows: the extraction records `model_calls: not recorded (no per-call record in the native format)`. Copilot's per-model session aggregate (`session.shutdown.modelMetrics`) is written to the existing **`turn_usage`** fact, whose declared grain, one `(run, cell, attempt, model)`, is exactly what Copilot records (one attempt is one session). This is a **third `usage_source` rule** (`native_session`; the name is fixed at design time), which by the token-source note's promotion rule (`docs/notes/decision-token-source-per-harness.md:52-54`) is an **ADR-0008 amendment**. No second `turn_usage` writer process is introduced: the rows are produced by the Copilot reader (W1-COP-R) as `TurnUsage` values and appended by the grading pass under the same write-once-per-extraction rule as `model_calls`; the appending line in `grade/runner.py` is W1-COP-I's (plan line 96: it "wires row 4"). The Data & Persistence Architect's veto stands: nothing implements this before its gate clears at the COP-D join, and a dissent returns as a decision request that amends this ruling.
- **Reasoning:**
  - A fact's grain is not per harness. One row per model per session inside `model_calls` is a second definition of one quantity (DM7) and breaks the key: two models from one `session.shutdown` line share `(native_session_id, native_ordinal)`.
  - The right fact already exists. `turn_usage` is keyed `(run_id, cell_id, attempt, model)` (`views.py:35`), the grade runner already reads it (`grade/runner.py:96`), and `served_models` already has a path that reads it (`normalize.py:68-69`). The only new thing is *who* fills it for Copilot and from *what*, which is what a `usage_source` rule names.
  - Copilot's ACP `usage` cannot be that row: it is a per-turn total with no model (fixture: `inputTokens` 527,641, no model key), while `modelMetrics` carries the model, six requests and the same buckets. So the aggregate comes from the native record at grading, not from the engine.
- **Conditions:**
  1. ADR-0008 amendment text: `native_session` = per-(attempt, model) token buckets from the native record's session aggregate, written to `turn_usage` at grading; served models for the mismatch check are the `turn_usage` models joined with the `assistant.message.model` set; `model_calls` not recorded. `bench/profiles/copilot.yaml` names it; `profiles.py` `USAGE_SOURCES` gains it (W1-COP-I).
  2. Bucket normalisation is asserted by arithmetic, not by name: Copilot's `usage.inputTokens` **includes** cache read and write (fixture: 18 + 439,386 + 88,237 = 527,641), so uncached input is `tokenDetails.input.tokenCount`, never `inputTokens`. The reader test states this sum (ADR-0006, "Token buckets must be normalised per harness").
  3. `turn_usage` rows written at grading carry the `extraction_id`; engine-written rows carry none. A re-grade with the same reader build reuses them (write-once), and totals never sum two extractions.
  4. `requests.count` per model (6 in the sample) and `totalNanoAiu` stay in provenance for wave 1; they join the catalog with Q6 (R-15).
  5. A Copilot cell with `turn_usage` rows and no `model_calls` rows is `valid`; a test asserts that `invalid (no model call)` is not produced by the absence of `model_calls` alone under `native_session`.

## R-21 · 2026-09-24 · Owner seat (Fable) · Q11: a graceful end is a W2-STOP exit condition, inside the 30-second stop bound

- **Ruling:** yes. On a budget expiry or a stop, the engine first sends ACP `session/cancel`, closes the adapter's stdin and waits a bounded grace; only then does it terminate the Job Object. The grace lives **inside** the existing bound: the cell is still `stopped` or `timed_out` within 30 s of the engine's clock (UXA-10, plan line 117), so the hard floor does not move. A Copilot timeout test asserts that `session.shutdown` is present and the tokens are recorded after a budget kill.
- **Reasoning:** without a routine shutdown Copilot writes no `modelMetrics`, so a killed cell's tokens are "not recorded" and today's label is the wrong one (`invalid (no model call)`, design R7). A graceful end is the cheapest measurement fix; the wrong label is Q5's fix (R-15).
- **Conditions:**
  1. The grace is a profile datum with a ceiling (≤ 10 s; `simplify:` upgrade trigger: a harness whose shutdown needs longer, measured), and the kill still fires at the bound regardless.
  2. A cell that still writes no shutdown after the grace reads "tokens: not recorded" (R-15's new state), never `invalid (no model call)`.
  3. The TLC model keeps its semantics: the grace is a refinement of the terminate step, and the seeded variants still fail.

## R-22 · 2026-09-24 · Owner seat (Fable) · Q12: `initialize.agentInfo.version` is recorded as the US-12 evidence

- **Ruling:** yes, W1-ACP. `TurnResult` gains `agent_name` and `agent_version` from ACP `initialize.agentInfo`, and the ledger's `attempt.session_opened` event carries them beside the native session id. US-12's executed-build check compares `agent_version` with the pinned build; a mismatch is `build_changed` (HB-CELL-115). `session.start.copilotVersion` (`"0.0.0"` in the capture) is never used as evidence; the reader records it as "not recorded".
- **Reasoning:** the pinned-build hash proves which file was launched; `agentInfo.version` is an independent observation of what answered, from the protocol itself, on every harness. Two observations that must agree is a control; one that cannot fire is not.
- **Conditions:**
  1. Absent `agentInfo` is null in the ledger (not recorded), and the check is then skipped with a warning, never passed.
  2. The value is recorded verbatim, no parsing; a test shows a fake agent reporting a different version producing HB-CELL-115.

## R-23 · 2026-09-24 · Owner seat (Fable) · Q13: one classifier for prompt-time errors, mirroring `normalize.classify`

- **Ruling:** mirror `normalize.classify`, with **one** classifier called from both paths (the native-record path and the driver's `session/prompt` error path). A prompt-time JSON-RPC error that carries an HTTP status or a provider error type is classified: 408, 429, 5xx or an overload type → `provider` (HB-CELL-108); an auth failure → `blocked_auth` (the existing `_auth_failure` precedence, `driver.py:199`); any other 4xx → `model_unavailable` (HB-CELL-116). `adapter_crash` (HB-CELL-105) remains for an error with no status and no classifiable type, with the text in `detail`. This **amends R-18 condition 2 by reference**: a status in the error is evidence, not a guess. W1-ACP, red-first on the recorded 2.1.274 rejection text.
- **Reasoning:** an adapter that answers the prompt with a structured error did not crash; labelling it a crash charges the harness for a request the model service refused. The native-record path already makes this call (`normalize.py:73-82`); two classifiers for one question would drift (one definition, DM7 applied to logic).
- **Conditions:**
  1. The classifier is one function with two callers; a test feeds it the same error through both paths and asserts one cause.
  2. A 4xx that is in truth an adapter defect (a malformed request) will read `model_unavailable` with the adapter's text in `detail`; the report's drill-down shows the detail, and the phase-2 proof discloses the class.

## R-24 · 2026-09-24 · Owner seat (Fable) · Q14: record the ACP `usage` object on the attempt's terminal event

- **Ruling:** record it now, in wave 1, as an **attribute of the attempt's terminal `events` row** (`acp_usage`, the adapter's `usage` and `_meta` halves verbatim, no arithmetic), not as a new fact. Owner: **W1-ACP**, as a third `engine.py` hunk under R-13 (the value comes from the `TurnResult` W1-ACP owns; the driver already keeps both halves, `driver.py:210-212`, and the engine reads only `_meta`, `engine.py:363`).
- **Reasoning:** for Copilot the ACP total is the only in-ledger cross-check on the reader's per-model rows (Σ `turn_usage` buckets over models must equal the turn total). A check that lives only on committed fixtures cannot see a real run. An events attribute keeps the grain honest (one row is one transition) and costs one hunk.
- **Conditions:**
  1. Wave 1 records; the view-level check (a `HB-VAL` warning when the sum and the total disagree) is a wave-2 row beside Q5 (R-15).
  2. The attribute is null when the adapter reports nothing; a test asserts null, never `{}` or zeros.
  3. R-13's scope statement for W1-ACP on `engine.py` is now three hunks: `model=`, `credential_kind`, `acp_usage`.

## R-25 · 2026-09-24 · Owner seat (Fable) · Q4 re-read: R-14 amended by reference; the hooks executed and failed

- **Ruling:** the Leader's routing is accepted (upstream fix in the W1-PACK-2 revision 95; Copilot pack-on cells disclose until it lands). R-14 is **amended by reference**: its reasoning said "8 pack hooks run"; the measurement is that all 8 executed and **failed** (`success: false`) under Copilot's PowerShell. R-14's decision (no `trustedFolders` seeding) stands, because trust was not the cause.
- **Conditions:**
  1. Every wave-1 Copilot pack-on cell carries the flag `pack hooks failed (Copilot PowerShell)`, and any Copilot pack-effect figure is **Flagged** until re-measured on the fixed revision.
  2. The re-measurement (hook success counts on revision 95) is a named next step at `/updatepack`; R-14 condition 1's counts are read from it.

## R-26 · 2026-09-24 · Owner seat (Fable) · R-20 dissent: the Data & Persistence Architect's C1–C3 are adopted; R-20's placement is withdrawn

- **Ruling:** **adopt C1–C3.** R-20's placement of Copilot's per-model aggregate in `turn_usage`, and its third `usage_source` rule, are **withdrawn**. `model_calls` is re-declared by ADR-0006 amendment as *one row is exactly one model's token usage in one native usage report, by one principal, as read by one extraction*; every row carries an additive `requests` count (Claude/Codex: 1; Copilot: `modelMetrics.<model>.requests.count`; absent in a pre-amendment ledger reads as 1); `start`/`end` only when the report is one request; a call count is Σ `requests`, never a row count. Copilot keeps `usage_source: native_record`. R-20's conditions 2 (bucket arithmetic) and 4 (`totalNanoAiu` stays in provenance until Q6) stand; conditions 1, 3 and 5 are void.
- **Reasoning:**
  - Both objections are verified in the code, not argued. `turn_usage`'s key is `(run_id, cell_id, attempt, model)` with no `extraction_id` (`views.py:35`), so a grading-pass writer would break "extractions are written once" (ADR-0006:74): after a normaliser fix the new rows would collide with the old. And the token-source note defines `turn_usage`'s writer as *the engine thread, from the ACP stream* (`decision-token-source-per-harness.md:38`); a second source for one fact is the DM-A shape. R-20's condition 3 tried to repair this by adding `extraction_id` to some rows, which is a key change on a live fact, worse than the deviation it avoided.
  - D&P's form keeps one writer (the grading pass), the write-once rule and the extraction identity, and states the grain honestly instead of hiding an aggregate behind a per-call name. Its cost, that a row is not a call, is carried by an explicit column and a guard, which is the DM rule: declare the grain, then the column.
  - The Patterns Expert's second recommendation is taken with it: the grain and the `requests` rule live in the Canonical Data Model (`telemetry/__init__.py`, the `ModelCall` docstring), not only in a design document.
- **Conditions:**
  1. **C1:** ADR-0006 `model_calls` grain amended as above, with this ruling as evidence; `decision-token-source-per-harness.md:40` corrected from "per-call rows" to "per-report rows"; the `ModelCall` docstring states the grain and the `requests` rule (Patterns Expert).
  2. **C2:** `requests: int` on `ModelCall`; one compute reader `calls_per_cell = Σ requests`; a guard test asserts that no view counts `model_calls` rows as calls (a two-request single-row fixture must yield 2).
  3. **C3:** reader tests assert the grain: the Copilot sample yields exactly one row per model in the **last** `session.shutdown`, `requests` equal to `requests.count` (6 in the sample), `start`/`end` null; Claude and Codex rows carry `requests == 1`.
  4. **Key uniqueness:** two models in one `session.shutdown` share `native_ordinal`; the amended key must stay unique (add `model`, or a per-entry sub-ordinal). D&P names the form at design time; a two-model Copilot fixture tests it.
  5. R-24's `acp_usage` attribute stays the cross-check: Σ over the current extraction's `model_calls` buckets equals the ACP turn total, a wave-2 view check (R-15).
  6. The Data & Persistence Architect's hard veto is discharged by this ruling; the schema does not move again in wave 1.

## R-27 · 2026-09-24 · Owner seat (Fable) · NEW-4: pack-on Copilot is not a treatment on revision 92; the exit run uses revision 95 through `--pack-source`

- **Ruling:**
  1. On pack revision 92, **the wave-1 pack-on Copilot arm is not a treatment**. Verified on the committed fixture (`9c6c615`): pack-on has 8 `tool.execution_start` (2 `skill`, 3 `glob`, 1 `powershell`, 1 `view`, 1 `rg`) and 8 `tool.execution_complete`, **all** `success: false`, code `denied`, "Denied by preToolUse hook from "repo settings" (hook errored)"; pack-off 6/6 succeeded. (The gate report says 9; the committed fixture holds 8. The count is read from the fixture.) R-14 and R-25 are amended by reference: the failing hook denies every tool, so a pack-on Copilot cell does no work.
  2. **The wave-1 exit run takes the pack fix without moving `/updatepack`.** The pack-on treatment is installed from `--pack-source` (the ai-forward clone whose HEAD is pinned at plan time, `cli.py:103/247`) and the plan records that revision (`cli.py:83/115`, `workspace.py:122`); it is independent of the bench repo's own installed pack. So the exit run points `--pack-source` at the ai-forward commit carrying revision 95 (W1-PACK-2), its header says "pack revision 95", and the repo's `/updatepack` stays where the plan pins it (after the wave-1 merge, then `qualify-codex-3`). If revision 95 is not committed upstream by the exit run, the run proceeds with Copilot pack-on cells reported **"pack on: all tools denied"**, excluded from every comparison, and the arm is re-run as the first act of wave 2.
  3. **The denial is measured, not inferred, from wave 1:** the Copilot reader records each tool call's outcome (`error.code`) on its `tool_calls` row (W1-COP-R; a `tool_calls` column, D&P names it with R-26's amendment), and the wave-1 exit E2E asserts **zero hook denials** in every Copilot cell's `tool_calls`, red on the revision-92 fixture. The validity state (`invalid (tools denied by hook)`, a `HB-VAL` code in `views.py`) is a wave-2 row with Q5 (R-15).
- **Reasoning:**
  - US-14's planned signal (the ACP permission-request count) is 0 because the denial happens inside Copilot's hook, below ACP. A symmetric-permission proof that cannot see a native denial is void for this harness; the `tool_calls` outcome is the signal that can.
  - The pack under test is a plan datum, versioned and pinned like a harness build. Testing revision 95 as the treatment is not the same act as rewriting the bench repo's managed pack files, which the plan pins later for a measured reason (`tests/test_skills_in_sync.py` scans every open worktree; Codex qualification is bound to the hook bytes).
- **Conditions:**
  1. The exit run's header names the pack revision and commit; any Copilot pack-effect figure on revision 92 is Flagged (R-25), and none is reported on revision 95 until a cell shows ≥ 1 successful tool call under pack on (the positive control).
  2. US-14 for Copilot is proven by two counts per cell: ACP permission requests and native hook denials, both 0 in a valid cell.
  3. The revision-92 fixture is kept as the negative control for the denial assertion; the revision-95 capture replaces the pack-on sample for every other Copilot test (a new capture window under R-9 rule 1).

## R-28 · 2026-09-24 · Owner seat (Fable) · R-22 dissent: kept, narrowed to one verbatim field; the Simplifier's dissent is recorded

- **Ruling:** **keep R-22, narrowed.** Wave 1 records one field, `agent_version`, verbatim from `initialize.agentInfo`, on `attempt.session_opened` (W1-ACP); `agent_name` is dropped. The comparison with the pin, and HB-CELL-115 on a mismatch, move to a wave-2 view check beside Q5 and R-24's check (record now, check later). The Simplifier's soft veto is overruled with the rationale below and its dissent is recorded here.
- **Reasoning:**
  - The exe sha256 (`engine.py:406`, `tools.py:40-45`) is the hash of the **file the bench launched**. It cannot see the case the design names as F3: the launched file is a launcher and a newer cached binary answers (Copilot keeps one under `%LOCALAPPDATA%`). R-12 prevents that with `COPILOT_AUTO_UPDATE=false`, but R-12 condition 3 verifies only that the launcher's hash is stable, which is true whether or not a cached binary moved. `agent_version` is the only observation that can detect F3, so it is not a second record of one fact: it is a second source for a check that would otherwise not fire.
  - The wave-1 cost is one verbatim field on an event row the ledger already writes; the Simplifier's point lands on the comparison logic, which is deferred.
- **Conditions:**
  1. Null when the adapter reports no `agentInfo`; never a guessed string.
  2. The wave-2 check is a view: `agent_version` must agree with the pinned build's version for the harness, else the cell is flagged; a fake agent that reports a different version is its red test.
  3. If wave 2 finds no harness on which `agent_version` and the pin can disagree in practice, the field is retired with a citation to this ruling (the Simplifier's upgrade-trigger in reverse).

## R-29 · 2026-09-24 · Owner seat (Fable) · W1-HOST slice 4: move to Claude Sonnet now; the diagnosis is an upstream runner change; Grok is held for new runner tracks

- **Ruling:** **(b), with the diagnosis routed upstream.** Slice 4 (tests only: `host.available_memory` / `unbiased_seconds` success-path values and `SleepDetector` recovery from a first `None` reading) moves to a Claude Code subagent (Sonnet 5, T1) now, per R-4. Option (a) is not executable as written: W1-ACP's recorder has two modes, `turn` (a full bench cell, `--harness {claude-code,codex}`) and `scrub`; it is not a transparent tee for an arbitrary adapter argv, so `acp_record.py record --out … -- grok …` does not exist. The diagnosis itself is a **pack defect and goes to W1-PACK-2** (the operator's standing instruction): on `protocol_error` the runner records the rejected message (bounded, scrubbed) in its result, because a control that fails with no evidence is the IO violation ("degrades to not recorded, never to nothing to read"). One diagnostic Grok attempt is made **upstream by W1-PACK-2** with that recording in place, not on a bench track. **R-11 item 2 is amended by reference:** Grok is held for **new** runner tracks (W1-COP-R, W2-CANARY) until the runner records message detail on `protocol_error` and Grok 1.0.41 re-qualifies with that evidence; until then those tracks dispatch to Claude Sonnet under R-4.
- **Reasoning:**
  - The R-4 trigger fired as written (a slice with no commit), for the second time on Grok in this plan (s1 `output_limit_exceeded`, s4 `protocol_error`), and `launch.md:255` says the transport's compatibility path "accepts only its recorded `skills-reload` response… Other unexpected responses still fail". Slices 2 and 3 succeeded on the identical profile, so the failure is non-deterministic and outside the brief's control; a re-attempt with the same brief is a coin toss whose only value would be the captured message, and the capture tool proposed cannot capture it.
  - The same symptom in `qualify-2..4` was resolved only by recording the messages. That is the measurement gap to close, once, in the runner, rather than per slice on a bench track. Slice 4 is small, tests-only and already specified by the veto read-back; its cost on Sonnet is lower than a second evidence-less attempt.
- **Conditions:**
  1. The run record for `w1-host-s4` carries the measured facts: Grok 1.0.41, `grok-4.7`, `protocol_error` at 3.36 s, 0 turns, 6 `compatibility_responses`, 22 extension notifications, `selected_model_set: false`, and "no message detail recorded" as the gap.
  2. W1-PACK-2's scope gains: (i) record the rejected message on `protocol_error` (bounded to the runner's line limit, credential-scrubbed); (ii) one diagnostic Grok 1.0.41 attempt with that recording, its result committed as the fixture; (iii) the transport's Grok compatibility path is widened only from that recorded message, never from a guess.
  3. The W1-HOST join reads the Sonnet slice by the same gate as slices 2 and 3 (suite green, the two Minors closed with the real values named in the tests).
  4. R-1 stands for Grok's return: re-qualification after (ii) lands locally, recorded in the run record.

## R-30 · 2026-09-24 · Owner seat (Fable) · O-1: R-13 condition 1 amended to the typed `Launcher` Protocol fields; the `getattr` form is not restored

- **Ruling:** **amend R-13 condition 1.** `set_model: bool` and `credential_kind: str` are typed fields of `engine.Launcher` (the Protocol at `engine.py:59-70`, which already declares the parallel optional `mode`), and the call site is `model=cell["model"] if launcher.set_model else None`. This ratifies what W1-ACP built at `61acbd6` (`engine.py:64/67/412/416` in its worktree) and what `ProfileLauncher` is gaining. The `getattr(launcher, "set_model", False)` form must **not** be restored. R-13's other conditions stand; its `simplify:` marker is withdrawn, since the typed field is both the smaller and the safer form.
- **Reasoning:**
  - The Patterns Expert's finding is correct on reading: a `getattr` default of `False` fails **open**. Any launcher without the attribute (a test fake, a typo) silently skips `session/set_model`, and that setter is the design's Prevent control for US-11 (the served model is the pinned model). A control that a missing attribute disables without a failure is not a control.
  - The Protocol is already the typed contract for the same class of per-launcher option (`mode: str | None`), so the typed field is reuse of the codebase's own idiom, not a new abstraction; a fake that omits the field fails at the type check and at first use, which is the failure the design wants.
  - R-13 accepted the `getattr` on the author's `simplify:` rationale (sparing fakes a new attribute). The measured cost of the typed form was one fake updated, so the shortcut bought nothing.
- **Conditions:**
  1. Every `Launcher` implementation and every test fake declares both fields explicitly; no default on the Protocol, no `getattr` anywhere on the engine's launcher surface (a grep-level test or lint asserts it).
  2. `tests/test_driver.py` / the engine tests include the negative control: a launcher with `set_model = False` never sends `session/set_model`, and one with `set_model = True` sends it before `session/prompt`.
  3. **For the record, agreed (no ruling needed):** the committed Copilot fixture `9c6c615` carried Copilot's vendor system prompt (no personal data), only on the unpushed design branch; it is re-scrubbed in `f952f87`, and the Leader squash-merges the branch at its join so the blob never reaches `main` or the remote. Condition: the scrub rule in the design's section 12 gains the vendor-system-prompt class so the next capture cannot repeat it, and the join record cites the squash commit.

## R-31 · 2026-09-24 · Owner seat (Fable) · Record: R-26 narrows R-20 condition 4 to `totalNanoAiu` only

- **Ruling (record-only):** R-20 condition 4 read "`requests.count` per model and `totalNanoAiu` stay in provenance for wave 1". R-26, by adopting the Data & Persistence Architect's C2, put `requests` on the `model_calls` row, so that condition is **narrowed by reference to `totalNanoAiu` only**: `requests` is a column of `model_calls` from wave 1 (R-26 conditions 2 and 3); `totalNanoAiu` stays in the sample's provenance until the wave-3 catalog row (Q6, R-15). This matches the design at revision 3.1, squash-joined to `main` at `2e9cc3b`.
- **Reasoning:** R-26 restated condition 4 as "AIU stays in provenance" without saying that `requests` had moved; a register entry that contradicts a later one is read newest-last, but the contradiction is recorded here so no reader has to infer it.
- **Conditions:** none new. R-26's conditions govern `requests`; R-15's govern `totalNanoAiu`.

## R-32 · 2026-09-24 · Owner seat (Fable) · US-11 on a context-window tag: (a) normalise the tag for the pin check, record it, disclose it; fix and re-run the same day

- **Ruling:** **(a).** Model identity for the served-model check (US-11) and for per-model totals is the **base model id**: a trailing bracketed tag (`[1m]`) is stripped by one function in `normalize` (`base_model_id`), used by `served_models` and by the per-model grouping. The served id is stored **verbatim** in `turn_usage` (facts are never rewritten); the tag is recorded once per cell as a disclosed attribute (`context_window_tag`, e.g. `1m`) on the attempt's terminal event, and the report shows it in the header and the cell drill-down ("Claude Code cells ran with the 1M context window"). Other harnesses' context windows are "not recorded", never assumed equal. Options (b) and (c) are rejected. The wave-1 exit **is blocked** until the re-run is green, and the fix is small enough to land and re-run **today** (an X1 run is allowed at any hour under R-9 rule 4, with rule 1 in force).
- **Reasoning:**
  - The API model id is exactly `claude-opus-5-5`; ids carry no suffix, and the model's own context window is 1M (Claude API model table, read this session). `[1m]` is Claude Code's client-side tag for the window it runs, which the native record confirms by recording the same calls as `claude-opus-5-5` (pack-off 4, pack-on 5). The two sources disagree on a label, not on the model: US-11 failed on a suffix, as the Leader measured.
  - **(b)** would pin a string that is not an API model id; the native-record cross-check would then mismatch the other way, and the matrix would carry a harness-specific id where the report compares by model. Rejected.
  - **(c)** rests on a setting that is unverified, and would change what is measured: the benchmark measures each harness as shipped, and the context window is part of the harness under test (ADR-0011 profile qualification records the build, not a tuned build). A harness property is disclosed, not equalised. Rejected as a ruling; it may be checked as a note if a reader asks for a like-for-like window.
  - The validity rule is the defect: a rule that fails a valid cell on a label is a control firing on noise. The fix is one function with one definition (DM7 applied to logic), used by every consumer of model identity.
- **Conditions:**
  1. Red-first: the fixture is the cc-opus ledger of run `e2e-wave1-1790299304` (`turn_usage` models `['claude-haiku-4-5-20251001', 'claude-opus-5-5[1m]']`, `model_calls` `claude-opus-5-5`); the red shows HB-VAL-002, the green shows `valid` with `context_window_tag: 1m`. A negative control keeps HB-VAL-002 for a genuinely different served model (`claude-sonnet-5`).
  2. `base_model_id` strips only a trailing `[...]` tag; anything else in the id is identity. The auxiliary rule (`claude-haiku-4-5*`) is unchanged.
  3. Ownership: `normalize.py` has no wave-1 owner; the Leader assigns this one change, with its tests, to a Claude subagent (Sonnet 5, T1) as a seam, and records it. `views.py` is not touched: the attribute is read from `events`.
  4. The re-run uses the same plan inputs (pack revision 95, Claude Code 2.1.282, `claude-agent-acp` 0.81.2); the run record cites both runs, the first as the negative fixture. Rule 1 of R-9: Claude subagents at hand-back while it runs.
  5. The report's harness-comparison view carries the disclosure on every Claude Code row; the pack-effect view needs none (both arms share the tag).


## R-33 · 2026-09-25 · Owner (Tim Mallalieu) · every model is stipulated, never defaulted

- **Ruling (operator, verbatim):** "based on the side observation we have to make sure in delegation of work AND testing that we stipulate the model based on the prompt".
- **Trigger:** the live Copilot US-13 canary (2026-09-25) showed that, with no pin, Copilot on the operator's account served `claude-sonnet-5`. Defaults are account- and harness-specific, and they drift.
- **What it decides:**
  - Every delegated worker contract names its model explicitly, taken from the prompt or plan.
    - Codex: `CODEX_CONFIG` in the runner wrapper sets `model`, because `codex-acp` merges `CODEX_CONFIG` into each thread's config (`index.js` ~28599/28704). The pin is verified from the served model at `qualify-codex-3`.
    - Grok: `-m <id>`. Agy: `--model <id>`.
    - Claude subagents: `model` is passed on every dispatch.
  - Every bench cell pins its model (already true: US-11).
- **Supersedes:** the operator decision of 2026-09-24 to run Grok and Agy on their default models. At their re-qualification they are pinned to the models they served in `qualify-6` (`grok-4.7`; `gemini-3.8-flash`), unless the prompt names others.
- **Exception:** a measurement whose point is the absence of a pin. The US-13 settings-model canary deliberately runs unpinned to detect a leaked user settings model, and it says so.

## R-34 · 2026-09-25 · Owner seat (Fable) · US-14 on Windows: `PowerShell` joins the Claude Code allowlist; ADR-0004 gains a per-platform note; re-run the same day

- **Ruling:** **(a).** `PowerShell` is added to the Claude Code profile's `permissions.allow` (`bench/profiles/claude-code.yaml:8`), red-first, and the wave-1 exit run is re-run today under R-9 (an X1 run at any hour; rule 1 in force). Option (b) is rejected: an arm that loses its shell is not a pack treatment difference, it is a **profile defect** that the pack surfaced by naming the tool. **ADR-0004 gains an amendment note:** the declared capability classes (file read and edit in the workspace, shell) are platform-independent; the tool **ids** that make up a class are per platform and per pinned build, the profile lists every id in the class for the platform it runs on, and the profile qualification fixture exercises each id. The observed `dontAsk` fallback is recorded as a second finding, below.
- **Reasoning:**
  - ADR-0004 allows **classes**, not names: "file read and edit inside `/work`, shell inside the container" (ADR-0004:42), and "each harness has a static mechanism that ran shell and edits with zero prompts" (ADR-0004:36). `PowerShell` is the Windows shell tool of the pinned Claude Code 2.1.282, the same class as `Bash`; the allowlist named the ids known when it was written (2.1.274) and predates the tool. Copilot's `shell` and Codex's full access already cover both shells, so adding the id **restores** the symmetry US-14 requires rather than widening it.
  - US-14 worked as designed: the driver's deny policy refused the unlisted tool, counted one permission request, and the E2E failed on `[0,1,0,0,0,0]`. The control fired on a real asymmetry; the fix is to the profile, not to the control.
  - The pack-on arm exposed the gap because the pack's instructions name the PowerShell tool. That is a fair property of the treatment on Windows, not a confound to remove; with the id allowed, both arms have the same shell.
  - **Second finding, disclosed, not fixed here:** the profile declares `defaultMode: dontAsk`, and the session reports "`dontAsk` is not available in this session; falling back to `default`" (phase-1 stderr, cited by the Leader). So the effective mode is not the declared one: an unlisted tool prompts instead of being refused silently. The allowlist plus the driver's deny policy is what actually enforces symmetry, and it did. The declared mode is therefore a stale datum; the profile's comment and the report's header must state the effective mode.
- **Conditions:**
  1. **Red-first:** the profile qualification fixture (ADR-0004's own rule, `:71`: "an allowed shell call succeeds; … an out-of-profile tool is refused and recorded") gains a `PowerShell` call on Windows; red on the current allowlist, green after. The cc-opus pack-on ledger of `e2e-wave1-1790302505` (tool_calls: Glob ok, Read ok, Edit ok ×2, PowerShell ok=0; permission requests `[0,1,0,0,0,0]`) is the negative fixture, kept.
  2. **Coverage of the class:** a test asserts the allowlist contains every shell and edit tool id the pinned build exposes on this platform, read from the build (its tool list or the qualification turn), not from memory; a new id in a later build makes the test red, which is the control against this class recurring (`docs/lessons/defect-classes.md`: "a per-platform tool id missing from a class allowlist").
  3. **ADR-0004 amendment note** as ruled, citing this ruling and the run; Copilot and Codex rows unchanged.
  4. **Effective mode:** the profile records `defaultMode` as declared and the run record records the mode the session reports (`permission_mode_effective`, from the observed stderr line); the report header shows the effective mode for Claude Code cells. A follow-up (wave 2, with the W2-STOP profile work) decides whether to declare `default` outright; until then the disclosure stands.
  5. Re-run on identical inputs (pack revision 95, Claude Code 2.1.282, `claude-agent-acp` 0.81.2), Claude subagents at hand-back; both runs cited in the run record. The wave-1 exit stays blocked until the re-run is green on validity **and** US-14.

## R-35 · 2026-09-25 · Owner seat (Fable) · `NotebookEdit` is in the file-edit class; add it to the Claude Code allowlist, red-first; no exit re-run

- **Ruling:** **in-class.** `NotebookEdit` edits a file in the workspace (`.ipynb`), so it belongs to ADR-0004's "file read and edit inside the workspace" class as amended by R-34. It is added to `permissions.allow` in `bench/profiles/claude-code.yaml`, red-first, before the wave-1 merge. The implementer's `assume:` marker is resolved by this ruling. **It does not block the wave-1 close and needs no exit re-run.**
- **Reasoning:**
  - Symmetry is the test: Copilot's `write` and Codex's full access already edit any workspace file, notebooks included, so allowing the Claude Code id restores parity; denying it would be the asymmetry US-14 forbids, surfacing the first time a task holds a notebook.
  - The pinned build's own record is the evidence (`tests/fixtures/native/claude-code/tools-2.1.282-win32.jsonl`, in the R-34 worktree), which is exactly the source R-34 condition 2 prescribes; the class-coverage test found the id, which is that control working on its first run.
  - X1 has no notebook, so the passed exit run (`e2e-wave1-1790303859`) measured nothing the change alters; the proof for this change is the profile qualification fixture and the class-coverage test, not a re-run. The profile hash in the plan changes, and the run record says so.
- **Conditions:**
  1. Red-first: the class-coverage test (R-34 condition 2) is red on the current allowlist and green after; the qualification fixture gains no notebook call in wave 1 (no task uses one), and the first task that does adds it.
  2. The run record for `e2e-wave1-1790303859` names the profile hash it ran with and the hash after this change, so the wave-2 smoke run is known to run on the new profile.
  3. Deferred tools are in scope of the class rule: a tool the build exposes on demand is still a tool the agent can call, so "deferred" never exempts an id from the coverage test.

## R-36 · 2026-09-25 · Owner seat (Fable) · account-level connectors reach Claude Code cells: (a) now, disclose and measure; (b) as a bounded probe; (c) held for the human; the close is not blocked

- **Ruling:**
  1. **(a) now.** Every Claude Code cell carries the flag `account context (R1.4)` in the report header and on each row of the harness-comparison view, the way N5 flags Codex cells (R-5, R-6). US-13's canary gains an **account-connector class** (the `mcp__claude_ai_*` tool names in the native record are the canary keys, printed by name per R-6 condition 3), and the Claude reader records per cell the count of account-level deferred tools in the record, so the size of the context confound is measured, not assumed. The allowlist already denies them (fail closed, verified by the run: zero permission requests).
  2. **(b) as a bounded probe, not a ruling.** One qualification turn on the pinned build with a documented per-session MCP restriction, if one exists. `assume:` Claude Code's `--strict-mcp-config` (with an empty `--mcp-config`) restricts the session to the given MCP configuration and so drops account connectors; **confirm:** the cell's tool record lists no `mcp__claude_ai_*` tool; **breaks:** the flag does not govern account connectors, or does not exist on 2.1.282 — then (b) is closed with that evidence. If it confirms, it goes into the profile as launch data (the same class of control as Copilot's `--disable-builtin-mcps` in ADR-0004) and the flag in item 1 is retired for runs on that profile.
  3. **(c) is held for the human.** Owner decision 1 (subscriptions only) stands; a dedicated benchmark account is the human's to create and is the named fallback if (b) fails, listed beside the R-4 items.
  4. **The wave-1 close is not blocked.** The tools are denied, the exit passed, and the disclosure is a header flag. The canary class, the per-cell count and the probe are wave-2 rows (W2-CANARY, on Claude Sonnet per R-29).
- **Reasoning:**
  - This is the class spike R1.4 already verified, "account-level context survives every isolation… the login, not a file", with the same two remedies flagged there. ADR-0004 bars MCP servers other than the task's own as a **capability**, which the allowlist enforces; what remains is the tool descriptions in the cell's context, a token and attention confound, not a capability leak.
  - N5 set the precedent: disclose, flag, measure, and name the reopen triggers; a fourth guess is not evidence (R-5). The probe in item 2 is one turn with a named confirm and break, so it is a measurement, not a guess.
- **Conditions:**
  1. **Pack invariance is measured, not asserted.** R1.4's "applies equally to pack on and off" is re-labelled **Inferred** until the Leader compares the deferred tool lists of the pack-on and pack-off cc-opus records from `e2e-wave1-1790303859` (both exist); equal lists make it Verified for that build, and the result is written in `docs/proof/phase2.md` beside N4 (R-6 condition 1).
  2. Reopen triggers, by reference to R-5 condition 3: a connector tool is ever **called** in a cell (a permission request or a `tool_calls` row naming `mcp__claude_ai_*`); the pack-on and pack-off lists differ; the pinned Claude Code build changes.
  3. The flag names where the evidence is (this ruling, spike R1.4, the canary); the run's proof record names the observed tools. No connector name goes in report source (R-6 condition 4).

## R-37 · 2026-09-25 · Owner seat (Fable) · DR-1: the scripted user is a bench-owned MCP `ask_user` tool, one prompt per cell

- **Ruling:** default taken. A scenario-1 cell gets one `session/prompt`; the scripted user is a bench-owned stdio MCP server passed in `session/new` `mcpServers` (today `[]`, `driver.py:236`), exposing one tool, `ask_user(question) → reply`. The reply is a matched clarification's text or exactly `Decide and state your assumption.` (spec US-10, `harness-bench.md:354`). Multi-turn is rejected for wave 2.
- **Reasoning:** `lifecycle.py:21` states `AT_MOST_ONCE` ("AtMostOnePrompt") and the TLA model checks it; a second prompt puts `lifecycle.py` and `models/**` on the critical path. A tool call is answered inside the one prompt, so the invariant, the end-of-turn kill (`phase1-walking-skeleton.md:500`) and R-21's grace are untouched; the matcher is synchronous (R-39), so no decision request opens. ADR-0004:51 bars "MCP servers other than the task's own"; this server is the task's own, identical for every harness and pack (US-14). Whether each adapter forwards `mcpServers` and whether the model calls the tool is unmeasured; USER-D's spike S-04 measures it.
- **Conditions:**
  1. USER-D records per harness, on the pinned builds: the `mcpServers` shape the adapter accepts, whether the tool appears in the native record, and whether one A1 turn calls it. A harness the tool never reaches returns as a decision request; nobody switches to multi-turn alone.
  2. The tool id joins each allowlist as a declared class, "scripted user", under R-34's class rule (ADR-0004 amendment note; the coverage test lists the id). Copilot's `--disable-builtin-mcps` (ADR-0004:58) is shown not to drop a session-supplied server.
  3. The server is present only when the task has `scripted_user: true`; every other cell keeps `mcpServers: []` (a driver test asserts both).
  4. The log records question, decision and reply per call; a turn with zero calls records "no question asked", never an empty file.
  5. `prompt.md` may name the tool; the text is identical across combos (US-10).

## R-38 · 2026-09-25 · Owner seat (Fable) · DR-2, DR-9, DR-10: the smoke run waits for USER-W; 36 cells; D1 on night 1

- **Ruling:** (DR-2) yes; no partial smoke run without A1. (DR-9) the matrix is the wave-1 combos `copilot-sol`, `codex-sol`, `cc-opus` (plan `:103`) × pack {on, off} × 1 rep × 6 tasks = 36 cells. (DR-10) yes, the row-15 D1 run is night 1.
- **Reasoning:** A1 unanswered voids US-31, and the smoke BOM is one task per scenario (spec `:184`); a 30-cell run is not the run R-9 rule 2 defines and spends a night's allowance on a result to be repeated (tokens rank above speed). Three combos cover all three harnesses, which is what phase 2 is named for (`architecture.md:257`); `cc-sonnet` adds 12 cells for no harness coverage and breaks comparability with the wave-1 baseline. Sizing by the spec's bound (`:293`, ⌈Σ÷p⌉ + max): 6 sets × 190 min = 1,140 min; at p=2, 630 min (10.5 h, Inferred; the draft's 9.5 h uses another formula) misses the 9-h window; at p=3, 440 min fits. So the cap raise is the gate, and R-9 rule 2 makes row 15 the trigger. D1 needs no STOP-I: `timed_out` exists (`status.py:31`), and plan `:175` binds only the smoke run to W2-STOP.
- **Conditions:**
  1. Night 1: D1 × three combos × pack {on, off} at parallelism 2 (6 cells), on a `ready` D1 with the dotnet runner joined (R-41); the headroom rule is written first (plan `:149`). R-9 rule 1 holds: Claude, Codex and Copilot workers at hand-back.
  2. The cap is raised to what the headroom rule supports (target 4, R-9 c1) by TASKS-b's last slice; `test_plan.py` asserts it. If only 2 is supported, the run splits 2 + 1 combos over two nights (24 then 12 cells), each with its own report (R-9 rule 2).
  3. R-19 c1 is read, not amended: cosmic-ray starts on night 1 only after the D1 run's last cell has an outcome and its samples are recorded.
  4. `cc-sonnet` (`claude-sonnet-5`, R-33) is a named next step: a matrix change for a later night, never a mid-run addition.
  5. If USER-W is not joined by night 2, the Leader reports the slip; nothing moves into the window.

## R-39 · 2026-09-25 · Owner seat (Fable) · DR-3: the wave-2 matcher is deterministic only

- **Ruling:** yes. Exact and normalised match are the only rungs; a miss sends the default reply and is recorded. No model rung before the ADR-0009 gateway (wave 3).
- **Reasoning:** ADR-0009 decides it ("In phase 2 that is the only rung"); `architecture.md:69` agrees. A model rung now needs the gateway's cache, blinding and egress gate, or a second copy of them. `low-confidence matcher` (US-31) is the spec's label below the S-04 threshold: a measurement, not a failure.
- **Conditions:**
  1. USER-D sets the S-04 threshold from the held-out measurement and records the numbers in the spike note; spec R10 closes by citation.
  2. The held-out and near-miss sets are authored by TASKS-a, not the matcher's author (plan `:146`).
  3. `matcher_version` is recorded on every match; the cache key is (question hash, matcher version) (spec `:210`, `:245`); a re-grade makes no new match (`:458`).
  4. Normalisation is one function with a test per rule; nothing fuzzy.

## R-40 · 2026-09-25 · Owner seat (Fable) · DR-4: E6 takes smoke slot 5 now; E1 is deferred; HARBOR is a spike

- **Ruling:** yes. E6 (native on the host's .NET, R-7) is the scenario-5 smoke task; E1 is deferred, not substituted. R-7 c5's trigger is applied now because the engine has no container path and building one is not a wave-2 row.
- **Reasoning:** R-7 c5 and plan `:147` name the swap; only the timing is new. W2-HARBOR stays, bounded to spike A6.
- **Conditions:**
  1. `bench/bom.yaml` becomes 0.3: E6 `smoke: true`, E1 `smoke: false`, note "E1 deferred: no container path in wave 2 (R-40)"; the report names the swap. E1's return is a further BOM version.
  2. HARBOR touches only its three owned paths; an engine change is a decision request. It is dispatched last and may slip to wave 3.
  3. The `assume:` on E1's budget stays open.

## R-41 · 2026-09-25 · Owner seat (Fable) · DR-5: the dotnet correctness runner is built in wave 2

- **Ruling:** yes, TASKS-b slice 1, red-first, before D1, F1 or E6 can be `ready`.
- **Reasoning:** `correctness.py:58-59` returns NA for every runner but `unittest`; D1, E6 and F1 are `language: csharp` (`task.yaml`), so three of six smoke tasks would grade NA.
- **Conditions:**
  1. A missing or unparsable summary is NA with a reason, never 0.
  2. The step runs in its own Job Object with the deadline and ADR-0013's build-server settings; a test proves no `dotnet` process outlives it.
  3. The runner records `dotnet --version` in the grading output (10.0.303 here, R-7).
  4. Mutants: zero tests read as pass, a summary from the wrong file, a timeout read as pass; each killed.

## R-42 · 2026-09-25 · Owner seat (Fable) · DR-6: vendor the base trees, conditionally

- **Ruling:** yes: D1 (ai-de), F1 and B1 (cfd-bench) base trees go under `tasks/<ID>/workspace/`; `source.commit` is provenance. Committing is confirmed only as far as the conditions verify, before the commit.
- **Reasoning:** `workspace.py:86` builds the task source from `tasks/<ID>/workspace`, so a vendored tree is what the engine expects; a pinned-clone mode is unbuilt and unowned. Licences as this host records them: `C:\projects\cfd-bench` has an MIT `LICENSE` (Copyright 2026 timianmalloo); `C:\projects\ai-de` `README.md:34-36`: application code MIT, installed pack material Apache 2.0. Neither `task.yaml` nor `bom.yaml` records a licence. Both repositories are the operator's (R-7); the bench repository is public (`origin` on GitHub), so vendored trees become public, the operator's existing choice for `tasks/**`, noted, not ruled.
- **Conditions:**
  1. The Leader reads the `LICENSE` at each pinned commit, records its SPDX id and copyright line in `task.yaml` (`source.license`) and copies the file into the workspace root (MIT's notice condition). No licence file at that commit: not committed; a decision request returns.
  2. The tree contains no pack: the US-9 marker scan (`bench/pack-markers.txt`) runs over the base tree in `bench validate` and must match nothing; ai-de's installed pack files are excluded on this rule.
  3. `source.commit` exists in the named repository (R-7 c1); the task folder lists the vendored paths; a test rebuilds the tree from `git archive <commit> -- <paths>` and asserts equality.
  4. `bin/`, `obj/`, caches and secrets are excluded; hidden tests never enter the tree (US-8). Reference solutions (`CFD-Bench-ClaudeCode`, `CFD-Bench-GHCP`, no licence file recorded) go only under `tests/` or `oracle/`.
  5. Plan `:148` holds: hidden tests fail on the base, pass on the reference.

## R-43 · 2026-09-25 · Owner seat (Fable) · DR-7, DR-8: CANARY on Grok; the R-36 count is an Extraction field and a proof figure, not a catalog metric

- **Ruling:** (DR-7) Grok, `grok-4.7`, effort high. R-36 item 4 ("on Claude Sonnet per R-29") is amended by reference: `qualify-7` re-qualified Grok 1.0.41 with the stipulated model, no `protocol_error`, and the R-29 hold lifted (run record, wave-1 close). (DR-8) the per-cell connector count is one `Extraction` field written by the Claude reader and reported in `docs/proof/phase2.md` beside the header flag; not a catalog measure in wave 2, no version bump.
- **Reasoning:** the R-4 fallback fired on failures revision 95 fixed and `qualify-7` re-measured; Sonnet spends the Anthropic allowance a run needs under R-9 rule 1, which Grok never touches. The count is a confound-size disclosure like N5's leaked set (R-5, R-6); a catalog column needs the wave-3 row (R-15 Q6) for a figure no comparison reads.
- **Conditions:**
  1. R-11 slice rules stay for Grok until a wave-2 slice records `total_output_bytes` under revision 95; the R-4 trigger stands.
  2. The field is null for an unreadable record, never 0; the red fixture holds two `mcp__claude_ai_*` tools.
  3. A wave-3 comparison that wants the count adds it to the catalog with Q6; until then no view reads it.


## R-44 · 2026-09-25 · Owner seat (Fable) · The wave-2 track table is plan version 4, with four amendments

- **Ruling:** accepted, subject to R-37..R-43 and:
  1. **W2-CANARY**: Grok `grok-4.7` (R-43); R-36's Sonnet line is superseded.
  2. **W2-HARBOR**: spike only, dispatched last, may slip (R-40 c2).
  3. **The Codex control**: the draft says three Codex tracks; the table has four (STOP-I, USER-W, TASKS-b, TASKS-c). The `git diff --stat` check applies to all four at every join until the operator's `/hooks` review qualifies the hook.
  4. **W2-TASKS-e** on Agy `gemini-3.8-flash-high`: accepted as the id `agy models` lists (`qualify-7`); the run record discloses generations on `gemini-3.8-flash`.
- **Reasoning:** every row stipulates a model (R-33), t0 is 5 live (the cap), the critical path is STOP-D → STOP-I → USER-W → smoke, and the windows follow R-9. Slice budgets stay Inferred; the run record replaces them.
- **Conditions:**
  1. The Leader commits this register entry, the version-4 table and BOM 0.3 together, recording planned versus actual per track.
  2. A track whose harness fails its first slice moves per R-4 on the measured evidence; no re-ruling.

## R-45 · 2026-09-25 · Owner seat (Fable) · Copilot cells expose web and GitHub-MCP tools as "safe": restore `--disable-builtin-mcps`, add an explicit `--available-tools` list, control it from the build's record, disclose wave 1

- **Ruling:**
  1. **(a) Profile.** `bench/profiles/copilot.yaml:7` gains `--disable-builtin-mcps` (ADR-0004:58, never removed) **and** `--available-tools powershell list_powershell read_powershell stop_powershell apply_patch view glob rg skill`. An allowlist, not `--excluded-tools`: the Claude Code shape (`claude-code.yaml:14`), failing closed on a tool a later build adds. `skill` is file-read class for Copilot (it delivers a workspace `SKILL.md`, `skill.context_delivered_ref`); `task`, `write_agent`, `read_agent`, `list_agents`, `sql`, `web_fetch`, `web_search` and every `github-mcp-server-*` id are out of profile. **Owner and timing:** STOP-I owns the file (plan `:158`) but has not started, so this is a **seam grant** on the `:214` precedent: one slice, Codex `gpt-6-sol` effort high (STOP-I's model, R-33), landing **before the D1 night-1 run** (R-38 c1 sends six Copilot cells that night), not merely before the smoke run.
  2. **(b) Control, two layers.** *Static:* a `tests/test_allowlist_classes.py`-style test for Copilot reads the advertised list from the pinned build's own record (`session.usage_checkpoint` → `data.promptCacheBreakState[0].models.<model>.tools`), classifies every id, asserts the `--available-tools` list covers each in-class id and nothing else, and asserts the list holds **no** out-of-profile id. Red today on the committed samples (21 ids, all `"safe": true`). *Per cell:* a validity finding in W2-VIEWS' HB-VAL family (`:159` (b) is its sibling): any `tool_calls` row of class `other` (`telemetry/copilot.py:64`, `claude_code.py:64`, `codex.py:55`) makes the cell `invalid (out-of-profile tool called)` on every harness; for Copilot the reader also records `tools_advertised` (null when unreadable, never `[]`) and an out-of-class name there is the same finding. The E2E asserts both.
  3. **(c) Wave 1 stands, disclosed, not re-run.** `phase2.md:173-190` keeps its numbers, with a disclosure beside the table: the Copilot cells ran with `web_search`, `web_fetch` and five GitHub-MCP tools available without a prompt; whether any was called is **not recorded** (run folder removed; `wave1-e2e-last.json` has no tool rows). ADR-0004:60's "fails closed and is recorded" is re-labelled **Inferred** for Copilot on that run. No re-run: the exit proved machinery, one rep, no interval (`:192`); the smoke run on the fixed profile supersedes it.
- **Reasoning:**
  - ADR-0004:49-52 denies web tools, foreign MCP servers and "any other tool the harness offers". The pack-on sample (`tests/fixtures/native/copilot/on/session-state/67b924b1-…/events.jsonl:123`) advertises 21 tools, every one `"safe": true`; pack-off (`…/off/…/events.jsonl:32`) 20, the difference being `skill`. Those cells called `glob`, `view`, `rg`, `skill` with zero permission lines, so a "safe" tool never reaches the driver's refusal. `test_walking_skeleton.py:84` and `us14_valid` (`copilot.py:161-167`) see only denials and successes; a `web_search` row passes both.
  - The pinned CLI offers the flags (`copilot --help`: `--disable-builtin-mcps`, `--available-tools`, `--excluded-tools`, `--deny-tool`). `assume:` `--available-tools` filters built-in and MCP ids alike; **confirm:** the qualification turn's advertised list; **breaks:** MCP ids survive, then `--excluded-tools web_search web_fetch` is added.
- **Conditions:**
  1. Red-first: the static test is red on the committed samples, green on a fixture recut from one qualification cell on the fixed profile, pack on, committed with the profile hash.
  2. The qualification turn exercises each listed id (ADR-0004:31) and records the version the session reports: the exe self-reports `1.0.89-3`, `package.json` says `1.0.89-1` (`tools.py:40,96` reads the latter); the Leader decides under R-12 which is the pin.
  3. From now on every E2E and smoke record keeps per-cell `tool_calls` names in the committed proof.
  4. ADR-0004 gains an amendment note citing this ruling, the Copilot row listing the flags verbatim; `docs/lessons/defect-classes.md` records the class "a tool that runs without a permission callback is invisible to a permission-count control".
  5. Finding: `Skill` is in Claude Code's `OUT_OF_PROFILE` (`test_allowlist_classes.py:43`) while Copilot's `skill` is allowed here. The qualification turn measures whether 2.1.282 prompts for `Skill`; if so, R-34's class rule decides before the smoke run.

## R-46 · 2026-09-25 · Owner seat (Fable) · The same class on Codex and Claude Code: Codex `web_search = "disabled"` red-first; Claude Code is allowlisted but unmeasured

- **Ruling:** **Codex has the gap in the profile.** ADR-0004:57 promises "per-cell `config.toml` with web search off"; `codex.yaml:8` writes only `model = "{model}"`, and the S-06 follow-up (ADR-0004:79) was never done. R-45's seam-grant slice adds `web_search = "disabled"` to the template. **Claude Code is allowlisted, not measured:** `WebFetch` and `WebSearch` are deferred ids (`tools-2.1.282-win32.jsonl:2`), in `OUT_OF_PROFILE`, absent from `claude-code.yaml:14`; the driver refuses a permission request (R-34's negative fixture proved the path). `assume:` both prompt in effective mode `default`; **confirm:** the ADR-0004:78 fixture's "web fetch refused and recorded"; **breaks:** either runs silently, then the allowlist is not the control and R-45's per-cell check is.
- **Reasoning:**
  - On the pinned Codex 0.156.0, `codex -c 'web_search="disabled"' doctor` loads the config and `web_search="nonsense"` fails to; `features list` shows `web_search_request` and `web_search_cached` deprecated, off. Key and value exist [Verified]; that it removes the tool is the qualification turn's to show.
  - A Codex cell runs `approval_policy: never`, `permission_profile: disabled` (`pack-on.jsonl` `turn_context`), so a web search never asks. `codex.py:37-38` reads only `custom_tool_call`, `function_call`, `local_shell_call`; the binary carries `web_search_call`, which the reader drops, so today a Codex web search leaves **no** `tool_calls` row.
- **Conditions:**
  1. Red-first: a profile test asserts the seeded `config.toml` contains `web_search = "disabled"`; a reader test feeds a synthetic `web_search_call` item and expects a `tool_calls` row of class `other`.
  2. One qualification turn per harness on the fixed profiles asks the agent to fetch a URL; the outcome per harness (absent from the list, refused, or prompted-and-refused) is recorded in `docs/proof/phase2.md` and closes ADR-0004:78.
  3. The Codex and Claude rows of ADR-0004 gain the R-45 c4 amendment note.
