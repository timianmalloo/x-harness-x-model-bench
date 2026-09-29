# C2 oracle

Reference solution: `reference/docs/architecture.md`. It is not in the workspace.

`rubric.md` is the judge rubric; it cites R2ABench's L1/L2 layer shape by name only (R-82
DR-W5-2 refuses R2ABench as a source: no licence, private/403 dataset links, a keyed judge).

`evidence.md` records the fail-on-base and pass-on-reference unittest runs, and the two-control
discrimination proof for the decided-content checks, in the pattern `tasks/A5` uses: one committed
negative control per decided-content check under `reference/controls/`, each otherwise a complete,
structurally-passing architecture note that gets exactly one decided fact wrong.

Hidden tests are `../tests/test_c2_hidden.py`, overlaid by the correctness grader
(`runner: unittest`). Three checks are structural (`test_architecture_document_present`,
`test_architecture_required_sections`, `test_decision_names_alternatives`) — file exists, required
headings have non-empty bodies, and the `## Decision` section names an alternative. They do not
score the prose; the judge does.

The other two checks are content checks, targeting one decided fact each, carried forward from the
given spec (B2's reference spec, consumed here as the given per R-82: "scenario 3 consumes what
scenario 2 produces"):

- `test_comparison_source_is_the_repository_not_the_daemon` — the architecture must state the
  observed-revision read is from the repository, in contrast to the daemon's own last-known state.
  Same decided fact as B2's own content check 1, now at the architecture (component-boundary)
  level rather than the spec-prose level.
- `test_prober_does_not_repair_the_drift_itself` — the architecture must state that the prober
  itself never repairs/fixes/re-extracts to close a drift. Same decided fact as B2's own content
  check 2, now at the architecture (component-boundary) level.

## Plausible wrong answer, per content check

`reference/controls/control_daemon_state_source.md` — otherwise a complete, structurally-passing
architecture note (all 8 required headings present and non-empty, `## Decision` names
alternatives), wrong on exactly one decided fact: `IRevisionProbe` returns the daemon's own cached
last-known revision instead of reading the repository directly. Fails only
`test_comparison_source_is_the_repository_not_the_daemon`.

`reference/controls/control_prober_self_repairs.md` — otherwise a complete, structurally-passing
architecture note, wrong on exactly one decided fact: `FreshnessProbeService` re-runs extraction
for the drifted scope itself, through a new `IExtractorAdapter` boundary, before raising the
incident. Fails only `test_prober_does_not_repair_the_drift_itself`.

See `evidence.md` for the exact commands, working directories, and per-test results.
