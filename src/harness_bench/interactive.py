"""bench interactive: the lean tasks worked by the operator's own interactive CLI session, one session per arm.

Why: a headless cell (`claude -p`, `codex exec`, `copilot -p` behind the adapter) is one launch per task. A developer
works in one interactive session. This mode measures that session (docs/runbooks/interactive-run.md).

- prepare: `<out>/<run>/off/` and `<out>/<run>/on/`, each one git repository holding `tasks/<ID>/` (each task's base
  tree, built by the engine's own `workspace.task_source`, never its hidden tests) and `.bench/` (next.py, the task
  queue, grade.json). `on` also has the pack installed at its root, so the CLI launched there loads it at startup; `off`
  holds no agent instruction file (checked). The repository's HEAD after prepare is the arm's base. One run per harness.
- The operator launches the CLI in an arm folder and pastes PASTE. next.py hands out one task at a time and records the
  times; a two-turn task's turn-1 tree is snapshotted when turn 2 is handed out. When it closes the last item it starts
  grade.json's command (`bench interactive collect <run> --arm <arm> --open`) detached, so each session ends graded,
  with its arm's report open in Chrome; the session is told nothing of it.
- collect: per arm, each task folder's changes become an overlay that the synthetic agent applies to a fresh cell in a
  replay run through the real engine and grading pass (the path `bench discriminate` uses), so pass/fail, the property
  check and the change-set drift scores are graded exactly as a headless cell's are. Tokens and tool calls come from the
  session's own native record, read by the harness's reader and split per task on the next.py calls.
- gather: after the sessions exit, re-read every graded arm's session records (Copilot writes its usage only at exit)
  and write each run's two-arm report, as Markdown.

Limits (stated in every report): one session per arm; context carries from task to task in a fixed order; the overlay
cannot replay a deleted file (listed as a warning); the catalog's process metrics need a per-cell record and are not
graded here; a harness whose record summarises usage (Copilot's session.shutdown) gives session totals only.
"""

from __future__ import annotations

import filecmp
import json
import os
import re
import shutil
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

from harness_bench import config, engine, gitsafe, plan, readiness, views, workspace
from harness_bench.discriminate import SyntheticLauncher
from harness_bench.errors import BenchError
from harness_bench.grade import judge, runner
from harness_bench.synthetic_agent import SYNTHETIC_VERSION, OverlayError, overlay_files
from harness_bench.telemetry import (
    Extraction,
    agy,
    claude_code,
    codex,
    copilot,
    grok,
    is_not_recorded,
)

ARM_ON = next(a for a in config.PACKS if a != config.ARM_OFF)
ARMS = (config.ARM_OFF, ARM_ON)
MANIFEST = "interactive.json"
SCHEMA = "bench-interactive/1"
NEXT = Path(__file__).with_name("interactive_next.py")
SKIP_DIRS = frozenset({".git", "__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache", ".venv", "venv", "node_modules"})
GIT_TIMEOUT = 120
READERS = {"claude-code": claude_code, "codex": codex, "copilot": copilot, "agy": agy, "grok": grok}
# Where each harness keeps its session records when launched interactively: (home env var, default home, record glob).
RECORD_HOMES = {
    "claude-code": ("CLAUDE_CONFIG_DIR", ".claude", "projects/*/**/*.jsonl"),  # ** reaches <session>/subagents/*.jsonl
    "codex": ("CODEX_HOME", ".codex", "sessions/**/rollout-*.jsonl"),
    "copilot": ("COPILOT_HOME", ".copilot", "session-state/*/events.jsonl"),
    "agy": (None, ".gemini", "antigravity-cli/conversations/*.db"),
}
ALIASES = {"claude": "claude-code"}  # what the operator types for a harness -> its bench name
LEAN_RING = Path("bench") / "rings" / "lean.yaml"  # its BOM subset is the default task list, in queue order
GRADE = "grade.json"  # .bench/grade.json: the command next.py starts when the last item closes
# The pack's dispatcher appends one line per hook dispatch here when the file exists (pack revision 109 on; its
# dispatch.py docstring). prepare creates it in both arms, so the pack's own hook time is measured on every harness.
HOOK_TIMES = Path(".git") / "ai-forward" / "hook-times.jsonl"
HOOK_TIMES_REVISION = 109
# Change-set drift (grade/drift.py; `all_tasks` metrics) graded on the replay. attention_drift and the process metrics
# read the replay's synthetic record, not the session's, so they are not kept.
DRIFT_SCORES = ("scope_creep", "drift_task_implied_lines", "drift_machine_lines")
SCAN_BYTES = 4 << 20  # a record names its cwd near its start; read at most this much to find it
MAX_DB_SCAN = 256 << 20  # an agy db stores the prompt in whichever page sqlite chose; telemetry.MAX_FILE's bound

# The one paste, the same in both arms (docs/benchmarkpromps/interactive-benchmark-prompt.html shows it verbatim;
# tests/test_interactive.py keeps the two equal).
PASTE = """\
You have a short backlog of coding tasks in this folder. Work through them one at a time, as you would on a real project.

1. Run `python .bench/next.py` from this folder. It prints your first task and the folder to work in.
2. Do that task completely, in its folder only.
3. When the task is finished, run the next.py command printed under the task. It prints the next task.
4. Repeat until next.py prints ALL DONE. Then stop.

Keep going through every task without stopping to ask me anything: nobody will answer until the end, so make reasonable
decisions yourself. Work in place in these folders: no git worktrees, branches or copies elsewhere. If you lose track of
which task you are on, `python .bench/next.py --status` prints the current task again without moving on."""


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def _git(args: list[str], cwd: Path) -> str:
    return gitsafe.git(args, cwd=cwd, timeout=GIT_TIMEOUT).stdout


def _items(root: Path, task_ids: list[str]) -> list[dict]:
    """The queue: each task's prompt.md as turn 1, then its `turns:` files, in the order given."""
    items = []
    for tid in task_ids:
        task_dir = root / "tasks" / tid
        task = config.load_yaml(task_dir / "task.yaml")
        prompts = [(task_dir / "prompt.md").read_text(encoding="utf-8")]
        prompts += [(task_dir / rel).read_text(encoding="utf-8") for rel in task.get("turns") or ()]
        items += [{"task": tid, "turn": k, "turns": len(prompts), "prompt": text} for k, text in enumerate(prompts, 1)]
    return items


def harnesses(values: list[str]) -> list[str]:
    """`claude, codex copilot` (commas, spaces or both) -> bench harness names, in order, once each."""
    names = [ALIASES.get(n, n) for v in values for n in (part.strip().lower() for part in v.split(",")) if n]
    unknown = sorted({n for n in names if n not in RECORD_HOMES})
    if unknown or not names:
        raise BenchError("HB-USR-002", f"unknown harness {', '.join(unknown) or '(none given)'}; "
                                       f"one or more of {', '.join(sorted(RECORD_HOMES))} (claude = claude-code)")
    return list(dict.fromkeys(names))


def default_tasks(root: Path) -> list[str]:
    """Every lean task, in the lean ring's order."""
    return list(config.load_yaml(root / LEAN_RING)["bom"]["subset"])


def latest_pack(source: Path) -> tuple[str, str]:
    """(source, commit) for the pack clone's HEAD: the latest pack the operator has."""
    return str(source), _git(["rev-parse", "HEAD"], source).strip()


