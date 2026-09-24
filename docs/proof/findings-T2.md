---
id: "findings-t2-ledger-verify"
title: "Findings → tests: track T2 ledger-verify"
type: proof-pack
status: accepted
owner: "@timianmalloo"
phase: "Phase 1 · walking skeleton"
tags: [proof, findings, red-first, T2]
links:
  - { to: coordination-phase1-finish, rel: relates-to }
review-by: "2026-12-22"
summary: >-
  Track T2's findings→tests map: twelve findings on the ledger, verify and grading, each with its red commit, test
  nodes and failing line. The harness refused the sub-agent's writes of this file, so the Coordinator transcribed
  it from the track's report and re-ran two red SHAs itself.
---

# Findings → tests: track T2 ledger-verify

**Transcribed by the Coordinator.** The harness refused the T2 sub-agent's writes of this file ("Subagents should return findings as text"), so the Coordinator transcribed it from the track's report. The Coordinator itself re-ran these red SHAs in a throwaway worktree, and both failed on the recorded lines:
- **T2-1** `7f07555`: `assert (0 == 5)` on the cut and delete probes.
- **T2-3** `f6563ef`: `DID NOT RAISE BenchError`.

At head `5270809`, `tests/mutations/{ledger,views,grade}.json` were re-run: every mutation killed. The mutation record is `docs/notes/mutation-record-t2.md`. cosmic-ray 8.7.0 ran natively on `src` at `2263575`, which is the same `src` as the head: 1,803 mutants, 1,546 killed, 257 equivalent, none open.

| # | finding | test | red | failing line | fix |
| --- | --- | --- | --- | --- | --- |
| T2-1 | a pass cut short or deleted exits 0 | `tests/test_verify.py::test_cutting_the_seal_and_last_row_of_a_completed_pass_is_exit_5[*]`, `::test_deleting_a_completed_pass_fact_segment_is_exit_5[*]` | `7f07555` | `test_verify.py:50: assert (0 == 5)`; `:59` | `bb993db` |
| T2-2 | no `heads`; run heads unchecked | `tests/test_grade.py::test_grading_completed_records_the_sealed_heads_of_its_other_facts`; `tests/test_verify.py::test_cutting_or_deleting_a_completed_run_segment_is_exit_5[*]`, `::test_the_in_run_pass_cannot_be_turned_into_an_abandoned_one`, `::test_a_run_completed_naming_the_wrong_events_head_is_exit_5` | `be76e90`, `7f07555` | `test_grade.py:200: KeyError: 'heads'`; `test_verify.py:74/88/95: assert (0 == 5)` | `bb993db` |
| T2-3 | SRE-5: no poison after a failed write | `tests/test_ledger.py::test_a_failed_write_poisons_the_writer` | `f6563ef` | `test_ledger.py:91: DID NOT RAISE BenchError` | `c68f10b` |
| T2-4 | ledger survivors (second writer, seal count, bytes after the seal) | `tests/test_ledger.py::test_a_segment_has_one_writer_until_it_closes`, `::test_a_re_hashed_seal_must_still_match_its_segment[*]`, `::test_bytes_after_the_seal_are_a_break_not_a_torn_tail[*]`, and others | `ca87796` (mutant red) | `ledger.json` 20/20 killed | tests only |
| T2-5 | D2 ledger properties | `tests/test_ledger.py::test_append_then_verify_round_trips`, `::test_any_cut_or_insert_is_detected`, `::test_a_torn_tail_is_handled_at_any_offset`; `tests/test_verify.py::test_any_change_to_a_completed_run_ledger_is_detected` | `4039174` (mutant red) | kills "reopen keeps the torn tail" | tests only |
| T2-6 | D6 golden ledgers (`c44dd2b-no-heads`, `heads`, tampered overlays) | `tests/test_verify.py::test_a_golden_ledger_keeps_its_hashes_and_row_counts[*]`, `::test_the_ledger_written_before_heads_verifies_with_a_warning`, `::test_a_tampered_golden_ledger_is_exit_5[*]` | `7f07555`; `455c72e` (against `c68f10b`'s `src`) | `test_verify.py:128` (warning missing), `:135` and `:142: assert (0 == 5)` | `bb993db` |
| T2-7 | a record may forge a seal | `tests/test_ledger.py::test_a_record_may_not_forge_a_seal_or_its_chain_fields` | `ca87796` | `:238 DID NOT RAISE ValueError` | `152adc3` |
| T2-8 | garbage after a seal passes as a torn tail | `tests/test_ledger.py::test_bytes_after_the_seal_are_a_break_not_a_torn_tail[\n\|garbage\n]` | `4039174` | `assert (None,'') == ('HB-LED-002'…)` | `393dc86` |
| T2-9 | Simplifier minors (one span rule; one turn_usage row mapping) | existing view and grade tests pin the behaviour | refactor | n/a | `6822669` |
| T2-10 | tamper tests passed only because of CRLF | `tests/test_ledger.py::test_a_torn_line_that_is_not_the_tail_is_a_break`, `::test_tampering_is_detected[*]` | `6822669` (mutant survived) | "survived a torn line in the middle is a torn tail" | `b1e7940` |
| T2-11 | cosmic-ray survivor gaps | about 45 nodes across the four test files | `ff27e06`, `4c8e9d9`, `2263575`, `9646248` | see the mutation record | tests only |
| T2-12 | seam from T3: `Extraction.missing` was never read | `tests/test_grade.py::test_cost_is_na_naming_hb_tel_001_when_the_native_record_misses_a_usage_field` | `5f7349f` | `:211 ('0.010272', None) == (None, 'HB-TE…')` | `5b440a7` |

**Residual risk (disclosed by the track):**
- For a pass with no `heads` (the pre-R-2 ledgers), a cut that is re-sealed, or a deleted segment, gets a warning, not an error. That follows R-2.
- Truncating the engine events segment back past `run.completed` shows the run as incomplete, not as an integrity error.
- The pass-without-heads warning reuses HB-LED-002, since only T1 adds error codes.
