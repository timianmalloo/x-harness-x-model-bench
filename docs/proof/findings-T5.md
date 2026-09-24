---
id: "proof-findings-t5"
title: "T5 findings: N5 spike (Codex host skill discovery)"
type: proof-pack
status: draft
owner: "@timianmalloo"
phase: "Phase 1 · walking skeleton"
tags: [proof, phase-1, codex, N5, T5]
links:
  - { to: coordination-phase1-finish, rel: relates-to }
  - { to: note-spike-n5-codex-skill-roots, rel: relates-to }
review-by: "2026-10-08"
summary: >-
  T5's findings->tests map and the T5 fallback decision request. One mechanism was tried for real
  (features.skip_host_skill_discovery); the canary still leaked, so the change is reverted and N5 stays
  open. Recommends fallback option (a): keep xfail(strict), record the exposure, flag Codex cells in the
  report header.
---

# T5 findings

## Findings -> tests map

| finding | test node id | red SHA | failing line (at red SHA) | disposition |
| --- | --- | --- | --- | --- |
| N5: `features.skip_host_skill_discovery=true` should stop `~/.agents/skills` reaching a Codex cell | `tests/test_profiles.py::test_codex_profile_disables_host_skill_discovery` | `1678c43a56df6dca149c10f68c9e407558d8ad45` | `tests/test_profiles.py:48: assert "[features]" in config` | **Disproven by a real canary run** (below). The unit test and the `bench/profiles/codex.yaml` change are reverted; the hypothesis is recorded in `docs/notes/spike-n5-codex-skill-roots.md`, not carried in the tree as a false fix. |

## Real canary run (2026-09-24, run 1 of 3 permitted)

Command: `uv run pytest -q -p no:cacheprovider tests/e2e/test_us13_canary.py -s -m ""`, with
`features.skip_host_skill_discovery = true` applied in the per-cell `config.toml`.

```
US-13 claude-code: shown by the control ['skill']; void (control did not show) ['skill (~/.agents/skills, via USERPROFILE)']; leaked into the probe []
US-13 codex: shown by the control ['skill (~/.agents/skills, via USERPROFILE)']; void (control did not show) []; leaked into the probe ['skill (~/.agents/skills, via USERPROFILE)']
AssertionError: user-level configuration reached a codex cell: ['skill (~/.agents/skills, via USERPROFILE)']
1 failed, 1 passed in 33.86s
```

Claude Code: clean (as before this spike). Codex: `microsoft-foundry` (the operator's
`~/.agents/skills` entry) still reached the cell. Runs 2 and 3 of the permitted 3 were not used: after
this result, and the independent corroboration in the spike note, further guesses at flag names would
not be evidence — the timebox was spent on the read-source-then-run cycle (Spike Protocol) that produced
this one real answer, not on trying more names without a source for what they do.

## Gates (after the revert, HEAD)

- `uv run ruff check src tests tools`: **All checks passed.**
- `uv run pytest -q -p no:cacheprovider -m "not credentials"`: **304 passed, 5 deselected.**

## Timebox

Research timebox (1.5h) and whole-track timebox (3h): the research timebox is spent — one candidate
mechanism was found by reading the installed Codex 0.156 binary's own `features list` (source of truth:
a run, not recall), applied, and disproven by a real canary run, with independent third-party
corroboration on 0.154.0. No second candidate reached the same standard of evidence within the
timebox: the remaining candidate (Windows known-folder API ignoring `USERPROFILE`) is Flagged, not
Verified — see the spike note's "not reached" section for the cheapest next probe.

## T5 fallback: decision request to the Owner

Per the coordination plan's T5 fallback, three options:

- **(a) keep `xfail(strict)`, record the contamination in the Proof Pack, and flag Codex cells
  `user-config exposed (N5)` in the report header.** *Recommended.* Evidence: two independent attempts
  (the reverted per-cell `USERPROFILE`/`HOME`, and this spike's `skip_host_skill_discovery`) plus a
  third party's four-flag attempt on 0.154.0 all fail identically — this smells like Codex 0.156
  resolving its personal-skills `~` through a path that ignores every config- and env-level control
  surface tried so far (candidate: the Windows known-folder API, unconfirmed). Disclosing the exposure
  costs nothing in correctness (US-13's own canary already proves and pins the leak) and unblocks M1/M2
  today.
- **(b) run tomorrow with Claude Code combos only.** Available if the Owner wants zero Codex exposure
  before M1; costs a day and drops Codex from the walking-skeleton E2E until N5 closes.
- **(c) accept the exposure via ADR-0013 (the agent reaching outside its working copy).** Not
  recommended without a stronger argument than "found no fix in 1.5h": (a) already gets the same
  practical outcome (ship, disclosed) with a lower bar to reopen and fix later, since it does not need
  an ADR amendment to walk back.

**Not decided by T5.** T5 holds no veto and made no ruling; this is a decision request per
`coord decide request --to owner-fable`, recorded here per the plan's format since T5's owned paths do
not include `docs/notes/rulings.md`.
