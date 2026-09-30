/-- fold-fixture: sums a list of naturals (stand-in given definition for G2's real fold). -/
def total : List Nat -> Nat
  | [] => 0
  | (n :: ns) => n + total ns
