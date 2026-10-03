---
id: "design-eval-campaign-record"
title: "W1-C design: the campaign record and `bench campaign`"
type: design
status: proposed
owner: "@timianmalloo"
phase: "Enterprise evaluation: Wave 1 (W1-C; builds as X-C in E1)"
tags: [benchmark, campaign, ledger, freeze, locks, evaluation-campaign]
links:
  - { to: spec-enterprise-evaluation, rel: implements }
  - { to: arch-evaluation-campaign, rel: implements }
  - { to: adr-0016-campaign-record, rel: depends-on }
  - { to: adr-0017-engine-identity-and-freeze, rel: depends-on }
  - { to: adr-0018-hidden-check-harness, rel: depends-on }
  - { to: adr-0006-results-data-model, rel: depends-on }
  - { to: design-eval-seam-contracts, rel: depends-on }
review-by: "2026-10-17"
summary: >-
  Designs campaign.py and the `bench campaign` commands (revision 2): a closed 11-kind hash-chained ledger folded into a
  derived state with one legal path from every fix back to a registration, a state guard / idempotency rule / refusal copy /
  test node for every command, write commands under the own-lock-then-probe protocol (the proof plus a barrier test with a
  positive control, not a race count) and lock-free reads, the pre-registration freeze (attach before launch, re-register
  refused once attached, a run-side check inside the engine), plan binding by plan_hash, id and link validation before any
  path is built, `verify` with a content-keyed git witness over the committed history, derived eligibility, and a test plan
  whose every node names the assertion that fails today, the red fixture, the real-wiring partner and a written mutant.
---

# W1-C: the campaign record and `bench campaign`

Evidence labels: **V** verified (opened or run this session), **I** inferred, **A** `assume:` (belief, what confirms it, what breaks if false). W0 means `docs/design/eval-seam-contracts.md` at **revision 4** (main `5fcd8a7c`); its rev-4 change table and sections 4, 6, 8 and 13 were re-read for this revision. **Revision 2** (this file) applies the five first-round reviews in `docs/design/reviews/eval-review-{pat,sec,ds,ta,sim}-w1c.md`; every finding has a row in section 16. Text that changed in revision 2 is marked "(rev 2, <reviewer> <n>)".

## 0. Findings against W0 and the ADRs (read first)

Each is evidence-backed. Rev 4 of W0 adopted W-1, W-2, W-3, W-6, W-7 and W-8; they stay as the record of why.

| # | finding | evidence | effect on this design |
| --- | --- | --- | --- |
| W-1 | W0 section 6 said `admission.decided` carries `admitted: bool`. `ledger.canonical` refuses a bool. | V `ledger.py:43` (`isinstance(value, bool)` raises `TypeError`) | `admitted` is an int, 0 or 1. **Adopted, W0 rev 4.** |
| W-2 | W0 said of the lock test "exactly one proceeds". Measured: **at most one** proceeds; **both refusing** also happens. Never both proceeding. | V spike S-C4: forced overlap, 30 runs: 14 + 6 one side proceeded, 10 both refused, 0 both proceeded. Natural race, 60 runs: 0 both proceeded. | The test asserts "never both". **Adopted, W0 rev 4.** The count is a characterisation, not the proof (section 6). |
| W-3 | A **pilot** plan carries the `campaign` block too (`prereg_hash: null`) and is attached by `ring_run.attached`. | W0 section 5 `campaign` block; ADR-0016 section 1 | **Adopted, W0 rev 4** (a null hash matches only `ring_run.attached`). |
| W-4 | `RunLock.acquire` on a path that is a folder raises a raw `PermissionError`. `is_held` does the same. | V spike S-C1 | `campaign.lock` is `lstat`-ed first; a folder or link is HB-CMP-003. |
| W-5 | `is_held` try-locks and then unlocks. During those microseconds the **other** side's `RunLock.acquire` can fail. | V spike S-C4: 2 of 60 natural runs showed `own-held` while the other proceeded | Harmless (a refusal). Section 6 states it. |
| W-6 | `git status --porcelain` lists the ledger as ` M` after any uncommitted append. | V spike S-C3 | **Adopted, W0 rev 4**, and tightened: the witness keys on content, never on status letters (section 7). |
| W-7 | The error registry rejects unknown codes (`ValueError`). | V spike S-C1 first run | X-D's first commit carries the `HB-CMP-*` rows (join dependency, section 13 order). |
| W-8 | `cli._exit_for` maps only `HB-LED*` and `HB-SEC*` to exit 5. | V `cli.py:48-49` | X-C adds `HB-CMP-003` to the integrity prefixes. Test C-38. |
| W-9 (rev 2) | The positive control for the lock proof. Two processes with a barrier between the two operations: the **swap** (check-then-lock) variant had both proceed in 20 of 20 runs; the correct order never did (17 one proceeded, 3 both refused). | V spike S-C5 (section 15) | The barrier test has teeth; the 90-race count is not cited as evidence. Under the barrier "both refused" is **not** forced (the first refuser releases before the second probes), so the assertion is "never both" (section 13, L-1). |

## 1. Responsibility, boundary, phasing

**One responsibility:** keep the record of one campaign, and decide, under one lock, whether each next write is allowed.

It owns `src/harness_bench/campaign.py` (grade class, W0 section 9), the `bench campaign` subcommands in `cli.py`, the `--campaign` option of `cmd_plan`, the `campaign_check=` line in `cmd_run` beside X-D's `identity_check=` (rev 4), `.gitignore` (three lines), the after-grading `verify` hook hunk in `grade/runner.py` (after X-F joins, W0 section 13), `ledger.py` (**no edit needed**) and `status.py` (`stop_reason`, `stop_diff` per W0 section 13; no campaign view). It does not own `oslock.py` (**X-B1**, rev 4), the identity builder (W1-D), the power and verdict maths and `gates.*` (W1-H, X-H1), readiness or the discrimination records' content (X-E), or the grader's lock half (X-F, HB-GRD-007).

**Phase and mocks.** E1, vertical slice "operator runs the E1 demo": real in this slice: ledger, lock protocol, verify, state fold, every command. Fakes at the seams, each with a real-wiring partner (section 13): `gates.pilot`, `gates.admission` and `power.analyse` (X-H1), `readiness.*` (X-E), `identity.manifest` (X-D). Until those join, tests use a stub callable passed to the command function. The CLI path itself is never faked (all command tests drive `cli.main(argv)`).

**Placement against R-89:** the demo is one campaign, `cc-opus`, k = 3, a 2-arm pilot ring (`off`, `candidate`), then a mini grid expected `inconclusive (underpowered)`. The pre-registration records `min_pairs` <= 3. This slice only records that number (and warns, section 5 `register`).

## 2. Data model (settled first)

**Bounded context:** Evaluation Campaign. **Ubiquitous terms:** campaign, baseline, effective identity, defect fix, pilot, admission, pre-registration, attach, freeze, eligible.

**Aggregate: Campaign.** Root: `campaign_id`. Invariant it protects (one): *the campaign's state is a forward-only walk over its rows; from the baseline on the engine identity changes only by an admitted fix; from the first attached grid run the registered pre-registration never changes.* Everything else is referenced by identity: runs by `run_id`, gradings by `grading_id`, plans by `plan_hash` (rev 4), identities, pre-registrations and power inputs by content hash, tasks by id. One aggregate per transaction: a command appends at most one row, except `admit`, which appends one row per task whose decision changed, under one lock hold (rev 2, PAT 5; the rows are one decision of one pilot).

**Entities and value objects.**
- Entity: the Campaign (the ledger). A **recorded defect fix** is a row of it, not a second aggregate.
- Value objects, content-addressed, immutable: *engine identity manifest*, *pre-registration*, *power-analysis inputs*.
- The **discrimination record** is X-E's aggregate (W0 section 6). This slice only verifies its folder (section 7).

**Durable representation.** Facts: `bench/campaigns/<id>/ledger.jsonl`, append-only, ADR-0006 rules (`ledger.canonical`, `stamp`, chain). Dimensions: `identity/<h>.json`, `prereg/<h>.json`, `power/<h>.json`, create-only, name = sha256 of bytes. No SQL, no cache.

**Grains (declared before columns).**

| table | one row / file is exactly one | identified by | recorded when |
| --- | --- | --- | --- |
| `ledger.jsonl` | state transition or recorded decision of one campaign | `(campaign_id, seq)` | a `bench campaign` command succeeds and changes something |
| `identity/<h>.json` | engine identity manifest, both sides | `identity_hash` | `baseline` (the one writer) |
| `prereg/<h>.json` | pre-registration statement | `prereg_hash` | `register --confirm` |
| `power/<h>.json` | set of power-analysis inputs | `input_hash` | `power` |

**Additivity.** No measure is stored. `seq`, `mono_ns` and `recorded_at` are order keys, not additive. Hashes are non-additive. Nothing is summed anywhere in this slice.

**History rule per attribute (Type-2 for all; no attribute is ever rewritten).**
- `registered.prereg_hash`: a later `registered` row supersedes (latest wins; the earlier row stays). Allowed only before any grid is attached.
- `power.recorded.input_hash` per role, `admission.decided.admitted` per task: latest wins, earlier rows stay. A decision counts as **current** only if its `seq` is greater than the last `baseline.recorded`, `defect_fix.admitted` (power final) or `pilot.passed` (admission) row (rev 2, PAT 6): see `register`.
- `defect_fix.admitted`: accumulates in order; the **effective identity** is the fold of the baseline manifest with the fixes in seq order.
- A Type-1 overwrite exists nowhere. Tests attempt one (F-6; V-3, V-4).

**Derive, don't store.** Derived, never written: `state`, the effective identity, the admitted-task set, the gate result, eligibility, power outputs, verdicts. A row with a `state` field is refused (F-6). **There is no stored or derived `pilot_current` (rev 2, PAT 1):** with the transition table below, the pilot is current exactly when the state is `piloted` or `registered`, because every fix demotes those states to `baselined`. `scope` and `role` are stored but are **written by the command from derived facts**, never accepted from the operator (section 5), so there is no second operator-supplied definition. `scope` is the one stored derivation; see section 3, kind 3.

**Persisted field -> writer -> compute reader (DM15).**

