"""Expand a matrix and a BOM into the run's cells, and freeze them in a content-addressed plan (US-6).

One cell is exactly one (task version, combo, arm, repetition). Launch order is hash-keyed
by seed, with every arm of a (task, combo, rep) block adjacent (ADR-0014).

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
import sys
import tempfile
import time
from collections import defaultdict
from collections.abc import Iterable
from copy import deepcopy
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from fractions import Fraction
from pathlib import Path

from harness_bench import archive, config, procs, profiles, tools, workspace
from harness_bench.errors import BenchError
from harness_bench.ledger import canonical
from harness_bench.scripted_user import clarifications
from harness_bench.scripted_user.matcher import MATCHER_VERSION

SCHEMA = "bench-plan/2"
BALANCE_BOUND = Fraction(1, 20)
# simplify: 100 redraws; exhaustion refuses the shape and prompts adding blocks, not raising the cap.
MAX_DRAWS = 100
SYNTHETIC_PROFILE_RECORD = {
    "profile_hash": None, "vendor": "synthetic", "usage_source": "acp_turn",
    "auxiliary_models": [], "record_glob": None, "subagent_glob": None, "shutdown_grace_seconds": "1",
}
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
    arm: str
    rep: int
    budget_seconds: int

    @property
    def id(self) -> str:
        # "pack" is a frozen recipe label: changing the key would rewrite historical cell identities.
        ingredients = {"task_version": self.task_version, "combo": self.combo, "pack": self.arm, "rep": self.rep}
        return hashlib.sha256(canonical(ingredients)).hexdigest()[:16]

    @property
    def label(self) -> str:
        return f"{self.task}.{self.combo}.arm-{self.arm}.r{self.rep}"


def select_tasks(bom: dict, subset) -> list[dict]:
    tasks = bom["tasks"]
    if subset == "full":
        return [t for t in tasks if not t.get("fixture")]
    if subset == "smoke":
        return [t for t in tasks if t.get("smoke") and not t.get("fixture")]
    wanted = set(subset)
    return [t for t in tasks if t["id"] in wanted]


def tree_hash(base: Path, files: Iterable[Path]) -> str:
    """The one content-address recipe (R-59 c1, seam S-2): sha256 over each file's path relative to `base`, NUL,
    its bytes with CRLF as LF, NUL, in sorted path order. The task version and the catalog hash are both this.

    Sort key is the case-folded posix-relative path, not native `Path` comparison (ADR-0013 Amendment 1,
    macOS port): `pathlib.Path.__lt__` compares case-insensitively on Windows (`os.path.normcase` lowercases)
    but case-sensitively on POSIX, so the same file set hashed the same sorted(files) call landed in two
    different orders on the two hosts and produced two different digests for the same content -- the actual
    cause of the tasks/A1 (etc.) mismatch on macos-latest CI, verified by reproducing both orders locally
    against the CI-reported digest, not the line-ending difference the CI's own failure log first suggested
    (both hosts check out these files as pure LF; ADR-0013's `eol=lf` and `git show`'s blob content confirm
    no CRLF ever reaches this hash). Explicit casefold order matches the case-insensitive order the frozen
    task versions were already computed in on Windows, so Windows digests are unchanged by this fix."""
    h = hashlib.sha256()
    for f in sorted(files, key=lambda p: p.relative_to(base).as_posix().casefold()):
        h.update(f.relative_to(base).as_posix().encode() + b"\0")
        h.update(f.read_bytes().replace(b"\r\n", b"\n") + b"\0")
    return h.hexdigest()


def task_version_hash(task_dir: Path) -> str:
    """tree_hash over every file in the task folder (bytecode caches aside)."""
    return tree_hash(task_dir, [p for p in task_dir.rglob("*") if p.is_file() and "__pycache__" not in p.parts])


def expand(matrix: dict, bom: dict, task_versions: dict[str, str] | None = None) -> list[Cell]:
    tasks = select_tasks(bom, matrix["bom"]["subset"])
    versions = task_versions or {}
    cells = []
    for rep in range(1, matrix["repetitions"] + 1):
        for t in tasks:
            for arm in arms_of(matrix):
                for c in matrix["combos"]:
                    cells.append(Cell(t["id"], versions.get(t["id"], t["id"]), t["scenario"], c["id"], c["harness"],
                                      c["model"], arm["id"], rep, t["budget_minutes"] * 60))
    return cells


def arms_of(matrix: dict) -> list[dict]:
    """Adapter: upcast in memory, preserving declared order and the original matrix."""
    if matrix.get("schema") == "bench-matrix/1":
        return [{"id": aid, "pack": None} for aid in matrix["packs"]]
    return [{"id": arm["id"], "pack": arm.get("pack")} for arm in matrix["arms"]]


def default_comparisons(arm_ids: list[str]) -> list[list[str]]:
    if len(arm_ids) < 2:
        return []
    if len(arm_ids) > 2:
        raise BenchError("HB-PLN-002", "3 or more arms require explicit comparisons")
    if config.ARM_OFF in arm_ids:
        return [[config.ARM_OFF, next(a for a in arm_ids if a != config.ARM_OFF)]]
    return [list(arm_ids)]


def cell_arm(cell: dict) -> str:
    """Facade over the versioned cell; explicit arm wins over a legacy pack key."""
    arm = cell["arm"] if "arm" in cell else cell.get("pack")
    if not isinstance(arm, str) or not config.ARM_ID.fullmatch(arm):
        raise BenchError("HB-USR-002", f"cell has no valid arm: {arm!r}")
    return arm


def plan_packs(plan: dict) -> dict[str, dict]:
    """The sole reader of arm pack records and the historical top-level pack."""
    if "arms" in plan:
        return {aid: arm["pack"] for aid, arm in plan["arms"].items() if arm.get("pack") is not None}
    pack = plan.get("pack")
    return {"on": pack} if pack is not None else {}


def plan_pack(plan: dict) -> dict | None:
    packs = plan_packs(plan)
    if len(packs) > 1:
        raise BenchError("HB-PLN-005", f"single-pack reader received several packs: {', '.join(packs)}")
    return next(iter(packs.values()), None)


def arm_pack(plan: dict, arm: str) -> dict | None:
    declared = set(plan["arms"]) if "arms" in plan else set(config.PACKS)
    if arm not in declared:
        raise BenchError("HB-USR-002", f"arm {arm!r} is not in the plan")
    return plan_packs(plan).get(arm)


def plan_comparisons(plan: dict) -> list[tuple[str, str]]:
    if "comparisons" in plan:
        return [tuple(pair) for pair in plan["comparisons"]]
    arms = {cell_arm(cell) for cell in plan.get("cells", [])}
    return [(config.ARM_OFF, "on")] if set(config.PACKS) <= arms else []


def kind_of(plan: dict) -> str:
    kind = plan.get("kind", "measurement")
    if kind not in ("measurement", "discrimination"):
        raise BenchError("HB-PLN-004", f"unknown plan kind {kind!r}; expected measurement or discrimination")
    return kind


def launch_order(cells: list[Cell], seed: int) -> list[Cell]:
    """Stable hash keys replay across Python versions; all arms of a block stay adjacent."""
    def key(cell):
        block = f"{cell.task}|{cell.combo}|{cell.rep}"
        return (hashlib.sha256(f"{seed}|block|{block}".encode()).digest(),
                hashlib.sha256(f"{seed}|arm|{block}|{cell.arm}".encode()).digest())
    return sorted(cells, key=key)


def launch_balance(cells: list[Cell]) -> Fraction:
    if not cells:
        return Fraction(0)
    positions = defaultdict(list)
    for position, cell in enumerate(cells):
        positions[cell.arm].append(position)
    midpoint = Fraction(len(cells) - 1, 2)
    return max(abs(Fraction(sum(ps), len(ps)) - midpoint) / len(cells) for ps in positions.values())


def draw_launch_order(cells: list[Cell], draw=None) -> tuple[int, list[Cell], int]:
    draw = draw if draw is not None else lambda: secrets.randbits(63)
    for attempt in range(1, MAX_DRAWS + 1):
        seed = draw()
        ordered = launch_order(cells, seed)
        if launch_balance(ordered) < BALANCE_BOUND:
            return seed, ordered, attempt
    blocks = len({(c.task, c.combo, c.rep) for c in cells})
    arms = len({c.arm for c in cells})
    raise BenchError("HB-PLN-001", f"launch order cannot meet the 5 % balance bound after {MAX_DRAWS} draws: "
                                 f"{blocks} blocks of {arms} arms; add tasks, combos or repetitions")


def parse_binding(text: str) -> tuple[str, str, str]:
    role, equals, rest = text.partition("=")
    source, at, commit = rest.rpartition("@")
    if not equals or not at or not config.ARM_ID.fullmatch(role) or role == config.ARM_OFF:
        raise BenchError("HB-PLN-002", "binding must be ROLE=ABSOLUTE_SOURCE@COMMIT; off cannot be bound")
    problem = config.pack_pin_problem({"source": source, "commit": commit})
    if problem:
        raise BenchError("HB-PLN-002", f"arm {role}: {problem}")
    return role, source, commit


def resolve_arms(matrix: dict, bindings: dict) -> dict[str, dict | None]:
    arms = arms_of(matrix)
    ids = [arm["id"] for arm in arms]
    if any(not isinstance(aid, str) or not config.ARM_ID.fullmatch(aid) for aid in ids) or len(ids) != len(set(ids)):
        raise BenchError("HB-PLN-002", "invalid or duplicate arm ids")
    unknown = set(bindings) - set(ids)
    if unknown:
        raise BenchError("HB-PLN-002", f"bindings name unknown arms {sorted(unknown)}")
    resolved = {}
    for arm in arms:
        aid, pack = arm["id"], arm["pack"]
        if aid == config.ARM_OFF:
            if pack is not None or aid in bindings:
                raise BenchError("HB-PLN-002", "off arm cannot have a pack or binding")
            resolved[aid] = None
            continue
        if aid in bindings:
            if pack is not None:
                raise BenchError("HB-PLN-002", f"arm {aid} is already pinned; cannot bind it again")
            binding = bindings[aid]
            if not isinstance(binding, (tuple, list)) or len(binding) != 2:
                raise BenchError("HB-PLN-002", f"arm {aid}: binding must name source and commit")
            pack = {"source": binding[0], "commit": binding[1]}
        if pack is None:
            raise BenchError("HB-PLN-002", f"unbound role arm {aid}")
        problem = config.pack_pin_problem(pack)
        if problem:
            raise BenchError("HB-PLN-002", f"arm {aid}: {problem}")
        resolved[aid] = dict(pack)
    return resolved


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
    turns = [{"n": int(p.stem), "prompt": p.read_text(encoding="utf-8"), "sha256": ""}
             for p in sorted((task_dir / "turns").glob("*.md"))]
    return {"prompt": text, "prompt_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
            **({"turns": turns} if turns else {})}


def _model_map(task_dir: Path) -> dict:
    """The task's `model_map` ({role: model}, scenario 6; null otherwise), frozen so the served-model check reads the
    run, not today's task.yaml (US-11; W2-VIEWS seam S3)."""
    return {"model_map": config.load_yaml(task_dir / "task.yaml").get("model_map")}


