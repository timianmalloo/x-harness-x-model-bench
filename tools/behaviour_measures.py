"""Behaviour measures for lean runs: drift, ceremony, tool use and over-thinking, per cell and per combo x arm.

Analysis only (read-only over each run's own fact streams; never writes into a run). Two layers:
- cells: every cell of every run whose latest grading pass completed (events/grade-*.jsonl has grading.completed).
  Measures come from the run's facts (model_calls, tool_calls, reasoning, scores), its drift logs and, for the harnesses
  with a tool-input reader, the cell's own trace (report/tool_phases.py `cell_trace`: re-reads, tool-result bytes, the
  first edit, assistant text when the reader counts it).
- sessions (optional): the operator's interactive CLI sessions, read with the bench's own native readers
  (profiles.READERS), given as --session <label>=<harness>:<transcript path> (a Copilot folder reads its events.jsonl).
  Each also gets a compliance read against Prompt 1 (docs/benchmarkpromps/lean-benchmark-run-prompt.html).

Usage: uv run python tools/behaviour_measures.py --run <runs/RUN_ID> [--run ...] [--session ...] --out <folder>
Writes <out>/behaviour-cells.json, <out>/behaviour-sessions.json and <out>/behaviour.md. Every number is read from a
record; medians, spreads and ratios are computed here and labelled "computed". A measure a record cannot give is
"not recorded", with the reason (cell["why"][measure]; the page lists them).
"""

from __future__ import annotations

import argparse
import json
import re
import statistics
import sys
from collections import Counter, defaultdict
from collections.abc import Sequence
from dataclasses import replace
from datetime import datetime
from itertools import pairwise
from pathlib import Path

NOT_RECORDED = "not recorded"
TOP_FILES = 5  # files named per combo x arm behind the discretionary lines
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


def _m(name: str):
    return lambda c: c["m"].get(name)


# plan rows C1, C2, C3, C5, C6: (header, key in cell["m"]); each absent value has a reason in cell["why"][key]
TOOL_MEASURES = (
    ("tool_error_rate", "tool_error_rate"), ("stuck_loops", "stuck_loops"), ("re-reads", "rereads"),
    ("tool-result bytes", "tool_result_bytes"), ("assistant text chars", "assistant_chars"),
    ("assistant messages", "assistant_messages"), ("planning calls", "planning_calls"),
    ("reasoning tok / tool call", "reasoning_per_tool_call"),
)
# plan row B5: attention.log targets around the cell's first edit
ATTENTION_MEASURES = (
    ("outside reads before 1st edit", "outside_before"), ("outside reads after 1st edit", "outside_after"),
    ("inside reads before 1st edit", "inside_before"), ("inside reads after 1st edit", "inside_after"),
)
TOOL_COLUMNS = tuple((h, _m(k)) for h, k in TOOL_MEASURES)
ATTENTION_COLUMNS = tuple((h, _m(k)) for h, k in ATTENTION_MEASURES)
NO_TEXT = "the reader does not count assistant text yet (ProcessTrace.assistant_chars is None)"


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


def spread(values: Sequence[float]) -> dict | None:
    """n, median, inclusive quartiles (p25, p75) and min-max of the recorded values; None for none (A8)."""
    vals = sorted(values)
    if not vals:
        return None
    q = statistics.quantiles(vals, n=4, method="inclusive") if len(vals) > 1 else [vals[0]] * 3
    return {"n": len(vals), "median": statistics.median(vals), "p25": q[0], "p75": q[2], "min": vals[0], "max": vals[-1]}


def _fmt(x: float) -> str:
    if x == int(x):
        return str(int(x))
    return f"{x:.1f}" if abs(x) >= 100 else f"{x:.3g}"


def graded(run: Path) -> bool:
    """The latest grading pass completed (a pass still running has only grading.started)."""
    files = sorted((run / "events").glob("grade-*.jsonl"))
    return bool(files) and any(r.get("kind") == "grading.completed" for r in _rows(files[-1]))


