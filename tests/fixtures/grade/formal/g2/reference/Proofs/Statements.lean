import Fold

/-- theorem_names names this declaration; statement_integrity hashes only its elaborated type. -/
theorem total_cons (n : Nat) (ns : List Nat) : total (n :: ns) = n + total ns := by
  rfl
