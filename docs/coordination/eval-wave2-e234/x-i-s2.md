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
summary: "X-I-S2 runs the S2 spike W1-I section 12 requires (prompt, latent requirement, probes each proven live, the session rules as amended by R-99: login route only, no bottle or pickle import, inert bytes only, tamper-refusal in place of forged-session), records it for RV-SEC and RV-TA, then authors tasks/S2 to draft on Claude Sonnet; ready after X-F joins and catalog 0.7 is frozen."
---

# X-I-S2: security task S2

**Harness** Claude Code sub-agent · `model: sonnet` (served `claude-sonnet-5-5`, R-91) · **session** `x-is2-e1e4` · **branch** `build/eval-x-i-s2` · **budget** as X-I: 200 calls · 200k · 2 sessions + 1 follow-on · 3 h · **skill** `/new-bench-task`.

**Design:** W1-I `docs/design/eval-security-tasks.md` §12 (S2: base `bottlepy/bottle` @ `cbd569c4…`, signed-cookie session, team tenancy, five probe classes, canary `BENCHCANARY-S2-<hex>`) and *Erratum 1* (X-I's measured corrections); `docs/coordination/eval-wave2-e1/x-i.md` (S1's acceptance items, which S2 meets in kind); W0 rev 6.6 §1-§3.

