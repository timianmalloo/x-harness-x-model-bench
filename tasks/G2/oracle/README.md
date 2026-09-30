# G2 oracle — Lean 4 proofs of fixed statements about the lease fold

## S1. Source pin

`formal.commit` (via `source.commit`) pins `ai-forward` at
`b647a34c20e6accab7fe9c11000496173f44f684`, read from a **fresh clone**
(`git clone https://github.com/timianmalloo/ai-forward.git`, into a scratch directory outside
this repo and outside `C:/Projects/ai-forward`) — never the local `C:/Projects/ai-forward`
checkout, per the brief's instruction that the pin must come from a clone whose state is exactly
what that public SHA reproduces. `ai-forward` is Apache-2.0 licensed
(`ai-forward-fresh/LICENSE`); `Fold.lean` below is an original Lean re-implementation, not a
verbatim copy of the Python source text, so no `LICENSE` file is carried into this task folder —
only the correspondence (S2) and the commit pin (S1) are reused.

The lease fold lives at `pack/scripts/coord-core.py:323-344` in that clone (identical byte-for-
byte to `docs/ai-forward-pack/scripts/coord-core.py` in the same clone — checked with `diff`,
they are the same file vendored twice):

```python
def fold(events, now):
    """Pure fold: events -> live leases. Replaying is idempotent (NFR-R1).

    derive-don't-store (DM7): `expires` is computed here (at + ttl) and never persisted.
    Two stored definitions of one quantity is the defect signature.
    """
    leases, seen = {}, set()
    for event in events:
        ident = (event.get("session"), event.get("seq"))
        if ident in seen:            # F9: a retried tool call must not take a second lease
            continue
        seen.add(ident)
        key = (event.get("path"), event.get("session"))
        if event.get("kind") == "claim":
            leases[key] = {"path": event["path"], "session": event["session"],
                           "agent": event.get("agent", event["session"]),
                           "wi": event.get("wi", ""),
                           "except": list(event.get("except", [])),
                           "expires": event["at"] + event.get("ttl", TTL_DEFAULT)}
        elif event.get("kind") == "release":
            leases.pop(key, None)
    return {k: v for k, v in leases.items() if v["expires"] > now}
```

## S2. Correspondence: `Fold.lean` vs. the Python `fold`

| Python | Lean (`Proofs/Fold.lean`) | Note |
| --- | --- | --- |
| `event.get("session")`, `event.get("seq")` | `Event.sess`, `Event.seq` : `Nat` | The Python values are opaque strings/ints, compared only for equality; `Nat` is a faithful stand-in because these theorems never do arithmetic on them, only equality-test them (as the Python does). |
| `ident = (session, seq)` | `Event.id : EventId := (e.sess, e.seq)`, `EventId := Nat × Nat` | Direct transliteration. |
| `if ident in seen: continue` / `seen.add(ident)` | `step`'s outer `if acc.2.contains e.id then acc else ...` | The Python `seen: set()` becomes a `List EventId` tested with `List.contains`; `seen.add` becomes consing `e.id` onto the accumulator. |
| `key = (event.get("path"), event.get("session"))` | `Event.key : Nat` | Same reasoning as `sess`/`seq`: the Python fold only ever tests two keys for equality (dict lookup, `leases[key] = ...`, `leases.pop(key, None)`), never inspects `path`'s structure, so one `Nat` per distinct real `(path, session)` pair is behaviourally identical for these theorems. This is a genuine simplification (not every possible Lean `Nat` pair is reachable from a real `(str, str)` pair), but neither theorem below depends on `key`'s internal structure — only on Lean/DecidableEq equality between two `key`s — so the simplification changes nothing the theorems can observe. |
| `leases[key] = {...}` | `Store.set : Store -> Nat -> Nat -> Store` (cons the new pair, filter out the old one at that key) | The Python dict assignment is "replace-or-insert"; `Store.set` does the same over an association list. Only `expires` is carried into `Store` (`Store := List (Nat x Nat)`, key -> expiry) — the other fields (`path`, `session`, `agent`, `wi`, `except`) are never read by `fold`'s return value or by either theorem, so they are omitted rather than carried as dead weight (Solution-Selection Ladder: YAGNI). |
| `leases.pop(key, None)` | `Store.drop` | Direct transliteration (filter out the key). |
| `event["at"] + event.get("ttl", TTL_DEFAULT)` | `Event.expiresAt : Nat` | The Python computes this sum once, before folding (DM7: "derive, don't store" — `expires` is computed, never persisted). The Lean model takes the already-computed sum as a field of `Event`, which is the same choice one level earlier: nothing in either theorem depends on how `expiresAt` was derived, only on its value being compared against `now`. |
| `{k: v for ... if v["expires"] > now}` | `fold events now := (foldRaw events).1.filter (fun p => now < p.2)` | Direct transliteration of the final filter. |
| `leases, seen = {}, set()` (initial state) | `foldRaw events := events.foldl step (([], []))` | Direct transliteration of the initial accumulator and the `for event in events` loop as a `List.foldl`. |

