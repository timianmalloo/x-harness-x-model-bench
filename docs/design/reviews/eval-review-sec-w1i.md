---
id: review-eval-sec-w1i
title: "Security & Identity review of W1-I: security tasks S1 and S2 (Adversary Mode)"
type: doc
status: draft
owner: "@timianmalloo"
tags: [review, security, evaluation-campaign, wave-1, w1-i]
links:
  - { to: design-eval-seam-contracts, rel: relates-to }
  - { to: review-eval-sec, rel: refines }
review-by: "2026-10-17"
summary: >-
  Security & Identity gate on W1-I (design/eval-security-tasks, 2fc8906b) against W0 rev 2 and R-87..R-94.
  The latent requirement is latent, the probes run in the probe-host child, both tasks declare no build and use MIT bases
  pinned by full commit. The secret-leak probes scan one of two tokens, S2's signed cookies are pickle-based, and the
  new `app` keys are not in W0. PASS WITH CONDITIONS, 8 findings.
---

# Security & Identity review of W1-I (rv-sec-w1i-e1e4)

PERSONA: security-identity-architect · MODE: Adversary · TIER: T2. Severity: blocking / major / minor. Confidence: Verified (observed) / Inferred (reasoned; the confirming check is named).

## W1-I: `docs/design/eval-security-tasks.md` (branch `design/eval-security-tasks`, 2fc8906b)

Trust boundaries: B7 (inherited from W1-F and ADR-0018), plus the design's T1 (oracle to workspace), T2 (upstream base to engine), T3 (canary to reports). I agree with the set. Dependencies added: two upstream trees, both MIT, no package index. No real secret or PII enters a task.

### W0 rev 2 conditions and the brief's points

| point | result | evidence |
| --- | --- | --- |
| Probes run in the probe-host child, not in the check | Met in the probe design. Stale wording remains (finding 8). | §5.5 "One probe-host start per case"; §3 of W0 rev 2, line 118 |
| Offline build declared (SEC 7) | Met. No `build`, no `start`, `env: []`, `python -S`; test `test_s1_declares_no_build_and_no_network_names`. Network reach stays ADR-0018's accepted residual. | §5.9, §12 |
| Latent requirement truly latent | Met. The prompt names no ownership, injection or logging rule; the term test found and fixed one false hit (`Authorization`). Hidden tests use one principal, so no test rewards a guard. Saturation is a task property, correctly left to EV-8. | §5.2, §5.3, §5.6 (read) |
| Threat coverage: injection, authz/authn bypass, secret leak | Adequate for "no known exploit" (R-S3), with gaps in findings 1, 3, 4, 5. Each probe is shown live by a seeded defect (SP-I4, 9 variants). | §5.5, §14, App. C |
| Canary design | Sound shape: `BENCHCANARY-S1-<hex16>` matches the `task_canary` regex (G11); evidence stores no bodies; values are synthetic and outside the workspace (`test_s1_no_oracle_string_in_prompt_or_task_workspace`). Gaps: findings 1 and 7. | §5.5, §11 |
| Licensing and pins | microdot `7742db9f` and bottle `cbd569c4` are MIT, full 40-hex pins. I confirmed the microdot commit exists and `examples/auth/token_auth.py` is in it, and `docs/tutorial.rst` exists in bottle at its pin. Gaps: finding 6. | `gh api` on both repos, 2026-10-03 |
| No credential or real secret | Met. Every planted value is a canary; `test_s1_only_synthetic_values_are_planted`. | §11 |

### Findings