def _graders(task_dir: Path) -> dict:
    """The task's `graders` list, verbatim, frozen so a pass grades the run's list, not today's task.yaml (seam S-1)."""
    return {"graders": list(config.load_yaml(task_dir / "task.yaml").get("graders") or [])}


def _scripted_user(task_dir: Path) -> dict:
    """Freeze the responder's input identity alongside the task version (R-53)."""
    enabled = config.load_yaml(task_dir / "task.yaml").get("scripted_user") is True
    if not enabled:
        return {"scripted_user": 0, "clarifications_path": None,
                "clarifications_sha256": None, "matcher_version": None}
    path = (task_dir / "oracle" / "clarifications.yaml").resolve()
    cset = clarifications.load(path)
    return {"scripted_user": 1, "clarifications_path": str(path),
            "clarifications_sha256": cset.sha256, "matcher_version": MATCHER_VERSION}


def require_scripted_user_inputs(root: Path, frozen: dict) -> None:
    """Refuse a run if its responder inputs disagree with the confirmed plan (R-53 c2)."""
    for task_id, record in frozen["tasks"].items():
        if not record.get("scripted_user"):
            continue
        path = (root / "tasks" / task_id / "oracle" / "clarifications.yaml").resolve()
        if record.get("clarifications_path") != str(path):
            raise BenchError("HB-USR-002", f"task {task_id}: clarification path differs from the plan")
        if record.get("clarifications_sha256") != clarifications.load(path).sha256:
            raise BenchError("HB-USR-002", f"task {task_id}: clarification-set hash differs from the plan")
        if record.get("matcher_version") != MATCHER_VERSION:
            raise BenchError("HB-USR-002", f"task {task_id}: matcher_version differs from the plan")


