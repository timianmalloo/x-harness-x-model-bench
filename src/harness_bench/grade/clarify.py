"""Scripted-user log vs the oracle's annotated clarifications.

Metrics: key_question_recall, key_question_precision, ask_vs_assume, asked_unmatched.
Design: docs/design/phase3-graders.md section "Clarification" (W3-GR-CLAR slice l1).
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from decimal import Decimal
from pathlib import Path

import yaml

from harness_bench.grade import CellInput, Score

METRICS = ("key_question_recall", "key_question_precision", "ask_vs_assume", "asked_unmatched")


def _na_all(reason: str, evidence: str = "") -> dict[str, Score]:
    return {m: Score(None, reason, evidence) for m in METRICS}


def _ratio(num: int, denom: int, scale: int | None) -> int | Decimal:
    if scale is not None:
        return Decimal(num) / Decimal(denom)
    return num // denom


def grade_cell(inp: CellInput) -> Mapping[str, Score]:
    """Grade clarification metrics from the cell's archived scripted-user.jsonl."""
    log_path = inp.archive / "scripted-user.jsonl" if inp.archive.is_dir() else inp.archive
    try:
        evidence = log_path.relative_to(inp.run_dir).as_posix()
    except ValueError:
        evidence = log_path.name

    if not log_path.is_file():
        return _na_all("no scripted-user log", "")

    try:
        text = log_path.read_text(encoding="utf-8")
    except OSError:
        return _na_all("scripted-user log unreadable: invalid row", evidence)

    if not text.endswith("\n"):
        return _na_all("scripted-user log unreadable: torn tail", evidence)

    rows: list[dict] = []
    for line in text.split("\n")[:-1]:
        try:
            row = json.loads(line)
        except (ValueError, json.JSONDecodeError):
            return _na_all("scripted-user log unreadable: invalid row", evidence)
        if not isinstance(row, dict) or "kind" not in row or not isinstance(row["kind"], str):
            return _na_all("scripted-user log unreadable: invalid row", evidence)
        if row.get("torn_tail") is True:
            return _na_all("scripted-user log unreadable: torn tail", evidence)
        rows.append(row)

    end_row = next((r for r in rows if r["kind"] == "end"), None)
    if end_row is not None and not end_row.get("tool_listed", True):
        return _na_all("tool not reached", evidence)

    task_name = inp.cell.get("task", "")
    plan_task = inp.plan.get("tasks", {}).get(task_name, {})
    frozen_cset_hash = plan_task.get("clarifications_sha256")
    frozen_matcher_version = plan_task.get("matcher_version")

    header_row = next((r for r in rows if r["kind"] == "header"), None)
    if header_row is not None:
        if frozen_cset_hash is not None and header_row.get("clarifications_sha256") != frozen_cset_hash:
            return _na_all("clarification set changed since the plan", evidence)
        if frozen_matcher_version is not None and header_row.get("matcher_version") != frozen_matcher_version:
            return _na_all("matcher version differs from the plan's", evidence)

    cset_path_str = plan_task.get("clarifications_path")
    cset_file = Path(cset_path_str) if cset_path_str else inp.task_dir / "oracle" / "clarifications.yaml"
    if cset_file.is_file():
        cset_bytes = cset_file.read_bytes()
        cset_sha256 = hashlib.sha256(cset_bytes).hexdigest()
        if frozen_cset_hash is not None and cset_sha256 != frozen_cset_hash:
            return _na_all("clarification set changed since the plan", evidence)
        try:
            cset_doc = yaml.safe_load(cset_bytes)
        except (yaml.YAMLError, UnicodeDecodeError):
            cset_doc = {}
    else:
        cset_doc = {}

    annotated_items = cset_doc.get("clarifications") if isinstance(cset_doc, dict) else []
    annotated_ids = {c["id"] for c in annotated_items if isinstance(c, dict) and "id" in c}
    if not annotated_ids:
        annotated_ids = {"goal-maximum"}
    annotated_count = len(annotated_ids)

    call_rows = [r for r in rows if r["kind"] == "call"]
    for call in call_rows:
        if frozen_cset_hash is not None and call.get("clarifications_sha256") != frozen_cset_hash:
            return _na_all("clarification set changed since the plan", evidence)
        if frozen_matcher_version is not None and call.get("matcher_version") != frozen_matcher_version:
            return _na_all("matcher version differs from the plan's", evidence)

    if not call_rows:
        return {
            "key_question_recall": Score(0, None, evidence),
            "key_question_precision": Score(None, "no question asked", evidence),
            "ask_vs_assume": Score(0, None, evidence),
            "asked_unmatched": Score(0, None, evidence),
        }

    matched_annotated_ids: set[str] = set()
    matched_call_count = 0
    unmatched_call_count = 0

    for row in call_rows:
        decision = row.get("decision") or {}
        clarification_id = decision.get("clarification")
        if clarification_id is not None and clarification_id in annotated_ids:
            matched_annotated_ids.add(clarification_id)
            matched_call_count += 1
        else:
            unmatched_call_count += 1

    distinct_matched = len(matched_annotated_ids)
    recall_scale = inp.metrics.get("key_question_recall", {}).get("scale")
    precision_scale = inp.metrics.get("key_question_precision", {}).get("scale")
    ask_scale = inp.metrics.get("ask_vs_assume", {}).get("scale")

    recall = _ratio(distinct_matched, annotated_count, recall_scale)
    precision = _ratio(matched_call_count, len(call_rows), precision_scale)
    capped_calls = min(len(call_rows), annotated_count)
    ask_vs_assume = _ratio(capped_calls, annotated_count, ask_scale)
    asked_unmatched = unmatched_call_count

    return {
        "key_question_recall": Score(recall, None, evidence),
        "key_question_precision": Score(precision, None, evidence),
        "ask_vs_assume": Score(ask_vs_assume, None, evidence),
        "asked_unmatched": Score(asked_unmatched, None, evidence),
    }
