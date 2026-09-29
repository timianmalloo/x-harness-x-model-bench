# G2 oracle evidence

Host: the same Windows 11 operator workstation as spike S-12. Toolchain: `elan 4.2.4`,
`leanprover/lean4:v4.34.1` (already warm at `%USERPROFILE%/.elan/toolchains/`, per S-12). All
commands invoked directly (never `cmd.exe`), forward-slash paths, `lake.exe` at
`%USERPROFILE%/.elan/bin/lake.exe`. `cwd` is given relative to the repo root.

## 1. The given (unfilled) workspace stub builds — with `sorry` only, never a hard error

```
cwd: tasks/G2/workspace/Proofs
$ %USERPROFILE%/.elan/bin/lake.exe build
```
Output:
```
info: Proofs: no previous manifest, creating one from scratch
info: toolchain not updated; already up-to-date
✔ [2/5] Built Fold (486ms)
⚠ [4/5] Built Statements (458ms)
warning: Statements.lean:22:8: declaration uses `sorry`
warning: Statements.lean:33:8: declaration uses `sorry`
Build completed successfully (5 jobs).
```
Exit code: `0`. Wall time: 1.05s (cold, first build in this working copy; toolchain already warm).
This is the discriminating "base" state for this scenario: it type-checks (a malformed workspace
would hard-error here) but proves nothing yet (`sorryAx`, confirmed next), analogous to a hidden
test failing on the base commit in every other scenario.

`#print axioms` on the two given (unfilled) theorems:
```
cwd: tasks/G2/workspace/Proofs
$ %USERPROFILE%/.elan/bin/lake.exe env lean CheckStatements.lean
```
where `CheckStatements.lean` (not committed — a scratch, throwaway script) is:
```lean
import Statements
#print axioms fold_replay_is_idempotent
#print axioms retried_event_is_a_no_op
```
Output:
```
'fold_replay_is_idempotent' depends on axioms: [sorryAx]
'retried_event_is_a_no_op' depends on axioms: [sorryAx]
```
Exit code: `0`. This is exactly what `formal_checks_clean` must score `0` on (design
`formal-grader.md`'s `#print axioms` clause).

## 2. The reference proofs build clean, `#print axioms` is standard-only

```
cwd: tasks/G2/oracle/reference/Proofs
$ %USERPROFILE%/.elan/bin/lake.exe build
```
Output:
```
info: Proofs: no previous manifest, creating one from scratch
info: toolchain not updated; already up-to-date
✔ [2/5] Built Fold (508ms)
⚠ [4/5] Built Statements (451ms)
warning: Statements.lean:61:10: `if_pos` has been deprecated: Use `ite_eq_left` instead
Build completed successfully (5 jobs).
```
Exit code: `0`. Wall time: 1.09s (clean; toolchain already warm — no network call observed, no
`.tools`/toolchain download in the log). The one warning is a deprecated-lemma-name lint
(`if_pos` still resolves and is not `sorry`/an axiom); it does not affect `formal_checks_clean`'s
lexical or axiom checks.

`#print axioms` and `#check` on the same two theorems, now filled in:
```
cwd: tasks/G2/oracle/reference/Proofs
$ %USERPROFILE%/.elan/bin/lake.exe env lean CheckStatements.lean
```
where `CheckStatements.lean` (not committed) is:
```lean
import Statements
#print axioms fold_replay_is_idempotent
#print axioms retried_event_is_a_no_op
#check @fold_replay_is_idempotent
#check @retried_event_is_a_no_op
```
Output:
```
'fold_replay_is_idempotent' depends on axioms: [propext, Quot.sound]
'retried_event_is_a_no_op' depends on axioms: [propext, Quot.sound]
fold_replay_is_idempotent : ∀ (events : List Event) (now : Nat), fold (events ++ events) now = fold events now
retried_event_is_a_no_op : ∀ (e1 e2 : Event) (now : Nat), e1.id = e2.id → fold [e1, e2] now = fold [e1] now
```
Exit code: `0`. Wall time: 0.50s. Axioms are a subset of `{propext, Classical.choice,
Quot.sound}` for both — no `sorryAx`, no custom axiom — exactly what US-32 / `formal_checks_clean`
requires.

**The `#check` text is byte-identical between the given (unfilled, `sorry`) `Statements.lean` and
the reference (filled) one** (diffed directly): the elaborated *type* of a declaration never
depends on its proof term, which is the property `statement_integrity`'s clause (c) relies on
(agent proof work never changes `formal.statement_hash`). Confirmed, not assumed.

## 3. The reference proofs fail to build against the bug-seeded `Fold.lean`

Setup: a scratch working copy with `oracle/reference/Proofs/{lakefile.toml, lean-toolchain,
Statements.lean}` unchanged, and `Fold.lean` replaced by `oracle/fold-buggy/Fold.lean` (the
`(session, seq)` dedup guard removed from `step` — S5 in `README.md`).

```
cwd: <scratch>  (lakefile.toml, lean-toolchain, Statements.lean from oracle/reference/Proofs/;
                 Fold.lean from oracle/fold-buggy/)
$ %USERPROFILE%/.elan/bin/lake.exe build
```
Output (excerpt; full log is 30 lines of Lean elaboration errors):
```
✖ [3/5] Building Statements (441ms)
error: Statements.lean:10:4: Tactic `rfl` failed: The left-hand side
  (acc.fst.set e.key e.expiresAt, e.id :: acc.snd).snd
is not definitionally equal to the right-hand side
  if acc.snd.contains e.id = true then acc.snd else e.id :: acc.snd
...
error: Statements.lean:61:10: Tactic `rewrite` failed: Did not find an occurrence of the pattern
  if acc.snd.contains e0.id = true then ?m.56 else ?m.57
in the target expression
  (if e0.isClaim = true then (acc.fst.set e0.key e0.expiresAt, e0.id :: acc.snd)
    else (acc.fst.drop e0.key, e0.id :: acc.snd)) =
    acc
...
Some required targets logged failures:
- Statements
error: build failed
```
Exit code: `1`. Wall time: 1.09s. This is a genuine compile failure, not a vacuous pass: the
reference proof's shared lemma (`foldl_step_no_op`, used by both theorems) pattern-matches
directly on `step`'s `if acc.2.contains e.id then ... else ...` shape, which the seeded bug
removes — the proof breaks because it actually depends on the dedup guard the bug deletes. This
is the required "proofs fail on the bug-seeded variant" evidence (`tasks/README.md` scenario-7
rule; R-84 condition 2's US-2 clause-three reproducing test).

## 4. Warm-rebuild wall time (no changes, cache replay)

```
cwd: tasks/G2/oracle/reference/Proofs
$ %USERPROFILE%/.elan/bin/lake.exe build
```
Output: `⚠ [4/5] Replayed Statements` / `Build completed successfully (5 jobs).` Exit `0`. Wall
time: 0.19s. Recorded for comparison only — the task's 45-minute budget has ample headroom over
either the ~1.1s cold-in-this-copy build or the ~0.2s warm replay; the toolchain itself (not
shown here) took 54.3s to install once, per S-12, which is why it is warmed host-level and not
per task run.

## 5. `bench validate`

```
$ uv run bench validate
```
Output: `ok` (run after `task.yaml` was advanced to `status: ready`; see the worker's final
report for the exact transcript).