def drift_lines(path: Path) -> dict:
    """drift.log rows: change, path, inside|outside, +added -removed, (blank), class. Added lines per class. A
    discretionary path the bench's CURRENT machine list names (a pass graded before .venv joined it) is re-labelled
    machine:<kind> and counted in relabelled_lines, so older passes read like new ones. discretionary_files holds the
    added lines of each file behind the discretionary class (B4), after the same re-labelling."""
    from harness_bench.grade import _changes

    lines, files, relabelled, behind = Counter(), Counter(), 0, Counter()
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
            if key in ("discretionary", "outside-unclassed") and added:
                behind[parts[1]] += added
    return {"lines": dict(lines), "files": dict(files), "relabelled_lines": relabelled, "recorded": path.is_file(),
            "discretionary_files": dict(behind)}


def top_drift_files(all_cells: list[dict], top: int = TOP_FILES) -> dict[tuple[str, str], list[tuple[str, int, int]]]:
    """B4: per combo x arm, the files with the most discretionary added lines: (path, total lines, cells that wrote it)."""
    lines: dict[tuple[str, str], Counter] = defaultdict(Counter)
    cells_with: dict[tuple[str, str], Counter] = defaultdict(Counter)
    for c in all_cells:
        for path, n in (c["drift"].get("discretionary_files") or {}).items():
            lines[(c["combo"], c["arm"])][path] += n
            cells_with[(c["combo"], c["arm"])][path] += 1
    return {k: [(p, n, cells_with[k][p]) for p, n in sorted(v.items(), key=lambda kv: (-kv[1], kv[0]))[:top]]
            for k, v in lines.items() if v}


def process_measures(scores: dict, reasons: dict, tool_rows: list[dict]) -> dict[str, tuple[float | None, str | None]]:
    """C1: tool_error_rate and stuck_loops. The cell's graded score when the pass has one; else the grader's own rule
    (grade/process.py, the one definition) over the cell's tool_calls rows. process.py is not in runner.GRADERS, so
    today's runs carry no score and this fallback is the usual path. A value or (None, reason), never 0 for unknown."""
    from harness_bench.grade import process

    calls = process._counted(tuple(tool_rows))
    rules = {"tool_error_rate": process._tool_error_rate, "stuck_loops": process._stuck_loops}
    out = {}
    for name, rule in rules.items():
        if scores.get(name) is not None:
            out[name] = (_num(scores[name]), None)
        elif name in scores:
            out[name] = (None, reasons.get(name) or "graded NA")
        else:
            got = rule(calls)
            out[name] = (None if got.value is None else float(got.value), got.reason)
    return out


def trace_measures(trace) -> dict:
    """C2, C3, C5 and the first edit from one cell trace (report/tool_phases.py: rereads, bytes_returned, phases are the
    one definitions). Assistant text is None until a reader counts it (ProcessTrace.assistant_*), with the reason."""
    from harness_bench.report import tool_phases as tp

    calls = trace.calls
    got = tp.bytes_returned(calls)
    phase = tp.phases(calls)
    edit = phase.index("edit") if "edit" in phase else None
    out = {"rereads": tp.rereads(calls), "tool_result_bytes": got.value,
           "first_edit_ordinal": calls[edit].native_ordinal if edit is not None else None,
           "assistant_chars": trace.assistant_chars, "assistant_messages": trace.assistant_messages, "why": {}}
    for name, value, reason in (("tool_result_bytes", got.value, got.reason), ("assistant_chars", trace.assistant_chars, NO_TEXT),
                                ("assistant_messages", trace.assistant_messages, NO_TEXT)):
        if value is None:
            out["why"][name] = reason
    return out


def attention_split(text: str, first_edit_ordinal: int | None) -> dict | None:
    """B5: from attention.log (one row per read or search target: record, native ordinal, tool, target, inside|outside|
    no-path), the counts of inside and outside targets before and after the cell's first edit. A read in the same
    record turn as the edit (ordinal <= the edit's) cannot have seen it, so it counts as before; with no edit every read
    is before. None when the log names more than one record (a sub-agent's ordinals are a different sequence)."""
    rows = [line.split("\t") for line in text.splitlines() if line.strip()]
    rows = [r for r in rows if len(r) >= 5 and r[4] in ("inside", "outside") and r[1].isdigit()]
    if len({r[0] for r in rows}) > 1:
        return None
    out = dict.fromkeys(("outside_before", "outside_after", "inside_before", "inside_after"), 0)
    for r in rows:
        after = first_edit_ordinal is not None and int(r[1]) > first_edit_ordinal
        out[f"{r[4]}_{'after' if after else 'before'}"] += 1
    return out