def prepare(root: Path, run_id: str, harness: str, out_root: Path, task_ids: list[str], pin: tuple[str, str],
            tools_root: Path, bench_argv: list[str] | None = None) -> dict:
    """Build both arm folders and write `<out>/<run>/interactive.json`; returns the manifest. `pin` is the on arm's
    (source, commit); `tools_root` holds the engine's pack checkouts and upstream clones (`.tools/`). `bench_argv` is the
    command that runs this bench (with its path options); with it, each arm's `.bench/grade.json` holds the collect command
    next.py starts when the session closes its last item."""
    upstream_root = tools_root / "upstream"
    missing = [t for t in task_ids if not (root / "tasks" / t / "task.yaml").is_file()]
    if missing or not task_ids:
        raise BenchError("HB-USR-002", f"no task folder for {', '.join(missing) or '(none given)'} under tasks/")
    out_root.mkdir(parents=True, exist_ok=True)
    workspace.check_cells_root(out_root)  # HB-PRE-002: no instruction file above an arm, or both arms would load it
    run_root = out_root / run_id
    if run_root.exists():
        raise BenchError("HB-USR-002", f"{run_root} already exists; an interactive run is prepared once")
    versions = {t: plan.task_version_hash(root / "tasks" / t) for t in task_ids}
    pack_dir = workspace.pack_checkout(Path(pin[0]), pin[1], tools_root / "pack")  # cli.cmd_plan's checkout cache
    items = _items(root, task_ids)
    python = session_python()  # each arm's venv is made from it
    if python is None:
        raise BenchError("HB-PRE-014", "no `python` on PATH to make the arms' environments from")
    versions_seen: set[str] = set()
    arms = {}
    for arm in ARMS:
        arm_dir = run_root / arm
        for tid in task_ids:
            source = workspace.task_source(root / "tasks" / tid, versions[tid], out_root / ".sources", upstream_root)
            shutil.copytree(source, arm_dir / "tasks" / tid, ignore=_tracked_only(source))
        bench = arm_dir / ".bench"
        bench.mkdir()
        shutil.copyfile(NEXT, bench / "next.py")
        (bench / "queue.json").write_text(json.dumps({"schema": "bench-interactive-queue/1", "run_id": run_id, "arm": arm,
                                                      "items": items}, indent=2), encoding="utf-8")
        if bench_argv:
            argv = [*bench_argv, "interactive", "collect", str(run_root.resolve()), "--arm", arm, "--open"]
            (bench / GRADE).write_text(json.dumps({"argv": argv, "cwd": str(root.resolve()),
                                                   "log": str(run_root.resolve() / f"grade-{arm}.log")}, indent=2), encoding="utf-8")
        _git(["init", "-q", "-b", "main"], arm_dir)
        (arm_dir / HOOK_TIMES).parent.mkdir(parents=True, exist_ok=True)
        (arm_dir / HOOK_TIMES).write_text("", encoding="utf-8")  # asks the pack's dispatcher to time itself (REC-UNREAD-A)
        _git(["add", "-A"], arm_dir)
        gitsafe.git(["commit", "-q", "-m", f"interactive base ({arm})"], cwd=arm_dir, timeout=GIT_TIMEOUT, identity=True)
        pack_files = workspace.install_pack(pack_dir, arm_dir, project=run_id, timeout=300) if arm == ARM_ON else []
        workspace.write_eol_rule(arm_dir)  # ARM-FAIR-A: outranks the pack's .gitattributes
        with (arm_dir / ".git" / "info" / "exclude").open("a", encoding="utf-8") as exclude:
            exclude.write("\n.venv/\n")
        versions_seen.add(workspace.make_venv(python, arm_dir / ".venv"))  # ARM-FAIR-A: no shared interpreter
        if arm == config.ARM_OFF:
            found = workspace._instruction_paths(arm_dir)
            if found:  # X-PACKOFF: the pack-off arm loads no agent instruction file
                raise BenchError("HB-PRE-009", f"the pack-off arm holds an instruction file: {found[0]}")
        arms[arm] = {"path": str(arm_dir), "base": _git(["rev-parse", "HEAD"], arm_dir).strip(), "pack_files": len(pack_files)}
    check_arms_alike(*(Path(arms[a]["path"]) for a in ARMS))
    manifest = {"schema": SCHEMA, "run_id": run_id, "harness": harness, "created_at": _now(), "tasks": task_ids, "task_versions": versions,
                "python": {"path": python, "version": ", ".join(sorted(versions_seen))},
                "pack_pin": {"source": pin[0], "commit": pin[1], "revision": workspace.pack_revision(pack_dir)}, "arms": arms}
    (run_root / MANIFEST).write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest


def session_python() -> str | None:
    """The `python` a session launched from the operator's shell resolves to: PATH without the bench's own environment,
    which `uv run bench` puts first (it would make every arm's venv from the bench's interpreter)."""
    own = os.path.normcase(os.path.normpath(sys.prefix))
    path = [p for p in os.environ.get("PATH", "").split(os.pathsep)
            if p and not os.path.normcase(os.path.normpath(p)).startswith(own)]
    return shutil.which("python", path=os.pathsep.join(path))


def _tracked_only(source: Path):
    """A copytree `ignore` keeping only the files the task source's base commit tracks, and the folders that hold them:
    the replay's cell is a clone of that commit, so an ignored or stray file in the source folder never reaches an arm
    (run 20261015T1529: S1's ignored files were replayed as the agent's new files)."""
    tracked = {p for p in _git(["ls-files", "-z"], source).split("\0") if p}
    folders = {str(Path(p).parent.as_posix()) for p in tracked}
    folders |= {f.rsplit("/", k)[0] for f in list(folders) for k in range(1, f.count("/") + 1)}

    def ignore(directory: str, names: list[str]) -> list[str]:
        rel = Path(directory).relative_to(source).as_posix()
        prefix = "" if rel == "." else rel + "/"
        return [n for n in names if prefix + n not in tracked and prefix + n not in folders]
    return ignore


def check_arms_alike(off_dir: Path, on_dir: Path) -> None:
    """HB-PRE-013: every task file has the same index and working-tree line endings and the same line-ending rule in both
    arms, so the pack is the only difference a session meets (ARM-FAIR-A)."""
    rows = {d: _git(["ls-files", "-z", "--eol", "--", "tasks"], d).split("\0") for d in (off_dir, on_dir)}
    for off_row, on_row in zip(rows[off_dir], rows[on_dir], strict=False):
        if off_row.split() != on_row.split():
            raise BenchError("HB-PRE-013", f"the arms differ in line endings: off {off_row!r}, on {on_row!r}")
    if len(rows[off_dir]) != len(rows[on_dir]):
        raise BenchError("HB-PRE-013", f"the arms track {len(rows[off_dir])} and {len(rows[on_dir])} task files")


def python_warnings(arm_dir: Path, state: dict) -> list[str]:
    """The session must run its arm's own .venv (ARM-FAIR-A); next.py records the interpreter that ran it."""
    ran = (state.get("python") or {}).get("prefix")
    if ran is None:
        return ["next.py recorded no interpreter: whether the session used the arm's .venv is not recorded"]
    norm = lambda p: os.path.normcase(os.path.normpath(str(p)))
    if norm(ran) != norm(arm_dir / ".venv"):
        return [(f"next.py ran under {ran}, not the arm's .venv: the session shared an interpreter (activate .venv "
                 "before launching the CLI)")]
    return []