def _validate_ids(cells: list[dict]) -> None:
    """Every frozen cell_id and label must match bench-status/1's id and label patterns (config.py),
    so status never has to emit a document its own strict parser would reject."""
    for c in cells:
        if not config.CELL_ID.fullmatch(c["cell_id"]):
            raise BenchError("HB-USR-002", f"cell_id {c['cell_id']!r} does not match the status id pattern")
        if not config.LABEL.fullmatch(c["label"]):
            raise BenchError("HB-USR-002", f"label {c['label']!r} does not match the status label pattern")


def resolved_model_map(plan: dict, cell: dict) -> dict[str, str]:
    """R-73 item 2, the one resolver: {role: model} from the cell's task's frozen `model_map`, only the keys whose vendor is
    the vendor frozen in the plan's profile record for the cell's harness. A bare key, another vendor's key, or a plan
    that froze no vendor (before R-73) resolves to nothing, so no other vendor's id is ever an allowance (US-11).
    views._mapped reads it; grade/coordination.py's role comparison is to read it (R-73 c2; not built in 0.4)."""
    record = (plan.get("profiles") or {}).get(cell.get("harness"))
    vendor = record.get("vendor") if isinstance(record, dict) else None
    task = (plan.get("tasks") or {}).get(cell.get("task"))
    model_map = task.get("model_map") if isinstance(task, dict) else None
    if not isinstance(model_map, dict):
        return {}
    out = {}
    for key, model in model_map.items():
        parsed = config.map_key(key)
        if parsed is not None and parsed[1] == vendor and isinstance(model, str):
            out[parsed[0]] = model
    return out


