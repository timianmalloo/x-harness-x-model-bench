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
  Designs campaign.py and the `bench campaign` commands: a closed 11-kind hash-chained ledger folded into a derived state,
  the transition table, a state guard / idempotency rule / refusal copy / test node for every command, lock-then-read with
  the own-lock-then-probe protocol (measured: at most one side proceeds, never both), the pre-registration freeze
  (attach before launch, re-register refused once attached), the effective-identity checks at plan time and at attach
  (W1-D F-1), `verify` with a git-prefix rule for the ledger, derived eligibility, and a test plan whose every node
  names the assertion that fails today, the red fixture, the real-wiring partner and the distinguishing mutant.
---

# W1-C: the campaign record and `bench campaign`

Evidence labels: **V** verified (opened or run this session), **I** inferred, **A** `assume:` (belief, what confirms it, what breaks if false). W0 means `docs/design/eval-seam-contracts.md` at **revision 3** (main `1ceea651`); sections 4, 6 and 13 were re-read at rev 3 before this was finished.

## 0. Findings against W0 and the ADRs (read first)

Each is evidence-backed and each has a disposition in section 14.

| # | finding | evidence | effect on this design |
| --- | --- | --- | --- |
| W-1 | W0 section 6 says `admission.decided` carries `admitted: bool`. `ledger.canonical` refuses a bool. | V `ledger.py:43` (`isinstance(value, bool)` raises `TypeError`) | `admitted` is an int, 0 or 1. A narrowing of the type, not a new field. |
| W-2 | W0 section 6 says of the lock test "exactly one proceeds". Measured: **at most one** proceeds; **both refusing** also happens. Never both proceeding. | V spike S-C4: forced overlap, 30 runs: 14 + 6 one side proceeded, 10 both refused, 0 both proceeded. Natural race, 60 runs: 0 both proceeded. | The test asserts "never both"; both-refused is allowed and leaves every file unchanged (section 6). |
| W-3 | W0 section 6 step 3 says `bench run` of a plan with a `campaign` block needs `grid.attached`. A **pilot** plan carries the block too (`prereg_hash: null`) and is attached by `ring_run.attached`. As written, a pilot run cannot start. | W0 section 5 `campaign` block; ADR-0016 section 1 row kinds | `bench run` accepts `ring_run.attached` for a plan whose `prereg_hash` is null and `grid.attached` for one that carries a hash (section 5, `require_attached`). |
| W-4 | `RunLock.acquire` on a path that is a folder raises a raw `PermissionError`. `is_held` does the same. | V spike S-C1 | `campaign.lock` is `lstat`-ed first (RV-SEC W1-B 8): a folder or link is HB-CMP-003. |
| W-5 | `is_held` try-locks and then unlocks. During those microseconds the **other** side's `RunLock.acquire` can fail. | V spike S-C4: 2 of 60 natural runs showed `own-held` while the other proceeded | Harmless (a refusal), but the refusal code can be the "wrong" one for a moment. Section 6 states it. |
| W-6 | `git status --porcelain` lists the ledger as ` M` after any uncommitted append. A rule "any change refuses" would block the second command of every campaign. | V spike S-C3 | `verify` interprets porcelain: untracked new content files are fine; a modified tracked content file is tampering; a modified ledger is fine only if `git show HEAD:<ledger>` is a byte prefix of it (section 7). |
| W-7 | The error registry rejects unknown codes (`ValueError`). Every `HB-CMP-*` must be in `errors.py` before the first test runs. | V spike S-C1 first run | X-D's first commit (W0 section 11) is a join dependency. |
| W-8 | `cli._exit_for` maps only `HB-LED*` and `HB-SEC*` to exit 5. `HB-CMP-003` would exit 1. | V `cli.py:48-49` | X-C adds `HB-CMP-003` to the integrity prefixes. Test C-38. |

## 1. Responsibility, boundary, phasing

**One responsibility:** keep the record of one campaign, and decide, under one lock, whether each next step is allowed.

It owns `src/harness_bench/campaign.py` (grade class, W0 section 9), the `bench campaign` subcommands in `cli.py`, the `--campaign` option of `cmd_plan`, the `require_attached` line in `cmd_run` and the `identity_check=` keyword (seam X-D to X-C, W0 section 13), `.gitignore` (three lines), `ledger.py` (**no edit needed**, section 3) and `status.py` (**no edit**, section 9). It does not own the identity builder (W1-D), the power and verdict maths (W1-H), the gate items (W1-H), readiness or the discrimination records' content (X-E), or the grader's lock half (X-F, HB-GRD-007).

**Phase and mocks.** E1, vertical slice "operator runs the E1 demo": real in this slice: ledger, lock protocol, verify, state fold, every command. Fakes at the seams, each with a real-wiring partner (section 12): `gates.pilot` and `power.analyse` (X-H1), `readiness.hidden_test_disagreements` (X-E), `identity.manifest` (X-D). Until those join, tests use a stub callable passed to the command function. The CLI path itself is never faked (all command tests drive `cli.main(argv)`).

**Placement against R-89:** the demo is one campaign, `cc-opus`, k = 3, a 2-arm pilot ring (`off`, `candidate`), then a mini grid expected `inconclusive (underpowered)`. The pre-registration records `min_pairs` <= 3. This slice only records that number.

## 2. Data model (settled first)

**Bounded context:** Evaluation Campaign. **Ubiquitous terms:** campaign, baseline, effective identity, defect fix, pilot, admission, pre-registration, attach, freeze, eligible.

**Aggregate: Campaign.** Root: `campaign_id`. Invariant it protects (one): *the campaign's state is a forward-only walk over its rows; from the baseline on the engine identity changes only by an admitted fix; from the first attached grid run the registered pre-registration never changes.* Everything else is referenced by identity: runs by `run_id`, gradings by `grading_id`, identities, pre-registrations and power inputs by content hash, tasks by id. One aggregate per transaction: a command appends at most one row (the one exception is `create`, whose single row is also the whole aggregate).

**Entities and value objects.**
- Entity: the Campaign (the ledger). A **recorded defect fix** is a row of it, not a second aggregate (it has no life outside the campaign).
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
- `power.recorded.input_hash` per role, `admission.decided.admitted` per task: latest wins, earlier rows stay.
- `defect_fix.admitted`: accumulates in order; the **effective identity** is the fold of the baseline manifest with the fixes in seq order.
- A Type-1 overwrite exists nowhere. A test attempts one (F-6, C-30).

**Derive, don't store.** Derived, never written: `state`, `pilot_current`, the effective identity, the admitted-task set, the gate result, eligibility, power outputs, verdicts. A row with a `state` field is refused (F-6). `scope` and `role` are stored but are **written by the command from derived facts**, never accepted from the operator (section 4), so there is no second operator-supplied definition. `scope` is the one stored derivation; see the justification in section 3, kind 3.

**Persisted field -> writer -> compute reader (DM15).**

| field | writer | compute reader |
| --- | --- | --- |
| `campaign.created.question` | `create` | `campaign.read`; `register` (question equality); not in B2 |
| `baseline.recorded.{identity_hash, bench_commit}` | `baseline` | `effective_identity`; `verify` (file exists, name = hash); `status` |
| `defect_fix.admitted.{defect_class, commit, changes, scope}` | `fix` | `effective_identity`; `eligibility`; `verify` (replay) |
| `power.recorded.{role, input_hash}` | `power` | `register` (final equals prereg); X-H2 header |
| `ring_run.attached.{tag, ring_hash, run_id}` | `pilot attach` | `pilot pass`; lock probe set; `eligibility` |
| `pilot.passed.{run_id, grading_id, gate_input_hash}` | `pilot pass` | `register` (re-verifies heads); state fold |
| `admission.decided.{task, admitted, reason}` | `admit` | `register` (coverage); X-H2 |
| `registered.prereg_hash` | `register` | `attach`, `require_attached`, `plan --campaign`, `eligibility` |
| `grid.attached.run_id` | `attach` | `require_attached`; lock probe set; `eligibility`; `conclude` |
| `concluded`, `abandoned.reason` | `conclude`, `abandon` | state fold; `status` |
| every row: `kind`, `campaign_id`, `recorded_at`, `mono_ns`, `seq`, `prev_hash`, `hash` | `campaign._append` | `verify`, `fold` |

**Migration.** None: new folders, no existing data. The only shared-data change is `.gitignore` (three added lines): expand only, reversible by deleting them.

**Append-only enforcement.** The only write API is `_append(kind, **fields)`, which validates the closed field set and takes the next `seq` from the chain. There is no update or delete function. Tests attempt a forbidden update (C-30: edit a committed content file; rewrite a ledger prefix) and `verify` refuses.

## 3. The kinds, justified against "derivable from the other rows?" (RV-SIM 11)

The W0 kind enum is kept as-is: 11 kinds, none added, none merged. Each was tested for derivability.

