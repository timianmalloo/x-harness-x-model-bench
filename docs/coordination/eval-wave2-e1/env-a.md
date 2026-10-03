---
id: brief-eval-env-a
title: "Brief ENV-A: hermetic tests never read the operator's credential (the ambient-credential fix)"
type: plan
status: proposed
owner: "@timianmalloo"
links:
  - { to: coordination-eval-wave2-e1-briefs, rel: implements }
review-by: "2026-10-17"
summary: "An autouse fixture that clears every credential variable for tests not marked credentials, with a test that proves the three Q0-join failures pass with the token set; Grok grok-4.7 high, one turn."
---

# ENV-A: the ambient-credential fix

**Harness** Grok via `coord-runner` (Leader, R-87), `grok-4.7`, `--reasoning-effort high`, `XAI_API_KEY` removed · **contract** `env-a.contract.json` · **deadline** 1,200 s · **dispatch** one turn, red then green · **budget** 30 calls · 80k · 1 · 0.5 h · **fallback** a red-only end or a failed served-model read: the green follow-on as Claude Sonnet (`model: sonnet`, served `claude-sonnet-5-5`) in the same tree (R-92 is the Owner review).

**The class** (`docs/lessons/defect-classes.md`, the candidate "a hermetic test reads an ambient credential from the operator's shell", class id **ENV-C**, renamed from a duplicate `ENV-A`; cite ENV-C in your report and commits): with `HB_CLAUDE_OAUTH_TOKEN` set to a dummy value, three tests fail on `main`: `tests/test_gateway_headless.py::test_t_gw_10_the_credential_is_present_during_the_call_and_gone_after_it`, `::test_t_gw_10_the_credential_is_gone_after_a_timeout_and_after_an_exception_past_the_copy`, `tests/test_profiles.py::test_the_launcher_reports_no_model_setter_and_a_copied_login[claude-code]`.

## Owned paths
`tests/conftest.py` (E1 owner: this track; another track needs a seam request), `tests/test_env_isolation.py` (new). **Not yours:** `tests/test_profiles.py` (X-E's in E1), `tests/test_gateway_headless.py`; the fix must make them pass **without editing them**.

## Depends on
TOOL-GSM joined (this is a later Grok dispatch, R-92).

## Work
1. **Sweep first, recorded in the report:** `git grep -n -E "OAUTH_TOKEN|_API_KEY|GH_TOKEN" -- tests src/harness_bench/profiles.py` and the profile denylist (`profiles.DROP_EXACT`, `profiles.DROP_PREFIXES`). The credential list is **one** definition: import it from the production source if one exists; if none does, write it once in `conftest.py` and say so.
2. **Red:** `tests/test_env_isolation.py` sets each listed variable to a dummy value with `monkeypatch.setenv` in a subprocess-free way (re-run the three named tests through `pytest.main` in-process, or call their bodies) and asserts they pass; plus one test that a test marked `credentials` still sees the variable. Red today by assertion.
3. **Green:** an autouse fixture in `tests/conftest.py` that `monkeypatch.delenv(name, raising=False)` for every listed name, skipped for tests marked `credentials`.

## Acceptance items
1. The three named tests pass with `HB_CLAUDE_OAUTH_TOKEN=dummy` set in the shell, and with it unset.
2. A mutant that removes the fixture is killed by `tests/test_env_isolation.py`.
3. The defect-class text for the Coordinator: instances, sweep result, control (this fixture and its test), status `controlled` proposed.

## Exit
README §3 join gate, run **twice**: with the token unset and with `HB_CLAUDE_OAUTH_TOKEN=dummy`. `python tools/grok_served_model.py <session dir>` exits 0. Report per README §4.