| field | writer | compute reader |
| --- | --- | --- |
| `campaign.created.question` | `create` | `campaign.read`; `register` (question equality); not in B2 |
| `baseline.recorded.{identity_hash, bench_commit}` | `baseline` | `effective_identity`; `verify` (file exists, name = hash); `status` |
| `defect_fix.admitted.{defect_class, commit, changes, scope}` | `fix` | `effective_identity`; `eligibility`; `verify` (replay) |
| `power.recorded.{role, input_hash}` | `power` | `register` (final equals prereg, and is current); X-H2 header |
| `ring_run.attached.{ring_hash, run_id, plan_hash}` | `pilot attach` | `pilot pass`; lock probe set; `run_side_check` (`ring_hash` equals `plan.ring.hash`; `plan_hash` equals the plan file's hash); `eligibility` |
| `pilot.passed.{run_id, grading_id, gate_input_hash}` | `pilot pass` | `admit`; `register` (re-verifies heads); state fold |
| `admission.decided.{task, admitted, reason}` | `admit` | `register` (coverage and currency); X-H2 |
| `registered.prereg_hash` | `register` | `attach`, `run_side_check`, `plan --campaign`, `eligibility` |
| `grid.attached.{run_id, plan_hash}` | `attach` | `run_side_check`; lock probe set; `eligibility`; `conclude` |
| `concluded`, `abandoned.reason` | `conclude`, `abandon` | state fold; `status` |
| every row: `kind`, `campaign_id`, `recorded_at`, `mono_ns`, `seq`, `prev_hash`, `hash` | `campaign._append` | `verify`, `fold` |

**Migration.** None: new folders, no existing data. The only shared-data change is `.gitignore` (three added lines): expand only, reversible by deleting them.

**Append-only enforcement.** The only write API is `_append(kind, **fields)`, which validates the closed field set and takes the next `seq` from the chain. There is no update or delete function. Tests attempt a forbidden update (edit a committed content file; rewrite a ledger prefix, in one commit and across commits) and `verify` refuses (V-3, V-4).

## 3. The kinds, justified against "derivable from the other rows?" (RV-SIM 11)

W0 rev 4 fixes the kind enum at 11 kinds and the fields below. None added, none merged. Each was tested for derivability.

| # | kind | derivable? | why it stays |
| --- | --- | --- | --- |
| 1 | `campaign.created` | no | it holds the id binding and the question; nothing else does |
| 2 | `baseline.recorded` | no | an operator act that fixes the identity; the transition `draft` to `baselined` |
| 3 | `defect_fix.admitted` | no | an operator act. Its `scope` field **is** derivable from the `changes` keys and `identity.CLASSES`, but is kept: `CLASSES` can change later (editing it is itself a fix), and a past fix must keep the meaning it had when admitted (Type-2 reasoning). The command computes it; no flag accepts it |
| 4 | `power.recorded` | no. Its `role` looks positional, but a fix after the pilot re-opens the "prior" slot, so position is ambiguous | `role` is written by the command from the state (`baselined` -> prior, `piloted` -> final) |
| 5 | `ring_run.attached` | membership is not derivable: `plan.campaign` in a plan is a claim; the ledger is the witness, and `runs/` is gitignored. Needed by `pilot pass`, the lock probe set and `run_side_check` | merging with `grid.attached` rejected: the grid has a **freeze effect** (HB-CMP-009) and need not come from a ring file |
| 6 | `pilot.passed` | not derivable from 5 | a **decision** with the hash of its inputs; the attach row exists even when the gate fails |
| 7 | `admission.decided` | the saturation test is derivable from pilot scores, but those live in gitignored `runs/` and are absent on a fresh clone; the row is the durable witness of why a task is not in the grid (UF-E1) | `admitted` is int 0/1 (W-1) |
| 8 | `registered` | no | transition and the pointer to the prereg file |
| 9 | `grid.attached` | no | see 5 |
| 10 | `concluded` | not derivable: a multi-night grid has no "last run" until the operator says so | transition |
| 11 | `abandoned` | no | transition and reason |

`ring_run.attached.tag` is **dropped** (rev 2, SIM 1 / OI-4; W0 rev 4): it was always `pilot`. `ring_hash` stays; its reader is `run_side_check` (it must equal `plan.ring.hash`) and `eligibility`. `plan_hash` is on both attach rows (W0 rev 4, SEC 7).

Closed field sets, enforced by `_append` and re-checked by `verify`:

```python
FIELDS = {  # exact field sets besides kind, campaign_id and the stamp; types: s=str, i=int, d=dict
    "campaign.created": {"question": "s"},
    "baseline.recorded": {"identity_hash": "s", "bench_commit": "s"},
    "defect_fix.admitted": {"defect_class": "s", "commit": "s", "changes": "d", "scope": "s"},
    "power.recorded": {"role": "s", "input_hash": "s"},
    "ring_run.attached": {"ring_hash": "s", "run_id": "s", "plan_hash": "s"},
    "pilot.passed": {"run_id": "s", "grading_id": "s", "gate_input_hash": "s"},
    "admission.decided": {"task": "s", "admitted": "i", "reason": "s"},
    "registered": {"prereg_hash": "s"},
    "grid.attached": {"run_id": "s", "plan_hash": "s"},
    "concluded": {},
    "abandoned": {"reason": "s"},
}
HOUSEKEEPING = {"ledger.tail_repaired"}   # ledger.TAIL_REPAIRED: written by SegmentWriter.reopen, no campaign_id (V ledger.py:182)
FREE_TEXT = {("campaign.created", "question"), ("abandoned", "reason"), ("admission.decided", "reason")}  # <= 500 chars, printable; never in B2
```

## 4. The state machine

State is `fold(rows)`. There is one table, in code, and `verify` replays through the same function.

| kind | legal in states | result state |
| --- | --- | --- |
| `campaign.created` | (first row) | `draft` |
| `baseline.recorded` | `draft` | `baselined` |
| `defect_fix.admitted` | `baselined`, `piloted`, `registered`, `measuring` | `piloted` -> `baselined`; **`registered` -> `baselined`** (rev 2, PAT 1); `baselined` and `measuring` unchanged |
| `power.recorded` role prior | `baselined`, `piloted` | unchanged |
| `power.recorded` role final | `piloted` | unchanged |
| `ring_run.attached` | `baselined`, `piloted` | unchanged |
| `pilot.passed` | `baselined`, `piloted` | `piloted` |
| `admission.decided` | `piloted` | unchanged |
| `registered` | `piloted`, `registered` | `registered` |
| `grid.attached` | `registered`, `measuring` | `measuring` |
| `concluded` | `measuring` | `concluded` |
| `abandoned` | `draft`, `baselined`, `piloted`, `registered`, `measuring` | `abandoned` |

**The one rule that closes the dead end (rev 2, PAT 1, blocking).** A fix in `registered` demotes to `baselined`, exactly like a fix in `piloted`. The pre-registration is not frozen until a grid is attached (HB-CMP-009), so a fix before any attach legitimately sends the campaign back through pilot, power, admit and register. The path exists and every step is legal: `baselined` -> (`pilot attach`, `pilot pass`) `piloted` -> (`power` final, `admit`) -> `register` -> `registered`. C-33 walks it end to end on the real CLI. A fix in `measuring` is legal and changes no state: a run-side fix makes every attached run ineligible (eligibility rule 5) and the campaign continues with new attaches under the new effective identity; a grade-side fix withholds passes until re-graded (rule 6, EV-16). The pilot is **not** re-run in `measuring`: the pilot gate is part of what the registration was made under, and the registration is frozen.

A row that is illegal in its state makes `verify` fail with HB-CMP-003 naming the row's `seq` and kind.

Adjacent state pairs the tests must tell apart (each has a mutant, section 13): `draft`/`baselined` (baseline), `baselined`/`piloted` (pilot pass and the fix demotion), `piloted`/`registered` (register), `registered`/`baselined` (the fix demotion, F-3), `registered`/`measuring` (attach).

## 5. The commands (the convergence condition)

Every command is `bench campaign <sub> <campaign_id> ...`. **Write commands** (`create`, `baseline`, `fix`, `power`, `pilot attach`, `pilot pass`, `admit`, `register --confirm`, `attach`, `conclude`, `abandon`) follow the **session protocol** (section 6). **Reads** (`status`, `verify`, the `register` preview) are lock-free (W0 rev 4; rev 2, SIM 2): they validate ids, `lstat` the path chain, read through `campaign.read`, run `verify()` (`status` prints its result; `verify` is its output), take no lock, probe nothing, sweep nothing and create nothing. "No-op" means exit 0, no row, the line `no change: <what already holds>`. Refusal copy is `<code>: <item> <cause>. <action>.` and names the item (EVX-4). Exit codes: 0 ok or no-op; 1 refusal (`_exit_for`); 5 for HB-CMP-003. Tests are ids from section 13.

**Argument validation (rev 2, SEC 1).** Before any path is built, in the argument parser's `type=` callbacks and again at `session` entry: `campaign_id` matches `^[a-z0-9][a-z0-9-]{0,39}$`; `run_id`, `--grading-id` and every task id match `status.RUN_ID` (`[A-Za-z0-9][A-Za-z0-9._-]{0,63}`, V `status.py:38`: no separator, never a leading dot, so no `..`); the resolved campaign folder's parent is `bench/campaigns`. A bad value is `HB-USR-002: <what> "X" is malformed (<pattern>). Use <example>.`, exit 1, nothing created. Only `create` may create the folder. **assume:** grading ids fit `status.RUN_ID`. Confirm: read `grade/runner.py` where the id is minted at X-F's join (C-3 asserts every minted id matches). If false: the pattern widens by one test, not the design.

| command | state guard (else HB-CMP-002) | idempotency (the one definition: same content again = no-op, different content in a state that forbids it = refusal) | refusals (code: copy) | tests |
| --- | --- | --- | --- | --- |
| `create <id> --question Q` | no ledger yet | ledger exists with the same question: no-op. Different question: HB-CMP-002 | `HB-USR-002: campaign id "X" is malformed (^[a-z0-9][a-z0-9-]{0,39}$). Choose another id.` / `HB-CMP-002: campaign "X" already exists with another question. A new question needs a new campaign id.` | C-1..C-3, N-1 |
| `baseline <id> --tasks T,...` (default: the ten property ids in the BOM) | `draft`. In any later state: no-op if the tree's manifest hash equals the **effective** identity hash (rev 2, PAT 8: after a recorded fix the tree equals the effective identity, so a repeat is a no-op), else HB-CMP-006 | as left | HB-CMP-006, one copy per unmet precondition, each ending with its action: `component "src/harness_bench/x.py" has an uncommitted change. Commit or discard it, then run baseline again.` / `task "S1" is not ready (BOM status stub). Finish authoring it.` / `catalog 0.7 is not frozen in bench/catalog-freeze.yaml. Run the catalog freeze.` / `spike E4 is not accepted (docs/notes/spike-e4-post-turn-prompt.md status is X). Complete the spike.` / `the tree differs from the effective identity at <diff>. Only a recorded fix changes the engine: bench campaign fix.` | C-4..C-9 |
| `fix <id> --class C --commit SHA --component KEY ...` | `baselined`, `piloted`, `registered`, `measuring` | a fix row with the same `defect_class` and `commit` whose `after` values equal the effective identity now: no-op | HB-CMP-007: `defect class "X" is malformed (^[A-Z]+-[A-Z0-9]+$).` (HB-USR-002) / `defect class "X" is not in docs/lessons/defect-classes.md. Record the class first.` / `commit "X" is not an ancestor of HEAD. Commit the fix.` / `component "K" changed and no fix names it. Add --component K.` / `component "K" is named but unchanged. Remove it.` / `component "K": before <h12> is not the effective identity's <h12>.` / `component "K" differs from commit <c12> (or has an uncommitted change). The recorded identity must be what the commit holds. Commit the change or check out the commit's file.` | C-10..C-15, C-47 (param), C-50 |
| `power <id> --inputs FILE` | `baselined`, `piloted` | the same `input_hash` with the same role already recorded: no-op. A crash between the file and the row: the retry appends the row only | `HB-PWR-001: power inputs invalid: <field>. Fix the field.` (raised by `power.analyse`; a float anywhere is invalid because the canonical form has none) | C-17..C-19 |
| `pilot attach <id> <run_id>` | `baselined`, `piloted` | same run with the same `plan_hash`: no-op | HB-CMP-002 `run "R" belongs to campaign "Y" (plan.campaign), not "X".` / `run "R" is a <tag> ring run, not a pilot. Plan it from the pilot ring.` / `run "R" has no confirmed plan under runs/.` / `run "R" has no ring hash.` | C-20, C-21 |
| `pilot pass <id> <run_id> [--grading-id G]` | `baselined`, `piloted` | same `(run_id, grading_id, gate_input_hash)` as the latest `pilot.passed`: no-op | `HB-CMP-008: pilot gate failed: <kind> <ident> ... Fix the cause, record the fix, rerun the pilot.` / `HB-CMP-008: reader "readiness.X" failed: <exception text>. The gate was not evaluated; no row was written. Fix the reader's input and rerun.` / `HB-CMP-002: run "R" is not attached as a pilot.` / `HB-CMP-002: grading pass "G" is not complete.` | C-23..C-25, C-48 |
| `admit <id>` (rev 2, PAT 5 / W0 OI-3: no task arguments, no operator override in E1) | `piloted` | for each task of the pilot run's plan whose latest decision **after the latest `pilot.passed`** equals `gates.admission`'s output: no row; others append | `HB-USR-002: task "T" has a not-recorded primary metric in an off-arm cell. Rerun the pilot (the gate named it primary-not-recorded).` (raised by `gates.admission`) | C-26, C-27 |
| `register <id> --prereg FILE` (preview) / `register <id> --prereg FILE --confirm <hash12>` | `piloted`, or `registered` while no grid is attached. The preview writes nothing and may run in any state from `baselined` on (it only prints) | same hash as the current `registered`: no-op | HB-CMP-008 and HB-CMP-009 copy below | C-28..C-35 |
| `attach <id> <run_id>` (grid) | `registered`, `measuring` | same run with the same `plan_hash`: no-op | HB-CMP-010 (one predicate, `check_plan`, below) | C-36, C-37, C-41, C-49 |
| `conclude <id>` | `measuring` | `concluded`: no-op | HB-CMP-002: `run "R" is still running. Wait or bench stop.` | C-42, C-43 |
| `abandon <id> --reason R` | `draft` .. `measuring` | `abandoned` with the same reason: no-op; another reason: HB-CMP-002 | `campaign "X" is already abandoned (<reason>).` / `campaign "X" is concluded; nothing to abandon.` / `run "R" is still running. Wait or bench stop.` | C-42, C-44 |
| `verify <id>` | any | read-only, lock-free | HB-CMP-003 (section 7) | V-series |
| `status <id> [--json]` | any | read-only, lock-free | HB-CMP-005 for an unknown id (nothing created) | B-series, L-10 |

**`register` refusal copy.** HB-CMP-008: `prereg question differs from the campaign's. Changing the question needs a new campaign.` / `prereg mde for "P" (x) is not the final analysis's (y). Re-run power with the MDE you accept.` / `the final power inputs predate the last fix (row <seq> < <seq>). Re-run bench campaign power.` / `task "T" has no admission decision after the latest pilot pass. Run bench campaign admit.` / `pilot did not cover (task T, harness H, arm A). Rerun the pilot.` / `pilot gate inputs changed since the pass (heads differ). Re-record the pilot.` / `arm "A" source is a local path. Use the remote URL or omit source.` / `--confirm <h12> does not match the statement's hash <h12>. Run the preview again.` HB-CMP-009: `pre-registration is frozen: run "R" is attached. Abandon this campaign or create a new one; the grid's verdicts would be exploratory.`

**Command details that carry a decision.**

- **baseline.** Builds `identity.manifest(root, tasks, builds)` (X-D) and writes `identity/<h>.json` through `create_once`, then the row. `identity_hash` is the hash of the **full** manifest. Preconditions are one function, `baseline_unmet(root, tasks) -> list[str]`, so a test reads the list. The dirty check is `git status --porcelain` limited to the manifest components' paths (`src/harness_bench`, `bench/{bom,metrics,prices,gateway}.yaml`, `bench/profiles`, `uv.lock`, `tasks/<id>`); untracked files under them count. "Every property task authored" is `status: ready` in `bench/bom.yaml`. "Catalog 0.7 frozen" is `bench/catalog-freeze.yaml` `versions['0.7'].catalog_hash == identity.catalog_hash(root)`. "Spike E4 cited as passed": the constant `SPIKE_E4 = "docs/notes/spike-e4-post-turn-prompt.md"` has frontmatter `status: accepted` (V: it does today); `simplify:` ceiling one spike, upgrade trigger a second spike precondition (rev 2, SIM 9). *Flag:* the machine sees only "accepted", not whether the spike passed.
- **fix.** The operator names the components (`--component`, at least one). The command computes `diff(effective, working-tree manifest)` and requires the named set to equal the differing set exactly (ADR-0017 section 4). `before` is read from the effective identity, `after` from the tree; `scope` from `identity.side`. **The tree must hold what the commit holds (rev 2, SEC 8):** for each named component, `git status --porcelain -- <path>` is clean and `git diff --quiet <commit> -- <path>` holds, else HB-CMP-007. The pure function `check_fix(effective, changes)` raises HB-CMP-007 on a before-hash that is not the effective one; the same function runs in `verify`'s replay. **The defect class (rev 2, SEC 10)** must match `^[A-Z]+-[A-Z0-9]+$` first, then is `re.escape`d into the heading regex `^#{2,4}\s+<ID>\s*[:—–-]` over `docs/lessons/defect-classes.md` (V: headings read `### MOD-A — ...` and `### CONC-A: ...`).
- **power.** The file is parsed, `power.analyse(inputs)` is called only as validation (HB-PWR-001 propagates), the canonical bytes are written with `create_once` to `power/<input_hash>.json`, then the row.
- **pilot attach.** Reads `runs/<run>/plan.json`; the row is `{ring_hash: plan.ring.hash, run_id, plan_hash: file_hash(plan.json)}`.
- **pilot pass.** Calls `gates.pilot(view, disagreements, unbiased, expected_na=expected_na)` (W0 rev 4 arity: `expected_na` keyword-only, default empty) with `readiness.hidden_test_disagreements(run_dir, grading_id)`, `readiness.unbiased_failures(run_dir, grading_id)` and `readiness.expected_na(root, tasks)`. **A failed reader (rev 2, PAT 5b):** the call site turns a reader exception into `None` and keeps its text; `pilot` raises HB-USR-002 naming the `None` list; `pilot pass` writes no row and prints the `reader ... failed` copy. A non-empty gate list refuses and prints each `GateItem` (kind, ident, detail). `gate_input_hash` = sha256 of `ledger.canonical({"grading_id": G, "scores_head": <head of scores/G.jsonl>, "events_head": <head of events/G.jsonl>})`, from `ledger.verify_segment(...).head_hash` (ADR-0016 section 7; V `views.py` layout). A missing or unsealed segment refuses.
- **admit (rev 2, PAT 5, W0 OI-3).** Reads the view of the latest `pilot.passed` row's grading, calls `gates.admission(view, tasks)` (X-H1) and writes its `(admitted, reason)` per task. The operator decides nothing in E1; an override would be a seam request.
- **register.** The prereg file is the EV-13 statement (W0 section 6). The **preview** (rev 2, PAT 5c, 5d; R-96 condition 1) prints the statement, `alpha_per_test` and `level_rule` for the registered method (X-H1's one table), the hash, and a **warning** (never a refusal; R-89) for every (property, harness, comparison) whose registered `min_pairs` is below the final power result's required `n`, then writes nothing. `--confirm <hash12>` (rev 2, DS 6) re-reads the file, recomputes the hash and refuses unless its first 12 hex digits equal the argument, so a file edited between preview and confirm cannot register a statement the operator never saw. Checks, in order, all inside the lock: schema and closed field set; `question` equals the created one; `arms` packs are `{commit (40 hex), revision, source?}` and `source`, if present, matches `^(https://|ssh://|git@)` (W1-A section 8); for each property the prereg `mde`, `alpha`, `power`, `correction`, `pairing_unit` equal the **final** power inputs, where "final" is the latest `role: final` row **and its `seq` exceeds the last `baseline.recorded` or `defect_fix.admitted` row** (rev 2, PAT 6); every pilot task has an `admission.decided` row with `seq` greater than the latest `pilot.passed`; the recorded `gate_input_hash` equals the heads now; coverage: every admitted task x every harness in the final inputs x every prereg arm was a cell of the pilot run's plan. "The grid the pre-registration names" is the final power inputs' `properties.<p>.tasks`, `harnesses`, `comparisons` (W0 rev 4, OI-2: ruled; no prereg field added). The pilot run's plan must be present locally; otherwise HB-CMP-008 says so.
- **attach and `check_plan` (one predicate for `attach` and the run-side check; rev 2, SEC 5, 6, 7).** Under the session lock, all of: `plan.campaign.campaign_id` is this id; the plan's `prereg_hash` equals the current `registered.prereg_hash` (W0 freeze step 1); `identity_hash` **recomputed from the block's `components`** equals `block.identity.hash` and equals `identity_hash(side(effective, "run"))`; **the working tree's** `side(manifest(root, tasks_of(effective), builds_of(plan)), "run")` equals the effective run side (SEC 5: a chain-stamped plan over a drifted tree is refused before the freeze); every arm of the plan has the pre-registered pack commit; the run has no `cell.launch_intent` in `runs/<id>/events`. The row's `plan_hash` is `file_hash(plan.json)`. All refusals are HB-CMP-010, each with its own copy: `plan.campaign.prereg_hash <h12> is not the registered <h12>.` / `plan.campaign.identity <h12> is not the effective run-side identity <h12>; differs at <diff>. Plan again.` / `plan identity components do not hash to plan.campaign.identity.hash. Plan again.` / `the working tree differs from the effective run side at <components>. Record a fix or restore the files.` / `plan arm "A" pack <commit12> is not the pre-registered <commit12>.` / `run "R" has already launched a cell. Plan a new run.` / `run "R" belongs to campaign "Y".` *assume (SEC 6):* `tasks_of(effective)` is the `tasks/<id>` keys of the effective components and `builds_of(plan)` is the builds the plan names; the comparison is per component over the plan's keys. Confirm: C-49 with a subset plan and a host with other builds. If false: a false refusal on a subset plan (safe) or an unseen drift in an unplanned task (the first launch still stops it, HB-IDN-001).
- **bench plan --campaign <id> (rev 3 check 1, plus SR-2; tree drift is HB-CMP-010, rev 2).** A lock-free read (advisory; the binding check is `attach`). It builds the campaign block as `{campaign_id, prereg_hash, identity: {hash: identity_hash(side(effective,"run")), components: side(effective,"run")["components"]}}` -- the **chain's effective run side, never a stamp of the working tree**. It first runs the same tree comparison as `attach` and refuses with HB-CMP-010 naming the differing components: `the working tree differs from the effective run side at grade/formal.py. Record a fix or restore the file.` A pilot-ring matrix gets `prereg_hash: null`; any other matrix needs state `registered` or `measuring` and takes the registered hash; a `pack-regression` ring with `--campaign` is refused. The `cmd_plan` wiring from W1-A section 3.9 is pasted verbatim (SR-2) and adds the `campaign=` argument to `build_plan`.
- **bench run: `run_side_check` (W0 rev 4; rev 2, DS 2).** `campaign.run_side_check(root, plan, run_id)` (X-C) runs **inside the engine**, after the run lock (`runs/<id>/.lock`) is held and before the first `cell.launch_intent`, through the keyword `campaign_check: Callable[[], None] | None` that X-D adds to `engine.py` and `cli.py` passes (`campaign_check=lambda: campaign.run_side_check(root, plan, run_id)`, one line beside `identity_check=`). It try-probes `campaign.lock` (held: HB-CMP-001 `campaign "X" is being written. Retry in a moment.`, nothing launched), reads the ledger lock-free, and refuses with HB-CMP-010 unless: for a pilot plan (`prereg_hash` null) a `ring_run.attached` row names this run and its `ring_hash` equals `plan.ring.hash`; for a grid plan a `grid.attached` row names it; the row's `plan_hash` equals the plan file's hash (a post-attach edit of `plan.json` is caught here, SEC 7); and `check_plan`'s registered-hash and identity clauses still hold. A concluded or abandoned campaign refuses with HB-CMP-002 naming the state. Copy: `run "R" is not attached to campaign "X" (or its plan no longer matches the ledger). Run bench campaign attach.` It holds no lock afterwards: the run lock it already holds is the other half of the pair `conclude`/`abandon` probe (section 6).
- **conclude and abandon (rev 2, DS 2).** Their session probe set adds the `.lock` of every attached run (code HB-CMP-002, `run "R" is still running. Wait or bench stop.`) to the `grade.lock` probes, in the same `acquire_then_probe` call.

## 6. Locks and sessions (D6; ADR-0018 11(a))

**Session protocol** (write commands only; rev 2, SIM 2), one context manager, `campaign.session(root, campaign_id, *, others_extra=(), wait_s=0.0)`:

0. **Validate** the ids (section 5) and `lstat` the path chain **without creating anything** (rev 2, SEC 1, 2): the campaign folder, `ledger.jsonl`, `identity/`, `prereg/`, `power/`, `campaign.lock`, and each content file must be a plain regular file or real folder, not a link or reparse point (`stat.S_ISLNK`, and `st_file_attributes & FILE_ATTRIBUTE_REPARSE_POINT` on Windows); else HB-CMP-003 naming it (W-4). Absent is fine. Every command except `create` then requires `ledger.jsonl` to exist: absent is HB-CMP-005 and **nothing was created** (the lock's `mkdir` has not run).
1. `oslock.acquire_then_probe(campaign.lock, "HB-CMP-001", others)` where `others` is, in order: for every run in the campaign's attach rows plus the command's run argument, `(runs/<run>/grade.lock, "HB-CMP-004")`; for `conclude` and `abandon` also `(runs/<run>/.lock, "HB-CMP-002")`. Held lock: wait up to `wait_s` (fixed 0.2 s steps; `simplify:` ceiling: callers wait seconds; upgrade trigger: a caller that waits minutes), then refuse. HB-CMP-004 copy: `run "R" is being graded. A campaign write must not be open during a grading pass. Wait for the pass to finish.`
2. **Read the ledger** (lock-then-read). `create` passes `create=True`.
3. `verify` (section 7). Failure: release, HB-CMP-003, no command ran.
4. Sweep leaked temps (section 7).
5. Run the command; append; release in `finally`.

**One function, owned by X-B1 (rev 2; W0 rev 4, SR-C1).** `oslock.acquire_then_probe(own, own_code, others: Sequence[tuple[Path, str]], *, between=None) -> RunLock` is written by X-B1 in `oslock.py`; this slice calls it and does not edit `oslock.py`. It acquires `own`, probes each of `others` with `is_held`, and on the first held one releases `own` and raises that entry's code. `between` is keyword-only and runs **after the first operation and before the second** (so the swap mutant still has the barrier between its own two operations). The grading side (X-F, `grade/runner.py`) calls it with `[(campaign.lock, "HB-GRD-007")]` for a plan with a `campaign` block. Pattern: **Mutual Exclusion by symmetric try-lock handshake**, one definition for both sides (DM7).

**Why safe (reasoned, then measured with a positive control; rev 2, TA 5, DS 3).** A proceeds only if its probe saw G's lock free; G holds its own lock before it probes, so if A's probe saw it free G had not yet taken it; G then takes its own and probes A's lock, which A has held since before its probe: G refuses. So both cannot proceed. Both can refuse; one can proceed after the other refused and released. Evidence, in order of weight: **(1) the proof; (2) the barrier test L-1 with its positive control:** S-C5 ran the two orders with a barrier between the two operations of each side: the correct order never had both proceed (20 runs: 17 one proceeded, 3 both refused), the swapped order had both proceed in 20 of 20; so a barrier race can fail, and L-1 fails on M-L1. **(3)** the S-C4 counts (0 of 90 both proceeded) are a characterisation of this host and are **not** evidence of the safety claim. Windows only (`msvcrt`); POSIX (`flock`) is inferred and runs in the POSIX job. The `is_held` probe takes the other lock for microseconds; a concurrent `acquire` of it can fail with its own held-code (W-5), a refusal either way. Safety does not depend on liveness.

*assume (rev 2, DS 7):* both sides of every pair run in one OS lock domain on a local disk (Windows `msvcrt` or POSIX `flock`, not mixed, not a synced or network folder). Confirm: the operator doc says so (W0 rev 4). If false: the two sides do not exclude each other, and a campaign write can overlap a grading pass.

**The run side of the pair (rev 2, DS 2).** The run takes its own lock (`runs/<id>/.lock`), then `run_side_check` try-probes `campaign.lock` and re-reads; `conclude` and `abandon` take `campaign.lock` and probe the run lock. This is the same handshake, so a run and a conclusion can never both proceed (L-9).

**What the lock does not cover.** `status`, stand-alone `verify`, the `register` preview and `plan --campaign` are lock-free reads: `campaign.read(root, id)` is library code, verifies the chain, and ignores a torn last line (ADR-0006). X-H2 uses it. `status` therefore works while a campaign run is being graded (L-10). `plan --campaign` is advisory because `attach` re-checks everything under the lock.

**The freeze order (DS-1; W0 section 6), and the race it closes.**
1. `attach` appends `grid.attached` under `campaign.lock` before the first launch, only if `check_plan` holds.
2. `register` is refused with HB-CMP-009 once any `grid.attached` exists.
3. The run-side check re-reads the ledger inside the engine (above).
Interleaving A: register(Y) first, attach(plan X): attach refuses (hash mismatch). Interleaving B: attach(plan X) first, register(Y): register refuses HB-CMP-009. Either way the registered hash equals the hash any attached run planned under. Tests I-1, I-2 (threads with `wait_s=30` and event hand-offs, rev 2, DS 5; real cross-process lock semantics in L-2, L-3, L-9).

**After-grading hook (X-F seam, SR-C2 e; hunk X-C's after X-F joins).** ADR-0018 11(b) requires `verify` after every grading pass. `campaign.verify_for_plan(root, plan)` is **lock-free** (W0 rev 4; rev 2, DS 4): it runs `verify()` with no lock and no probe, so a sibling attached run being graded in parallel can neither fail it nor be failed by it, and there is no HB-CMP-001/004 to map. The hook runs after the pass ends (it verifies the records the pass could have touched). Output: `campaign verify: ok (<n> rows)`, or HB-CMP-003 (exit 5) with the first finding. The one non-verified outcome is HB-CMP-005 (no such campaign folder): `campaign verify: not run (HB-CMP-005)`, and the grading result stands. The claim is "not verified", never "verified".

## 7. `verify`, the sweep and `.gitignore`

`verify(root, id)` returns a list of `Finding(code, path, detail)` and runs these checks in order. Any finding makes the command exit 5 with HB-CMP-003 naming the first and counting the rest. It reads the ledger lock-free; a torn tail is not a finding (ADR-0006).

0. **Plain paths (rev 2, SEC 2).** The campaign folder, `identity/`, `prereg/`, `power/`, `ledger.jsonl`, every content file, `bench/discrimination/` and each `bench/discrimination/<task>/` named by the effective identity's `tasks/*` keys are `lstat`-ed: a link, junction or other reparse point is a finding naming it. (A race between the `lstat` and the later open remains: no `O_NOFOLLOW` in `oslock`/`SegmentWriter`; accepted residual, FM-17.)
1. **Chain.** `ledger.verify_segment`: `error` set means a break.
2. **Row shape.** Every row's `kind` is in `FIELDS` or `HOUSEKEEPING`; its field set equals `FIELDS[kind]` plus the stamp and chain fields; types match; `campaign_id` equals the folder name (the chain's genesis is bound to the segment id `ledger`, the same for every campaign, V `ledger.py:65`).
3. **Replay.** `fold` raises on an illegal row (section 4); each fix's `before` equals the effective value at that point.
4. **Content files.** Every file in `identity/`, `prereg/`, `power/` that is not a temp name (`atomic.is_temp_name`) has name = sha256 of its bytes and valid JSON of the right `schema`; every hash named by a row exists.
5. **Git witness (ADR-0018 11(b); W0 rev 4; rev 2, SEC 3, 4, PAT 2, DS 1).** The rule keys on **content, never on status letters**; `git status` letters are not read. Not a work tree (exit 128): refuse HB-CMP-003 `bench/campaigns is not in a git work tree; the witness is absent`, no bypass. With no commit yet (`git rev-parse HEAD` exit 128): everything is new and allowed. Otherwise, over every path under `bench/campaigns/` and `bench/discrimination/` (through `gitsafe.git`):
   - **a.** `ledger.jsonl`, if in `HEAD`: `HEAD`'s blob **cut at its last newline** must be a byte prefix of the working file. The cut keeps a torn tail committed before a repair from failing every later command (DS 1; the next write's `reopen` truncates the working file back to its last good line).
   - **b.** **History walk (SEC 4, fixed, not a residual).** For the ledger's commits in first-parent order (`git log --first-parent --reverse --format=%H -- <ledger>`), each blob cut at its last newline must be a byte prefix of the next commit's blob. A commit that rewrites a prefix is a finding naming the commit. Cost: one `git show` per commit; `simplify:` ceiling 500 ledger commits, trigger `verify` over 2 s. *assume:* a single operator on one branch line (ADR-0012); a merge of two branches' ledgers fails closed (a finding, never silent).
   - **c.** Any other path in `HEAD` (a content file, a discrimination record): working bytes equal `HEAD`'s; **a path in `HEAD` and absent from the working tree is a finding** (a deleted record).
   - **d.** A path not in `HEAD`: a content file's name equals its hash (step 4); a ledger is new content and passes a. as "not in HEAD".
   - **e.** `git ls-files -v -- <folders>`: any entry with flag `h` (assume-unchanged) or `S` (skip-worktree) is a finding naming the path.
   - **f.** `git status --ignored --porcelain -uall -- <folders>`: any `!!` (ignored) path that is not a temp name (`atomic.is_temp_name`, file or folder) or `campaign.lock` is a finding. This catches a `.gitignore` line, a `.git/info/exclude` line or a global ignore that hides the ledger or a record.
   - **g.** The root `.gitignore` contains each of these three lines **exactly**, as whole lines: `bench/campaigns/**/*.tmp-*`, `bench/discrimination/**/*.tmp-*`, `bench/campaigns/*/campaign.lock`; a missing one is a finding (it would turn the temp warnings in step 6 into untracked noise or the lock into an untracked file).
6. **Temps.** Every name matching `atomic.is_temp_name` in the campaign folders and `bench/discrimination/<task>/` is reported as a **warning line with its name** (a temp folder too); exit stays 0.

**The sweep** follows `verify` (write commands only; `status` and `verify` never sweep). It visits the campaign sub-folders and `bench/discrimination/<task>/` for the tasks of the **effective identity's `tasks/*` keys** (rev 2, SEC 9; each task directory is `lstat`-ed and a link is skipped with a named warning, S-4). For each base name that has temps, if **every** temp of that base has `mtime` older than `TEMP_MIN_AGE_S = 3600`, call `atomic.sweep_temps(dir / base, lock)` under the lock (W0 section 4, rev 4: the lock argument). A younger temp may belong to a live `bench discriminate` writer, which does not take `campaign.lock`; it is left and reported. `sweep_temps` is the one place that guards reparse points; this module never calls `rmtree`.

**`.gitignore` (S-B2):** the three lines in 5g. `.gitattributes` already says `* text=auto eol=lf` (V), so a ledger stays LF on every checkout; G-2 proves a fresh clone with `core.autocrlf=true` still verifies (slow ring).

## 8. Eligibility and the effective identity (compute readers)

```python
def effective_identity(root: Path, state: CampaignState, upto_seq: int | None = None) -> dict   # baseline manifest with fixes (seq <= upto) applied
def eligibility(state: CampaignState, effective: dict, run: RunFacts, first_grid: RunFacts | None) -> Eligibility   # pure
@dataclass(frozen=True)
class RunFacts: run_id; plan_present; plan_file_hash; plan_campaign_id; plan_prereg_hash; plan_run_identity_hash; plan_ring_hash; grade_identity_hash
@dataclass(frozen=True)
class Eligibility: eligible: bool; reasons: tuple[str, ...]      # EV-20 copy, one per failing rule, fixed order
def run_facts(run_dir: Path, grading_id: str) -> RunFacts        # the only impure loader (reads plan.json and the grading.started row)
```

A run is eligible iff all hold, and each failure adds its reason (rev 2: the old rule 7, "pilot current", is removed with `pilot_current`; rule 7 is the ring rule of W0 rev 4, OI-1):
0. **`plan_present`** (W0 rev 4): a grid run whose `plan.json` is absent locally is ineligible with the single reason `not recorded`, never assumed eligible; rules 1-7 need the plan.
1. its plan names this campaign;
2. a grid run's `plan_prereg_hash` equals the registered one;
3. the run is attached (`ring_run.attached` or `grid.attached`) **and** the row's `plan_hash` equals `plan_file_hash`;
4. `plan_run_identity_hash` equals `identity_hash(side(effective_identity(upto = attach seq), "run"))` (recomputed so a hand-edited ledger cannot hide it);
5. **no fix of scope `run` or `both` has `seq` greater than the run's attach `seq`** (attach precedes the first launch by the freeze order, so this is "no run-side fix after the first launch" without comparing clocks);
6. `grade_identity_hash` equals `identity_hash(side(effective_identity(now), "grade"))` (a pass under an older grade side is withheld until re-graded, EV-16); the reason names `diff`;
7. **ring (W0 rev 4, OI-1):** `plan_ring_hash` equals the `plan_ring_hash` of the first attached grid run (`null` when that plan has no ring); a later grid run with a different value is ineligible, named.

*Narrowing noted:* ADR-0017 says the run-side manifest equals the effective one "at some point of the chain". Because attach demands equality with the **current** effective identity, "some point" is always the attach point; rule 4 states that.

## 9. Change surfaces (E7)

| layer | surface | owner |
| --- | --- | --- |
| store | `bench/campaigns/<id>/{ledger.jsonl, identity/, prereg/, power/, campaign.lock}`; `.gitignore` | X-C |
| model | `campaign.py`: `FIELDS`, `fold`, `CampaignState`, `effective_identity`, `eligibility`, `check_plan`, `check_fix`, `baseline_unmet`, `run_side_check`, `verify_for_plan`, `validate_id` | X-C |
| service | `session`, the command functions; `cmd_plan --campaign`; the `campaign_check=` line in `cmd_run`; the after-grading hook hunk in `grade/runner.py` | X-C |
| external to this slice | `oslock.acquire_then_probe` | X-B1 |
| external to this slice | `engine.py` `campaign_check=` keyword | X-D |
| projection / wire | `bench campaign status --json` = `bench-campaign-status/1` (below). `bench-status/1` is **unchanged**: it is strict (`status._exact`), and a campaign view is not a run view (`architecture-evaluation-campaign.md:254`, V). The `stop_reason`, `stop_diff` fields of W0 section 13 are X-C's, tracked in their own design | X-C |
| client type | `parse_status(document) -> CampaignStatus` validates strictly like `status.parse`; the `question` and `reason` are not in the document (B2) | X-C |
| UI | CLI text of each command; the report header reads `campaign.read` (X-H2) | X-C, X-H2 |
| compute reader | `eligibility`, `effective_identity` (X-H2, W1-D's diff text), `gate_input_hash` | X-C |

`bench-campaign-status/1` document: `{"schema", "campaign_id", "state", "baseline_identity_hash", "effective_run_hash", "effective_grade_hash", "fixes": [{"defect_class","commit","scope"}], "power": {"prior","final"}, "prereg_hash", "pilot_runs": [...], "grid_runs": [...], "excluded_tasks": [...], "next": "<fixed token>"}` (rev 2: `pilot_current` removed with the concept); `next` is a fixed token from a closed set (`baseline`, `pilot`, `power`, `register`, `attach`, `wait`, `conclude`, `none`).

## 10. Patterns (Ladder climbed)

| decision | rung | pattern | rejected |
| --- | --- | --- | --- |
| ledger | reuse `ledger.SegmentWriter` unchanged | append-only hash-chained log (ADR-0006) | a campaign-specific log format |
| state | derive | **Event sourcing, fold over a closed transition table** | a stored `state` column (a second definition) |
| content files | reuse `atomic.create_once` | **Content-addressed store** | `open("x")` |
| mutual exclusion | reuse `oslock` (X-B1's `acquire_then_probe`) | **Mutual Exclusion, symmetric try-lock handshake** (one function, a set of others) | check-then-lock (races, M-L1) |
| command shape | one context manager | **Execute-Around** (`session`; rev 2, PAT 8: it is a context manager, not Template Method) | per-command copies of lock/verify/sweep |
| plan check | one function | **Specification** (`check_plan`) shared by `attach`, `run_side_check`, `plan --campaign` | two predicates drifting |
| eligibility | pure function over facts | **Policy as a pure function** | reading `runs/` inside the rule |
| `verify` git rule | stdlib `git` via `gitsafe` | **Witness check** keyed on content (prefix for the append-only ledger, over each commit pair; equality for immutable files) | status letters (W-6, SEC 3) |

Simplifier pass: no `Campaign` class with methods (a frozen `CampaignState` and functions), no registry of commands (a dict in `cli.COMMANDS`), no cache of the fold (tens of rows; `simplify:` ceiling 10,000 rows, trigger: `fold` over 5 ms median), no per-command lock variants, no `ledger.py` change, no `status.py` campaign view, no `pilot_current`, no `--campaign` alias for `bench verify`, no generic sweeper (W0 section 4 supplies it). A new dependency: none.

## 11. Failure modes, adversarial analysis, privacy

**Failure modes** (design choices -> how it fails -> disposition -> test):

| # | category | mode | disposition | test |
| --- | --- | --- | --- | --- |
| FM-1 | concurrency | check-then-lock window on a command | prevent: lock first, then read (`session`) | I-1, I-2, M-I1, M-I2 |
| FM-2 | concurrency | `campaign.lock` and `grade.lock` both held by two writers | prevent: own-then-probe; never both; both-refused leaves files unchanged | L-1, L-2 |
| FM-3 | concurrency | the freeze window between register and first launch | prevent: attach freezes (HB-CMP-009) and the run-side check re-reads inside the engine | I-1, I-2, P-3 |
| FM-4 | state | crash between `create_once` and the row append | recover: the retry finds the file, appends the row (idempotent) | C-18 |
| FM-5 | state | crash mid-append (torn tail), committed or not | recover: `reopen` truncates and records `ledger.tail_repaired`; readers ignore the tail; the witness cuts HEAD at its last newline | F-9, V-4b |
| FM-6 | state | a plan stamped from a drifted tree | prevent at plan time, at attach (HB-CMP-010) and at the first launch (HB-IDN-001) | P-1, P-2, P-4, C-49 |
| FM-7 | state | run-side fix after attach, before launch | detect: the engine stops at the first launch (drift vs the plan's identity); eligibility rule 5 | P-5, E-4 |
| FM-8 | input | float, bool or non-string key in an inbound JSON | prevent: canonical form refuses; HB-PWR-001 / HB-CMP-008 | C-19, F-7 |
| FM-9 | input | oversized or control-character free text; a malformed id | prevent: <= 500 chars, printable; id patterns before any path | C-3, N-1 |
| FM-10 | resource | leaked temps accumulate | recover: sweep under the lock, age-gated; warn by name | S-1, S-2 |
| FM-11 | resource | live writer's temp swept | prevent: age gate (`TEMP_MIN_AGE_S`) | S-2 |
| FM-12 | dependency | git absent or not a work tree | prevent: refuse HB-CMP-003, no bypass | V-8 |
| FM-13 | dependency | a seam module (gates, power, readiness) not joined, or a reader fails | the commands that call it refuse with a named error and write no row; tests use the stub parameter | C-23, C-48 |
| FM-14 | time | clock skew | not used: ordering is by `seq` | E-5 |
| FM-15 | state | the operator edits the ledger and recomputes the chain | detect: the content witness over every commit pair (5a, 5b); an **uncommitted** full rewrite is the accepted residual (single operator, ADR-0012) | V-4, V-4c |
| FM-16 | concurrency | spurious refusal by a probe (W-5) | accept: a refusal is safe; retry | L-1 |
| FM-17 | state | a link swapped in between `lstat` and open | accept as residual (no `O_NOFOLLOW`); a link present at `lstat` time is refused | L-8 |
| FM-18 | concurrency | a run starts while `conclude` runs | prevent: the run side takes its lock then probes `campaign.lock`; `conclude` takes `campaign.lock` then probes the run lock | L-9 |

**STRIDE-lite.** Boundaries: (1) operator CLI -> ledger; (2) hostile agent code during a grading pass -> committed records (ADR-0018 11); (3) plan files in gitignored `runs/` -> the campaign.

| threat | boundary | disposition | negative test |
| --- | --- | --- | --- |
| S: a plan claims another campaign's id | 3 | mitigate: `check_plan` compares `plan.campaign.campaign_id` and the attach row | C-36 |
| T: edit a committed content file | 2 | mitigate: name = hash, content equality with HEAD; detected not prevented (ADR-0016 8) | V-2, V-3 |
| T: rewrite the committed ledger prefix, in one commit or across commits | 2 | mitigate: HEAD-prefix and commit-pair prefix rules | V-4, V-4c |
| T: hide a modified file from `git status` (`assume-unchanged`, skip-worktree, an ignore line) | 2 | mitigate: `ls-files -v` flags, `--ignored` scan, exact `.gitignore` lines | V-11, V-12 |
| T: plant content in a temp folder, a `campaign.lock` folder, or a linked ledger or sub-folder | 2 | mitigate: warn by name; `lstat` the whole chain | V-6, L-5, L-8 |
| T: edit `plan.json` after attach (drop tasks or arms) | 3 | mitigate: `plan_hash` on both attach rows, re-checked in the engine | P-6 |
| T: forge the block's `components` with the right `hash` | 3 | mitigate: `identity_hash` recomputed from `components` | C-36 |
| T: swap a temp between write and link (`create_once`) | 2 | transfer to W1-B's inode check; the content-addressed hash check is the second line | V-2 |
| T: `status ../../x` writes outside the folder | 1 | mitigate: id patterns; no creation outside `create`; lock-free reads create nothing | N-1 |
| R: who changed what | 1 | mitigate: every row is chained, stamped, committed; refusals are not rows (architecture line 254) and are logged | T-1 |
| I: path, user name or env in a committed file | 1 | mitigate: manifests carry no path (W1-D leak test); prereg `source` must not be a path; free text is bounded | C-32 |
| D: a held lock blocks the grader for long | 1 | accept: commands are short; the grader's hook is lock-free | L-3 |
| E: agent code writes a campaign record while a pass runs | 2 | mitigate: ADR-0018 11(a) both-directions refusal; residual accepted (ADR-0012/0013) | L-2, X-INT-2 |

**Privacy (LINDDUN-lite).** No personal data by design: the files hold hashes, ids, a campaign question and decision reasons that the operator writes. Residual: free text could hold a name; it is length-bounded, printable-only and absent from the B2 document. Retention: git history. Rights path: the operator edits their own repo. Linkability of `bench_commit` to a person: accepted (git history already links).

## 12. Telemetry (instrumentation over inference)

Questions an operator asks, each with an emitting source (no flag, on the normal path): how long did a command take, how much of it was waiting for the lock, verifying, sweeping; how often is a command refused and by which code; how many temps were swept; how big is the ledger.

One structured log record per command on logger `harness_bench.campaign` (the project's JSON-lines convention, no cell text):
`{"event": "campaign.command", "command", "campaign_id", "state_before", "state_after", "outcome": "ok|noop|refused", "code": "HB-CMP-...|null", "rows": n, "lock_wait_ms", "verify_ms", "sweep_ms", "swept": n, "duration_ms"}`. A phase that did not run is **absent**, never `0` (IO1): a lock-free read has no `lock_wait_ms` and no `sweep_ms`. `bench campaign status` prints the last line `rows <n>, verified in <ms>`. Load-bearing telemetry has a test: T-1 (record fields), T-2 (absent, never zero).

Error codes used: `HB-CMP-001..010` (none retired, none merged: each has a distinct operator action; **HB-CMP-008** means "a decision's inputs do not hold" for both the pilot gate and the register preconditions, one meaning per command family, rev 2, PAT 7; **HB-CMP-010** covers attach refusal, tree drift and the run-side check), `HB-USR-002`, `HB-PWR-001`, `HB-LED-007` (via `create_once`). `errors.py` rows are X-D's first commit (W-7). No HTTP surface.

## 13. Test plan by node id

**Red-first protocol and landing order (rev 2, TA 1).** Tests span four tracks. The commits land in this order, and a test is "red by value" only after the commits it names:
1. **X-D first commit:** `errors.py` rows (`HB-CMP-001..010`, `HB-GRD-007`, `HB-PWR-001`). Until it lands, any test that raises a new code fails with the registry `ValueError` (W-7), which is the wrong reason; C-38 (exit code 5) is red by value only after it.
2. **X-B1:** `atomic.py` skeleton (`create_once` returns False, `sweep_temps` and `is_temp_name` inert) and the `oslock.acquire_then_probe` skeleton (acquires `own`, does not probe).
3. **X-D:** `identity.py` skeleton returning out-of-domain values (`manifest -> {"components": {}}`, `side` the same, `CLASSES = {}`).
4. **X-C:** `campaign.py` skeleton with inert bodies: `read` returns `state=draft` with no rows, `verify` returns `[]`, `session` yields without locking, command functions return 0 and write nothing, `run_side_check` and `verify_for_plan` return None, `parse_status` and `to_json` exist.

Tests marked **(1)**, **(2)**, **(3)** need that commit first and are provisional until it lands: C-4, C-10, C-15, C-29, C-37, C-49, P-1, P-4, P-5 need (3); C-18, C-29, S-1, S-2, V-6 need (2); C-38 needs (1). Every other test is red by value on the skeleton alone. **Expected values are never computed with the function under test:** C-4 and C-10 compute the expected `identity_hash` with `hashlib.sha256(path.read_bytes())` over the written file and compare it with the row; they do not call `identity_hash(manifest)`. None fails with an `ImportError`, `AttributeError` or `NameError`.

Files: `tests/test_campaign.py` (F, C, E, N), `tests/test_campaign_locks.py` (L, I), `tests/test_campaign_verify.py` (V, S, G), `tests/test_cli_campaign.py` (P, B, T, Q). Temp repos are real `git init` repos in `tmp_path`; the CLI is driven through a helper `cli_rc(argv)` that calls `cli.main(argv)` and converts `SystemExit` into its code (rev 2, TA 8), so a missing option fails by value, not by error. Mutants live in `tests/mutations/campaign.json` in the repo's format (`name`, `file`, `find`, `replace`, `tests`); **every mutant has its written edit in the mutant ledger below** (rev 2, TA 2).

Column key: **Assert / red today** = the assertion and why it fails on the skeleton or today's code. **Red fixture** = the input that must be refused (for a guard). **Real wiring** = the test that exercises the real collaborator beside a fake. **Mutant** = a ledger id.

Retired ids (not reused): F-4, F-5, F-10, F-11, C-16, C-22, C-34, C-39, C-40, V-7, V-9, S-3 (section 16, SIM 3-6, TA 8).

### F: fold, rows, state

| id | assert / red today | red fixture | real wiring | mutant |
| --- | --- | --- | --- | --- |
| F-1 `test_fold_walks_the_transition_table` | after each legal prefix, `read(...).state == TABLE[...]` (skeleton returns `draft`) | n/a | rows written by real commands via `cli.main` | M-F1 |
| F-2 `test_illegal_row_for_its_state_is_hb_cmp_003` | `verify` returns a finding naming `seq` and kind (skeleton `[]`) | 9 cases: `baseline.recorded` first; `grid.attached` in `piloted`; `registered` in `baselined`; any kind after `concluded`; `admission.decided` in `baselined`; `power final` in `baselined`; second `campaign.created`; `defect_fix` in `draft`; `pilot.passed` in `registered` | ledgers hand-built with `ledger.SegmentWriter` | M-F2 |
| F-3 `test_fix_demotes_piloted_and_registered_to_baselined` (rev 2, PAT 1) | parametrized over `piloted`, `registered`: after the fix `state == baselined` (skeleton `draft`) | n/a | rows from the real CLI | M-F3a (piloted), M-F3b (registered) |
| F-6 `test_row_field_sets_are_closed_and_state_is_not_stored` | `verify` finds a row with a `state` field, a missing field, an extra field (including a stale `tag` on `ring_run.attached`), a wrong type (skeleton `[]`) | the five rows | `_append` refuses the same before writing | M-F6 |
| F-7 `test_admission_row_stores_int_and_bool_is_refused` | stored line contains `"admitted":1`; `_append(admitted=True)` raises HB-CMP-003 (W-1) | a bool row | real `ledger.canonical` refuses a bool beneath | M-F7 |
| F-8 `test_ledger_copied_between_campaigns_fails_verify` | finding `campaign_id` differs from folder | ledger of A in folder B | n/a | M-F8 |
| F-9 `test_tail_repaired_row_is_housekeeping_not_a_transition` | after a torn tail and `reopen`, state is unchanged, the earlier **2** rows are still read, and verify passes (count assertion, rev 2, TA 8: the skeleton reads none) | the repaired ledger | real `SegmentWriter.reopen` | M-F9 |
| F-12 `test_fix_in_measuring_keeps_measuring_and_attached_runs_follow_rules_5_and_6` (rev 2, PAT 1) | state `measuring` after a fix; a new attach under the new effective identity succeeds | a fix after `grid.attached` | real CLI | M-F12 |

### C: commands (state guard x idempotency x refusal copy)

| id | assert / red today | red fixture | real wiring | mutant |
| --- | --- | --- | --- | --- |
| C-1 `test_create_writes_one_created_row` | one `campaign.created` row (skeleton: zero) | n/a | real `cli.main` | M-C1 |
| C-2 `test_create_with_another_question_is_refused` | exit 1, `HB-CMP-002`, ledger bytes unchanged | second question | n/a | M-C2 |
| C-3 `test_malformed_id_and_free_text_are_refused` | `HB-USR-002` for `-a`, `A`, 41 chars; question of 501 chars or with a control char; every id minted by the grader fits `status.RUN_ID` | those inputs | n/a | M-C3 |
| C-4 `test_baseline_records_identity_file_and_row` (3) | `identity/<h>.json` exists, name = `hashlib.sha256` of its bytes, row `identity_hash` equals that name, `bench_commit == HEAD` | n/a | **real `identity.manifest` and a real git repo** | M-C4 |
| C-5 `test_baseline_refuses_a_dirty_component` | `HB-CMP-006` naming the file and the action | modified tracked `src/` file; untracked new `src/` file | real `git status` | M-C5 |
| C-6 `test_baseline_refuses_a_task_not_ready` | `HB-CMP-006` naming `S1` | BOM status `stub` on the last task | n/a | M-C6 |
| C-7 `test_baseline_refuses_unfrozen_catalog` | `HB-CMP-006` | freeze file without `0.7`; with `0.7` but a different hash | real `identity.catalog_hash` | M-C7 |
| C-8 `test_baseline_refuses_unaccepted_spike` | `HB-CMP-006` | note with `status: draft` | n/a | M-C8 |
| C-9 `test_baseline_after_a_tree_change_is_refused_and_after_a_fix_is_a_noop` (rev 2, PAT 8) | `HB-CMP-006` naming the diff after an unrecorded edit; after `fix` records it, a repeat `baseline` is a no-op | edit after baseline | n/a | M-C9 |
| C-10 `test_fix_roundtrip_effective_identity_equals_tree` (3) | after one fix, `effective_identity == identity.manifest(tree)` | n/a | **real manifest**, two commits | M-C10 |
| C-11 `test_fix_refuses_an_unknown_or_malformed_defect_class` | `HB-CMP-007` for `ZZZ-Z`; `HB-USR-002` for `.*`, `(`, `mod-a` (rev 2, SEC 10) | those classes; a class named only inside prose | real `defect-classes.md` | M-C11 |
| C-12 `test_fix_refuses_a_commit_not_an_ancestor` | `HB-CMP-007` | an unrelated branch commit | real git | M-C12 |
| C-13 `test_fix_names_exactly_the_differing_components` | `HB-CMP-007` for each | one edit, zero named; one edit, one named + one unchanged named | n/a | M-C13 |
| C-14 `test_check_fix_refuses_a_wrong_before_hash` | `HB-CMP-007`; and `verify` replay fails on a hand-edited `before` | wrong `before` | real fold | M-C14 |
| C-15 `test_fix_scope_is_computed_never_accepted` (3) | scope `run`, `grade`, `both` for edits of `engine.py`, `grade/formal.py`, both; the parser has no `--scope` | n/a | real `identity.CLASSES` | M-C15 |
| C-17 `test_power_role_comes_from_state` | `prior` in `baselined`, `final` in `piloted` | n/a | stub `power.analyse` + X-INT-1 | M-C17 |
| C-18 `test_crash_between_file_and_row_recovers` (2) | parametrized over `power` and `register`: after a forced failure in `_append`, the rerun leaves one row and one file | monkeypatch `_append` to raise once | real `create_once` | M-C18 |
| C-19 `test_power_float_or_invalid_inputs_refused` | `HB-PWR-001` naming the field | a float `alpha` | real `ledger.canonical` | M-C19 |
| C-20 `test_pilot_attach_refuses_a_foreign_plan_a_missing_plan_and_a_ringless_plan` | `HB-CMP-002` for each; the row has `ring_hash`, `plan_hash` and no `tag` | plan with another campaign id; no `plan.json`; `ring: null` | real `plan.json` | M-C20 |
| C-21 `test_pilot_attach_refuses_non_pilot_ring` | `HB-CMP-002` | tag `comparison` | n/a | M-C21 |
| C-23 `test_pilot_pass_refuses_on_gate_items_and_passes_expected_na` | `HB-CMP-008` listing each item; no row; the stub receives `expected_na` equal to `readiness.expected_na`'s output as a keyword | stub gate returning one item | X-INT-1 runs the real `gates.pilot` | M-C23 |
| C-24 `test_pilot_gate_input_hash_changes_with_the_segment_heads` | two passes of one run differ in hash after a re-grade | n/a | **real segments** via `ledger.SegmentWriter` | M-C24 |
| C-25 `test_pilot_pass_refuses_an_unsealed_pass_and_an_unattached_run` | `HB-CMP-002` / `HB-CMP-008` | both | n/a | M-C25 |
| C-26 `test_admit_records_gates_admission_output` (rev 2) | one `admission.decided` row per task whose decision differs, `admitted` int, reason from `gates.admission`; `HB-USR-002` propagates for a not-recorded primary and writes no row | stub `gates.admission`: saturated, floor, kept, NA | X-INT-1 runs the real function | M-C26 |
| C-27 `test_admit_is_current_only_after_the_latest_pilot_pass` | a repeat `admit` after the same pass is a no-op; after a fix and a new pass, rows are appended again even when the decision is unchanged | n/a | n/a | M-C27 |
| C-28 `test_register_preview_writes_nothing_and_prints_level_rule_and_warning` | tree bytes identical; output has the hash, `alpha_per_test`, `level_rule`, and a `min_pairs` warning when below the required `n` (rev 2, PAT 5c, 5d) | `min_pairs` 3 against required `n` 20 | byte-compare of the whole campaign folder | M-C28 |
| C-29 `test_register_confirm_writes_file_then_row` (2) | `prereg/<h>.json` name = sha256, row names it; `--confirm` with a wrong or missing hash12 refuses `HB-CMP-008` and writes nothing (rev 2, DS 6) | file edited between preview and confirm | real `create_once` | M-C29, M-C29b |
| C-30 `test_register_refuses_each_unmet_precondition` | `HB-CMP-008` with its own copy | question differs; mde differs from final power; **final power predates the last fix** (rev 2, PAT 6); **no admission after the latest pass**; coverage cell missing; heads changed; local-path source | pilot plan from a real `plan.json`; power files real | M-C30a..g (one per case) |
| C-31 `test_register_with_another_hash_before_attach_appends_and_latest_wins` | second `registered` row; state `registered`; both rows remain | n/a | n/a | M-C31 |
| C-32 `test_prereg_with_a_local_path_source_is_refused` | refused (the manifest leak assertion is W1-D's) | `C:\Users\x\ai-forward` | n/a | M-C32 |
| C-33 `test_a_fix_in_registered_re_pilots_and_re_registers` (rev 2, PAT 1; absorbs old F-4) | on the real CLI: `registered` -> `fix` -> state `baselined` -> `register` refused `HB-CMP-002` (state) -> `pilot attach`, `pilot pass`, `power` final, `admit` each succeed -> `register` succeeds with state `registered` and a second `registered` row | n/a | real CLI throughout (fails today: no command) | M-F3b |
| C-35 `test_register_refused_once_a_grid_is_attached` | `HB-CMP-009` naming the run | after attach | n/a | M-C35 |
| C-36 `test_attach_refuses_each_plan_mismatch` | `HB-CMP-010` with its own copy | other campaign id; prereg hash; **identity hash (F-1)**; **forged `components` with the right `hash`** (rev 2, SEC 7); arm commit; launched run | real `plan.json`, real `identity.side` | M-C36a..f (one per case) |
| C-37 `test_attach_identity_check_compares_with_the_chain_not_the_tree` (3) | a plan whose identity equals the tree but not the chain is refused | tree drifted after the fix-free baseline, plan stamped from the tree | real manifest | M-C37 |
| C-38 `test_verify_failure_exits_5` (1) | exit code 5 via `main` | a broken chain | real `_exit_for` | M-C38 |
| C-41 `test_attach_of_a_pilot_plan_as_a_grid_is_refused` | `HB-CMP-010` (`prereg_hash` null) | pilot plan | n/a | M-C41 |
| C-42 `test_conclude_and_abandon_refuse_a_live_run` | `HB-CMP-002` for each | a subprocess holds the attached run's `.lock` | **real cross-process lock** | M-C42 |
| C-43 `test_conclude_only_from_measuring` | `HB-CMP-002` from `registered` | n/a | n/a | M-C43 |
| C-44 `test_abandon_other_reason_and_terminal_states_refused` | as named | n/a | n/a | M-C44 |
| C-45 `test_state_guard_matrix` | for every (command, state) cell: expected ok or `HB-CMP-002`; cells include `pilot pass` in `registered`, `register` in `baselined`, `attach` in `piloted`, `fix` in `measuring` ok | all refused cells | CLI | M-C45a..c |
| C-46 `test_every_refusal_names_item_cause_action` | the message matches `^HB-[A-Z]+-\d{3}: .+\. .+\.$` and contains the item from the case table | all refusal cases | CLI | M-C46 |
| C-47 `test_rerun_is_a_noop` (rev 2, SIM 4) | one parametrized node over (state fixture, argv) for `create`, `fix`, `power`, `pilot attach`, `pilot pass`, `admit`, `register`, `attach`, `conclude`, `abandon`: second run exits 0, prints `no change:`, ledger bytes unchanged | n/a | real CLI | M-C47 (one mutant per row: "no-op branch removed") |
| C-48 `test_a_failed_reader_writes_no_row_and_prints_its_text` (rev 2, PAT 5b) | `readiness.hidden_test_disagreements` raises; exit 1, `HB-CMP-008` with the exception text, no row | a raising stub reader | stub reader + the real `gates.pilot` in X-INT-1 | M-C48 |
| C-49 `test_attach_refuses_a_chain_stamped_plan_over_a_drifted_tree` (3; rev 2, SEC 5, 6) | `HB-CMP-010` naming the component, no row, and `register` is still allowed afterwards; a subset plan over an unchanged tree attaches | plan stamped with the chain hash while `grade/formal.py` differs; a subset plan | real manifest, real `plan.json` | M-C49 |
| C-50 `test_fix_refuses_a_component_unequal_to_its_commit` (rev 2, SEC 8) | `HB-CMP-007` | named component with an uncommitted edit; named component equal to the tree but not to `<commit>` | real git | M-C50 |

### N: names and paths

| id | assert / red today | red fixture | real wiring | mutant |
| --- | --- | --- | --- | --- |
| N-1 `test_malformed_ids_create_nothing` (rev 2, SEC 1) | for **every** command in `cli.COMMANDS`: `status ../../x`, `status ..`, `status nope`, `verify ..`, a run id `../x`, a task `a/b` exit 1 (`HB-USR-002` or `HB-CMP-005`) and the tmp tree is **byte-identical** afterwards (skeleton: `RunLock.acquire` would create folders) | those inputs | real CLI, real `RunLock` | M-N1: validate only in `create` |

### E: eligibility (pure)

| id | assert / red today | red fixture | real wiring | mutant |
| --- | --- | --- | --- | --- |
| E-1 `test_eligible_when_every_rule_holds` | `eligible True, reasons ()` (skeleton returns `eligible False`) | n/a | `run_facts` on a real run dir (X-INT) | M-E1 |
| E-2 `test_each_rule_adds_its_reason` | eight cases (rules 0-7: `not recorded` for an absent plan, then one reason each, fixed order) | eight runs, including a `plan_hash` that differs from the row and a second grid run with another `ring.hash` | n/a | M-E2a..h (drop each rule) |
| E-3 `test_grade_side_is_compared_with_the_current_effective_not_the_baseline` | a pass under the baseline grade side, after a grade fix, is withheld | n/a | n/a | M-E3 |
| E-4 `test_run_side_fix_after_attach_makes_the_run_ineligible_grade_fix_does_not` | ineligible for scope `run`, eligible-but-withheld for `grade` | n/a | n/a | M-E4 |
| E-5 `test_ordering_uses_seq_not_clocks` | with `recorded_at` skewed backwards, the verdict is unchanged | skewed stamps | n/a | M-E5 |

### L, I: locks and interleavings

| id | assert / red today | red fixture | real wiring | mutant |
| --- | --- | --- | --- | --- |
| L-1 `test_acquire_then_probe_never_lets_both_proceed` | across barrier races (a handful, 8; `between=Barrier(2).wait(timeout=10)`, test timeout 60 s with `terminate()`): `not (a_proceeded and g_proceeded)` in every race, and the refusing side's files unchanged; the swapped-order mutant makes **both proceed in every race** (S-C5: 20 of 20), so the test fails on it (skeleton does not probe: both proceed). **Rev 2, TA 4 / DS 3:** the assertion is *never both*, not *exactly both refused*: measured, one side proceeding after the other refused and released is allowed (17 of 20). No natural races in the fast ring; one batch of 40 runs once in the slow ring as characterisation (SIM 7) | n/a | **real `oslock` files, two OS processes** | M-L1 (probe before taking the own lock), M-L1b (probe the own path instead of the other's) |
| L-2 `test_a_command_is_refused_while_a_campaign_run_is_graded` | `HB-CMP-004`, campaign folder bytes unchanged, and the own lock is free afterwards | a subprocess holds `runs/R/grade.lock` | **real** lock, real CLI | M-L2 |
| L-3 `test_a_held_campaign_lock_refuses_with_hb_cmp_001` | exit 1 and the code | a subprocess holds `campaign.lock` | real lock | M-L3 |
| L-4 `test_lock_released_on_every_path` | after an exception inside a command, `is_held` is false | forced exception | n/a | M-L4 |
| L-5 `test_lock_that_is_a_folder_or_link_is_refused` | `HB-CMP-003` naming it (today: raw `PermissionError`) | a folder named `campaign.lock`; a symlink where the OS allows (skip reason asserted to run in the POSIX job) | n/a | M-L5 |
| L-6 `test_probe_set_is_the_attached_runs_plus_the_argument_only` | an unrelated run's held `grade.lock` does not block; an attached one does; for `conclude`/`abandon` an attached run's `.lock` blocks | both | real locks | M-L6 |
| L-7 `test_both_sides_call_the_same_helper_with_a_set` | AST: `campaign.session` and `grade/runner.py` call `oslock.acquire_then_probe` with a sequence of `(path, code)` entries; the engine-side `run_side_check` and `conclude` use the same primitives (rev 2, DS 2) | a runner that probes by `is_held` then acquires | n/a | M-L7 |
| L-8 `test_links_and_junctions_in_the_path_chain_are_refused` (rev 2, SEC 2) | `HB-CMP-003` naming the path | a linked `ledger.jsonl`; a linked `identity/`; a linked campaign folder; a linked `bench/discrimination/<task>/` (junctions on Windows, symlinks on POSIX with a skip reason asserted) | n/a | M-L8: `lstat` only the lock |
| L-9 `test_a_conclusion_and_a_run_start_never_both_proceed` (rev 2, DS 2) | with `between` on the `conclude` side and a barrier-synced `run_side_check`: never both (the run launches under a concluded campaign, or `conclude` appends under a live run) | n/a | **real** run lock and `campaign.lock` in two processes | M-L9: `run_side_check` reads the state without probing `campaign.lock` |
| L-10 `test_status_and_verify_work_while_a_run_is_graded_and_take_no_lock` (rev 2, SIM 2) | exit 0 with a held `grade.lock`; folder bytes unchanged; `RunLock.acquire` never called (spy) | a subprocess holds an attached run's `grade.lock` | real lock, real CLI | M-L10: route `status` through `session` |
| L-11 `test_every_writing_command_goes_through_session` (rev 2, TA 7) | AST scan of the command functions named in `cli.COMMANDS`: every function that calls `_append` is reached through `session`; reads do not call it | a fixture command that appends without `session` | n/a | M-L11 |
| I-1 `test_register_then_attach_interleaving` | register(Y) wins the lock, attach(plan X) is refused `HB-CMP-010`; ledger `registered` = Y. Both threads use `wait_s=30`; the winner releases on an event the loser sets (rev 2, DS 5) | n/a | threads, `session(wait_s)` and the `between` hook; real files | M-I1 |
| I-2 `test_attach_then_register_interleaving` | attach(plan X) wins; register(Y) refused `HB-CMP-009`; the run's plan hash equals the ledger's; same hand-off | n/a | same | **M-I2** (register reads its state before taking the lock; rev 2, TA 3) |
| I-3 `test_a_grid_launch_never_precedes_its_attach_row` | with a stub launcher recording the order, the `grid.attached` row's `seq` exists before the first launch | n/a | real `cmd_run` (P-3) | M-I3 |

### V, S, G: verify, sweep, ignore

| id | assert / red today | red fixture | real wiring | mutant |
| --- | --- | --- | --- | --- |
| V-1 `test_chain_break_is_named` | finding with line number | flipped byte | real file | M-V1 |
| V-2 `test_name_not_hash_is_named_for_identity_prereg_power` | one finding per folder | renamed file | n/a | M-V2 |
| V-3 `test_modified_deleted_or_renamed_committed_record_is_tampering` (rev 2, SIM 6: absorbs V-9) | finding names the path; parametrized over a content file edited, a content file deleted, a discrimination record deleted, a discrimination record renamed | those four | **real git** | M-V3: skip the equality-with-HEAD check |
| V-4 `test_ledger_appends_pass_and_a_rewritten_prefix_is_refused` | passes after an uncommitted append, after `git add` (`A `, `AM`, `MM`; rev 2, PAT 2); a finding after rewriting a committed line | all | **real git** (spike S-C3) | M-V4a (any difference from HEAD refuses), M-V4b (a rewritten prefix passes) |
| V-4b `test_a_committed_torn_tail_does_not_block_the_next_command` (rev 2, DS 1) | torn tail, `git commit`, a command (`reopen` truncates and appends), then `verify` is clean | the committed torn ledger | real git, real `reopen` | M-V4c: compare the whole HEAD blob |
| V-4c `test_a_committed_prefix_rewrite_is_refused` (rev 2, SEC 4) | two commits, the second rewrites a prefix with a recomputed chain: finding naming the commit | that history | real git | M-V4d: compare HEAD only |
| V-5 `test_untracked_new_content_file_is_allowed` | no finding | new `identity/<h>.json` | real git | M-V5 |
| V-6 `test_leaked_temp_is_a_named_warning_not_a_failure` (rev 2, SIM 6: absorbs V-7) | warning lists the name, exit 0; parametrized over a temp file and a temp folder with a file | both | real `atomic.is_temp_name` | M-V6 |
| V-8 `test_not_a_work_tree_is_refused` | `HB-CMP-003` | tmp dir without git | real git | M-V8 |
| V-10 `test_referenced_hash_missing_is_named` | finding | row names a missing prereg | n/a | M-V10 |
| V-11 `test_assume_unchanged_and_skip_worktree_are_findings` (rev 2, SEC 3b) | finding naming the path for `h` and `S` flags on a modified committed ledger and a modified committed content file | `git update-index --assume-unchanged` and `--skip-worktree` edits | real git | M-V11: drop the `ls-files -v` check |
| V-12 `test_an_ignored_stray_path_and_a_missing_gitignore_line_are_findings` (rev 2, SEC 3b) | finding for an extra `.gitignore` line covering `bench/campaigns/`, a `.git/info/exclude` line, and each of the three lines removed in turn | those | real git | M-V12a (drop `--ignored`), M-V12b (drop the exact-text check) |
| S-1 `test_old_temp_is_swept_under_the_lock_and_logged` (2) | the temp is gone; the sweep ran while `is_held(campaign.lock)` | aged temp (`os.utime`) | **real `atomic.sweep_temps`** | M-S1 |
| S-2 `test_young_temp_is_left` (2) | still present, reported | fresh temp | n/a | M-S2 |
| S-4 `test_a_linked_task_dir_is_skipped_with_a_warning` (rev 2, SEC 9) | the link target survives; a named warning | junction as `bench/discrimination/<task>` | real sweep | M-S4: sweep every directory |
| G-1 `test_gitignore_covers_every_temp_name_and_the_campaign_lock` | `git check-ignore` true for a temp file, a temp folder and its inner file under both trees and for `campaign.lock` (today: false) | `x.json`, `campaign.lock.bak` must **not** be ignored | real `git check-ignore` | M-G1 |
| G-2 `test_a_fresh_clone_with_autocrlf_still_verifies` (slow ring, SIM 6) | state `baselined`, verify clean | clone with `core.autocrlf=true` | real git | M-G2 |

### P, B, T, Q: plan, run, status, telemetry, trace

| id | assert / red today | red fixture | real wiring | mutant |
| --- | --- | --- | --- | --- |
| P-1 `test_plan_with_campaign_stamps_the_chains_effective_run_side` (3) | `plan.json` block `identity.hash == identity_hash(side(effective,"run"))`, not the tree's; asserted by value through `cli_rc` (today `--campaign` does not exist: `cli_rc` returns 2 and no `plan.json` exists) | after a recorded fix, tree == effective; both stamps differ from the baseline's | **real `cmd_plan`** | M-P1 |
| P-2 `test_plan_refuses_a_drifted_tree` | exit 1, `HB-CMP-010` naming `grade/formal.py` (rev 2: tree drift is HB-CMP-010) | edit without a fix | real manifest | M-P2 |
| P-3 `test_bench_run_refuses_an_unattached_campaign_plan` | exit 1, `HB-CMP-010`, **no `cell.launch_intent` in the run's events** (today `cmd_run` ignores the block and the fake launcher launches) | pilot plan unattached; grid plan attached to nothing; grid plan whose registered hash moved | **real `cmd_run` and engine**, fake only at the launcher | M-P3 |
| P-3b `test_bench_run_accepts_a_pilot_plan_via_ring_run_attached` | the launcher is reached (W-3) | attached pilot | real | M-P3b |
| P-4 `test_a_plan_stamped_from_a_drifted_tree_is_refused_at_plan_time_at_attach_and_at_the_first_launch` (3) | three refusals: `HB-CMP-010`, `HB-CMP-010`, then `HB-IDN-001` from the real engine | hand-built stamp from the tree | **real `bench run` with `identity_check=` wired**; fails if that keyword is removed from `cmd_run` | M-P4 |
| P-5 `test_tree_edit_after_attach_stops_the_first_launch` (3) | engine stops, no `cell.launch_intent`, exit 3 | edit a run-side file after attach | real engine with a fake launcher | M-P5 |
| P-6 `test_a_plan_edited_after_attach_is_refused_at_run_time` (rev 2, SEC 7) | `HB-CMP-010` naming the run, no launch | delete a task from `plan.json` after attach | real engine, real `plan_hash` | M-P6: skip the `plan_hash` compare |
| P-7 `test_the_campaign_check_runs_under_the_run_lock_before_the_first_launch` (rev 2, DS 2) | the check callable observes `is_held(runs/R/.lock)` true and no launch yet; removing the `campaign_check=` line from `cmd_run` fails it | a recording check | **real `cmd_run`** | M-P7: drop the line |
| B-1 `test_status_json_is_schema_bound` | `parse_status(to_json(x)) == x`; unknown field, wrong `state`, missing field rejected | three bad documents | real `parse_status` | M-B1 |
| B-2 `test_status_json_carries_no_free_text` | `question` and every `reason` absent | a campaign with both | n/a | M-B2 |
| B-3 `test_status_next_token_follows_state` | one token per state (adjacent: `baselined`/`piloted`, `piloted`/`registered`) | n/a | n/a | M-B3 |
| T-1 `test_one_log_record_per_command_with_the_declared_fields` | record fields, `outcome`, `code` on refusal | refusal and success | real logger | M-T1 |
| T-2 `test_a_phase_that_did_not_run_is_absent_never_zero` | refused at probe: no `verify_ms` key; `status`: no `lock_wait_ms` | the L-2 case | n/a | M-T2 |
| T-3 `test_every_cited_test_id_exists` (rev 2, TA 6) | every `[A-Z]-\d+[a-z]?` id cited in sections 2 to 12 and 16 exists in section 13 and every mutant id cited exists in the ledger | a doc with a dangling id | the real doc | M-T3 |

### Cross-track joins (owner **X-INT**, a condition of done for X-C; rev 2, TA 9)

X-INT is the Leader's join node; X-C is not done until these three pass with the partners joined.
- X-INT-1 `test_full_walk_with_real_gates_power_and_readiness`: create to attach with the real `gates.pilot`, `gates.admission`, `power.analyse` and `readiness.*` (partners of C-17, C-23, C-26, C-48).
- X-INT-2 `test_run_pass_of_a_campaign_run_is_refused_while_campaign_lock_is_held`: X-F's HB-GRD-007 with the real runner (partner of L-2; both orders of the same helper).
- X-INT-3 `test_after_grading_hook_is_lock_free_and_verifies_with_two_attached_runs_one_graded` (rev 2, DS 4): the hook prints `campaign verify: ok`, with a sibling attached run's `grade.lock` held; HB-CMP-005 prints `not run`.

### Mutant ledger (rev 2, TA 2: every mutant is a written edit and the input it flips)

File `tests/mutations/campaign.json`; `find`/`replace` are gists to be made literal at X-C. Where two rules are adjacent the input on which they differ is named.

| id | edit | flips on |
| --- | --- | --- |
| M-F1 | `registered` result state `measuring` | any prefix ending in `registered` (registered/measuring) |
| M-F2 | allow `grid.attached` from `piloted` | `piloted` then `grid.attached` |
| M-F3a / M-F3b | a fix leaves `piloted` / `registered` unchanged | fix in `piloted` / in `registered` (piloted vs baselined; registered vs baselined) |
| M-F6 | `FIELDS` check allows extra keys | row with a `state` field |
| M-F7 | store `True` for `admitted` | a bool row |
| M-F8 | skip the folder-id check | ledger of A in folder B |
| M-F9 | treat `ledger.tail_repaired` as an unknown kind | repaired ledger |
| M-F12 | a fix in `measuring` moves to `baselined` | fix after `grid.attached` |
| M-C1 | `create` appends two rows | a single `create` |
| M-C2 | overwrite the question | second `create` with another question |
| M-C3 | drop the 500-char bound | 501-char question |
| M-C4 | hash only the run side for `identity_hash` | the full manifest vs the run side (differ on any grade-side component) |
| M-C5 | ignore untracked files in the dirty check | untracked new `src/` file |
| M-C6 | check only the first BOM task | last task `stub` |
| M-C7 | compare the freeze version only, not the hash | freeze with `0.7` but another hash |
| M-C8 | file-exists check for the spike note | note with `status: draft` |
| M-C9 | second `baseline` appends; or compares with the baseline instead of the effective identity | repeat after a fix |
| M-C10 | apply the first fix's `after` twice | two fixes |
| M-C11 | substring match for the class instead of the heading regex | `MOD-A` only inside prose |
| M-C12 | `git cat-file -e` instead of `merge-base --is-ancestor` | unrelated branch commit |
| M-C13 | allow the named set to be a subset | one edit, zero named |
| M-C14 | skip the before-hash comparison | wrong `before` |
| M-C15 | take `scope` from `--scope` | an edit whose real scope is `grade` |
| M-C17 | accept `role` from args | `power` in `baselined` with `final` |
| M-C18 | delete the file on a failed append | forced `_append` failure then rerun |
| M-C19 | coerce floats to strings | float `alpha` |
| M-C20 | skip the campaign-id check in `pilot attach` | foreign plan |
| M-C21 | accept any ring tag | `comparison` plan |
| M-C23 | ignore the gate list | one `GateItem`; also: drop the `expected_na` keyword |
| M-C24 | hash the run id only | re-graded pass |
| M-C25 | skip the unsealed-segment check | missing `scores/G.jsonl` seal |
| M-C26 | write `admitted=True` or recompute saturation locally | stub returning `(0, "floor")` |
| M-C27 | the no-op test ignores the latest-pass boundary | repeat `admit` after a fix and a new pass |
| M-C28 | preview writes the prereg file | preview run |
| M-C29 | append the row before the file / M-C29b: skip the `--confirm` hash compare | crash between; edited file |
| M-C30a..g | remove one register check each: question, mde, final-power currency, admission currency, coverage, heads, local path | the matching red fixture |
| M-C31 | the second `registered` row replaces the first | register twice |
| M-C32 | allow any string as `source` | local path |
| M-C35 | allow register while no run has launched (the ADR wording) | attached but unlaunched run |
| M-C36a..f | remove one `check_plan` clause each: campaign id, prereg hash, identity vs chain, components rehash, arm commit, launched run | the matching mismatch |
| M-C37 | compare the plan's identity with the tree | chain differs from tree |
| M-C38 | remove `HB-CMP-003` from the integrity prefixes | broken chain |
| M-C41 | skip the `prereg_hash` null check | pilot plan attached as grid |
| M-C42 | skip the run-lock probe in `conclude`/`abandon` | live run |
| M-C43 | allow `conclude` from `registered` | registered vs measuring |
| M-C44 | allow another reason on a repeat `abandon` | repeat with another reason |
| M-C45a..c | widen the guard of `register` to `baselined`, `attach` to `piloted`, `pilot pass` to `registered` | those cells |
| M-C46 | drop the action sentence from one refusal | every refusal |
| M-C47 | remove the no-op branch of the command under test | the second run |
| M-C48 | swallow the reader exception and call the gate with `[]` | raising stub |
| M-C49 | skip the tree comparison in `attach` | chain stamp over drifted tree |
| M-C50 | skip the commit-equality check in `fix` | named component equal to the tree, not the commit |
| M-N1 | validate ids only in `create` | `status ../../x` |
| M-E1 | `eligible` always False (skeleton shape) | all rules hold |
| M-E2a..h | drop rule 0..7 in turn | the matching run |
| M-E3 | compare the grade side with the baseline | grade fix then a pass under the baseline grade side |
| M-E4 | any fix scope counts for rule 5 | a grade fix after attach |
| M-E5 | order by `recorded_at` | skewed stamps |
| M-L1 | in `acquire_then_probe`, probe `others` before acquiring `own` (the barrier stays between the two operations) | every barrier race: both proceed |
| M-L1b | probe `own` instead of `others` | every barrier race |
| M-L2 | probe only the run argument, not the attach rows | held lock on an attached sibling |
| M-L3 | block instead of try on `campaign.lock` | held lock: the command hangs, test times out |
| M-L4 | release only on success | forced exception |
| M-L5 | no `lstat` on `campaign.lock` | folder named `campaign.lock` |
| M-L6 | probe every run under `runs/` | unrelated held run |
| M-L7 | the runner probes by `is_held` then acquires | AST fixture |
| M-L8 | `lstat` only the lock | linked ledger or sub-folder |
| M-L9 | `run_side_check` reads state without probing `campaign.lock` | `conclude` vs run start |
| M-L10 | route `status` through `session` | held `grade.lock` |
| M-L11 | one command appends without `session` | AST fixture |
| M-I1 | `attach` reads the state before taking the lock | register(Y) then attach(plan X) |
| M-I2 | `register` reads the state before taking the lock | attach(plan X) then register(Y) |
| M-I3 | skip `campaign_check` | unattached grid plan |
| M-V1 | skip the chain check | flipped byte |
| M-V2 | check one folder only | renamed file in each |
| M-V3 | skip equality-with-HEAD for content files | edited, deleted, renamed record |
| M-V4a | any difference from HEAD refuses the ledger | uncommitted append |
| M-V4b | a rewritten prefix passes | rewritten committed line |
| M-V4c | compare the whole HEAD blob | committed torn tail then repair |
| M-V4d | compare HEAD only (no pair walk) | committed prefix rewrite |
| M-V5 | untracked new content refused | new `identity/<h>.json` |
| M-V6 | skip temps silently | temp file or folder |
| M-V8 | pass when not a work tree | tmp dir |
| M-V10 | skip the referenced-hash check | row naming a missing prereg |
| M-V11 | drop the `ls-files -v` check | assume-unchanged edit |
| M-V12a / M-V12b | drop the `--ignored` scan / the exact `.gitignore` text check | extra ignore line; removed line |
| M-S1 | sweep outside the lock | aged temp |
| M-S2 | no age gate | fresh temp |
| M-S4 | sweep every directory under `bench/discrimination` | junction task dir |
| M-G1 | delete one `.gitignore` pattern | each ignore case |
| M-G2 | keep CRLF in the written ledger | autocrlf clone |
| M-P1 | stamp the working tree | after a recorded fix |
| M-P2 | warn only on tree drift | edit without a fix |
| M-P3 | delete the `campaign_check=` line | unattached plan |
| M-P3b | require `grid.attached` for a pilot | attached pilot |
| M-P4 | drop `identity_check=` | stamp from drifted tree |
| M-P5 | skip the launch-time identity check | edit after attach |
| M-P6 | skip the `plan_hash` compare in the run-side check | plan edited after attach |
| M-P7 | the check runs before the run lock is taken | recording check |
| M-B1 | lenient `parse_status` | three bad documents |
| M-B2 | include `question` in the document | campaign with both |
| M-B3 | one `next` token for `baselined` and `piloted` | adjacent states |
| M-T1 | omit `code` on refusal | refusal |
| M-T2 | default the missing phase to 0 | the L-2 case |
| M-T3 | skip the id scan | doc with a dangling id |

**Trace to W0 contracts (README testability trace).** W0 section 6 ledger kinds -> F-6, F-2; freeze order -> C-35, C-36, I-1, I-2, P-3, P-7; locks -> L-1..L-11; `.gitignore` -> G-1, V-12; content-addressed files -> C-4, C-29, V-2; identity API use -> C-4, C-10, P-1; section 4 `sweep_temps`, `is_temp_name` in `verify` -> S-1, S-2, S-4, V-6; section 13 `cmd_plan`, `identity_check=`, `campaign_check=` -> P-1..P-7; ADR-0018 11(b) -> V-3..V-12; `plan_hash` -> C-20, C-36, P-6, E-2.

## 14. Requests, decisions, open items

| id | to | content | status |
| --- | --- | --- | --- |
| SR-C1 `req-01M41F6QRJ49VE2VES5Y527K61` | Coordinator | `oslock.acquire_then_probe` | **granted in part, W0 rev 4**: a set of `others`, `between` keyword-only; owner **X-B1**, not X-C. This revision conforms |
| SR-C2 `req-01M41F6R2NR3JTJDA1JMX9V0KX` | Coordinator | W0 text fixes (a) to (e) | **granted, W0 rev 4.** (e): the hook is lock-free and X-C's hunk |
| OI-1 | W1-H / X-H2 | ring eligibility | **ruled, W0 rev 4**: read from the attached runs' plans; implemented as eligibility rule 7 |
| OI-2 | W1-H | the grid a prereg names | **ruled, W0 rev 4**: the final power inputs; implemented in `register` coverage |
| OI-3 | W1-H | admission saturation | **ruled, W0 rev 4**: `gates.admission` (X-H1); implemented as `admit` |
| OI-4 | RV-SIM | `ring_run.attached.tag` constant | **ruled, W0 rev 4**: dropped |
| OI-5 (rev 2) | Coordinator | After `register`, the powered design cannot change without abandoning: `power` final is legal only in `piloted`, and a fix needs an engine diff. EV-13 allows re-registering before launch, so a different MDE after registering needs a path. Not widened here (findings are advice, not scope). Recommendation: allow `power` final in `registered` and refuse `attach` unless the latest final row predates the latest `registered` row | open, deferred to X-C or a ruling |

Spikes run (scratchpad, not committed; commands in section 15): S-C1 lock semantics and the folder-lock failure; S-C4 own-then-probe, 90 races; S-C3 git porcelain on campaign-shaped changes; **S-C5 (rev 2)** the barrier positive control.

## 15. Evidence

| claim | evidence |
| --- | --- |
| bool refused by canonical | V `ledger.py:43` |
| same-process second acquire refused; cross-process acquire refused; a killed holder frees the lock; a folder lock raises `PermissionError` | V spike S-C1 (`spike_c1.py`, PYTHONPATH = the tree's `src`, Python 3.12.10) |
| never both proceed; both-refused occurs; probe makes the other's acquire fail briefly | V spike S-C4: forced overlap 30 runs `{one proceeded: 20, both refused: 10}`; natural 60 runs `{one proceeded: 54, both refused: 4, own-held: 2}` (characterisation, not proof) |
| the barrier test can fail, and the correct order passes it | V spike S-C5 (`spike_c5.py`, `msvcrt`, Windows, 20 runs per mode, this session): correct order `{one proceeded: 17, both refused: 3}`, 0 both; swapped order `{BOTH PROCEEDED: 20}` |
| porcelain: lock and temps invisible; ` M` on an appended ledger; `??` new files; ` D`; rename `R  a -> b`; HEAD prefix true for append, false for rewrite; no commit gives 128; not a repo gives 128 | V spike S-C3. Not run this revision: staged letters, `ls-files -v` flags and `--ignored` output. They are consumed through content comparison and exit codes, with tests V-4, V-11, V-12 on a real repo (I: git behaviour) |
| `.gitattributes` `* text=auto eol=lf` | V `.gitattributes:4` |
| error registry rejects unknown codes | V spike S-C1 first run (`errors.py:118`) |
| `_exit_for` integrity prefixes | V `cli.py:48-49` |
| `RUN_ID` pattern | V `status.py:38` |
| `oslock.acquire`/`is_held` use the same byte-0 lock and `acquire` does `mkdir(parents=True)` then `O_CREAT` | V `oslock.py` (read this revision) |
| `plan.confirm` writes `plan.json` with mode `x` | V `plan.py:357-366` |
| grading segments are `scores/<grading_id>.jsonl` and `events/<grading_id>.jsonl` | V `views.py:52-100` |
| spike E4 note is `status: accepted` | V `docs/notes/spike-e4-post-turn-prompt.md` frontmatter |
| B2 is the schema-bound campaign status | V `docs/architecture-evaluation-campaign.md:254, 302` |
| W0 rev 4 change table and sections 6, 8, 13 re-read | V main `5fcd8a7c` |

## 16. Review disposition (rev 2)

Every finding of the five first-round reviews has a row. "Applied" names where.

| review | # | severity | disposition | where |
| --- | --- | --- | --- | --- |
| RV-PAT | 1 | blocking | **Applied.** A fix in `registered` demotes to `baselined`; the full re-pilot path is legal at each step; `pilot_current` removed (it is implied by the state); C-33 walks it on the real CLI; C-45 carries the `registered` row for `pilot pass` | 4, 2, 5, C-33, F-3 |
| RV-PAT | 2 | major | **Applied.** The witness keys on content; staged `A `, `AM`, `MM` need no rule; V-4 asserts them on a real repo | 7 step 5, V-4 |
| RV-PAT | 3 | major | **Applied.** The set form of `others`, owned by X-B1; L-6 and L-7 assert the set | 6, L-6, L-7 |
| RV-PAT | 4 | minor | **Applied.** `between` keyword-only; pattern named | 6, 10 |
| RV-PAT | 5 | major | **Applied.** (a) arity per W0 rev 4 with `expected_na=`; (b) a failed reader writes no row; (c) `level_rule` and `alpha_per_test` in the preview; (d) the `min_pairs` warning | 5 `pilot pass`, `register`, C-23, C-28, C-48 |
| RV-PAT | 6 | major | **Applied.** The final power row must follow the last baseline or fix; admissions must follow the latest pilot pass; C-30 has a case and a mutant for each | 2, 5 `register`, C-30, C-27 |
| RV-PAT | 7 | minor | **Applied as a stated rule.** One code per command family; HB-CMP-008 means "a decision's inputs do not hold" | 12 |
| RV-PAT | 8 | minor | **Applied.** `baseline` compares with the effective identity (C-9); `session` named Execute-Around | 5, 10 |
| RV-SEC | 1 | major | **Applied.** Ids validated at parse and at `session` entry; non-`create` commands create nothing; N-1 | 5, 6 step 0, N-1 |
| RV-SEC | 2 | major | **Applied.** `lstat` of the whole chain in `session` and `verify` step 0; L-8; the `lstat`-to-open race named as FM-17 | 6 step 0, 7 step 0, L-8 |
| RV-SEC | 3 | major | **Applied.** Content witness; `ls-files -v` `h`/`S`; `--ignored` scan; the three `.gitignore` lines by exact text; V-11, V-12 | 7 step 5 |
| RV-SEC | 4 | major | **Fixed, not a residual.** Commit-pair prefix walk; V-4c; the uncommitted full rewrite stays the accepted residual | 7 step 5b, FM-15 |
| RV-SEC | 5 | major | **Applied** (and W0 rev 4). `attach` and `plan --campaign` compare the tree's run side; C-49 | 5 `attach`, C-49 |
| RV-SEC | 6 | minor | **Applied with an `assume:`**: tasks from the effective identity, builds from the plan; C-49's subset case | 5 `attach` |
| RV-SEC | 7 | major | **Applied.** `plan_hash` on both rows (W0 rev 4); `components` re-hashed; the run-side check compares `plan_hash`; C-36, P-6 | 3, 5, P-6 |
| RV-SEC | 8 | minor | **Applied.** Named components must be clean and equal to the commit; C-50 | 5 `fix` |
| RV-SEC | 9 | minor | **Applied.** Task dirs from the effective identity, `lstat`-ed; S-4 | 7 sweep |
| RV-SEC | 10 | minor | **Applied.** `^[A-Z]+-[A-Z0-9]+$` then `re.escape`; C-11 | 5 `fix` |
| RV-DS | 1 | major | **Applied.** HEAD blob cut at its last newline; V-4b | 7 step 5a |
| RV-DS | 2 | major | **Applied.** `run_side_check` inside the engine through `campaign_check=` (run lock, then probe `campaign.lock`); `conclude` and `abandon` probe the run lock; L-9, L-7, P-7 | 5, 6 |
| RV-DS | 3 | major | **Applied.** `between` defined between the two operations (W0 rev 4); a timeout on the barrier; the swap mutant kills the test; no natural races in the fast ring | 6, L-1 |
| RV-DS | 4 | major | **Applied.** The hook is lock-free, so HB-CMP-001/004 cannot arise; HB-CMP-005 prints `not run`; X-INT-3 with two attached runs | 6 hook |
| RV-DS | 5 | minor | **Applied.** `wait_s=30` and event hand-offs | 6, I-1, I-2 |
| RV-DS | 6 | minor | **Applied.** `--confirm <hash12>`; C-29 | 5 `register` |
| RV-DS | 7 | minor | **Applied.** The lock domain `assume:` | 6 |
| RV-TA | 1 | major | **Applied.** The landing order and which tests are provisional until which commit; independent expected values | 13 |
| RV-TA | 2 | major | **Applied.** The mutant ledger gives every mutant an edit and an input | 13 |
| RV-TA | 3 | major | **Applied.** M-I2 on I-2 | 13 |
| RV-TA | 4 | major | **Applied in part, with a measurement.** The barrier test asserts *never both* and the mutant's both-proceed; "exactly both refused" is not forced (S-C5: 17 of 20 had one side proceed after the other refused and released), so the finding's assertion would fail a correct implementation. M-L1b added; natural races moved to the slow ring | 13 L-1, 0 W-9 |
| RV-TA | 5 | minor | **Applied.** The evidence is the proof plus the barrier test with a positive control (S-C5); the 90-race count is labelled a characterisation; Windows only is stated | 6, 15 |
| RV-TA | 6 | minor | **Applied.** References corrected; T-3 scans the ids | 5, 11, T-3 |
| RV-TA | 7 | minor | **Applied.** L-11 (AST scan with a red fixture); the "no exception" sentence now says "write commands" | 5, 6, L-11 |
| RV-TA | 8 | minor | **Applied.** F-9 asserts the row count; F-10 retired; `parse_status`/`to_json` in the skeleton; `cli_rc` for P-1 | 13 |
| RV-TA | 9 | minor | **Applied.** Owner X-INT; a condition of done for X-C | 13 joins |
| RV-SIM | 1 (OI-4) | minor | **Applied.** `tag` dropped (W0 rev 4); `ring_hash` kept with named readers | 3, 2 |
| RV-SIM | 2 | major | **Applied** (W0 rev 4). `status`, `verify`, the preview and the hook are lock-free; L-10 | 5, 6 |
| RV-SIM | 3 | minor | **Applied.** F-5, F-10, F-11 retired | 13 |
| RV-SIM | 4 | minor | **Applied.** C-47 parametrized; C-16, C-22, C-39 retired | 13 |
| RV-SIM | 5 | minor | **Applied.** C-32 trimmed; C-40 retired; F-4 merged into C-33 | 13 |
| RV-SIM | 6 | minor | **Applied.** V-7 into V-6, V-9 into V-3, S-3 retired, G-2 to the slow ring | 13 |
| RV-SIM | 7 | minor | **Applied.** Natural races out of L-1 | L-1 |
| RV-SIM | 8 | major | **Applied** (W0 rev 4 arity ruled). `expected_na` from `readiness.expected_na`; OI-2 and OI-3 ruled | 5, 14 |
| RV-SIM | 9 | minor | **Applied.** `SPIKE_E4` marked `simplify:` | 5 `baseline` |

## Gate record

First round (verbatim):

`GATE W1-C · Patterns Expert · BLOCK · 8 findings (rv-pat-hc-e1e4, 2026-10-03)`
`GATE W1-C · Security & Identity · PASS WITH CONDITIONS · 10 findings (rv-sec-w1c-e1e4, 2026-10-03)`
`GATE W1-C · Distributed Systems · PASS WITH CONDITIONS · 7 findings (rv-ds-w1c-e1e4, 2026-10-03)`
`GATE W1-C · Test Architect · PASS WITH CONDITIONS · 9 findings (rv-ta-hc-e1e4, 2026-10-03)`
`GATE W1-C · Simplifier · PASS WITH CONDITIONS · 9 findings (rv-sim-hc-e1e4, 2026-10-03)`

rev 2 pending RV-PAT, RV-SEC

## Status

| | |
|---|---|
| **Completed** | revision 2: the one re-pilot path after a fix, content-keyed git witness over the committed history, id and link validation, plan binding by `plan_hash`, the run-side pair inside the engine, lock-free reads, a written mutant for every test, the S-C5 positive control, and a disposition row for all 43 findings |
| **Remaining** | RV-PAT and RV-SEC on revision 2; OI-5; X-INT joins |
| **Best next action** | RV-PAT re-reads sections 4 and 5 and C-33; RV-SEC re-reads sections 5, 6 step 0 and 7 |
