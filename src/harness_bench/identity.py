"""Content-addressed engine identity and bounded run-side drift checks (ADR-0017).

One class per source file. Manifest values use the plan's existing hash recipes;
run and grade projections derive from that table, never from stored classes.
"""

import hashlib
import sys
import time
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Literal, NamedTuple

from harness_bench import plan, profiles
from harness_bench.errors import BenchError
from harness_bench.ledger import canonical

SCHEMA = "bench-identity/1"


class CheckResult(NamedTuple):
    diff: list[str]
    rechecked: bool

# Pattern: Table-driven classification (ADR-0017 Amendment 1; W0 §9).
# Explicit file keys keep a new file red until its class is reviewed.
CLASSES: Mapping[str, Literal["run", "grade"]] = {
    "__init__.py": "run",
    "archive.py": "run",
    "cli.py": "run",
    "config.py": "run",
    "driver.py": "run",
    "engine.py": "run",
    "errors.py": "run",
    "gitsafe.py": "run",
    "host.py": "run",
    "ledger.py": "run",
    "lifecycle.py": "run",
    "oslock.py": "run",
    "plan.py": "run",
    "preflight.py": "run",
    "procs.py": "run",
    "profiles.py": "run",
    "tools.py": "run",
    "workspace.py": "run",
    "scripted_user/__init__.py": "run",
    "scripted_user/clarifications.py": "run",
    "scripted_user/log.py": "run",
    "scripted_user/matcher.py": "run",
    "scripted_user/server.py": "run",
    "telemetry/__init__.py": "run",
    "telemetry/claude_code.py": "run",
    "telemetry/codex.py": "run",
    "telemetry/copilot.py": "run",
    "telemetry/normalize.py": "run",
    "board.py": "grade",
    "composites.py": "grade",
    "egress.py": "grade",
    "stats.py": "grade",
    "status.py": "grade",
    "views.py": "grade",
    "gateway/__init__.py": "grade",
    "gateway/backend.py": "grade",
    "gateway/calibration.py": "grade",
    "gateway/pipeline.py": "grade",
    "gateway/request.py": "grade",
    "gateway/schema.py": "grade",
    "gateway/scrub.py": "grade",
    "gateway/store.py": "grade",
    "gateway/schemas/summary-claims.v1.json": "grade",
    "gateway/schemas/verdict-set.v1.json": "grade",
    "grade/__init__.py": "grade",
    "grade/_changes.py": "grade",
    "grade/architecture.py": "grade",
    "grade/clarify.py": "grade",
    "grade/coordination.py": "grade",
    "grade/correctness.py": "grade",
    "grade/cost.py": "grade",
    "grade/drift.py": "grade",
    "grade/formal.py": "grade",
    "grade/judge.py": "grade",
    "grade/mutation.py": "grade",
    "grade/process.py": "grade",
    "grade/rigor.py": "grade",
    "grade/runner.py": "grade",
    "report/__init__.py": "grade",
    "report/cli_table.py": "grade",
    "report/context_growth.py": "grade",
    "report/credentials.py": "grade",
    "report/html.py": "grade",
    "report/html_builder.py": "grade",
    "report/judges.py": "grade",
    "report/model.py": "grade",
    "report/pack_improvement.py": "grade",
    "report/lean_section.py": "grade",
    "report/summaries.py": "grade",
    "report/assets/report.js": "grade",
    # W0 §9 includes these future phase modules and the two landed D1/F0 modules.
    "atomic.py": "run",
    "identity.py": "run",
    "resume.py": "run",
    "campaign.py": "grade",
    "power.py": "grade",
    "verdicts.py": "grade",
    "lean.py": "grade",
    "gates.py": "grade",
    "discriminate.py": "grade",
    "readiness.py": "grade",
    "synthetic_agent.py": "grade",
    "grade/property.py": "grade",
    "grade/bench_check.py": "grade",
    "grade/_env.py": "grade",
    "report/campaign_section.py": "grade",
    "grade/rework.py": "grade",
    "alarm.py": "grade",
    "grade/noguess.py": "grade",
    "grade/diffstats.py": "grade",
}

# Explicitly retired on landing; stale() prevents a landed key lingering here.
PLANNED: frozenset[str] = frozenset()

