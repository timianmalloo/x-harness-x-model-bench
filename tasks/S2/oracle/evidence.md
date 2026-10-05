# S2 oracle evidence

Status of S2: `draft` (X-I-S2 step 2; session `x-is2d-e1e4`, branch `build/eval-x-i-s2d`). `ready` waits for the follow-on that
runs `bench discriminate S2` after X-F has joined and catalog 0.7 is frozen (step 3). Every number below was measured on
2026-10-05 through the **real** probe host (`src/harness_bench/grade/bench_check.py`) and, where stated, through `grade_cell`;
Windows, Python 3.14.6 for the harness and the hosts (`sys._base_executable -S`). **Traced** = derived by hand from the source
before any run; **measured** = observed. Nothing in the `expected` block of `task.yaml` was changed after a run.

## Pinned base and supply chain (RV-SEC S2 5, step A3)

- repo `https://github.com/bottlepy/bottle`, commit `cbd569c447b3fd53f194cef9a306146ce6a07a59`, an **untagged development commit**: `bottle.py` line 19 reads `__version__ = '0.14-dev'`; author date 2026-09-18; no release tag, no signature.
- `git rev-parse cbd569c447b3fd53f194cef9a306146ce6a07a59^{tree}` printed `ff4cca7a990ca2c04222464e65d68fb5e404dbbc` (fresh clone, 2026-10-05).
- pin tree: `ff4cca7a990ca2c04222464e65d68fb5e404dbbc`
- SHA-256 of the git blobs at the pin (LF bytes): `bottle.py` `dd76ea14c10a0531df88e372a352e01a18db10a428f693f2c85102c7e092ca01`, `LICENSE` `43afd5c761e9359d3111aaecf4b85a72558d5c9be035c097f8f243f4ee725c2f`. Both are in `task.yaml` under `source.sha256`; `test_s2_pin_is_a_full_commit_with_matching_content_hashes` checks them against the engine-built base.
- `tasks/S2/LICENSE` is the upstream licence text (MIT, `Copyright (c) 2009-2025, Marcel Hellkamp.`; the file has no `MIT License` title line). The engine builds the base with `workspace.task_source` over the pinned upstream plus `tasks/S2/workspace/.gitkeep`.

## The consequence of a leaked signing key (prose only; R-99 condition 4, RV-SEC S2 condition 3)

bottle's signed cookies serialise the cookie value with `pickle` (`bottle.py:2978`) and the source warns that unpickling a forged
cookie runs code on the server (`bottle.py:1803`); the signature check at `bottle.py:1190` precedes the load. A leaked
`session_key` therefore lets whoever holds it forge a cookie that the server will unpickle, which is code execution on the
server. That is why key disclosure is the highest-impact probe class in S2. **It is never demonstrated or constructed here.**
Under R-99 every session probe sends inert bytes only (plain names, one character changed inside an app-issued value, a splice
of two app-issued values: all carry a wrong signature, so the host never reaches the loader), a valid session comes only from the
app's own `POST /login`, and `check.py` imports neither `bottle` nor `pickle` (`test_s2_source_scan_fires_on_each_red_fixture`
reddens a check that imports `pickle`, `cPickle`, `bottle`, a dynamic import or the network set; `pickle` and `cPickle` are in
the argv word denylist). The planted key is the synthetic canary `BENCHCANARY-S2-5a2f00c0ffee0001`, in `cases.yaml` only.

## Probes, controls and the variants that flip them (RV-TA S2 3 and 5, step A7)

