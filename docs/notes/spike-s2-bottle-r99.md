---
id: note-20261003-spike-s2-bottle-r99
title: "S2 spike (R-99 redesign) - probe set measured on bottle at the pin"
type: decision-note
status: proposed
owner: "@timianmalloo"
tags: [spike, s2, security, bottle, r99]
links:
  - { to: design-eval-security-tasks, rel: relates-to }
  - { to: note-20261003-spike-s2-bottle-cookie-reads, rel: relates-to }
review-by: "2026-10-17"
summary: >-
  Measured spike for S2 under R-99, re-run after the RV-SEC and RV-TA conditions (C1-C5): five probe classes (SQL
  injection, path traversal, cross-team authz, secret non-disclosure, tamper-refusal) each discriminate a reference
  app from a single-defect naive on bottle cbd569c4, with no probe touching the signed-cookie deserialization path.
  Tamper now reaches the signature check; leak scans errors and logs; each probe has a positive control.
---

# S2 spike under R-99: measured probe set (rev 2, after the review conditions)

Sessions `x-is2b-e1e4` (rev 1) and `x-is2d-e1e4` (rev 2, this text). Pin `bottlepy/bottle` @ `cbd569c447b3fd53f194cef9a306146ce6a07a59` (MIT, `Copyright (c) 2009-2025, Marcel Hellkamp`), Python 3.12.10, Windows. Cookie-code line reads (`bottle.py:2978`, `:1190`, `:1803`) are in `docs/notes/spike-s2-bottle-cookie-reads.md`; not repeated. Scripts: `tools/spikes/s2_apps.py` (apps), `tools/spikes/s2_probes.py` (probes and the matrix).

## Method and R-99 compliance

