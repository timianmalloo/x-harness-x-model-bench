"""Expand a matrix and a BOM into the ordered list of measured cells.

One cell is exactly one (task, combo, pack, repetition). The order interleaves combos
innermost, so provider load and time-of-day drift affect every combo alike
(proposal: "runs interleaved across combos").
"""

from __future__ import annotations

from dataclasses import dataclass

# coord-run/1 admits at most 8 workers per contract (coord-runner.py RUN-CONTRACT).
MAX_WORKERS_PER_CONTRACT = 8


@dataclass(frozen=True)
class Cell:
    task: str
    scenario: int
    combo: str
    harness: str
    model: str
    pack: str
    rep: int

    @property
    def id(self) -> str:
        return f"{self.task}.{self.combo}.pack-{self.pack}.r{self.rep}"


def select_tasks(bom: dict, subset) -> list[dict]:
    tasks = bom["tasks"]
    if subset == "full":
        return list(tasks)
    if subset == "smoke":
        return [t for t in tasks if t.get("smoke")]
    wanted = set(subset)
    return [t for t in tasks if t["id"] in wanted]


def expand(matrix: dict, bom: dict) -> list[Cell]:
    tasks = select_tasks(bom, matrix["bom"]["subset"])
    cells = []
    for rep in range(1, matrix["repetitions"] + 1):
        for t in tasks:
            for pack in matrix["packs"]:
                for c in matrix["combos"]:
                    cells.append(Cell(t["id"], t["scenario"], c["id"], c["harness"], c["model"], pack, rep))
    return cells


def batches(cells: list[Cell], size: int = MAX_WORKERS_PER_CONTRACT) -> list[list[Cell]]:
    if not 1 <= size <= MAX_WORKERS_PER_CONTRACT:
        raise ValueError(f"batch size must be 1-{MAX_WORKERS_PER_CONTRACT}")
    return [cells[i : i + size] for i in range(0, len(cells), size)]
