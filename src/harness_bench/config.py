"""Load and validate the benchmark's declarative inputs: BOM, matrix, metrics, task folders.

Validation returns a list of problems rather than raising on the first one, so
`bench validate` reports everything wrong in one pass.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from harness_bench.errors import BenchError

# bench-status/1's id and label patterns (status.py): plan.py validates every cell_id and label
# against them at plan time, so status never has to emit a document its own parser would reject.
CELL_ID = re.compile(r"[0-9a-z]{1,16}")
LABEL = re.compile(r"[A-Za-z0-9.\-]{1,80}")

SCENARIOS = range(1, 8)
# The smoke BOM needs exactly one task per scenario 1-6. Scenario 7 may add one after the
# formal-toolchain spike (spec S-12).
SMOKE_REQUIRED = range(1, 7)
FORMAL_TOOLS = ("tla", "lean")
TASK_STATUSES = ("stub", "draft", "ready")
HARNESSES = ("claude-code", "codex", "copilot", "grok", "agy")
PACKS = ("on", "off")
METRIC_SOURCES = ("D", "J", "H", "P")
# A cell budget is 1-60 minutes: every BOM task fits, so a larger one is an input error until a task needs it.
MAX_BUDGET_MINUTES = 60
# Files in tests/ or oracle/ that do not count as content.
PLACEHOLDERS = {"README.md", ".gitkeep"}
# R-42 condition 4: generated/cache folder names that must never be vendored into workspace/.
GENERATED_DIR_NAMES = {"bin", "obj", ".vs", "__pycache__", "node_modules", ".pytest_cache"}
# An absolute path under an operator's home directory. %USERPROFILE% and $HOME are fine: they
# resolve per-machine and name no one, so this pattern never matches them.
PROFILE_PATH = re.compile(
    r"[A-Za-z]:[\\/]Users[\\/][^\\/\s\"'<>]+"
    r"|(?<![\w.-])/home/[^/\s\"'<>]+"
    r"|(?<![\w.-])/Users/[^/\s\"'<>]+",
    re.IGNORECASE,
)


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
        raise BenchError("HB-USR-002", f"{path}: expected a mapping at the top level")
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
            p.add(where, f"{tid}: scenario must be {SCENARIOS.start}-{SCENARIOS.stop - 1}")
        minutes = t.get("budget_minutes")
        if not isinstance(minutes, int) or not 1 <= minutes <= MAX_BUDGET_MINUTES:
            p.add(where, f"{tid}: budget_minutes must be 1-{MAX_BUDGET_MINUTES}")
        if t.get("smoke"):
            smoke.setdefault(t.get("scenario"), []).append(tid)
    for s in SCENARIOS:
        n = len(smoke.get(s, []))
        if (s in SMOKE_REQUIRED and n != 1) or n > 1:
            p.add(where, f"smoke BOM needs {'exactly' if s in SMOKE_REQUIRED else 'at most'} one task for scenario {s}, has {smoke.get(s, [])}")


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


def pack_marker_bytes(root: Path) -> list[bytes]:
    """R-42 condition 2's marker list, read once and threaded into every validate_task call
    (validate_repo reads it a single time for the whole tasks/ sweep). tests/test_task_vendoring.py
    and tests/test_workspace.py each parse bench/pack-markers.txt inline for their own assertions;
    this is validate_task's one reader, not a third parse of the same file."""
    text = (root / "bench" / "pack-markers.txt").read_text(encoding="utf-8")
    return [line.strip().encode("utf-8") for line in text.splitlines() if line.strip()]


def _workspace_vendoring_problems(task_dir: Path, pack_markers: list[bytes], p: Problems, where: str) -> None:
    """R-42 conditions 2 and 4: a ready task's workspace/ carries no pack material and no
    generated/cache folder. One report of each kind is enough to name the offender."""
    ws = task_dir / "workspace"
    if not ws.is_dir():
        return
    for d in sorted(ws.rglob("*")):
        if d.is_dir() and d.name in GENERATED_DIR_NAMES:
            p.add(where, f"{d.relative_to(task_dir).as_posix()}/ is a generated or cache folder and must not be vendored")
            break
    for f in sorted(ws.rglob("*")):
        if f.is_file() and any(m in f.read_bytes() for m in pack_markers):
            p.add(where, f"{f.relative_to(task_dir).as_posix()} contains pack material (bench/pack-markers.txt)")
            break


