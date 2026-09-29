import Fold

/-!
Statements.lean -- prove these two theorems about `fold` (`Fold.lean`, FROZEN -- do not edit it,
or `lakefile.toml`, or `lean-toolchain`). Both statements are taken verbatim from coord-core.py's
own documented properties and its own test suite; see `../../oracle/README.md` for the full
correspondence.

You may add helper lemmas in this file, or in new files anywhere under `Proofs/**`, and import
them here -- only the elaborated TYPE of the two named theorems below is checked against the
task's frozen statement hash (`task.yaml` `formal.theorem_names`); the proof term after `:=` is
never part of that hash. The build must stay clean: no `sorry`, `admit`, `native_decide`,
`#eval`, `initialize`, `run_cmd`, `unsafe` or `@[extern]` anywhere under `Proofs/**`, and
`#print axioms` on each theorem below must list only `propext`, `Classical.choice` and/or
`Quot.sound`.
-/

/-- `NFR-R1` (coord-core's own spec, `docs/specs/agent-coordination.md`): "Replaying the record
    twice yields identical folded state." Python test:
    `test_T2_fold_is_idempotent_under_replay` (`tests/docs_explorer/test_coord_core.py`):
    `fold(events + events, now) == fold(events, now)`. -/
theorem fold_replay_is_idempotent (events : List Event) (now : Nat) :
    fold (events ++ events) now = fold events now := by
  sorry

/-- `F9` (coord-core's own design, `docs/design/coord-core-phase1.md`): "The same claim emitted
    twice (a retried tool call) ... Idempotent by (session, seq); re-emitting is a no-op, not a
    second lease." Python test: `test_T15_duplicate_seq_is_idempotent`
    (`tests/docs_explorer/test_coord_core.py`). Stated here for ANY two events sharing an id --
    not only byte-identical ones -- because the Python dedup guard is on `(session, seq)` alone
    (`ident = (event.get("session"), event.get("seq"))`), so a differently keyed duplicate must
    still be dropped, not merely a byte-identical one. -/
theorem retried_event_is_a_no_op (e1 e2 : Event) (now : Nat) (h : e1.id = e2.id) :
    fold [e1, e2] now = fold [e1] now := by
  sorry