def _require_discriminating_maps(body: dict) -> None:
    """R-73 item 5: every scenario-6 cell has at least one resolved role on a model other than its pin; a map whose every
    role equals the pin cannot tell routing from no routing, so the plan is refused."""
    # Refusal text must be reproducible even when the launch seed puts a different arm first.
    for c in sorted(body["cells"], key=lambda cell: cell["label"]):
        if c["scenario"] != 6:
            continue
        vendor = body["profiles"][c["harness"]]["vendor"]
        roles = resolved_model_map(body, c)
        if not roles:
            raise BenchError("HB-USR-002", f"scenario 6: {c['task']}'s model_map names no role for vendor {vendor} "
                                           f"(cell {c['label']}) (R-73 item 5)")
        if all(model == c["model"] for model in roles.values()):
            raise BenchError("HB-USR-002", f"scenario 6: every role of {c['task']}'s model_map for vendor {vendor} equals "
                                           f"the pin of {c['label']} ({c['model']}), so routing cannot be told from no "
                                           "routing (R-73 item 5)")


def profile_record(root: Path, harness: str) -> dict:
    if harness == "synthetic":
        return SYNTHETIC_PROFILE_RECORD
    p = profiles.load(root, harness)
    # The plan's canonical form has no floats; the decimal string preserves a fractional profile value exactly.
    return {"profile_hash": file_hash(root / "bench" / "profiles" / f"{harness}.yaml"), "vendor": p.vendor, "usage_source": p.usage_source,
            "auxiliary_models": list(p.auxiliary_models), "record_glob": p.record_glob, "subagent_glob": p.subagent_glob,
            "shutdown_grace_seconds": format(p.shutdown_grace, "g")}


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


