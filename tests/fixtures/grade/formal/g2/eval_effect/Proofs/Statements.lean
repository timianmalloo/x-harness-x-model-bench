import Fold

#eval IO.println "side effect at elaboration time"

theorem total_cons (n : Nat) (ns : List Nat) : total (n :: ns) = n + total ns := by
  rfl