def load(run_root: Path) -> dict:
    path = run_root / MANIFEST
    if not path.is_file():
        raise BenchError("HB-USR-002", f"{path} not found; run `bench interactive prepare` first")
    manifest = json.loads(path.read_text(encoding="utf-8"))
    if manifest.get("schema") != SCHEMA:
        raise BenchError("HB-USR-002", f"{path}: schema {manifest.get('schema')!r}, expected {SCHEMA}")
    return manifest


# --- collect: the overlays -----------------------------------------------------------------------------------------

def _skipped(rel: str) -> bool:
    return any(part in SKIP_DIRS for part in rel.split("/"))


def _changes(arm_dir: Path, base: str, tid: str) -> tuple[list[str], list[str]]:
    """(changed or new files, deleted files) under tasks/<tid>/ against the base (committed or not), relative to the
    task folder. `-z` keeps a non-ASCII name unquoted."""
    prefix = f"tasks/{tid}/"
    changed, deleted = [], []
    parts = _git(["diff", "-z", "--name-status", "--no-renames", base, "--", prefix], arm_dir).split("\0")
    for status, path in zip(parts[0::2], parts[1::2]):
        (deleted if status.startswith("D") else changed).append(path)
    changed += [p for p in _git(["ls-files", "-z", "--others", "--", prefix], arm_dir).split("\0") if p]
    keep = lambda paths: sorted({p[len(prefix):] for p in paths if p.startswith(prefix) and not _skipped(p[len(prefix):])})
    return keep(changed), keep(deleted)


def _copy(files: list[str], src_root: Path, dest: Path) -> None:
    dest.mkdir(parents=True, exist_ok=True)
    for rel in files:
        (dest / rel).parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src_root / rel, dest / rel)


def _tree_files(root: Path) -> list[str]:
    """Every file of a turn snapshot (next.py copied the whole task folder): an unchanged file overlays as a no-op."""
    return sorted(rel for rel in (p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file()) if not _skipped(rel))


def _handed_off(arm_dir: Path, base: str, tid: str, snap: Path) -> tuple[list[str], list[str], list[str]]:
    """(every file of the hand-off copy, the base files it lacks, the files that differ in the final tree since): the
    task as next.py closed it, and what a later task did to its folder afterwards."""
    prefix = f"tasks/{tid}/"
    files = _tree_files(snap)
    listed = (p[len(prefix):] for p in _git(["ls-tree", "-r", "-z", "--name-only", base, "--", prefix], arm_dir).split("\0") if p)
    deleted = sorted(rel for rel in listed if not _skipped(rel) and not (snap / rel).is_file())
    live = arm_dir / "tasks" / tid
    later = sorted(rel for rel in set(files) | set(_tree_files(live) if live.is_dir() else [])
                   if not ((snap / rel).is_file() and (live / rel).is_file() and filecmp.cmp(snap / rel, live / rel, shallow=False)))
    return files, deleted, later


def build_overlays(manifest: dict, arm: str, items: list[dict], state: dict, dest: Path) -> tuple[dict[str, Path], list[str]]:
    """task id -> overlay folder (with turn-<n>/ folders for a multi-turn task), and the warnings. Each task's last turn is
    graded from next.py's copy at its hand-off (TASK-ISO-A), or from the final tree when there is none: the item still
    open at the end, or an arm whose next.py kept a copy only of a two-turn task's turn 1."""
    arm_dir, base = Path(manifest["arms"][arm]["path"]), manifest["arms"][arm]["base"]
    closed = {(d["task"], d["turn"]) for d in state.get("done", [])}
    opened = closed | ({(state["open"]["task"], state["open"]["turn"])} if state.get("open") else set())
    overlays, warnings = {}, []
    for tid in manifest["tasks"]:
        turns = max(i["turns"] for i in items if i["task"] == tid)
        folder = dest / tid
        snap = arm_dir / ".bench" / "snapshots" / tid / f"turn-{turns}"
        if snap.is_dir():
            src = snap
            files, deleted, later = _handed_off(arm_dir, base, tid, snap)
            if later:
                warnings.append(f"{tid}: {len(later)} file(s) changed after its hand-off (a later task's edits) are not graded: "
                                f"{', '.join(later[:5])}")
        else:
            src = arm_dir / "tasks" / tid
            files, deleted = _changes(arm_dir, base, tid)
            if (tid, turns) in closed:
                warnings.append(f"{tid}: next.py kept no copy at its hand-off; graded from the final tree, which a later task "
                                "may have changed")
        if deleted:
            warnings.append(f"{tid}: {len(deleted)} deleted file(s) cannot be replayed and stay in the graded tree: {', '.join(deleted[:5])}")
        if (tid, 1) not in opened:
            warnings.append(f"{tid}: never handed out (next.py did not reach it)")
        for d in state.get("done", []):
            if d["task"] == tid and isinstance(d.get("commit"), dict) and "error" in d["commit"]:
                warnings.append(f"{tid} turn {d['turn']}: next.py could not commit the task folder ({d['commit']['error']})")
        if turns == 1:
            _copy(files, src, folder)
        else:
            first = arm_dir / ".bench" / "snapshots" / tid / "turn-1"
            if first.is_dir():
                _copy(_tree_files(first), first, folder / "turn-1")
                _copy(files, src, folder / f"turn-{turns}")
            else:  # turn 2 was never handed out: the final tree is turn 1's, and the later turns change nothing
                _copy(files, src, folder / "turn-1")
                warnings.append(f"{tid}: turn 2 never handed out; the tree is graded as turn 1 with no turn 2 work")
            for k in range(2, turns + 1):
                (folder / f"turn-{k}").mkdir(parents=True, exist_ok=True)
        try:
            overlay_files(folder)
        except OverlayError as exc:
            warnings.append(f"{tid}: overlay refused ({exc}); the task is graded on its base tree")
            shutil.rmtree(folder)
            folder.mkdir(parents=True)
        overlays[tid] = folder
    return overlays, warnings


class ReplayLauncher(SyntheticLauncher):
    """The synthetic agent, with one overlay per task instead of one per combo."""

    def argv_env(self, cell: dict, home: Path, traceparent: str):
        return super().argv_env(cell | {"combo": cell["task"]}, home, traceparent)