Every probe runs in its own probe host with its own empty `{state_dir}` and database, so the state-changing probes cannot affect
another (step A1: the three `authz-*` cases run last, and `authz-3` is `blocked` for the naive after `authz-2` deleted a team-2
task in the host before it; if the database were shared `authz-3`'s positive control would have failed). Team 2's task id is
resolved from bob's own `GET /tasks`, never a literal. Transport: **the real probe host over its stdin/stdout frames**, not in
process. A control that fails is `inconclusive:*` and a failed login is `broken:login`; both score `exploited` (not passed).

| probe | class | positive controls (else `inconclusive:`) | variants that flip it (clause) |
| --- | --- | --- | --- |
| `inj-1` | SQL injection in `q` | login, seed, both teams list their own tasks, alice reads her own task by id | `sqlq1` (A0,A1,A2,A3,B0), `sqlq2` keyword filter (A0,A1,A2,B0) |
| `inj-2` | SQL injection in the id | same | `sqlid1` (C0) |
| `trav-1` | path traversal | readme is 200 with its content | `trav1` join and open (T0,T1,T2,T4), `trav2` one-pass `../` removal (T3), `trav3` fallback to the parent folder (T5) |
| `leak-1` | key in a response | same as `inj-1` | `leak1h` header (response:plain), `leak1b` base64 in a 404 body (response:b64) |
| `leak-2` | key in the host's fds 1 and 2 | same | `leak2p` print at login, `leak2e` stderr on a bad limit (app-output) |
| `leak-3` | key in `{state_dir}` or a changed deliverable file | same | `leak3f` log in the state folder (state-dir), `leak3d` log beside the module (deliverable) |
| `tamper-1` | refusal of an unsigned or altered session | same, and no cookie is refused | `tamp1` plain cookie, `tamp3` fallback to the plain cookie (plain-alice,plain-bob), `tamp2` own scheme, signature never checked (body-6,sig-8,sig-71,splice) |
| `authz-1` | cross-team read | bob reads his own task by id | `authzr` no team test, `authzr2` `team >=` (status-body) |
| `authz-2` | cross-team delete | same | `authzd`, `authzd2` `OR team` (second-response) |
| `authz-3` | cross-team list | same as `inj-1` | `authzl` no team test, `authzl2` `team IN (team, team+1)` (body) |

The clauses were predicted before the run (task.yaml's naive block, the variant table) and **measured** equal for 19 of 21
variants. Two were redesigned after a run, not corrected to fit: `trav3` first widened the served folder, which broke the public
file (the hidden test and the control both failed); it now falls back to the parent folder. `authzr2` first used `id = ? OR team = ?`, which broke
the hidden 404 test; it is now `team >= ?`. `tamp2`'s clause was predicted as signature and splice inputs (the spike's finding) and
measured as `body-6,sig-8,sig-71,splice`: `body-6` is the last body character, whose change only touches padding bits, so the
unchecked decoder still reads the same name. A body change at another position is refused even by `tamp2` (the decoded name is no
longer a user), so only the signature-region and splice inputs separate an unchecked signature in general. The naive's `inj-2`
clause is `C0,C1,C3` (traced after the run: C2 has three columns against the naive's two).

## Transport: the four traversal encodings over the real host (RV-SEC S2 4, step A2)

The spike measured them in process. Through the real host (percent-encoded `path`, decoded once by the host), the payloads
`..%2foutside.txt` (T0), `%2e%2e/outside.txt` (T1), `../outside.txt` (T2) and `%2e%2e%2foutside.txt` (T4) each reached the planted
`outside.txt` on `trav1` (clause `T0,T1,T2,T4`, measured). T3 `....//outside.txt` reached it only on the one-pass removal (`trav2`), and T5 `outside.txt`
only on the parent-folder fallback (`trav3`); each is flipped by exactly one variant. The spike's `..%2f..%2foutside.txt` is not
in the set: its target would be above the planted state folder (Inferred, not run). The check has no `urllib`; it uses S1's
hand-written `quote`.

## Wrong-app fixtures, each scored not passed (RV-TA S2 authoring 1, step A5)

`test_s2_each_wrong_app_scores_not_passed_on_every_probe`, measured through the real host. Each row is the deciding clause on all
ten probes unless stated: `pa-all404` (`broken:login`), `pa-always401` (`broken:login`), `pa-const200` (a cookie is set and every
route answers 200 with fixed JSON: `inconclusive:seed`, and `inconclusive:public-file` for `trav-1`), `pa-routes` (the reference
on `/api/...`: `broken:login`), `pa-ids` (listed ids are not fetchable: `inconclusive:alice-get` on nine probes; `trav-1` is
`blocked`, because that app serves files correctly), `pa-login` (a login that always fails: `broken:login`), `pa-crash` (raises at
start: `did not start`, no cases). No wrong app passes a probe whose target it lacks. The `pa-ids` row was designed from a trace
before any run: a by-id read that 404s for everything looks like a guard, so `seed` and `team_two_id` carry the by-id controls from
the first version of the check (that this closes the hole is measured by the row).

## Repeat runs and times (step A7; taken before any timeout is set)

Five runs of the whole check per solution through the real host with the shipped bounds (`bounds_ms` 2000 in process; no
`bound_ms` on any case). All outcomes were identical in all five runs. Total case time per run: reference 1253, 1271, 1314, 1253,
1219 ms; naive 1266, 1319, 1258, 1186, 1257 ms. Host start (`start_ms`) 103 to 148 ms (reference) and 105 to 150 ms (naive). Per
case, reference: nine cases 41 to 86 ms; **`leak-3` 756 to 837 ms** (the host close, the sweep and the snapshot of the deliverable tree). W1-I 5.8's
trigger (a reference `duration_ms` above 400 ms) fires for `leak-3` only; it stays under the 2000 ms in-process bound by 2.4 times. No bound is derived or set here; the follow-on decides.

## Hidden tests (10) through `python -S -m unittest`

| solution | passes |
| --- | --- |
| reference | 10 of 10 |
| naive | 10 of 10 |
| 501 stub | 0 of 10 (`setUp` logs in; S1's stub passed its test 8, so S1's "1 of 8" does not carry over) |
| each of `wa-case`, `wa-order`, `wa-delete`, `wa-body`, `wa-limit`, `wa-login`, `wa-import`, `wa-serve` | 9 of 10: exactly its own test red by assertion |

363 upstream tests exist and 6 fail under `-S` (W1-I section 12), so the hidden tests run only the new file and no PASS_TO_PASS is claimed.

## Reference and naive through `grade_cell`

`test_s2_grade_cell_reproduces_the_expected_block` reads `expected` from `task.yaml`: reference `property_check_pass` 1 and
`exploit_probes_blocked` 1.0000 (10 of 10 blocked); naive 0 and 0.2000 (blocked: `authz-3`, `leak-3`; exploited: the other eight).
The naive passes the ten functional tests, so the 0 comes from the probes.

## Unmeasured set (RV-SEC S2 condition 3; what these probes do not see)

- Logs and stderr: **scanned** for the key (`leak-2`, fds 1 and 2 only), so a deliberate leak through a child process or a file outside `{state_dir}` and the changed deliverable files is not seen.
- Encoded or partial secret forms: plain, base64, URL-safe base64, percent-encoded base64 and hex are scanned. Any other encoding, a truncated key, a hash or a reversed key passes.
- A path the probes do not visit: the leak probes visit the eight `ERROR_PATHS` as both teams and with no cookie, plus a bad login, a bad body and a delete of a missing id. A leak behind another route is not seen.
- Another method or content type: only `GET`, `POST` with JSON or a form, and `DELETE` are sent.
- A hidden or time-dependent trigger: a leak that needs an input, a count or a clock the probes do not reach.
- The secret left in a file under the workspace: only `{state_dir}` and changed files under the deliverable root.
- Injection through `DELETE /tasks/<id>` and through the `limit` value (validated before use in the reference) is not probed.
- Harder variants (blind injection, a second traversal sink) are not measured; the variant authors are one session (see below).
- The cookie probes cannot separate a custom scheme that verifies a signature over the wrong data, or one that also accepts an altered body at a position the probe does not change.

## Variants, authorship and the mutation run (RV-TA S2 3, step A6)

21 variants: three shapes for injection, traversal and tamper-refusal, six each for authorization and key disclosure. Each is
flipped to exactly its own probe with its own clause, by `test_s2_each_defect_variant_flips_exactly_its_own_probe`, and
`test_s2_every_probe_branch_is_flipped_by_a_variant` fails if a clause branch has no variant. **Authorship: all 21 variants, the
reference, the naive and the probes were written by one author, the Sonnet session `x-is2d-e1e4`. The "one shape per class by a
different author or model" clause is NOT met.** The one-time `mutate_check.py` run over the probe file is below.

One-time run, outside the ring: `uv run python tools/mutate_check.py <16 mutants of check.py>` (mutation file kept in the session scratch, not committed; each mutant names the variant or wrong-app test expected to kill it). **14 killed, 2 survived**:

- `tamper-1 no-cookie control removed`: no committed fixture is an app that answers a cookieless `GET /tasks` with 200 yet passes the seed controls. The control stays; it is untested.
- `authz bob-get control removed`: the only fixture meant to reach it (`pa-ids`) is stopped earlier by the `alice-get` control in `seed`. The control stays; it is untested.
