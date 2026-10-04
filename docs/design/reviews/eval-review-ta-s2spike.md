---
id: review-eval-ta-s2spike
title: "Test Architect review of the redesigned S2 spike (R-99) (Adversary Mode)"
type: doc
status: draft
owner: "@timianmalloo"
tags: [review, test-architect, evaluation-campaign, s2, r99]
links:
  - { to: design-eval-seam-contracts, rel: relates-to }
  - { to: review-eval-ta, rel: refines }
review-by: "2026-10-17"
summary: >-
  Test Architect gate on the S2 spike (build/eval-x-i-s2b, 12f828df). The diagonal reproduces and is real for four
  probes; the tamper probe is live for one input shape only, and two probes pass vacuously on a wrong app. PASS WITH
  CONDITIONS, 6 findings.
---

# Test Architect review of the S2 spike (rv-s2-e1e4)

PERSONA: test-architect · MODE: Adversary · TIER: T2. Severity: blocking / major / minor. Confidence: Verified (observed) / Inferred (reasoned; the confirming check is named).

## S2-SPIKE: `docs/notes/spike-s2-bottle-r99.md`, `tools/spikes/s2_apps.py`, `tools/spikes/s2_probes.py` (branch `build/eval-x-i-s2b`, 12f828df)

### Are the numbers measured?

Verified. I cloned bottle at `cbd569c447b3fd53f194cef9a306146ce6a07a59` and ran `python s2_probes.py <clone>` from `tools/spikes/`, and again with `python -S`. Output matches the note: reference all pass; all-naive all fail; each single-defect variant fails its own probe and passes the other four. The reference and naive outcomes are **measured, with the command shown in the note**. The timings are one run each, and the note already marks bounds as Inferred. Not measured: repeat-run stability; any app other than the author's own.

### Is the diagonal real evidence that each probe is live?

Partly. A single-defect flip proves a probe can fail, which is the necessary half. It proves less than the note says:

- It shows the probe responds to the defect the author wrote. Each defect is the author's own flag in the same app, written beside the probe. It is not an independent solution (finding 3).
- The tamper probe is live for one input shape only (finding 1).
- Two probes (sqli, leak) pass on an app that does nothing (finding 2). A probe that cannot fail on a wrong app is live for the planted defect and dead for the class.

### Findings

| # | location | finding | severity | evidence | fix | confidence |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | `s2_probes.py:70` tamper | The flipped-cookie input is dead. The flip lands on the closing quote of the issued value; the cookie parser then returns an empty jar, so the input behaves as "no cookie". Of the six cookie inputs, none carries the signed shape with a wrong signature. The diagonal flips tamper only because the naive trusts a plain `session=<user>`. A naive that accepts the signed shape without verifying is not caught. Changing a character inside the message body gave 401 on the reference, so the live input is easy to build. | major | Experiment: `dict(SimpleCookie(flipped)) == {}`; the body-change input parsed and was refused. | Make the flip inside the body (and one in the signature region); add the variant "signed shape, signature unchecked" and require it to flip tamper to false while the other four stay true. | Verified |
| 2 | `s2_probes.py` sqli, leak | No positive control. sqli passes on `status < 500` and absence of `B-task`; leak passes on absence of the canary. Against a stub app that returns 404 for everything (login patched to return a value), the result was `sqli True, trav False, authz False, leak True, tamper False`. A wrong app, a crashed app or a renamed route passes two of five probes. When login fails, `run()` raises `TypeError` instead of recording a result (`a[-1]` on `None`). | major | Re-run with the stub; traceback without the patch. | Add per-probe positive controls: alice `GET /tasks` is 200 and contains `A-task-*`; the leak paths return the status class the fixture expects; a login failure is a recorded `broken` outcome, never a crash or a pass. A probe that cannot find its target returns `inconclusive`, scored as not passed. | Verified |
| 3 | note "Measured results" | Reference and naive are one app with flags, authored by the person who wrote the probes; one defect shape per class (the note's limit 1). Independent shapes are untested. For sqli only the union form looks effective on the naive (the quote-tautology input yields no extra row because of the clause precedence). Mutation-testing the probe file (`tools/mutate_check.py`) is not run. | major | `s2_apps.py` defect branches; `s2_probes.py:46-48`. | S2 task: at least two defect shapes per class, one written by a different author or model; a mutation run over the probe file with survivors listed. | Verified (structure) · Inferred (payload effect; confirm by running that input against the sqli naive alone) |
| 4 | authz probe | The state mutation (`DELETE /tasks/3`) makes probes order-dependent, and the id is a fixture literal. A re-run on the same workspace sees the deleted row. | minor | `s2_probes.py:56-60`. | Fresh seeded database per probe, or authz last; resolve ids from the API; record in the readiness record. | Verified |
| 5 | note timings | One run per variant; the reference figure includes first-import cost; the note says "not bounds". No budget is derived from them, which is correct. | minor | Note, "Measured results". | Measure N runs per cell in the S2 readiness record before any timeout is set. | Verified |
| 6 | note "Verdict on the R-99 fallback" | "Option (a) holds" is supported for four classes and for the plain-cookie shape of the fifth. It is not yet supported where the solution signs its own session (the note's limit 3), the common shape a model will write. A black-box probe separates a verified custom signature from an unchecked one only with a body-change input. | minor | Note, limit 3. | After finding 1, add a naive that signs with its own scheme but does not check, and a reference that checks; confirm the body-change input separates them. | Inferred (confirm by building both and running the diagonal) |

### What S2 authoring must add

1. **Wrong-app fixtures, each scored not-passed:** all-404 app; app that always returns 401; app that always returns 200 with fixed JSON; app on different routes; app with other task ids; app that crashes at start; a login that fails. The expected outcome per probe is recorded (fail or inconclusive); a probe that returns pass on one of these is a defect in the probe.
2. **Variant flips, committed as a test:** the expected matrix (reference all pass; all-naive all fail; each single defect fails exactly its own probe), at least two defect shapes per class including the signed-shape-unchecked tamper variant, in the continuous ring. One-time proofs (the mutation run over the probe file) stay out of the ring.
3. **The readiness record, per probe:** positive-control result; the variant it flips; the wrong-app rows; the transport measured (in-process versus the probe host); repeat-run count and time; the fresh-database step; what is unmeasured (logs, harder variants).
4. **Gates from R-99 condition 3:** the import scan reddens a fixture check that imports `pickle`; `pickle` and `cPickle` are in the argv and word denylist.

### Conditions

1. Fix findings 1 and 2 and re-run the full matrix before probe ids are fixed.
2. Findings 3 to 6 land as items in the S2 task authoring checklist above.

GATE S2-SPIKE · Test Architect · PASS WITH CONDITIONS · 6 findings (rv-s2-e1e4, 2026-10-03)