def replay(root: Path, manifest: dict, arm: str, overlays: dict[str, Path], runs: Path, cells_root: Path,
           upstream_root: Path) -> tuple[str, dict]:
    """Grade the overlays through the real engine and an in-run grading pass; (replay run id, task -> scores)."""
    run_id = f"{manifest['run_id']}-{arm}-replay-{datetime.now(UTC):%Y%m%dT%H%M%S}"
    run_dir = runs / run_id
    matrix = {"schema": "bench-matrix/1", "run_id": run_id, "bom": {"subset": manifest["tasks"]}, "packs": [config.ARM_OFF],
              "repetitions": 1, "combos": [{"id": f"interactive-{arm}", "harness": "synthetic", "model": "synthetic-1"}]}
    bom = config.load_yaml(root / "bench" / "bom.yaml")
    p = plan.build_plan(root, matrix, bom, run_id, {"synthetic": {"version": SYNTHETIC_VERSION}}, parallelism=4, kind="discrimination")
    seen = seen_changes(root, manifest, arm, cells_root / ".sources", upstream_root)
    refused = {t: what for t, what in seen.items() if what}
    if refused:
        raise BenchError("HB-PRE-007", "task(s) changed since prepare in what the session saw: "
                                       + "; ".join(f"{t} ({', '.join(what)})" for t, what in refused.items()))
    notes = [f"{t}: changed since prepare only in what grades it (its base tree and prompt are unchanged); graded with the "
             "current version" for t in seen]
    plan.confirm(run_dir, p)
    cells_root.mkdir(parents=True, exist_ok=True)
    workspace.check_cells_root(cells_root)

    def build(cell: dict, cell_dir: Path) -> dict:
        source = workspace.task_source(root / "tasks" / cell["task"], cell["task_version"], cells_root / ".sources", upstream_root)
        workspace.cell_working_copy(source, cell_dir / "ws")
        return {"arm": config.ARM_OFF, "pack_manifest": 0}

    cfg = engine.EngineConfig(run_dir=run_dir, cells_root=cells_root, launchers={"synthetic": ReplayLauncher(overlays)},
                              build_workspace=build, grade=lambda d: runner.run_pass(d, root, judge.IN_RUN, cells_root=cells_root).summary())
    handler = engine.configure_logging(run_dir, p["trace_id"])
    try:
        summary = engine.Engine(p, cfg).run()
    finally:
        engine.log.removeHandler(handler)
        handler.close()
    passes = views.completed_passes(run_dir)
    if summary.exit_code != 0 or len(passes) != 1:
        raise BenchError("HB-RUN-001", f"replay run {run_id} did not complete with one grading pass (exit {summary.exit_code})")
    keep = set(readiness.CORRECTNESS_SCORES) | set(DRIFT_SCORES)
    for tid in manifest["tasks"]:
        task = config.load_yaml(root / "tasks" / tid / "task.yaml")
        if task.get("property"):
            keep |= set(readiness.recorded_metrics(root, task))
    (grading_id,) = passes
    scores, _pointers = readiness.run_scores(run_dir, grading_id, {c["cell_id"]: c["task"] for c in p["cells"]}, keep)
    return run_id, scores, notes


def _blob_ids(listing: str, sha_field: int, prefix: str = "") -> dict[str, str]:
    """path (less `prefix`) -> blob id, from `git ls-files -s -z` (sha field 1) or `git ls-tree -r -z` (field 2)."""
    rows = (entry.split("\t", 1) for entry in listing.split("\0") if entry)
    return {path[len(prefix):]: meta.split()[sha_field] for meta, path in rows}


def seen_changes(root: Path, manifest: dict, arm: str, sources_root: Path, upstream_root: Path) -> dict[str, list[str]]:
    """Each task whose folder changed since prepare -> what changed of what the session saw: `base tree` (the current
    base's blobs against the arm's base commit, both staged by gitsafe from the same files) and `prompt` (the queue's
    text against the task's). An empty list: only what grades the task changed (its oracle, hidden tests, expectations),
    so the session's work can be re-graded with the current version (S2's recalibration after run 20261015T1529)."""
    arm_dir, items, _state = _arm_state(manifest, arm)
    base = manifest["arms"][arm]["base"]
    out = {}
    for tid in manifest["tasks"]:
        task_dir = root / "tasks" / tid
        version = plan.task_version_hash(task_dir)
        if version == manifest["task_versions"][tid]:
            continue
        source = workspace.task_source(task_dir, version, sources_root, upstream_root)
        prefix = f"tasks/{tid}/"
        what = []
        if _blob_ids(_git(["ls-files", "-s", "-z"], source), 1) != _blob_ids(_git(["ls-tree", "-r", "-z", base, "--", prefix], arm_dir), 2, prefix):
            what.append("base tree")
        if [i["prompt"] for i in _items(root, [tid])] != [i["prompt"] for i in items if i["task"] == tid]:
            what.append("prompt")
        out[tid] = what
    return out


# --- collect: the session record -----------------------------------------------------------------------------------

def _path_forms(path: Path) -> list[bytes]:
    text = str(path)
    forms = {text, text.replace("\\", "/"), text.replace("\\", "\\\\")}
    return [f.lower().encode() for f in forms]


def _first_value(value, key: str) -> str | None:
    """The first string under `key` in a parsed JSON value, a level's own key before its children's."""
    if isinstance(value, dict):
        if isinstance(value.get(key), str):
            return value[key]
        value = list(value.values())
    if isinstance(value, list):
        return next((c for c in (_first_value(v, key) for v in value) if c), None)
    return None


def _head_value(head: bytes, key: str) -> str | None:
    for line in head.splitlines():
        try:
            found = _first_value(json.loads(line), key)
        except ValueError:
            continue
        if found:
            return found
    return None


def _launch_dir(head: bytes) -> str | None:
    """The folder a JSONL record says its session was launched in: the first `cwd` in it (Claude Code: every line's
    `cwd`; Codex: `session_meta.payload.cwd`; Copilot: `session.start.data.context.cwd`)."""
    return _head_value(head, "cwd")


# Where a record names the CLI build that wrote it (checked on the 2026-10-15 records). Copilot's `version` is the
# events schema's, not the CLI's. agy's conversation db names none.
CLI_VERSION_KEYS = {"claude-code": "version", "codex": "cli_version", "copilot": "copilotVersion"}


def cli_version(harness: str, head: bytes) -> str | None:
    key = CLI_VERSION_KEYS.get(harness)
    return _head_value(head, key) if key else None


def cli_build_warnings(arms: dict[str, dict]) -> list[str]:
    """ARM-FAIR-A: both arms must run one CLI build. A difference, or a build not recorded, is a warning."""
    builds = {a: sorted(set((s.get("session") or {}).get("cli_versions") or [])) for a, s in arms.items()}
    if any(not b for b in builds.values()):
        return ["the CLI build is not recorded for " + ", ".join(a for a, b in builds.items() if not b)
                + "; whether the arms ran one build is unknown"]
    if len({tuple(b) for b in builds.values()}) > 1:
        return ["the arms ran different CLI builds (" + "; ".join(f"{a} {', '.join(b)}" for a, b in builds.items())
                + "): an update landed between the launches, so the pack is not the only difference"]
    return []


def served_model_warnings(arms: dict[str, dict]) -> list[str]:
    """Both arms must be served one model. Copilot starts on its default model and the operator picks the run's model
    by hand in each window (run int-copilot-20261015T1529: gpt-5.5 at start, gpt-6.1-sol from the picker), so a window
    can be missed. A model not recorded in either arm is no warning here; the served settings say so."""
    models = {a: ((s.get("session") or {}).get("served") or {}).get("model_served") for a, s in arms.items()}
    known = {a: m for a, m in models.items() if isinstance(m, str) and not m.startswith("not recorded")}
    if len(known) == len(models) and len(set(known.values())) > 1:
        return ["the arms were served different models (" + "; ".join(f"{a} {m}" for a, m in known.items())
                + "): the model is not the same in both windows, so the pack is not the only difference"]
    return []


def _same_dir(recorded: str, arm_dir: Path) -> bool:
    drive = re.match(r"^/([a-zA-Z])(/|$)", recorded)  # Claude Code on Windows writes Git Bash's /c/... form
    if drive:
        recorded = f"{drive.group(1)}:/{recorded[3:]}"
    norm = lambda p: os.path.normcase(os.path.normpath(str(p)))
    return norm(recorded) == norm(arm_dir)


