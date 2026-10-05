---
id: coordination-eval-wave2-e1-briefs
title: "Wave 2 E1 dispatch pack: build briefs, routing, DAG and launch order (Evaluation Campaign)"
type: plan
status: proposed
owner: "@timianmalloo"
phase: "Enterprise evaluation: Wave 2, phase E1 (walking skeleton build)"
tags: [coordination, briefs, wave-2, e1, evaluation-campaign]
links:
  - { to: coordination-eval-campaign, rel: implements }
  - { to: design-eval-seam-contracts, rel: depends-on }
  - { to: coordination-eval-wave1-briefs, rel: relates-to }
  - { to: rulings-register, rel: depends-on }
review-by: "2026-10-17"
summary: >-
  The rules every E1 build worker follows, the routing of the fourteen E1 items to harness and pinned model (R-87,
  R-88 confirmed to Codex, R-91, R-92), the real dependency DAG, the launch order by critical path, the dispatch
  shape per track (one external turn red and green, or a Sonnet follow-on), and one brief per item. Nine briefs
  are written; five wait on designs that have not passed their gate. Part 2 (W0 rev 6, Coordinator session #6): the X-C, X-H1, X-H2, X-E and X-INT briefs, TOOL-GSM-B, the rev-6 alignment of part 1, the external compilations, the Grok transport finding, and the DAG and launch order as of 2026-10-03 evening.
---

# Wave 2 E1 dispatch pack

You were given a brief in this folder. Read this file, then your brief, then the design it names. All three bind you. Where they differ, your brief wins over this file, and **W0** (`docs/design/eval-seam-contracts.md`, rev 6 or later) wins over a design.

**Seats.** Leader `leader-e1e4` (epoch 13; merges, pushes, runs every external dispatch through `.tools/coord/runner-leader.sh`, R-87). Owner `owner-fable` (rulings into `docs/notes/rulings.md`). Coordinator `coord-opus-e1e4` (W0, seams, join review). If the epoch changes, stop at your next commit and report.

**Paths.** Primary checkout `C:\Projects\x-harness-x-model-bench` (`main`). On Windows use `python`, never `python3`. `C=docs/ai-forward-pack/scripts/coord-core.py`.

## 1. Start (Sonnet workers; external workers get the same lines from the runner)
1. `python docs/ai-forward-pack/scripts/audit-log.py start --session <your session> --skill implement`.
2. **Prefix every `git commit` and every coord call inline:** `AGENT_SESSION=<your session> git commit …` (class COORD-D: an `export` does not survive to the next tool call).
3. If your cwd is not your brief's tree: from the primary run `python $C worktree new --branch <your branch> --session <your session>` and use absolute paths into the printed tree. Never `coord install`, never `EnterWorktree`, never `checkout`/`switch` in the primary.
4. In the tree: `python $C doctor`. Check W0 rev 6 is in your base: `git log --oneline -1 --grep "W0 seam contracts rev 6"` prints a commit. If not, stop: "W0 rev 6 not on main". Then read W0's *Revision 6 change table* and its re-read row for your track.
5. Check every item of your brief's **Depends on** is on `main` (`git log --oneline main -- <path>`). If one is missing, stop and report which.

## 2. While working
- **Owned paths only** (your brief's list; the hub-file owner per W0 §13). A line in another owner's file is a seam request: `python $C request add --to coord-opus-e1e4 --deadline default --fallback "<what you do meanwhile>" "<ask>"`.
- **A request never parks you (rev 6.4, after X-D1).** The Coordinator runs as hand-back sessions, so a request may wait an hour. Your `--fallback` is the option you recommend, stated so it reaches green ("build the scans in `tests/import_graph.py`", never "keep it pending"). Build it in its own commit (also when it is the exact lines the request names in another owner's file), put the request id in the message, and finish the turn green. The join holds that branch until the request is resolved; if the ruling differs, the follow-on reverts that one commit. Stop red only when the fallback would change another track's behaviour, not just its lines.
- **Red first, observed.** Each behaviour lands as a red commit whose tests fail **on an assertion** (never `ImportError`/`AttributeError`/`NameError`: land a skeleton with final signatures and neutral wrong values first), then a green commit. Record in your report, per red commit: SHA, test node, the failing assertion line. The Wave 1 *Testability floor* (`docs/coordination/eval-wave1/README.md` §2a: failing assertion, red fixture for every guard, real-wiring test beside every fake, a mutant per adjacent rule pair, allowlists checked against the tree) applies to every test you write.
- **Commit named paths** (`git add <path>…`; never `-A`, `.` or `-a`). Each message ends with your model's `Co-Authored-By` line.
- **Shell shape (CT27).** A gate's exit status is never behind a pipe; a multi-line program is a file, then a run (no heredoc into Python).
- **No guessing.** Open it, run it, or write an inline `assume:` (belief, what confirms it, what breaks if false).
- **Fixture claims are measured (FIXT-A).** Every quantitative claim about a fixture's behaviour ("all 8 hidden tests fail on the base", "a crash flips every probe") is marked Inferred until a fixture run measures it, and your report gives the measured number beside the design's.
- **Never kill by name, pattern or command line; only PIDs you started (class PROC-A, Coordinator #13).** Many worktrees share this machine. `Stop-Process -Name`, a `Get-Process`/`Get-CimInstance` filter piped to `Stop-Process`, `taskkill /IM` or `/FI`, `pkill` and `killall` also kill other tracks' tests, agents and mutation runs (X-F F2 killed three trees' `mutate_check` runs and left their mutants applied). Keep the PID of what you start and stop that PID (`Stop-Process -Id`, `taskkill /PID … /T`). If a run of yours is stuck and you lost its PID, stop and report; never sweep. After any interrupted `mutate_check` in your tree, run `uv run python tools/mutate_check.py --restore`.
- **Real time in tests (TIME-B's scan, on `main`).** `tests/test_timing_hygiene.py` fails on a new `time.sleep`, a fake `sleep`/`delay` parameter or a wall-clock assert under `tests/` that is not in `TIMING_ALLOWED`. Prefer an event-driven wait or an injected clock. If a real wait must stay, add **one entry for your own test** with a reason a reviewer can check; that one-entry hunk is granted to every track (Coordinator #13). The scan's logic is TIME-B2's.
- **Defect classes** you find go to the Coordinator as text in your report; `docs/lessons/defect-classes.md` is Coordinator-owned.
- **Budget.** At 85 % of your brief's budget: commit, stop, report what remains. A budget firing is a defect signal (GO9).

## 3. The join gate (every track; run in your tree on your final commit, each on its own line)
```
uv run ruff check src tests tools
env -u HB_CLAUDE_OAUTH_TOKEN uv run pytest -q          # the full non-credential suite; PowerShell: Remove-Item Env:HB_CLAUDE_OAUTH_TOKEN -ErrorAction SilentlyContinue; uv run pytest -q
uv run python tools/mutate_check.py --touched main     # every mutant killed, or a recorded reason per survivor
python docs/ai-forward-pack/scripts/docs-graph.py validate
```
A track that touches `grade/`: the gate ring and stamp renewal, once per batch (the Leader). **Grok joins (R-92 condition 1):** `python tools/grok_served_model.py <the dispatch's session dir>` exits 0, and its output goes in the plan's Tracks row; a non-zero exit pauses Grok dispatch and the Coordinator raises a request. **R-103 (fail-fast, before the join):** the first assistant row's `model_id` is read within 120 s of `run` (by hand until TOOL-GSM-FIRST lands, then `python tools/grok_served_model.py --first --wait 120 …`); a non-`grok-4.7*` id kills the turn at once, it is retried once with the next contract suffix, a second drift sends that turn to Sonnet, and two consecutive exhausted retries pause Grok for E1. **On a deadline-killed session** the reader exits 2 "not recorded" today (`usage.json` is written only at a clean end; class OBS-A); until TOOL-GSM-B joins, the Leader reads the assistant rows' model ids in `chat_history.jsonl` and records that source in the Tracks row. **Codex and Agy joins:** the served model is read from the native record (Codex `~/.codex/sessions/…/rollout-*.jsonl` `model`; Agy `cli.log` model resolution), as Q0 did. The Coordinator re-runs at least one red SHA per track at the join.

**Open requests at every join (rev 6.4, class COORD-B second instance; the Leader).** Before each join and before each dispatch batch, the Leader runs `python $C request list` (open is the default). Any request to `coord-opus-e1e4` that is open → the Leader spawns a Coordinator hand-back session with those ids as its first item, before the batch. A branch whose commits name an open request id is not merged until it is resolved. X-D1's two requests went 25-32 min overdue with no Coordinator live; this is the control.

## 4. Report (final message, at most 12 lines)
Served model id (first line, R-91 c1) · branch and SHAs (red, green) · per red commit: node and failing assertion · join-gate results (each command's exit status, read from its own line) · acceptance items met / not met · seam requests raised · defect-class text · budget used (calls, tokens, wall) against the brief · what remains.

## 5. Routing (harness and pinned model, never a default)

**R-88 confirmed: X-A1 and X-D go to Codex.** R-88 condition 1: "(c) applies to a slice only when its design (W1-A, W1-D) passes its gate while B-1 is still open. If the operator clears B-1 and Q0 qualifies Codex 0.160.0 / `gpt-6.1-sol` (served id read back) before that moment, the slice goes to Codex as planned." Q0 qualified Codex at commit `6676e9d2` (2026-10-03T17:02Z, served `gpt-6.1-sol` read from the native record); W1-D's gate merge is `301a8705` (18:30Z) and W1-A's gate has not merged. Neither slice started on Sonnet.

| item | brief | session · branch | harness · model (pinned) | dispatch shape | brief status |
| --- | --- | --- | --- | --- | --- |
| TOOL-GSM served-model reader (R-92 c1) | `tool-gsm.md` | `x-gsm-e1e4` · `build/eval-grok-served-model` | Claude Code · Sonnet (`model: sonnet`, served `claude-sonnet-5-5`, R-91) | one Sonnet session | written |
| ENV-A ambient-credential fix | `env-a.md` | `x-enva-e1e4` · `build/eval-env-a` | Grok · `grok-4.7`, `--reasoning-effort high` | one turn, red and green | written; contract `env-a.contract.json` |
| X-G1 catalog 0.7.dev | `x-g1.md` | `x-g1-e1e4` · `build/eval-x-g1` | Grok · `grok-4.7` high | one turn, red and green | written; contract |
| X-B1 create_once, publish_dir, oslock helper | `x-b1.md` | `x-b1{a,b,c}-e1e4` · `build/eval-x-b1{a,b,c}` | Grok · `grok-4.7` high | three turns, each red and green, each joined before the next | written; contract (B1a) |
| X-H1 power, verdicts, gates | `x-h1.md` | `x-h1{a,b,c}-e1e4` · `build/eval-x-h1{a,b,c}` | Grok · `grok-4.7` high | three turns (power; then verdicts ∥ gates), 2,400 s each | written (part 2); contract `x-h1.contract.json` |
| X-A1 arms + ring plumbing | `x-a1.md` | `x-a1{a,b}-e1e4` · `build/eval-x-a1{a,b}` | Codex · `gpt-6.1-sol`, effort high (codex-cli 0.160.0) | two turns, each red and green | written; contract (A1a) |
| X-D identity + launch recheck | `x-d.md` | `x-d{1,2}-e1e4` · `build/eval-x-d{1,2}` | Codex · `gpt-6.1-sol` high | two turns, each red and green | written; contract (D1) |
| X-B2 crash-atomic archive | `x-b2.md` | `x-b2-e1e4` · `build/eval-x-b2` | Agy · `gemini-3.8-flash-high` | one turn, red and green | written; contract |
| X-C campaign record + CLI | `x-c.md` | `x-c{1,2,3}-e1e4` · `build/eval-x-c{1,2,3}` | Agy · `gemini-3.8-flash-high` | three turns | written (part 2); contract `x-c.contract.json` |
| X-H2 report section 3 | `x-h2.md` | `x-h2-e1e4` · `build/eval-x-h2` | Agy · `gemini-3.8-flash-high` | one turn | written (part 2); contract `x-h2.contract.json` |
| X-F property grader | `x-f.md` | `x-f-e1e4` · `build/eval-x-f` | Claude Code · Sonnet (`model: sonnet`, served `claude-sonnet-5-5`, R-91) | one Sonnet session, four commits groups, F0 joined early | written |
| X-I security task S1 | `x-i.md` | `x-i-e1e4` · `build/eval-x-i` | Claude Code · Sonnet (R-91) | one Sonnet session, then a follow-on after X-F joins | written |
| X-E discriminate, synthetic, readiness | `x-e.md` | `x-e-e1e4` · `build/eval-x-e` | Claude Code · Sonnet (R-91) | Sonnet session | written (part 2); W1-E gated (`2bd4401d`); RV-TA R2-1..R2-4 before the skeleton commit |
| X-INT E1 E2E | `x-int.md` | `x-int-e1e4` · `build/eval-x-int` | Claude Code · Sonnet (R-91) | Sonnet session | written (part 2); last |
| TOOL-GSM-B served-model fallback (class OBS-A) | `tool-gsm-b.md` | `x-gsmb-e1e4` · `build/eval-grok-served-model-b` | Claude Code · Sonnet (`model: sonnet`, served `claude-sonnet-5-5`, R-91) | one Sonnet session | written (part 2) |
| XPORT Grok `session/new` race (class XPORT-A) | — (Leader's brief) | `xport-grok-e1e4` · `fix/grok-session-new-race` | Claude Code · Sonnet | one Sonnet session, red first in `coord_transport.py` (repo-local pack deviation) | running (Leader) |
| TIME-B load-sensitive timing tests (defect class TIME-B) | `time-b.md` | `x-timeb-e1e4` · `build/eval-time-b` | Claude Code · Sonnet (`model: sonnet`, served `claude-sonnet-5-5`, R-91) | one Sonnet session | written (W0 rev 5 branch); **merged `8b4cce33`** |
| TIME-B2 the 13 unaudited real-time tests | `time-b2.md` | `x-timeb2-e1e4` · `build/eval-time-b2` | Claude Code · Sonnet (`model: sonnet`, served `claude-sonnet-5-5`, R-91) | one Sonnet session | written (Coordinator #13) |
| TOOL-GSM-FIRST `--first` read (R-103 c3) | `tool-gsm-first.md` | `x-gsmf-e1e4` · `build/eval-grok-served-model-first` | Claude Code · Sonnet (`model: sonnet`, served `claude-sonnet-5-5`, R-91) | one Sonnet session | written (Coordinator #13) |
| KILL-GUARD no kill by name (class PROC-A) | `kill-guard.md` | `x-killg-e1e4` · `build/eval-kill-guard` | Claude Code · Sonnet (`model: sonnet`, served `claude-sonnet-5-5`, R-91) | one Sonnet session | written (Coordinator #13) |

**Why "one turn, red and green" for external tracks.** The runner bases every dispatch on the primary checkout's HEAD (`coord-runner.py:426`; the Leader's wrapper `cd`s to the primary, Q0 README item 4), so a follow-on cannot start from an unmerged red tip. Each external dispatch therefore lands its red commit and its green commit in one turn. A dispatch that ends red-only (deadline, budget) is **not** re-dispatched externally: its green follow-on runs as a Claude Sonnet sub-agent in the same worker tree (R-87 Option 1), and the Tracks row says so. A multi-turn track joins each turn before the next is prepared.

**Contracts.** `*.contract.json` beside each external brief is a `coord-run/1` contract, copied from Q0's qualified workers (`docs/coordination/eval-q0/q0-contract.json`): the same argv, binding files and capabilities; the deadline from the plan (Grok 1,200 s; Codex and Agy 3,300 s). **Part 2:** a catalog-sized Grok turn needs more: X-G1's retry (`w2-g1b-e1e4`) committed red and green and was still killed at 1,200 s, so X-H1's turns get 2,400 s; short Grok turns (ENV-A, X-B1a..c) keep 1,200 s. Its `prompts` entry is **`COMPILE-OWED:<brief path>`**: before dispatch the Coordinator runs `/compile` on the brief (CO-S0) and replaces it with the compile-audit id. The runner refuses the placeholder (`RUN-COMPILE`), so an uncompiled brief cannot be dispatched. The Leader runs `prepare`, the attestation, `run`, `status` (R-87 condition 1) with `env -u XAI_API_KEY` for Grok.

## 6. The E1 DAG (real dependencies only)

A track starts when its design gate has passed, its design is on `main`, and every item it depends on has **joined `main`**.

| item | depends on (and why) |
| --- | --- |
| TOOL-GSM | — |
| X-D1 (errors rows, `CLASSES` seed, `tests/import_graph.py`, `test_architecture.py` entries, `catalog_hash` move) | W1-D ✓ |
| X-F0 (`grade/property.py` docstring skeleton) | W1-F ✓ |
| X-B1a (`atomic.py` core) | W1-B ✓; X-D1 (HB-LED-007 in the registry); TOOL-GSM (it is the second Grok dispatch, R-92) |
| X-I (author S1) | W1-I ✓ (probes through the real grader: X-F joined, in its follow-on) |
| ENV-A | TOOL-GSM (R-92: the reader exists before the second Grok dispatch) |
| X-G1 | W1-G ✓; **X-F0** (`validate_repo` refuses a metric whose grader has no module, W0 §7) |
| X-B1b (`publish_dir`, `workspace._land`, `test_atomic_sites.py`) | X-B1a |
| X-B1c (`oslock.acquire_then_probe`) | X-B1a (one Grok slot at a time is the cap, not a data edge) |
| X-D2 (manifest, launch recheck, `campaign_check=` keyword) | X-D1 |
| X-A1a (`config.py`, `plan.py` core) | W1-A ✓ (rev 2, `92e977b2`); X-D1 (HB-PLN rows in the registry) |
| X-A1b (readers, G1 guard, migrations, `pilot.yaml`, catalog checks) | X-A1a |
| X-F1..F3 (the grader) | X-F0; X-D1 (HB-CHK/HB-GRD rows, `SUBPROCESS_CALLERS`, `import_graph.py`, the `catalog_hash` hunk to rebase on); **X-G1** (the property tags `applicable` narrows on); X-B1b (the three `test_atomic_sites.py` entries it deletes); X-B1c (the grading-side probe) |
| X-B2 | X-B1b (`publish_dir`); X-D1 (codes) |
| XPORT fix (Grok `session/new` race) | — (running); **every Grok dispatch waits on it** (Leader, 2026-10-03: 2 of 3 Grok dispatches failed in under 10 s) |
| TOOL-GSM-B | — ; nothing waits on it (the Leader reads `chat_history.jsonl` meanwhile) |
| X-H1 | W1-H ✓; X-D1; X-G1; X-A1a (`plan.cell_arm`; the G1 guard forbids reading `pack`); XPORT fix; ADR-0020 Amendment 1 ✓; TOOL-GSM-FIRST (R-103 c3, before X-H1a) |
| X-C | W1-C ✓; X-B1c, X-D2, X-H1, X-A1b, X-F (the runner hook hunk is X-C's after X-F joins) |
| X-E | W1-E ✓ (`2bd4401d`); X-A1b, X-B1b, X-D2, X-G1, X-I ✓; X-F's `grade/_env.py` before the skeleton, X-F's host before T-E1b and T-E10..T-E13 (W1-E §15) |
| X-H2 | W1-H ✓; X-H1; X-C (built against fixtures of `campaign.read` until X-C joins) |
| TIME-B | X-D1 (it edits one function of X-D's `tests/test_engine.py`); nothing waits on it |
| TIME-B2 | TIME-B ✓; starts now; **joins after X-D2** (`tests/test_engine.py`, X-D's in E1) **and X-B1c** (`tests/test_oslock.py`); nothing waits on it |
| TOOL-GSM-FIRST | TOOL-GSM-B ✓; **X-H1a waits on it** (R-103 c3) |
| KILL-GUARD | — ; nothing waits on it |
| X-INT | every E1 item |

**Critical path (part 2; Inferred durations from the plan's budgets, which ran 2-14× long in phase 1):** every E1 design has passed its gate, so the path is now build-only. **XPORT fix → X-B1a → X-B1b → X-E (3.5 h) → X-INT (1.5 h) → demo**: the Grok transport race holds the three B1 turns, and X-B1b feeds X-E, X-F1..F3 and X-B2. Nearly as long: X-D1 → X-D2 → X-C (three Agy turns) → X-H2 → X-INT, and X-D1 → X-A1a → X-A1b → X-E. **Re-route trigger:** if the XPORT fix has not joined when X-D2 and X-A1b have, the B1 turns go to Sonnet under R-92 (the Leader decides).

## 7. Launch order (cap 6 running; at most 2 per external harness; critical path first)

**Precondition for every dispatch below (W0 rev 5 branch):** the branch `coord/eval-w0-rev5-wave2b` is merged, so `main` carries W0 rev 5 (README §1 step 4 greps for it), the aligned briefs, and the six `kind: compilation` entries the contracts name (the runner reads them from `docs/audit/audit-log.jsonl`).

**Batch 1 (the first dispatch batch, confirmed 2026-10-03 after F0 and TOOL-GSM merged):** running or startable now: X-F (Sonnet, running), X-D1 (Codex), X-I (Sonnet), X-G1 (Grok; F0 has joined), ENV-A (Grok; TOOL-GSM has joined, so R-92's reader exists for this second Grok dispatch). That is five; the sixth slot is X-A1a (Codex) when X-D1 joins. TOOL-GSM is done.

**Batch 1 as first planned (kept for the record; 5 start now, the 6th slot opens when X-D1 joins):**
1. **X-F** (Sonnet) — commit F0 first and ask the Leader to merge it at once (X-G1 waits on it).
2. **X-D1** (Codex) — every other code track needs its registry rows.
3. **TOOL-GSM** (Sonnet) — must join before the second Grok dispatch.
4. **X-I** (Sonnet) — feeds X-E.
5. **X-G1** (Grok, the first Grok dispatch) as soon as F0 has joined (minutes after X-F starts).
6. **X-A1a** (Codex) once X-D1 has joined.

**State at part 2 (2026-10-03 evening, from the Leader):** merged: X-F F0, TOOL-GSM, X-I (S1 through the stand-in host, still `stub`). Joining: X-G1 (red `a08a4060`, green `76deb253`). Running: X-D1 (Codex), X-F (Sonnet), XPORT fix (Sonnet). Waiting on the XPORT fix: ENV-A retry and every Grok track.

**Then, as slots free (critical path first; cap 6; at most 2 per external harness):** (1) TOOL-GSM-B (Sonnet, now; short). (2) X-A1a (Codex) when X-D1 joins, then X-D2 (Codex). (3) When the XPORT fix joins: X-B1a (Grok) → ENV-A retry (Grok) → X-B1b (Grok). (4) TIME-B (Sonnet, after X-D1). (5) X-A1b (Codex, after A1a). (6) X-B2 (Agy, after X-B1b) and X-B1c (Grok). (7) X-H1a (Grok, after X-G1 and X-D1), then X-H1b ∥ X-H1c. (8) X-E (Sonnet) as soon as X-A1b, X-B1b and X-D2 have joined and X-F's `_env.py` is on main. (9) X-C1..C3 (Agy, after X-B1c, X-D2, X-H1, X-A1b, X-F). (10) X-H2 (Agy). (11) X-INT (Sonnet).

## 8. Blockers and findings for the Leader
- **Part 2 (Coordinator session #6).** Every E1 design is gated (A, B, C, D, E, F, G, H, I). W0 rev 6 is on main (`1c9eaafc`). Briefs written: `x-c.md`, `x-h1.md`, `x-h2.md`, `x-e.md`, `x-int.md`, `tool-gsm-b.md`; part-1 briefs aligned to rev 6: `x-b1.md`, `x-a1.md`, `x-d.md`, `x-f.md` (X-F also gets X-I's six `assume:` names, the naive `0.3750` check on the real host, and the new `check.clauses` duty). *Erratum 1* in `docs/design/eval-security-tasks.md` (X-I's measured corrections).
- **Compile ids (part 2, CO-S0):** `C1` `al-01M41NR9YEHGCK0XN2QB83804H`, `C2` `al-01M41NRHZF6BP0CN92R6R35WV1`, `C3` `al-01M41NRJPH6Q66CZBXRFQHXZV7`, `X-H2` `al-01M41NRKDW17XAP6WS7AFPQF9K`, `H1a` `al-01M41NRM9X2NVDN5QASJ391EBH`, `H1b` `al-01M41NRN2E7T3EYKPQG5MA0GY5`, `H1c` `al-01M41NRNTRMPPATGS64P2FTP0V`, `B1a` `al-01M41NRPQMNPJXB170E87T32NE`, `B1b` `al-01M41NRQGXEH11C49W8B95C72K`, `B1c` `al-01M41NRRGFA4GC81E2TBSH0J91`, `A1a` `al-01M41NRSQN7CVAF72MCDF68X9E`, `A1b` `al-01M41NRTJE0W2ZY0HRSH4W71N8`, `D2` `al-01M41NRVGHHR6A5JN8SVGAH4D0`. B1a and A1a are **recompiled**: their part-1 prompts named rev-5 signatures (`sweep_temps(target, lock)`, `oslock.is_held(lock.path)`, the `config.HARNESSES` hunk); the part-1 ids for them are superseded, unused.
- **Grok transport race (XPORT-A, candidate, in the register):** the skills-reload acknowledgement can arrive before the `session/new` response; the runner tolerates it only inside `session/prompt`. 2 of 3 Wave 2 Grok dispatches failed this way in under 10 s. The fix is the Leader's Sonnet slice (`xport-grok-e1e4`), red first in `coord_transport.py`, a repo-local pack deviation; a push to ai-forward needs the operator. Grok tracks wait for it (not rerouted).
- **TOOL-GSM gap (OBS-A, candidate):** `tools/grok_served_model.py` exits 2 on a deadline-killed session; TOOL-GSM-B adds the `chat_history.jsonl` fallback.
- **FIXT-A (candidate):** W1-I stated fixture numbers nobody had run; section 2 now requires them marked Inferred until measured.
- **MUT-C (candidate, the Leader's own finding):** `mutate_check.py` under the global interpreter reported all 80 mutants as `error`. Section 3's line now reads `uv run python tools/mutate_check.py`; TOOL-GSM-B section B2 makes the tool refuse (exit 2, interpreter named) when it cannot import `harness_bench`.
- **W0 rev 6.1 (this branch):** the RV-TA and RV-SEC conditions on rev 6, all applied in W0 text and in the X-C, X-E, X-F, X-A1 and X-H briefs; RV-DS's rev 6 review is pending. W1-C contradicts W0 rev 6 in six places (OI-5 state, HB-CMP-004 for run locks, `plan_hash`, the reader carrier, who sweeps `bench/discrimination`, the non-measurement refusals); the X-C brief says W0 wins in each.
- **W1-J (E2) seams for pack part 3 or W0 rev 7.** SR-J2 (`req-01M41F2PAKH97KH6BDGXCTA1KK`; rev 4 granted "data rows only, no change to the checker's logic"): **ruled: RV-SIM's route first, then a bounded widening** (RV-TA W1-J merge blocker; RV-SIM W1-J alternative). The turn variants go in as data through the existing `WIDER` substitution (`{'NumTurns = 1': 'NumTurns = 2'}` per turn variant), not a new `TURN_VARIANTS` routing. Only the lines that cannot be data (the real design checked at two turns, and the turn witnesses, if `WIDER` cannot express them) are granted as logic; W1-J's gate revision lists each such line and why. Main's `tests/test_check_models.py` goes red the moment the `.tla` lands without them, so W1-J's author applies the change in W1-J's gate revision, and `models/run_lifecycle.tla`, `run_lifecycle.turns.cfg` and `tools/check_models.py` land in **one commit**; proof at merge: `tests/test_check_models.py` 7/7 and `check_models.py --quick` green on the merged tree. The test pin and the mapping rows are optional extras in that commit. W0 §13's row is amended in rev 7. SR-J1, SR-J3 and SR-J4 are **ruled in W0 rev 6.2** (§12, this branch): one `archive.append_missing_rows` owned by X-J1 (HB-LED-005 or HB-LED-008 by caller; X-K1's `recover_archive` calls it); `turns` entries `{n, prompt, sha256}`, checked at plan load; `job_active_baseline` read after the lazy helper spawns. W1-J §13's ADR-0015 amendments are for its gate, with RV-SIM's two notes: the 42-minute US-44 run is one-time evidence, never a ring member; the resume-owned model branches (`BetweenSnapped`, `ClassOf`'s else-branch) are marked provisional for W1-K. **For the X-J1 brief (pack part 3), conditions before X-J1:** `engine._after_append` resets the budget clock on every `cell.prompt_sent` (turn 2 gets a second budget); claude-code `acp_turn` spend counts only the last turn; the turn loop breaks before writing `cell.turn_ended` for a stopping turn (max_tokens, error, kill), so no turn row and no reason (RV-SRE, RV-PAT F2); `status.py:128` keeps the last `prompt_sent` per cell, so `bench status` restarts its clock at turn 2, and `status.py` is missing from W1-J's surface list; S-J2's copy cost is a floor (no fsync, no verify). W1-K is briefed after W1-J's gate.
- **W1-L rev 2 seams (resolved):** SR-L5 (`req-01M41MWN4RJHW0XPG2R5X1QHSM`) is an E4 follow-on of the E4 owners of `grade/property.py`/`bench_check.py`, not an X-F E1 item; SR-L6 (`req-01M41MWN84V40RJXYE2NA6KR8M`) granted: `_changes.line_delta` and `is_test_path` join X-J2's first E2 commit. Both enter W0 §13 with rev 7, after W1-L rev 2's gate.
- **Compile ids written (W0 rev 5 branch, CO-S0):** `x-d` `al-01M41JX06P8TETKP1XTWD8GP2F` (Codex template), `x-a1` `al-01M41JX1G7Z511DJZXRQE1DXC7` (Codex), `x-g1` `al-01M41JX2G67CJTAJEJJ6752NW9`, `x-b1` `al-01M41JX3PQW2EA9Z4KKSFW3764`, `env-a` `al-01M41JX4E3Y85MKT11APTKCMM2`, `x-b2` `al-01M41JX5J2A1XH7TZ7BTY8MW70` (Grok and Agy use the `claude-code` template: no Grok or Agy template exists, as Q0's compilation did). Each names its brief path in the goal; B1b, B1c, A1b and D2 each need their own compilation before dispatch (the contract is reused with a suffix, the prompt is not).
- **Coordinator #13 (2026-10-04, base `4561daea`, W0 rev 6.10, R-103).** On `main` since #12: R-103, X-B1a (`1d5e0490`; Grok **served `grok-4.6-build` x59**, joined per R-103), TIME-B (`8b4cce33`). No request to `coord-opus-e1e4` is open (`coord request list`: 0).
  - **Compiled now (CO-S0), dispatchable now:** **X-B1b** and **X-B1c**, Grok `grok-4.7` high, deadline **2,400 s**, each with R-103's first-response read (§3). The compile ids are in `x-b1b.contract.json` and `x-b1c.contract.json`, not here, so this file's hash in each compilation stays the hash the worker reads. Disjoint files: they may run together (2 Grok slots).
  - **Dispatchable now, Sonnet (no compile):** TOOL-GSM-FIRST (before X-H1a), KILL-GUARD, TIME-B2 (starts now, joins after X-D2 and X-B1c), and the X-I-S2 spike redo under R-99 (E2-E4 pack; not re-dispatched since the stopped spike `a4b1b101`).
  - **Order under the cap:** X-B1b ∥ X-B1c (critical path: B1b feeds X-E, X-F's RF-9 commit and X-B2; B1c feeds X-F F3 and X-C) → TOOL-GSM-FIRST → KILL-GUARD → TIME-B2 → X-I-S2.
  - **Blocked, by join:** X-H1a on X-A1a and TOOL-GSM-FIRST (compile at A1a's join; its part-2 compile predates this README). X-B2 on X-B1b (recompile at that join: `al-01M41JX5…` predates rev 6.10). X-LB0 on X-F whole (F2 and F3 still write `grade/property.py`, the file LB0 edits; F3 needs X-B1b and X-B1c). X-K2a on X-C and X-J1 (`last_progress_at` is a `status.py` hunk read through X-J1's cell-start definition, R6.5b); a split that dispatches only `tools/alarm-task.ps1`, its test and the runbook has no code dependency and could use the idle Agy slot, but W0 §13 names those paths "second dispatch", so it needs a W0 edit: the Leader's call, by request. X-A1b on X-A1a; X-E on X-A1b, X-B1b, X-D2; X-C on X-B1c, X-D2, X-H1, X-A1b, X-F; X-H2 on X-H1, X-C. X-LB1 and X-RS on the operator's SP-LB run (B-2).
  - **Classes:** SERVE-A registered `observed` (R-103 c5; four instances), with a RUL-A instance for R-92 c3's missing entry; PROC-A registered (X-F F2's machine-wide pytest kill) with the §2 rule above and the KILL-GUARD hook. **Owed:** the next W0 revision says how ruling conditions are tracked to a commit (R-103 c5).
- **Coordinator #14a (2026-10-04, base `fec54563`, W0 rev 6.10, Leader epoch 17).** On `main` since #13: X-B1b (`d162dc42`), X-B1c (`f301a6fb`), X-D2 (`d3f5dd45`), X-A1a + A1af (`3d71d594`), X-F whole incl. F3a/F3b and the JOB-A sweep guard (`a03b849f`), TIME-B2 (`f8a10d75`), KILL-GUARD (`cb02bb90`), TOOL-GSM-FIRST (`5b80d39f`), the S2 spike and its RV-SEC/RV-TA reviews (`18bdce7e`, `e2af2692`), the integration fix (`d9155f86`). No request to `coord-opus-e1e4` is open.
  - **Compiled now (CO-S0), dispatchable now:** **X-A1b** (Codex `gpt-6.1-sol` high, 3,300 s, `x-a1b.contract.json`, new: `x-a1.contract.json` with the suffix `b`); **X-H1a** (Grok `grok-4.7` high, 2,400 s, R-103 first-response read, `x-h1.contract.json`); **X-B2** (Agy `gemini-3.8-flash-high`, 3,300 s, `x-b2.contract.json`); **X-J2a** (Agy, E2, 3,300 s, `docs/coordination/eval-wave2-e234/x-j2.contract.json`, recompiled). The compile ids are in the contracts, not here (#13's rule). Two Agy slots: X-B2 and X-J2a.
  - **Facts the compilations carry (checked on `fec54563`):** A1af already moved `views.py:525` to `plan.cell_arm`, so A1b's `views.py` work is the kind refusal only (item 12). A1b's other sites moved: `grade/_changes.py:86`, `report/pack_improvement.py:747`, `board.py:756-757`, `report/summaries.py:177`, `cli.py:146-149`. The two `validate_catalog` checks (`property:` tag, `also_graded_by`) are not in A1a's `config.py`, so they are A1b's; the strict xfail at `tests/test_catalog_version.py:746` (X-G1's file) passes once they land, so its marker removal goes by §2 (request plus fallback commit). `archive.make_writable` is still its own definition on `main`; W0 §4 says archive re-exports `atomic.make_writable`, so X-B2 makes it one. `power.py` is in `identity.PLANNED`: the X-H1a commit that lands it deletes that key (R6.10a).
  - **Hub file `grade/_changes.py`:** A1b's line-86 migration and J2a's four new functions are disjoint hunks (W0 §13). Part 3's §3 names "X-A1a (line 84)" for J2a, but that G1 migration is A1b's (`x-a1.md` item 13). Both may run at once; whichever joins second rebases.
  - **G1 ratchet at A1b's join:** A1b pins the `pack`-token counts on its base. A track joining first that adds or removes a `pack` token under `src/harness_bench/` moves them, so the Leader re-runs `test_pack_hits_equal_the_pinned_counts` on the merged tree.
  - **Order under the cap:** X-A1b (feeds X-E, X-C, X-A3) ∥ X-H1a (feeds H1b ∥ H1c, then X-C, X-H2) ∥ X-B2 (feeds X-J1) ∥ X-J2a (feeds X-LG, the X-SM `ready`). H1b and H1c are compiled when H1a joins.
- **Defect register finding (closed, W0 rev 5 branch):** the duplicate `ENV-A` (the ambient-credential candidate) is renamed **ENV-C**, because `ENV-B` already exists (`docs/lessons/defect-classes.md`, the build-environment class). The ENV-A track keeps its brief name and cites ENV-C.