def _trace_for(run: Path, view, vcell):
    """(ProcessTrace | None, reason | None) for one cell: tool_phases.cell_trace, with the reason it is absent."""
    from harness_bench.report import tool_phases as tp

    if view is None or vcell is None:
        return None, "run view unreadable"
    if vcell.harness not in tp.TRACE_READERS:
        return None, f"no tool-input reader for {vcell.harness}"
    session = tp.main_session(view, vcell)
    if not session:
        return None, "no session id recorded for the cell"
    trace = tp.cell_trace(run, view, vcell, session)
    return (trace, None) if trace is not None else (None, "no readable native record in the archive")


def cells(run: Path) -> list[dict]:
    from harness_bench import views

    plan = json.loads((run / "plan.json").read_text(encoding="utf-8"))
    aux = {m for prof in plan.get("profiles", {}).values() for m in (prof.get("auxiliary_models") or [])}
    gdir = max((run / "grading").glob("grade-*"))
    try:
        view = views.load(run)
        vcells = {c.cell_id: c for c in view.cells}
    except Exception:  # noqa: BLE001 - an unreadable view leaves the trace-based measures "not recorded", never fatal
        view, vcells = None, {}
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
        scores = {s["metric_id"]: s.get("value") for s in b["scores"] if "metric_id" in s}
        score_why = {s["metric_id"]: s.get("reason") for s in b["scores"] if "metric_id" in s and s.get("reason")}
        m: dict = {}
        why: dict = {}
        for name, (value, reason) in process_measures(scores, score_why, tools).items():
            m[name], why[name] = value, reason
        m["planning_calls"] = sum(1 for t in tools if t.get("tool_class") == "meta") if tools else None  # views.meta_calls
        why["planning_calls"] = None if tools else "no tool calls recorded"
        if not main or not tok["requests"]:
            m["reasoning_per_tool_call"], why["reasoning_per_tool_call"] = None, "no model calls recorded"
        elif not any(x.get("reasoning") is not None for x in main):
            m["reasoning_per_tool_call"], why["reasoning_per_tool_call"] = None, "reasoning tokens not recorded"
        elif not tools:
            m["reasoning_per_tool_call"], why["reasoning_per_tool_call"] = None, "no tool calls recorded"
        else:
            m["reasoning_per_tool_call"] = tok["reasoning"] / len(tools)
        trace, no_trace = _trace_for(run, view, vcells.get(c["cell_id"]))
        got = trace_measures(trace) if trace is not None else None
        for name in ("rereads", "tool_result_bytes", "assistant_chars", "assistant_messages"):
            m[name] = got[name] if got else None
            why[name] = no_trace if got is None else got["why"].get(name)
        attn_log = gdir / c["cell_id"] / "drift" / "attention.log"
        split, no_attn = None, None
        if not attn_log.is_file():
            no_attn = "no attention.log for the cell (the grader did not write one)"
        elif got is None:
            no_attn = f"first edit unknown: {no_trace}"
        elif not (text := attn_log.read_text(encoding="utf-8", errors="replace")).strip():
            no_attn = str(score_why.get("attention_drift") or "attention.log is empty (no read or search targets)")
        elif (split := attention_split(text, got["first_edit_ordinal"])) is None:
            no_attn = "attention.log spans more than one record (a sub-agent); the ordinals are not one sequence"
        for name in ("outside_before", "outside_after", "inside_before", "inside_after"):
            m[name], why[name] = (split[name], None) if split else (None, no_attn)
        out.append({
            "run": run.name, "combo": c["combo"], "harness": c["harness"], "model": c["model"], "arm": c["arm"],
            "task": c["task"], "rep": c["rep"], "cell_id": c["cell_id"],
            "tokens": dict(tok) if main else {},
            "reasoning_tokens_recorded": any(x.get("reasoning") is not None for x in main),
            "reasoning_chars": sum(r.get("chars") or 0 for r in b["reasoning"]),
            "tool_calls": len(tools), "tool_classes": dict(Counter(t.get("tool_class") for t in tools)),
            "tool_names": dict(Counter(t.get("name") for t in tools)),
            "calls_before_first_edit": first_edit if first_edit is not None else (None if not tools else len(tools)),
            "wall_s": (end - start).total_seconds() if start and end else None,
            "drift": drift_lines(gdir / c["cell_id"] / "drift" / "drift.log"),
            "scores": scores,
            "m": m, "why": {k: v for k, v in why.items() if v and m.get(k) is None},
        })
    return out


