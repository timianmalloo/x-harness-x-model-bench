---
id: review-w3-egress-codex
title: "W3-EGRESS slice 1 cross-vendor security review"
type: decision-note
status: accepted
owner: "@timianmalloo"
links:
  - { to: coordination-finish-harness-bench, rel: relates-to }
review-by: "2026-10-09"
summary: >-
  Security Adversary review of W3-EGRESS slice 1 at a45fbfa: BLOCK because synthetic
  sensitive values bypass the scanner and the gateway import lint permits a direct backend call.
---

# W3-EGRESS slice 1 — Security Adversary review

**Verdict: BLOCK.** Security & Identity Architect, Adversary Mode, T1 review; Codex on a different model from the Claude Opus 5.5 author (R-60 condition 3). I reviewed `git diff 87606c6..a45fbfa` on `w3-egress` at `a45fbfa` against US-47 and R-60. The trust boundary is the in-process handoff of agent-derived payload text to a future judge backend. The current scanner and import lint do not prove that sensitive text stays on the trusted side. The `w3-egress` checkout was read by absolute path and was not edited.

## Findings

| ID | Severity / confidence | Evidence and minimum clearing condition |
| --- | --- | --- |
| F1 — encoded and transformed sensitive values pass | **Blocker / Verified.** `check` searches the original string (`src/harness_bench/egress.py:84-93`). `_exact` recognizes the raw value and only the standard base64 and one URL-quoted form from `report.credentials.encodings` (`src/harness_bench/egress.py:48-50`; `src/harness_bench/report/credentials.py:93-99`). Email uses casefolded substring matching, username a case-insensitive whole-word regex, and home a casefolded separator rewrite (`src/harness_bench/egress.py:53-72`). The reused token-shape regexes are case-sensitive ASCII shapes (`src/harness_bench/report/html.py:23-28`). On the unmodified commit, synthetic JSON-escaped `synthetic\/alpha+beta` with `secrets=["synthetic/alpha+beta"]`, URL-encoded `operator%40example.invalid` with `email=...`, a line-split canary, URL-encoded home, base64 username, double-URL-encoded credential, upper-case token shape, and an NFKC-equivalent fullwidth canary all returned `classes=()` and `release` reached the fake backend. The fullwidth probe normalized to the original canary under NFKC. This violates US-47's no-outbound-sensitive-value condition (`docs/specs/harness-bench.md:495-501`). Define a bounded canonicalization contract for each class, scan the representation actually sent, fail closed on unsupported transformations where needed, and add negative backend-capture tests for these forms. |
| F2 — gateway lint does not bind the backend path | **Blocker / Verified.** The lint watches imports of one assumed module name, `harness_bench.gateway.backend`, and accepts any gateway module that merely imports `harness_bench.egress`; it never verifies a `check` or `release` call (`tests/test_architecture.py:68-98`). With a temporary `src/harness_bench/gateway/backend.py` defining `send(payload, backend): return backend(payload)` and no import of its own module, `test_only_the_gateway_reaches_a_judge_backend_and_only_beside_egress` passed. The module name is also an explicit unconfirmed assumption at `tests/test_architecture.py:71-77`; another spawner name would evade the rule. Bind the lint to the actual GW-I backend entry point and prove a direct call without a check fails, including a gateway module that imports `egress` without using it. Re-run the rule when GW-I creates the package. |
| F3 — Verdict representation can carry content | **Major / Verified.** For a `check`-produced hit with a fixed safe destination, `classes` contains static class labels, `payload` is `None`, and `payload_sha256` is a digest (`src/harness_bench/egress.py:24-31,84-93`); the tested matched value was absent from its representation (`tests/test_egress.py:140-147`). But `destination` is unconstrained caller input and an ordinary dataclass field. Passing the same synthetic matched value as `destination` made `repr(verdict)` contain it, even though the verdict was withheld. A clean verdict's default repr also includes its entire raw `payload` (`src/harness_bench/egress.py:24-31,75-76,93`). No log emission was found in this slice, so this is a log *exposure path*, not evidence that a log was written. Restrict destination to a safe backend identifier and exclude payload and untrusted destination text from repr/log records; keep only the digest, class and fixed destination id in telemetry. |

**Release and forbidden constructs.** For a verdict returned by `check` with a hit, `withheld` is true, `payload` is `None`, and `Verdict.release` returns before calling the backend (`src/harness_bench/egress.py:33-45,93`). The baseline `tests/test_egress.py::test_a_withheld_payload_never_reaches_the_backend` passed, and my release mutant was caught below. The public `Verdict` constructor is not a capability boundary: a caller can fabricate a clean verdict or call a backend directly, which makes F2 consequential. Inspection of the changed Python, fixtures, mutation manifest and audit entry found no socket, listener, network request, subprocess invocation, or access to a real credential. `urllib.parse` in `tests/test_egress.py:9,58` is local encoding; `token_hex` at `tests/test_egress.py:11,50-52,69-74,83-85,92-95,109-110,121-124` makes inert synthetic values. `egress.py` imports only the pure `encodings` helper from the credential module (`src/harness_bench/egress.py:16-17`). This is a static review of this diff, not a claim about later GW-I code.

## Independent bypass probes

I created one detached throwaway worktree of commit `a45fbfa`, used only inert synthetic strings and a fake in-process backend, and restored the source between mutants. The unmodified baseline command `uv run pytest -q -p no:cacheprovider tests/test_egress.py` passed **21 tests**. Each mutant below was tried alone with that exact command; these are independent of the author's `tests/mutations/egress.json`.

| Mutant or bypass input | Result under the requested test command | Named test that caught it |
| --- | --- | --- |
| M1 — change `Verdict.release`'s guard at `src/harness_bench/egress.py:43` so a withheld verdict calls the backend. | **1 failed, 20 passed.** | `tests/test_egress.py::test_a_withheld_payload_never_reaches_the_backend` |
| M2 — change `_exact` at `src/harness_bench/egress.py:50` to check only raw strings, removing base64 and URL forms. | **3 failed, 18 passed.** | `tests/test_egress.py::test_a_credential_value_is_withheld_in_each_encoding[base64]`, `[url]`, and `tests/test_egress.py::test_a_planted_canary_is_withheld[base64]` |
| M3 — retain raw and base64 canary matching but remove its URL-encoded form at `src/harness_bench/egress.py:91`. | **21 passed: not caught.** The committed canary test covers only plain and base64 (`tests/test_egress.py:117-126`); its alphanumeric/hyphen canary would not exercise a distinct URL form. This is a test gap; the unmodified implementation does call `_exact` for canaries. | **Not caught** |

After restoring `egress.py`, direct in-process probes on the original code produced the F1 bypass results. I separately ran `uv run pytest -q -p no:cacheprovider tests/test_architecture.py::test_only_the_gateway_reaches_a_judge_backend_and_only_beside_egress` with the temporary direct-call gateway module: **1 passed**, demonstrating F2. I deleted that module and removed the detached worktree after confirming it was clean. No full suite, `tests/e2e`, `-m ""`, network call, listener, or real secret was used.

**Clears the security veto:** no. F1 and F2 are verified trust-boundary failures. D&P's separate R-60 review of operator identifier patterns is still required; this security review does not stand in for it. The residual risk is that later gateway wiring could send transformed sensitive content or bypass the gate while the current tests remain green.
