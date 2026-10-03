---
id: brief-eval-x-i-s2
title: "Brief X-I-S2: the second security task S2 on bottle (E4) - spike and authoring now, ready after X-F and the 0.7 freeze"
type: plan
status: proposed
owner: "@timianmalloo"
links:
  - { to: coordination-eval-wave2-e234-briefs, rel: implements }
  - { to: design-eval-seam-contracts, rel: depends-on }
review-by: "2026-10-17"
summary: "X-I-S2 runs the S2 spike W1-I section 12 requires (prompt, latent requirement, probes each proven live, the pickle-cookie rules), records it for RV-SEC and RV-TA, then authors tasks/S2 to draft on Claude Sonnet; ready after X-F joins and catalog 0.7 is frozen."
---

# X-I-S2: security task S2

**Harness** Claude Code sub-agent · `model: sonnet` (served `claude-sonnet-5-5`, R-91) · **session** `x-is2-e1e4` · **branch** `build/eval-x-i-s2` · **budget** as X-I: 200 calls · 200k · 2 sessions + 1 follow-on · 3 h · **skill** `/new-bench-task`.

**Design:** W1-I `docs/design/eval-security-tasks.md` §12 (S2: base `bottlepy/bottle` @ `cbd569c4…`, signed-cookie session, team tenancy, five probe classes, canary `BENCHCANARY-S2-<hex>`) and *Erratum 1* (X-I's measured corrections); `docs/coordination/eval-wave2-e1/x-i.md` (S1's acceptance items, which S2 meets in kind); W0 rev 6.6 §1-§3.

## Owned paths
`tasks/S2/**`, the `S2` entry of `bench/bom.yaml`, `docs/notes/spike-s2-security.md` (new: the spike's record). Not yours: any `src/` file.

## Step 1: the S2 spike (W1-I §12 "Open before X-I authors S2")
1. Prompt, latent requirement, evidence paths, and payload lists **each proven live by a defect variant** (§5.5's method), expected values with provenance, and bounds from the S2 reference's measured duration.
2. **Pickle-cookie rules (RV-SEC 2, major):** (a) the check gets a valid cookie only through the app's own login route or an HMAC re-implemented in the check, **never by importing bottle**; (b) forged-cookie probes send inert bytes, never a pickle gadget; (c) a defect variant where the secret leaks and a forged cookie is accepted. Re-read `bottle.py:2978` and `:1803` at the pin and mark them Verified.
3. Commit the note and stop for review: **RV-SEC (hard veto) and RV-TA** review the note before step 2. The Leader routes the reviews. This is the gate that W1-I §12 left open.

## Step 2: authoring to `draft` (after both reviews pass)
S1's acceptance items 1-6 and 9-10 (`x-i.md`), in kind for S2: EV-1 contract, the full-commit pin, `NOTICE.md` and licence, case ids to W0's charset, variant names to `^[a-z0-9]{1,16}$`, `variants.py` as data, `clauses.json`, the `ready` order. S2's hidden tests run only the new file (363 upstream tests, 6 fail under `-S`; no PASS_TO_PASS claimed).

## Step 3: the `ready` follow-on
After X-F has joined and catalog 0.7 is frozen (W1-I §4 E4): the reference passes every probe and the naive fails at least one, through X-F's real grader; expected values confirmed or corrected with provenance (GLD-A); the record under W0's `ready` order.

## Exit
E1 README §3 join gate per step. Report per E1 README §4.