def _probe_instructions(root: Path, cells: list[Cell], versions: dict, builds: dict, arm_packs: dict,
                        tools_dir: Path | None, cells_root: Path | None) -> tuple[dict, list[dict]]:
    instruction_counts, instruction_lists = {}, []
    if not any(c.harness == "copilot" for c in cells):
        return instruction_counts, instruction_lists
    build = tools.resolve(tools_dir or root / ".tools" / "harness")["copilot"]
    tools.check_build(build, builds["copilot"])
    copilot_profile = profiles.load(root, "copilot")
    # A plan probe uses the same source, clone and arm pack installation as a cell, in a fresh home.
    cells_root = cells_root or root.parent / "bench-cells"
    workspace.check_cells_root(cells_root)
    cells_root.mkdir(parents=True, exist_ok=True)
    probe = Path(tempfile.mkdtemp(prefix="bench-plan-", dir=cells_root))
    try:
        for task_id, arm in sorted({(c.task, c.arm) for c in cells if c.harness == "copilot"}):
            source = workspace.task_source(root / "tasks" / task_id, versions[task_id], probe / "sources", probe / "upstream")
            ws = workspace.cell_working_copy(source, probe / "cells" / task_id / arm / "ws")
            pack = arm_packs[arm]
            if pack is not None:
                pack_dir = workspace.pack_checkout(Path(pack["source"]), pack["commit"], probe / "pack")
                workspace.install_pack(pack_dir, ws, project=task_id, timeout=300)
            home = probe / "homes" / task_id / arm
            home.mkdir(parents=True)
            env = copilot_profile.cell_env(dict(os.environ), home, build, "", "")
            rows = instruction_list(build.exe, ws, env)
            if pack is None and rows:
                raise BenchError("HB-PRE-008", f"Copilot pack-off {task_id} loaded {len(rows)} instruction files")
            instruction_counts[task_id, arm] = len(rows)
            instruction_lists.append({"task": task_id, "task_version": versions[task_id], "arm": arm,
                                      "build_sha256": builds["copilot"]["sha256"], "count": len(rows),
                                      "instructions": [_instruction_identity(row) for row in rows]})
    finally:
        try:
            shutil.rmtree(probe, onexc=archive.make_writable)
        except OSError as exc:
            logger.warning("Could not remove plan probe %s: %s", probe, exc)
    return instruction_counts, instruction_lists


