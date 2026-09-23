---
id: defect-classes
title: "Defect-class register"
type: doc
status: accepted
owner: "@timianmalloo"
tags: [lessons, defect-classes, continuous-improvement]
links:
  - { to: arch-harness-bench, rel: relates-to }
  - { to: design-run-lifecycle-model, rel: relates-to }
review-by: "2026-12-22"
summary: >-
  The project's register of defect classes: the recurring shapes of things that go wrong here, what
  each one survives, and the control that now fails when the shape recurs. Read at grounding;
  appended to on every defect, correction or falsified assumption.
---

# Defect-class register

*Governed by `continuous-improvement.md` (CI1–CI12). **One entry per class, not per bug.** A new occurrence of an existing class appends to that class's Instances and triggers a control review. Read this at grounding (CI5) for the area you are working in.*

**How to use this file**
1. On any defect, correction, or falsified assumption, answer **class → sweep → derive → prevent** in writing (CI2).
2. Find the matching class below, or add one. Append the instance.
3. Climb the control ladder (CI6) and record the highest rung that actually holds: *make it impossible* > *automated control* > *always-loaded instruction* > *knowledge doc* > *register entry only*.
4. A control is not a control until it has been **observed failing** on the un-fixed code.

**Status counts:** controlled 1 · partially-controlled 1 · uncontrolled 0 (project classes)
**Recurrence since last review:** 4 instances of MOD-A in one session: the control was built after the fourth.

---

## Project classes

### MOD-A — A seeded model variant that cannot fail, or fails for the wrong reason
- **Signature:** a seeded-bug variant of a TLA+ model reports `NOT rejected`, or is rejected by an invariant other than the one it targets. The model looks verified; the targeted invariant proves nothing.
- **Why it survives:** the real design passes, so the model looks correct. TLC stops at the first violation, so a variant caught by the *wrong* invariant still prints "violated". A later fix (a new invariant, a new guard) can silently change which invariant catches an older variant.
- **Instances:**
  - `2026-09-23` design gate round 2 — the new `NoOutcomeWhileRunning` pre-empted `launch_after_outcome` and `reconcile_no_wait`; both still showed "violated", but not by their targets.
  - `2026-09-23` model v2 — `archive_live` made vacuous by the kill → record fix; `ignore_orphans` vacuous (replaced by `NoLaunchBesideOrphan`).
  - `2026-09-23` model v1/v2 — a guard reading a history variable (`prompts = 0`) hid `relaunch_prompted` twice.
  - `2026-09-23` model v1 — two guards for one invariant masked `exceed_parallelism`.
- **Sweep:** all 22 variants re-run after the isolation change; every one is rejected by its own target.
- **Control:** `tools/check_models.py` checks each safety variant against its target invariant alone (`only_invariant`) and each liveness variant against its target property alone (`only_property`), asserting the target's name in TLC's output. `tests/test_check_models.py::test_every_checked_property_has_a_seeded_variant` (observed failing when a variant was removed, 2026-09-23) and `test_variant_config_checks_only_its_target`. Guards never read history variables (stated in the model design).
- **Status:** `controlled`

### INS-A — Progress hidden by buffered output
- **Signature:** a long check writes to a log file that stays empty until the process exits, so nobody can tell which stage is slow or hung.
- **Why it survives:** on a terminal, output is line-buffered and looks fine; redirected to a file, it is block-buffered.
- **Instances:**
  - `2026-09-23` `check_models.py` redirected to a log: 10 minutes with an empty log and TLC at 43 GB; the run was stopped blind.
- **Control:** every result line in `check_models.py` prints with `flush=True`. `NONE YET` as a test; the upgrade trigger is a second instance in another script.
- **Status:** `partially-controlled`

---

## Inherited classes (seeded from the pack)

*Observed in production across independent codebases running the AI-Forward pack (`continuous-improvement.md` §6). Each is **uncontrolled here until this repo builds the control** — that is the work, not the copying.*

