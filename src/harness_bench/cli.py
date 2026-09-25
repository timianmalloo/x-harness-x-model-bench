"""`bench`: validate, plan, run, status, stop, answer, grade, report, verify, teardown, tools install (design: Exposed contracts).

This is the composition root: it builds the real launchers, the working-copy builder and the grading hook,
and hands them to the engine. Errors go to stderr as `<code>: <message>`. Exit codes (design):
0 ok · 1 invalid input · 2 usage (argparse only) · 3 run incomplete · 4 not built · 5 integrity failure.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import uuid
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

from rich.console import Console
from rich.table import Table

from harness_bench import (
    archive,
    config,
    engine,
    oslock,
    plan,
    preflight,
    profiles,
    status,
    tools,
    views,
    workspace,
)
from harness_bench.errors import BenchError
from harness_bench.grade import runner
from harness_bench.report import cli_table, html
from harness_bench.report import credentials as report_credentials

OK, INVALID, INCOMPLETE, NOT_BUILT, INTEGRITY = 0, 1, 3, 4, 5


def _exit_for(code: str) -> int:
    return INTEGRITY if code.startswith(("HB-LED", "HB-SEC")) else INVALID


def _plain() -> bool:
    return bool(os.environ.get("NO_COLOR")) or not sys.stdout.isatty()


_PATH_ARGS = ("root", "runs", "cells_root", "tools_dir", "pack_source", "matrix")


def _resolve_paths(args: argparse.Namespace) -> None:
    """Every path argument is resolved to an absolute path once, here, at parse time (HB-CELL-113,
    real E2E): a relative --tools-dir left the pack root (tools_dir.parent) relative, and
    install_pack's subprocess runs with cwd = the cell working copy, not the process cwd -- so a
    relative pack-apply.py path resolved under the workspace and was never found."""
    for name in _PATH_ARGS:
        value = getattr(args, name, None)
        if value is not None:
            setattr(args, name, str(Path(value).resolve()))


def _run_dir(args) -> Path:
    run_dir = Path(args.runs) / args.run_id
    status.require_known(run_dir)
    return run_dir


def cmd_validate(args) -> int:
    problems = config.validate_repo(Path(args.root))
    for item in problems:
        print(f"x {item}")
    print(f"{len(problems)} problem(s)" if problems else "ok: bom, metrics, example matrix and every task folder are valid")
    return INVALID if problems else OK


def _pack(source: Path, pack_root: Path) -> dict:
    from harness_bench import gitsafe

    commit = gitsafe.git(["rev-parse", "HEAD"], cwd=source, timeout=60).stdout.strip()
    checkout = workspace.pack_checkout(source, commit, pack_root)
    return {"source": str(source), "commit": commit, "revision": workspace.pack_revision(checkout)}


def cmd_plan(args) -> int:
    root = Path(args.root)
    bom = config.load_yaml(root / "bench" / "bom.yaml")
    matrix_path = Path(args.matrix) if args.matrix else root / "bench" / "matrix.example.yaml"
    matrix = config.load_yaml(matrix_path)
    problems = config.Problems()
    config.validate_matrix(matrix, bom, problems, str(matrix_path))
    if problems:
        for item in problems.items:
            print(f"x {item}", file=sys.stderr)
        return INVALID
    if args.json:
        tasks = plan.select_tasks(bom, matrix["bom"]["subset"])
        versions = {t["id"]: plan.task_version_hash(root / "tasks" / t["id"]) for t in tasks}
        print(json.dumps([c.__dict__ | {"id": c.id} for c in plan.expand(matrix, bom, versions)], indent=2))
        return OK
    builds = {h: b.record() for h, b in tools.resolve(Path(args.tools_dir)).items()}
    pack = _pack(Path(args.pack_source), Path(args.tools_dir).parent / "pack")
    run_id = args.run_id or f"{matrix.get('run_id', 'run')}-{datetime.now(UTC):%Y%m%dT%H%M%S}"
    parameters = {"decision_timeout": args.decision_timeout_minutes * 60, "spend_cap_tokens": args.spend_cap_tokens}
    p = plan.build_plan(root, matrix, bom, run_id, builds, pack, parallelism=args.parallelism, parameters=parameters,
                        tools_dir=Path(args.tools_dir), cells_root=Path(args.cells_root))
    console = Console(no_color=_plain(), highlight=False)
    table = Table(title=f"plan {run_id}: {matrix_path.name}")
    for col in ("combo", "harness", "model", "planned build", "cells"):
        table.add_column(col, justify="right" if col == "cells" else "left")
    per_combo = Counter(c["combo"] for c in p["cells"])
    for c in matrix["combos"]:
        b = p["builds"].get(c["harness"], {})
        table.add_row(c["id"], c["harness"], c["model"], f"{b.get('version')} ({(b.get('sha256') or '')[:12]})", str(per_combo[c["id"]]))
    console.print(table)
    print(f"pack revision {pack['revision']} ({pack['commit'][:12]}); {len(p['cells'])} cells; parallelism {p['parameters']['parallelism']}; "
          f"envelope {p['envelope_seconds']} s; price list {p['price_list_hash'][:12] or 'absent'}")
    print("parameters: " + ", ".join(f"{k}={v}" for k, v in sorted(p["parameters"].items())))
    print(f"decision timeout: {p['parameters']['decision_timeout'] // 60} min; "
          f"spend cap: {p['parameters']['spend_cap_tokens'] if p['parameters']['spend_cap_tokens'] is not None else 'none'}"
          + (" tokens, checked when each cell ends; cells whose usage is not recorded are not counted"
             if p['parameters']['spend_cap_tokens'] is not None else ""))
    if args.confirm:
        path = plan.confirm(Path(args.runs) / run_id, p)
        print(f"confirmed: {path}")
    else:
        print(f"not confirmed; run again with --confirm to freeze plan {run_id}")
    return OK


def _workspace_builder(root: Path, p: dict, sources_root: Path, pack_root: Path):
    def build(cell: dict, cell_dir: Path) -> dict:
        task_dir = root / "tasks" / cell["task"]
        source = workspace.task_source(task_dir, cell["task_version"], sources_root)
        ws = workspace.cell_working_copy(source, cell_dir / "ws")
        manifest: list[str] = []
        if cell["pack"] == "on":
            pack_dir = workspace.pack_checkout(Path(p["pack"]["source"]), p["pack"]["commit"], pack_root)
            manifest = workspace.install_pack(pack_dir, ws, project=cell["task"], timeout=p["parameters"]["git_timeout"] * 5)
        return {"pack": cell["pack"], "pack_manifest": len(manifest)}

    return build


def cmd_run(args) -> int:
    root, run_dir = Path(args.root), _run_dir(args)
    p = plan.load_confirmed(run_dir)
    plan.require_run_parameters(p)
    if (run_dir / "events").exists():
        raise BenchError("HB-USR-002", f"run {args.run_id} has already started; phase 1 re-runs under a new run id")
    for task_id, t in p["tasks"].items():
        if plan.task_version_hash(root / "tasks" / task_id) != t["version_hash"]:
            raise BenchError("HB-USR-002", f"task {task_id} changed since the plan; plan a new run")
    plan.require_scripted_user_inputs(root, p)
    cells_root, tools_dir = Path(args.cells_root), Path(args.tools_dir)
    preflight.check(p, cells_root, tools_dir)
    launchers = {h: profiles.ProfileLauncher(profiles.load(root, h), tools_dir, planned) for h, planned in p["builds"].items()}
    log_handler = engine.configure_logging(run_dir, p["trace_id"])
    try:
        cfg = engine.EngineConfig(run_dir=run_dir, cells_root=cells_root, launchers=launchers,
                                  build_workspace=_workspace_builder(root, p, cells_root / ".sources", tools_dir.parent / "pack"),
                                  grade=lambda d: runner.run_pass(d, root).summary())
        summary = engine.Engine(p, cfg).run()
    finally:
        engine.log.removeHandler(log_handler)
        log_handler.close()
    print(status.text(status.build(run_dir)), end="")
    return OK if summary.exit_code == 0 else INCOMPLETE


def cmd_status(args) -> int:
    s = status.build(_run_dir(args))
    print(status.to_json(s) if args.json else status.text(s), end="\n" if args.json else "")
    return OK


def _require_running(run_dir: Path, run_id: str, action: str) -> None:
    """A control is written only while an engine holds the run's lock: nothing else would ever read it."""
    if not oslock.is_held(run_dir / ".lock"):
        completion = status.build(run_dir).completion
        raise BenchError("HB-USR-002", f"run {run_id} is not running ({completion}); nothing to {action}")


