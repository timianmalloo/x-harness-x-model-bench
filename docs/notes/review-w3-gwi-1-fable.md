---
id: review-w3-gwi-1-fable
title: "W3-GW-I slice 1 cross-model security review"
type: decision-note
status: accepted
owner: "@timianmalloo"
links:
  - { to: coordination-finish-harness-bench, rel: relates-to }
review-by: "2026-10-09"
summary: >-
  Security Adversary review of W3-GW-I slice 1 at 371637e: CONDITION. No blocker; two Majors (the served-model
  check accepts an answer the pin never produced; the gateway lint is evaded by a local alias of the backend),
  five Minors, and the author's six findings ruled.
---

# W3-GW-I slice 1 — Security Adversary review

**Verdict: CONDITION** (PASS-WITH-CONDITIONS). Security & Identity Architect, Adversary Mode, T1; Claude Fable 5.1
on a different model from the Claude Opus 5.5 author (R-60 c3; Codex, the plan's cross-vendor reviewer, is at its
usage limit). Reviewed `git diff main...w3-gwi-1` at `371637e` (17 files, +1723) in the checkout
`C:\Projects\x-harness-x-model-bench-w3-gwi-1`, read by absolute path and not edited, against design
`phase3-gateway-judges.md` §7.1–7.4 and §9.1–9.3, US-35/46/47, R-58, R-60, R-63–R-66, and `egress.py`.

**Trust boundaries named.** (1) Cell artifact bytes → judge request (`request.render`, `scrub`): untrusted content
enters operator text. (2) Rendered request → backend (`pipeline._send` → `egress.check(...).release`): the only
outbound edge. (3) Backend stdout → verdict (`backend.read_reply`, `schema.validate`): a vendor's answer enters the
ledger. (4) `cache/verdicts` and `runs/` → a hit (`store.lookup`): a file the adversary can reach becomes a score.
Validation is on the trusted side at each: the scan runs over the whole rendered text after the scrub
(`pipeline.py:115`), egress before release (`pipeline.py:97-98`), the schema on the answer (`pipeline.py:141`), the
one §9.3 check on the store (`store.py:132-153`). `Result.__post_init__` (`pipeline.py:82-87`) makes a NOT_RECORDED
result structurally unable to carry a verdict, a key or an entry hash.

**Baseline.** In a throwaway `git worktree add --detach` at `371637e`: the five named test files plus
`tests/test_architecture.py` — 53 passed. No dependency changed (`pyproject.toml`, `uv.lock` untouched;
`hypothesis` and `pyyaml` are pre-existing, `pyproject.toml:9,:18`). No `socket`, `subprocess`, `urllib`, `http`,
`procs`, `popen` or `listen` reference in `src/harness_bench/gateway/` or `tests/test_gateway_*.py` outside
docstrings (grep, Verified). Operators and canaries in the tests are `token_hex` synthetics (R-42).

## Findings

