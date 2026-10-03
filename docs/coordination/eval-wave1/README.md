---
id: coordination-eval-wave1-briefs
title: "Wave 1 dispatch pack: design-slice and lens-reviewer briefs (Evaluation Campaign)"
type: plan
status: proposed
owner: "@timianmalloo"
phase: "Enterprise evaluation: Wave 1 (design slices W1-A..W1-L, spike SP-LB, lens reviewers RV-*)"
tags: [coordination, briefs, wave-1, evaluation-campaign]
links:
  - { to: coordination-eval-campaign, rel: implements }
  - { to: design-eval-seam-contracts, rel: depends-on }
  - { to: rulings-register, rel: depends-on }
review-by: "2026-10-17"
summary: >-
  The rules every Wave 1 worker follows, plus one self-contained brief per design track (W1-A..W1-L), the loopback
  spike (SP-LB) and the six lens reviewers. A launcher passes only the brief's path; the brief tells the worker to
  read this file first.
---

# Wave 1 dispatch pack: rules common to every brief

You were given a brief in this folder. Read this file, then your brief. Both bind you. Where they differ, your brief wins.

**Seats.** Leader `leader-e1e4` (merges to `main`; you never merge). Owner `owner-fable` (rules on decision requests into `docs/notes/rulings.md`). Coordinator `coord-opus-e1e4` (owns the W0 contracts, arbitrates seams). Leader epoch 13. If the epoch changes, stop at your next commit and report.

**Paths.** The primary checkout is `C:\Projects\x-harness-x-model-bench` (`main`, which holds W0: `docs/design/eval-seam-contracts.md`). On Windows use `python`, never `python3`. `C=docs/ai-forward-pack/scripts/coord-core.py`.

## 1. Start (in this order, before anything else)
1. `python docs/ai-forward-pack/scripts/audit-log.py start --session <your session> --skill <your skill>` (DC-190). A resumed run repeats this line first.
2. **Prefix every `git commit` and every coord call inline:** `AGENT_SESSION=<your session> git commit …`, `AGENT_SESSION=<your session> python $C …` (PowerShell: `$env:AGENT_SESSION='<your session>'; git commit …` in the **same** call). **Why:** each Bash or PowerShell tool call starts a fresh shell, so an `export` in one call is gone in the next. The commit floor then prints "AGENT_SESSION is unset" and only advises; it enforces nothing. At least five worker commits on 2026-10-03 went through that way (class COORD-D). A one-time `export` is not compliance.
3. If your cwd is not already your brief's tree, then from the primary checkout run `python $C worktree new --branch <your branch> --session <your session>`. It prints the tree path, `C:\Projects\x-harness-x-model-bench-<branch with / as ->`. Use **absolute paths into that tree** from then on.
4. In the tree, run `python $C doctor` and read it. **Never** `coord install`. **Never** `EnterWorktree` or `ExitWorktree` (F-25: an 8,143 s stall).
5. Check that W0 is in your base: `git -C <tree> log --oneline -1 -- docs/design/eval-seam-contracts.md` prints a commit. If it does not, stop and report "W0 not on main".

## 2. While working
- **Owned paths only.** Edit only the paths your brief owns. Claim an owned file for the minutes of an edit (`python $C claim --wi <your session> --path <path>`, default TTL; release by committing). A `register`-class file (`docs/audit/*.jsonl`, `docs/notes/rulings.md`) is never claimed: you append and commit.
- **Commit named paths.** `git add <path> …` then commit. Never `git add -A`, `git add .` or `git commit -a`. Every commit message ends with your model's `Co-Authored-By` line.
- **Shell shape (CT27).** A gate's exit status is never behind a pipe: redirect to a scratch file, then echo `$?`. A multi-line program is a file, then a run; never a heredoc into Python.
- **Need something outside your paths, or a W0 contract change?** Send a seam request, do not edit: `python $C request add --to coord-opus-e1e4 --deadline default --fallback "<what you do meanwhile>" "<the ask>"`. Then design to the W0 text as written and mark the dependent section `provisional (seam <id>)`.
- **A decision only the Owner can make?** `python docs/ai-forward-pack/scripts/coord-decide.py request --to owner-fable --options "…" --recommendation "…" --evidence "…" --reversibility "…" --blast-radius "…" --deadline 1800 --fallback "<the recommended option, provisional>" "<question>"`. Do not wait idle: proceed on the recommendation, mark it provisional, and list the request id in your report.
- **No guessing.** Open the file, run it, read the signature; or write an inline `assume:` (the belief, what confirms it, what breaks if false). Quote ADR and spec lines verbatim when a control rests on them (DC-189).
- **Fan-out cap 0.** Spawn no sub-agents. In a design slice, the adversary seats are the separate lens reviewers (RV-*). You run `/design-slice` Stage 4 as a self-check against `.claude/skills/design-slice/reference/definition-of-done.md`, and leave the Gate record **pending** with the reviewer list from your brief. You never clear a veto.
- **Context ceiling.** Your brief's budget states it. At 85 % of it: commit, write what remains into the doc's *Status* table, and stop with your report. Never `/compact` in the middle of a section.
- **A budget firing is a defect signal (GO9),** not a reason to continue. Stop and report the overrun with its cause.

