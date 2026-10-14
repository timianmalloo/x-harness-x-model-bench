"""Behaviour measures for lean runs: drift, ceremony and over-thinking, per cell and per combo x arm.

Analysis only (read-only over each run's own fact streams; never writes into a run). Two layers:
- cells: every cell of every run whose latest grading pass completed (events/grade-*.jsonl has grading.completed).
  Measures come from the run's facts (model_calls, tool_calls, reasoning, scores) and its drift logs.
- sessions (optional): the operator's interactive CLI sessions, read with the bench's own native readers
  (profiles.READERS), given as --session <label>=<harness>:<transcript path>.

Usage: uv run python tools/behaviour_measures.py --run <runs/RUN_ID> [--run ...] [--session ...] --out <folder>
Writes <out>/behaviour-cells.json, <out>/behaviour-sessions.json and <out>/behaviour.md. Every number is read from a
record; medians are computed here and labelled "computed". A measure a record cannot give is "not recorded".
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

NOT_RECORDED = "not recorded"
COLUMNS = (  # (header, cell -> value)
    ("pass@1", lambda c: c["scores"].get("pass_at_1")),
    ("requests", lambda c: c["tokens"].get("requests")),
    ("output tok", lambda c: c["tokens"].get("output")),
    ("reasoning tok", lambda c: c["tokens"].get("reasoning")),
    ("reasoning chars", lambda c: c["reasoning_chars"]),
    ("tool calls", lambda c: c["tool_calls"]),
    ("calls before 1st edit", lambda c: c["calls_before_first_edit"]),
    ("shell", lambda c: c["tool_classes"].get("shell", 0)),
    ("read", lambda c: c["tool_classes"].get("read", 0)),
    ("edit", lambda c: c["tool_classes"].get("edit", 0)),
    ("delegate", lambda c: c["tool_classes"].get("delegate", 0)),
    ("lines inside", lambda c: c["drift"]["lines"].get("inside", 0)),
    ("lines discretionary", lambda c: c["drift"]["lines"].get("discretionary", 0)
     + c["drift"]["lines"].get("outside-unclassed", 0)),
    ("lines task-implied", lambda c: c["drift"]["lines"].get("task-implied", 0)),
    ("lines machine", lambda c: sum(v for k, v in c["drift"]["lines"].items() if k.startswith("machine"))),
    ("scope_creep", lambda c: c["scores"].get("scope_creep")),
    ("attention_drift", lambda c: c["scores"].get("attention_drift")),
    ("wall min", lambda c: round(c["wall_s"] / 60, 2) if c["wall_s"] is not None else None),
)


def _rows(path: Path) -> list[dict]:
    out = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            row = json.loads(line)
        except ValueError:
            continue
        if isinstance(row, dict):
            out.append(row)
    return out


def _latest(run: Path, stream: str) -> list[dict]:
    files = sorted((run / stream).glob("grade-*.jsonl"))
    return [r for r in _rows(files[-1]) if r.get("cell_id")] if files else []


def _ts(text: str | None) -> datetime | None:
    return datetime.fromisoformat(text) if text else None


def _num(value) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def graded(run: Path) -> bool:
    """The latest grading pass completed (a pass still running has only grading.started)."""
    files = sorted((run / "events").glob("grade-*.jsonl"))
    return bool(files) and any(r.get("kind") == "grading.completed" for r in _rows(files[-1]))


def drift_lines(path: Path) -> dict:
    """drift.log rows: change, path, inside|outside, +added -removed, (blank), class. Added lines per class. A
    discretionary path the bench's CURRENT machine list names (a pass graded before .venv joined it) is re-labelled
    machine:<kind> and counted in relabelled_lines, so older passes read like new ones."""
    from harness_bench.grade import _changes

    lines, files, relabelled = Counter(), Counter(), 0
    if path.is_file():
        for row in path.read_text(encoding="utf-8", errors="replace").splitlines():
            parts = row.split("\t")
            if len(parts) < 4:
                continue
            delta = parts[3].split()
            added = int(delta[0].lstrip("+")) if delta and delta[0].lstrip("+").isdigit() else 0
            cls = parts[5] if len(parts) > 5 and parts[5] else None
            key = "inside" if parts[2] == "inside" else (cls or "outside-unclassed")
            if key in ("discretionary", "outside-unclassed") and (kind := _changes.machine_written(parts[1])):
                key, relabelled = f"machine:{kind}", relabelled + added
            lines[key] += added
            files[key] += 1
    return {"lines": dict(lines), "files": dict(files), "relabelled_lines": relabelled, "recorded": path.is_file()}


def cells(run: Path) -> list[dict]:
    plan = json.loads((run / "plan.json").read_text(encoding="utf-8"))
    aux = {m for prof in plan.get("profiles", {}).values() for m in (prof.get("auxiliary_models") or [])}
    gdir = max((run / "grading").glob("grade-*"))
    by: dict[str, dict[str, list]] = defaultdict(lambda: defaultdict(list))
    for stream in ("model_calls", "tool_calls", "reasoning", "scores"):
        for r in _latest(run, stream):
            by[r["cell_id"]][stream].append(r)
    for f in sorted((run / "events").glob("engine-*.jsonl")):
        for r in _rows(f):
            if r.get("cell_id"):
                by[r["cell_id"]]["events"].append(r)
    out = []
    for c in plan["cells"]:
        b = by[c["cell_id"]]
        main = [m for m in b["model_calls"] if not any(str(m.get("model", "")).startswith(a) for a in aux)]
        tok = Counter()
        for m in main:
            for k in ("uncached_input", "cache_read", "cache_write", "output", "reasoning"):
                tok[k] += m.get(k) or 0
            tok["requests"] += m.get("requests") or 1
        tools = sorted(b["tool_calls"], key=lambda t: (t.get("native_session_id") or "", t.get("native_ordinal") or 0))
        first_edit = next((i for i, t in enumerate(tools) if t.get("tool_class") == "edit"), None)
        ev = {e["kind"]: e for e in b["events"]}
        start = _ts((ev.get("attempt.process_started") or {}).get("recorded_at"))
        end = _ts((ev.get("attempt.process_ended") or {}).get("recorded_at"))
        out.append({
            "run": run.name, "combo": c["combo"], "harness": c["harness"], "model": c["model"], "arm": c["arm"],
            "task": c["task"], "rep": c["rep"], "cell_id": c["cell_id"],
            "tokens": dict(tok) if main else {},
            "reasoning_tokens_recorded": any(m.get("reasoning") is not None for m in main),
            "reasoning_chars": sum(r.get("chars") or 0 for r in b["reasoning"]),
            "tool_calls": len(tools), "tool_classes": dict(Counter(t.get("tool_class") for t in tools)),
            "tool_names": dict(Counter(t.get("name") for t in tools)),
            "calls_before_first_edit": first_edit if first_edit is not None else (None if not tools else len(tools)),
            "wall_s": (end - start).total_seconds() if start and end else None,
            "drift": drift_lines(gdir / c["cell_id"] / "drift" / "drift.log"),
            "scores": {s["metric_id"]: s.get("value") for s in b["scores"] if "metric_id" in s},
        })
    return out


def sessions(specs: list[str]) -> list[dict]:
    """--session label=harness:path, read with the bench's own reader for that harness."""
    from harness_bench import profiles

    out = []
    for spec in specs:
        label, _, rest = spec.partition("=")
        harness, _, path = rest.partition(":")
        try:
            ex = profiles.READERS[harness](Path(path))
        except Exception as exc:  # noqa: BLE001 - one unreadable transcript is recorded, never fatal
            out.append({"label": label, "harness": harness, "path": path, "error": f"{type(exc).__name__}: {exc}"})
            continue
        calls = ex.model_calls
        out.append({
            "label": label, "harness": harness, "path": path,
            "model_calls": len(calls) or NOT_RECORDED,
            "output_tokens": sum(c.output for c in calls) if calls else NOT_RECORDED,
            "reasoning_tokens": (sum(c.reasoning or 0 for c in calls)
                                 if calls and any(c.reasoning is not None for c in calls) else NOT_RECORDED),
            "input_tokens": sum(c.uncached_input + c.cache_read + c.cache_write for c in calls) if calls else NOT_RECORDED,
            "tool_calls": len(ex.tool_calls),
            "tool_classes": dict(Counter(t.tool_class for t in ex.tool_calls)),
            "missing_fields": len(ex.missing),
        })
    return out