def find_records(harness: str, arm_dir: Path, since: float, home: Path | None = None) -> list[Path]:
    """The harness's session records modified since `since` (epoch seconds) that were launched in the arm folder. A JSONL
    record matches by the folder it states (`_launch_dir`), never by a mention: a session that prints the other arm's path
    is not that arm's (run int-copilot-20261015T1529). An agy db states no folder, so it matches by its prompt's
    workspace path anywhere in the file."""
    if harness not in RECORD_HOMES:
        raise BenchError("HB-USR-002", f"no interactive record location known for {harness!r}; pass --record")
    env, default, pattern = RECORD_HOMES[harness]
    base = Path(os.environ[env]) if env and os.environ.get(env) else (home or Path.home()) / default
    found = []
    for path in base.glob(pattern):
        try:
            if path.stat().st_mtime < since:
                continue
        except OSError:
            continue
        if _launched_in(path, arm_dir):
            found.append(path)
    return sorted(found, key=lambda p: p.stat().st_mtime)


def _launched_in(path: Path, arm_dir: Path) -> bool:
    """A JSONL record by the folder it states; an agy db by its prompt's workspace path anywhere in it."""
    try:
        with path.open("rb") as fh:
            head = fh.read(SCAN_BYTES if path.suffix != ".db" else MAX_DB_SCAN)
    except OSError:
        return False
    if path.suffix == ".db":
        return any(f in head.lower() for f in _path_forms(arm_dir))
    launched = _launch_dir(head)
    return launched is not None and _same_dir(launched, arm_dir)


def _is_next(command: str | None) -> bool:
    return bool(command) and re.search(r"\.bench[\\/]+next\.py", command) is not None and "--status" not in command


HANDOUT_SLACK_S = 2  # state.json stamps whole seconds; a record stamps the call's start and end


def task_boundaries(ex: Extraction, trace, state: dict) -> tuple[list[int], list[int]]:
    """(boundaries, rejected): the ordinals of the next.py calls that handed something out, and of those that did not.
    A call naming next.py is a boundary only when a hand-out next.py recorded (an item's start, or the ALL DONE close)
    falls in its time window; each hand-out is used once, in order. A call the record gives no times is kept unless it
    failed. Run int-codex-20261015T1529: a blocked cell naming next.py shifted every later task by one label."""
    entries = [*state.get("done", []), *([state["open"]] if state.get("open") else [])]
    handouts = [datetime.fromisoformat(d["start"]) for d in entries]
    if entries and not state.get("open") and entries[-1].get("end"):
        handouts.append(datetime.fromisoformat(entries[-1]["end"]))  # the call that printed ALL DONE
    tools = {t.native_ordinal: t for t in ex.tool_calls}
    kept, rejected, k = [], [], 0
    for ordinal in sorted(c.native_ordinal for c in trace.calls if _is_next(c.command)):
        tool = tools.get(ordinal)
        start, end = (_when(tool.start), _when(tool.end) or _when(tool.start)) if tool else (None, None)
        if start is None:
            (rejected if tool is not None and tool.ok is False else kept).append(ordinal)
            continue
        slack = timedelta(seconds=HANDOUT_SLACK_S)
        while k < len(handouts) and handouts[k] < start - slack:
            k += 1
        if k < len(handouts) and handouts[k] <= end + slack:
            kept.append(ordinal)
            k += 1
        else:
            rejected.append(ordinal)
    return kept, rejected


def _peeks(trace) -> int:
    """Tool calls that read the queue, the progress file or the snapshots (next.py hands those out itself)."""
    pat = re.compile(r"\.bench[\\/]+(queue\.json|state\.json|snapshots)", re.IGNORECASE)
    return sum(1 for c in trace.calls if any(pat.search(p) for p in c.paths) or (c.command and pat.search(c.command)))


TOKEN_FIELDS = ("uncached_input", "cache_read", "cache_write", "output", "reasoning")


def _zero() -> dict:
    return {**dict.fromkeys(TOKEN_FIELDS, 0), "model_calls": 0, "tool_calls": 0, "tool_failures": 0, "tool_failures_exit": 0}


def _count_tool(seg: dict, tool) -> None:
    """One tool call into a segment. `tool_failures_exit` is the failures that were a command returning non-zero
    (`outcome_code` `exit_<N>`): it ran, and the exit is often intended (a `grep` with no match, a test run expected to
    fail), so `tool_failures` alone is not agent error."""
    seg["tool_calls"] += 1
    seg["tool_failures"] += tool.ok is False
    seg["tool_failures_exit"] += tool.ok is False and (tool.outcome_code or "").startswith("exit_")


def _add(seg: dict, call) -> None:
    for f in TOKEN_FIELDS:
        value = getattr(call, f)
        seg[f] = None if seg[f] is None or value is None else seg[f] + value
    seg["model_calls"] += call.requests


def split(ex: Extraction, boundaries: list[int], labels: list[str]) -> dict[str, dict]:
    """Totals per segment: `setup` before the first next.py call, then labels[k] from the k-th call, `wrap-up` after
    the labels run out. A summary row (requests > 1) cannot be placed in a segment: the per-segment tokens are then
    `None` (not recorded) and only the session total holds them."""
    names = ["setup", *labels[: len(boundaries)]]
    if len(boundaries) > len(labels):
        names.append("wrap-up")
    segs = {n: _zero() for n in names}

    def seg_of(ordinal: int) -> str:
        k = sum(1 for b in boundaries if b <= ordinal)
        return names[min(k, len(names) - 1)]

    summarised = any(c.requests > 1 for c in ex.model_calls)
    for call in ex.model_calls:
        _add(segs[seg_of(call.native_ordinal)], call)
    if summarised:
        for seg in segs.values():
            seg.update(dict.fromkeys(TOKEN_FIELDS))
    for tool in ex.tool_calls:
        _count_tool(segs[seg_of(tool.native_ordinal)], tool)
    return segs


def _when(stamp: str | None) -> datetime | None:
    try:
        return datetime.fromisoformat(stamp) if stamp else None
    except ValueError:
        return None


def split_by_time(ex: Extraction, windows: list[tuple[str, datetime, datetime | None]]) -> dict[str, dict]:
    """Totals per item for a record with no next.py call in it (a sub-agent's own record, or a resumed session's): each
    call goes to the item whose next.py start/end window holds its start time, else to `unattributed`. A call with no
    time, or a summary row, is `unattributed`."""
    def name_of(stamp: str | None, summary: bool = False) -> str:
        when = _when(stamp)
        if when is None or summary:
            return "unattributed"
        return next((label for label, start, end in windows if start <= when and (end is None or when <= end)), "unattributed")

    segs: dict[str, dict] = {}
    for call in ex.model_calls:
        _add(segs.setdefault(name_of(call.start, call.requests > 1), _zero()), call)
    for tool in ex.tool_calls:
        _count_tool(segs.setdefault(name_of(tool.start), _zero()), tool)
    return segs


def _merge(into: dict, seg: dict) -> None:
    for f, value in seg.items():
        if f in TOKEN_FIELDS:
            into[f] = None if into[f] is None or value is None else into[f] + value
        else:
            into[f] += value


def windows_of(items: list[dict], state: dict) -> list[tuple[str, datetime, datetime | None]]:
    """(item label, start, end) for every item next.py handed out; the open item has no end."""
    out = []
    for d in [*state.get("done", []), *([state["open"]] if state.get("open") else [])]:
        out.append((_label(items[d["index"]]), datetime.fromisoformat(d["start"]), datetime.fromisoformat(d["end"]) if d.get("end") else None))
    return out


def _label(item: dict) -> str:
    return item["task"] + (f" turn {item['turn']}" if item["turns"] > 1 else "")