**What is intentionally not modelled:** the `agent`, `wi`, and `except` fields (never read by
`fold`'s own logic, only by `check`, which is out of scope — these two theorems are about `fold`
alone); `TTL_DEFAULT` (folded into `expiresAt` being a plain `Nat`, S2 row above);
`event.get("kind")` being a free-text string with values other than `"claim"`/`"release"`
(`Event.isClaim : Bool` is exhaustive by construction, matching the Python `if .. elif ..`
which silently no-ops on any third value — the Lean model's `if .. then .. else ..` is
`Bool`-exhaustive, so there is no third case to omit).

## S3. Where the theorem statements came from

Per `tasks/README.md`'s scenario-7 rule ("take the properties from the source project's own
docs and tests, not from your reading of its code") and the `/new-bench-task` skill, both
theorems are taken verbatim from `ai-forward`'s own documentation and its own test suite for
`fold` — never invented from reading `coord-core.py` cold:

1. **`fold_replay_is_idempotent`** — `NFR-R1`, stated in `docs/specs/agent-coordination.md`:
   *"Replaying the record twice yields identical folded state."* Backed by
   `tests/docs_explorer/test_coord_core.py::FoldTests::test_T2_fold_is_idempotent_under_replay`:
   ```python
   first = self.m.fold(events, now + 2)
   second = self.m.fold(events, now + 2)
   self.assertEqual(first, second)
   self.assertEqual(self.m.fold(events + events, now + 2), first,
                    "replaying the same events twice changed the folded state")
   ```
   The Lean statement formalizes the second assertion (`fold(events + events, now) ==
   fold(events, now)`), which is the one that actually exercises replay (the first assertion,
   `fold(events, x) == fold(events, x)`, is reflexivity and states nothing).

2. **`retried_event_is_a_no_op`** — `F9`, stated in `docs/design/coord-core-phase1.md`'s
   boundary-set table: *"The same claim emitted twice (a retried tool call) — **PREVENT**.
   Idempotent by `(session, seq)`; re-emitting is a no-op, not a second lease."* Backed by
   `tests/docs_explorer/test_coord_core.py::FoldTests::test_T15_duplicate_seq_is_idempotent`:
   ```python
   self.claim("s1", "src/**", at=now, seq=1)
   self.claim("s1", "src/**", at=now, seq=1)
   events, _, _ = self.m.read_events(self.root)
   self.assertEqual(len(events), 2, "both writes landed (expected -- the file is append-only)")
   self.assertEqual(len(self.m.fold(events, now)), 1, "a replayed event produced a second lease")
   ```
   The Lean statement generalizes this from "the exact same claim, replayed" to "any two events
   sharing an id" (`e1.id = e2.id`, `e1` and `e2` otherwise arbitrary), because F9's own prose
   names the guard as `(session, seq)` alone, not byte-identical content — the stronger statement
   is what the design and the Python `ident in seen` check actually guarantee, and it is what
   `foldl_step_no_op` (the reference proof's key lemma) needs to be true of the fold in general,
   not merely of one specific replayed instance.

No other property of `fold` (e.g. `T5`'s expiry behaviour, which belongs to `check`, not `fold`
itself) is claimed here — scenario 7's "fixed statements" are exactly these two, matching
`task.yaml`'s `formal.theorem_names`.

## S4. Toolchain

Pinned per spike S-12 (`docs/notes/spike-s12-formal-toolchains.md`): `elan 4.2.4`,
`leanprover/lean4:v4.34.1`, no Mathlib (`lakefile.toml` has no `[[require]]` entries). Both are
already warm on this host (`~/.elan/toolchains/leanprover--lean4---v4.34.1`, 3.1 GB, per-user,
outside every working copy). `lake build` needs no network once the toolchain is warm — verified
in `evidence.md`.

**macOS [Assume]:** this task has only been authored and proved on Windows (this host), matching
S-12's own residual gap. **Assume:** elan and Lean 4 both publish macOS release archives (S-12
verified this by checking `gh api repos/leanprover/elan/releases/latest` directly), so the same
`elan` -> `lean-toolchain` pin -> `lake build` path works unchanged on macOS. **What would
confirm it:** a `macos-latest` CI job running this task's `lake build` once, as S-12 itself names
as its own next step. **What breaks if false:** a path-resolution or case-sensitivity quirk in
`lake`/`elan` specific to macOS — low probability (the proofs use only `Init`, no OS-facing code
at all), but unverified until that CI job exists.

