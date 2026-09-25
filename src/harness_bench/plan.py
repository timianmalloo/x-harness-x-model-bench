"""Expand a matrix and a BOM into the run's cells, and freeze them in a content-addressed plan (US-6).

One cell is exactly one (task version, combo, pack, repetition). The order interleaves combos
innermost, so provider load and time-of-day drift affect every combo alike (proposal).

- `cell_id` is a deterministic hash of (task version hash, combo, pack, repetition) (ADR-0006).
- The task version hash covers every file in the task folder, so any edit to the prompt, the base
  tree or the hidden tests is a new version.
- `bench plan --confirm` writes `runs/<run_id>/plan.json` once; `plan_hash` covers every field, and
  loading a confirmed plan re-checks it (an edited plan is an integrity failure).
- The plan records each harness profile it uses (content hash, token source, auxiliary models), so
  grading and views read the run's own dimensions, never today's profile files (US-26).
"""

from __future__ import annotations

import hashlib
import json
import logging
import math
import os
import secrets
import shutil
import tempfile
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path

from harness_bench import archive, config, procs, profiles, tools, workspace
from harness_bench.errors import BenchError
from harness_bench.ledger import canonical

SCHEMA = "bench-plan/1"
logger = logging.getLogger(__name__)
# Instruction rows come from `copilot instruction list --json` verbatim, and Copilot may add
# non-string fields (e.g. `defaultDisabled`: bool) the ledger's canonical form forbids (ADR-0006).
# Only these identity fields are frozen into the plan, and only when they are strings.
INSTRUCTION_IDENTITY_FIELDS = ("sourcePath", "id", "label", "location", "type")
PHASE1_MAX_PARALLELISM = 4
# Plan parameters (ADR-0007: shown at confirmation, recorded in the plan). Seconds unless named.
DEFAULT_PARAMETERS = {
    "parallelism": 2,
    "decision_timeout": 1800,
    "spend_cap_tokens": None,
    "git_timeout": 120,
    "spawn_timeout": 30,
    "handshake_timeout": 60,
    "grading_step_timeout": 900,
    "lock_staleness": 120,
    "kill_escalation": 300,
    "suspend_gap": 60,
    "disk_floor_bytes": 10 * 1024**3,
    "stderr_tail_bytes": 64 * 1024,
}


@dataclass(frozen=True)
class Cell:
    task: str
    task_version: str
    scenario: int
    combo: str
    harness: str
    model: str
    pack: str
    rep: int
    budget_seconds: int

    @property
    def id(self) -> str:
        ingredients = {"task_version": self.task_version, "combo": self.combo, "pack": self.pack, "rep": self.rep}
        return hashlib.sha256(canonical(ingredients)).hexdigest()[:16]

    @property
    def label(self) -> str:
        return f"{self.task}.{self.combo}.pack-{self.pack}.r{self.rep}"


def select_tasks(bom: dict, subset) -> list[dict]:
    tasks = bom["tasks"]
    if subset == "full":
        return [t for t in tasks if not t.get("fixture")]
    if subset == "smoke":
        return [t for t in tasks if t.get("smoke") and not t.get("fixture")]
    wanted = set(subset)
    return [t for t in tasks if t["id"] in wanted]


def task_version_hash(task_dir: Path) -> str:
    """sha256 over every file in the task folder: relative path, NUL, bytes, in sorted path order."""
    h = hashlib.sha256()
    for f in sorted(p for p in task_dir.rglob("*") if p.is_file() and "__pycache__" not in p.parts):
        h.update(f.relative_to(task_dir).as_posix().encode() + b"\0")
        h.update(f.read_bytes().replace(b"\r\n", b"\n") + b"\0")
    return h.hexdigest()


def expand(matrix: dict, bom: dict, task_versions: dict[str, str] | None = None) -> list[Cell]:
    tasks = select_tasks(bom, matrix["bom"]["subset"])
    versions = task_versions or {}
    cells = []
    for rep in range(1, matrix["repetitions"] + 1):
        for t in tasks:
            for pack in matrix["packs"]:
                for c in matrix["combos"]:
                    cells.append(Cell(t["id"], versions.get(t["id"], t["id"]), t["scenario"], c["id"], c["harness"],
                                      c["model"], pack, rep, t["budget_minutes"] * 60))
    return cells


def envelope_seconds(cells: list[Cell], parallelism: int) -> int:
    """The worst-case wall clock the operator confirms: ceil(sum of budgets / p) + the largest budget."""
    if not cells:
        return 0
    budgets = [c.budget_seconds for c in cells]
    return math.ceil(sum(budgets) / parallelism) + max(budgets)