def _served(ex: Extraction) -> dict:
    served = ex.served
    if isinstance(served, tuple):
        served = served[0] if served else None
    if served is None or isinstance(served, str):
        return {"note": served or "not recorded"}
    out = {}
    for f in ("model_served", "model_api", "effort", "context_tokens", "context_tier"):
        value = getattr(served, f)
        out[f] = value[1] if is_not_recorded(value) else value
    return out


def _read(harness: str, path: Path):
    """(extraction, trace) of one record; an agy conversation db alone is read by the db reader."""
    if harness == "agy" and path.suffix == ".db":
        return agy.read_db(path), agy.tool_inputs_db(path)
    reader = READERS[harness]
    return reader.read(path), reader.tool_inputs(path)


def session_metrics(harness: str, records: list[Path], items: list[dict], state: dict | None = None) -> dict:
    """The session's totals, its per-item split (summed over its records) and its notes, from its own records."""
    labels = [_label(i) for i in items]
    windows = windows_of(items, state or {})
    total, per_item, notes, served, peeks = _zero(), {}, [], [], 0
    builds: set[str] = set()
    hooks: int | None = 0
    hook_rows: list[dict] | str = []  # every hook the records time (pack and user-level), or why a reader keeps none
    model_rows: list[dict] = []
    tool_rows: list[dict] = []
    for path in records:
        ex, trace = _read(harness, path)
        boundaries, rejected = task_boundaries(ex, trace, state or {})
        if rejected:
            notes.append(f"{path.name}: {len(rejected)} call(s) naming next.py handed nothing out (blocked or failed); "
                         "they are not task boundaries")
        segs =split(ex, boundaries, labels) if boundaries else split_by_time(ex, windows)
        for name, seg in segs.items():
            if name in labels or name == "unattributed":
                _merge(per_item.setdefault(name, _zero()), seg)
        for f in TOKEN_FIELDS:  # the record's own total, so a summary row still counts in the session total
            values = [getattr(c, f) for c in ex.model_calls]
            rec = None if any(v is None for v in values) else sum(values)
            total[f] = None if total[f] is None or rec is None else total[f] + rec
        total["model_calls"] += sum(c.requests for c in ex.model_calls)
        for tool in ex.tool_calls:
            _count_tool(total, tool)
        model_rows += [{"start": c.start, "end": c.end} for c in ex.model_calls]
        tool_rows += [{"start": t.start, "end": t.end} for t in ex.tool_calls]
        if any(c.requests > 1 for c in ex.model_calls):
            notes.append(f"{path.name}: usage is a session summary; per-task tokens are not recorded")
        if ex.missing:
            notes.append(f"{path.name}: {len(ex.missing)} usage field(s) not recorded (HB-TEL-001)")
        if ex.malformed_lines or ex.truncated:
            notes.append(f"{path.name}: {ex.malformed_lines} malformed line(s), truncated={ex.truncated}")
        if not boundaries:
            notes.append(f"{path.name}: no next.py call in this record (a sub-agent's, or a resumed session's); its calls "
                         "are placed in tasks by their start time")
        served.append(_served(ex))
        try:
            with path.open("rb") as fh:
                build = cli_version(harness, fh.read(SCAN_BYTES))
        except OSError:
            build = None
        if build:
            builds.add(build)
        hooks = None if hooks is None else _pack_hooks(harness, ex, hooks)
        if isinstance(hook_rows, list):
            hook_rows = (ex.harness_events if isinstance(ex.harness_events, str) else
                         hook_rows + [{"start": e.start, "end": e.end} for e in ex.harness_events if e.event == "hook"])
        peeks += _peeks(trace)
    hook_ms = views.hook_time(harness, hook_rows) if isinstance(hook_rows, list) else views.Measure(None, hook_rows)
    # The per-cell views' rules (views.time_anatomy): the union of the calls' spans, NOT_RECORDED when one lacks an end.
    model_ms = (views.busy_ms(model_rows, positive=True, missing=views.NO_MODEL_START) if model_rows
                else views.Measure(None, views.NO_MODEL_START))
    tool_ms = views.busy_ms(tool_rows)
    return {"records": [str(p) for p in records], "total": total, "per_item": per_item, "served": served, "cli_versions": sorted(builds),
            "pack_hook_events": hooks, "hook_events": len(hook_rows) if isinstance(hook_rows, list) else None,
            "hook_ms": hook_ms.value, "hook_ms_reason": hook_ms.reason, "model_ms": model_ms.value,
            "model_ms_reason": model_ms.reason, "tool_ms": tool_ms.value, "tool_ms_reason": tool_ms.reason,
            "queue_reads": peeks, "notes": notes}


PACK_HOOK = "ai-forward-pack"  # every pack hook runs a script under docs/ai-forward-pack/hooks/ (its command names it)


def _pack_hooks(harness: str, ex: Extraction, so_far: int) -> int | None:
    """The pack's own hook events (the operator's user-level hooks run in both arms and are not counted). None where the
    record cannot show it: a reader that records no hook events (Codex, agy), or one that names only the event, never
    the command (Copilot's `sessionStart`, `agentStop`... rows)."""
    if not isinstance(ex.harness_events, list) or harness == "copilot":
        return None
    return so_far + sum(1 for e in ex.harness_events if e.event == "hook" and PACK_HOOK in f"{e.name} {e.detail}")


def pack_hook_time(arm_dir: Path, revision: int) -> dict:
    """The pack's hooks as its dispatcher timed them in this arm: `{dispatches, ms, reason}`. Not recorded (with the
    reason) for a pack that does not time itself, an arm prepared without the file, or a line that is not a timing row;
    never a partial sum. A pack-off arm reads 0 dispatches: no pack hook ran there."""
    path = arm_dir / HOOK_TIMES
    if revision < HOOK_TIMES_REVISION:
        return {"dispatches": None, "ms": None, "reason": f"pack revision {revision} does not time its hooks "
                                                          f"(revision {HOOK_TIMES_REVISION} on)"}
    if not path.is_file():
        return {"dispatches": None, "ms": None, "reason": f"no {HOOK_TIMES.as_posix()} in the arm"}
    total, count = 0.0, 0
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            ms = json.loads(line)["ms"]
        except (ValueError, KeyError, TypeError):
            ms = None
        if not isinstance(ms, (int, float)) or isinstance(ms, bool):
            return {"dispatches": None, "ms": None, "reason": f"{HOOK_TIMES.as_posix()} holds a line that is not a timing row"}
        total, count = total + ms, count + 1
    return {"dispatches": count, "ms": round(total), "reason": None}


def _minutes(state: dict) -> dict[str, float]:
    out = {}
    for d in state.get("done", []):
        start, end = datetime.fromisoformat(d["start"]), datetime.fromisoformat(d["end"])
        out[f"{d['task']}|{d['turn']}"] = round((end - start).total_seconds() / 60, 1)
    return out


def outside_task_folders(arm_dir: Path, base: str) -> list[str]:
    """Files changed, added or deleted in the arm outside `tasks/` and `.bench/`: work that left the task folders."""
    spec = ["--", ".", ":(exclude)tasks", ":(exclude).bench"]
    tracked = _git(["diff", "-z", "--name-only", "--no-renames", base, *spec], arm_dir).split("\0")
    untracked = _git(["ls-files", "-z", "--others", *spec], arm_dir).split("\0")
    return sorted({p for p in tracked + untracked if p and not _skipped(p)})


