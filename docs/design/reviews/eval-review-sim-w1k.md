---
id: review-eval-sim-w1k
title: "Simplifier review of W1-K, resume, liveness and the alarm (Adversary Mode)"
type: doc
status: draft
owner: "@timianmalloo"
tags: [review, simplifier, evaluation-campaign, wave-1, w1-k]
links:
  - { to: design-eval-seam-contracts, rel: relates-to }
review-by: "2026-10-17"
summary: >-
  RV-SIM review of design/eval-resume rev 1.1 (315cf1d4). The reconcile design is the smallest correct core; the
  proof is larger than it needs to be (the prefix sweep already kills the classifier mutants), and the alarm channel
  ships two deliveries where one reaches the sleeping operator. Soft veto: conditions, no block.
---

# RV-SIM review: W1-K `docs/design/eval-resume.md` rev 1.1

Read in full at 315cf1d4; ADR-0021 + Amendment 1, R-100, `cli.py` and `engine.py` read on `main` ef4e86dc. Session `rv-patsim-w1k-e1e4`, 2026-10-03. Ladder used: YAGNI, reuse, stdlib, native, one line, minimum. The floors (red first, the Testing-Strategy union, the model's invariants, the refusals) are not cut.

**Counts, from the doc (the brief's numbers differ).** Window rows: 20 table rows (W1..W16 with a/b/c params and W12d/e), about 33 parametrized cases. Mutants: 15 in `resume.json` plus 5 in `alarm.json` = 20 named, not 11. Model: 5 new variants, 1 retired, 34 in all; the new ones pin guards W1-J left untested, so keep. Alarm: 12 tests, 1 wrapper test, 5 mutants.

| # | location | finding | severity | evidence | fix | confidence |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | section 4, prefix sweep vs windows W1, W3, W3b, W6, W7, W8 | **Two proofs of one table.** `classify` is pure. The prefix sweep runs it on every prefix against an independent oracle, so it already covers every classifier row (C2, C3, C5, C6, C7). W1, W3, W3b, W6, W7, W8 re-prove those rows through a real kill (T2) or a fixture (T1). The sweep catches an unlisted prefix; the windows catch only listed ones. | major | design lines 150-158, 170 | Keep the sweep. Make W1, W3, W3b, W6, W7, W8 rows of the sweep's oracle (one assertion each, no T2). Keep the windows that need disk state or a second process: W2 (D-K3 discard), W4, W5abc, W9, W10abc, W11, W12 x3, W12d/e, W13-W16. One T2 stays for wiring (`test_cli_run_resumes`). Saves about six child-process runs. | Verified |
| 2 | section 4 (d), five classifier mutants | M-OLDPRED, M-IGNORENEXT, M-ELSEDONE, M-LAUNCHAFTERINTENT, M-RESEND each swap one `classify` branch. The sweep fails on any of them by construction (a deleted branch fails a prefix). Their only job is to show that the sweep and windows work. Keep the other ten: M-NODISCARD, M-SKIPARCH, M-APPENDALL, M-WRITEOLD, M-ORDER, M-STOPONLYRUNSTOPPED, M-LAUNCHSTOPPEDISSTOP, M-STOPCRASHREC, M-STOPLAUNCHES, M-STOPGRADES. | major | design lines 178-196 | Run the five once at X-K1 K4 to show the sweep kills them (a one-time proof, `tests-earn-their-place`); do not keep them in `resume.json`. | Verified (by construction); Inferred until run |
| 3 | section 6.3, channel | **Two deliveries where one reaches the operator.** The need is a sleeping operator on a multi-night run. A toast needs a signed-in, awake user at the screen, and spike S-K1 never saw one shown. ntfy reaches the phone with one env var and one POST and no stored credential. The toast adds WinRT/AUMID code, an unproven `powershell.exe` 5.1 constraint, XML, and a Windows-only dry-run branch. The doc's own table calls ntfy "the away-from-terminal path ADR-0021 asks for". | major | design lines 299-304, 315; ADR-0021 section 7 ("reaches the operator") | E3 ships ntfy only; an unset `HB_ALARM_NTFY_TOPIC` makes the wrapper exit non-zero and write one event-log line. Toast can join at the drill. If the Owner refuses third-party egress, toast-only is the fallback and the runbook must say it wakes no one. A decision for the Owner, not the builder. | Verified (design text); toast behaviour Inferred |
| 4 | section 6.3 "Alarm of the alarm": `HB-ALM-003`, `.alarm_check`, `ALARM_INTERVAL_S`, two tests | The warning prints only when a human runs `bench status`, the human the alarm exists to replace. ADR-0021 chose it as "cheapest", not as needed for E3. It costs a stamp file, a constant, a code, a status and campaign warning line, two tests and a ceiling marker. | minor | design lines 289, 293, 313; ADR-0021 section 7 | Defer to E5 with the drill, where a disabled task is actually tested. If kept: one stamp, one warning, one test (`test_alm_003_warning_when_stamp_is_old`). | Verified |
| 5 | section 8, report, plan and campaign surfaces | Not needed to resume safely: the report header resume lines (a seam to two other tracks), `bench plan` worst-case lines, `resume.history` with per-resume skipped / launched / reconciled, `campaign status --alarm-after`, five telemetry kinds. Each has value; none blocks E3's goal (a crashed night is recovered and recorded). | minor | design lines 82, 291, 320, 336, 359 | Move to E5: the report header, `campaign status --alarm-after`, `bench plan` lines. Keep in E3: `run.resumed`, `segment.abandoned`, `cell.outcome.resume`, `resume.started/classified/done`, "resumed n times" in `bench status`. | Inferred |
| 6 | section 7, disk query | The `_free_bytes` handler is real (ADR-0021 section 8) but unrelated to the resume path and touches `_launch`. | minor | design line 319; `engine.py:893-897` | Keep, as its own commit (K6b) so it can ship or revert alone. | Verified |
| 7 | section 5.4, US-44 run | A 357M-state, 40-minute run, marked stale and one-time; correctly outside every continuous ring. | minor | design line 273 | Do not re-run unless the model changes again; the quick run covers the same invariants. | Verified |
| 8 | section 5.3 F-1 | The model keeps the engine's grade enabled on a stopped run; the code will not. A model that proves a property the code lacks is not a proof of the code. The cheap fix is a sentence, not a new exception. | minor | design line 232 | State in `run-lifecycle-model.md` that `ArchivedCellsGetGraded` after a finish-the-stop holds through `bench grade`, not the resumed engine. | Verified |

**Patterns-versus-Simplifier tension.** Patterns asked for names, an alert edge (dedupe state) and a segment factory. The Simplifier declines a dedupe state file for E3 (use ntfy's sequence id, or accept a loud repeat: a night of 15-minute pushes is rare and the loudness is deliberate) and accepts the factory (it removes a second definition of the id rule). Patterns' finding 2 (a finished stop still alarms) is a correctness defect the Simplifier agrees blocks; its fix is a definition, not new code. Patterns' wish to name the alarm of the alarm as a Watchdog loses to finding 4 here: the cheapest honest move is to defer it.

GATE W1-K · Simplifier · PASS WITH CONDITIONS · 8 findings (rv-patsim-w1k-e1e4, 2026-10-03)

Conditions: findings 1, 2 and 3 applied or answered by the author before the gate record is copied; 4 to 8 are advice.
