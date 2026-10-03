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
  are written; five wait on designs that have not passed their gate.
---

# Wave 2 E1 dispatch pack

You were given a brief in this folder. Read this file, then your brief, then the design it names. All three bind you. Where they differ, your brief wins over this file, and **W0 rev 5** (`docs/design/eval-seam-contracts.md`) wins over a design.

**Seats.** Leader `leader-e1e4` (epoch 13; merges, pushes, runs every external dispatch through `.tools/coord/runner-leader.sh`, R-87). Owner `owner-fable` (rulings into `docs/notes/rulings.md`). Coordinator `coord-opus-e1e4` (W0, seams, join review). If the epoch changes, stop at your next commit and report.

**Paths.** Primary checkout `C:\Projects\x-harness-x-model-bench` (`main`). On Windows use `python`, never `python3`. `C=docs/ai-forward-pack/scripts/coord-core.py`.

## 1. Start (Sonnet workers; external workers get the same lines from the runner)
1. `python docs/ai-forward-pack/scripts/audit-log.py start --session <your session> --skill implement`.
2. **Prefix every `git commit` and every coord call inline:** `AGENT_SESSION=<your session> git commit …` (class COORD-D: an `export` does not survive to the next tool call).
3. If your cwd is not your brief's tree: from the primary run `python $C worktree new --branch <your branch> --session <your session>` and use absolute paths into the printed tree. Never `coord install`, never `EnterWorktree`, never `checkout`/`switch` in the primary.
4. In the tree: `python $C doctor`. Check W0 rev 5 is in your base: `git log --oneline -1 --grep "W0 seam contracts rev 5"` prints a commit. If not, stop: "W0 rev 5 not on main".
5. Check every item of your brief's **Depends on** is on `main` (`git log --oneline main -- <path>`). If one is missing, stop and report which.