## S5. The seeded bug and its reproducing test

**Seeded bug (`oracle/fold-buggy/Fold.lean`):** the `(session, seq)` replay-dedup guard is
removed from `step` — as if the Python `if ident in seen: continue` / `seen.add(ident)` pair
(coord-core.py:332-334) had been deleted, i.e. every event is applied unconditionally. This is a
realistic, minimal, single-purpose regression: exactly the line F9 exists to protect, and exactly
what `test_T15_duplicate_seq_is_idempotent` would catch on the Python side. It is not a hash- or
signature-level edit (that is what `statement_integrity`, a separate score, already catches) — it
is a semantic change to the given `Fold.lean` that a hash check cannot see, which is the entire
point of `model_non_vacuity`.

**Reproducing test:** `evidence.md` §3 swaps this file in for the real `Proofs/Fold.lean` (the
agent's `Statements.lean` — i.e., the reference proof, unmodified — untouched) and runs the exact
same `lake build` used for the real fold. The build **fails**: both reference proofs (which both
route through the shared lemma `foldl_step_no_op`, whose proof pattern-matches on `step`'s
`if acc.2.contains e.id then ...` shape) no longer type-check against the bug-seeded `step`,
because that shape is gone. This is a real compile failure, not a vacuous pass-either-way result
— the reference proof genuinely depends on the dedup guard's presence, which is what
`model_non_vacuity` requires (design `formal-grader.md` G2 clause, `oracle/fold-buggy/Fold.lean`
swapped in, agent proof files untouched, build must fail).

## S6. `formal.statement_hash`, computed

`formal.statement_hash` follows the design's recipe (`formal-grader.md` §`statement_integrity`,
"G2"): a `plan.tree_hash`-shaped hash (`plan.py:91-97` — sha256, entries in casefold-sorted
order, each entry `path.encode() + b"\0" + content.replace(CRLF, LF) + b"\0"`) over:

- `Proofs/Fold.lean` (full bytes, from `workspace/Proofs/`);
- `Proofs/lakefile.toml` and `Proofs/lean-toolchain` (full bytes);
- for each name in `formal.theorem_names`, a synthetic entry labelled
  `Proofs/Statements.lean::<name>` whose content is that name's `#check` rendering (captured with
  `lake env lean <script>.lean`, `evidence.md` §2) plus a trailing newline. The design leaves this
  synthetic label unspecified; this is the one that materialized it, recorded here so the future
  grader implementation matches this value exactly rather than re-deriving a different one.

Recomputing this hash from a changed `Fold.lean`, `lakefile.toml`, `lean-toolchain`, or either
theorem's *type* will produce a different digest, exactly as `statement_integrity` requires; a
changed proof *term* (the agent's real work) does not change `#check`'s output, so it does not
change the hash — confirmed directly in `evidence.md` §2 (the unfilled, `sorry`-bodied given
`Statements.lean` and the filled reference produce byte-identical `#check` text).

## S7. `bench validate`

`ok` — see the worker's final report for the exact run.