## 2a. Testability floor (binding on every design from batch b on, and on every revision)

RV-TA blocked every first-pass Wave 1 design (W1-F, W1-G, W1-B, W1-D) on the same five shapes (class TEST-B, `docs/lessons/defect-classes.md`). A design that misses any item below fails its own Stage 4 self-check; RV-TA checks this list first.

For **each named test**, the design states:
1. **The assertion that fails today, and why.** Name the assertion and the current behaviour that makes it false. "Red" never means an `ImportError`, `AttributeError` or `NameError`: a test that patches or imports a symbol that does not exist yet fails for the wrong reason, and stays wrong after a broken build. If the symbol is new, the test reaches it through the public path that will call it, or the design says which skeleton commit lands first.
2. **The red fixture for every guard or scan.** A temp tree or input that the rule must flag, run before the real tree. Deleting the rule must turn the test red. Name the fixture.
3. **The real-wiring test beside any fake.** Where an engine, CLI or runner test uses a fake, one test drives the real composition (the real `cli.py` command, the real `run_pass`) and fails if the wiring line is removed. Name it.
4. **The mutant that separates each adjacent pair of rules.** Where two rules can give the same observable result (precedence rows, a guard and its fallback), name one input on which they differ and the mutant that swaps them.
5. **The allowlist or sweep checked against the tree.** An allowlist or "every reader migrated" claim cites the scan run on the design's base commit and its output count, and the test asserts the same set.

## 3. Finish (design tracks)
1. The design doc carries V2 frontmatter: `id: design-eval-<slice>`, `type: design`, `status: proposed`, `owner: "@timianmalloo"`, `links` with at least `implements` → `spec-enterprise-evaluation` and `arch-evaluation-campaign`, `depends-on` → its ADR(s) and `design-eval-seam-contracts`, `review-by`, and a real summary.
2. `python docs/ai-forward-pack/scripts/docs-graph.py derive`, then `python docs/ai-forward-pack/scripts/docs-graph.py validate` (exit 0; status read from its own line).
3. Audit, last: `python docs/ai-forward-pack/scripts/audit-log.py append --shortname "design-slice-eval-<slice>" --session <your session> --skill design-slice --kind skill --prompt "<your brief path>" --summary "<what it produced>" --artifact docs/design/eval-<slice>.md --goal "<brief goal>" --done-when "<brief done-when>" --tier T2 --fan-out 0`. Also `audit-log.py change --title "<the design decision>" --kind design --skill design-slice …` (the Change Mandate).
4. Commit by named paths (doc, `docs/docs-index.js`, `docs/audit/audit-log.jsonl`, `docs/audit/change-log.jsonl`, plus any other owned path you touched).
5. **Report** (your final message, at most 10 lines): branch and commit SHAs · doc path · gate status (pending reviewers) · decision and seam request ids · spikes run, with their result · self-check items unmet · budget used (tool calls, approximate tokens, wall minutes) against the brief · not done.

