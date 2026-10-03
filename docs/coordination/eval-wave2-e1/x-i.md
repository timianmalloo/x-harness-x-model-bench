---
id: brief-eval-x-i
title: "Brief X-I: security task S1 (E1 build)"
type: plan
status: proposed
owner: "@timianmalloo"
links:
  - { to: coordination-eval-wave2-e1-briefs, rel: implements }
  - { to: design-eval-security-tasks, rel: depends-on }
  - { to: design-eval-seam-contracts, rel: depends-on }
review-by: "2026-10-17"
summary: "X-I authors tasks/S1 per W1-I rev 2 on Sonnet, then, in a follow-on after X-F joins, proves the reference and naive solutions through the real grader."
---

# X-I: security task S1

**Session** `x-i-e1e4` · **branch** `build/eval-x-i` · **harness** Claude Code Agent tool, `model: sonnet` (served `claude-sonnet-5-5`, R-91) · **budget** 200 calls · 200k · 2 sessions (authoring; the real-grader follow-on after X-F joins, rebased on `main`) · 3 h · **fallback** a fresh Sonnet session from this brief.

**Design:** `docs/design/eval-security-tasks.md` (W1-I rev 2, on `main`; S1 only, S2 is E4). **W0 rev 5:** §2 (variants, `clauses.json`, the `ready` order, overlay rule). **W0 rev 4:** sections 1, 2, 3 (including "Section 3 additions (rev 4)": case ids, `{state_dir}`, what the app-output capture measures).

## Owned paths
`tasks/S1/**`, the `S1` entry of `bench/bom.yaml` (its hunk only), the tests W1-I names for S1 (`tests/test_s1_*.py` or as the design places them). **Not yours:** any `src/` file, `tasks/README.md` (seam request).

## Depends on
W1-I ✓ for authoring. The follow-on needs **X-F joined** (the real probe host and grader).

## Acceptance items
1. `bench validate` passes the EV-1 contract for S1; no listed `latent_terms` term in `prompt.md`; the base pinned to a full commit (`test_s1_pin_is_a_full_commit`), `NOTICE.md` and `LICENSE` with a test (RV-SEC W1-I 6); `test_s1_declares_no_build_and_no_network_names`.
2. Case ids match `^[a-z0-9][a-z0-9_-]{0,31}$` (W0 rev 4 §3); S1's `inj-*`, `authz-1..3`, `leak-1..3` already do.
3. **RV-TA W1-I D1 (major):** the variant test runs against the **real** host before S1 leaves `stub`, or its clauses join `test_s1_real_host_reproduces_the_expected_values` (the follow-on).
4. **RV-TA D2, D3 (with the skeleton commit):** m12's clause pinned to one value (or both listed with a membership assertion); a wrong-app fixture for test 7 (accepts a prefix token); m9's path stated as absolute-to-deliverable or tied to the cwd rule.
5. **RV-SEC W1-F rev 3, 6 (W0 rev 4 §3):** `leak-2`'s text says the probe scans the host's fds 1 and 2 only and measures accidental logging, not a deliberate leak through a child process or a file. If the built host lacks the app-output capture, drop `leak-2` and re-derive the expected values for 7 probes; never default a case to `blocked`.
6. RV-SEC W1-I 3: residual R-S3 stated (leak scope: `leak-3` scans `{state_dir}` and changed files only).
7. Follow-on: the reference passes its hidden tests and every probe; the naive passes the functional tests and fails at least one probe, both through X-F's real grader; the expected values W1-I derives (the naive's `exploit_probes_blocked` `"0.3750"` is hand-derived and Inferred until measured) are confirmed or corrected with provenance (GLD-A).
8. Not yours: readiness refusing `ready` without a real-host discrimination record (RV-TA D4) is X-E's; S1 stays `draft` until X-E's record exists.
9. **W0 rev 5 §2 (SR-E2 1): the variants file is data.** `tasks/S1/oracle/variants.py` assigns one top-level literal `VARIANTS = {<name>: {"flips": [...], "clauses": {...}, "edits": [{"file", "old", "new"}]}}` (names `^[a-z0-9]{1,16}$`; each `old` occurs exactly once in its file). The bench reads it with `ast.literal_eval` and never imports it; your `apply()` may stay in the file for your own tests. When a variant declares `clauses`, S1's check writes `clauses.json` (`{<case id>: <clause>}`) into its `--evidence` directory. Test: `ast.literal_eval` of the assignment equals the table your tests use.
10. **W0 rev 5 §2 (SR-E2 3): the `ready` order.** `status:` is inside the task version hash. The order is: set `status: ready`, run `bench discriminate S1`, commit `tasks/S1/` and the record in one commit. W1-I's "advance to `ready` only when the record exists" means this order. In E1 that is X-E's join, not yours: you leave S1 at `draft`.

## Exit
README §3 join gate (authoring and follow-on). Report per README §4.
