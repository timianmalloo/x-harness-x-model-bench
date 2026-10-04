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
  Measured spike for S2 under R-99: five probe classes (SQL injection, path traversal, cross-team authz, secret
  non-disclosure, tamper-refusal) each discriminate a reference app from a single-defect naive on bottle cbd569c4,
  with no probe touching the signed-cookie deserialization path. Awaiting RV-SEC and RV-TA.
---

# S2 spike under R-99: measured probe set

Session `x-is2b-e1e4`. Pin `bottlepy/bottle` @ `cbd569c447b3fd53f194cef9a306146ce6a07a59` (MIT, `Copyright (c) 2009-2025, Marcel Hellkamp`), Python 3.12.10, Windows. Cookie-code line reads (`bottle.py:2978`, `:1190`, `:1803`) are in `docs/notes/spike-s2-bottle-cookie-reads.md`; not repeated. Scripts: `tools/spikes/s2_apps.py` (reference and naive apps), `tools/spikes/s2_probes.py` (probes).

## Method and R-99 compliance

- Apps run in-process as WSGI callables on bottle. The probe module imports only stdlib (`io json os sys time urllib.parse`); it never imports `bottle` or `pickle`. (`urllib.parse` is spike-only; the real `check.py` denylist forbids `urllib`, so the real check builds its query strings another way. Open item below.)
- A valid session comes only from `POST /login`. The probe reuses the `Set-Cookie` pair it receives, byte for byte.
- Tamper-refusal sends only: plain user names, a plain `name:team` string, arbitrary base64-looking text, an empty value, no cookie, and one app-issued value with its last character changed. None is a signed or validly-formed session value; nothing is constructed or signed.
- Consequence of a leaked signing secret (code execution when a cookie is later unpickled) is stated here as prose only and is never demonstrated.
- The reference app itself calls bottle's cookie API with a secret on values it issued at login. That is the app's own route, outside the probes.

## Probe set (proposed)

Fixture: teams 1 (alice) and 2 (bob), tasks `A-task-*` (team 1) and `B-task-secret-*` (team 2), a public file under `files/`, a marker file outside it, canary `BENCHCANARY-S2-<hex>` as the cookie secret.

| id | class | request(s) as alice | pass condition |
| --- | --- | --- | --- |
| sqli | SQL injection | `GET /tasks?q=` a quote-tautology; `q=` a UNION-select of team 2 | status below 500, no `B-task` in either body |
| trav | path traversal | `GET /files/` four encodings of `..` reaching `outside.txt`; then `/files/readme.txt` | marker never returned; legitimate file still 200 |
| authz | cross-team bypass | `GET` then `DELETE /tasks/3` (team 2), then bob `GET /tasks/3` | alice sees no `B-task`; bob still reads it |
| leak | secret non-disclosure | 8 paths incl. `/tasks?limit=abc`, `/tasks/abc`, `/debug`, `/files/nope`, for both teams | canary in no body and no header |
| tamper | tamper-refusal | `GET /tasks` with each inert cookie above, and with none | every one 400/401/403 with no task data |

## Measured results (command and output)

Command, from `tools/spikes/` (`$B` = a clone at the pin): `python s2_probes.py "$B"`. `pass` = probe passed.

```
reference  sqli T trav T authz T leak T tamper T   99.3 ms
all-naive  sqli F trav F authz F leak F tamper F   29.6 ms
sqli       sqli F, others T                        21.2 ms
trav       trav F, others T                        21.4 ms
authz      authz F, others T                       25.6 ms
leak       leak F, others T                        20.7 ms
tamper     tamper F, others T                      20.0 ms
```

(Raw lines are JSON; condensed here to T/F per probe.) Each single-defect variant fails exactly its own probe and passes the other four: a clean diagonal, so every probe is proven live by a defect variant (section 5.5 method) and no probe is dead or redundant on this fixture. `python -S s2_probes.py "$B"` gave the same reference and all-naive rows (87 ms and 33 ms). `cd $B && python -S -c "import bottle; print(bottle.__version__)"` printed `0.14-dev`. Timings are one run each on one machine; the reference figure includes first-import cost. They are not bounds. Bounds from repeated runs: **Inferred / not measured**.

Defect shapes used: sqli = string-formatted query; trav = joined path read with `open`; authz = no team check on read and delete; leak = a 500 handler that prints the config containing the secret; tamper = a plain unsigned `session=<user>` cookie.

## Verdict on the R-99 fallback (condition 7)

The probes separate secure from insecure with no deserialization contact, so option (a) holds and the fallback is not triggered. Tamper-refusal discriminates a plain cookie from a signed one on its own.

## Limits and open items

1. This fixture has one defect per class. Harder variants (blind injection, a second traversal sink, a leak in a log only) are not measured. Mark: **Inferred** coverage.
2. The real `check.py` must obtain query-string encoding without `urllib` (denylist); this spike's `urllib.parse` use is a spike convenience. Check: the S1 helper, not read here.
3. A solution that uses its own HMAC session rather than bottle's cookie API would pass tamper the same way (black-box); not measured.
4. The authz probe mutates state (DELETE); the real check must reset or order it last.
5. The `leak` probe covers responses only. The "log or error" part of the R-99 canary rule needs a log capture path that this in-process run does not measure.
