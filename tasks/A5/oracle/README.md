# A5 oracle

A5 is the authored task for Scenario 1 ("Specify from an ambiguous prompt") on ai-de's AiDe.Core:
"Users want to see what changed". The prompt is deliberately underspecified; the scripted user
answers the 4 key clarification dimensions from `clarifications.yaml`.

| File | What it is | Who reads it |
| --- | --- | --- |
| `clarifications.yaml` | The 4 annotated key clarifications (scope, granularity, source of truth, refresh) and default reply | The scripted user (`scripted_user`), the `clarify` grader |
| `rubric.md` | 9-item judge rubric scoring the specification against the 4 clarifications and /specify DoD | The LLM `judge` grader (not wired into `bench/metrics.yaml` in this slice, same as A1/A4) |
| `evidence.md` | Detailed discrimination proof and test run logs | The auditor / verification pass |
| `reference/docs/specs/what-changed-view.md` | Complete three-layer reference specification (`/specify` conformant) | Discrimination proof, judge reference |
| `reference/controls/control_scope_all_lanes.md` | Negative control: covers every agent's lane / the whole repository instead of the current lane's own worktree | Discrimination proof for clarification 1 (scope) |
| `reference/controls/control_full_diff_content.md` | Negative control: shows the full line-by-line diff content of each file instead of a file-level list | Discrimination proof for clarification 2 (granularity) |
| `reference/controls/control_audit_log_source.md` | Negative control: reconstructs the list from the recorded tool-call/audit log instead of computing it from git | Discrimination proof for clarification 3 (source of truth) |
| `reference/controls/control_live_streaming.md` | Negative control: a live-updating, continuously-refreshing view instead of an on-demand snapshot | Discrimination proof for clarification 4 (refresh) |
| `../tests/test_a5_hidden.py` | 7 hidden unittest assertions checking file presence, required sections, all 4 clarification dimensions, and Gherkin ACs | The `correctness` grader |

## Authoring choices

- **Underspecified requirement:** the prompt is the exact one-line prompt from the authored-task
  inventory: "Users want to see what changed". In Scenario 1, the prompt does not say whose changes
  ("what changed" could mean one agent's own lane, every lane, or the wider repository), how much
  detail to show (a file list or the full diff text), where the answer comes from (git, or the
  agent's own recorded tool-call/audit trail), or whether the view stays current on its own.
- **4 clarifications**, grounded in the real ai-de `AgentPlane/WorktreeProvisioner.cs` (pinned at
  the D1/D2 commit): its `Inspect()` method already asks git about one lane's own worktree, but
  today reduces the answer to two booleans (`HasUncommittedChanges`, `HasUnpushedWork`) used only to
  decide whether the tree is safe to remove — it names none of the changed files. The clarifications
  extend that exact seam rather than inventing an unrelated one:
  1. *scope:* the current lane's own worktree only, never every lane or the repository.
  2. *granularity:* a file-level list with a change kind (added/modified/deleted), never the full
     diff content.
  3. *source of truth:* computed from git (as `Inspect()` already does), never reconstructed from
     the tool-call or audit log.
  4. *refresh:* computed on demand, as a snapshot, never a live-updating stream.
- **Workspace:** the two real files the feature would extend — `AgentPlane/WorktreeProvisioner.cs`
  and `Workbench/AgentWorktree.cs` — copied byte-for-byte from `tasks/D2/workspace/` (already
  vendored there at the same pin), plus a minimal `net10.0` csproj and the upstream `LICENSE`.
- **Hidden tests:** Python stdlib `unittest` in `tests/test_a5_hidden.py`. Every clarification check
  pairs a **positive** assertion (the decided content is present) with a **negative** assertion
  scoped to the "In scope" half of the In scope / Out of scope section only — so a decision correctly
  named as an explicit non-goal never trips it, but a spec that put the wrong decision *in scope*
  does. This targets the decided content directly rather than a single on-topic keyword any
  plausible answer would contain (the weak shape A4's `test_clarification_scope` used: `any(term in
  text for term in ("station", "derived", "planform"))`, which no wing spec can fail).
- **Not authored in this slice:** `heldout_questions.yaml` (matcher precision/recall measurement).
  It is not read by anything `bench validate` or the graders check for A5 — the one test that reads
  a `heldout_questions.yaml` (`tests/test_heldout_matcher.py`) is hardcoded to `tasks/A1/oracle`, and
  tasks/README.md's oracle contract for scenario 1 lists rubric, reference spec and
  `clarifications.yaml`, not a held-out set. Authoring one is unrequested scope beyond this task's
  Done-when; `oracle/clarifications.yaml`'s 4 questions and replies are simplifier-plain enough not to
  need a separate labelled matcher-evaluation set to be usable.

## Discrimination proof

Evaluated on Windows 11 (CPython 3.14.6 via `uv run`), running the task's own oracle command,
`{python} -m unittest -v test_a5_hidden`, in a grading copy (`workspace/` plus `tests/`), with
`docs/specs/what-changed-view.md` replaced by each working copy in turn. Full command transcripts
are in `evidence.md`.

| Working copy | Exit | Summary | pass@1 | Failing tests |
| --- | --- | --- | --- | --- |
| base (`workspace/` as shipped) | 1 | `Ran 7 tests` · `FAILED (failures=7)` | 0 | all 7 (spec file does not exist) |
| reference (`reference/docs/specs/what-changed-view.md`) | 0 | `Ran 7 tests` · `OK` | 1 | none |
| control: scope → all lanes / repository | 1 | `Ran 7 tests` · `FAILED (failures=1)` | 0 | `test_clarification_scope` only |
| control: granularity → full diff content | 1 | `Ran 7 tests` · `FAILED (failures=1)` | 0 | `test_clarification_granularity` only |
| control: source → tool-call/audit log | 1 | `Ran 7 tests` · `FAILED (failures=1)` | 0 | `test_clarification_source_of_truth` only |
| control: refresh → live-updating stream | 1 | `Ran 7 tests` · `FAILED (failures=1)` | 0 | `test_clarification_refresh` only |

The hidden tests fail on the base, pass on the reference, and — for every one of the 4
clarifications — reject a plausible wrong answer that decided that one dimension wrongly while
getting every other item right; each control fails **only** the check for the dimension it got
wrong (verified by name above, not just by count), which is the discrimination the brief asked for.

To reproduce by hand: copy `workspace/` and `tests/` into one empty folder, drop in a spec as
`docs/specs/what-changed-view.md` (the reference, or any one control), and run
`python -m unittest -v test_a5_hidden` there.

## Portability (ADR-0013 Amendment 1)

The oracle command invokes Python directly using forward slashes:
`command: ["{python}", "-m", "unittest", "-v", "test_a5_hidden"]`. It does not invoke `cmd.exe` or
any shell. All paths in the hidden tests use `pathlib.Path` with forward-slash literals
(`docs/specs/what-changed-view.md`). Proven on Windows.
assume: runs identically on macOS/Linux using the Python 3 standard library (`pathlib`, `unittest`);
confirm by running the same command on a macOS runner in cross-platform CI. If false, `pathlib.Path`
on POSIX still resolves the same forward-slash literal, so the likely failure mode is a
locale/encoding difference in `Path.read_text(encoding="utf-8")`, not the path syntax itself.

## Budget and headroom

- Budget: 15 minutes (900 s).
- Reference test suite execution time: 0.001 s (measured, see `evidence.md`).
- Headroom: > 99.99%.