# --- sessions: the bench readers' totals plus a compliance read against Prompt 1 ---------------------------------------

BENCH = (r"(?<![\w.-])(?:[^\s\"']*[\\/])?bench(?:\.ps1)?[\"']?\s+(?:--[\w-]+\s+\S+\s+)*")  # the bench CLI, wrapper or `uv run bench`
_WROTE = re.compile(r"Set-Content|Out-File|Add-Content|WriteAllText|write_text|writeFile|json\.dump\(|\btee\b|>>?\s")
_LOOPS = re.compile(r"setTimeout|Start-Sleep|\bsleep\b|while\s*\(\s*true|for\s*\(\s*;\s*;")  # a poll loop inside one call
STEPS = (  # (step, how a session proves it): a bench subcommand, a command pattern, or a file it wrote
    ("worktree_created", "cmd", r"coord-core\.py[\"']?\s+worktree\s+new"),
    ("tools_installed", "cmd", BENCH + r"tools\s+install\b"),
    ("matrix_written", "write", r"\.matrix\.yaml"),
    ("plan_confirmed", "cmd", BENCH + r"plan\b.*--confirm"),
    ("run_started", "cmd", BENCH + r"run\s+[\w$\"'`{]"),  # a literal run id or a variable holding it
    ("status_checked", "cmd", BENCH + r"status\b"),
    ("verified", "cmd", BENCH + r"verify\b"),
    ("report_run", "cmd", BENCH + r"report\b"),
    ("run_summary_written", "write", r"run-summary\.md"),
    ("summary_rendered", "cmd", r"render-markdown\.py.*run-summary"),
    ("handoff_json_written", "write", r"handoff\.json"),
)
_STATUS = re.compile(BENCH + r"(?:status|verify)\b")
WAIT_TOOLS = frozenset({"wait", "sleep", "Monitor"})  # a harness's own wait or watch tools (Codex wait/sleep, Claude Monitor)
_ASKED = re.compile(r"status\b[^\n]{0,40}?\bevery\s+(\d+)\s+minutes?", re.IGNORECASE)
_HANDOFF = re.compile(r"^\s*HANDOFF:\s+lean-\S+@\S+", re.MULTILINE)


def _proved(step: tuple, start, call, ok) -> bool:
    _, how, pattern = step
    if ok is False:
        return False
    text = call.command or ""
    if how == "cmd":
        return re.search(pattern, text, re.DOTALL) is not None
    named = any(re.search(pattern, p) for p in call.paths)
    return (call.is_write and named) or (re.search(pattern, text) is not None and _WROTE.search(text) is not None)


def session_compliance(events: list, user_texts: list[str] | None, assistant_texts: list[str] | None) -> dict:
    """B6: a session against Prompt 1. `events` are (start time, ToolInput, ok) in native order. Reports the poll
    cadence (gaps between `bench status`/`verify` commands) against the interval the prompt asks for, which steps of the
    prompt have a proving call, and a HANDOFF line printed without handoff.json written. A call counts when it did not
    error (ok is not False); its exit code is not in the record, so "done" means attempted, not succeeded."""
    polls = sorted(t for t, call, ok in events if t and call.command and _STATUS.search(call.command))
    gaps = [(_ts(b) - _ts(a)).total_seconds() / 60 for a, b in pairwise(polls)]
    asked = next((int(m.group(1)) for t in user_texts or () if (m := _ASKED.search(t))), None)
    steps = {s[0]: any(_proved(s, t, call, ok) for t, call, ok in events) for s in STEPS}
    printed = None if assistant_texts is None else any(_HANDOFF.search(t) for t in assistant_texts)
    return {
        "status_checks": len(polls),
        "watcher_calls": sum(1 for _, call, _ in events if call.command and _STATUS.search(call.command) and _LOOPS.search(call.command)),
        "wait_calls": sum(1 for _, call, _ in events if call.name in WAIT_TOOLS),
        "intervals": len(gaps),
        "median_interval_min": round(statistics.median(gaps), 2) if gaps else None,
        "interval_why": None if gaps else "fewer than two status or verify commands with a start time",
        "asked_interval_min": asked,
        "asked_why": None if asked is not None else "no user message in the session states a status interval",
        "intervals_under_half_asked": sum(1 for g in gaps if g < asked / 2) if asked is not None and gaps else None,
        "steps": steps, "steps_done": sum(steps.values()), "steps_required": len(STEPS),
        "handoff_printed": printed, "handoff_json_written": steps["handoff_json_written"],
        "handoff_without_json": None if printed is None else (printed and not steps["handoff_json_written"]),
    }