def _arm_state(manifest: dict, arm: str) -> tuple[Path, list[dict], dict]:
    arm_dir = Path(manifest["arms"][arm]["path"])
    queue = json.loads((arm_dir / ".bench" / "queue.json").read_text(encoding="utf-8"))
    state_path = arm_dir / ".bench" / "state.json"
    state = json.loads(state_path.read_text(encoding="utf-8")) if state_path.is_file() else {"done": [], "open": None}
    return arm_dir, queue["items"], state


def read_session(manifest: dict, arm: str, harness: str, records: list[Path] | None = None) -> tuple[dict | None, list[str]]:
    """(the session's metrics from its own records, the warnings about them); found by search when `records` is None."""
    arm_dir, items, state = _arm_state(manifest, arm)
    found = records or find_records(harness, arm_dir, datetime.fromisoformat(manifest["created_at"]).timestamp())
    if not found:
        return None, [f"no {harness} session record names {arm_dir}; tokens and tool calls are not recorded (pass --record)"]
    session, warnings = session_metrics(harness, found, items, state), []
    if len(found) > 1:
        warnings.append(f"{len(found)} session records name this arm (a restart or sub-agents); all are summed")
    if session["queue_reads"]:
        warnings.append(f"{session['queue_reads']} tool call(s) read .bench/ files directly (the queue, progress or snapshots)")
    if arm == ARM_ON and session["pack_hook_events"] == 0:
        warnings.append("the pack-on session's record shows no pack hook event: the pack's hooks did not run (folder trust?)")
    if arm == config.ARM_OFF and session["pack_hook_events"]:
        warnings.append(f"the pack-off session's record shows {session['pack_hook_events']} pack hook event(s): the arm is not pack-free")
    return session, warnings


def collect(root: Path, run_root: Path, arm: str, harness: str, runs: Path, cells_root: Path, upstream_root: Path,
            records: list[Path] | None = None) -> dict:
    """Grade one arm and read its session; writes `<run>/collect/<arm>/summary.json` and returns it."""
    manifest = load(run_root)
    arm_dir, items, state = _arm_state(manifest, arm)
    out = run_root / "collect" / arm
    if out.exists():
        shutil.rmtree(out)
    overlays, warnings = build_overlays(manifest, arm, items, state, out / "overlays")
    outside = outside_task_folders(arm_dir, manifest["arms"][arm]["base"])
    if outside:
        warnings.append(f"{len(outside)} file(s) changed outside the task folders (not graded): {', '.join(outside[:5])}")
    warnings += python_warnings(arm_dir, state)
    session, session_warnings = read_session(manifest, arm, harness, records)
    if state.get("open") or len(state.get("done", [])) < len(items):
        warnings.append(f"{len(state.get('done', []))} of {len(items)} items finished (next.py never printed ALL DONE)")
    replay_id, scores, notes = replay(root, manifest, arm, overlays, runs, cells_root, upstream_root)
    warnings += notes
    summary = {"schema": "bench-interactive-summary/1", "run_id": manifest["run_id"], "arm": arm, "harness": harness,
               "collected_at": _now(), "replay_run": replay_id, "scores": scores, "minutes": _minutes(state),
               "outside_task_folders": outside, "session": session, "session_read_at": _now(),
               "session_warnings": session_warnings, "warnings": warnings,
               "pack_hook_time": pack_hook_time(arm_dir, manifest["pack_pin"]["revision"])}
    out.mkdir(parents=True, exist_ok=True)
    (out / "summary.json").write_text(json.dumps(summary, indent=2, default=str), encoding="utf-8")
    return summary


def refresh_session(run_root: Path, arm: str) -> dict:
    """Re-read a graded arm's session records (after the CLI exited: Copilot writes its usage only then) into its
    summary.json. The records the arm's grading read are re-read; only when it read none is the search run again. A new
    search would also match any later session that named the arm folder, such as the analysis session reading its work
    (seen in the 2026-10-15 smoke). A kept record launched in another folder is dropped, with a warning: a grading from
    before REC-ATTR-A's fix kept it by a mention."""
    manifest = load(run_root)
    path = run_root / "collect" / arm / "summary.json"
    summary = json.loads(path.read_text(encoding="utf-8"))
    listed = [Path(r) for r in (summary["session"] or {}).get("records", []) if Path(r).is_file()]
    known = [r for r in listed if _launched_in(r, Path(manifest["arms"][arm]["path"]))]
    summary["session"], summary["session_warnings"] = read_session(manifest, arm, summary["harness"], known or None)
    dropped = [str(r) for r in listed if r not in known]
    if dropped:
        summary["session_warnings"].append(f"{len(dropped)} record(s) the grading read were launched in another folder and "
                                           f"are no longer read: {', '.join(dropped)}")
    summary["session_read_at"] = _now()
    summary["pack_hook_time"] = pack_hook_time(Path(manifest["arms"][arm]["path"]), manifest["pack_pin"]["revision"])
    path.write_text(json.dumps(summary, indent=2, default=str), encoding="utf-8")
    return summary


def gather(out_root: Path) -> list[dict]:
    """Every interactive run under `out_root`: re-read each graded arm's session and write the run's two-arm report.
    One row per run: run folder, harness, arm -> `graded` or `not graded`, and the report (None until an arm is graded)."""
    rows = []
    for manifest_path in sorted(out_root.glob(f"*/{MANIFEST}")):
        run_root = manifest_path.parent
        manifest = load(run_root)
        status = {arm: "graded" if (run_root / "collect" / arm / "summary.json").is_file() else "not graded" for arm in ARMS}
        for arm, state in status.items():
            if state == "graded":
                refresh_session(run_root, arm)
        graded = any(s == "graded" for s in status.values())
        if graded:
            report(run_root)
        rows.append({"run": str(run_root), "harness": manifest["harness"], "arms": status,
                     "report": str(run_root / "interactive-report.md") if graded else None})
    return rows


# --- report ---------------------------------------------------------------------------------------------------------

def _score(value) -> str:
    if isinstance(value, dict):
        return f"NA ({value.get('na')})"
    return "-" if value is None else str(value)


def _num(value) -> str:
    return "not recorded" if value is None else f"{value:,}" if isinstance(value, int) else str(value)


def _seconds(found: dict | None, key: str, count: str | None = None, noun: str = "") -> str:
    """`<s> s` (`over <n> <noun>` with `count`), or `not recorded (<reason>)` from `<key>_reason` / `reason`; a summary
    collected before the measure existed reads `not recorded`."""
    if not found or key not in found:
        return "not recorded"
    if found[key] is None:
        reason = found.get(f"{key}_reason", found.get("reason")) or ""
        return reason if reason.startswith("not recorded") else f"not recorded ({reason})"
    text = f"{found[key] / 1000:,.1f} s"
    return f"{text} over {found[count]:,} {noun}" if count else text


def _hook_seconds(session: dict | None) -> str:
    return _seconds(session, "hook_ms", "hook_events", "hooks")