| ID | Class | Signature | Why it survives | Control to build | Status here |
|---|---|---|---|---|---|
| **DM-A** | One quantity, two homes | A value produced in two places; a new call site wires to whichever it found first | Both implementations pass their own tests; nothing compares them | Derive once (DM7); cross-surface consistency test | `uncontrolled` |
| **DM-B** | Stored fact that nothing writes | A persisted flag beside a function computing the same thing | Reads succeed and return a plausible default | Reader/writer trace (DM15); stored-equals-derived test | `uncontrolled` |
| **DM-C** | Persisted field with no compute reader | Stored, entered, round-tripped, tested — read by nothing that computes | Round-trip tests pass perfectly | Reader trace: write / CRUD / schema / **compute** | `uncontrolled` |
| **DM-D** | Grain inferred, not declared | Period/owner derived from a date rule; exceptions break it | Works for every non-exceptional record | Declare the grain; put it in the key (DM8) | `uncontrolled` |
| **DM-E** | Semi-additive measure summed across time | Balances/positions/headcounts added over periods | The arithmetic is valid; only the meaning is wrong | Declare additivity per measure (DM9) | `uncontrolled` |
| **DM-F** | Type-1 where Type-2 was needed | A mutable attribute silently rewrites the meaning of past records | Nothing errors; history just changes | History rule per attribute (DM10); point-in-time test | `uncontrolled` |
| **E2E-A** | Field reaches the DTO but not the wire | Present in model, service, client type, column list; missing from the projection | Every layer's own test passes | Write the surface list first (E7); one end-to-end assertion per field | `uncontrolled` |
| **E2E-B** | Declared shape with no write path | A facet/status/enum/route declared and never set | Telemetry reports "nothing to do" — true, for the wrong reason | Test that the shape is written under the claimed condition | `uncontrolled` |
| **E2E-C** | Green suite, broken surface | All units green; the page never renders; the composition root is never exercised | Units construct their subject by hand | One proof through the real composition root to the rendered surface (E11) | `uncontrolled` |
| **E2E-D** | Component tests that can't see each other | Every part correct against its own expectation; parts disagree | Per-component coverage is high | Cross-surface consistency test on one seeded scenario (E12) | `uncontrolled` |
| **E2E-E** | The gate passed, its contents didn't | Several checks in one block; only the last exit code propagates | The gate is green | Run each control independently; assert each reports its own status (E13) | `uncontrolled` |
| **E2E-F** | Exit code taken as result | A command returned success; the state was never read back | Success is success-shaped | Read back the state and assert on it (E14) | `uncontrolled` |
| **E2E-G** | Reachability not verified | The surface exists but nothing links to it — or a link points at nothing | The feature works if you can get to it | Assert the navigation path to any new surface (E10) | `uncontrolled` |
| **RIG-A** | Own-code shape asserted from memory | "This type has that member" — written in a design, never opened | Designs aren't compiled | Read the file or label Inferred (E15); review opens the cited file | `uncontrolled` |
| **RIG-B** | Delegated inventory cited as fact | A sub-agent's counts/listings enter an artifact unverified | Sub-agent output is fluent and specific | Spot-check before citing (E16) | `uncontrolled` |
| **RIG-C** | Sweep stopped at the instance | The fix works; the sibling ships the same bug days later | The reported symptom is gone | class → sweep → derive → prevent (CI2) | `uncontrolled` |
| **REC-A** | Stale record / overstated claim | A comment, status table or doc asserts something that was true once | Documentation isn't executed | Re-verify records you touch (E17); correct overstatements in their own change | `uncontrolled` |
| **OPS-A** | Migration compiles but is never applied | The migration builds; the deployer doesn't run it | The build is green | Migrate-before-publish enforcement; exercise the down path (DM16) | `uncontrolled` |
| **UX-A** | Archetype mismatched to the task | A dashboard archetype on a data-entry task: everything visible, nothing sequenced | Each component is individually fine | Verify archetype vs JTBD on changes to *existing* screens too | `uncontrolled` |
| **UX-B** | Shipped with data-only states | Loading/empty/error never designed; "it looked fine with data" | Demos and tests use populated fixtures | Complete component state set as a design gate (U9) | `uncontrolled` |