## 4. How a slice passes its gate
The lens reviewers in the brief each write one gate line. The slice passes when RV-TA and every hard-veto lens it names (RV-SEC, RV-DS) say **PASS** or **PASS WITH CONDITIONS**, and RV-PAT and RV-SIM have no unresolved blocking finding (the Simplifier's veto is soft; the Tech Lead's casting vote decides a Patterns-versus-Simplifier tie). The author applies the findings in a follow-up message (it starts with the `start` line again), and copies each reviewer's gate line verbatim into the doc's Gate record. Findings are advice, not scope: a finding that widens the slice goes to the Coordinator.

## 5. The briefs

| brief | session | model (pin) | owns |
| --- | --- | --- | --- |
| `w1-a-arms.md` | `w1a-arms-e1e4` | Sonnet (`model: sonnet`, served `claude-sonnet-5-5`, R-91) | `docs/design/eval-arms.md` |
| `w1-b-atomic-publish.md` | `w1b-publish-e1e4` | Sonnet | `docs/design/eval-atomic-publish.md` |
| `w1-c-campaign-record.md` | `w1c-campaign-e1e4` | Sonnet | `docs/design/eval-campaign-record.md` |
| `w1-d-identity.md` | `w1d-identity-e1e4` | Sonnet | `docs/design/eval-identity.md` |
| `w1-e-discriminate.md` | `w1e-discrim-e1e4` | Sonnet | `docs/design/eval-discriminate.md` |
| `w1-f-property-grader.md` | `w1f-property-e1e4` | **Opus `claude-opus-5-5`** | `docs/design/eval-property-grader.md` |
| `w1-g-catalog.md` | `w1g-catalog-e1e4` | Sonnet | `docs/design/eval-catalog-0-7.md` |
| `w1-h-power-verdicts.md` | `w1h-power-e1e4` | Sonnet | `docs/design/eval-power-verdicts.md` |
| `w1-i-security-tasks.md` | `w1i-security-e1e4` | Sonnet | `docs/design/eval-security-tasks.md` |
| `w1-j-multi-turn.md` | `w1j-multiturn-e1e4` | Sonnet | `docs/design/eval-multi-turn.md`, `models/run_lifecycle.tla`, `models/run_lifecycle.*.cfg` |
| `w1-k-resume.md` | `w1k-resume-e1e4` | Sonnet | `docs/design/eval-resume.md` (+ the `.tla` after W1-J joins) |
| `w1-l-property-tasks.md` | `w1l-tasks-e1e4` | Sonnet | `docs/design/eval-property-tasks.md` |
| `sp-lb-loopback.md` | `splb-loopback-e1e4` | Sonnet | `tools/spikes/s_lb_loopback.py`, `docs/notes/spike-s-lb-loopback.md` |
| `rv-pat.md`, `rv-sim.md`, `rv-ta.md`, `rv-sec.md`, `rv-ds.md`, `rv-sre.md` | `rv-<lens>-e1e4` | Sonnet | `docs/design/reviews/eval-review-<lens>.md` |

**Launch order (cap 6 running workers; a design track or a reviewer counts as one while it runs; an idle reviewer waiting for `SendMessage` does not).**
1. **Slot 1-6:** W1-F (Opus; the longest node on the critical path W1-F → X-F → X-E), plus RV-TA, RV-SEC, RV-DS, RV-PAT and RV-SIM, each on **W0 only** (plan step 5).
2. As the W0 reviews return: W1-G, W1-A, W1-B, W1-D, W1-I (with W1-F, plan batch a). W1-G first: X-G1 gates X-F and X-H1.
3. Each freed slot goes, in this order: (a) the reviewers of a returned slice, critical-path slices first (G, F, then A, D, B, I); (b) batch b: W1-H, W1-C, W1-E, W1-J, W1-L; (c) W1-K once W1-J's model is on `main`; (d) SP-LB whenever the operator is present (it holds a slot only for the script). RV-SRE starts with W1-D's review.
4. Each author's follow-up (applying findings) takes a slot like a new dispatch.

**Launching (R-87 Option 1).** The Agent tool with `model: sonnet` (or `model: opus` for W1-F), never a default. The prompt is the brief's absolute path and the line "Read it and follow it." Read the served model id back from the first spawn's transcript (R-87 condition 3); if it is not `claude-sonnet-5-5` (R-91 condition 4), stop Sonnet dispatch and tell the Coordinator.
