/-- The bug-seeded variant of the given fold (model_non_vacuity, G2): drops `n` from the
    recursive case, so a proof that genuinely depends on the real fold's semantics must fail
    to build against this file. -/
def total : List Nat -> Nat
  | [] => 0
  | (_n :: ns) => total ns