def _sha(obj) -> str:
    return hashlib.sha256(canonical(obj)).hexdigest()


def plan_hash(plan: dict) -> str:
    return _sha({k: v for k, v in plan.items() if k != "plan_hash"})


def file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest() if path.exists() else ""


def _prompt(task_dir: Path) -> dict:
    """The task prompt the agent receives, frozen in the plan with its hash (US-10); line ends as LF."""
    text = (task_dir / "prompt.md").read_bytes().replace(b"\r\n", b"\n").decode("utf-8")
    return {"prompt": text, "prompt_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest()}


def _model_map(task_dir: Path) -> dict:
    """The task's `model_map` ({role: model}, scenario 6; null otherwise), frozen so the served-model check reads the
    run, not today's task.yaml (US-11; W2-VIEWS seam S3)."""
    return {"model_map": config.load_yaml(task_dir / "task.yaml").get("model_map")}


def _validate_ids(cells: list[dict]) -> None:
    """Every frozen cell_id and label must match bench-status/1's id and label patterns (config.py),
    so status never has to emit a document its own strict parser would reject."""
    for c in cells:
        if not config.CELL_ID.fullmatch(c["cell_id"]):
            raise BenchError("HB-USR-002", f"cell_id {c['cell_id']!r} does not match the status id pattern")
        if not config.LABEL.fullmatch(c["label"]):
            raise BenchError("HB-USR-002", f"label {c['label']!r} does not match the status label pattern")


def profile_record(root: Path, harness: str) -> dict:
    p = profiles.load(root, harness)
    return {"profile_hash": file_hash(root / "bench" / "profiles" / f"{harness}.yaml"), "usage_source": p.usage_source,
            "auxiliary_models": list(p.auxiliary_models), "record_glob": p.record_glob}


def instruction_list(exe: Path, ws: Path, env: dict[str, str]) -> list[dict]:
    """Read the pinned Copilot build's effective repository instructions in one working copy."""
    result = procs.run([str(exe), "instruction", "list", "--json"], cwd=str(ws), env=env, timeout=120)
    if result.timed_out:
        raise BenchError("HB-PRE-008", "Copilot instruction list timed out after 120 s")
    if result.returncode != 0:
        raise BenchError("HB-PRE-008", f"Copilot instruction list failed ({result.returncode}): {result.stderr.strip()[-300:]}")
    try:
        rows = json.loads(result.stdout)
    except ValueError as exc:
        if result.stdout.lstrip().startswith("[") and not result.stdout.rstrip().endswith("]"):
            raise BenchError("HB-PRE-008", "Copilot instruction list stdout was truncated") from exc
        raise BenchError("HB-PRE-008", "Copilot instruction list did not return JSON") from exc
    if not isinstance(rows, list) or not all(isinstance(row, dict) for row in rows):
        raise BenchError("HB-PRE-008", "Copilot instruction list did not return an array of objects")
    return rows


def _instruction_identity(row: dict) -> dict:
    """Project one instruction row to its string-valued identity fields (ledger canonical is
    str/int/None/list/dict only; a bool like `defaultDisabled` must not reach the plan)."""
    return {k: row[k] for k in INSTRUCTION_IDENTITY_FIELDS if isinstance(row.get(k), str)}


def build_plan(root: Path, matrix: dict, bom: dict, run_id: str, builds: dict, pack: dict,
               parallelism: int = DEFAULT_PARAMETERS["parallelism"], parameters: dict | None = None,
               tools_dir: Path | None = None, cells_root: Path | None = None) -> dict:
    if not 1 <= parallelism <= PHASE1_MAX_PARALLELISM:
        raise BenchError("HB-USR-002", f"parallelism must be 1-{PHASE1_MAX_PARALLELISM} in phase 1, got {parallelism}")
    params = {**DEFAULT_PARAMETERS, **(parameters or {}), "parallelism": parallelism}
    for name in ("decision_timeout", "spend_cap_tokens"):
        value = params[name]
        if value is None and name == "spend_cap_tokens":
            continue
        if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
            raise BenchError("HB-USR-002", f"{name} must be a positive integer")
    tasks = select_tasks(bom, matrix["bom"]["subset"])
    versions = {t["id"]: task_version_hash(root / "tasks" / t["id"]) for t in tasks}
    cells = expand(matrix, bom, versions)
    harnesses = {c.harness for c in cells}
    missing = harnesses - set(builds)
    if missing:
        raise BenchError("HB-PRE-007", f"no planned build for {sorted(missing)}")
    instruction_counts: dict[tuple[str, str], int] = {}
    instruction_lists: list[dict] = []
    if "copilot" in harnesses:
        build = tools.resolve(tools_dir or root / ".tools" / "harness")["copilot"]
        tools.check_build(build, builds["copilot"])
        copilot_profile = profiles.load(root, "copilot")
        # A plan probe uses the same source, clone and pack installation as a cell, in a fresh home.
        cells_root = cells_root or root.parent / "bench-cells"
        workspace.check_cells_root(cells_root)
        cells_root.mkdir(parents=True, exist_ok=True)
        probe = Path(tempfile.mkdtemp(prefix="bench-plan-", dir=cells_root))
        try:
            for task_id, arm in sorted({(c.task, c.pack) for c in cells if c.harness == "copilot"}):
                source = workspace.task_source(root / "tasks" / task_id, versions[task_id], probe / "sources")
                ws = workspace.cell_working_copy(source, probe / "cells" / task_id / arm / "ws")
                if arm == "on":
                    pack_dir = workspace.pack_checkout(Path(pack["source"]), pack["commit"], probe / "pack")
                    workspace.install_pack(pack_dir, ws, project=task_id, timeout=300)
                home = probe / "homes" / task_id / arm
                home.mkdir(parents=True)
                env = copilot_profile.cell_env(dict(os.environ), home, build, "", "")
                rows = instruction_list(build.exe, ws, env)
                if arm == "off" and rows:
                    raise BenchError("HB-PRE-008", f"Copilot pack-off {task_id} loaded {len(rows)} instruction files")
                instruction_counts[task_id, arm] = len(rows)
                instruction_lists.append({"task": task_id, "task_version": versions[task_id], "pack": arm,
                                          "build_sha256": builds["copilot"]["sha256"], "count": len(rows),
                                          "instructions": [_instruction_identity(row) for row in rows]})
        finally:
            try:
                shutil.rmtree(probe, onexc=archive.make_writable)
            except OSError as exc:
                logger.warning("Could not remove plan probe %s: %s", probe, exc)
    body = {
        "schema": SCHEMA,
        "run_id": run_id,
        "created_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "trace_id": secrets.token_hex(16),
        "matrix": matrix,
        "matrix_hash": _sha(matrix),
        "bom_version": str(bom.get("version")),
        "tasks": {t["id"]: {"version_hash": versions[t["id"]], "scenario": t["scenario"], "budget_seconds": t["budget_minutes"] * 60,
                            **_prompt(root / "tasks" / t["id"]), **_model_map(root / "tasks" / t["id"])} for t in tasks},
        "builds": {h: builds[h] for h in sorted(harnesses)},
        "profiles": {h: profile_record(root, h) for h in sorted(harnesses)},
        "pack": pack,
        "parameters": params,
        "price_list_hash": file_hash(root / "bench" / "prices.yaml"),
        "envelope_seconds": envelope_seconds(cells, parallelism),
        "cells": [{"cell_id": c.id, "label": c.label, **asdict(c),
                   **({"instruction_count": instruction_counts[c.task, c.pack]} if c.harness == "copilot" else {})} for c in cells],
    }
    if instruction_lists:
        body["instruction_lists"] = instruction_lists
    _validate_ids(body["cells"])
    body["plan_hash"] = plan_hash(body)
    return body


def confirm(run_dir: Path, plan: dict) -> Path:
    """Freeze the plan: written once, never overwritten."""
    run_dir.mkdir(parents=True, exist_ok=True)
    path = run_dir / "plan.json"
    try:
        with path.open("x", encoding="utf-8") as f:
            f.write(json.dumps(plan, indent=2, sort_keys=True))
    except FileExistsError:
        raise BenchError("HB-USR-002", f"{path} already confirmed; a confirmed plan is frozen") from None
    return path


def load_confirmed(run_dir: Path) -> dict:
    path = run_dir / "plan.json"
    if not path.exists():
        raise BenchError("HB-USR-001", f"no confirmed plan at {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    if plan_hash(data) != data.get("plan_hash"):
        raise BenchError("HB-LED-002", f"{path} was edited after confirmation (plan_hash mismatch)")
    return data


def require_run_parameters(data: dict) -> None:
    """An old plan is readable, but cannot start under a newer engine's defaults."""
    missing = set(DEFAULT_PARAMETERS) - set(data.get("parameters", {}))
    if missing:
        raise BenchError("HB-USR-002", f"old plan missing parameters {sorted(missing)}; plan a new run")