def report(run_root: Path, only: str | None = None) -> Path:
    """The collected arms side by side, as Markdown: both arms to `<run>/interactive-report.md`, or with `only` that arm
    alone to `<run>/collect/<arm>/report.md` (the report the session's own grading opens). Returns the path."""
    manifest = load(run_root)
    arms = {}
    for arm in (only,) if only else ARMS:
        path = run_root / "collect" / arm / "summary.json"
        if path.is_file():
            arms[arm] = json.loads(path.read_text(encoding="utf-8"))
    if not arms:
        raise BenchError("HB-USR-002", f"no collected arm under {run_root / 'collect'}; run `bench interactive collect` first")
    harness = next(iter(arms.values()))["harness"]
    title = f"Interactive run {manifest['run_id']}" + (f": the {only} arm, graded at the end of its session" if only else "")
    lines = [f"# {title}", "",
             f"- Harness: **{harness}**. One interactive session per arm, launched by the operator.",
             f"- Pack (on arm): `{manifest['pack_pin']['source']}` at `{manifest['pack_pin']['commit'][:12]}` (revision {manifest['pack_pin']['revision']}).",
             f"- Tasks, in queue order: {', '.join(manifest['tasks'])}. Prepared {manifest['created_at']}.",
             "- Arms collected: " + ", ".join(f"{a} (replay run `{s['replay_run']}`)" for a, s in arms.items()) + ".", "",
             "## Results per task", "",
             "| Task | " + " | ".join(f"{a}: hidden tests (pass_at_1) | {a}: property_check_pass | {a}: minutes" for a in arms) + " |",
             "|---|" + "---|---|---|" * len(arms)]
    for tid in manifest["tasks"]:
        row = [tid]
        for a, s in arms.items():
            sc = s["scores"].get(tid, {})
            mins = [v for k, v in s["minutes"].items() if k.split("|")[0] == tid]
            row += [_score(sc.get("pass_at_1")), _score(sc.get("property_check_pass")), _num(round(sum(mins), 1)) if mins else "not reached"]
        lines.append("| " + " | ".join(row) + " |")
    lines += ["", "## Drift per task (changed lines outside the task's blast radius)", "",
              "| Task | " + " | ".join(f"{a}: {m}" for a in arms for m in DRIFT_SCORES) + " |",
              "|---|" + "---|" * (len(arms) * len(DRIFT_SCORES))]
    for tid in manifest["tasks"]:
        lines.append(f"| {tid} | " + " | ".join(_score(s["scores"].get(tid, {}).get(m)) for s in arms.values() for m in DRIFT_SCORES) + " |")
    lines.append("")
    for a, s in arms.items():
        outside = s.get("outside_task_folders") or []
        lines.append(f"- **{a}**: {len(outside)} file(s) changed outside the task folders" + (f": {', '.join(outside[:10])}" if outside else "."))
    primary = [t for t in manifest["tasks"] if t != "SV1"]
    lines += ["", "## Totals", "", "| Measure | " + " | ".join(arms) + " |", "|---|" + "---|" * len(arms)]

    def count(arm_summary, metric, tasks):
        vals = [arm_summary["scores"].get(t, {}).get(metric) for t in tasks]
        return f"{sum(1 for v in vals if v == 1)} of {sum(1 for v in vals if isinstance(v, int))} graded"

    lines.append("| property_check_pass (primary, without SV1) | " + " | ".join(count(s, "property_check_pass", primary) for s in arms.values()) + " |")
    lines.append("| hidden tests pass (all tasks) | " + " | ".join(count(s, "pass_at_1", manifest["tasks"]) for s in arms.values()) + " |")
    lines.append("| wall minutes (sum of tasks) | " + " | ".join(_num(round(sum(s["minutes"].values()), 1)) for s in arms.values()) + " |")
    for f in (*TOKEN_FIELDS, "model_calls", "tool_calls", "tool_failures", "tool_failures_exit"):
        label = "tool_failures_exit (of those, a command that ran and exited non-zero)" if f == "tool_failures_exit" else f
        lines.append(f"| {label} | " + " | ".join(_num((s["session"] or {}).get("total", {}).get(f)) if s["session"] else "not recorded" for s in arms.values()) + " |")
    lines.append("| pack hook events | " + " | ".join(_num(s["session"]["pack_hook_events"]) if s["session"] else "not recorded"
                                                     for s in arms.values()) + " |")
    lines.append("| hook seconds (every hook the record times, pack and user-level) | " + " | ".join(
        _hook_seconds(s["session"]) for s in arms.values()) + " |")
    lines.append("| pack hook seconds (the pack's dispatcher, self-timed) | " + " | ".join(
        _seconds(s.get("pack_hook_time"), "ms", "dispatches", "dispatches") for s in arms.values()) + " |")
    lines.append("| model seconds (union of model-call spans) | " + " | ".join(
        _seconds(s["session"], "model_ms") for s in arms.values()) + " |")
    lines.append("| tool seconds (union of tool-call spans) | " + " | ".join(
        _seconds(s["session"], "tool_ms") for s in arms.values()) + " |")
    lines += ["", "## Served settings (from each session's own record)", ""]
    for a, s in arms.items():
        lines.append(f"- **{a}**: " + ("; ".join(json.dumps(x) for x in s["session"]["served"]) if s["session"] else "no record"))
        lines.append(f"- **{a}** CLI build: " + (", ".join((s["session"] or {}).get("cli_versions") or []) or "not recorded"))
    if "python" in manifest:
        lines.append(f"- Arm environments: a .venv per arm from `{manifest['python']['path']}` (Python {manifest['python']['version']}).")
    lines += ["", "## Tokens per task", "", "| Task | " + " | ".join(f"{a}: input+cache | {a}: output | {a}: tool calls" for a in arms) + " |",
              "|---|" + "---|---|---|" * len(arms)]
    order = {t: n for n, t in enumerate(manifest["tasks"])}
    labels = sorted({k for s in arms.values() if s["session"] for k in s["session"]["per_item"]},
                    key=lambda k: (order.get(k.split(" ")[0], len(order)), k))  # `unattributed` last
    for label in labels:
        row = [label]
        for s in arms.values():
            seg = (s["session"] or {}).get("per_item", {}).get(label)
            if not seg:
                row += ["not recorded"] * 3
                continue
            inp = None if seg["uncached_input"] is None else seg["uncached_input"] + seg["cache_read"] + seg["cache_write"]
            row += [_num(inp), _num(seg["output"]), _num(seg["tool_calls"])]
        lines.append("| " + " | ".join(row) + " |")
    lines += ["", "## Warnings", ""]
    if len(arms) > 1:
        lines += [f"- **both arms**: {w}" for w in cli_build_warnings(arms) + served_model_warnings(arms)]
    for a, s in arms.items():
        notes = s["warnings"] + s.get("session_warnings", []) + ((s["session"] or {}).get("notes") or [])
        lines += [f"- **{a}**: {n}" for n in notes] or [f"- **{a}**: none"]
    lines += ["", "## How to read this", "",
              "- One session per arm: a single paired observation per task, not a statistical result.",
              "- Context carries from task to task in the fixed queue order, the same order in both arms.",
              ("- Pass/fail and property checks are graded by the bench's own graders on a replay of each task folder; "
               "the catalog's process metrics need a per-cell record and are not graded in this mode."),
              ("- Tokens come from the session's own record. A record that only summarises usage gives session totals, "
               "and the per-task rows read `not recorded`."),
              "- Session records read at: " + ", ".join(f"{a} {s.get('session_read_at', s['collected_at'])}" for a, s in arms.items())
              + (". The session was still open, so its last turns are missing until `bench interactive gather` re-reads them "
                 "(Copilot writes its usage only at exit)." if only else ".")]
    dest = run_root / "collect" / only / "report.md" if only else run_root / "interactive-report.md"
    dest.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return dest


__all__ = ["ARMS", "PASTE", "build_overlays", "collect", "default_tasks", "find_records", "gather", "harnesses",
           "latest_pack", "load", "outside_task_folders", "prepare", "read_session", "refresh_session", "replay", "report", "seen_changes", "served_model_warnings",
           "session_metrics", "split"]
