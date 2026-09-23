"""`bench` — the pipeline CLI: validate, plan, run, grade, report, teardown.

/start-benchmark is the only way a real run starts; it calls these commands in order.
Commands that are not built yet exit 2 and name the spec that defines them
(docs/specs/README.md).
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

from rich.console import Console
from rich.table import Table

from harness_bench import config, plan

NOT_BUILT = 2

# command -> spec id in docs/specs/README.md
PENDING = {
    "run": "S-05 runner, S-06 adapters",
    "grade": "S-08 graders",
    "report": "S-10 report",
    "teardown": "S-05 runner (archive then delete)",
}


def cmd_validate(args, console: Console) -> int:
    root = config.repo_root()
    problems = config.validate_repo(root)
    for item in problems:
        console.print(f"[red]x[/red] {item}")
    if problems:
        console.print(f"{len(problems)} problem(s)")
        return 1
    console.print("[green]ok[/green] bom, metrics, example matrix and every task folder are valid")
    return 0


def cmd_plan(args, console: Console) -> int:
    root = config.repo_root()
    bom = config.load_yaml(root / "bench" / "bom.yaml")
    matrix_path = Path(args.matrix) if args.matrix else root / "bench" / "matrix.example.yaml"
    matrix = config.load_yaml(matrix_path)
    problems = config.Problems()
    config.validate_matrix(matrix, bom, problems, str(matrix_path))
    if problems:
        for item in problems.items:
            console.print(f"[red]x[/red] {item}")
        return 1
    cells = plan.expand(matrix, bom)
    if args.json:
        print(json.dumps([c.__dict__ | {"id": c.id} for c in cells], indent=2))
        return 0
    table = Table(title=f"plan: {matrix_path.name}")
    table.add_column("combo")
    table.add_column("harness")
    table.add_column("model")
    table.add_column("cells", justify="right")
    per_combo = Counter(c.combo for c in cells)
    for c in matrix["combos"]:
        table.add_row(c["id"], c["harness"], c["model"], str(per_combo[c["id"]]))
    console.print(table)
    tasks = sorted({c.task for c in cells})
    console.print(
        f"{len(tasks)} tasks x {len(matrix['combos'])} combos x {len(matrix['packs'])} pack settings "
        f"x {matrix['repetitions']} reps = [b]{len(cells)} cells[/b]"
    )
    return 0


def cmd_pending(args, console: Console) -> int:
    console.print(f"[yellow]bench {args.command}[/yellow] is not built yet. Spec: {PENDING[args.command]} (docs/specs/README.md)")
    return NOT_BUILT


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="bench", description=__doc__.splitlines()[0])
    sub = p.add_subparsers(dest="command", required=True)
    sub.add_parser("validate", help="check bench/*.yaml and every tasks/<ID>/ against the contract")
    pl = sub.add_parser("plan", help="expand a matrix x BOM into ordered cells")
    pl.add_argument("--matrix", help="matrix.yaml (default: bench/matrix.example.yaml)")
    pl.add_argument("--json", action="store_true", help="print the cell list as JSON")
    for name in PENDING:
        sub.add_parser(name, help=f"not built yet ({PENDING[name]})")
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    console = Console()
    handler = {"validate": cmd_validate, "plan": cmd_plan}.get(args.command, cmd_pending)
    return handler(args, console)


if __name__ == "__main__":
    sys.exit(main())