def _text_blocks(content) -> list[str]:
    if isinstance(content, str):
        return [content]
    return [b["text"] for b in content or () if isinstance(b, dict) and isinstance(b.get("text"), str)]


def session_texts(harness: str, path: Path) -> tuple[list[str], list[str]] | None:
    """(user texts, assistant texts) read from the raw transcript; None for a harness with no text reader here."""
    if harness not in ("claude-code", "codex", "copilot"):
        return None
    user, assistant = [], []
    for row in _rows(path):
        if harness == "claude-code" and row.get("type") in ("user", "assistant"):
            msg = row.get("message") if isinstance(row.get("message"), dict) else {}
            (assistant if row["type"] == "assistant" else user).extend(_text_blocks(msg.get("content")))
        elif harness == "codex" and row.get("type") == "response_item":
            p = row.get("payload") if isinstance(row.get("payload"), dict) else {}
            if p.get("type") == "message" and p.get("role") in ("user", "assistant"):
                (assistant if p["role"] == "assistant" else user).extend(_text_blocks(p.get("content")))
        elif harness == "copilot" and row.get("type") in ("user.message", "assistant.message", "session.task_complete"):
            data = row.get("data") if isinstance(row.get("data"), dict) else {}
            # Copilot's final reply is the `summary` of its task_complete tool, not an assistant message's content
            text = data.get("summary") if row["type"] == "session.task_complete" else data.get("content")
            (user if row["type"] == "user.message" else assistant).extend(_text_blocks(text))
    return user, assistant


def codex_call_texts(path: Path) -> list[str]:
    """Each Codex tool call's argument text, in call order. Codex's `exec` carries its shell commands inside JavaScript
    source, which `ToolInput.command` does not read (it is None there), so the session read takes them from here."""
    from harness_bench.telemetry import codex

    out = []
    for row in _rows(path):
        p = row.get("payload") if isinstance(row.get("payload"), dict) else {}
        if row.get("type") == "response_item" and p.get("type") in codex.CALL_TYPES and p.get("call_id") is not None:
            text = p.get("arguments") if isinstance(p.get("arguments"), str) else p.get("input")
            out.append(text if isinstance(text, str) else "")
    return out


def sessions(specs: list[str]) -> list[dict]:
    """--session label=harness:path, read with the bench's own reader for that harness."""
    from harness_bench import profiles
    from harness_bench.report import tool_phases as tp

    out = []
    for spec in specs:
        label, _, rest = spec.partition("=")
        harness, _, raw = rest.partition(":")
        path = Path(raw)
        if path.is_dir():  # a Copilot session is a folder; its record is events.jsonl
            path = path / "events.jsonl"
        try:
            ex = profiles.READERS[harness](path)
        except Exception as exc:  # noqa: BLE001 - one unreadable transcript is recorded, never fatal
            out.append({"label": label, "harness": harness, "path": raw, "error": f"{type(exc).__name__}: {exc}"})
            continue
        calls = ex.model_calls
        row = {
            "label": label, "harness": harness, "path": raw,
            "model_calls": len(calls) or NOT_RECORDED,
            "output_tokens": sum(c.output for c in calls) if calls else NOT_RECORDED,
            "reasoning_tokens": (sum(c.reasoning or 0 for c in calls)
                                 if calls and any(c.reasoning is not None for c in calls) else NOT_RECORDED),
            "input_tokens": sum(c.uncached_input + c.cache_read + c.cache_write for c in calls) if calls else NOT_RECORDED,
            "tool_calls": len(ex.tool_calls),
            "tool_classes": dict(Counter(t.tool_class for t in ex.tool_calls)),
            "missing_fields": len(ex.missing),
        }
        reader = tp.TRACE_READERS.get(harness)
        try:
            trace = reader.tool_inputs(path) if reader else None
            if trace is None:
                row["compliance"] = {"not_recorded": f"no tool-input reader for {harness}"}
            elif len(trace.calls) != len(ex.tool_calls) or any(a.name != b.name for a, b in zip(trace.calls, ex.tool_calls)):
                row["compliance"] = {"not_recorded": f"tool calls and tool inputs disagree ({len(ex.tool_calls)} vs {len(trace.calls)})"}
            else:
                texts = session_texts(harness, path)
                inputs = list(trace.calls)
                if harness == "codex" and len(codex_call_texts(path)) == len(inputs):
                    inputs = [i if i.command else replace(i, command=t) for i, t in zip(inputs, codex_call_texts(path))]
                events = [(c.start, i, c.ok) for c, i in zip(ex.tool_calls, inputs)]
                row["compliance"] = session_compliance(events, texts[0] if texts else None, texts[1] if texts else None)
        except Exception as exc:  # noqa: BLE001 - recorded, never fatal
            row["compliance"] = {"not_recorded": f"{type(exc).__name__}: {exc}"}
        out.append(row)
    return out


