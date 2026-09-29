# B2 oracle

Reference spec: `reference/docs/specs/freshness-prober.md`. It is not in the workspace.

`rubric.md` is the judge rubric for the /specify definition of done named in `task.yaml`. `evidence.md` records the fail-on-base and pass-on-reference unittest runs, and the two-wrong-answer discrimination proof for the content checks.

Hidden tests are `../tests/test_b2_hidden.py`, overlaid by the correctness grader (`runner: unittest`). Two checks are structural (`test_spec_file_present`, `test_spec_required_sections`) — file exists, required headings have non-empty bodies. They do not score the prose; the judge does.

The other two checks are content checks, added because a structural-only check "can fail for a plausible wrong answer" is not the bar (A4's finding: a single keyword any on-topic text contains measures nothing). Each targets one decided fact named in `prompt.md`, not a generic keyword:

- `test_comparison_source_is_the_repository_not_the_daemon` — the primer's own point (`docs/architecture.md`, "Failure and resilience": *"not by the daemon's own last-event view (which would read fresh while the graph rots)"*) is that the Freshness Prober exists **because** the obvious self-referential staleness check is wrong. A spec that only says "detects stale data" without naming the repository as the independent comparison source, in contrast to the daemon's own view, has dropped the one fact that explains why the capability exists at all.
- `test_prober_does_not_repair_the_drift_itself` — the prompt requires the spec to state the prober does not itself repair the drift. A spec that lets the prober re-extract/fix/correct the drift on its own has taken over the Ingestion Scheduler's job.

## Plausible wrong answer, per content check

Both fixtures below are otherwise complete (all 7 required headings present and non-empty, Gherkin ACs, ISO 25010 table) — on-topic, structurally passing, and wrong on exactly one decided fact. They are not committed to the task folder (they exist only to prove discrimination); the exact text and run below is the record.

**Wrong answer 1 — self-referential comparison** (fails check 1 only). Core scenario reads:

> "The Freshness Prober periodically checks whether each scope's indexed data is still current. It compares the workspace's current index snapshot against **the daemon's last known state** for that scope, and if the two disagree it raises a health incident for the scope. The comparison never repairs the drift itself; a later extraction run must fix it."

This gets the "does not repair" fact right but compares against the daemon's own last-known state instead of the repository — exactly the self-referential design the primer rejects.

**Wrong answer 2 — self-repairs the drift** (fails check 2 only). Core scenario reads:

> "The Freshness Prober compares each scope's repository-observed revision to its indexed revision. It reads the repository directly and never substitutes the daemon's own last-known state for that read, which is why the check catches what the daemon's own view cannot. When the two revisions disagree, **the prober immediately re-runs extraction for that scope to bring the index back in sync**, then raises an incident recording that it happened."

This gets the repository-vs-daemon fact right but has the prober repair the drift itself, which the primer never grants it.

See `evidence.md` for the exact commands, working directories, and counts.
