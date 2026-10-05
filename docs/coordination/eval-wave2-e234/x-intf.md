---
id: brief-eval-x-intf
title: "Brief X-INTF: X-INT's three follow-ons - run_side_check on a plan without a campaign block, the EV-18 cell id in status.text, campaign commands honour --runs (Sonnet)"
type: plan
status: proposed
owner: "@timianmalloo"
links:
  - { to: coordination-eval-wave2-e234-briefs, rel: implements }
  - { to: coordination-e2e4, rel: implements }
  - { to: brief-eval-x-int, rel: depends-on }
  - { to: design-eval-seam-contracts, rel: depends-on }
  - { to: design-eval-discriminate, rel: depends-on }
  - { to: design-eval-power-verdicts, rel: depends-on }
review-by: "2026-10-19"
summary: "X-INTF fixes the three src/ findings X-INT recorded as strict-xfail legs: campaign.run_side_check refuses a non-measurement plan with no campaign block (HB-CMP-010, SR-E3), status.text names a blocked cell with its id and cause (EV-18), and the campaign commands read the --runs folder instead of <root>/runs. One Sonnet session, dispatched only after X-J1a joins (the status.py order); markers :471 and :591 in tests/test_e1_e2e.py are removed when their legs pass (Coordinator #30). Coordinator #32 adds finding 4, the R-106 c7 loop-back (W0 rev 6.11 section 6 F-1 and F-2 in campaign._tree_run_diff, with a cross-owner attach-vs-launch_check test), because X-INTF already owns campaign.py this phase."
---

# X-INTF: X-INT's three follow-ons

Written by Coordinator #30 on `coord/eval-c30-t0` at `37ec0585` (`integrate/e2e4-18`), from X-INT's three strict-xfail reasons (`tests/test_e1_e2e.py`, joined at `13db8d6f`) and the plan's track X-INTF (`docs/coordination/coordination-e2e4.md`). Three struck follow-ons were merged into this one session (plan, Struck tracks). Where this brief differs from `docs/coordination/eval-wave2-e1/README.md` sections 1-4, this brief wins.

## Seat and tree
- **Seat:** Claude Code Agent tool, `model: sonnet`, served `claude-sonnet-5-5` expected (R-91). The served id is the first line of your report.
- **Session** `x-intf-e1e4` · **branch** `build/eval-x-intf` · no contract file.
- **Dispatch order:** only after **X-J1a has joined** the integration branch. `status.py`'s owner sequence is X-J1a (`build()`, the cell clock) → X-INTF → X-K2b (plan, Hub files; serial spine 5).
- **Base:** the integration head at dispatch, never `main`. From the primary: `python docs/ai-forward-pack/scripts/coord-core.py worktree new --branch build/eval-x-intf --session x-intf-e1e4 --base <integration head>`. Record the base SHA. Work only in the printed tree by absolute path. Never `EnterWorktree`; never checkout or switch in the primary. `AGENT_SESSION=x-intf-e1e4` inline on every commit and coord call.
- **Leader** `leader-e1e4`, epoch 18. **Owner** `owner-fable`.