# --- the page ------------------------------------------------------------------------------------------------------

def _groups(all_cells: list[dict]) -> dict[tuple[str, str], list[dict]]:
    groups = defaultdict(list)
    for c in all_cells:
        groups[(c["combo"], c["arm"])].append(c)
    return dict(sorted(groups.items()))


def _values(cs: list[dict], get) -> list[float]:
    return [v for v in (_num(get(c)) for c in cs) if v is not None]


def _table(groups, title: str, columns) -> list[str]:
    head = ["combo", "arm", "n", *(h for h, _ in columns)]
    lines = [title, "", "| " + " | ".join(head) + " |", "|" + "---|" * len(head)]
    for (combo, arm), cs in groups.items():
        row = [combo, arm, str(len(cs))]
        for _, get in columns:
            vals = _values(cs, get)
            row.append(_fmt(statistics.median(vals)) if vals else "-")
        lines.append("| " + " | ".join(row) + " |")
    return lines


def summary(all_cells: list[dict]) -> list[str]:
    groups = _groups(all_cells)
    return _table(groups, "Medians per combo x arm (computed from the runs' facts; `-` = not recorded, reasons below).",
                  COLUMNS)


def spread_table(all_cells: list[dict]) -> list[str]:
    """A8: median with its spread per measure, combo and arm, so a gap can be read against the noise between repetitions."""
    groups = _groups(all_cells)
    note = ("Per measure, combo and arm: recorded cells / cells, median, IQR (p25-p75, inclusive quartiles) and min-max. "
            "A gap smaller than the IQR is inside the noise.")
    lines = ["## Spread between repetitions (computed)", "", note, "",
             "| measure | combo | arm | recorded | median | p25-p75 | min-max |", "|---|---|---|---|---|---|---|"]
    for header, get in (*COLUMNS, *TOOL_COLUMNS, *ATTENTION_COLUMNS):
        for (combo, arm), cs in groups.items():
            s = spread(_values(cs, get))
            lines.append(f"| {header} | {combo} | {arm} | {s['n'] if s else 0}/{len(cs)} | "
                         + (f"{_fmt(s['median'])} | {_fmt(s['p25'])}-{_fmt(s['p75'])} | {_fmt(s['min'])}-{_fmt(s['max'])} |"
                            if s else "- | - | - |"))
    return lines


def drift_files_section(all_cells: list[dict]) -> list[str]:
    top = top_drift_files(all_cells)
    note = (f"Per combo x arm, the top {TOP_FILES} files by added lines in the discretionary class "
            "(machine-written paths excluded). `cells` = cells of that combo and arm that wrote the file.")
    lines = ["## Files behind the discretionary lines (computed from drift.log)", "", note, "",
             "| combo | arm | file | lines | cells |", "|---|---|---|---|---|"]
    for (combo, arm), files in sorted(top.items()):
        lines += [f"| {combo} | {arm} | {p} | {n} | {k} |" for p, n, k in files]
    if not top:
        lines.append("| - | - | no discretionary lines in any measured cell | - | - |")
    return lines