def build_plan(root: Path, matrix: dict, bom: dict, run_id: str, builds: dict, arm_packs: dict | None = None,
               parallelism: int = DEFAULT_PARAMETERS["parallelism"], parameters: dict | None = None,
               tools_dir: Path | None = None, cells_root: Path | None = None, *,
               matrix_path: Path | None = None, kind: str = "measurement", campaign: dict | None = None,
               launch_seed: int | None = None, task_versions: dict[str, str] | None = None,
               pack: dict | None = None) -> dict:
    started_ns = time.perf_counter_ns()
    kind = kind_of({"kind": kind})
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
    permitted_statuses = ("ready",) if kind == "measurement" else ("draft", "ready")
    offenders = []
    for task in tasks:
        status = config.load_yaml(root / "tasks" / task["id"] / "task.yaml").get("status")
        if status not in permitted_statuses:
            offenders.append(f"{task['id']} ({status})")
    if kind == "measurement":
        offenders.extend(f"combo {combo['id']} (synthetic)" for combo in matrix["combos"] if combo["harness"] == "synthetic")
    if offenders:
        raise BenchError("HB-PLN-004", f"{kind} plan refuses: {'; '.join(offenders)}")
    declared = arms_of(matrix)
    ids = [arm["id"] for arm in declared]
    if len(ids) != len(set(ids)) or any(not isinstance(a, str) or not config.ARM_ID.fullmatch(a) for a in ids):
        raise BenchError("HB-PLN-002", "invalid or duplicate arm ids")
    # simplify: accept the old sixth pack argument until X-C migrates cmd_plan; no legacy field is written.
    # Ceiling: bench-matrix/1 only. Upgrade trigger: the X-C caller switches to resolved arm_packs.
    if pack is not None:
        if arm_packs is not None or matrix.get("schema") != "bench-matrix/1":
            raise BenchError("HB-PLN-002", "legacy pack argument applies only to bench-matrix/1 without arm_packs")
        arm_packs = pack
    if matrix.get("schema") == "bench-matrix/1" and (arm_packs is None or "source" in arm_packs):
        legacy_pack = arm_packs
        arm_packs = {aid: None if aid == config.ARM_OFF else legacy_pack for aid in ids}
    arm_packs = arm_packs or {}
    if set(arm_packs) != set(ids):
        raise BenchError("HB-PLN-002", "resolved packs must name exactly the declared arms")
    for arm in declared:
        aid, record = arm["id"], arm_packs[arm["id"]]
        if aid == config.ARM_OFF:
            if record is not None or arm["pack"] is not None:
                raise BenchError("HB-PLN-002", "off arm cannot have a pack")
        elif not isinstance(record, dict) or not {"source", "commit", "revision"} <= record.keys():
            raise BenchError("HB-PLN-002", f"unbound role or incomplete pack record for arm {aid}")
    comparisons = matrix["comparisons"] if "comparisons" in matrix else default_comparisons(ids)
    for pair in comparisons:
        if len(pair) != 2 or any(aid not in ids for aid in pair) or pair[0] == pair[1]:
            raise BenchError("HB-PLN-002", f"invalid comparison pair {pair!r}")
    versions = {t["id"]: task_versions[t["id"]] if task_versions is not None else task_version_hash(root / "tasks" / t["id"])
                for t in tasks}
    cells = expand(matrix, bom, versions)
    if launch_seed is None:
        launch_seed, cells, draws = draw_launch_order(cells)
    else:
        if not isinstance(launch_seed, int) or isinstance(launch_seed, bool) or launch_seed < 0:
            raise BenchError("HB-PLN-001", "launch_seed must be a nonnegative integer")
        cells = launch_order(cells, launch_seed)
        if launch_balance(cells) >= BALANCE_BOUND:
            raise BenchError("HB-PLN-001", "given launch_seed cannot meet the 5 % balance bound after 1 draw")
        draws = 1
    harnesses = {c.harness for c in cells}
    missing = harnesses - set(builds)
    if missing:
        raise BenchError("HB-PRE-007", f"no planned build for {sorted(missing)}")
    instruction_counts, instruction_lists = _probe_instructions(root, cells, versions, builds, arm_packs, tools_dir, cells_root)
    body = {
        "schema": SCHEMA,
        "run_id": run_id,
        "created_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "trace_id": secrets.token_hex(16),
        # ADR-0013 Amendment 1 section 5: the report header names the platform, and board.compare
        # refuses to compare runs recorded on different platforms (the platform changes what is
        # measured: wall clock, the harness build, the toolchain).
        "platform": sys.platform,
        "matrix": matrix,
        "matrix_hash": _sha(matrix),
        "bom_version": str(bom.get("version")),
        "tasks": {t["id"]: {"version_hash": versions[t["id"]], "scenario": t["scenario"], "budget_seconds": t["budget_minutes"] * 60,
                            **_graders(root / "tasks" / t["id"]), **_prompt(root / "tasks" / t["id"]),
                            **_model_map(root / "tasks" / t["id"]),
                            **_scripted_user(root / "tasks" / t["id"])} for t in tasks},
        "builds": {h: builds[h] for h in sorted(harnesses)},
        "profiles": {h: profile_record(root, h) for h in sorted(harnesses)},
        "arms": {aid: {"pack": arm_packs[aid]} for aid in ids},
        "comparisons": deepcopy(comparisons),
        "launch_seed": launch_seed,
        "kind": kind,
        "parameters": params,
        "price_list_hash": file_hash(root / "bench" / "prices.yaml"),
        "envelope_seconds": envelope_seconds(cells, parallelism),
        "cells": [{"cell_id": c.id, "label": c.label, **asdict(c),
                   **({"instruction_count": instruction_counts[c.task, c.arm]} if c.harness == "copilot" else {})} for c in cells],
    }
    if campaign is not None:
        body["campaign"] = deepcopy(campaign)
    if "ring" in matrix:
        if matrix_path is None:
            raise BenchError("HB-PLN-002", "a ring requires matrix_path for its content hash")
        body["ring"] = {"tag": matrix["ring"]["tag"], "hash": tree_hash(matrix_path.parent, [matrix_path])}
    if instruction_lists:
        body["instruction_lists"] = instruction_lists
    _validate_ids(body["cells"])
    _require_discriminating_maps(body)
    body["plan_hash"] = plan_hash(body)
    logger.info("Plan built", extra={"run_id": run_id, "trace_id": body["trace_id"], "plan_kind": kind,
                                    "cell_count": len(cells), "launch_seed": launch_seed, "launch_draws": draws,
                                    "launch_balance": str(launch_balance(cells)),
                                    "duration_ns": time.perf_counter_ns() - started_ns})
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
    # Historical hand-authored ledger fixtures predate a schema field; explicit newer schemas still refuse.
    if data.get("schema", "bench-plan/1") not in ("bench-plan/1", SCHEMA):
        raise BenchError("HB-USR-002", f"unsupported plan schema {data.get('schema')!r}")
    if plan_hash(data) != data.get("plan_hash"):
        raise BenchError("HB-LED-002", f"{path} was edited after confirmation (plan_hash mismatch)")
    return data


def require_run_parameters(data: dict) -> None:
    """An old plan is readable, but cannot start under a newer engine's defaults."""
    missing = set(DEFAULT_PARAMETERS) - set(data.get("parameters", {}))
    if missing:
        raise BenchError("HB-USR-002", f"old plan missing parameters {sorted(missing)}; plan a new run")
