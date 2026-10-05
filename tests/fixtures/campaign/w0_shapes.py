"""Fixtures for the three C2/C3 inputs of report section 3 (X-H2 brief, "Fixtures until C2/C3 land").

Provenance: each shape copies a W0 rev 6 line (`docs/design/eval-seam-contracts.md`):
- `prereg()`: `bench-prereg/1`, the `prereg/<hash>.json` row of the content-file table (line 350): question, arms,
  primary_metric, mde (property -> decimal string), alpha, power, correction {method, m}, pairing_unit, method,
  exclusions, min_pairs. Swap point: C2b's `register --confirm` writes the file and `bench report` reads it (C3 binder).
- `power_inputs()`: `bench-power-inputs/1`, the section 8 `power.py` comment block (line 436): alpha, power,
  correction, pairing_unit, harnesses, comparisons, properties {<p>: {primary_metric, tasks, mde, ...}}, slots,
  mean_wall_per_cell_s, mean_tokens_per_cell. Swap point: C2a's `power` command writes it; the binder reads it.
- `EXPECTED_NA`: the `readiness.expected_na(root, tasks)` result (absent on the base; C2b's). Swap point: the binder
  calls `readiness.expected_na` once C2b joins.
No `src/` line changes at any swap.
"""

from __future__ import annotations

from collections.abc import Mapping

PROPERTY = "security"
EXPECTED_NA: Mapping[str, frozenset[str]] = {"S1": frozenset({"mutation_score"})}


def prereg(*, mde: str = "0.30", method: str = "none", m: int = 1, min_pairs: int = 3, alpha: str = "0.05",
           question: str = "does the pack help") -> dict:
    return {"schema": "bench-prereg/1", "question": question,
            "arms": {"off": None, "on": {"revision": 7, "commit": "ab" * 20}},
            "primary_metric": {PROPERTY: "property_check_pass"}, "mde": {PROPERTY: mde}, "alpha": alpha, "power": "0.8",
            "correction": {"method": method, "m": m}, "pairing_unit": "task-harness-rep", "method": "bootstrap",
            "exclusions": "calibration cells", "min_pairs": min_pairs}


def power_inputs(*, method: str = "none", m: int = 1, tasks: tuple[str, ...] = ("S1", "S2"), mde: str = "0.30") -> dict:
    return {"schema": "bench-power-inputs/1", "population": {"description": "fixture", "exclusions": []},
            "source_run_ids": ["R0"], "alpha": "0.05", "power": "0.8", "correction": {"method": method, "m": m},
            "pairing_unit": "task-harness-rep", "harnesses": ["cc"], "comparisons": [["off", "on"]], "slots": 4,
            "properties": {PROPERTY: {"primary_metric": "property_check_pass", "tasks": list(tasks), "mde": mde,
                                      "control_rate": "0.5", "discordance": "assumed"}},
            "mean_wall_per_cell_s": 600, "mean_tokens_per_cell": 50000}


def analysable(inputs: Mapping) -> dict:
    """The inputs as `power.analyse` takes them. FINDING: the file is `ledger.canonical` bytes, which refuse a float, while
    `power.analyse` refuses a str `mde` or `control_rate` (`_open_unit`); so a reader must convert between the two. The
    section never calls `analyse`; the C2a/C3 binder owns this conversion (swap point of fixture 2)."""
    from decimal import Decimal
    body = {**inputs, "properties": {}}
    for name, prop in inputs["properties"].items():
        body["properties"][name] = {k: (Decimal(v) if k in ("mde", "control_rate") and v != "assumed" else v) for k, v in prop.items()}
    return body
