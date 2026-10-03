---
id: review-eval-pat-w1j
title: "W1-J multi-turn: Patterns Expert lens review"
type: doc
status: draft
owner: "@timianmalloo"
links:
  - { to: design-eval-seam-contracts, rel: relates-to }
review-by: "2026-10-17"
summary: >-
  Adversary-mode review of docs/design/eval-multi-turn.md (branch design/eval-multi-turn, 6b838ff2) by the Patterns
  Expert lens: session protocol, the _attempt turn loop, the snapshot as a Memento, the turn-<n> archive layout,
  KEYS and the final-rows filter, the shared append_missing_rows helper (a seam disagreement with W1-B), and the
  check_models.py extension. RV-TA's findings are not repeated.
---

# W1-J multi-turn: Patterns Expert review (rv-pat-w1j-e1e4, 2026-10-03)

Read: the whole design (585 lines), W0 sections 4, 11, 12, 13 on main, W1-B (`design/eval-atomic-publish`) sections 1, 5, and RV-TA's table. Code opened in the review tree (main at 484b9a9a): `views.py:53-60, 150-166, 672-692`, `archive.py:27-90`, `engine.py:276-283`, `driver.py:286-300`; `git grep archive_files src` (the only row reader is `views.py:677`) and `git grep 'iterdir\|glob(\|rglob' src` filtered for archive paths (no reader outside the section 7 list sees `turn-<n>`).

## Pattern checks

| pattern asked | result |
| --- | --- |
| Driver open/send/close as a session protocol | Two of three. `open_session` and `send_turn` exist; there is no `close`. Close is the engine's `_end_process` in `finally`. See F1. |
| `_attempt` lifecycle | Structure kept (spawn, try, finally). Loop is sound except F2. |
| Turn snapshots as Memento | Not Memento; it is an archived checkpoint. See F4. Name is cosmetic; the design is right to avoid restore. |
| Archive layout `archive/<cell>/turn-<n>/ws/` | **Verified.** Sweep rerun: the five `attempt-*` globs are the whole set; no reader iterates `archive/<cell>/*`. `turn-1.tmp-*` is also outside every glob. |
| `views.KEYS` and final-rows filter | Sound, but the filter has no single definition. See F5. |
| Shared `append_missing_rows` (SR-J4) | **Seam disagreement with W1-B.** See F3. |
| `check_models.py` (Appendix A) | Table-driven structure bends. See F6. Grant scope is RV-TA 1's. |

## Findings

| # | location | finding | severity | evidence | fix | confidence |
| --- | --- | --- | --- | --- | --- | --- |
| F1 | s4.1 `Session`, s4.2 `finally` | The session has two owners. `Session` owns the `_Channel`, but the engine closes stdin through `_end_process`. `open_session` returns `None` and reports failure through a side channel (`result.cause`), and `send_turn` does the same. That is Optional-plus-out-parameter, not a protocol. A caller can forget the `None` check (the loop's `if session is None: break` sits inside the loop for that reason). | major | s4.1 signatures `-> Session \| None`, `-> TurnRecord \| None`; s4.2 `finally` "unchanged"; ADR-0015 s2a names open, send and close. | Give `Session` a `close()` (idempotent) that the engine's `finally` calls, so one object owns the channel from open to close. Check `session is None` once, before the loop. Keep the `None` returns if X-J1 wants the smaller change, but state them as the protocol's failure convention in the docstring and test `send_turn` after a failed `open_session`. | Verified (design text); the code shape is Inferred from s4.1 |
| F2 | s4.2 loop, s4.6, s11 T-ENG-6 | `cell.turn_ended` is recorded only after the break test `rec.stop_reason != "end_turn"`. A turn that ends with `max_tokens` or `refusal` gets no `turn_ended`, yet s4.2 says X-J2 derives "turn k not reached" by counting `turn_ended` events against the plan. A turn that ran and stopped on `max_tokens` would read as not reached, and the model action `TurnEnd` has no ledger line for it. The loop mixes two decisions: "this turn ended" (always record) and "continue" (only `end_turn`). | major | s4.2 code block: `if rec is None or rec.stop_reason != "end_turn" ... : break` precedes `self.record(... "cell.turn_ended" ...)`; s4.2 "Turns not reached". | Record `turn_ended` for every `TurnRecord` returned (any stop reason), then decide continue. T-ENG-6 adds the assertion: `turn_ended{1}` with `stop_reason == "max_tokens"` is present and `prompt_sent{2}` is absent. | Verified (design text) |
| F3 | s3 "crash windows", s13 SR-J4 | **Seam disagreement, W1-J vs W1-B, under W0 section 4.** W1-J says "the helper `archive.append_missing_rows(present, recomputed)` should be shared" and rates it "not blocking, to tell W1-B". W1-B section 5 specifies the recovery as `Recovery(result, missing_rows)` taking `recorded_rows`, with the W0 rule in two states only (rows absent, rows present). Neither names the partial-rows state W1-J adds, and W1-B never mentions `append_missing_rows`. Two designs describe one rule with two shapes, X-K1 builds the W1-B shape, X-J1 the W1-J shape: two helpers (DM7). Codes also differ: a differing present row is HB-LED-008 for a snapshot, HB-LED-005 for a final archive, for one defect shape. | major | W0 section 4 (the "if `final` exists and its rows are absent ... If ... present, verify only" paragraph); W1-B section 5 (`Recovery`, RV-PAT 4 advice); W1-J s3 and s13 SR-J4; `views.py:162` (`HB-LED-003` on a duplicate key) shows the partial-rows retry fails today. | Promote SR-J4 to a W0 section 4 amendment, owned by the Coordinator: the recovery rule gains the third state (rows partly present), and one pure function `missing_rows(recorded, recomputed) -> list[dict]` raises on a present row that differs. W1-B returns it inside `Recovery.missing_rows`; W1-J's `_snapshot_turn` calls the same function. State the one code mapping (005 for final, 008 for snapshot) in that amendment. | Verified (both texts opened) |
| F4 | s2 "Snapshot", s5 | The snapshot is a write-once, hash-sealed archived checkpoint with no restore. Memento's defining parts (an opaque state object handed back to the originator to restore it) are absent, and none is wanted. Calling it a Memento in the design or code invites a `restore` method nobody needs. The closer names are Checkpoint and Event-Sourced Commitment, which s5 already uses. | minor | s5 pattern table has no row for the snapshot as an object; s2 "append-only fact about that position". | Name it a "checkpoint (archived value object)" in s5, with one line that restore is a non-goal. | Verified |
| F5 | s2 D-J2, s7 row 7, T-VER-1 | "Final rows" is defined by absence of the `snapshot` key in prose, but W0 section 12 allows both `final` and absent. Each reader (`views.verify`, a future X-J2 or report reader) would re-spell the test. A reader that tests `r.get("snapshot") is None` rejects a W0-legal `"final"` row. The only `archive_files` row reader today is `views.py:677` (Verified), so the cost of one shared predicate is one call site. | minor | `views.py:677-681` filters by `cell_id` and `archive_attempt` only; W0 section 12 `archive_files` row: "`+ snapshot` ∈ {`turn-<n>`, `final`} (absent reads `final`)". | One predicate, `archive.snapshot_of(row) -> str` returning `"final"` when absent or `"final"`, used by `KEYS` readers and `verify`. T-VER adds a row written with `"snapshot": "final"`: same `archive_hash` as the bare row. Keep D-J2 (writer omits). | Verified |
| F6 | App. A, `check_models.py` | The diff bolts a second dispatch onto a table that already has one: `grading if bug in TWO_PASS else turns if bug in TURN_VARIANTS else small`, plus `TURN_VARIANTS` as a parallel set and a witness dict picked by `name in TURN_WITNESSES.values()`. A third bounds class repeats the pattern. The data belongs in the `VARIANTS` row, not in membership sets. RV-TA 1 covers whether the grant allows logic edits; this is about the shape of the edit. | minor | App. A hunks at `@@ -161` and `@@ -175`. | `VARIANTS[bug] = (kind, target, cfg_name)` with `cfg_name` default `small`; `TWO_PASS` and `TURN_VARIANTS` fold into it; the same for witnesses. The reverse MOD-A check then reads one table. If X-J1 prefers the smaller diff, record the nested-conditional as `simplify:` with the trigger "a third bounds class". | Verified (diff text) |
| F7 | s4.1 D-J5, s2 "derive don't store" | `TurnResult` holds the last turn's `stop_reason`, `usage`, `turn_seconds`, `last_update_seconds` and `turns: list[TurnRecord]`. The same quantities exist twice, and a writer can update one and not the other. The design's own rule is "derive, don't store". | minor | s4.1 "`TurnResult` stays the attempt-level record. Its `stop_reason` ... hold the last sent turn ... and `turns` holds every turn". | Make the four last-turn fields read-only properties over `turns[-1]`. `engine._classify` and the outcome row read the same names, so no caller changes. A test: after two turns the properties equal `turns[-1]`. | Inferred (needs `driver.py` dataclass text; the field list is from the design) |
| F8 | s4.2 `barrier_for(n)` | A closure factory per turn is fine (Strategy by function). The risk is that `barrier_for(1)` writes two records (`session_opened` then `prompt_sent{1}`) and `barrier_for(n>1)` one: two behaviours behind one name. | minor | s4.2 bullet 1. | Split: `record_session_opened(session_id)` called once after `open_session`, `barrier_for(n)` writes only `prompt_sent{n}`. The prompt-once barrier then has one meaning. The order `session_opened` before `prompt_sent{1}` stays, since `open_session` returns before the first `send_turn`; confirm that against the `before_send(session_id)` call at `driver.py:294`, which today runs after the handshake and passes the session id. | Verified (`driver.py:294`) |

## Seam disagreements (E2E-D)

1. **W1-J s3/SR-J4 vs W1-B s5, under W0 section 4:** the recovery helper has two names and two shapes, and only W1-J covers partial rows (F3). Needs a Coordinator ruling and a W0 section 4 line.
2. No other seam disagreement found. W0 section 11 (HB-LED-008, HB-CELL-117) and section 14 (the snapshot folder) agree with s2 and s3.

## Gate

Blocking: none. F1, F2 and F3 are the conditions (F3 needs the Coordinator, not the author).

GATE W1-J · Patterns Expert · PASS WITH CONDITIONS · 8 findings (rv-pat-w1j-e1e4, 2026-10-03)
