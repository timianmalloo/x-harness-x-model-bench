---
id: brief-eval-w1-k
title: "Design brief W1-K: resume, liveness and the alarm (dispatch after W1-J merges)"
type: plan
status: proposed
owner: "@timianmalloo"
links:
  - { to: coordination-eval-wave2-e234-briefs, rel: implements }
  - { to: coordination-eval-campaign, rel: implements }
  - { to: design-eval-seam-contracts, rel: depends-on }
review-by: "2026-10-17"
summary: "The design slice for ADR-0021's plan-level resume, liveness and alarm, run with /design-slice on Claude Sonnet after W1-J merges. It extends W1-J's TLA+ model with NoResumeAfterStop, maps every ADR-0021 section 4 row to a kill-then-resume test, and chooses the alarm channel. X-K1 and X-K2 build from it."
---

# W1-K: resume, liveness, alarm (design)

**Dispatch after W1-J merges** (`docs/design/eval-multi-turn.md`, `models/run_lifecycle.tla` and its `.cfg` files on `main`). Run `/design-slice` (the skill), not `/implement`: no code except the `.tla`/`.cfg` additions and TLC runs.

**Harness** Claude Code sub-agent · `model: sonnet` (served `claude-sonnet-5-5`, R-91) · **session** `w1k-resume-e1e4` · **branch** `design/eval-resume` · **tier** T2 · **fan-out cap** 0 · **budget** 140 calls · 180k · 1 session · 2 h.

**Reads:** ADR-0021 (all), ADR-0015 §5-§7, W1-J (merged), W1-B `docs/design/eval-atomic-publish.md` (the `recover_archive` state table), W0 rev 6.6 §4 (the sweep and `recover_archive`), §9 (`resume.py` run, `alarm.py` grade), §10 (the alarm row), §11 (HB-CELL-118/119, HB-RUN-008/009, HB-ALM-001..003; reused HB-RUN-004/005), §12 (the resume record row; `free_bytes`; the rev 6.2 and 6.5 bullets), §13, §14 (the alarm channel is W1-K's). Wave 1 README for the design floor (`docs/coordination/eval-wave1/README.md`).

## Owned paths
`docs/design/eval-resume.md` (new, with frontmatter), `models/run_lifecycle.tla` and `.cfg` (`NoResumeAfterStop` and its seeded variant only; W0 §13: by seam), `tools/check_models.py` (data rows for the new variant through `WIDER`, as SR-J2 ruled; a logic line is a seam request). Not yours: any `src/` file.

## Done when (campaign plan, W1-K row)
1. Gate PASS including **Distributed Systems** and **SRE** (both hard veto), plus Test Architect.
2. Every ADR-0021 §4 row mapped to a kill-then-resume test by node id, the per-turn rows and the turn-1 snapshot-crashed row included; split into X-K1's turns.
3. `NoResumeAfterStop` added to the model **after** W1-J, with TLC output in the doc and its seeded variant **rejected**; `tests/test_check_models.py` and `check_models.py --quick` green on the branch.
4. The resume-owned model branches W1-J left provisional (`BetweenSnapped`, `ClassOf`'s else-branch) settled.
5. The resume record designed (ADR-0021 §6: "resumed n times, with each resume's time and segment id"): grain declared first, append-only, derived counts never stored.
6. The alarm channel chosen (ADR-0021 §7: "The channel is chosen at `/design-slice`") with the runbook entry's path; the drill is out of scope.
7. The `bench run <run_id>` resume entry line in `cli.py` assigned to X-K2 (W0 §13 `cli.py` E3) and stated as a seam X-K1 → X-K2.
8. Surface list (E7) from store to compute reader, including `status.py` (X-K2, rebased on X-J1's R6.5b hunk).

Seams go to `coord-opus-e1e4` with a fallback built to green (E1 README §2, rev 6.4). Report: the gate line, TLC output summary, and the X-K1 / X-K2 split.