def _write_control(run_dir: Path, control: str, decision_id: str | None = None, option: str | None = None) -> str:
    """A `bench-control/1` file, written as a temp file then os.replace, so the engine never reads a partial one
    (design 4.1). Returns its uuid, which is also its file stem."""
    uid = uuid.uuid4().hex
    control_dir = run_dir / "control"
    control_dir.mkdir(exist_ok=True)
    target = control_dir / f"{uid}.json"
    temp = control_dir / f"{uid}.json.tmp"
    payload = {"schema": "bench-control/1", "uuid": uid, "control": control, "decision_id": decision_id,
               "option": option, "requested_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")}
    temp.write_text(json.dumps(payload, separators=(",", ":")), encoding="utf-8")
    os.replace(temp, target)
    return uid


def cmd_stop(args) -> int:
    run_dir = _run_dir(args)
    _require_running(run_dir, args.run_id, "stop")
    uid = _write_control(run_dir, "stop")
    print(f"stop requested ({uid}). bench status {args.run_id} shows stopped within 30 s.")
    return OK


def cmd_answer(args) -> int:
    """Design 4.2: checked at write time against the ledger; the engine re-checks when it applies the file."""
    run_dir = _run_dir(args)
    _require_running(run_dir, args.run_id, "answer")
    decision = next((d for d in status.build(run_dir).decisions if d.decision_id == args.decision_id), None)
    if decision is None:
        raise BenchError("HB-USR-002", f"run {args.run_id} has no decision {args.decision_id}")
    if decision.state != "open":
        raise BenchError("HB-USR-002", f"decision {decision.decision_id} is not open ({decision.state}); nothing to answer")
    if args.option not in decision.options:
        raise BenchError("HB-USR-002", f"decision {decision.decision_id} offers {' | '.join(decision.options)}, not {args.option}")
    uid = _write_control(run_dir, "answer", decision.decision_id, args.option)
    print(f"answer requested ({uid}): {decision.decision_id} {args.option}. bench status {args.run_id} shows the decision's state.")
    return OK


