---
id: brief-eval-x-cv
title: "Brief X-CV: the convergence check, the final ten discrimination records, the proof note"
type: plan
status: proposed
owner: "@timianmalloo"
links:
  - { to: coordination-eval-wave2-e234-briefs, rel: implements }
  - { to: coordination-eval-campaign, rel: implements }
review-by: "2026-10-17"
summary: "X-CV runs after every E2-E4 item has joined and the 0.7 freeze is committed: the whole ADR-0021 section 4 table, TLC with every invariant, then the ten discrimination records at the final engine identity (the Leader), on Claude Sonnet."
---

# X-CV: convergence

> **Waits on** every E2-E4 item joined and the Leader's `freeze_catalog.py` commit. A discrimination record is keyed by engine identity (ADR-0016 §4), so any `src/` change after it supersedes it: the final ten are produced once, after the last code join (campaign plan, serial spine 8).

**Harness** Claude Code sub-agent · `model: sonnet` (served `claude-sonnet-5-5`, R-91) · **session** `x-cv-e1e4` · **branch** `build/eval-x-cv` · **budget** 120 calls · 180k · 1 session · 2 h + machine time. The records run under the Leader.

## Owned paths
`tests/test_resume_table.py` (new, the whole ADR-0021 §4 table), `docs/proof/eval-campaign-convergence.md` (new), `bench/discrimination/**` (the final ten, written by the Leader's runs).

## Acceptance items
1. The whole ADR-0021 §4 table green in `tests/test_resume_table.py`, each row a kill-then-resume test (reusing X-K1's fixtures; no second implementation).
2. TLC with every ADR-0015 §7 invariant and `NoLaunchAfterStop` (R-100); the output in the proof note. One-time evidence such as W1-J's 42-minute US-44 run is cited, never added to a ring (RV-SIM).
3. **All ten discrimination records** (S1, S2, RS1, RS2, RW1, RW2, NG1, NG2, SM1, SM2) at the final engine identity: synthetic cells, no model spend; `bench validate` reports all ten `ready`. A record whose `identity_hash` is not the final one is a failure, not a warning.
4. The proof note gives planned against actual per track (GO19), measured from the audit log's `duration_seconds` and the joins' committer times.

## Compiled (Coordinator #50, 2026-10-06)

- **Compile `al-01M49X6KEJRBXZ8PPK5817ARAR`** (raw `al-01M49X6JKH4N22ZZNADZM8T5RN`). Claude Code Sonnet, session `x-cv-e1e4`, 7,200 s, T2. Stop check: `join-x-k2b` and `join-r113` are both in the log (Ruling 113 withdrew X-START).
- **Folded in:** S2's open-items section in `tasks/S2/oracle/evidence.md` comes first, before S2's record (operator decision 5). The scope of `tests/test_resume_table.py`: W1-K section 4 already maps every row to a node, so the file checks the mapping and adds tests only for rows that have no node. TLC `--quick`, with the full-bound runs cited. SM1's mismatch gets a bounded read. The proof note has a ten-row records table.
- **The records are not in this turn.** The Leader takes them after X-K2b, X-TE9 (R6.14b) and this branch join. The commands, in order, are in `docs/coordination/coordinator-log/c50.md`.
- **Join gate (Ruling 113 condition 3):** the compiling Coordinator reads each record's `hosts.jsonl` for `end: "start bound"`. A reference hit means that record is not accepted as final. The X-CV join commit also carries Ruling 113 condition 4's two errata and condition 5's class.

## Exit
E1 README §3 join gate; the Leader pushes, CI green on Windows and macOS, `docs-graph derive`, then `coord worktree cleanup` (reports only). Report per E1 README §4.