## 2. While working
- **Owned paths only** (your brief's list; the hub-file owner per W0 §13). A line in another owner's file is a seam request: `python $C request add --to coord-opus-e1e4 --deadline default --fallback "<what you do meanwhile>" "<ask>"`.
- **Red first, observed.** Each behaviour lands as a red commit whose tests fail **on an assertion** (never `ImportError`/`AttributeError`/`NameError`: land a skeleton with final signatures and neutral wrong values first), then a green commit. Record in your report, per red commit: SHA, test node, the failing assertion line. The Wave 1 *Testability floor* (`docs/coordination/eval-wave1/README.md` §2a: failing assertion, red fixture for every guard, real-wiring test beside every fake, a mutant per adjacent rule pair, allowlists checked against the tree) applies to every test you write.
- **Commit named paths** (`git add <path>…`; never `-A`, `.` or `-a`). Each message ends with your model's `Co-Authored-By` line.
- **Shell shape (CT27).** A gate's exit status is never behind a pipe; a multi-line program is a file, then a run (no heredoc into Python).
- **No guessing.** Open it, run it, or write an inline `assume:` (belief, what confirms it, what breaks if false).
- **Defect classes** you find go to the Coordinator as text in your report; `docs/lessons/defect-classes.md` is Coordinator-owned.
- **Budget.** At 85 % of your brief's budget: commit, stop, report what remains. A budget firing is a defect signal (GO9).

## 3. The join gate (every track; run in your tree on your final commit, each on its own line)
```
uv run ruff check src tests tools
env -u HB_CLAUDE_OAUTH_TOKEN uv run pytest -q          # the full non-credential suite; PowerShell: Remove-Item Env:HB_CLAUDE_OAUTH_TOKEN -ErrorAction SilentlyContinue; uv run pytest -q
uv run python tools/mutate_check.py --touched main     # every mutant killed, or a recorded reason per survivor
python docs/ai-forward-pack/scripts/docs-graph.py validate
```
A track that touches `grade/`: the gate ring and stamp renewal, once per batch (the Leader). **Grok joins (R-92 condition 1):** `python tools/grok_served_model.py <the dispatch's session dir>` exits 0, and its output goes in the plan's Tracks row; a non-zero exit pauses Grok dispatch and the Coordinator raises a request. **Codex and Agy joins:** the served model is read from the native record (Codex `~/.codex/sessions/…/rollout-*.jsonl` `model`; Agy `cli.log` model resolution), as Q0 did. The Coordinator re-runs at least one red SHA per track at the join.

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
| X-H1 power, verdicts, gates | `x-h1.md` | — | Grok · `grok-4.7` high | three turns (power; then verdicts ∥ gates) | **owed**: W1-H rev 2 not passed |
| X-A1 arms + ring plumbing | `x-a1.md` | `x-a1{a,b}-e1e4` · `build/eval-x-a1{a,b}` | Codex · `gpt-6.1-sol`, effort high (codex-cli 0.160.0) | two turns, each red and green | written; contract (A1a) |
| X-D identity + launch recheck | `x-d.md` | `x-d{1,2}-e1e4` · `build/eval-x-d{1,2}` | Codex · `gpt-6.1-sol` high | two turns, each red and green | written; contract (D1) |
| X-B2 crash-atomic archive | `x-b2.md` | `x-b2-e1e4` · `build/eval-x-b2` | Agy · `gemini-3.8-flash-high` | one turn, red and green | written; contract |
| X-C campaign record + CLI | `x-c.md` | — | Agy · `gemini-3.8-flash-high` | three turns | **owed**: W1-C rev 2 (PAT BLOCK) |
| X-H2 report section 3 | `x-h2.md` | — | Agy · `gemini-3.8-flash-high` | one turn | **owed**: W1-H rev 2 |
| X-F property grader | `x-f.md` | `x-f-e1e4` · `build/eval-x-f` | Claude Code · Sonnet (`model: sonnet`, served `claude-sonnet-5-5`, R-91) | one Sonnet session, four commits groups, F0 joined early | written |
| X-I security task S1 | `x-i.md` | `x-i-e1e4` · `build/eval-x-i` | Claude Code · Sonnet (R-91) | one Sonnet session, then a follow-on after X-F joins | written |
| X-E discriminate, synthetic, readiness | `x-e.md` | — | Claude Code · Sonnet (R-91) | Sonnet session | **owed**: W1-E not designed |
| X-INT E1 E2E | `x-int.md` | — | Claude Code · Sonnet (R-91) | Sonnet session | **owed**: last; written when X-C and X-E briefs are |
| TIME-B load-sensitive timing tests (defect class TIME-B) | `time-b.md` | `x-timeb-e1e4` · `build/eval-time-b` | Claude Code · Sonnet (`model: sonnet`, served `claude-sonnet-5-5`, R-91) | one Sonnet session | written (W0 rev 5 branch) |

**Why "one turn, red and green" for external tracks.** The runner bases every dispatch on the primary checkout's HEAD (`coord-runner.py:426`; the Leader's wrapper `cd`s to the primary, Q0 README item 4), so a follow-on cannot start from an unmerged red tip. Each external dispatch therefore lands its red commit and its green commit in one turn. A dispatch that ends red-only (deadline, budget) is **not** re-dispatched externally: its green follow-on runs as a Claude Sonnet sub-agent in the same worker tree (R-87 Option 1), and the Tracks row says so. A multi-turn track joins each turn before the next is prepared.

