---
id: plan-eval-x-crlf
title: "X-CRLF: one applying-edit definition, and RS2's requeue5xx"
type: doc
status: proposed
owner: "@timianmalloo"
summary: "C1: readiness and the discriminate applier share one edit definition (CRLF read as LF, `old` once, else HB-RDY-005). C2: RS2 gains requeue5xx, measured to flip g-ordering alone; RS2's record replaced."
tags: [evaluation, property, execution-plan]
links:
  - { to: plan-eval-x-rs, rel: depends-on }
review-by: "2026-10-20"
---

# X-CRLF (session x-crlf-e1e4, rulings CR47-15 and CR47-16)

## C1: one definition of "the edit applies" (APPLY-A)

Shape: one helper, `readiness.apply_edit(task_id, name, edit, raw, where)`. It decodes the file, reads CRLF as LF, requires `old` exactly once, and raises HB-RDY-005 naming the variant and the file. It returns the replaced text. `readiness.variants` calls it as its check. `discriminate._variant_overlay` calls it and writes the returned text, never the unchanged bytes.

- Red `2288ba97`. `test_a_variant_edit_applies_to_a_crlf_reference_file_and_its_declared_flip_is_observed`: `assert [] == ['p-2']`. `test_the_variant_applier_refuses_an_edit_whose_old_is_absent_naming_the_variant`: `DID NOT RAISE BenchError`. The CRLF test uses a two-line anchor, because a one-line anchor matches a CRLF file under a byte replace (a first draft with a one-line anchor was green on arrival and was replaced).
- Green `6d7d8363`; `70e4a4a2` fixes the escape in one mutant's `find` (found by the MUT-E control, `test_every_mutation_find_text_occurs_exactly_once_in_its_target_file`).
- Mutants added to `tests/mutations/property.json`: the absent-anchor refusal removed, killed by the refusal test; the CRLF normalisation removed, killed by the CRLF test. Result: every mutation killed.

### Applier sweep

- `src/harness_bench/discriminate.py:142` (was `read_bytes().replace(edit["old"]...)`): fixed here; it now normalises and refuses.
- `tools/mutate_check.py:454` (`text.replace(m["find"], ...)`): already normalises CRLF at line 449 and skips, counted as a survivor, when the find is absent.
- `src/harness_bench/grade/drift.py:59`, `grade/runner.py:104`, `plan.py:121,301,306,312`, `telemetry/normalize.py:88`, `tools/gate_stamp.py:77,94,100,122`: normalise CRLF to LF for hashing or line reading; none is an edit applier, so none needs a refusal.

## C2: RS2 `requeue5xx` (CR47-16)

After a flush that failed on HTTP 5xx, the pending batch is re-queued behind the newer records. After a lost response the order is kept (three edits: a `_requeue` flag set in `_send`'s except branch from `isinstance(exc, HTTPError)`, and the re-queue at the top of the flush loop).

- Red `c035072b`: `AssertionError: R2-1 names: no v-, no hyphen`, extra item `'requeue5xx'` (the `PREDICTED` row exists before the variant).
- Green `fffd9bac`, with the variant, `evidence.md`'s table, and the record.
- Measured flips: `requeue5xx` flips `['g-ordering']` alone, on clause `result`, as traced; all five hidden tests stay green. `tests/test_rs2_task.py`: 11 passed.
- RS2's new record: `bench/discrimination/RS2/edf7186d09faaf04-af0bbc1e3f354b8e-win32.json` (replaces `ce78c3a1eb92fd5e-af46dc82a3f6bf4f`); `readiness_failures` is empty.

## RS1

`bench discriminate RS1` wrote a record that differs from the committed one in `identity_hash` only (`b7d0b017...` to `cbe12181...`); every other field is equal. Inferred (not opened): the `src/` change moved the identity hash. The record is not byte-equal. The new RS1 file was not committed; the RS1 record is unchanged in this branch. The Leader or the Coordinator rules whether to replace it.