| ID | Severity / confidence | Evidence · fix · disposition |
| --- | --- | --- |
| F1 — an answer the pin never produced is stored as its verdict | **Major / Verified** | `pipeline.py:143-145` accepts a reply when every served model is in `judge.allowed_models`; the pin's presence is not required. Probe (P1e): `allowed=("judge-model-a","aux-model-b")`, stdout `modelUsage={"aux-model-b":{}}` → outcome `stored`, entry `served_models=["aux-model-b"]`. Design §4.3 "never stored: any outcome other than a validated verdict set from the pinned served model" and `HB-GW-003` "served model not the pin" (`pipeline.py:33`) say otherwise; §8.3 step 2's wording ("the pin or a declared auxiliary") is the looser reading the code took — the design tension is itself a finding. The test floor is also thin: mutant P2 (`all(` → `any(` at `:144`) survived all 45 tests, so a reply served by the pin plus an undeclared model would pass too. **Fix:** `if judge.model not in served or not all(m in judge.allowed_models for m in served)` plus two negative tests (auxiliary-only; pin + undeclared). **Disposition: CONDITION for this join** (one line in the author's file, two tests), or by written rationale the first commit of s2 — the §8.3/§4.3 wording must be reconciled in writing either way. |
| F2 — the gateway lint is evaded by a local alias of the backend | **Major / Verified** | `tests/test_architecture.py:137-147`: a sink is a call whose root *name* is a non-data parameter; `root()` returns the alias. Probe (P4): appending `def _leak(backend: Backend, text: str): b = backend; return b.judge(text)` to `pipeline.py` — `test_architecture.py` 8 passed. The branch holds no such path (the only backend references are `_ask`/`_send`, `pipeline.py:90-98`; read, Verified) and T-GW-30 "withheld by egress" proves the runtime edge, so this does not block the join. But the lint is the *static* half of "any outbound payload bypasses `egress.check(...).release`" and it is the control Codex F2 asked for. **Fix:** taint local names assigned from a non-data parameter (as `tainted` already does for `self.<attr>`, `:140-142`). **Disposition: CONDITION for a later slice** — the owner of `test_architecture.py` (W3-EGRESS lineage), landed before s2 introduces the headless backend. Pairs with A6 below. |
| F3 — scan residuals not recorded in §7.3 | **Minor / Verified** | `scrub.py:50-64` normalizes NFKC and drops Cf; it does not fold confusables, strip combining marks, or allow separators inside a word. Probe (P1a), `scan(...)` returned `()` and `scrub` left the text unchanged for: Cyrillic `Cl\u0430ude`; letter-spaced `C l a u d e`; trailing combining acute `Claude\u0301` (NFKC composes it to `Claudé`, so the whole-word boundary moves); `Cla-ude`; `Cla**ude`. Controls fullwidth and mathematical-bold were caught. None is in T-GW-03's fragment set, so no named test catches them. Under ADR-0012:40 (surprising, not malicious) these are accepted residuals, but §7.3 lists none where `egress.py:14` lists its own. **Fix:** record them in §7.3 and the STRIDE "identity leaks" row; optionally strip `Mn` in `_normal` and allow `[\s*_-]?` between letters as `egress._word` does. **Disposition: later slice** (design note; owner W3-GW-I). |
| F4 — a wholly forged sealed ledger under a known root vouches for a planted entry | **Minor / Verified** | `ledger.py:65` `genesis = sha256("genesis:<segment_id>")`; the chain carries no secret, so any writer can produce a segment that "verifies from its genesis row". Probe (P1f): store an entry, then build its `verdict_uses`/`model_calls` segments and `record.jsonl` from scratch with `ledger.SegmentWriter` under `runs/` → `lookup` = `hit` (the pipeline test's own `_storing_ledger`, `test_gateway_pipeline.py:129-139`, does exactly this). The STRIDE row "planted or edited by a cell agent → mitigate → hash-chained storing row" overclaims: the chain proves a segment's integrity, not its authorship. Proportionate under ADR-0012's threat model (the adversary is not malicious), and T-GW-13's edited/forged-in-place cases hold. **Fix:** reword the disposition to *accept with rationale* (ADR-0012) with the residual named, or *transfer* to the wave-5 anchor (R-61) once anchors are recorded. No code change. **Disposition: later slice** (design). |
| F5 — the known-roots symlink guard has no negative test | **Minor / Verified** | `store.py:146-147` refuses `runs/<ledger_id>` unless `resolve().parent == r.resolve()`. Mutant P3 (guard dropped) survived all 45 tests; T-GW-13 "stored_by outside the known roots" uses `../`, which `_SAFE_ID` (`store.py:33,:143-145`) already refuses. The guard is defence in depth beyond `_SAFE_ID`, and its practical value is bounded by F4 (an adversary who can plant a junction in `runs/` can write the ledger directly). **Fix:** one junction test (`_winapi.CreateJunction`, no privilege on Windows; `os.symlink` elsewhere) → `HB-GW-005`. **Disposition: later slice** (s3, when the store is wired into grading). |
| F6 — `pipeline.run` can raise instead of returning a closed-set result | **Minor / Verified** | `egress.check` raises `ValueError` when the destination fails `DESTINATION` or scans as an operator identifier (`egress.py:252-253`). Probes: `Judge(model="Judge-Model-A")` → `ValueError` escapes `run` (P1d); `Operator(username="fable")` with destination `claude-fable-5-1` → `ValueError` (P1c; `_word` at `egress.py:200-205` matches the whole word `fable`). Fail-closed (nothing sent, no value in the message), but it breaks "every path is one (outcome, code)" (`pipeline.py:12`) and at s3 would abort a pass rather than write an NA row. Real collisions exist: usernames `sol`, `opus`, `fable` against `gpt-6-sol`, `claude-opus-5-5`, `claude-fable-5-1`. **Fix:** at s2, where `Judge` and the operator are wired, map a `ValueError` from `_send` to a NOT_RECORDED code (`HB-GW-001` or a new one) and validate `judge.model` against `DESTINATION` when the catalog is read. **Disposition: later slice** (s2). |
| F7 — `verify_entries` trusts a ledger row's `cache_key` as a path and a message | **Nit / Verified** | `store.py:170-174` builds `root / f"{ref['cache_key']}.json"` and echoes the key in the warning without `_SAFE_ID` (Codex F3's shape: content carried into a record). Read-only; the rows come from the operator's own ledger. **Fix:** `_SAFE_ID.fullmatch` before use. **Disposition: later slice** (verify wiring). |

**Withdrawn during review.** A first probe fed `denylist()` the matrix file as the plan and read "no model or combo
id in the real denylist"; the plan embeds the matrix under `"matrix"` (`plan.py:270`), and the re-run with a
plan-shaped input gave `cc-opus, claude-opus-5-5, codex-sol, copilot-sol, gpt-6-sol` plus the harness ids and
names and the three pack markers. `bench/prices.yaml` has `entries: []`, so today the plan's combos are the only
model-id source — as designed.

## The brief's adversary questions

- **Can an identifier reach a judge request past the scrub and scan?** Not by the forms the design names: whole
  word, any case, whitespace runs, Cf characters, NFKC compatibility forms — Verified by T-GW-03 and the fullwidth
  and math-bold controls. By confusables, combining marks and in-word separators: yes (F3), a recorded-residual
  class under ADR-0012, not a blocker.
- **Can any outbound payload bypass `egress.check(...).release(...)`?** Not in this branch: the one backend call is
  `_ask` inside `release` (`pipeline.py:90-98`); the author's "egress bypassed" mutant is killed by T-GW-30; the
  withheld path sends nothing (T-GW-30 "withheld by egress"). The static lint that would catch a *new* path can be
  evaded by an alias (F2).
- **Can a store entry be overwritten, or a planted or orphaned entry accepted as a hit?** Overwrite: no —
  `os.link` write-once (`store.py:84`), the loser reads the winner (T-GW-11), the entry is read-only (`:94`).
  Planted under an existing verifying ledger with no row: `HB-GW-005` (T-GW-13, T-GW-30 "planted entry").
  Orphaned: never a hit unless this run's own sealed row matches key and hash (`store.py:151-152`, T-GW-13); moved
  aside before a fresh call (`pipeline.py:128-129`). Residual: F4.
- **Does a down or failing backend ever yield a score?** No. `BackendDown` → `HB-GW-001`, a withheld verdict →
  `HB-GW-009`, unreadable stdout or a bad shape → `HB-GW-002` (`pipeline.py:130-142`); T-GW-30 asserts `verdicts
  is None` on every failed path, and `Result.__post_init__` refuses a failed result that carries one. A backend
  raising anything other than `BackendDown` escapes `run` — s2's CLI backend must map every failure to `BackendDown`
  (same class as F6).
- **Does any Result, log or error carry a scanned value?** No. `Result` holds outcome, code, hashes, the validated
  verdicts and catalog paths (`pipeline.py:73-80`); the store entry holds hashes, model ids, `stored_by`, a session
  id and verdicts (`:146-152`) — no operator identifier, no secret; `egress.Verdict.payload` is `None` on a hit
  (`egress.py:257`). `schema.validate` puts a rejected `score` value into a message (`schema.py:34`), which the
  pipeline discards.
- **Network, listener, subprocess, real identifier?** None (grep above). `ReplayBackend` is a dict lookup
  (`backend.py:31-44`).

## The author's six findings

| # | Finding | Ruling | Disposition |
| --- | --- | --- | --- |
| A1 | `HB-GRD-003` reused for the live-run refusal while `errors.RUN_CODES:66` defines it as grader failure | Concur: one code, two meanings breaks the stable-error-code rule; s4 takes a new code and design §6/§17 are amended | Later slice (s4) |
| A2 | `HB-GW-001..011` live in `pipeline.CODES` (`pipeline.py:29-42`), not `errors.RUN_CODES` (STOP-I owns `errors.py`) | Two registries of one quantity; not a security defect. When the seam is granted, T-GW-30's `set(pipeline.CODES) == {...}` (`test_gateway_pipeline.py:177`) becomes an equality against `RUN_CODES`'s `HB-GW-` subset, so a drift fails | Later slice (seam to STOP-I; before s3's `verdict_uses` rows are read by verify/report) |
| A3 | `.gitignore` lacks `cache/` (design §4.3); the ADR-0006 amendment is owed | `.gitignore`: the store holds no secret or identifier (above), so the exposure is a generated artifact reaching the public origin (R-42), not PII — one line. ADR-0006: Data & Persistence's lane, with the `verdict_uses` fact | `.gitignore`: **CONDITION for this join** (Leader, at the join commit). ADR-0006: later slice (s3) |
| A4 | `bench/gateway.yaml` not created | s2 owns it; slice 1 stipulates the model through `Judge.model` | No action |
| A5 | `backend.read_reply` reads only Claude `--output-format json` stdout (`backend.py:47-62`) | The served-model check rests on the CLI's self-report (`modelUsage`); §8.3 step 2 requires the record. A Copilot/Codex stdout returns `None` → `HB-GW-002` today (fail-closed, Verified by reading). Ties to F1 | Later slice (s2: served models and tool events from the native record) |
| A6 | The architecture lint's false positive on methods of non-data parameters (worked around by the `rubric = inputs.rubric` alias, `pipeline.py:112`) | Fail-closed, so no action for the join. The same name-based `params` rule is both over-strict (this) and evadable (F2): one fix — taint-track names, and treat method calls on the gateway's own frozen dataclasses (`Inputs`, `Judge`, `Context`) as data | Later slice (with F2) |

## Bypass attempts (each in a throwaway `git worktree add --detach 371637e`, removed afterwards)

| # | Attempt | Named tests run | Result |
| --- | --- | --- | --- |
| P2 | Mutant `pipeline.py:144` `all(` → `any(` (a reply served by the pin plus an undeclared model passes) | the five named files | **Not caught** — 45 passed (F1) |
| P3 | Mutant `store.py:147` drop `.resolve().parent == r.resolve()` (a junction inside `runs/` is followed) | the five named files | **Not caught** — 45 passed (F5) |
| P1 | Bypass inputs, no mutant: (a) five scrub forms above; (e) auxiliary-only served reply; (f) from-scratch sealed ledger; (c)(d) destination `ValueError`s | the five named files (green, 45) + a probe script | **Not caught** — scan `()` for all five forms (F3); `stored` (F1); `hit` (F4); `ValueError` escapes (F6) |
| P4 (extra) | Lint evasion: an unreleased `b = backend; b.judge(text)` appended to `pipeline.py` | `tests/test_architecture.py` | **Not caught** — 8 passed (F2) |

The author's 45 mutants (`tests/mutations/gateway.json`) are all named and all killed; mine target the seams
between them. A clean run of the named tests is a floor, not a verdict.

## Veto and residual risk

**CLEARS-THE-VETO: yes** — boundaries named; boundary input validated on the trusted side; no secret or
identifier in source, logs, results or the store; no dependency change, so no CVE, licence or provenance question;
least privilege (offline, no process, no socket, read-only entries). No Blocker in my domain; the two Majors carry
the conditions above and neither is on a shipped live path (slice 1 ships the replay backend only).

**Residual risk left open:** confusable and combining-mark forms of a family word reach the judge (F3); a forged
ledger under `runs/` vouches for a planted entry (F4, unkeyed chain); the served-model fact is the CLI's own report
until s2 reads the record (A5); the lint's alias gap until it is fixed (F2); what the CLI adds after `release`
(account e-mail, skill root) is DR-GW-5's ruling, not this slice's.

Handoff: no PII change in this slice; Privacy & Data Governance is not convened. Data & Persistence owns the
ADR-0006 amendment (A3).