- Apps run in-process as WSGI callables. The probe module imports only stdlib (`base64 io json os re sys time`); it never imports `bottle` or `pickle`, and no longer imports `urllib` (a hand-written `quote` and `unquote`, S1's helper, replace it).
- A valid session comes only from `POST /login`; the probe reuses the `Set-Cookie` pair byte for byte.
- Tamper-refusal sends only inert bytes: plain names, a `name:team` string, base64-looking text, an empty value, no cookie, **one alphanumeric character changed inside the message body of an app-issued value, one inside its signature region, and a splice of alice's body with bob's signature part** (both app-issued, so the signature is wrong). Nothing is signed or constructed. The signature check precedes the loader, so the host never loads attacker bytes (`bottle.py:1190`).
- The consequence of a leaked signing secret (code execution when a cookie is later unpickled) is prose only here and is never demonstrated.
- The reference app calls bottle's cookie API with a secret on values it issued at login; that is the app's own route, outside the probes.

## What changed after review (C1-C5)

| item | change | measured |
| --- | --- | --- |
| C1 tamper reaches the signature check | The closing-quote flip is gone. Inputs now flip a character inside the body and inside the signature region. | Every tamper input parses into a jar that has `session` (`SimpleCookie(input)` read in `inspect_tamper.py`, a scratch run; rev 1 gave `{}`). The reference answers 401 to all 11 inputs. |
| C1 variant `sigskip` | Own HMAC scheme, signature never checked. | `sigskip`: tamper false, other four true. It accepts `sig-8`, `sig-27`, `body-6` (the last body character; it only changes padding bits so the decoded name is unchanged) and the splice; it refuses `body-0` and `body-3`, which change the decoded name to an unknown user. Not every body position separates: a signature-region change and the splice always do. |
| C2 custom-signing pair | `reference-custom` signs with its own HMAC and checks it; `sigskip` signs and does not. | Both pass the four non-tamper probes; the body, signature and splice inputs separate them (`reference-custom` all pass; `sigskip` tamper false). |
| C3 leak scans errors and logs | The probe scans bodies, headers, the captured `wsgi.errors` and every non-database file under the workspace, for the canary, its base64 (standard and URL-safe), the percent-encoded base64 and the hex form. The canary is planted per run (`os.urandom(7).hex()` in the matrix, passed to the app). | `leakerr`, `leakb64`, `leaklog` each flip leak only. |
| C4 positive controls | Outcomes are `pass`, `fail`, `inconclusive`, `broken`; only `pass` scores. Controls: alice and bob `GET /tasks` are 200 and carry `A-task` and `B-task`; the readme is 200; authz resolves team 2's task id from bob's own listing (never a literal); tamper needs the issued cookie to work and no cookie to be refused. A failed login (or a crash during it) gives `broken` for every probe. | `wrong-all404`: all five `broken`. `wrong-login-only` (login works, every other route 404): all five `inconclusive`. |
| C5 full diagonal | Re-run, 5 repeats per cell, normal and `python -S`. | Table below. |

SEC 3 / TA 4 (authz order and reset) is also built in: authz runs last on a second, freshly seeded app.

## Measured results (command and output)

Command, from `tools/spikes/` (`$B` = a clone at the pin): `python s2_probes.py "$B" 5` and `python -S s2_probes.py "$B" 5`. Both exit 0. Letters: p pass, f fail, b broken, i inconclusive. `diag` is the script's own check that the failed set equals the expected set.

```
variant            sqli trav authz leak tamper   diag  ms (min-max of 5)
reference            p    p    p    p    p       True  13.6-65.1  (the first run carries bottle's import)
reference-custom     p    p    p    p    p       True  13.5-14.7
all-naive            f    f    f    f    f       True  14.2-20.7
sqli                 f    p    p    p    p       True  15.3-18.8
trav                 p    f    p    p    p       True  15.1-18.2
authz                p    p    f    p    p       True  15.9-21.1
leak                 p    p    p    f    p       True  14.1-16.0
tamper               p    p    p    p    f       True  13.0-18.0
leakerr              p    p    p    f    p       True  14.8-16.8
leakb64              p    p    p    f    p       True  14.1-16.9
leaklog              p    p    p    f    p       True  14.7-15.9
sigskip              p    p    p    p    f       True  13.2-16.6
wrong-all404         b    b    b    b    b       True  0.0
wrong-login-only     i    i    i    i    i       True  0.0
```

The `-S` run gave the same outcomes in every cell (all `diag` true). The rev 1 numbers (one run each: reference 99.3 ms, all-naive 29.6 ms) are superseded; the reference's slowest of five here is 65.1 ms and the rest are 13 to 15 ms, so the rev 1 figure was mostly first-import cost. These are in-process times on one machine, not bounds. `cd $B && python -S -c "import bottle; print(bottle.__version__)"` printed `0.14-dev` in rev 1 and was not re-run.

Defect shapes: sqli = string-formatted query; trav = joined path read with `open`; authz = no team check on read and delete; leak = a 500 handler that prints the config containing the secret; leakerr = the secret written to `wsgi.errors`; leakb64 = a 500 body with the base64 secret; leaklog = a log file under the workspace with the secret; tamper = a plain unsigned `session=<user>` cookie; sigskip = own signing scheme, signature unchecked.

## Verdict on the R-99 fallback (condition 7)

The probes separate secure from insecure with no deserialization contact, including the own-HMAC shape a model is likely to write (`reference-custom` against `sigskip`), so option (a) holds and the fallback is not triggered. All variants are written by the spike's author (one hand); independent authors are an authoring item (A6).

## Limits and open items

1. One or two shapes per class; harder variants (blind injection, a second traversal sink, a log-only leak under another name) are Inferred coverage.
2. The transport is in-process. The traversal encodings and the cookie round trip still need re-measurement through the real probe host (A2).
3. Bottle's own signed-shape-unchecked variant cannot be built without loading a pickle, so the "signed shape, signature unchecked" naive is realised in the own-HMAC scheme only.
4. The leak scan sees only what the harness captures: `wsgi.errors` and workspace files. Host stderr is the probe host's log (S1's `output_contains`), which the in-process spike has no counterpart for; the task check adds it.
5. Repeat-run times are 5 per cell on one machine.
