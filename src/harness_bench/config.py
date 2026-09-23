"""Load and validate the benchmark's declarative inputs: BOM, matrix, metrics, task folders.

Validation returns a list of problems rather than raising on the first one, so
`bench validate` reports everything wrong in one pass.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml

SCENARIOS = range(1, 7)
TASK_STATUSES = ("stub", "draft", "ready")
HARNESSES = ("claude-code", "codex", "copilot", "grok", "agy")
PACKS = ("on", "off")
METRIC_SOURCES = ("D", "J", "H", "P")
# coord-run/1 refuses a worker deadline above one hour (coord-runner.py RUN-BOUNDS).
MAX_BUDGET_MINUTES = 60
# Files in tests/ or oracle/ that do not count as content.
PLACEHOLDERS = {"README.md", ".gitkeep"}


@dataclass
class Problems:
    items: list[str] = field(default_factory=list)

    def add(self, where: str, msg: str) -> None:
        self.items.append(f"{where}: {msg}")

    def __bool__(self) -> bool:
        return bool(self.items)


def load_yaml(path: Path) -> dict:
    with path.open(encoding="utf-8") as f:
        data = yaml.safe_load(f)
    if not isinstance(data, dict):
        raise ValueError(f"{path}: expected a mapping at the top level")
    return data


def repo_root(start: Path | None = None) -> Path:
    here = (start or Path.cwd()).resolve()
    for p in (here, *here.parents):
        if (p / "bench" / "bom.yaml").is_file():
            return p
    raise FileNotFoundError("not inside the benchmark repo (no bench/bom.yaml above cwd)")


def validate_bom(bom: dict, p: Problems, where: str = "bench/bom.yaml") -> None:
    if bom.get("schema") != "bench-bom/1":
        p.add(where, "schema must be bench-bom/1")
    ids = [t.get("id") for t in bom.get("tasks", [])]
    if len(ids) != len(set(ids)):
        p.add(where, "duplicate task ids")
    smoke = {}
    for t in bom.get("tasks", []):
        tid = t.get("id", "?")
        if t.get("scenario") not in SCENARIOS:
            p.add(where, f"{tid}: scenario must be 1-6")
        minutes = t.get("budget_minutes")
        if not isinstance(minutes, int) or not 1 <= minutes <= MAX_BUDGET_MINUTES:
            p.add(where, f"{tid}: budget_minutes must be 1-{MAX_BUDGET_MINUTES}")
        if t.get("smoke"):
            smoke.setdefault(t.get("scenario"), []).append(tid)
    for s in SCENARIOS:
        if len(smoke.get(s, [])) != 1:
            p.add(where, f"smoke BOM needs exactly one task for scenario {s}, has {smoke.get(s, [])}")


def validate_matrix(m: dict, bom: dict, p: Problems, where: str) -> None:
    if m.get("schema") != "bench-matrix/1":
        p.add(where, "schema must be bench-matrix/1")
    if not isinstance(m.get("repetitions"), int) or m["repetitions"] < 1:
        p.add(where, "repetitions must be a positive integer")
    packs = m.get("packs") or []
    if any(isinstance(x, bool) for x in packs):
        p.add(where, 'packs contains a boolean: YAML 1.1 reads bare on/off as true/false; quote them ("on", "off")')
    elif not packs or any(x not in PACKS for x in packs):
        p.add(where, f"packs must be a non-empty subset of {PACKS}")
    ids = set()
    for c in m.get("combos") or []:
        if c.get("id") in ids:
            p.add(where, f"duplicate combo id {c.get('id')}")
        ids.add(c.get("id"))
        if c.get("harness") not in HARNESSES:
            p.add(where, f"{c.get('id')}: harness must be one of {HARNESSES}")
        if not c.get("model") or c.get("model") == "auto":
            p.add(where, f"{c.get('id')}: model must be pinned (not empty, not auto)")
    if not ids:
        p.add(where, "at least one combo is required")
    subset = (m.get("bom") or {}).get("subset")
    known = {t["id"] for t in bom.get("tasks", [])}
    if isinstance(subset, list):
        for tid in set(subset) - known:
            p.add(where, f"bom subset names unknown task {tid}")
    elif subset not in ("smoke", "full"):
        p.add(where, "bom.subset must be smoke, full, or a list of task ids")


def validate_metrics(metrics: dict, p: Problems, grader_modules: set[str], where: str = "bench/metrics.yaml") -> None:
    if metrics.get("schema") != "bench-metrics/1":
        p.add(where, "schema must be bench-metrics/1")
    seen = set()
    for area_id, area in (metrics.get("areas") or {}).items():
        for m in area.get("metrics") or []:
            mid = m.get("id")
            if mid in seen:
                p.add(where, f"duplicate metric id {mid}")
            seen.add(mid)
            if not set(m.get("source") or []) or not set(m["source"]) <= set(METRIC_SOURCES):
                p.add(where, f"{area_id}.{mid}: source must be a non-empty subset of {METRIC_SOURCES}")
            if m.get("better") not in ("higher", "lower"):
                p.add(where, f"{area_id}.{mid}: better must be higher or lower")
            if m.get("grader") not in grader_modules:
                p.add(where, f"{area_id}.{mid}: grader {m.get('grader')!r} has no module in harness_bench.grade")
    if len(metrics.get("areas") or {}) != 7:
        p.add(where, "expected the proposal's seven areas")


def _has_content(d: Path) -> bool:
    return d.is_dir() and any(f.name not in PLACEHOLDERS for f in d.rglob("*") if f.is_file())


def validate_task(task_dir: Path, bom_entry: dict | None, p: Problems, grader_modules: set[str]) -> None:
    where = f"tasks/{task_dir.name}"
    ty = task_dir / "task.yaml"
    if not ty.is_file():
        p.add(where, "missing task.yaml")
        return
    t = load_yaml(ty)
    if t.get("schema") != "bench-task/1":
        p.add(where, "schema must be bench-task/1")
    if t.get("id") != task_dir.name:
        p.add(where, f"id {t.get('id')!r} does not match folder name")
    status = t.get("status")
    if status not in TASK_STATUSES:
        p.add(where, f"status must be one of {TASK_STATUSES}")
    if bom_entry is None:
        p.add(where, "not listed in bench/bom.yaml")
    else:
        if t.get("scenario") != bom_entry.get("scenario"):
            p.add(where, "scenario disagrees with bench/bom.yaml")
        if (t.get("budget") or {}).get("minutes") != bom_entry.get("budget_minutes"):
            p.add(where, "budget.minutes disagrees with bench/bom.yaml")
    for g in t.get("graders") or []:
        if g not in grader_modules:
            p.add(where, f"grader {g!r} has no module in harness_bench.grade")
    if t.get("scenario") == 6 and not t.get("model_map"):
        p.add(where, "scenario 6 tasks need a model_map")
    if t.get("scenario") == 1 and not t.get("scripted_user"):
        p.add(where, "scenario 1 tasks need scripted_user: true")
    if status in ("draft", "ready") and not (task_dir / "prompt.md").is_file():
        p.add(where, f"status {status} requires prompt.md")
    if status == "ready":
        if not (_has_content(task_dir / "tests") or _has_content(task_dir / "oracle")):
            p.add(where, "status ready requires hidden tests or an oracle")
        if not (task_dir / "workspace").is_dir():
            p.add(where, "status ready requires workspace/")
        if "tbd" in {str((t.get("source") or {}).get(k)) for k in ("repo", "commit")}:
            p.add(where, "status ready requires a pinned source.repo and source.commit")


def grader_modules(root: Path) -> set[str]:
    gdir = root / "src" / "harness_bench" / "grade"
    return {f.stem for f in gdir.glob("*.py") if not f.stem.startswith("_")}


def validate_repo(root: Path) -> list[str]:
    p = Problems()
    graders = grader_modules(root)
    bom = load_yaml(root / "bench" / "bom.yaml")
    validate_bom(bom, p)
    validate_metrics(load_yaml(root / "bench" / "metrics.yaml"), p, graders)
    validate_matrix(load_yaml(root / "bench" / "matrix.example.yaml"), bom, p, "bench/matrix.example.yaml")
    entries = {t["id"]: t for t in bom.get("tasks", [])}
    tasks_dir = root / "tasks"
    folders = {d.name for d in tasks_dir.iterdir() if d.is_dir() and not d.name.startswith("_")}
    for tid in sorted(set(entries) - folders):
        p.add(f"tasks/{tid}", "listed in bench/bom.yaml but has no folder")
    for name in sorted(folders):
        validate_task(tasks_dir / name, entries.get(name), p, graders)
    return p.items
