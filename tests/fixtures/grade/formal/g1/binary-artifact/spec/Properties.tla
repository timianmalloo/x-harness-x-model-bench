---- MODULE Properties ----
(* The given, frozen safety properties for the G1 lease-lock fold (fixture: a minimal stand-in for
   coord-core.py's real lease protocol, S-08g). The agent's own model (spec/Model.tla) EXTENDS this
   module and is never hashed by statement_integrity; only this file is. *)
EXTENDS Naturals

CONSTANTS Procs

VARIABLES locked, holder

TypeOK == /\ locked \in BOOLEAN
          /\ holder \in (Procs \cup {"none"})

AtMostOneHolder == locked = FALSE => holder = "none"
====