| # | kind | derivable? | why it stays |
| --- | --- | --- | --- |
| 1 | `campaign.created` | no | it holds the id binding and the question; nothing else does |
| 2 | `baseline.recorded` | no | an operator act that fixes the identity; the transition `draft` to `baselined` |
| 3 | `defect_fix.admitted` | no | an operator act. Its `scope` field **is** derivable from the `changes` keys and `identity.CLASSES`, but is kept: `CLASSES` can change later (editing it is itself a fix), and a past fix must keep the meaning it had when admitted (Type-2 reasoning). The command computes it; no flag accepts it |
| 4 | `power.recorded` | no. Its `role` looks positional (before or after the pilot), but a fix after the pilot re-opens the "prior" slot, so position is ambiguous | `role` is written by the command from the state (`baselined` -> prior, `piloted` -> final) |
| 5 | `ring_run.attached` | membership is not derivable: `plan.campaign` in a plan is a claim; the ledger is the witness, and `runs/` is gitignored. Needed by `pilot pass`, the lock probe set and `require_attached` | merged candidate: `ring_run.attached` + `grid.attached` into one. Rejected: the grid has a **freeze effect** (HB-CMP-009) and need not come from a ring file, so the two are different transitions |
| 6 | `pilot.passed` | not derivable from 5 | it is a **decision** with the hash of its inputs; the attach row exists even when the gate fails |
| 7 | `admission.decided` | the saturation test is derivable from pilot scores, but those live in gitignored `runs/` and are absent on a fresh clone; the row is the durable witness of why a task is not in the grid (UF-E1 "named tasks not admitted") | `admitted` is int 0/1 (W-1) |
| 8 | `registered` | no | transition and the pointer to the prereg file |
| 9 | `grid.attached` | no | see 5 |
| 10 | `concluded` | not derivable: a multi-night grid has no "last run" until the operator says so | transition |
| 11 | `abandoned` | no | transition and reason |

`ring_run.attached.tag` is constant in E1: only a `pilot` ring run attaches (a `pack-regression` run belongs to no campaign, UF-E2 and EV-20). It is kept because it is W0's field; the command stores the plan's own `ring.tag` and refuses any tag but `pilot`. *Flag for RV-SIM:* a constant field. The cost of dropping it is a W0 change; the cost of keeping it is one string.

Closed field sets, enforced by `_append` and re-checked by `verify`:

```python
FIELDS = {  # exact field sets besides kind, campaign_id and the stamp; types: s=str, i=int, d=dict
    "campaign.created": {"question": "s"},
    "baseline.recorded": {"identity_hash": "s", "bench_commit": "s"},
    "defect_fix.admitted": {"defect_class": "s", "commit": "s", "changes": "d", "scope": "s"},
    "power.recorded": {"role": "s", "input_hash": "s"},
    "ring_run.attached": {"tag": "s", "ring_hash": "s", "run_id": "s"},
    "pilot.passed": {"run_id": "s", "grading_id": "s", "gate_input_hash": "s"},
    "admission.decided": {"task": "s", "admitted": "i", "reason": "s"},
    "registered": {"prereg_hash": "s"},
    "grid.attached": {"run_id": "s"},
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
| `defect_fix.admitted` | `baselined`, `piloted`, `registered`, `measuring` | `piloted` -> `baselined`; others unchanged |
| `power.recorded` role prior | `baselined`, `piloted` | unchanged |
| `power.recorded` role final | `piloted` | unchanged |
| `ring_run.attached` | `baselined`, `piloted` | unchanged |
| `pilot.passed` | `baselined`, `piloted` | `piloted` |
| `admission.decided` | `piloted` | unchanged |
| `registered` | `piloted`, `registered` | `registered` |
| `grid.attached` | `registered`, `measuring` | `measuring` |
| `concluded` | `measuring` | `concluded` |
| `abandoned` | `draft`, `baselined`, `piloted`, `registered`, `measuring` | `abandoned` |

`pilot_current` (derived flag) = a `pilot.passed` row exists with `seq` greater than the last `baseline.recorded` or `defect_fix.admitted` row. A fix in `registered` leaves the state `registered` but makes `pilot_current` false, so a re-registration waits for a new pilot pass (section 5, register). A row that is illegal in its state makes `verify` fail with HB-CMP-003 naming the row's `seq` and kind.

Adjacent state pairs the tests must tell apart (each has a mutant, section 12): `draft`/`baselined` (baseline), `baselined`/`piloted` (pilot pass and the fix demotion), `piloted`/`registered` (register), `registered`/`measuring` (attach).

## 5. The commands (the convergence condition)

Every command is `bench campaign <sub> <campaign_id> ...` and follows the **session protocol** (section 6): own lock, probe, verify, read state, decide, write, release. "No-op" means exit 0, no row, the line `no change: <what already holds>`. Refusal copy is `<code>: <item> <cause>. <action>.` and names the item (EVX-4). Exit codes: 0 ok or no-op; 1 refusal (`_exit_for`); 5 for HB-CMP-003. Tests are ids from section 12.

| command | state guard (else HB-CMP-002) | idempotency (the one definition: same content again = no-op, different content in a state that forbids it = refusal) | refusals (code: copy) | tests |
| --- | --- | --- | --- | --- |
| `create <id> --question Q` | no ledger yet | ledger exists with the same question: no-op. Different question: HB-CMP-002 | `HB-USR-002: campaign id "X" is malformed (^[a-z0-9][a-z0-9-]{0,39}$). Choose another id.` / `HB-CMP-002: campaign "X" already exists with another question. A new question needs a new campaign id.` | C-1..C-3 |
| `baseline <id> --tasks T,...` (default: the ten property ids in the BOM) | `draft`. In any later state: no-op if the tree's manifest hash equals the recorded `identity_hash`, else HB-CMP-006 | as left | HB-CMP-006, one copy per unmet precondition, each ending with its action: `component "src/harness_bench/x.py" has an uncommitted change. Commit or discard it, then run baseline again.` / `task "S1" is not ready (BOM status stub). Finish authoring it.` / `catalog 0.7 is not frozen in bench/catalog-freeze.yaml. Run the catalog freeze.` / `spike E4 is not accepted (docs/notes/spike-e4-post-turn-prompt.md status is X). Complete the spike.` / `the tree differs from the baseline at <diff>. Only a recorded fix changes the engine: bench campaign fix.` | C-4..C-9 |
| `fix <id> --class C --commit SHA --component KEY ...` | `baselined`, `piloted`, `registered`, `measuring` | a fix row with the same `defect_class` and `commit` whose `after` values equal the effective identity now: no-op | HB-CMP-007: `defect class "X" is not in docs/lessons/defect-classes.md. Record the class first.` / `commit "X" is not an ancestor of HEAD. Commit the fix.` / `component "K" changed and no fix names it. Add --component K.` / `component "K" is named but unchanged. Remove it.` / `component "K": before <h12> is not the effective identity's <h12>.` | C-10..C-16 |
| `power <id> --inputs FILE` | `baselined`, `piloted` | the same `input_hash` with the same role already recorded: no-op. A crash between the file and the row: the retry appends the row only | `HB-PWR-001: power inputs invalid: <field>. Fix the field.` (raised by `power.analyse`; a float anywhere is invalid because the canonical form has none) | C-17..C-19 |
| `pilot attach <id> <run_id>` | `baselined`, `piloted` | same run: no-op | HB-CMP-002 `run "R" belongs to campaign "Y" (plan.campaign), not "X".` / `run "R" is a <tag> ring run, not a pilot. Plan it from the pilot ring.` / `run "R" has no confirmed plan under runs/.` | C-20..C-22 |
| `pilot pass <id> <run_id> [--grading-id G]` | `baselined`, `piloted` | same `(run_id, grading_id, gate_input_hash)` as the latest `pilot.passed`: no-op | `HB-CMP-008: pilot gate failed: <kind> <ident> ... Fix the cause, record the fix, rerun the pilot.` / `HB-CMP-002: run "R" is not attached as a pilot.` / `grading pass "G" is not complete.` | C-23..C-25 |
| `admit <id> <task> --admit\|--exclude --reason R` | `piloted` | same latest decision for the task: no-op | `HB-CMP-002: task "T" is not in the pilot run's plan.` | C-26, C-27 |
| `register <id> --prereg FILE [--confirm]` | `piloted`, or `registered` while `pilot_current` and no grid attached. Without `--confirm`: print the statement and hash, write nothing | same hash as the current `registered`: no-op | HB-CMP-008: `prereg question differs from the campaign's. Changing the question needs a new campaign.` / `prereg mde for "P" (x) is not the final analysis's (y). Re-run power with the MDE you accept.` / `pilot did not cover (task T, harness H, arm A). Rerun the pilot.` / `pilot gate inputs changed since the pass (heads differ). Re-record the pilot.` / `arm "A" source is a local path. Use the remote URL or omit source.` / `no current pilot: a fix was admitted after the last pass.` HB-CMP-009: `pre-registration is frozen: run "R" is attached. Abandon this campaign or create a new one; the grid's verdicts would be exploratory.` | C-28..C-35 |
| `attach <id> <run_id>` (grid) | `registered`, `measuring` | same run: no-op | HB-CMP-010 (one predicate, `check_plan`): `plan.campaign.prereg_hash <h12> is not the registered <h12>.` / `plan.campaign.identity <h12> is not the effective run-side identity <h12>; differs at <diff>. Plan again.` / `plan arm "A" pack <commit12> is not the pre-registered <commit12>.` / `run "R" has already launched a cell. Plan a new run.` / `run "R" belongs to campaign "Y".` | C-36..C-41 |
| `conclude <id>` | `measuring` | `concluded`: no-op | HB-CMP-002: `run "R" is still running. Wait or bench stop.` | C-42, C-43 |
| `abandon <id> --reason R` | `draft` .. `measuring` | `abandoned` with the same reason: no-op; another reason: HB-CMP-002 | `campaign "X" is already abandoned (<reason>).` / `campaign "X" is concluded; nothing to abandon.` | C-44 |
| `verify <id>` | any | read-only | HB-CMP-003 (section 7) | V-series |
| `status <id> [--json]` | any | read-only | HB-CMP-005 for an unknown id | B-series |