def cmd_grade(args) -> int:
    result = runner.run_pass(_run_dir(args), Path(args.root))
    print(f"graded {result.cells_graded} cell(s) in pass {result.grading_id}")
    for name in result.abandoned:
        print(f"HB-LED-004: named abandoned segment {name}", file=sys.stderr)
    return OK


def _credential_values(root: Path, run_dir: Path) -> set[str]:
    """Every credential value html.write's exact-value scan checks for: the host's own credential
    files (named by bench/profiles/*.yaml) and any leftover copy in an archived cell home."""
    files = report_credentials.credential_files(root)
    values = report_credentials.host_values(root)
    values |= report_credentials.archived_home_values(run_dir, {name for _, name in files.values()})
    return values


def cmd_report(args) -> int:
    run_dir = _run_dir(args)
    root = Path(args.root)
    view = views.load(run_dir)
    text, code = cli_table.render(view, plain=_plain())
    if code == OK:
        # html.write's credential scan must run before a label reaches the terminal (residual 5).
        report_path = html.write(run_dir, view, _credential_values(root, run_dir))
        print(text, end="")
        print(f"report: {report_path}")
    else:
        print(text, end="")
    return code


def cmd_verify(args) -> int:
    findings = views.verify(_run_dir(args))
    for f in findings:
        print(f"{f.code}: {f.message}" + (" (warning)" if f.level == "warning" else ""), file=sys.stderr)
    if any(f.level == "error" for f in findings):
        return INTEGRITY
    print("verify: ok")
    return OK


def cmd_teardown(args) -> int:
    run_dir = _run_dir(args)
    if oslock.is_held(run_dir / ".lock"):
        raise BenchError("HB-RUN-003", f"run {args.run_id} is held by a live engine; teardown refused")
    archived = {e["cell_id"] for e in views.rows(run_dir, "events") if e["kind"] == "cell.archived"}
    removed, kept = archive.teardown(Path(args.cells_root) / args.run_id, archived)
    for cid in removed:
        print(f"removed {cid}")
    for cid in kept:
        print(f"kept {cid}: not archived")
    return OK