def not_recorded_section(all_cells: list[dict]) -> list[str]:
    """Why a measure has no value: per combo x arm, the commonest reason and how many cells it covers."""
    lines = ["## Not recorded, and why", "", "| combo | arm | measure | cells | reason |", "|---|---|---|---|---|"]
    n = 0
    for (combo, arm), cs in _groups(all_cells).items():
        for header, name in (*TOOL_MEASURES, *ATTENTION_MEASURES):
            reasons = Counter(re.sub(r"\d+", "N", c["why"].get(name) or NOT_RECORDED) for c in cs if c["m"].get(name) is None)
            if reasons:
                reason, count = reasons.most_common(1)[0]
                lines.append(f"| {combo} | {arm} | {header} | {sum(reasons.values())}/{len(cs)} | {reason}"
                             + (f" ({count} cells; {len(reasons) - 1} other reasons)" if len(reasons) > 1 else "") + " |")
                n += 1
    return lines if n else lines + ["| - | - | every new measure is recorded | - | - |"]


def sessions_section(sess: list[dict]) -> list[str]:
    md = ["## Interactive sessions (bench readers)", "",
          "| label | harness | model calls | output tok | reasoning tok | tool calls | tool classes |",
          "|---|---|---|---|---|---|---|"]
    md += [f"| {s['label']} | {s['harness']} | {s.get('model_calls', s.get('error'))} | {s.get('output_tokens', '-')} | "
           f"{s.get('reasoning_tokens', '-')} | {s.get('tool_calls', '-')} | {s.get('tool_classes', '-')} |" for s in sess]
    steps_note = ("Steps count when a call that did not error proves them (a bench command, or a file written, named in the "
                  "command text); the exit code is not in the record. Poll gaps are between `bench status` and `bench verify` "
                  "commands.")
    watch_note = ("Watcher calls = status commands inside a loop or sleep in one call; wait calls = the harness's own wait, "
                  "sleep or monitor tool calls (neither is a status check).")
    head = ("| label | status checks | median gap min | asked min | gaps under half asked | watcher calls | wait calls | "
            "steps done | HANDOFF printed | handoff.json written | HANDOFF without handoff.json |")
    md += ["", "### Compliance with Prompt 1 (computed from the transcript)", "", steps_note, "", watch_note, "", head,
           "|---|---|---|---|---|---|---|---|---|---|---|"]
    for s in sess:
        c = s.get("compliance") or {}
        if "not_recorded" in c or not c:
            md.append(f"| {s['label']} | not recorded: {c.get('not_recorded', s.get('error', 'no compliance read'))} |||||||||| ")
            continue

        def show(v, why=None):
            return NOT_RECORDED + (f" ({why})" if why else "") if v is None else str(v)
        md.append(f"| {s['label']} | {c['status_checks']} | {show(c['median_interval_min'], c['interval_why'])} | "
                  f"{show(c['asked_interval_min'], c['asked_why'])} | {show(c['intervals_under_half_asked'])}{'' if c['intervals_under_half_asked'] is None else ' of ' + str(c['intervals'])} | "
                  f"{c['watcher_calls']} | {c['wait_calls']} | {c['steps_done']} of {c['steps_required']} | {show(c['handoff_printed'])} | {c['handoff_json_written']} | "
                  f"{show(c['handoff_without_json'])} |")
    missing = [f"{s['label']}: " + ", ".join(k for k, v in s["compliance"]["steps"].items() if not v)
               for s in sess if "steps" in (s.get("compliance") or {}) and not all(s["compliance"]["steps"].values())]
    return md + ["", "Steps with no proving call: " + "; ".join(missing)] if missing else md


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
    groups = _groups(all_cells)
    md = ["# Behaviour measures", "", *summary(all_cells), "",
          *_table(groups, "Tool use and ceremony, medians per combo x arm (computed). tool_error_rate and stuck_loops: the "
                  "graded score, else grade/process.py over the cell's tool calls. Re-reads, bytes and the first edit: "
                  "report/tool_phases.py over the cell trace. Planning calls: class-meta tool calls. Reasoning per tool call: "
                  "reasoning tokens / tool calls.", TOOL_COLUMNS), "",
          *_table(groups, "Reads outside and inside the task's neighbourhood around the first edit (attention.log, computed).",
                  ATTENTION_COLUMNS), "",
          *spread_table(all_cells), "", *drift_files_section(all_cells), "", *not_recorded_section(all_cells), ""]
    if skipped:
        md += [f"Not measured (grading pass not completed): {', '.join(skipped)}", ""]
    if sess:
        md += sessions_section(sess)
    (out / "behaviour.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print(f"{len(all_cells)} cells, {len(sess)} sessions -> {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