## Preconditions (each on its own line; stop and report if one fails)
1. `git merge-base --is-ancestor 13db8d6f HEAD` (X-INT's merge).
2. `git log --oneline -1 --merges --grep "X-J1a"` prints a merge commit (X-J1a joined).
3. `git log --oneline -1 --grep "W0 seam contracts rev 6.11"` prints a commit (Coordinator #32; README section 1 step 4).

## The three findings (state read by Coordinator #30 at `37ec0585`; re-read each on your base)
1. **`run_side_check` on a plan with no campaign block** (marker `tests/test_e1_e2e.py:471`, item 5, T-E19 parameter `campaign.run_side_check`). `campaign.run_side_check` (`src/harness_bench/campaign.py:1335`) returns `None` when the plan has no campaign block, so a real discrimination plan is not refused there. W0 SR-E3 (1), rev 6.1 (`docs/design/eval-seam-contracts.md:392`): every reader that takes a run id refuses a run whose kind is not `measurement`, naming the kind, through `plan.kind_of` (`src/harness_bench/plan.py:197`); the campaign commands, `campaign.run_side_check` included, with HB-CMP-010. **The fix:** the kind check through `plan.kind_of` comes before the "no campaign block" return. A measurement plan with no campaign block (an ordinary `bench run`) still returns `None`: test both.
2. **The EV-18 cell id in `status.text`** (marker `:591`, item 10, X-H2 item 9). `bench run` prints `status.text(status.build(run_dir))` (`src/harness_bench/cli.py:305`). `status.text` (`src/harness_bench/status.py:193`) prints `Causes` as counts per code and names no cell, so a blocked cell is never named. The leg asserts the blocked cell's id and `build changed` in the printed summary. **The fix:** the summary names each blocked cell with its id and cause, from the cell views `build()` already reads. If `Status` gains a field, `to_json` and `parse` change in the same commit, and `tests/test_status.py` pins the new key. A reader of the status JSON outside your owned paths that breaks (the `start-benchmark` skill source, for one) is a seam request.
3. **Campaign commands ignore `--runs`.** `cli.main` defaults `args.runs` to `<root>/runs` (`cli.py:681`), but the campaign handlers (`cli.py:59-142`) pass only `Path(args.root)`, and `campaign.py` builds `root / "runs" / <run>` itself at `:722`, `:724`, `:1314`, `:1431`, `:1479`, `:1516` and `:1610`. X-INT worked around it (`tests/test_e1_e2e.py:117`: "campaign commands read root/runs, so the walk's runs live there"). **The fix:** the campaign functions take the runs folder, and the handlers pass `Path(args.runs)`; one definition of the runs folder per call (no second default inside `campaign.py`). The plan's *assume:* "the fix is in `cli.py`'s campaign dispatch" is answered: it is in **both** files (the handlers and the seven `campaign.py` sites).
4. **The R-106 c7 loop-back: W0 rev 6.11 §6 findings F-1 and F-2** (added by Coordinator #32 at `86026384`; named **W0-F1** and **W0-F2** here so they do not clash with this brief's acceptance labels). `campaign._tree_run_diff` (`src/harness_bench/campaign.py:1246-1250`) iterates the effective run side's keys only. **W0-F1:** a run-side key that the tree has and the stamp lacks (a run-class `src/` file landing mid-campaign, `resume.py` for one) passes `attach` and `plan --campaign`, and then `identity.launch_check` (`src/harness_bench/identity.py:237`) diffs it as "added" and stops the first launch tick with HB-IDN-001. **W0-F2 (latent):** a `builds/<h>` key the stamp holds and the plan lacks is skipped by `_tree_run_diff`, while `launch_check` keeps it and diffs it as "removed" (R-106 c1). **The fix (W0 rev 6.11 §6, the route sentence):** `_tree_run_diff` compares over `wanted.keys() ∪ tree.keys()`, keeping R-106's builds rule (a stamp build key the plan lacks is a difference). **The cross-owner test (INT-A's control):** a tree with one added run-class file is refused by `attach` (HB-CMP-010) naming the same key that `launch_check` names, through the real `attach` and the real `launch_check`, with no raw-row fixture. No Owner decision is needed: R-106 already fixes the key set. **Why this is X-INTF's and not a separate track (Coordinator #32):** X-INTF owns `campaign.py` this phase (one owner per file per phase). `_tree_run_diff` (`:1246`) sits between the `--runs` site in `attach` (`:1314`) and `run_side_check` (`:1335`), and its test goes through the same `attach` that finding 3 re-plumbs. A second track on the same file would wait behind this one anyway and would need its own dispatch, join and rebase.

## Owned paths
`src/harness_bench/campaign.py` (the `run_side_check` hunk and the runs-folder parameter), `src/harness_bench/status.py` (the EV-18 hunk, after X-J1a's join), `src/harness_bench/cli.py` (the campaign handlers `cmd_campaign_*` only; X-TE9 owns `cmd_validate`, X-K1 the `cmd_run` resume branch), `tests/test_campaign.py`, `tests/test_cli_campaign.py`, `tests/test_status.py`, your own entries in `tests/mutations/{campaign,status,cli}.json`, and in `tests/test_e1_e2e.py` only the `:471` and `:591` strict-xfail markers (pre-granted by the plan). Not yours: every other file. A line in another owner's file is a seam request: `python docs/ai-forward-pack/scripts/coord-core.py request add --to coord-opus-e1e4 --deadline default --fallback "<what you build meanwhile>" "<ask>"`; build the fallback in its own commit that names the request id and finish green (README section 2).

## Acceptance items
- **F-1.** `campaign.run_side_check` refuses a non-measurement plan with HB-CMP-010 naming the kind, through `plan.kind_of`; a measurement plan with no campaign block returns `None`. The `:471` parameter passes with its marker removed. Mutant: skip the kind check (the `:471` parameter and your unit test go red).
- **F-2.** One blocked cell is named with its id and cause in the `bench run` summary; the `:591` leg passes with its marker removed. Mutant: drop the cell id from the line.
- **F-3.** A campaign command given `--runs <dir>` outside `<root>` reads that dir: a test through `cli.main` attaches a run that exists only under `<dir>`. Without `--runs` the default `<root>/runs` still applies. Mutant: a handler passes `<root>/runs` instead of `args.runs`.
- **F-5 (W0-F1, W0-F2; Coordinator #32).** A tree with one added run-class file is refused by `attach` with HB-CMP-010 naming the key that `launch_check` names (the cross-owner test); a stamp `builds/<h>` key the plan lacks is named by `_tree_run_diff` as `launch_check` names it. Mutant: `_tree_run_diff` iterating `wanted` only (the cross-owner test goes red).
- **F-4.** Every mutation `find` your edits move, in any `tests/mutations/*.json`, is retargeted and named in your report (MUT-E). No `pack`, `on` or `off` literal is added (the G1 guard).

## Red first (README section 2)
A skeleton commit first (final test names; neutral values that fail by assertion, RED-C), with the guard list run on it. Then each red test failing **on an assertion**; a test that already passes is recorded "green on arrival", never faked red. Then green. Report the SHA, node and failing assertion per red commit.

## Gate (R-104: own files and own mutations only; each command on its own line, exit status read, never behind a pipe)
1. `uv run pytest -q tests/test_architecture.py tests/test_identity.py tests/test_atomic_sites.py tests/test_arms_guard.py tests/test_discriminate.py tests/test_mutate_check.py tests/test_skills_in_sync.py tests/test_timing_hygiene.py` (the guard list, on the skeleton commit and on the final commit)
2. `uv run pytest -q tests/test_campaign.py tests/test_cli_campaign.py tests/test_status.py tests/test_e1_e2e.py`
3. `uv run python tools/mutate_check.py tests/mutations/campaign.json`, then the same for `status.json` and `cli.json` (your own mutation files; never `--touched`)
4. `uv run ruff check src tests tools`
5. `python docs/ai-forward-pack/scripts/docs-graph.py validate`

Never kill a process by name or pattern, only PIDs you started; after an interrupted `mutate_check`, run `uv run python tools/mutate_check.py --restore`. No campaign ledger (`bench/campaigns/**`) on your branch. The whole suite is the Leader's.

## Not in scope
- `cmd_validate` and the T-E9 markers `:384`, `:391`, `:397` (X-TE9, operator-held); the `:327` marker (X-I5); the `:525` marker (X-A3c).
- `status.py`'s `build()` clock (X-J1a's) and any E3 status field (`last_progress_at`, alarm, `has_work`: X-K2b).
- Merging or pushing.

## Budget
120 calls · 180k context · 1 session · 2 h (plan 80 calls and 1.5 h, plus about 40 calls for finding 4, one of the plan's three loop-back slots; Inferred, Coordinator #32). At 85 %: commit, stop, report what remains by finding. Fallback: a fresh Sonnet session from this brief.

## Report (README section 4, at most 12 lines)
Served model id first · base SHA and tip · per red commit: SHA, node, failing assertion · each gate command's exit status · mutants killed per file · retargeted finds · seam requests raised · every `assume:` and whether it held · budget used.