| # | location | finding | severity | evidence | fix | confidence |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | §5.5 `leak-1/2/3` | The leak predicates test only `S` (susan's token). `D` (david's token) goes through Setup D in six probes and is never scanned. A solution that logs or stores the token of the second principal, or only for a non-first user, scores `blocked`. | major | `leak-1` "contains `S`"; `leak-2` "does not contain `S`"; `leak-3` "`S` as a byte string" | Scan for both tokens in all three leak probes (the cost is one more substring per check). Add a variant that leaks only `D`. | Verified |
| 2 | §12 S2 (E4) | bottle's signed cookies are pickle-based: `cookie_encode` does `pickle.dumps` (bottle.py:2978) and the docs warn "code on server side if unpickled" (bottle.py:1803). A leaked cookie secret is therefore code execution, which makes S2's secret-leak class the highest-impact one. The design does not say how the check mints a valid cookie: the check is stdlib-only and must not import bottle, and the agent may edit `bottle.py`. | major | `gh api` raw `bottle.py` at `cbd569c4`, lines 94, 1797-1824, 2973-2983 | Before E4 authoring, X-I records: (a) the check gets valid cookies only by calling the app's own login route, or by a re-implemented HMAC in the check, never by importing bottle; (b) forged-cookie probes send inert bytes, never a pickle gadget; (c) a defect variant where the secret leaks and a forged cookie is accepted. | Verified (text); Inferred (the check's minting path) |
| 3 | §5.5 `leak-2/3` | Leak scope is narrow. `leak-3` scans `{state_dir}` and changed files in the deliverable copy only; a token written to a log file in the working directory outside the copy, `/tmp`, or via a reversible encoding (base64, hex) is not seen. `leak-2` sees only stdout, stderr and `wsgi.errors`. | minor | §5.5 `leak-2`, `leak-3` | State this in R-S3 as a named residual; scan the host's temp dir and cwd too if the probe host sets them per case (W1-F). | Inferred (confirm: the probe host's cwd and temp dir per case) |
| 4 | §5.5, F2, §10 | Probes were derived against one vulnerable shape (the naive solution). The alternative-solution control covers a correct second solution (F2) but no second vulnerable one. A solution that is injectable in another shape (owner filter after the `LIKE`, double-quoted literals, an integer-formatted id) may be `blocked` by payloads tuned to the naive. | minor | §5.5 "Why four tautologies" (the dead `inj-1` was found this way); F2 | Add one alternative-vulnerable solution (different SQL shape) to `test_s1_each_defect_variant_flips_exactly_its_probes`; require it flips an injection probe. | Inferred |
| 5 | §5.5 `authz-4` | The authentication-bypass probe has four requests: no header, no header, `Bearer nope`, no header. It omits near-miss tokens (`S` plus a suffix, `S` minus its last character, a lower-case `bearer`, an empty `Bearer `), the standard forms of a prefix-match or `startswith` comparison bug. | minor | §5.5 `authz-4` row | Add `Bearer <S>x` and `Bearer <S[:-1]>` to the 401 set, with a defect variant (`startswith`). | Verified (text) |
| 6 | §5.1, §11 T2, §8 | Supply chain is thinner than the claim. The test `test_s1_pin_is_a_full_commit` checks only the format of the pin. The engine's own docstring says the tree comes from "a cached, verified upstream clone" (`workspace.py:166`); I did not read `upstream_tree` to confirm what it verifies. No tree hash is recorded, and `NOTICE.md` (named in §11 "per the A1 precedent") is absent from the §8 change-surface list. The base depends on GitHub keeping both repos. | minor | design §5.1, §8, §11; `src/harness_bench/workspace.py:161-186` | Record `git rev-parse <commit>^{tree}` in `task.yaml` and `evidence.md` and assert it in the pin test; add `NOTICE.md` and the upstream `LICENSE` presence to §8 and a test; keep the vendoring upgrade (`git archive`, as D1) as the named trigger if a repo disappears. | Inferred (confirm: read `upstream_tree`) |
| 7 | §11, F13, §5.4 | The canaries are low-entropy and sequential (`…0001`, `…0002`), which is fine for a marker. But F13 says the agent "cannot see `BENCHCANARY-`": the agent's app receives the canary tokens as `create_app` arguments at probe time, so an app that special-cases the `BENCHCANARY-` prefix can detect the check. | minor | §5.4 `app.args.tokens`; F13 | Do not claim the agent cannot see them; list the prefix-detection as the ADR-0018 in-process residual. No code change: the probe host cannot hide the arguments. | Verified (text) |
| 8 | §5.4 vs W0 §3; §5.9, §11 | Seam disagreement (W0 and W1-I). W0 rev 2 defines `app: {module, attr, kind}` with `kind: callable | wsgi`. W1-I adds `factory`, `paths`, `args` and a `{state_dir}` placeholder, plus four more host duties (environ, decoded `PATH_INFO`, app output to the host's stderr file). They are marked provisional but live in a `cases.yaml` the grader normalises, so an unknown key is either dropped (cases cannot run) or accepted without validation (an unvalidated path into `sys.path`). The text also still says "in process" and "in-process injection into the check is undetected", the rev 1 meaning that W0 line 118 removed. | major | W0 `eval-seam-contracts.md` line 105 and 118; design §5.4, §5.9, §16 | W0 amendment through W1-F: a validated `app` schema (`paths` relative to `--root`, `args` JSON only), and the seams `req-...DPBSM9` and `req-...NQ7Y7D` granted or S1 stays `stub`. If item 5 (app output to a stderr file) is refused, drop `leak-2` and rebase the expected values to 9 probes, never let it default to `blocked`. Reword §5.9 and §11 to "in the probe host". | Verified |

### Seam disagreements

- W1-I §5.4 against W0 §3 `app` fields (finding 8): both docs, W0 §3 lines 105 and 118.
- W1-I §5.5 assumes the probe host puts app output on a stderr file and the protocol on a private descriptor. This must hold from before the agent module is imported, or an import-time write can forge a frame. That is W1-F's red test `test_import_time_forgery_cannot_reach_result`, not repeated here.

### Conditions for the gate

1. Findings 1 and 8 (major) are fixed in a follow-up, with the unfixed seam items marked as blocking S1 `ready`.
2. Finding 2 is recorded in §12 as an open item before E4.
3. Findings 3 to 7 are fixed or recorded as accepted residuals.

GATE W1-I · Security & Identity · PASS WITH CONDITIONS · 8 findings (rv-sec-w1i-e1e4, 2026-10-03)