# R-94 condition 3: exactly three validate-time edges, not cell-path imports.
RUN_IMPORTS_GRADE_ALLOWED: Mapping[tuple[str, str], str] = {
    ("config.py", "egress.py"): "validate-time check, not on a cell's path; owner X-A1/X-A3; review 2027-10-03; remove when the validators leave `config.py`",
    ("config.py", "gateway/backend.py"): "validate-time check, not on a cell's path; owner X-A1/X-A3; review 2027-10-03; remove when the validators leave `config.py`",
    ("config.py", "gateway/scrub.py"): "validate-time check, not on a cell's path; owner X-A1/X-A3; review 2027-10-03; remove when the validators leave `config.py`",
}


def catalog_hash(root: Path) -> str:
    """R-59 c1: tree_hash over metrics.yaml and rubrics/, relative to bench/."""
    from harness_bench.plan import tree_hash

    bench = root / "bench"
    rubrics = [p for p in (bench / "rubrics").rglob("*") if p.is_file()] if (bench / "rubrics").is_dir() else []
    return tree_hash(bench, [bench / "metrics.yaml", *rubrics])


def _source_files(root: Path) -> set[str]:
    src = root / "src" / "harness_bench"
    return {p.relative_to(src).as_posix() for p in src.rglob("*")
            if p.is_file() and "__pycache__" not in p.relative_to(src).parts}


def unclassed(root: Path, classes: Mapping[str, str], planned: frozenset[str]) -> list[str]:
    """Return disk files without a class; root is the repository root."""
    return sorted(_source_files(root) - classes.keys())


def stale(root: Path, classes: Mapping[str, str], planned: frozenset[str]) -> list[str]:
    """Return ghost class entries and planned entries that have landed."""
    files = _source_files(root)
    return sorted((classes.keys() - files - planned) | (files & planned))


def manifest(root: Path, tasks: Sequence[str], builds: Mapping[str, Mapping] | None = None, *,
             which: Literal["run", "grade"] | None = None) -> dict:
    """One component per input at this instant; no builds keys when builds is None. With `which`, only that side's
    inputs are read: grading never reads a run-side input such as today's profile files."""
    readers = _readers(root, tasks, builds)
    if which is not None:
        readers = {key: read for key, read in readers.items() if _class(key) == which}
    return {"schema": SCHEMA, "components": {key: read() for key, read in readers.items()}}


def identity_hash(m: dict) -> str:
    """The manifest's name, using the ledger's canonical content-address recipe."""
    return hashlib.sha256(canonical(m)).hexdigest()


def _class(key: str) -> Literal["run", "grade"]:
    if key.startswith("src/harness_bench/"):
        return CLASSES[key.removeprefix("src/harness_bench/")]
    if key in {"catalog", "prices", "gateway"}:
        return "grade"
    if key in {"bom", "uv.lock", "platform", "python"} or key.startswith(("profiles/", "builds/", "tasks/")):
        return "run"
    raise ValueError(f"unclassified identity component: {key}")


def side(m: dict, which: Literal["run", "grade"]) -> dict:
    """Derive a disjoint projection; unknown components fail closed."""
    if which not in {"run", "grade"}:
        raise ValueError(f"unknown identity side: {which}")
    return {"schema": m["schema"], "components": {k: v for k, v in m["components"].items() if _class(k) == which}}


def _display(key: str) -> str:
    return key.removeprefix("src/harness_bench/")


def diff(a: dict, b: dict) -> list[str]:
    """Sorted operator-facing relative component names, including additions/removals."""
    before, after = a["components"], b["components"]
    return sorted(f"{_display(k)} {'added' if k not in before else 'removed' if k not in after else 'changed'}"
                  for k in before.keys() | after.keys() if before.get(k) != after.get(k) or (k in before) != (k in after))


def for_task(m: dict, task: str) -> dict:
    """The one task's identity, independent of campaign tasks and installed builds."""
    return {"schema": m["schema"], "components": {k: v for k, v in m["components"].items()
                                                  if not k.startswith("builds/")
                                                  and (not k.startswith("tasks/") or k == f"tasks/{task}")}}


