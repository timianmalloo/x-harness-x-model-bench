# Prove two Lean 4 theorems about a lease fold

`Proofs/Fold.lean` is a Lean 4 translation of a real coordination-log fold: a pure function
`fold : List Event -> Nat -> Store` that replays a list of `claim`/`release` events into the set
of currently live leases, de-duplicating retried events by `(sess, seq)`. Read it before you
start; it is short and fully commented.

`Proofs/Statements.lean` states two theorems about `fold`, each with a `sorry` in place of its
proof. Replace both `sorry`s with real proofs. You may add helper lemmas, in `Statements.lean`
itself or in new `.lean` files anywhere under `Proofs/`, and `import` them from `Statements.lean`.

The two theorems:

1. `fold_replay_is_idempotent` — replaying the same list of events twice in a row (`events ++
   events`) yields the same live-lease set as replaying it once.
2. `retried_event_is_a_no_op` — given two events that carry the same `(sess, seq)` identity, the
   second one changes nothing: folding `[e1, e2]` gives the same result as folding `[e1]` alone.

Rules:

- Do not edit `Fold.lean`, `lakefile.toml`, or `lean-toolchain`. Do not change the *statement*
  (the type) of either theorem above — only replace `sorry` with a proof term. Adding helper
  lemmas or new files is fine; changing what the two named theorems assert is not.
- The project has no Mathlib and no external dependencies (`lakefile.toml` has no `[[require]]`
  entries, and none may be added). Prove everything from Lean 4's own core library (`Init`).
- No `sorry`, `admit`, `native_decide`, `#eval`, `initialize`, `run_cmd`, `unsafe`, or
  `@[extern]` anywhere under `Proofs/`.
- When you are done, `lake build` (run from the `Proofs/` directory) must exit `0`, and
  `#print axioms` on each of the two theorems must list only some subset of `propext`,
  `Classical.choice`, and `Quot.sound` — no `sorryAx`, no custom axiom.
- `elan` and `lake` are already installed and the `lean4:v4.34.1` toolchain is already warmed on
  this machine; you do not need network access to build.