## Owned paths
`tasks/S2/**`, the `S2` entry of `bench/bom.yaml`, `docs/notes/spike-s2-security.md` (new: the spike's record). Not yours: any `src/` file.

## Step 1: the S2 spike (W1-I §12 "Open before X-I authors S2")
1. Prompt, latent requirement, evidence paths, and payload lists **each proven live by a defect variant** (§5.5's method), expected values with provenance, and bounds from the S2 reference's measured duration.
2. **Session rules (RV-SEC 2, major; amended by R-99, DR-S2, which wins over W1-I §12 item 2 until X-I's Erratum 2 lands):**
   (a) **A valid session comes only from the app's own login route.** W1-I §12 item 2(a)'s alternative, an HMAC re-implemented in the check, is **withdrawn**: re-implementing `cookie_encode` reconstructs a sign-a-pickle procedure.
   (b) **The check never imports `bottle` or `pickle`.** Extend S1's §5.9 no-build/import test for S2 so `check.py` importing `pickle` reddens (beside the existing `socket`/`subprocess`/`urllib`/`http` set), and add `pickle`/`cPickle` to the argv/word denylist; red first on a fixture check that imports `pickle`.
   (c) **Probes send inert bytes only.** Every session probe sends unsigned or wrong-signature plaintext; no payload, variant, reference, naive solution or check constructs a pickle gadget or a validly-signed (forged) cookie, and no probe demonstrates code execution. The signature check at `bottle.py:1190` precedes `pickle.loads`, so the host never unpickles attacker bytes.
   (d) **Tamper-refusal replaces forged-session.** S2's probe classes are injection (SQL), path traversal, authorization bypass (cross-team), secret non-disclosure (the `BENCHCANARY-S2-<hex>` signing secret never appears in a response, log or error; an inert scan run for both teams) and tamper-refusal (the app rejects an unsigned or mis-signed session cookie). The defect variant of W1-I §12 item 2(c) is realised as the naive accepting inert unsigned or tampered bytes; each probe is proven live by a defect variant (§5.5).
   (e) **The leaked-secret consequence is prose only:** "a leaked secret is code execution on unpickle" goes in `evidence.md` and the spike note as the reason the class is high-impact; it is never demonstrated or constructed.
   (f) **Fallback (R-99 condition 7):** if the spike shows these probes cannot separate a secure from an insecure solution without touching deserialization, stop and report it; a different base or a non-pickle session is a new Owner request. Dropping S2 is not available to you.
   `bottle.py:2978`, `:1190` and `:1803` are Verified at the pin (`docs/notes/spike-s2-bottle-cookie-reads.md`); cite them, do not re-derive them. W1-I §12 *Erratum 2* (citing R-99) is X-I's to write, in the commit that supersedes the stopped spike note.
3. Commit the note and stop for review: **RV-SEC (hard veto) and RV-TA** review the note before step 2. The Leader routes the reviews. This is the gate that W1-I §12 left open.

## Step 1b: the review conditions (both reviews PASS WITH CONDITIONS, merged `e2af2692`; Coordinator #14b)

The spike (`18bdce7e`: `docs/notes/spike-s2-bottle-r99.md`, `tools/spikes/s2_apps.py`, `tools/spikes/s2_probes.py`) passed RV-SEC (`docs/design/reviews/eval-review-sec-s2spike.md`) and RV-TA (`docs/design/reviews/eval-review-ta-s2spike.md`), each with conditions. They are acceptance items here, and the authoring session does them **first**.

**Authoring session** `x-is2c-e1e4` · **branch** `build/eval-x-i-s2c` (a new tree from `main`; the spike ran as `build/eval-x-i-s2b`) · `model: sonnet` · **budget** 150 calls · 200k tokens · 1 session · 3 h. **Owned paths, added to those above:** `tools/spikes/s2_apps.py`, `tools/spikes/s2_probes.py`, `docs/notes/spike-s2-bottle-r99.md` (the spike's actual note; `spike-s2-security.md` above is not used). **Depends on:** `e2af2692` on `main` (`git merge-base --is-ancestor e2af2692 main`).

**C. Before any probe id is fixed: fix the spike and re-run the full matrix** (condition 1 of both reviews).
- **C1. Tamper reaches the signature check** (SEC 1, TA 1; major). The flip at `s2_probes.py:70` lands on the closing quote, so the parsed jar is empty (`dict(SimpleCookie(flipped)) == {}`). Replace it with two inputs: one byte changed inside the base64 message body, and one inside the signature region. Both are inert under R-99, because the signature check precedes the loader. Add the naive variant "signed shape, signature unchecked". It must flip tamper to false while the other four probes stay true.
- **C2. A custom-signing pair** (TA 6). Add a naive that signs with its own scheme but never checks the signature, and a reference that does check it. Show that the body-change input separates them.
- **C3. The leak scan reads errors and logs** (SEC 2; major). Scan the captured error stream (`wsgi.errors`, the host's stderr) and any log file under the workspace (S1's pattern, `tasks/S1/oracle/check/check.py:146-162`). Add the base64 and URL-encoded forms of the canary. Plant the canary per run, not as a constant in two files.
- **C4. Positive controls** (TA 2; major). Each probe first shows that its target exists: alice's `GET /tasks` is 200 and contains `A-task-*`, and each leak path returns the status class the fixture expects. A target that is not found gives `inconclusive`, which scores as not passed. A failed login is a recorded `broken` outcome, never a crash (today `a[-1]` on `None` raises `TypeError`) and never a pass.
- **C5.** Re-run the whole diagonal (reference, all-naive, each single defect, the new variants, and an all-404 app). Update the spike note's table with the commands. Commit the note before step 2 begins.

**A. Authoring checklist** (condition 2 of both reviews: findings 3 to 6, each a named step in step 2):
- **A1. Authz** (SEC 3, TA 4). Run it last, on a fresh copy of the seeded database. Resolve team 2's id from bob's own `GET /tasks`, never a literal `3`. Record the reset in the readiness record.
- **A2. Transport** (SEC 4). No `urllib`: keep it in the denylist and reuse S1's hand-written `quote` (`tasks/S1/oracle/check/check.py:21-23`). Re-measure the four traversal encodings over the real probe-host transport before the probe ids are fixed. The spike measured them in-process only.
- **A3. Supply chain** (SEC 5). Record the SHA-256 of `bottle.py` and of `LICENSE` in the task manifest, ship the licence text with the base, and record the upstream URL. Record that the pin is an untagged dev commit (`0.14-dev`).
- **A4. The check is an out-of-process client, as S1's is** (SEC 6; R-99 condition 3). The source scan covers `pickle`, `cPickle`, `bottle`, dynamic-import calls (`__import__`, `importlib`) and the existing network set. Red first, on a fixture check that imports `pickle`. `pickle` and `cPickle` go in the argv and word denylist (TA authoring 4).
- **A5. Wrong-app fixtures, each scored not passed** (TA authoring 1): an all-404 app; an app that always returns 401; an app that always returns 200 with fixed JSON; an app on different routes; an app with other task ids; an app that crashes at start; a failing login. Record the expected outcome per probe (fail or inconclusive). A probe that passes on one of them is a defect in the probe.
- **A6. The variant matrix is a committed test in the continuous ring** (TA 3, TA authoring 2): the reference passes all; the all-naive fails all; each single defect fails exactly its own probe. Use at least two defect shapes per class, including the signed-shape-unchecked tamper variant. One shape per class is written by a different author or model; the report says who wrote it, or reports the item as not met. A one-time `uv run python tools/mutate_check.py` run over the probe file lists its survivors and stays out of the ring.
- **A7. The readiness record, per probe** (TA authoring 3, TA 5): the positive-control result; the variant it flips; the wrong-app rows; the transport measured (in-process or probe host); N repeat runs per cell with their times, taken before any timeout is set; the fresh-database step; what is unmeasured.
- **A8. `evidence.md`** (SEC condition 3; R-99 condition 4) carries, in prose only, the consequence of a leaked signing secret. It also carries RV-SEC's unmeasured set: logs and stderr if not scanned, encoded or partial secret forms, a path the probe does not visit, another method or content type, a hidden or time-dependent trigger, and the secret left in a file under the workspace.
- **A9. Portable text I/O** (HYG-VERIFY, `docs/coordination/eval-wave2-e1/hyg-verify.md`). `python docs/ai-forward-pack/scripts/verify-portable-text-io.py` reports no finding in `tools/spikes/s2_*.py`. Measured on `main` at `fec54563`: `s2_apps.py:22` and `:24` (`open(..., "w")` without `newline="\n"`), and `s2_probes.py:1` (no stdio guard). These three are yours, not HYG-VERIFY's.

## Step 2: authoring to `draft` (after both reviews pass and step 1b's C items are committed)
S1's acceptance items 1-6 and 9-10 (`x-i.md`), in kind for S2: EV-1 contract, the full-commit pin, `NOTICE.md` and licence, case ids to W0's charset, variant names to `^[a-z0-9]{1,16}$`, `variants.py` as data, `clauses.json`, the `ready` order. S2's hidden tests run only the new file (363 upstream tests, 6 fail under `-S`; no PASS_TO_PASS claimed).

## Step 3: the `ready` follow-on
After X-F has joined and catalog 0.7 is frozen (W1-I §4 E4): the reference passes every probe and the naive fails at least one, through X-F's real grader; expected values confirmed or corrected with provenance (GLD-A); the record under W0's `ready` order.

## Exit
E1 README §3 join gate per step. Report per E1 README §4.
