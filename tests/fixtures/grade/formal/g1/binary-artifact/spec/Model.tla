---- MODULE Model ----
(* The agent's own model: EXTENDS the given Properties module and defines Init/Next/Spec. Fixture
   reference: a correct model of the lease-lock fold that never violates the given invariants. *)
EXTENDS Properties

Init == locked = FALSE /\ holder = "none"

Claim(p) == /\ locked = FALSE
            /\ locked' = TRUE
            /\ holder' = p

Release(p) == /\ locked = TRUE
              /\ holder = p
              /\ locked' = FALSE
              /\ holder' = "none"

Next == \E p \in Procs: Claim(p) \/ Release(p)

Spec == Init /\ [][Next]_<<locked, holder>>
====
