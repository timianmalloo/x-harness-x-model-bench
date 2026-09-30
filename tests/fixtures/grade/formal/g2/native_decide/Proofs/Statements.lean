import Fold

theorem total_cons (n : Nat) (ns : List Nat) : total (n :: ns) = n + total ns := by
  rfl

example : total [1, 2] = 3 := by native_decide