def summary(all_cells: list[dict]) -> list[str]:
    groups = defaultdict(list)
    for c in all_cells:
        groups[(c["combo"], c["arm"])].append(c)
    head = ["combo", "arm", "n", *(h for h, _ in COLUMNS)]
    lines = ["Medians per combo x arm (computed from the runs' facts; `-` = not recorded).", "",
             "| " + " | ".join(head) + " |", "|" + "---|" * len(head)]
    for (combo, arm), cs in sorted(groups.items()):
        row = [combo, arm, str(len(cs))]
        for _, get in COLUMNS:
            vals = [v for v in (_num(get(c)) for c in cs) if v is not None]
            row.append(f"{statistics.median(vals):g}" if vals else "-")
        lines.append("| " + " | ".join(row) + " |")
    return lines


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--run", action="append", default=[], help="a run folder (runs/<RUN_ID>); repeat")
    ap.add_argument("--session", action="append", default=[], help="label=harness:transcript path; repeat")
    ap.add_argument("--out", required=True)
    args = ap.parse_args(argv)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    all_cells, skipped = [], []
    for run in map(Path, args.run):
        if graded(run):
            all_cells += cells(run)
        else:
            skipped.append(run.name)
    sess = sessions(args.session)
    (out / "behaviour-cells.json").write_text(json.dumps(all_cells, indent=1), encoding="utf-8")
    (out / "behaviour-sessions.json").write_text(json.dumps(sess, indent=1), encoding="utf-8")
    md = ["# Behaviour measures", "", *summary(all_cells), ""]
    if skipped:
        md += [f"Not measured (grading pass not completed): {', '.join(skipped)}", ""]
    if sess:
        md += ["## Interactive sessions (bench readers)", "",
               "| label | harness | model calls | output tok | reasoning tok | tool calls | tool classes |",
               "|---|---|---|---|---|---|---|"]
        md += [f"| {s['label']} | {s['harness']} | {s.get('model_calls', s.get('error'))} | {s.get('output_tokens', '-')} | "
               f"{s.get('reasoning_tokens', '-')} | {s.get('tool_calls', '-')} | {s.get('tool_classes', '-')} |" for s in sess]
    (out / "behaviour.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print(f"{len(all_cells)} cells, {len(sess)} sessions -> {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
