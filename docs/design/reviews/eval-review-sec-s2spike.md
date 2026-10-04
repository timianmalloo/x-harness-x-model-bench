---
id: review-eval-sec-s2spike
title: "Security & Identity review of the redesigned S2 spike (R-99) (Adversary Mode)"
type: doc
status: draft
owner: "@timianmalloo"
tags: [review, security, evaluation-campaign, s2, r99]
links:
  - { to: design-eval-seam-contracts, rel: relates-to }
  - { to: review-eval-sec, rel: refines }
review-by: "2026-10-17"
summary: >-
  Security & Identity gate on the S2 spike under R-99 (build/eval-x-i-s2b, 12f828df). The letter of R-99 holds; the
  tamper-refusal probe never reaches bottle's signature check, the leak probe does not scan logs, and the pin lacks a
  content hash. PASS WITH CONDITIONS, 6 findings.
---

# Security & Identity review of the S2 spike (rv-s2-e1e4)

PERSONA: security-identity-architect · MODE: Adversary · TIER: T2. Severity: blocking / major / minor. Confidence: Verified (observed) / Inferred (reasoned; the confirming check is named). No deserialization payload is built or described here; where one would matter it is described abstractly only.

## S2-SPIKE: `docs/notes/spike-s2-bottle-r99.md`, `tools/spikes/s2_apps.py`, `tools/spikes/s2_probes.py` (branch `build/eval-x-i-s2b`, 12f828df)

Method: read all three files; fetched bottle at the pin into a scratch directory and read `bottle.py`; re-ran `python s2_probes.py <clone>` (and with `-S`) and reproduced the note's table exactly; ran two small inert experiments on the cookie jar (below).

### R-99 compliance

| R-99 condition | result | evidence |
| --- | --- | --- |
| probes never touch the deserialization path | holds | `get_cookie` verifies the HMAC (`bottle.py:1186-1191`) and only then calls the loader. No probe input can reach the loader. Valid sessions replay only the app's own `Set-Cookie`. |
| inert bytes only, nothing forged or signed | holds | The cookie list is plain names, a `name:team` string, base64-looking text, an empty value, none, and one app-issued value with its last character changed. No signing code exists in the probe file. |
| sessions only via the login route | holds | `login()` posts to `/login` and returns the `Set-Cookie` pair untouched (`s2_probes.py:38-41`). |
| check never imports bottle or pickle | holds by source (Verified: probe imports are `io json os sys time urllib.parse`) | At runtime the process does import bottle, because `create_app` does. R-99's rule is a source-level rule; the real check must prove it by the static import scan (finding 6). |

Verdict on spirit: yes, with finding 1. The one input derived from signed material is the flipped cookie. R-99 condition 2 allows wrong-signature bytes, and the signature check precedes the loader, so the flip is in scope. It is also the only input meant to exercise the verify step, and it does not (finding 1).

### Findings