def cmd_tools(args) -> int:
    root = Path(args.root)
    tools.install(root / "bench" / "tools", Path(args.tools_dir))
    for harness, b in sorted(tools.resolve(Path(args.tools_dir)).items()):
        print(f"{harness} {b.version} ({b.sha256[:12]}); adapter {b.adapter_version}")
    return OK


def _positive_int(value: str) -> int:
    try:
        number = int(value)
    except ValueError:
        raise argparse.ArgumentTypeError("must be a positive integer") from None
    if number <= 0:
        raise argparse.ArgumentTypeError("must be a positive integer")
    return number


def build_parser() -> argparse.ArgumentParser:
    root = config.repo_root()
    p = argparse.ArgumentParser(prog="bench", description=__doc__.splitlines()[0])
    p.add_argument("--root", default=str(root), help="bench root: tasks/ and bench/ (default: this repository)")
    p.add_argument("--runs", default=None, help="runs folder (default: <root>/runs)")
    p.add_argument("--cells-root", default=str(root.parent / "bench-cells"),
                   help="where cells' working copies live; no agent instruction file may sit above it (HB-PRE-002)")
    p.add_argument("--tools-dir", default=str(root / ".tools" / "harness"), help="pinned harness builds (bench tools install)")
    sub = p.add_subparsers(dest="command", required=True)
    sub.add_parser("validate", help="check bench/*.yaml and every tasks/<ID>/ against the contract")
    pl = sub.add_parser("plan", help="expand a matrix into a plan; --confirm freezes it")
    pl.add_argument("--matrix", help="matrix.yaml (default: bench/matrix.example.yaml)")
    pl.add_argument("--run-id", help="default: <matrix run_id>-<UTC time>")
    pl.add_argument("--parallelism", type=int, default=plan.DEFAULT_PARAMETERS["parallelism"])
    pl.add_argument("--decision-timeout-minutes", type=_positive_int, default=plan.DEFAULT_PARAMETERS["decision_timeout"] // 60)
    pl.add_argument("--spend-cap-tokens", type=_positive_int, default=None)
    pl.add_argument("--pack-source", default=str(root.parent / "ai-forward"), help="the ai-forward clone; its HEAD is pinned")
    pl.add_argument("--confirm", action="store_true", help="write runs/<run_id>/plan.json (frozen)")
    pl.add_argument("--json", action="store_true", help="print the cell list as JSON")
    for name, text in (("run", "run a confirmed plan to completion, then grade it"), ("status", "a run's progress (US-20)"),
                       ("stop", "request that a running run stop within 30 seconds"),
                       ("answer", "answer an open decision request (US-15)"),
                       ("grade", "a new grading pass"), ("report", "CLI table and report.html"),
                       ("verify", "check every ledger segment and archive"), ("teardown", "remove the run's archived cell folders")):
        sp = sub.add_parser(name, help=text)
        sp.add_argument("run_id")
        if name == "status":
            sp.add_argument("--json", action="store_true", help="bench-status/1 on stdout")
        if name == "answer":
            sp.add_argument("decision_id", help="the decision's id in bench status, e.g. D1")
            sp.add_argument("option", help="one of the options bench status lists for it")
    tl = sub.add_parser("tools", help="the pinned harness builds")
    tl.add_argument("action", choices=["install"])
    return p


COMMANDS = {"validate": cmd_validate, "plan": cmd_plan, "run": cmd_run, "status": cmd_status, "stop": cmd_stop, "answer": cmd_answer, "grade": cmd_grade,
            "report": cmd_report, "verify": cmd_verify, "teardown": cmd_teardown, "tools": cmd_tools}


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    args.runs = args.runs or str(Path(args.root) / "runs")
    _resolve_paths(args)
    try:
        return COMMANDS[args.command](args)
    except BenchError as exc:
        print(str(exc), file=sys.stderr)
        return _exit_for(exc.code)


if __name__ == "__main__":
    sys.exit(main())
