import Fold

/-!
Statements.lean -- reference solution. See `../../../workspace/Proofs/Statements.lean` for the
given (unproved) statements as the agent receives them, and `../README.md` for the correspondence
to coord-core.py and the proof strategy below.
-/

/-- `step` only ever extends `seen` by consing the new event's id on -- `isClaim` affects `.fst`
    (the store) alone. Isolating this makes the two theorems below tractable by structural
    induction, without re-deriving it at each use site. -/
theorem step_snd (acc : Store × List EventId) (e : Event) :
    (step acc e).snd = if acc.snd.contains e.id then acc.snd else e.id :: acc.snd := by
  unfold step
  split
  · rfl
  · split <;> rfl

/-- The `seen` component of the fold accumulator only grows as more events are folded in. -/
theorem seen_mono (l : List Event) (acc : Store × List EventId) :
    ∀ x, x ∈ acc.2 → x ∈ (List.foldl step acc l).2 := by
  induction l generalizing acc with
  | nil => intro x hx; simpa using hx
  | cons e0 l ih =>
    intro x hx
    have hstep : x ∈ (step acc e0).2 := by
      rw [step_snd]; split
      · exact hx
      · exact List.mem_cons_of_mem _ hx
    rw [List.foldl_cons]
    exact ih (step acc e0) x hstep

/-- Every event's id ends up in `seen` once the fold has passed over it. -/
theorem id_in_seen (l : List Event) (acc : Store × List EventId) :
    ∀ e ∈ l, e.id ∈ (List.foldl step acc l).2 := by
  induction l generalizing acc with
  | nil => intro e he; cases he
  | cons e0 l ih =>
    intro e he
    rcases List.mem_cons.mp he with heq | hmem
    · subst heq
      have h0 : e.id ∈ (step acc e).2 := by
        rw [step_snd]; split
        · rename_i hc; exact List.contains_iff_mem.mp hc
        · exact List.mem_cons_self
      rw [List.foldl_cons]
      exact seen_mono l (step acc e) e.id h0
    · rw [List.foldl_cons]
      exact ih (step acc e0) e hmem

/-- Folding a list all of whose event ids are already `seen` leaves the accumulator unchanged
    (this is exactly F9's "a retried event is a no-op", generalized to a whole list at once). -/
theorem foldl_step_no_op (l : List Event) (acc : Store × List EventId)
    (h : ∀ e ∈ l, e.id ∈ acc.2) : List.foldl step acc l = acc := by
  induction l generalizing acc with
  | nil => rfl
  | cons e0 l ih =>
    have h0 : e0.id ∈ acc.2 := h e0 List.mem_cons_self
    have hstep : step acc e0 = acc := by
      unfold step
      rw [if_pos (List.contains_iff_mem.mpr h0)]
    have htail : ∀ e ∈ l, e.id ∈ acc.2 := fun e he => h e (List.mem_cons_of_mem e0 he)
    calc List.foldl step acc (e0 :: l)
        = List.foldl step (step acc e0) l := List.foldl_cons
      _ = List.foldl step acc l := by rw [hstep]
      _ = acc := ih acc htail

/-- `NFR-R1` (coord-core's own spec, `docs/specs/agent-coordination.md`): "Replaying the record
    twice yields identical folded state." Python test:
    `test_T2_fold_is_idempotent_under_replay` (`tests/docs_explorer/test_coord_core.py`):
    `fold(events + events, now) == fold(events, now)`. -/
theorem fold_replay_is_idempotent (events : List Event) (now : Nat) :
    fold (events ++ events) now = fold events now := by
  unfold fold foldRaw
  have hsplit : List.foldl step (([], []) : Store × List EventId) (events ++ events)
      = List.foldl step (List.foldl step (([], []) : Store × List EventId) events) events :=
    List.foldl_append
  have hids : ∀ e ∈ events,
      e.id ∈ (List.foldl step (([], []) : Store × List EventId) events).2 :=
    id_in_seen events (([], []))
  have hnoop := foldl_step_no_op events
    (List.foldl step (([], []) : Store × List EventId) events) hids
  rw [hsplit, hnoop]

/-- `F9` (coord-core's own design, `docs/design/coord-core-phase1.md`): "The same claim emitted
    twice (a retried tool call) ... Idempotent by (session, seq); re-emitting is a no-op, not a
    second lease." Python test: `test_T15_duplicate_seq_is_idempotent`
    (`tests/docs_explorer/test_coord_core.py`). Stated for any two events sharing an id -- not
    only byte-identical ones -- because the dedup guard is on `(session, seq)` alone
    (coord-core.py: `ident = (event.get("session"), event.get("seq"))`), so a differently keyed
    duplicate must still be dropped, not merely a byte-identical one. -/
theorem retried_event_is_a_no_op (e1 e2 : Event) (now : Nat) (h : e1.id = e2.id) :
    fold [e1, e2] now = fold [e1] now := by
  unfold fold foldRaw
  have hlist : ([e1, e2] : List Event) = [e1] ++ [e2] := rfl
  rw [hlist]
  have hsplit : List.foldl step (([], []) : Store × List EventId) ([e1] ++ [e2])
      = List.foldl step (List.foldl step (([], []) : Store × List EventId) [e1]) [e2] :=
    List.foldl_append
  have hid : e2.id ∈ (List.foldl step (([], []) : Store × List EventId) [e1]).2 := by
    have := id_in_seen [e1] (([], []) : Store × List EventId) e1 (List.mem_singleton_self e1)
    rwa [h] at this
  have hnoop := foldl_step_no_op [e2]
    (List.foldl step (([], []) : Store × List EventId) [e1]) (by
      intro e he
      rw [List.mem_singleton] at he
      subst he
      exact hid)
  rw [hsplit, hnoop]