**Command details that carry a decision.**

- **baseline.** Builds `identity.manifest(root, tasks, builds)` (X-D) and writes `identity/<h>.json` through `create_once`, then the row. `identity_hash` is the hash of the **full** manifest (W0 rev 3). Preconditions are one function, `baseline_unmet(root, tasks) -> list[str]`, so a test reads the list. The dirty check is `git status --porcelain` limited to the manifest components' paths (`src/harness_bench`, `bench/{bom,metrics,prices,gateway}.yaml`, `bench/profiles`, `uv.lock`, `tasks/<id>`); untracked files under them count. "Every property task authored" is `status: ready` in `bench/bom.yaml`. "Catalog 0.7 frozen" is `bench/catalog-freeze.yaml` `versions['0.7'].catalog_hash == identity.catalog_hash(root)`. "Spike E4 cited as passed" is the constant `SPIKE_E4 = "docs/notes/spike-e4-post-turn-prompt.md"` having frontmatter `status: accepted` (V: it does today). *Flag:* the machine sees only "accepted", not whether the spike passed.
- **fix.** The operator names the components (`--component`, at least one). The command computes `diff(effective, working-tree manifest)` and requires the named set to equal the differing set exactly (ADR-0017 section 4 "a change to a component no fix names"). `before` is read from the effective identity, `after` from the tree; `scope` from `identity.side`. The pure function `check_fix(effective, changes)` raises HB-CMP-007 on a before-hash that is not the effective one; the same function runs in `verify`'s replay, so a hand-edited ledger fails. The defect class must match a heading `^#{2,4}\s+<ID>\s*[:—–-]` in `docs/lessons/defect-classes.md` (V: headings there read `### MOD-A — ...` and `### CONC-A: ...`).
- **power.** The file is parsed, `power.analyse(inputs)` is called only as validation (HB-PWR-001 propagates), the canonical bytes are written with `create_once` to `power/<input_hash>.json`, then the row.
- **pilot pass.** Calls `gates.pilot(view, disagreements)` with `readiness.hidden_test_disagreements(run_dir, grading_id)` and the third parameter W0 rev 3 gave it (`unbiased_failures`, W1-H). A non-empty list refuses and prints each `GateItem` (kind, ident, detail). `gate_input_hash` = sha256 of `ledger.canonical({"grading_id": G, "scores_head": <head of scores/G.jsonl>, "events_head": <head of events/G.jsonl>})`, from `ledger.verify_segment(...).head_hash` (ADR-0016 section 7 "score-set segment heads"; V `views.py` layout). A missing or unsealed segment refuses.
- **register.** The prereg file is the EV-13 statement (W0 section 6). Checks, in order, all inside the lock: schema and closed field set; `question` equals the created one; `arms` packs are `{commit (40 hex), revision, source?}` and `source`, if present, is not a filesystem path (it must match `^(https://|ssh://|git@)`; W1-A section 8 asks for this, V; a local path leaks a user name into a committed file); for each property the prereg `mde`, and `alpha`, `power`, `correction`, `pairing_unit` equal the **final** power inputs (the file named by the latest `role: final` row), so the pre-registered values are the analysed ones; `pilot_current`; the recorded `gate_input_hash` equals the heads now; coverage: every admitted task x every harness in the final inputs x every prereg arm was a cell of the pilot run's plan (the pilot run must be present locally; otherwise HB-CMP-008 says so). *Open item OI-2:* the prereg body names no tasks or combos, so "the grid the pre-registration names" (ADR-0016 section 7) is read from the final power inputs; flagged to W1-H.
- **attach.** `check_plan(state, effective, plan, plan_dir)` (the one predicate, also used by `bench run`): `plan.campaign.campaign_id` is this id; `plan.campaign.prereg_hash` equals the current `registered.prereg_hash` (W0 freeze step 1); **`plan.campaign.identity.hash` equals `identity_hash(side(effective, "run"))`** (W1-D F-1, W0 rev 3 section 6 check 2); every arm of the plan has the pre-registered pack commit; the run has no `cell.launch_intent` in `runs/<id>/events`. This refusal uses HB-CMP-010. *Seam note:* rev 3 says "`grid.attached` refuses" without a code; HB-CMP-010 is the reserved code for "the plan does not match the ledger", so one predicate has one code.
- **bench plan --campaign <id> (rev 3 check 1, plus SR-2).** Reads the state without taking the lock (advisory; the binding check is `attach`, under the lock). It builds the campaign block as `{campaign_id, prereg_hash, identity: {hash: identity_hash(side(effective,"run")), components: side(effective,"run")["components"]}}` -- the **chain's effective run side, never a stamp of the working tree**. It first computes `side(manifest(root, tasks, builds), "run")` for the tree and refuses with HB-CMP-002 naming `diff(...)` if it differs: `engine differs from the campaign's effective identity: grade/formal.py changed. Record a fix or restore the file.` A pilot-ring matrix gets `prereg_hash: null`; any other matrix needs state `registered` or `measuring` and takes the registered hash; a `pack-regression` ring with `--campaign` is refused. The `cmd_plan` wiring from W1-A section 3.9 is pasted verbatim (SR-2) and adds the `campaign=` argument to `build_plan`.
- **bench run (`require_attached`, one line before `preflight.check` in `cmd_run`).** For a plan with a `campaign` block, under `campaign.lock` (no probe: it writes nothing): the run id has a `ring_run.attached` row (if `prereg_hash` is null) or a `grid.attached` row (if it carries one), and `check_plan` holds (so the registered hash and the effective identity are still the plan's). Else HB-CMP-010: `run "R" is not attached to campaign "X" (or its plan no longer matches the ledger). Run bench campaign attach.` The line `identity_check=identity.launch_check(root, p)` is added to `EngineConfig` beside it (X-D keyword).
- **conclude.** Refuses while any attached grid run's engine lock is held (`oslock.is_held(run_dir / ".lock")`).

## 6. Locks and sessions (D6; ADR-0018 11(a))

**Session protocol**, one context manager, `campaign.session(root, campaign_id, *, probe=True, wait_s=0.0)`; every `bench campaign` subcommand uses it with no exception:

1. `lstat` `campaign.lock`. Absent: fine. Present but not a regular file, or a reparse point: HB-CMP-003 naming it (RV-SEC W1-B 8; W-4).
2. `oslock.RunLock.acquire(lock, "HB-CMP-001")`. Held: wait up to `wait_s` (fixed 0.2 s steps; `simplify:` ceiling: callers wait seconds; upgrade trigger: a caller that waits minutes), then refuse HB-CMP-001.
3. **Read the ledger** (lock-then-read). Unknown campaign: HB-CMP-005 (and `create` passes `create=True`).
4. **Probe:** for every run in the campaign's attach rows plus the run argument of the command: `oslock.is_held(runs/<run>/grade.lock)`. Held: release own lock, refuse HB-CMP-004 `run "R" is being graded. A campaign write must not be open during a grading pass. Wait for the pass to finish.`
5. `verify` (section 7). Failure: release, HB-CMP-003, no command ran.
6. Sweep leaked temps (section 7).
7. Run the command; append; release in `finally`.

The protocol itself (own lock, then a non-blocking probe, release on a held probe) is **one function in `oslock.py`**, `acquire_then_probe(own, own_code, other, other_code, between=None)`, used by X-C here and by X-F for `grade.lock` then `campaign.lock` (HB-GRD-007). One definition for both sides (DM7); `oslock.py` has no owner in W0 section 13, so this is **seam request SR-C1**. `between` is a callable run after the own lock is held and before the probe; production passes `None`; the interleaving tests pass a barrier. A grading side that reaches the helper must call it **after** reading `plan.campaign.campaign_id`; the other side's lock path is `bench/campaigns/<id>/campaign.lock`.

**Why safe (reasoned, then measured).** A proceeds only if its probe saw G's lock free; G holds its own lock before it probes, so if A's probe saw it free G had not yet taken it; G then takes its own and probes A's lock, which A has held since before its probe: G refuses. So both cannot proceed. Both can refuse (each probe sees the other's lock, both release). Measured on this host: 0 of 90 runs had both proceed (spike S-C4). The `is_held` probe takes the other lock for microseconds; a concurrent `acquire` of that lock can then fail with its own held-code (W-5), which is a refusal either way. Safety does not depend on liveness: a stuck pair retries by the operator.

**What the lock does not cover.** `status` and `plan --campaign` reads: `campaign.read(root, id)` is library code, lock-free, and verifies the chain; a torn last line is ignored (ADR-0006). X-H2 uses it. `plan --campaign` is advisory because `attach` re-checks everything under the lock.

**The freeze order (DS-1; W0 section 6), and the race it closes.**
1. `attach` appends `grid.attached` under `campaign.lock` before the first launch, only if `check_plan` holds.
2. `register` is refused with HB-CMP-009 once any `grid.attached` exists.
3. `bench run` re-reads the ledger under the lock (`require_attached`).
Interleaving A: register(Y) first, attach(plan X): attach refuses (hash mismatch). Interleaving B: attach(plan X) first, register(Y): register refuses HB-CMP-009. Either way the registered hash equals the hash any attached run planned under. Tests I-1, I-2 (threads with the `between` hook for determinism; real cross-process lock semantics in L-2, L-3).

**After-grading hook (X-F seam, SR-C2).** ADR-0018 11(b) requires `verify` after every grading pass. The hook must run **after** `grade.lock` is released (inside the pass, the probe in `verify` would see the grader's own lock and refuse). Its entry point is `campaign.verify_for_plan(root, plan)`, which opens a session with `wait_s=3` and `probe=True`; on HB-CMP-001 the grader prints `campaign verify: not run (campaign locked)` and the grading result stands (the claim is "not verified", never "verified").

## 7. `verify`, the sweep and `.gitignore`

`verify(root, id)` returns a list of `Finding(code, path, detail)` and runs these checks in order. Any finding makes the command exit 5 with HB-CMP-003 naming the first and counting the rest.

1. **Chain.** `ledger.verify_segment`: `error` set means a break. A torn tail is not an error for a reader; `reopen` repairs it for the writer (and writes `ledger.tail_repaired`).
2. **Row shape.** Every row's `kind` is in `FIELDS` or `HOUSEKEEPING`; its field set equals `FIELDS[kind]` plus the stamp and chain fields; types match; `campaign_id` equals the folder name (a ledger copied into another campaign's folder fails here: the chain's genesis is bound to the segment id `ledger`, which is the same for every campaign, V `ledger.py:65`).
3. **Replay.** `fold` raises on an illegal row (section 4); each fix's `before` equals the effective value at that point.
4. **Content files.** Every file in `identity/`, `prereg/`, `power/` that is not a temp name (`atomic.is_temp_name`) has name = sha256 of its bytes and valid JSON of the right `schema`; every hash named by a row (`identity_hash`, `prereg_hash`, `input_hash`) exists.
5. **Git witness** (ADR-0018 11(b)). `git status --porcelain -uall -- bench/campaigns bench/discrimination` through `gitsafe.git`. Not a work tree (exit 128): refuse HB-CMP-003 `bench/campaigns is not in a git work tree; the witness is absent` -- no bypass flag. Interpretation (W-6, V spike S-C3):
   - `??` (untracked new file): allowed (step 4 already checked its name).
   - ` M`/`M ` on `ledger.jsonl`: allowed only if `git show HEAD:<path>` is a byte prefix of the working file; else tampering.
   - any other status on a path under these folders (a modified or deleted tracked content file, a deleted tracked discrimination record, a rename line containing ` -> `): tampering, named.
   - With no commit yet (`git show HEAD:` exit 128): the ledger is all new; allowed.
6. **Temps.** Every name matching `atomic.is_temp_name` in the campaign folders and `bench/discrimination/<task>/` is reported as a **warning line with its name** (never silent: RV-SEC W1-B 1; the three `.gitignore` lines hide them from step 5), including a temp **folder**; exit stays 0.

**The sweep** follows `verify`: for each base name that has temps in the campaign sub-folders and in `bench/discrimination/<task>/`, if **every** temp of that base has `mtime` older than `TEMP_MIN_AGE_S = 3600`, call `atomic.sweep_temps(dir / base)` under the lock (W0 section 4, rev 3). A younger temp may belong to a live `bench discriminate` writer, which does not take `campaign.lock` (RV-DS W1-B 3); it is left and reported. `sweep_temps` is the one place that guards reparse points; this module never calls `rmtree`.

**`.gitignore` (S-B2):** add exactly `bench/campaigns/**/*.tmp-*`, `bench/discrimination/**/*.tmp-*`, `bench/campaigns/*/campaign.lock`. `.gitattributes` already says `* text=auto eol=lf` (V), so a ledger stays LF on every checkout; C-48 proves a fresh clone with `core.autocrlf=true` still verifies.

## 8. Eligibility and the effective identity (compute readers)

```python
def effective_identity(root: Path, state: CampaignState, upto_seq: int | None = None) -> dict   # baseline manifest with fixes (seq <= upto) applied
def eligibility(state: CampaignState, effective: dict, run: RunFacts) -> Eligibility          # pure
@dataclass(frozen=True)
class RunFacts: run_id; plan_campaign_id; plan_prereg_hash; plan_run_identity_hash; grade_identity_hash  # last: grading.started, W1-D 6
@dataclass(frozen=True)
class Eligibility: eligible: bool; reasons: tuple[str, ...]      # EV-20 copy, one per failing rule, fixed order
def run_facts(run_dir: Path, grading_id: str) -> RunFacts        # the only impure loader (reads plan.json and the grading.started row)
```

Rules (ADR-0017 section 5, narrowed to what the ledger can decide without clocks): a run is eligible iff all hold, and each failure adds its reason:
1. its plan names this campaign;
2. a grid run's `plan_prereg_hash` equals the registered one;
3. the run is attached (`ring_run.attached` or `grid.attached`);
4. `plan_run_identity_hash` equals `identity_hash(side(effective_identity(upto = attach seq), "run"))` (attach already enforced this; recomputed so a hand-edited ledger cannot hide it);
5. **no fix of scope `run` or `both` has `seq` greater than the run's attach `seq`** (attach precedes the first launch by the freeze order, so this is "no run-side fix after the first launch" without comparing clocks across stores);
6. `grade_identity_hash` equals `identity_hash(side(effective_identity(now), "grade"))` (a pass under an older grade side is withheld until re-graded, EV-16); the reason names `diff`;
7. `pilot_current` holds.

*Narrowing noted:* ADR-0017 says the run-side manifest equals the effective one "at some point of the chain". Because attach demands equality with the **current** effective identity, "some point" is always the attach point; rule 4 states that. *Open item OI-1:* ADR-0017 section 5 also says "its ring hash matches the campaign's ring". The grid row records no ring hash (and W0 forbids a new field), so this rule is not decidable from the ledger; it is left to W1-H/X-H2 against the plan, flagged.

## 9. Change surfaces (E7)

| layer | surface | owner |
| --- | --- | --- |
| store | `bench/campaigns/<id>/{ledger.jsonl, identity/, prereg/, power/, campaign.lock}`; `.gitignore` | X-C |
| model | `campaign.py`: `FIELDS`, `fold`, `CampaignState`, `effective_identity`, `eligibility`, `check_plan`, `check_fix`, `baseline_unmet` | X-C |
| service | `session`, the twelve command functions; `oslock.acquire_then_probe` (SR-C1); `cmd_plan --campaign`; `cmd_run` `require_attached` and `identity_check=` | X-C; `oslock` by seam |
| projection / wire | `bench campaign status --json` = `bench-campaign-status/1` (below). `bench-status/1` is **unchanged**: it is strict (`status._exact`), and a campaign view is not a run view. ADR-0016 "bench status --json gains a campaign view" is read as the B2 line in the architecture ("`bench campaign status --json`, schema-bound", V `architecture-evaluation-campaign.md:254`). A `campaign` field in run status can follow in E3 with X-K2 (`status.py` owner) | X-C |
| client type | `parse_status(document) -> CampaignStatus` validates strictly like `status.parse`; the `question` and `reason` are not in the document (B2) | X-C |
| UI | CLI text of each command; the report header reads `campaign.read` (X-H2) | X-C, X-H2 |
| compute reader | `eligibility`, `effective_identity` (X-H2, W1-D's diff text), `gate_input_hash` | X-C |

`bench-campaign-status/1` document: `{"schema", "campaign_id", "state", "pilot_current", "baseline_identity_hash", "effective_run_hash", "effective_grade_hash", "fixes": [{"defect_class","commit","scope"}], "power": {"prior","final"}, "prereg_hash", "pilot_runs": [...], "grid_runs": [...], "excluded_tasks": [...], "next": "<fixed token>"}`; `next` is a fixed token from a closed set (`baseline`, `pilot`, `power`, `register`, `attach`, `wait`, `conclude`, `none`) so a machine reader never parses prose.

## 10. Patterns (Ladder climbed)

| decision | rung | pattern | rejected |
| --- | --- | --- | --- |
| ledger | reuse `ledger.SegmentWriter` unchanged | append-only hash-chained log (ADR-0006) | a campaign-specific log format |
| state | derive | **Event sourcing, fold over a closed transition table** | a stored `state` column (a second definition) |
| content files | reuse `atomic.create_once` | **Content-addressed store** | `open("x")` |
| mutual exclusion | reuse `oslock` | **Mutual Exclusion, own-lock-then-try-probe** (one function) | check-then-lock (races, W-2 mutant) |
| command shape | one context manager | **Template Method** (`session`) | per-command copies of lock/verify/sweep |
| plan check | one function | **Specification** (`check_plan`) shared by `attach`, `bench run`, tests | two predicates drifting |
| eligibility | pure function over facts | **Policy as a pure function** | reading `runs/` inside the rule |
| `verify` git rule | stdlib `git` via `gitsafe` | **Witness check** (prefix for append-only, equality for immutable) | "any change refuses" (W-6) |

Simplifier pass: no `Campaign` class with methods (a frozen `CampaignState` and functions), no registry of commands (a dict in `cli.COMMANDS`), no cache of the fold (tens of rows; `simplify:` ceiling 10,000 rows, trigger: `fold` over 5 ms median), no per-command lock variants, no `ledger.py` change, no `status.py` change, no `--campaign` alias for `bench verify`, no generic sweeper (W0 section 4 supplies it). A new dependency: none.

## 11. Failure modes, adversarial analysis, privacy

**Failure modes** (design choices -> how it fails -> disposition -> test):

| # | category | mode | disposition | test |
| --- | --- | --- | --- | --- |
| FM-1 | concurrency | check-then-lock window on a command | prevent: lock first, then read (`session`) | I-1, I-2, M-I1 |
| FM-2 | concurrency | `campaign.lock` and `grade.lock` both held by two writers | prevent: own-then-probe; at most one proceeds; both-refused leaves files unchanged | L-1, L-2 |
| FM-3 | concurrency | the freeze window between register and first launch | prevent: attach freezes (HB-CMP-009) and `bench run` re-reads under the lock | I-1, I-2, P-3 |
| FM-4 | state | crash between `create_once` and the row append | recover: the retry finds the file, appends the row (idempotent) | C-18, C-34 |
| FM-5 | state | crash mid-append (torn tail) | recover: `reopen` truncates and records `ledger.tail_repaired`; readers ignore the tail | F-9, F-10 |
| FM-6 | state | a plan stamped from a drifted tree | prevent at plan time (HB-CMP-002), at attach (HB-CMP-010) and at the first launch (HB-IDN-001) | P-1, P-2, P-4 |
| FM-7 | state | run-side fix after attach, before launch | detect: the engine stops at the first launch (drift vs the plan's identity); eligibility rule 5 | P-5, E-5 |
| FM-8 | input | float, bool or non-string key in an inbound JSON | prevent: canonical form refuses; HB-PWR-001 / HB-CMP-008 | C-19, F-7 |
| FM-9 | input | oversized or control-character free text | prevent: <= 500 chars, printable | C-3 |
| FM-10 | resource | leaked temps accumulate | recover: sweep under the lock, age-gated; warn by name | S-1, S-2 |
| FM-11 | resource | live writer's temp swept | prevent: age gate (`TEMP_MIN_AGE_S`) | S-2 |
| FM-12 | dependency | git absent or not a work tree | prevent: refuse HB-CMP-003, no bypass | V-8 |
| FM-13 | dependency | a seam module (gates, power, readiness) not joined | the commands that call it refuse with a named import-time-free error; tests use the stub parameter | C-23 |
| FM-14 | time | clock skew | not used: ordering is by `seq`; eligibility uses `seq` | E-5 |
| FM-15 | state | the operator edits the ledger and recomputes the chain | detect: the git-prefix rule on a committed prefix; a fully uncommitted history is accepted residual (single operator, ADR-0012) | V-4 |
| FM-16 | concurrency | spurious refusal by a probe (W-5) | accept: a refusal is safe; retry | L-1 (counts outcomes) |

**STRIDE-lite.** Boundaries: (1) operator CLI -> ledger; (2) hostile agent code during a grading pass -> committed records (ADR-0018 11); (3) plan files in gitignored `runs/` -> the campaign.

| threat | boundary | disposition | negative test |
| --- | --- | --- | --- |
| S: a plan claims another campaign's id | 3 | mitigate: `check_plan` compares `plan.campaign.campaign_id` and the attach row | C-36 |
| T: edit a committed content file | 2 | mitigate: name = hash, git status; detected not prevented (ADR-0016 8) | V-2, V-3 |
| T: rewrite the committed ledger prefix | 2 | mitigate: git prefix rule | V-4 |
| T: plant content in a temp folder or a `campaign.lock` folder (hidden by the ignore lines) | 2 | mitigate: warn by name; `lstat` the lock | V-6, V-7, L-5 |
| T: swap a temp between write and link (`create_once`) | 2 | transfer to W1-B's inode check (RV-SEC W1-B 2); content-addressed callers' hash check is the second line | V-2 |
| R: who changed what | 1 | mitigate: every row is chained, stamped, committed; refusals are not rows (architecture line 254) and are logged | T-1 |
| I: path, user name or env in a committed file | 1 | mitigate: manifests carry no path (W1-D leak test); prereg `source` must not be a path; free text is bounded | C-32 |
| D: a held lock blocks the grader for long | 1 | accept: commands are short; the grader's own hook retries 3 s | L-3 |
| E: agent code writes a campaign record while a pass runs | 2 | mitigate: ADR-0018 11(a) both-directions refusal; residual accepted (ADR-0012/0013) | L-2, X-INT-2 |

**Privacy (LINDDUN-lite).** No personal data by design: the files hold hashes, ids, a campaign question and decision reasons that the operator writes. Residual: free text could hold a name; it is length-bounded, printable-only and absent from the B2 document. Retention: git history. Rights path: the operator edits their own repo. Linkability of `bench_commit` to a person: accepted (git history already links).

## 12. Telemetry (instrumentation over inference)

Questions an operator asks, each with an emitting source (no flag, on the normal path): how long did a command take, how much of it was waiting for the lock, verifying, sweeping; how often is a command refused and by which code; how many temps were swept; how big is the ledger.

One structured log record per command on logger `harness_bench.campaign` (the project's JSON-lines convention, no cell text):
`{"event": "campaign.command", "command", "campaign_id", "state_before", "state_after", "outcome": "ok|noop|refused", "code": "HB-CMP-...|null", "rows": n, "lock_wait_ms", "verify_ms", "sweep_ms", "swept": n, "duration_ms"}`. A phase that did not run (refused earlier) is **absent**, never `0` (IO1). `bench campaign status` prints the last line `rows <n>, verified in <ms>`. Load-bearing telemetry has a test: T-1 (record fields), T-2 (absent, never zero).

Error codes used: `HB-CMP-001..010` (confirmed, none retired, none merged: each has a distinct operator action), `HB-USR-002`, `HB-PWR-001`, `HB-LED-007` (via `create_once`). `errors.py` rows are X-D's first commit (W-7). No HTTP surface.

## 13. Test plan by node id

**Red-first protocol (the testability floor).** The first X-C commit lands `campaign.py` as a **skeleton with inert bodies**: `read` returns `state=draft` with no rows, `verify` returns `[]`, `session` yields without locking, command functions return 0 and write nothing, `oslock.acquire_then_probe` acquires the own lock and does not probe. Every test below is written against the skeleton and fails on a **value assertion**, named in the third column; none fails with an `ImportError` or `AttributeError`. Tests on existing code (`cmd_run`, `cmd_plan`, `.gitignore`, `_exit_for`) fail against today's tree for the reason given.

Files: `tests/test_campaign.py` (F, C, E), `tests/test_campaign_locks.py` (L, I), `tests/test_campaign_verify.py` (V, S, G), `tests/test_cli_campaign.py` (P, B, T). Temp repos are real `git init` repos in `tmp_path`; the CLI is driven through `cli.main(argv)` (real parser, real session) in every command test. Mutants live in `tests/mutations/campaign.json` in the repo's format (`name`, `file`, `find`, `replace`, `tests`); each mutant names the test that must fail.

Column key: **Assert / red today** = the assertion and why it fails on the skeleton or today's code. **Red fixture** = the input that must be refused (for a guard). **Real wiring** = the test that exercises the real collaborator beside a fake. **Mutant** = the change that only this test (or pair) catches, between adjacent rules or states.

### F: fold, rows, state

| id | assert / red today | red fixture | real wiring | mutant (adjacent pair) |
| --- | --- | --- | --- | --- |
| F-1 `test_fold_walks_the_transition_table` | after each legal prefix, `read(...).state == TABLE[...]` (skeleton returns `draft`, so the `baselined` assertion fails) | n/a | rows written by real commands via `cli.main` | M-F1: `registered` lands `measuring` (registered/measuring) |
| F-2 `test_illegal_row_for_its_state_is_hb_cmp_003` | `verify` returns a finding naming `seq` and kind (skeleton returns `[]`) | 8 cases: `baseline.recorded` first; `grid.attached` in `piloted`; `registered` in `baselined`; any kind after `concluded`; `admission.decided` in `baselined`; `power final` in `baselined`; second `campaign.created`; `defect_fix` in `draft` | ledgers hand-built with `ledger.SegmentWriter` | M-F2: allow `grid.attached` from `piloted` (skips `registered`) |
| F-3 `test_fix_after_pilot_demotes_to_baselined_and_stales_the_pilot` | state `baselined`, `pilot_current False`; then `pilot.passed` gives `piloted` | n/a | n/a | M-F3: a fix leaves `piloted` (baselined/piloted) |
| F-4 `test_fix_in_registered_keeps_registered_but_stales_the_pilot` | state `registered`, `pilot_current False` | n/a | register refusal C-33 | M-F4: a fix in `registered` demotes (registered/baselined) |
| F-5 `test_latest_wins_for_registered_power_and_admission` | the third `registered` value is current and all three rows remain | n/a | n/a | M-F5: first wins |
| F-6 `test_row_field_sets_are_closed_and_state_is_not_stored` | `verify` finds a row with a `state` field, a missing field, an extra field, a wrong type (skeleton `[]`) | the four rows | `_append` refuses the same four before writing (second assertion) | M-F6: `FIELDS` open (extra allowed) |
| F-7 `test_admission_row_stores_int_and_bool_is_refused` | stored line contains `"admitted":1`; `_append(admitted=True)` raises HB-CMP-003 (W-1) | a bool row | real `ledger.canonical` refuses a bool beneath | M-F7: store `True` (caught by canonical TypeError mapped to the code) |
| F-8 `test_ledger_copied_between_campaigns_fails_verify` | finding `campaign_id` differs from folder | ledger of A in folder B | n/a | M-F8: skip the folder-id check |
| F-9 `test_tail_repaired_row_is_housekeeping_not_a_transition` | after a torn tail and `reopen`, state is unchanged and verify passes | the repaired ledger | real `SegmentWriter.reopen` | M-F9: treat it as an unknown kind |
| F-10 `test_reader_ignores_a_torn_tail` | `read` excludes the half-written row | a ledger with a truncated last line | real file | M-F10: `read` counts the torn row |
| F-11 `test_every_kind_has_a_writer_and_a_reader` | the set of kinds written by a full walk equals `FIELDS` keys, and each is consumed by `fold` (skeleton writes none) | a 12th kind in `FIELDS` with no writer fails | the full walk uses the real CLI | M-F11: add an unused kind |

### C: commands (state guard x idempotency x refusal copy)

| id | assert / red today | red fixture | real wiring | mutant |
| --- | --- | --- | --- | --- |
| C-1 `test_create_writes_one_row_and_is_idempotent` | one `campaign.created` row after two runs (skeleton: zero) | n/a | real `cli.main` | M-C1: no-op branch removed (two rows) |
| C-2 `test_create_with_another_question_is_refused` | exit 1, `HB-CMP-002`, ledger bytes unchanged | second question | n/a | M-C2: overwrite question (same-vs-different content) |
| C-3 `test_malformed_id_and_free_text_are_refused` | `HB-USR-002` for `-a`, `A`, 41 chars; question of 501 chars or with a control char | those inputs | n/a | M-C3: drop the length bound |
| C-4 `test_baseline_records_identity_file_and_row` | `identity/<h>.json` exists, name = sha256 of bytes, row `identity_hash == identity_hash(manifest)`, `bench_commit == HEAD` | n/a | **real `identity.manifest` and a real git repo** | M-C4: hash of the run side only (full vs side) |
| C-5 `test_baseline_refuses_a_dirty_component` | `HB-CMP-006` naming the file and the action | modified tracked `src/` file; untracked new `src/` file | real `git status` | M-C5: ignore untracked (pair: tracked/untracked) |
| C-6 `test_baseline_refuses_a_task_not_ready` | `HB-CMP-006` naming `S1` | BOM status `stub` | n/a | M-C6: check only the first task |
| C-7 `test_baseline_refuses_unfrozen_catalog` | `HB-CMP-006` | freeze file without `0.7`; with `0.7` but a different hash | real `identity.catalog_hash` | M-C7: compare version only (version vs hash) |
| C-8 `test_baseline_refuses_unaccepted_spike` | `HB-CMP-006` | note with `status: draft` | n/a | M-C8: file-exists check only |
| C-9 `test_baseline_twice_same_tree_noop_changed_tree_refused` | no-op, then `HB-CMP-006` naming the diff | edit after baseline | n/a | M-C9: second baseline appends |
| C-10 `test_fix_roundtrip_effective_identity_equals_tree` | after one fix, `effective_identity == identity.manifest(tree)` | n/a | **real manifest**, two commits | M-C10: apply `after` of the first fix twice |
| C-11 `test_fix_refuses_an_unknown_defect_class` | `HB-CMP-007` | `ZZZ-Z` | real `defect-classes.md` | M-C11: substring match instead of heading (`MOD-A` inside prose) |
| C-12 `test_fix_refuses_a_commit_not_an_ancestor` | `HB-CMP-007` | an unrelated branch commit | real git | M-C12: only `cat-file -e` |
| C-13 `test_fix_names_exactly_the_differing_components` | `HB-CMP-007` for each | one edit, zero named; one edit, one named + one unchanged named | n/a | M-C13: allow a subset |
| C-14 `test_check_fix_refuses_a_wrong_before_hash` | `HB-CMP-007`; and `verify` replay fails on a hand-edited `before` | wrong `before` | real fold | M-C14: skip the before comparison |
| C-15 `test_fix_scope_is_computed_never_accepted` | scope `run`, `grade`, `both` for edits of `engine.py`, `grade/formal.py`, both; the parser has no `--scope` | n/a | real `identity.CLASSES` | M-C15: take scope from args |
| C-16 `test_fix_twice_is_one_row` | one row | n/a | n/a | M-C16: no-op removed |
| C-17 `test_power_role_comes_from_state` | `prior` in `baselined`, `final` in `piloted` | n/a | stub `power.analyse` + the real-wiring test X-INT-1 | M-C17: role accepted from args (baselined/piloted) |
| C-18 `test_power_crash_between_file_and_row_recovers` | after a forced failure in `_append`, the rerun leaves one row and one file | monkeypatch `_append` to raise once | real `create_once` | M-C18: delete the file on failure (loses the idempotency) |
| C-19 `test_power_float_or_invalid_inputs_refused` | `HB-PWR-001` naming the field | a float `alpha` | real `ledger.canonical` | M-C19: coerce floats |
| C-20 `test_pilot_attach_refuses_a_foreign_plan` | `HB-CMP-002` | plan with another campaign id | real `plan.json` | M-C20: skip the id check |
| C-21 `test_pilot_attach_refuses_non_pilot_ring` | `HB-CMP-002` | tag `comparison` | n/a | M-C21: accept any tag |
| C-22 `test_pilot_attach_is_idempotent_and_needs_a_plan` | no-op; missing plan refused | n/a | n/a | M-C22 |
| C-23 `test_pilot_pass_refuses_on_gate_items` | `HB-CMP-008` listing each item; no row | stub gate returning one item | X-INT-1 runs the real `gates.pilot` | M-C23: ignore the list |
| C-24 `test_pilot_gate_input_hash_changes_with_the_segment_heads` | two passes of one run differ in hash after a re-grade | n/a | **real segments** via `ledger.SegmentWriter` | M-C24: hash the run id only |
| C-25 `test_pilot_pass_refuses_an_unsealed_pass_and_an_unattached_run` | `HB-CMP-002` / `HB-CMP-008` | both | n/a | M-C25 |
| C-26 `test_admit_refuses_a_task_not_in_the_pilot` | `HB-CMP-002` | task `X9` | n/a | M-C26 |
| C-27 `test_admit_same_decision_noop_changed_decision_appends` | no-op, then a second row, latest wins | n/a | n/a | M-C27: always append |
| C-28 `test_register_preview_writes_nothing` | tree bytes identical, output has the hash | n/a | byte-compare of the whole campaign folder | M-C28: preview writes the prereg file |
| C-29 `test_register_confirm_writes_file_then_row` | `prereg/<h>.json` name = sha256, row names it | n/a | real `create_once` | M-C29: row before file |
| C-30 `test_register_refuses_each_unmet_precondition` | `HB-CMP-008` with its own copy | question differs; mde differs from final power; coverage cell missing; heads changed; local-path source; no current pilot | pilot plan from a real `plan.json`; power files real | M-C30 (one per case): remove each check |
| C-31 `test_register_same_hash_noop_other_hash_before_attach_appends` | no-op; second `registered` row; state `registered` | n/a | n/a | M-C31 (noop/append) |
| C-32 `test_prereg_with_a_local_path_source_is_refused_and_leaks_nothing` | refused; a manifest and prereg contain no `os.environ` value and no absolute path | `C:\Users\x\ai-forward` | n/a | M-C32: allow any string |
| C-33 `test_register_after_a_fix_waits_for_a_new_pilot` | `HB-CMP-008` `no current pilot`, then OK after `pilot pass` | n/a | n/a | M-C33 (F-4 pair) |
| C-34 `test_register_crash_between_file_and_row_recovers` | as C-18 | n/a | real `create_once` | M-C34 |
| C-35 `test_register_refused_once_a_grid_is_attached` | `HB-CMP-009` naming the run | after attach | n/a | M-C35: allow while no launch (the ADR wording; kills the W0 narrowing) |
| C-36 `test_attach_refuses_each_plan_mismatch` | `HB-CMP-010` with its own copy | other campaign id; prereg hash; **identity hash (F-1)**; arm commit; launched run | real `plan.json`, real `identity.side` | M-C36 (one per case) |
| C-37 `test_attach_identity_check_compares_with_the_chain_not_the_tree` | a plan whose identity equals the tree but not the chain is refused | tree drifted after the fix-free baseline, plan stamped from the tree | real manifest | M-C37: compare with the tree (the F-1 bug) |
| C-38 `test_verify_failure_exits_5` | exit code 5 via `main` | a broken chain | real `_exit_for` | M-C38: remove `HB-CMP-003` from the integrity prefixes (fails against today's `cli.py`) |
| C-39 `test_attach_is_idempotent` | one row | n/a | n/a | M-C39 |
| C-40 `test_attach_moves_registered_to_measuring_and_a_second_run_stays_measuring` | states | n/a | n/a | M-C40 |
| C-41 `test_attach_of_a_pilot_plan_as_a_grid_is_refused` | `HB-CMP-010` (`prereg_hash` null) | pilot plan | n/a | M-C41: role not checked |
| C-42 `test_conclude_refuses_a_live_run` | `HB-CMP-002` | a subprocess holds the run's `.lock` | **real cross-process lock** | M-C42: skip the check |
| C-43 `test_conclude_idempotent_and_only_from_measuring` | no-op / `HB-CMP-002` from `registered` | n/a | n/a | M-C43 (registered/measuring) |
| C-44 `test_abandon_same_reason_noop_other_reason_refused_terminal_refused` | as named | n/a | n/a | M-C44 |
| C-45 `test_state_guard_matrix` | for every (command, state) cell: expected ok or `HB-CMP-002` | all refused cells | CLI | M-C45 per command: widen the guard by the adjacent state (`register` from `baselined`, `attach` from `piloted`, `pilot pass` from `registered`) |
| C-46 `test_every_refusal_names_item_cause_action` | the message matches `^HB-[A-Z]+-\d{3}: .+\. .+\.$` and contains the item from the case table | all refusal cases of C-2..C-44 | CLI | M-C46: drop the action |

### E: eligibility (pure)

| id | assert / red today | red fixture | real wiring | mutant |
| --- | --- | --- | --- | --- |
| E-1 `test_eligible_when_every_rule_holds` | `eligible True, reasons ()` (skeleton returns `eligible False`) | n/a | `run_facts` on a real run dir (X-INT) | M-E1 |
| E-2 `test_each_rule_adds_its_reason` | seven cases, one reason each, fixed order | seven runs | n/a | one mutant per rule: drop it |
| E-3 `test_grade_side_is_compared_with_the_current_effective_not_the_baseline` | a pass under the baseline grade side, after a grade fix, is withheld | n/a | n/a | M-E3: compare with the baseline (current/baseline pair) |
| E-4 `test_run_side_fix_after_attach_makes_the_run_ineligible_grade_fix_does_not` | ineligible for scope `run`, eligible-but-withheld for `grade` | n/a | n/a | M-E4: any fix counts (run/grade pair) |
| E-5 `test_ordering_uses_seq_not_clocks` | with `recorded_at` skewed backwards, the verdict is unchanged | skewed stamps | n/a | M-E5: compare `recorded_at` |

### L, I: locks and interleavings

| id | assert / red today | red fixture | real wiring | mutant |
| --- | --- | --- | --- | --- |
| L-1 `test_acquire_then_probe_never_lets_both_proceed` | over 40 natural races and 20 barrier races (`between=Barrier.wait`): `not (a_proceeded and g_proceeded)`; and under the barrier every outcome is one-proceeded or both-refused (skeleton does not probe, so both proceed under the barrier) | n/a | **real `oslock` files, two OS processes** (spike S-C4 is this test) | M-L1: probe before taking the own lock (check-then-lock) |
| L-2 `test_a_command_is_refused_while_a_campaign_run_is_graded` | `HB-CMP-004`, campaign folder bytes unchanged, and the own lock is free afterwards | a subprocess holds `runs/R/grade.lock` | **real** lock, real CLI | M-L2: probe only the run argument, not the attach rows (L-6 pair) |
| L-3 `test_a_held_campaign_lock_refuses_with_hb_cmp_001` | exit 1 and the code | a subprocess holds `campaign.lock` | real lock | M-L3: block instead of try |
| L-4 `test_lock_released_on_every_path` | after an exception inside a command, `is_held` is false | forced exception | n/a | M-L4: release only on success |
| L-5 `test_lock_that_is_a_folder_or_link_is_refused` | `HB-CMP-003` naming it (today: raw `PermissionError`) | a folder named `campaign.lock`; a symlink where the OS allows (skip reason asserted to run in the POSIX job) | n/a | M-L5: no `lstat` |
| L-6 `test_probe_set_is_the_attached_runs_plus_the_argument_only` | an unrelated run's held `grade.lock` does not block; an attached one does | both | real locks | M-L6: probe every run under `runs/` |
| L-7 `test_the_grader_side_uses_the_same_helper` | `grade/runner.py` calls `oslock.acquire_then_probe` (AST) | a runner that probes by `is_held` then acquires | n/a | M-L7 |
| I-1 `test_register_then_attach_interleaving` | register(Y) wins the lock, attach(plan X) is refused `HB-CMP-010`; ledger `registered` = Y | n/a | threads, `session(wait_s)` and the `between` hook; real files | M-I1: attach reads the state before taking the lock |
| I-2 `test_attach_then_register_interleaving` | attach(plan X) wins; register(Y) refused `HB-CMP-009`; the run's plan hash equals the ledger's | n/a | same | M-I1 |
| I-3 `test_a_grid_launch_never_precedes_its_attach_row` | with a stub engine recording the order, the `grid.attached` row's `seq` exists before the stub's first launch | n/a | real `cmd_run` (P-3) | M-I3: skip `require_attached` |

### V, S, G: verify, sweep, ignore

| id | assert / red today | red fixture | real wiring | mutant |
| --- | --- | --- | --- | --- |
| V-1 `test_chain_break_is_named` | finding with line number | flipped byte | real file | M-V0 |
| V-2 `test_name_not_hash_is_named_for_identity_prereg_power` | one finding per folder | renamed file | n/a | M-V2: check one folder only |
| V-3 `test_modified_tracked_content_file_is_tampering` | finding names the path | edited committed `prereg/<h>.json` | **real git** | M-V3: ignore ` M` on content files |
| V-4 `test_ledger_uncommitted_append_ok_rewritten_prefix_refused` | passes after an append; finding after rewriting a committed line | both | **real git** (spike S-C3) | M-V4a: any ` M` refuses; M-V4b: ` M` always allowed (the prefix pair) |
| V-5 `test_untracked_new_content_file_is_allowed` | no finding | new `identity/<h>.json` | real git | M-V5 |
| V-6 `test_leaked_temp_is_a_named_warning_not_a_failure` | warning lists the name, exit 0 | temp file | real `atomic.is_temp_name` | M-V6: skip temps silently |
| V-7 `test_temp_folder_with_content_is_named` | warning names the folder | temp folder with a file | n/a | M-V7 |
| V-8 `test_not_a_work_tree_is_refused` | `HB-CMP-003` | tmp dir without git | real git | M-V8: pass |
| V-9 `test_discrimination_folder_tampering_is_named` | finding | deleted tracked record; renamed record | real git | M-V9 |
| V-10 `test_referenced_hash_missing_is_named` | finding | row names a missing prereg | n/a | M-V10 |
| S-1 `test_old_temp_is_swept_under_the_lock_and_logged` | the temp is gone; the sweep ran while `is_held(campaign.lock)` | aged temp (`os.utime`) | **real `atomic.sweep_temps`** | M-S1: sweep outside the lock |
| S-2 `test_young_temp_is_left` | still present, reported | fresh temp | n/a | M-S2: no age gate (S-1/S-2 pair) |
| S-3 `test_a_junction_inside_a_temp_is_not_followed` | the junction target survives | junction to a scratch dir | real sweep | M-S3: `rmtree` here |
| G-1 `test_gitignore_covers_every_temp_name_and_the_campaign_lock` | `git check-ignore` true for a temp file, a temp folder and its inner file under both trees and for `campaign.lock` (today: false, the lines are absent) | `x.json`, `campaign.lock.bak` must **not** be ignored | real `git check-ignore` | M-G1: delete one pattern |
| G-2 `test_a_fresh_clone_with_autocrlf_still_verifies` | state `baselined`, verify clean | clone with `core.autocrlf=true` | real git | M-G2 |

### P, B, T: plan, run, status, telemetry

| id | assert / red today | red fixture | real wiring | mutant |
| --- | --- | --- | --- | --- |
| P-1 `test_plan_with_campaign_stamps_the_chains_effective_run_side` | block `identity.hash == identity_hash(side(effective,"run"))`, not the tree's | after a recorded fix, tree == effective; both stamps differ from the baseline's | **real `cmd_plan`** (fails today: `--campaign` does not exist, argparse exit 2) | M-P1: stamp the tree |
| P-2 `test_plan_refuses_a_drifted_tree` | exit 1, `HB-CMP-002` naming `grade/formal.py changed` | edit without a fix | real manifest | M-P2: warn only |
| P-3 `test_bench_run_refuses_an_unattached_campaign_plan` | `HB-CMP-010`, and `preflight.check` was never called (today `cmd_run` ignores the block, so `preflight` is called) | pilot plan unattached; grid plan attached to nothing; grid plan whose registered hash moved | **real `cmd_run`**, fake only at `preflight.check` | M-P3: delete the line |
| P-3b `test_bench_run_accepts_a_pilot_plan_via_ring_run_attached` | `preflight.check` reached (W-3) | attached pilot | real | M-P3b: require `grid.attached` only |
| P-4 `test_a_plan_stamped_from_a_drifted_tree_is_refused_at_plan_time_at_attach_and_at_the_first_launch` | three refusals: `HB-CMP-002`, `HB-CMP-010`, then `HB-IDN-001` from the real engine | hand-built stamp from the tree | **real `bench run` with `identity_check=` wired**; fails if that keyword is removed from `cmd_run` (README floor item 3) | M-P4: drop `identity_check=` |
| P-5 `test_tree_edit_after_attach_stops_the_first_launch` | engine stops, no `cell.launch_intent`, exit 3 | edit a run-side file after attach | real engine with a fake launcher | M-P5 |
| B-1 `test_status_json_is_schema_bound` | `parse_status(to_json(x)) == x`; unknown field, wrong `state`, missing field rejected | three bad documents | real `parse_status` | M-B1: lenient parse |
| B-2 `test_status_json_carries_no_free_text` | `question` and every `reason` absent | a campaign with both | n/a | M-B2: include them |
| B-3 `test_status_next_token_follows_state` | one token per state | n/a | n/a | M-B3 (adjacent states) |
| T-1 `test_one_log_record_per_command_with_the_declared_fields` | record fields, `outcome`, `code` on refusal | refusal and success | real logger | M-T1 |
| T-2 `test_a_phase_that_did_not_run_is_absent_never_zero` | refused at probe: no `verify_ms` key | L-2 case | n/a | M-T2: default 0 |

### Cross-track joins (named here, owned jointly; fail if the partner is absent)

- X-INT-1 `test_full_walk_with_real_gates_power_and_readiness`: create to attach with the real `gates.pilot`, `power.analyse` and `readiness.hidden_test_disagreements` (partners of C-17, C-23).
- X-INT-2 `test_run_pass_of_a_campaign_run_is_refused_while_campaign_lock_is_held`: X-F's HB-GRD-007 with the real runner (partner of L-2; asserts both orders of the same helper).
- X-INT-3 `test_after_grading_hook_runs_after_grade_lock_is_released_and_degrades_to_not_verified`: SR-C2.

**Trace to W0 contracts (README testability trace).** W0 section 6 ledger kinds -> F-6, F-11; freeze order -> C-35, C-36, I-1, I-2, P-3; locks -> L-1..L-7; `.gitignore` -> G-1; content-addressed files -> C-4, C-29, V-2; identity API use -> C-4, C-10, P-1; section 4 `sweep_temps`, `is_temp_name` in `verify` -> S-1..S-3, V-6; section 13 `cmd_plan`, `identity_check=` -> P-1..P-5; ADR-0018 11(b) -> V-3..V-9.

## 14. Requests, decisions, open items

| id | to | content | provisional until |
| --- | --- | --- | --- |
| SR-C1 `req-01M41F6QRJ49VE2VES5Y527K61` | Coordinator | `oslock.py` gets `acquire_then_probe(own, own_code, other, other_code, between=None)`; assign `oslock.py` to X-C in E1 (it has no owner in W0 section 13); X-F consumes it | answer; fallback: this module keeps a private copy and X-F is told to call it |
| SR-C2 `req-01M41F6R2NR3JTJDA1JMX9V0KX` | Coordinator | W0 section 6 text fixes: (a) `admitted` int not bool (W-1); (b) lock test "at most one proceeds, never both" (W-2); (c) `bench run` accepts `ring_run.attached` for a pilot plan (W-3); (d) attach refusal code HB-CMP-010; (e) X-F's after-grading `verify` hook runs after `grade.lock` is released and calls `campaign.verify_for_plan` (section 6) | answer |
| OI-1 | W1-H / X-H2 | ADR-0017 section 5 ring-hash rule is not decidable from the ledger (no ring hash on `grid.attached`) | W1-H design |
| OI-2 | W1-H | the prereg body names no tasks or combos; coverage reads the final power inputs | W1-H design |
| OI-3 | W1-H | who computes admission saturation (EV-8)? W0 section 8 has no function; E1 records an operator decision | W1-H design |
| OI-4 | RV-SIM | `ring_run.attached.tag` is a constant in E1 | gate |

Spikes run (scratchpad, not committed; commands in section 15): S-C1 lock semantics and the folder-lock failure; S-C4 own-then-probe, 90 races; S-C3 git porcelain on campaign-shaped changes.

## 15. Evidence

| claim | evidence |
| --- | --- |
| bool refused by canonical | V `ledger.py:43` |
| same-process second acquire refused; cross-process acquire refused; a killed holder frees the lock; a folder lock raises `PermissionError` | V spike S-C1 (`spike_c1.py`, PYTHONPATH = the tree's `src`, Python 3.12.10) |
| never both proceed; both-refused occurs; probe makes the other's acquire fail briefly | V spike S-C4: forced overlap 30 runs `{one proceeded: 20, both refused: 10}`; natural 60 runs `{one proceeded: 54, both refused: 4, own-held: 2}` |
| porcelain: lock and temps invisible; ` M` on an appended ledger; `??` new files; ` D`; rename `R  a -> b`; HEAD prefix true for append, false for rewrite; no commit gives 128; not a repo gives 128 | V spike S-C3 |
| `.gitattributes` `* text=auto eol=lf` | V `.gitattributes:4` |
| error registry rejects unknown codes | V spike S-C1 first run (`errors.py:118`) |
| `_exit_for` integrity prefixes | V `cli.py:48-49` |
| `plan.confirm` writes `plan.json` with mode `x` | V `plan.py:357-366` |
| grading segments are `scores/<grading_id>.jsonl` and `events/<grading_id>.jsonl` | V `views.py:52-100` (`GRADE_PREFIX`, `segment_paths`) |
| spike E4 note is `status: accepted` | V `docs/notes/spike-e4-post-turn-prompt.md` frontmatter |
| B2 is the schema-bound campaign status | V `docs/architecture-evaluation-campaign.md:254, 302` |
| W0 rev 3 sections 4, 6, 13 re-read | V main `1ceea651` |

## Gate

`GATE w1-c-campaign-record · pending · RV-PAT, RV-SIM (soft), RV-TA (hard), RV-SEC (hard), RV-DS (hard)`

## Status

| | |
|---|---|
| **Completed** | the design above: data model, kinds, state table, every command's guard / idempotency / refusal / test, lock protocol with a measured safety claim, freeze order, F-1 checks at plan time and attach, verify with the git-prefix rule, eligibility, telemetry, test plan with mutants, three spikes |
| **Remaining** | the five lens gate lines; the author's follow-up applying findings; Coordinator answers to SR-C1 and SR-C2; W1-H answers to OI-1..OI-3 |
| **Best next action** | RV-TA and RV-DS review sections 5, 6 and 13; then X-C lands the skeleton and the red tests |