def _is_vendored(f: Path, ws: Path, vendored_paths: list[str]) -> bool:
    """True when `f` is a workspace/ file pinned by R-42 condition 3's source.vendored_paths --
    those bytes must match the upstream archive exactly (test_task_vendoring.py), so the
    profile-path scan must not force an edit there. Scoped to files under workspace/ only:
    vendored_paths never pins task.yaml, prompt.md, oracle/** or tests/**, so those are always
    scanned regardless of what vendored_paths lists."""
    if ws not in f.parents:
        return False
    rel_ws = f.relative_to(ws).as_posix()
    return any(rel_ws == vp or rel_ws.startswith(vp + "/") for vp in vendored_paths)


def _profile_path_problems(task_dir: Path, p: Problems, where: str, vendored_paths: list[str]) -> None:
    """Any text file anywhere under the task folder that hardcodes an operator's home-directory
    path is refused, naming the file and the first offending line. Binary files are skipped."""
    ws = task_dir / "workspace"
    for f in sorted(task_dir.rglob("*")):
        if not f.is_file() or _is_vendored(f, ws, vendored_paths):
            continue
        data = f.read_bytes()
        if b"\x00" in data[:8000]:
            continue
        for lineno, line in enumerate(data.decode("utf-8", errors="replace").splitlines(), start=1):
            if PROFILE_PATH.search(line):
                p.add(where, f"{f.relative_to(task_dir).as_posix()}:{lineno} hardcodes an absolute user-profile path")
                break


def validate_task(task_dir: Path, bom_entry: dict | None, p: Problems, grader_modules: set[str], pack_markers: list[bytes]) -> None:
    where = f"tasks/{task_dir.name}"
    ty = task_dir / "task.yaml"
    if not ty.is_file():
        p.add(where, "missing task.yaml")
        _profile_path_problems(task_dir, p, where, [])
        return
    t = load_yaml(ty)
    vendored_paths = [str(vp).rstrip("/") for vp in (t.get("source") or {}).get("vendored_paths") or []]
    _profile_path_problems(task_dir, p, where, vendored_paths)
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
    if t.get("scenario") == 7:
        formal = t.get("formal") or {}
        if formal.get("tool") not in FORMAL_TOOLS:
            p.add(where, f"scenario 7 tasks need formal.tool in {FORMAL_TOOLS}")
        if formal.get("statements") not in ("fixed", "agent"):
            p.add(where, "scenario 7 tasks need formal.statements: fixed | agent")
        if "formal" not in (t.get("graders") or []):
            p.add(where, "scenario 7 tasks need the formal grader")
    if status in ("draft", "ready") and not (task_dir / "prompt.md").is_file():
        p.add(where, f"status {status} requires prompt.md")
    if status == "ready":
        if not (_has_content(task_dir / "tests") or _has_content(task_dir / "oracle")):
            p.add(where, "status ready requires hidden tests or an oracle")
        if not (task_dir / "workspace").is_dir():
            p.add(where, "status ready requires workspace/")
        if t.get("scenario") == 1 and not (task_dir / "oracle" / "clarifications.yaml").is_file():
            p.add(where, "status ready requires oracle/clarifications.yaml for scenario 1")
        _workspace_vendoring_problems(task_dir, pack_markers, p, where)
        if "tbd" in {str((t.get("source") or {}).get(k)) for k in ("repo", "commit")}:
            p.add(where, "status ready requires a pinned source.repo and source.commit")
        formal = t.get("formal") or {}
        if t.get("scenario") == 7 and "tbd" in {str(formal.get("toolchain")), str(formal.get("statement_hash"))}:
            p.add(where, "status ready requires a pinned formal.toolchain and, for fixed statements, formal.statement_hash")


def grader_modules(root: Path) -> set[str]:
    gdir = root / "src" / "harness_bench" / "grade"
    return {f.stem for f in gdir.glob("*.py") if not f.stem.startswith("_")}


def validate_repo(root: Path) -> list[str]:
    p = Problems()
    graders = grader_modules(root)
    markers = pack_marker_bytes(root)
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
        validate_task(tasks_dir / name, entries.get(name), p, graders, markers)
    return p.items