def _readers(root: Path, tasks: Sequence[str], builds: Mapping[str, Mapping] | None) -> dict[str, Callable[[], str]]:
    """Recipes shared by manifest and the recheck; construction does no content reads."""
    missing = unclassed(root, CLASSES, PLANNED)
    if missing:
        raise BenchError("HB-IDN-002", f"{', '.join(missing)} has no run/grade class")
    readers = {}
    for name in sorted(_source_files(root)):
        path = root / "src/harness_bench" / name
        readers[f"src/harness_bench/{name}"] = lambda p=path: plan.tree_hash(p.parent, [p])
    readers["catalog"] = lambda: catalog_hash(root)
    for key, name in {"prices": "bench/prices.yaml", "gateway": "bench/gateway.yaml", "bom": "bench/bom.yaml", "uv.lock": "uv.lock"}.items():
        readers[key] = lambda p=root / name: plan.file_hash(p)
    for harness in profiles.HARNESSES:
        readers[f"profiles/{harness}"] = lambda h=harness: identity_hash(plan.profile_record(root, h))
    if builds is not None:
        for harness, record in builds.items():
            readers[f"builds/{harness}"] = lambda r=record: identity_hash(dict(r))
    for task in set(tasks):
        readers[f"tasks/{task}"] = lambda t=task: plan.task_version_hash(root / "tasks" / t)
    readers["platform"] = lambda: sys.platform
    readers["python"] = lambda: ".".join(map(str, sys.version_info[:3]))
    return dict(sorted(readers.items()))


class _Deadline(Exception):
    """Internal control flow: the shared call budget has expired."""


def launch_check(root: Path, plan: dict, *, clock=time.monotonic, sleep=time.sleep,
                 deadline_s: float = 2.0) -> Callable[[], CheckResult] | None:
    """An injected Strategy: check once per launch tick, with one bounded drift recheck.

    Filesystem calls themselves are synchronous; the budget is checked before and
    after each component read, and no further read starts after it expires.
    """
    if "campaign" not in plan:
        return None
    expected = dict(plan["campaign"]["identity"]["components"])
    # R-106 c1: the key set is the stamp's, never the plan's. A subset plan still rechecks every task the chain baselined, and a build is read
    # from the plan only where the stamp holds it; a stamp build the plan lacks stays in `expected` and diffs as removed (fail closed).
    tasks = tuple(key.removeprefix("tasks/") for key in expected if key.startswith("tasks/"))
    plan_builds = plan.get("builds", {})
    builds = {key.removeprefix("builds/"): plan_builds[key.removeprefix("builds/")]
              for key in expected if key.startswith("builds/") and key.removeprefix("builds/") in plan_builds}

    def check() -> CheckResult:
        deadline = clock() + deadline_s
        unreadable: dict[str, str] = {}
        values: dict[str, str] = {}

        def pause():
            if clock() + 0.05 >= deadline:
                raise _Deadline
            sleep(0.05)
            if clock() >= deadline:
                raise _Deadline

        def read(key, getter):
            # Initial attempt plus three 50 ms retries, all sharing the same cap.
            for attempt in range(4):
                if clock() >= deadline:
                    unreadable[key] = "unreadable (deadline)"
                    return
                try:
                    value = getter()
                except (PermissionError, FileNotFoundError):
                    if attempt == 3:
                        unreadable[key] = "unreadable"
                        return
                    try:
                        pause()
                    except _Deadline:
                        unreadable[key] = "unreadable (deadline)"
                        return
                else:
                    if clock() >= deadline:
                        unreadable[key] = "unreadable (deadline)"
                    else:
                        values[key] = value
                        unreadable.pop(key, None)
                    return

        def run_readers():
            return {k: get for k, get in _readers(root, tasks, builds).items() if _class(k) == "run"}

        try:
            readers = run_readers()
        except BenchError as exc:
            return CheckResult([str(exc)], False)
        for key, getter in readers.items():
            read(key, getter)
        differing = {k for k in expected.keys() | readers.keys()
                     if k not in unreadable and (k not in expected or k not in readers or expected[k] != values[k])}
        rechecked = False
        if differing:
            # simplify: one fixed pause and one differing-key recheck; upgrade on
            # measured false stops or an identity_recheck rate above 1% of launches.
            try:
                pause()
            except _Deadline:
                unreadable.update(dict.fromkeys(differing, "unreadable (deadline)"))
            else:
                try:
                    current = run_readers()
                except BenchError as exc:
                    return CheckResult([str(exc)], False)
                for key in sorted(differing):
                    if key in current:
                        read(key, current[key])
                    else:
                        values.pop(key, None)
                remaining = {k for k in differing if k in unreadable or (k in expected) != (k in values)
                             or expected.get(k) != values.get(k)}
                rechecked = bool(differing - remaining)
        clean_expected = {k: v for k, v in expected.items() if k not in unreadable}
        clean_values = {k: v for k, v in values.items() if k not in unreadable}
        changes = diff({"components": clean_expected}, {"components": clean_values})
        changes.extend(f"{_display(k)} {reason}" for k, reason in unreadable.items())
        return CheckResult(sorted(changes), rechecked)

    return check
