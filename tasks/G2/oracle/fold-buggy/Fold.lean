/-!
Fold.lean -- BUG-SEEDED VARIANT for `model_non_vacuity` grading only (never shown to the agent).
This is coord-core.py's `fold`, translated exactly as `../../workspace/Proofs/Fold.lean` is,
EXCEPT the `(session, seq)` replay-dedup guard has been removed from `step` -- as if the Python
`if ident in seen: continue` line (coord-core.py:332-333) had been deleted. See `../README.md`
S5 for why this is a faithful, minimal seed of a real regression class, and `../evidence.md` for
the exact `lake build` command and its failure against the (unmodified) reference proofs.
-/

structure Event where
  sess      : Nat
  seq       : Nat
  key       : Nat
  isClaim   : Bool
  expiresAt : Nat
  deriving DecidableEq, Repr

abbrev EventId := Nat × Nat

def Event.id (e : Event) : EventId := (e.sess, e.seq)

abbrev Store := List (Nat × Nat)

def Store.set (s : Store) (k v : Nat) : Store :=
  (k, v) :: s.filter (fun p => p.1 != k)

def Store.drop (s : Store) (k : Nat) : Store :=
  s.filter (fun p => p.1 != k)

-- BUG (seeded): the (session, seq) dedup guard is gone. Every event is applied unconditionally,
-- so a retried/duplicate event is no longer a no-op -- F9 and NFR-R1 both cease to hold in
-- general (a duplicate id with a different `key` now creates a second, genuinely different
-- lease instead of being dropped).
def step (acc : Store × List EventId) (e : Event) : Store × List EventId :=
  if e.isClaim then
    (acc.1.set e.key e.expiresAt, e.id :: acc.2)
  else
    (acc.1.drop e.key, e.id :: acc.2)

def foldRaw (events : List Event) : Store × List EventId :=
  events.foldl step (([], []))

def fold (events : List Event) (now : Nat) : Store :=
  (foldRaw events).1.filter (fun p => now < p.2)