| # | location | finding | severity | evidence | fix | confidence |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | `s2_probes.py:70` `flipped = a[:-1] + ...` | Tamper-refusal never reaches the signature check. The issued value is quoted (`session="!<sig>?<msg>=="`); the last character is the closing quote. Changing it leaves an unterminated quote, and the cookie parser returns an empty jar (`dict(SimpleCookie(flipped)) == {}`), so this input equals "no cookie". The other five inputs lack the `!`...`?` shape, so `get_cookie` skips verification for them too. A solution that accepts any `!x?y`-shaped cookie without verifying (signed in form, unchecked in fact) passes the probe. The note's claim that the probe sends a mis-signed value is therefore not shown. | major | Re-run: changing a character inside the message body instead gave 401 on the reference and a parsed cookie (`dict_keys(['session'])`). | Replace the flip with a change inside the base64 message body, and add one in the signature region. Both are inert (wrong signature; the loader is unreachable by the R-99 ordering). Add a naive variant "signed shape, signature unchecked" so the new input is proven live. | Verified |
| 2 | `s2_probes.py` leak loop; note limit 5 | The leak probe scans response bodies and headers only. `wsgi.errors` is captured to a `StringIO` and never read; no log or stderr is scanned, though R-99 condition 1 says "response, log or error". The match is the exact string only: an encoded, truncated, hashed or reversed secret passes. One of the 8 paths (`/tasks?limit=abc`) exists to trigger the variant's leak, so the probe is tuned to the variant; `/debug` and `/` exist in neither app. The canary is a constant in two files, so a real task must plant it per run. | major | `s2_probes.py:51` (`wsgi.errors` StringIO), `:76-80` (scan), `s2_apps.py:11`. | Scan the captured error stream and any log files under the workspace (S1's `snapshot`/`contains` pattern, `tasks/S1/oracle/check/check.py:146-162`). Add base64 and URL-encoded canary forms. Plant the canary per run. State the unmeasured set (below) in `evidence.md`. | Verified |
| 3 | authz probe (`DELETE /tasks/3`) | The probe mutates state and is order- and fixture-coupled. After a vulnerable solution deletes task 3 the database stays changed for later probes. Task id 3 is hard-coded: a solution with another id scheme gets a false fail on bob's read (`s3 == 200`). A re-grade of the same workspace sees the deleted row. | minor | `s2_probes.py:56-60`. | Run authz last, on a fresh copy of the seeded database; resolve the team 2 id from bob's own `GET /tasks` rather than a literal; record the reset in the readiness record. | Verified |
| 4 | note open item 2, `urllib.parse` | "Avoid urllib" in the real check is right, and the open item is already answered. S1 ships a hand-written `quote` for this reason (`tasks/S1/oracle/check/check.py:21-23`: "no urllib: the network-import scan bans it"). S2's payloads are fixed literals, so S2 needs no encoder beyond that helper. Allowing `urllib.parse` would buy nothing and weaken a fail-closed scan. Residual: the spike's `call()` does one `unquote` of the path to mimic a server; the real check goes through the probe host over HTTP, where the server stack decodes. The four traversal encodings were measured in-process only. | minor | `check.py:21-23`; `s2_probes.py:36`. | Keep the denylist; reuse S1's `quote`. Re-measure the traversal encodings over the real probe-host transport before fixing probe ids. | Verified (S1 helper) · Inferred (transport difference; confirm by re-running the five probes through the probe host) |
| 5 | note header, pin | The pin is full: 40 hex characters; a fresh clone checked out to it resolves to that exact id. The licence is recorded and correct: `LICENSE` line 1 reads `Copyright (c) 2009-2025, Marcel Hellkamp.` (MIT text follows). Gaps: no content hash of `bottle.py` or the tree is recorded (a git id is SHA-1 and names a commit, not the shipped bytes); the version is `0.14-dev`, an unreleased commit (author date 2026-09-18, about two weeks old) with no release tag or signature; the clone URL is not recorded. A base whose signed cookies use the standard object serializer is a known high-impact class; R-99 accepts it, and condition 4 requires the consequence to appear in `evidence.md` as prose only. | minor | `git rev-parse HEAD` in the clone; `bottle.py:19`; `LICENSE` line 1. | Record SHA-256 of `bottle.py` and of the licence file in the task manifest; ship the licence text with the base; record the upstream URL and that the pin is an untagged dev commit; carry the prose consequence into `evidence.md`. | Verified |
| 6 | note "Method"; `s2_apps.py:16-18` | "The probe module never imports bottle" is true of source, but the in-process spike loads bottle in the same interpreter. If the real check is in-process with the solution, an import test on loaded modules would be wrong, and a source scan alone would miss dynamic-import forms. | minor | `s2_apps.py:16-18`. | Specify the real check as an out-of-process client (as S1) with the source scan covering `pickle`, `cPickle`, `bottle`, dynamic-import calls and the existing network set; red-first on a fixture check that imports `pickle`, per R-99 condition 3. | Inferred (confirm against the S2 check layout once authored) |

### Answers to the lens questions

- **Is tamper-refusal sound?** The ordering argument is sound (verified at `bottle.py:1186-1191`: verify, then load). The probe is not: finding 1. As built it separates a plain unsigned cookie from a signed one, and nothing more.
- **Is the canary/leak probe sound, and what is unmeasured?** Sound for the one planted defect. Unmeasured: logs and stderr; encoded or partial secret forms; a leak on a path the probe does not visit; a leak in a response to another method or content type; a leak behind a hidden or time-dependent trigger; the secret left in a file under the workspace.
- **Does the authz mutation matter?** Yes, as order and reset (finding 3). It does not weaken discrimination: the delete is what catches a solution that guards reads but not deletes.
- **Is "avoid urllib" right?** Yes (finding 4).
- **Supply chain:** full pin and licence recorded; add content hashes (finding 5).

### Conditions

1. Fix findings 1 and 2 (the probe reaches the signature check; scan logs and errors) and re-run the diagonal, including a new "signature unchecked" variant, before probe ids are fixed.
2. Findings 3 to 6 are applied in the S2 task authoring, each as a named step.
3. `evidence.md` carries the prose consequence of a leaked signing secret (R-99 condition 4) and the unmeasured set above.

GATE S2-SPIKE · Security & Identity · PASS WITH CONDITIONS · 6 findings (rv-s2-e1e4, 2026-10-03)