**Contracts.** `*.contract.json` beside each external brief is a `coord-run/1` contract, copied from Q0's qualified workers (`docs/coordination/eval-q0/q0-contract.json`): the same argv, binding files and capabilities; the deadline from the plan (Grok 1,200 s; Codex and Agy 3,300 s). Its `prompts` entry is **`COMPILE-OWED:<brief path>`**: before dispatch the Coordinator runs `/compile` on the brief (CO-S0) and replaces it with the compile-audit id. The runner refuses the placeholder (`RUN-COMPILE`), so an uncompiled brief cannot be dispatched. The Leader runs `prepare`, the attestation, `run`, `status` (R-87 condition 1) with `env -u XAI_API_KEY` for Grok.

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
| X-H1 | W1-H rev 2 passed; X-D1; X-G1 |
| X-C | W1-C rev 2 passed; X-B1c, X-D2, X-H1, X-A1b, X-F (the runner hook hunk is X-C's after X-F joins) |
| X-E | W1-E passed; X-A1b, X-B1b, X-D2, X-F, X-G1, X-I |
| X-H2 | W1-H; X-H1; X-C (built against fixtures of `campaign.read` until X-C joins) |
| TIME-B | X-D1 (it edits one function of X-D's `tests/test_engine.py`); nothing waits on it |
| X-INT | every E1 item |

**Critical path (Inferred durations from the plan's budgets, which ran 2-14× long in phase 1):** W1-E design (not started) → X-E (3.5 h) → X-INT (1.5 h) → demo. In parallel and nearly as long: X-F0 → X-G1 (0.7 h) → X-F1..F3 (4 h) → X-E. **W1-E is now the E1 critical path.** The second chain is X-D1 → X-D2 → X-C (W1-C rev 2) → X-H2.

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

**Then, as slots free (in this order):** X-B1a (Grok, after X-D1 and TOOL-GSM) → X-D2 (Codex) → X-B1b (Grok) → X-B2 (Agy, after X-B1b) → X-B1c (Grok) → TIME-B (Sonnet, after X-D1) → X-A1b (Codex) → X-H1 (Grok, after W1-H rev 2) → X-C (Agy, after W1-C rev 2 and its deps) → X-E (Sonnet, after W1-E) → X-H2 (Agy) → X-INT (Sonnet). At most two Grok dispatches run at once; X-B1a..c and ENV-A are short.

## 8. Blockers and findings for the Leader
- **W1-E has no design yet**, and X-E is on the E1 critical path. Start W1-E next.
- **W1-C carries an RV-PAT BLOCK** (no re-pilot path after a fix in `registered`); its rev 2 can rely on W0 rev 4's rulings listed in the rev-4 change table. X-C's brief is written after its gate.
- **W1-H rev 2** must apply R-96 and W0 rev 4 §8 before X-H1 and X-H2 briefs; **ADR-0020 Amendment 1** (commit on this branch) must be on `main` before X-H1's first commit.
- **Compile ids written (W0 rev 5 branch, CO-S0):** `x-d` `al-01M41JX06P8TETKP1XTWD8GP2F` (Codex template), `x-a1` `al-01M41JX1G7Z511DJZXRQE1DXC7` (Codex), `x-g1` `al-01M41JX2G67CJTAJEJJ6752NW9`, `x-b1` `al-01M41JX3PQW2EA9Z4KKSFW3764`, `env-a` `al-01M41JX4E3Y85MKT11APTKCMM2`, `x-b2` `al-01M41JX5J2A1XH7TZ7BTY8MW70` (Grok and Agy use the `claude-code` template: no Grok or Agy template exists, as Q0's compilation did). Each names its brief path in the goal; B1b, B1c, A1b and D2 each need their own compilation before dispatch (the contract is reused with a suffix, the prompt is not).
- **W1-C and W1-H have passed their gates** (Leader, 2026-10-03): the X-C, X-H1 and X-H2 briefs are pack part 2, with X-E and X-INT (X-E after W1-E's gate, which waits on W0 rev 5).
- **Defect register finding (closed, W0 rev 5 branch):** the duplicate `ENV-A` (the ambient-credential candidate) is renamed **ENV-C**, because `ENV-B` already exists (`docs/lessons/defect-classes.md`, the build-environment class). The ENV-A track keeps its brief name and cites ENV-C.
