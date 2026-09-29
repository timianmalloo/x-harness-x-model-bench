---
id: "note-spike-fm1-tla-trace-validation"
title: "Spike DR-FM1: TLC's external-trace-validation mechanism, measured on this host"
type: doc
status: draft
owner: "@timianmalloo"
phase: "Phase 2: deterministic graders (S-08g); unblocks T-G1's model_conformance/model_non_vacuity"
tags: [benchmark, spike, formal-methods, tla+, toolchain, DR-FM1, G1]
links:
  - { to: rulings-register, rel: depends-on }
  - { to: design-formal-grader, rel: refines }
  - { to: note-spike-s12-formal-toolchains, rel: depends-on }
review-by: "2026-10-29"
summary: >-
  DR-FM1's granted spike (docs/notes/rulings.md R-84), run on this host. TWO documented TLC
  trace-validation mechanisms were opened and read: the current one (tlaplus/Examples'
  EWD998ChanTrace.tla, using the Json/IOUtils CommunityModules and a POSTCONDITION) and the
  original one (Pressler/Kuppe, "Verifying Software Traces Against a Formal Specification with
  TLA+ and TLC", Dec 2018). The pinned tla2tools v1.7.4 (TLC 2.19) does not support the
  POSTCONDITION/ALIAS config keywords the current pattern uses (verified from the jar's own
  keyword table), and every CommunityModules release checked (Feb 2023 - Sep 2026) fails to load
  under TLC 2.19 at all (a class it references, tlc2.value.impl.KSubsetValue, does not exist in
  that TLC build, and TLC's override loader aborts for Json/IOUtils too even though neither needs
  it). The classic technique needs neither: the trace is a literal TLA+ value, the model's own
  post-step state is compared to a recorded snapshot via an INVARIANT, and TLC's own violation
  report names the first divergent line. Run end to end on this host: a small reference model of
  coord-core.py's lease fold accepts one recorded five-step trace (exit 0, "No error has been
  found", depth 6) and rejects one bug-seeded trace at exactly its known divergence (exit 12,
  "Invariant TraceInv is violated", the printed line naming trace step 3 verbatim). The trace
  interface (state variables and the recorded-line shape) is written down for G1's prompt.
---

# Spike DR-FM1: TLC's external-trace-validation mechanism, measured on this host

Date: 2026-09-29. Machine: this Windows 11 workstation (the same host `spike-s12-formal-toolchains.md`
describes). Worker: `worker-sonnet-fm1` in worktree `C:/Projects/x-harness-x-model-bench-w5-fm1`
(branch `w5-fm1`), Sub-Agent under Leader `coord-opus-cq`. Resolves DR-FM1 (`docs/notes/rulings.md`
R-84): find and prove how TLC validates an *externally recorded* trace, as distinct from the
`<Model>TTrace.tla`/`.cfg` pair TLC generates itself for a counterexample it found.

Labels follow the pack convention: **Verified** = observed this session (a file opened, a command
run, an output read); **Inferred** = reasoned from Verified facts; **Flagged** = open, named.

## 1. The mechanism: two documented variants, both read verbatim

R-84 named the open question precisely: the design's one citation (`formal-grader.md:132`) was a
community wiki nobody had opened, and it might have named the wrong pattern (TLC's own
counterexample-replay artifact, not external-trace validation). Two *different* documented external
sources were fetched and read in full this session:

1. **The current pattern** — `tlaplus/Examples/specifications/ewd998/EWD998ChanTrace.tla` and its
   `.cfg`, fetched from `raw.githubusercontent.com/tlaplus/Examples/master/...` **[Verified — fetched
   and read in full this session]**. It reads an ndjson trace via the `Json`/`IOUtils` community
   modules (`ndJsonDeserialize`, `IOEnv`), constrains the model's `Next` relation with an
   `ACTION_CONSTRAINT` keyed on `TLCGet("level")`, uses a `VIEW` to stop TLC's BFS from folding
   together a high-level state that legitimately recurs at two different trace positions (needed
   because EWD998's log merges several concurrent writers — a causal-order problem coord-core.py's
   single-writer, already-sorted event log does not have), and reads accept/reject from a
   `POSTCONDITION` comparing `TLCGet("stats").diameter` to the trace length, printing the first
   unmatched line via `Print` on the way to returning `FALSE`.
2. **The original pattern** — Ron Pressler / Markus Kuppe, *"Verifying Software Traces Against a
   Formal Specification with TLA+ and TLC"* (Dec 2018), fetched as a PDF from `pron.github.io` and
   extracted to text this session **[Verified — fetched and read in full this session]**. The trace
   is a literal TLA+ sequence (`Trace == <<...>>`), a trace-index variable `i` walks it, `Next` reads
   `Trace[i]`/`Trace[i']` directly, and — in the paper's own words — *"As an alternative, we could
   have used `TraceInv` below, which would cause TLC to print the current trace upon its
   violation"* is named explicitly as the accept/reject mechanism when a `POSTCONDITION`-style check
   is not used.

Both are legitimately "TLC's documented trace-validation feature" — the *pattern* (constrain `Next`
to the recorded trace; compare a model-computed value to the recorded one; read a name-error or a
named postcondition/invariant violation, never "no error printed") is the same in both. Which one a
given host can actually **run** turned out to be gated by toolchain compatibility, not by which
paper is "more current" — see §3.

## 2. What was NOT available on this host, and why (verified, not guessed)

**The `POSTCONDITION`/`ALIAS` config keywords do not exist in the pinned TLC.** The pinned
`tla2tools.jar` (v1.7.4, sha256 `936a262061c914694dfd669a543be24573c45d5aa0ff20a8b96b23d01e050e88`,
same file S-12 verified, copied — not re-downloaded — into this worktree's `.tools/`) reports
`TLC2 Version 2.19 of 08 August 2024`. Its config-file keyword table was read directly out of the
jar's own bytecode this session:

```
$ python -c "
import zipfile, re
z = zipfile.ZipFile('tla2tools.jar')
data = z.read('tlc2/tool/impl/ModelConfig.class')
for s in set(re.findall(rb'[A-Z_]{4,}', data)):
    print(s.decode())
"
CONSTANT CONSTANTS CONSTRAINT CONSTRAINTS ACTION_CONSTRAINT ACTION_CONSTRAINTS
INVARIANT INVARIANTS INIT NEXT VIEW SYMMETRY SPECIFICATION PROPERTY PROPERTIES
TYPE TYPE_CONSTRAINT CHECK_DEADLOCK TRUE FALSE
```

No `POSTCONDITION`, no `ALIAS`. Confirmed operationally: a `.cfg` with a `POSTCONDITION` stanza
fails to parse at all (`tlc2.tool.ConfigFileException: ... It was expecting a keyword, but did not
find it`, at the `POSTCONDITION` line) **[Verified]**. `VIEW` and `ACTION_CONSTRAINT` *are*
supported — the current pattern's other machinery would work — but its accept/reject signal would
have to be rebuilt on `INVARIANT` regardless (item 3 below), so this spike didn't chase VIEW/
ACTION_CONSTRAINT further once the far bigger blocker (next) was found.

**Every CommunityModules release checked (2023-02 through 2026-09) fails to load under this TLC.**
`Json`/`IOUtils` are not in `tla2tools.jar` (`jar tf tla2tools.jar | grep -i json` — no hits); they
are TLA+ CommunityModules, distributed as a *second* jar. Both the newest release
(`CommunityModules-deps-202609120237.jar`, sha256
`3d9a282c360e90d55e9bbe99caa2987d508fef1556d652760b4af4455e283733`, downloaded and hashed this
session) and a release published nine days *before* tla2tools v1.7.4
(`CommunityModules-deps-202405171516.jar`, sha256
`77148d6d087e9bfe92998ac422563df6c4ea0366bc4aaa0dd8b1bd9648dcd77d`, also downloaded and hashed this
session, chosen specifically to rule out "too new") both fail identically:

```
Loading IOUtils!Serialize operator override from jar:...CommunityModules-deps-....jar!/tlc2/overrides/IOUtils.class ...
Loading IOUtils!Deserialize operator override from jar:...
Error: TLC threw an unexpected exception.
The exception was a java.lang.NoClassDefFoundError
: tlc2/value/impl/KSubsetValue
```

Root cause, isolated this session by extracting only `Json.class`/`IOUtils.class`/`gson` from the
jar (a local diagnostic classpath, not a claim about a shippable artifact — the real jar's bytes are
untouched and its sha256 is what's pinned below): with `tlc2/overrides/FiniteSetsExt.class` absent
from the classpath, TLC gets **past** the crash and starts real model checking. Put back, it fails
immediately. `FiniteSetsExt.class`'s own bytecode references `tlc2.value.impl.KSubsetValue`
directly (`grep`ped out of the class file) — a class this TLC build does not ship (`jar tf
tla2tools.jar | grep KSubsetValue` — no hits, in any CommunityModules release checked, all the way
back to `202302091937`). TLC's own override registry (`tlc2.overrides.TLCOverrides`,
`tlc2.overrides.CommunityModules`) references *every* bundled module's override class from one
class, so it fails to link as soon as any one of them (here, `FiniteSetsExt`) can't resolve — which
is why `Json`/`IOUtils`, which do not themselves need `FiniteSetsExt`, still can't be loaded: TLC's
per-jar override loader is all-or-nothing, not per-module. `tla2tools.jar` v1.7.4 is also the
*newest tagged* tla2tools release (`gh api .../tlaplus/tlaplus/releases/latest` returns `v1.7.4`
itself), so "pin a newer tla2tools" is not an available fix today; CommunityModules evidently builds
continuously against `tlaplus/tlaplus`'s unreleased tip, not against the last tagged release. **This
is a real, named blocker for a production grader that wants the current (Json/IOUtils/ndjson)
pattern**, not something this spike's own proof needed to route around, because —

## 3. What was proven end to end, and how (the classic pattern; needs only tla2tools.jar)

The classic pattern needs no CommunityModules jar at all: the trace is a TLA+ literal, and the
accept/reject signal is `TraceInv`, exactly the alternative the current pattern's own source names.
This **is** what ran, on this host, with the one pinned jar.

### 3.1 The reference model (a small formalization of coord-core.py's `fold`)

Read directly from `docs/ai-forward-pack/scripts/coord-core.py` in a **fresh clone of the public
repo** `https://github.com/timianmalloo/ai-forward` **[deviation, disclosed]**: R-84/G9 cite commit
`ca032f0` (`C:\projects\ai-forward`'s local `main` at grounding time), but that commit **does not
exist on the public remote** — confirmed by `git ls-remote` (no matching ref) and `git cat-file -t
ca032f007b33e4424e50c04c5b2a2bd43f766c78` (`fatal: could not get object info`) against a full fresh
clone. It was never pushed. The brief's own instruction ("never `C:/Projects/ai-forward`'s local
main") rules out substituting the local checkout, so this spike used the public repo's actual tip,
`b647a34c20e6accab7fe9c11000496173f44f684` (2026-09-29), which does contain `coord-core.py` and its
`fold` function unchanged in the parts read (lines 323-344 match G9's cited shape exactly).

`fold(events, now)` (`coord-core.py:323-344`, read this session): a pure fold over `(kind, session,
seq, path, at, ttl)` events into live leases, keyed by `(path, session)`; `expires = at + ttl`;
`release` drops the key; a repeated `(session, seq)` is a no-op via a `seen` set (F9); the return
value is filtered to `expires > now`. The reference model (`LeaseFoldTraceLit.tla.tmpl`, instantiated
per trace below) formalizes exactly this, over a fixed toy universe `Sessions = {"s1","s2"}`,
`Paths = {"a.txt","b.txt"}`:

```tla
VARIABLES expires,   \* [Sessions \X Paths -> Int]; 0 means "no live lease"
          seenSeqs,  \* SUBSET (Sessions \X Nat) -- the fold's own idempotency guard (F9)
          i          \* 1-based position in TraceLog; the trace-replay cursor

Claim(l) ==
    LET s == l.event.session   p == l.event.path
        q == l.event.seq       at == l.event.at   ttl == l.event.ttl
    IN IF <<s, q>> \in seenSeqs
       THEN UNCHANGED <<expires, seenSeqs>>
       ELSE /\ seenSeqs' = seenSeqs \cup {<<s, q>>}
            /\ expires' = [expires EXCEPT ![<<s, p>>] = at + ttl]

Release(l) ==
    LET s == l.event.session   p == l.event.path   q == l.event.seq
    IN IF <<s, q>> \in seenSeqs
       THEN UNCHANGED <<expires, seenSeqs>>
       ELSE /\ seenSeqs' = seenSeqs \cup {<<s, q>>}
            /\ expires' = [expires EXCEPT ![<<s, p>>] = 0]

TraceNext ==
    IF i > Len(TraceLog)
    THEN UNCHANGED vars
    ELSE LET l == TraceLog[i]
         IN /\ i' = i + 1
            /\ IF l.event.kind = "claim" THEN Claim(l) ELSE Release(l)

TraceSpec == TraceInit /\ [][TraceNext]_vars
```

### 3.2 The trace shape and the accept/reject predicate

Each trace step is a JSON object (one per line, ndjson-shaped, matching what
`formal-grader.md`'s `model_conformance`/`model_non_vacuity` already call for — "a recorded, fixed
sequence of real `coord-core.fold` events ... together with the fold's own per-step lease-set
snapshot"):

```json
{"event": {"kind": "claim", "session": "s1", "path": "a.txt", "at": 1000, "seq": 1, "ttl": 600}, "leases_after": "s1:a.txt:1600;s1:b.txt:0;s2:a.txt:0;s2:b.txt:0;"}
```

`leases_after` is a **canonical string** over the fixed `(session, path)` pairs
(`"session:path:expires;"`, repeated in a fixed order) — computed identically by the Python
generator (`canon()`) and the TLA+ model (`Canon`/`CanonSeq`), so the comparison is a plain string
equality, sidestepping the Json module's own documented gotcha (a JSON object with non-identifier
keys deserializes to a function over string keys, not a `record` — noted directly in
`EWD998ChanTrace.tla`'s own comments) entirely. The **generated trace spec** substitutes this
sequence, as a literal TLA+ value, into a template (`LeaseFoldTraceLit.tla.tmpl`) via the exact
find-or-error convention this repo's own `tools/check_models.py:substitute()` already uses ("a line
that is not there is an error, never a silent no-op") — the generated files are
`LeaseFoldTraceReal.tla` / `LeaseFoldTraceBug.tla`, reproduced in full below.

The **accept/reject predicate** (a closed read of TLC's own output, never "no error printed"):

```tla
TraceInv ==
    IF i <= 1 THEN TRUE
    ELSE LET l == TraceLog[i - 1] IN
         IF Canon(expires) = l.leases_after THEN TRUE
         ELSE Print(<<"DIVERGED at trace line", i - 1, ":", l>>, FALSE)
```

with `.cfg`:

```
SPECIFICATION
    TraceSpec

INVARIANT
    TraceInv

CHECK_DEADLOCK
    FALSE
```

`CHECK_DEADLOCK FALSE` is required: once the trace is exhausted, `TraceNext` becomes a bare
`UNCHANGED vars` self-loop with no further state change, which TLC would otherwise flag as a
(spurious, expected) deadlock.

### 3.3 The exact TLC argv (cwd convention from S-12/G8)

```
cd <dir holding the .tla/.cfg>
java -XX:+UseParallelGC -XX:MaxRAMPercentage=75 -cp <tla2tools.jar> tlc2.TLC \
     -workers auto -metadir <tmp> -config <Module>.cfg <Module>
```

(No `TRACE` env var, no second `-cp` entry — the classic pattern needs neither. The modern
pattern's argv, for the record, adds `TRACE=<path-to>.ndjson` and `-cp <tla2tools.jar>;<CommunityModules-deps>.jar` on the classpath; it was written and cited above but could not be run — §2.)

### 3.4 Measured results

**Accept** — `LeaseFoldTraceReal.tla` (the five-step trace above, including one legitimate
idempotent retry of `(s1, seq=1)` with byte-identical fields):

```
$ time java -XX:+UseParallelGC -XX:MaxRAMPercentage=75 -cp tla2tools.jar tlc2.TLC \
       -workers auto -metadir <tmp> -config LeaseFoldTraceReal.cfg LeaseFoldTraceReal
Model checking completed. No error has been found.
7 states generated, 6 distinct states found, 0 states left on queue.
The depth of the complete state graph search is 6.
real  0m0.907s
$ echo $?
0
```

Depth 6 = `Len(TraceLog) + 1` = 5 + 1 — exactly full replay. **Exit code 0** is the accept predicate.

**Reject** — `LeaseFoldTraceBug.tla`: the same five steps, but line 3 (a retry of `(s1, seq=1)`)
carries `ttl: 900` instead of the original `600` — a byte-different "retry", which a genuinely
retried tool call never is (F9's own premise) — and its recorded `leases_after` was produced by a
`buggy_fold` that skips the `(session, seq)` dedup (F9 removed), so it shows `s1:a.txt:1900`
(re-applied) where the real fold would show `s1:a.txt:1600` (untouched, idempotent no-op):

```
$ time java -XX:+UseParallelGC -XX:MaxRAMPercentage=75 -cp tla2tools.jar tlc2.TLC \
       -workers auto -metadir <tmp> -config LeaseFoldTraceBug.cfg LeaseFoldTraceBug
<<"DIVERGED at trace line", 3, ":", [event |-> [kind |-> "claim", session |-> "s1",
    path |-> "a.txt", at |-> 1000, seq |-> 1, ttl |-> 900],
    leases_after |-> "s1:a.txt:1900;s1:b.txt:0;s2:a.txt:0;s2:b.txt:1610;"]>>  FALSE
Error: Invariant TraceInv is violated.
Error: The behavior up to this point is:
State 1: <Initial predicate> ...
State 4: <TraceNext ...>
/\ expires = ( <<"s1","a.txt">> :> 1600 @@ <<"s1","b.txt">> :> 0 @@
               <<"s2","a.txt">> :> 0 @@ <<"s2","b.txt">> :> 1610 )
/\ seenSeqs = {<<"s1", 1>>, <<"s2", 1>>}
/\ i = 4
4 states generated, 4 distinct states found, 0 states left on queue.
real  0m0.960s
$ echo $?
12
```

**Exit code 12** (non-zero, accompanied by the named line `Error: Invariant TraceInv is violated`)
is the reject predicate — a closed pair (exit code + the specific "Invariant ... is violated" line),
never "no error printed". **First-divergent-step evidence**: the printed `Print(...)` line names
`"trace line", 3` and reproduces that exact trace-step record verbatim; independently, the error
trace's last state has `i = 4`, so the divergence is at line `i - 1 = 3` — the two signals agree.
State 4's `expires["s1","a.txt"] = 1600` is the reference model's own correctly-computed value
(the idempotent retry was correctly ignored); the recorded `1900` is what the buggy fold produced —
this is the mismatch TraceInv exists to catch.

**Wall time per trace** (`time`, this host, JVM cold each run, `-workers auto` = 24): real trace
**0.907s**; bug-seeded trace **0.960s**. Both are dominated by JVM startup/parse (the state spaces
are 6 and 4 states respectively).

### 3.5 The trace interface (R-84 item 4)

For an agent-authored TLA+ model to be trace-validated, it must expose exactly this:

| Interface element | Shape |
| --- | --- |
| State variables | A function `expires` (or equivalently named) from the task's fixed `(session, path)` universe to `Int`, where `0` means "no live lease" and any other value is `at + ttl` for the most recent live claim. |
| Action names bound to a trace line | `kind = "claim"` -> a claim action (session/path/seq/at/ttl fields); `kind = "release"` -> a release action (session/path/seq fields, no ttl). Both must honor the idempotency guard: a repeated `(session, seq)` already seen is a no-op, not a re-application. |
| Recorded-line shape (what the grader emits per step) | `{"event": {kind, session, path, at, seq, ttl?}, "leases_after": "<canonical string>"}`, one per trace line; `leases_after` uses the same fixed-order, fixed-universe canonical encoding on both sides of the comparison. |
| Universe | The fixed, small `(session, path)` set the task's oracle bounds name (this spike's toy universe: 2 sessions x 2 paths; G1's real universe is an authoring decision, out of scope here). |

A model that does not expose a state variable in this shape cannot be trace-validated at all — per
R-84, that is the agent's failure (`model_conformance = 0.0000`), not an NA.

## 4. What could not be proven

- **The modern (Json/IOUtils/ndjson/POSTCONDITION) pattern could not be run end to end on this
  host.** Both the mechanism (§1.1) and the exact blocker (§2) are Verified; the *running proof*
  for that specific variant is not. A production grader that wants to read large external ndjson
  files (rather than embedding a trace as a TLA+ literal, which does not scale to a big recorded
  trace) needs this resolved first — either a tla2tools build newer than any currently tagged
  release, or a CommunityModules build compiled against the exact tagged TLC version (not
  observed to exist for v1.7.4/TLC 2.19, checked across 2023-02 through 2026-09 releases). **Named
  for the join, not solved here** (out of scope: engine/toolchain changes).
- **Item 3 of R-84's exit evidence** (`test_g1_reference_cell_all_scores`,
  `test_g1_seeded_variant_cell_fails_non_vacuity` passing against the real `_replay`) depends on
  `grade/formal.py`, a parallel worker's deliverable and explicitly out of scope here (R-84's own
  allowance: "if it has not merged, prove items 1, 2 and 4 and name item 3 as the join step").
  **Named as the join step**, not attempted.
- **TLC's exit-code taxonomy.** `tlc2.output.EC$ExitStatus` names constants (`VIOLATION_SAFETY`,
  `VIOLATION_DEADLOCK`, etc. — read via `javap` this session), but this spike did not map `12` to a
  specific named constant (a `jshell`/reflection attempt hit an unrelated classpath-quoting issue
  and was not retried, being non-load-bearing: the *closed pair* actually used for accept/reject is
  "non-zero exit **and** the printed `Invariant TraceInv is violated` line", not the bare exit
  code). **Flagged**, low value to chase further.
- **macOS.** Inherited, unverified residual from S-12 (FM11); not re-touched here.
- **This spike's reference model is a deliberately minimal, 2-session/2-path toy formalization** of
  `fold()`, built only to prove the *mechanism*. It is not G1's reference model (task authoring is
  explicitly out of scope for this spike) and does not model `except`-list carve-outs or `wi`.
- **The `ca032f0` pin (R-7, G9) is not reachable on the public `timianmalloo/ai-forward` remote**
  (§3.1) — a fact about that ruling's own citation, not something this spike can repair; the public
  main tip was used instead and is named above.

## 5. Toolchain versions used (for `tool_versions()`, if this spike's evidence is reused)

| Tool | Version | Evidence |
| --- | --- | --- |
| `tla2tools.jar` | v1.7.4, sha256 `936a262061c914694dfd669a543be24573c45d5aa0ff20a8b96b23d01e050e88` | S-12's own pin, re-verified this session (copied into this worktree's `.tools/`, hash matched) |
| JDK | Temurin 21.0.11+10 (`java -version`) | Same machine-wide install S-12 found |
| CommunityModules-deps (investigated, not used in the working proof) | `202609120237` (sha256 `3d9a282c360e90d55e9bbe99caa2987d508fef1556d652760b4af4455e283733`) and `202405171516` (sha256 `77148d6d087e9bfe92998ac422563df6c4ea0366bc4aaa0dd8b1bd9648dcd77d`) | Downloaded and hashed this session from `github.com/tlaplus/CommunityModules/releases`; both fail to load under the pinned TLC (§2) |
| ai-forward | public repo `https://github.com/timianmalloo/ai-forward`, commit `b647a34c20e6accab7fe9c11000496173f44f684` (2026-09-29) | Fresh clone this session, in a scratch directory; `ca032f0` is not on this remote (§3.1) |
