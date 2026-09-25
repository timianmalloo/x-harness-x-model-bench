"""Calibration and kappa (design phase3-gateway-judges sections 4.4 and 11, row s5; R-58 c5, R-62 a3, R-72).

T-GW-16, 16b, 17, 17b and 17c. The calibration pass runs through the real gateway pipeline and the real headless
backend; each call launches the fake judge CLI (`fixtures/gateway/fake_judge_cli.py`), which replays the committed
placeholder record with the 7-item answer `ANSWER`, and the real readers decide the outcome (directive D7). No real
model CLI is launched and no network call is made. The calibration set here is a synthetic three-item set with fixed
placeholder text, and every labels file is written by the test into its temp root: no labels are committed (R-72).
"""

import hashlib
import importlib
import json
from pathlib import Path

import pytest
import yaml
from test_grade_judge import ANSWER, CLAUDE, ROOT, fake_calls, judged_root, spawns

from harness_bench import ledger
from harness_bench.errors import BenchError
from harness_bench.grade import judge


def _module(name: str):
    try:
        return importlib.import_module(name)
    except ModuleNotFoundError:
        return None


calibration = _module("harness_bench.gateway.calibration")
NOT_BUILT = "harness_bench.gateway.calibration (design section 11, slice 5) is not built"

ITEMS = (("c1-cal-01", 4), ("c1-cal-02", 1), ("c1-cal-03", 6))  # (id, rubric item): the fake judge scores 0, 2, 2
VERDICTS = {i: ANSWER[n - 1] for i, n in ITEMS}
NO_LABELS = "not recorded: no human labels (operator declined 2026-09-25)"
SECOND = "inter-judge κ: not recorded: second judge not qualified"


def cal_root(tmp_path: Path) -> Path:
    """judged_root plus C1's calibration: adr_quality carries the rubric for C1 too and judges C1's two artifact files
    (design section 13), and bench/calibration/C1/ holds a synthetic three-item manifest in W3-CAL's layout. Each
    item's `intended_score` equals the fake judge's verdict, so a reader that took it for a label would compute a
    kappa (R-72 condition 3)."""
    root = judged_root(tmp_path)
    path = root / "bench" / "metrics.yaml"
    catalog = yaml.safe_load(path.read_text(encoding="utf-8"))
    for area in catalog["areas"].values():
        for m in area["metrics"]:
            if m["id"] == "adr_quality":
                m.update(rubrics={"X1": "adr_quality.md", "C1": "adr_quality.md"},
                         artifact=["docs/architecture.md", "priority_queue.py"])
    path.write_text(yaml.safe_dump(catalog, sort_keys=False), encoding="utf-8")
    cal = root / "bench" / "calibration" / "C1"
    (cal / "items").mkdir(parents=True)
    (cal / "code").mkdir()
    code = b"class PriorityQueue:\n    pass\n"
    (cal / "code" / "k1.py").write_bytes(code)
    rows = []
    for n, (item_id, rubric_item) in enumerate(ITEMS, 1):
        note = f"# Architecture\n\nPlaceholder calibration note {n}.\n".encode()
        (cal / "items" / f"{item_id}.md").write_bytes(note)
        rows.append({"id": item_id, "rubric_item": rubric_item, "path": f"items/{item_id}.md",
                     "sha256": hashlib.sha256(note).hexdigest(), "code": "code/k1.py",
                     "code_sha256": hashlib.sha256(code).hexdigest(), "author_model": "claude-opus-5-5",
                     "author_track": "W3-CAL", "authored_utc": "2026-09-25T13:53:52Z",
                     "intended_score": VERDICTS[item_id]})
    rubric = (ROOT / "tasks" / "C1" / "oracle" / "rubric.md").read_bytes()
    manifest = {"schema": "bench-calibration-manifest/1", "task": "C1", "rubric": "tasks/C1/oracle/rubric.md",
                "rubric_sha256": hashlib.sha256(rubric).hexdigest(), "items": rows}
    (cal / "manifest.yaml").write_text(yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8")
    return root


def write_labels(root: Path, rows: list[dict] | None, blind: bool | None = True) -> Path:
    """A labels file in the design's grain, `{id, score, labelled_utc}` per row, plus the file-level `blind:`
    attestation (R-72 condition 4); `rows=None` writes an empty file."""
    path = root / "bench" / "calibration" / "C1" / "labels.yaml"
    if rows is None:
        path.write_text("", encoding="utf-8")
        return path
    data = {"blind": blind} if blind is not None else {}
    path.write_text(yaml.safe_dump(data | {"labels": rows}, sort_keys=False), encoding="utf-8")
    return path


def label(item_id: str, score, utc: str = "2026-09-25T00:00:00Z") -> dict:
    return {"id": item_id, "score": score, "labelled_utc": utc}


def calibrate(root: Path, tmp_path: Path, base: Path) -> str:
    return calibration.run(root, tmp_path / "runs", fake_calls(tmp_path, base / "cells", judge.Calls))


def ledger_dir(tmp_path: Path) -> Path:
    [folder] = sorted((tmp_path / "runs").glob("calibration-C1-*"))
    return folder


def started(tmp_path: Path, cal_id: str) -> dict:
    [row] = [e for e in ledger.read_segment(ledger_dir(tmp_path) / "events" / f"{cal_id}.jsonl")
             if e["kind"] == "calibration.started"]
    return row


def line(root: Path, tmp_path: Path) -> str:
    return calibration.header_line(root, tmp_path / "runs", "C1")


# --------------------------------------------------------------------------------------------------- T-GW-16
REFUSED = "HB-CAL-001: bench/calibration/C1/labels.yaml does not match the manifest (R-72: all or none): "


@pytest.mark.parametrize(("rows", "problem"), [
    ([label("c1-cal-01", 0), label("c1-cal-01", 0), label("c1-cal-02", 2)],
     "duplicate id c1-cal-01; missing id c1-cal-03"),
    ([label("c1-cal-01", 0), label("c1-cal-02", 2)], "missing id c1-cal-03"),
    ([label("c1-cal-01", 0), label("c1-cal-02", 2), label("c1-cal-03", 2), label("c1-cal-99", 1)],
     "unknown id c1-cal-99"),
    ([label("c1-cal-01", 0), label("c1-cal-02", 3), label("c1-cal-03", 2)], "c1-cal-02: score 3 is not 0, 1 or 2"),
    ([label("c1-cal-01", 0), label("c1-cal-02", True), label("c1-cal-03", 2)],
     "c1-cal-02: score True is not 0, 1 or 2"),
    (None, "no label rows (an empty file is not an absent file)"),
], ids=["duplicate", "missing", "unknown id", "score 3", "bool score", "empty file"])
def test_t_gw_16_a_labels_file_that_does_not_match_the_manifest_is_refused_before_any_spawn(tmp_path, base, rows,
                                                                                            problem):
    assert calibration is not None, NOT_BUILT
    root = cal_root(tmp_path)
    write_labels(root, rows)
    with pytest.raises(BenchError) as refused:
        calibrate(root, tmp_path, base)
    assert f"{refused.value.code}: {refused.value.message}" == REFUSED + problem
    assert spawns(tmp_path) == 0 and not (tmp_path / "runs").exists()  # no spawn, no ledger


def test_t_gw_16_with_no_labels_file_the_calibration_spawns_and_the_human_half_is_not_recorded(tmp_path, base):
    """R-72 item 4 and condition 2: HB-CAL-001 is file-conditional; an absent file runs the inter-judge calibration
    and records `labels_sha256: null` explicitly."""
    assert calibration is not None, NOT_BUILT
    root = cal_root(tmp_path)
    cal_id = calibrate(root, tmp_path, base)
    assert spawns(tmp_path) == len(ITEMS)  # the qualified judge, once per item; the unqualified one never
    row = started(tmp_path, cal_id)
    assert "labels_sha256" in row and row["labels_sha256"] is None
    assert line(root, tmp_path) == f"n = 3 · {SECOND} · vs human labels: {NO_LABELS}"


def test_t_gw_16_a_matching_labels_file_is_recorded_by_its_sha256_and_scored(tmp_path, base):
    assert calibration is not None, NOT_BUILT
    root = cal_root(tmp_path)
    path = write_labels(root, [label(i, VERDICTS[i]) for i, _ in ITEMS])
    cal_id = calibrate(root, tmp_path, base)
    assert started(tmp_path, cal_id)["labels_sha256"] == hashlib.sha256(path.read_bytes()).hexdigest()
    assert line(root, tmp_path) == f"n = 3 · {SECOND} · vs human labels: {CLAUDE} κ 1.000 (n = 3, exact 3)"


def test_calibration_uses_rows_carry_each_key_and_entry_sha256(tmp_path, base):
    """Design section 4.4: one row per (calibration item, judge), with the store key and entry hash of every recorded
    lookup, so kappa is derived from these rows and the entries they name."""
    assert calibration is not None, NOT_BUILT
    root = cal_root(tmp_path)
    cal_id = calibrate(root, tmp_path, base)
    rows = ledger.read_segment(ledger_dir(tmp_path) / "calibration_uses" / f"{cal_id}.jsonl")
    uses = sorted((r["item_id"], r["judge_or_matcher"], r["outcome"], r["code"]) for r in rows if "item_id" in r)
    assert uses == sorted([(i, CLAUDE, "stored", None) for i, _ in ITEMS] +
                          [(i, "gpt-6-sol", "failed", "HB-GW-007") for i, _ in ITEMS])
    for r in rows:
        if r.get("outcome") == "stored":
            entry = root / "cache" / "verdicts" / f"{r['cache_key']}.json"
            assert hashlib.sha256(entry.read_bytes()).hexdigest() == r["entry_sha256"]
    # a second calibration pass reads the store: 0 spawns, and every row a hit (R-72 item 5)
    again = calibrate(root, tmp_path, base)
    assert spawns(tmp_path) == len(ITEMS)
    rows = ledger.read_segment(ledger_dir(tmp_path) / "calibration_uses" / f"{again}.jsonl")
    assert sorted(r["outcome"] for r in rows if r.get("judge_or_matcher") == CLAUDE) == ["hit"] * len(ITEMS)


def test_the_calibration_request_is_the_production_template_with_the_full_rubric_and_both_artifact_files(tmp_path,
                                                                                                        base):
    """Design section 11: the production template and the full rubric; the artifact is the two files the W3-CAL
    manifest's layout names, `path` as docs/architecture.md and `code` as priority_queue.py (design section 7.1)."""
    assert calibration is not None, NOT_BUILT
    root = cal_root(tmp_path)
    calibrate(root, tmp_path, base)
    [first] = sorted((tmp_path / "capture").glob("*.json"))[:1]
    sent = json.loads(first.read_text(encoding="utf-8"))["stdin"]
    rubric = (ROOT / "tasks" / "C1" / "oracle" / "rubric.md").read_text(encoding="utf-8").strip()
    assert sent.startswith("Grade the artifact below against the rubric. Score each rubric item 0, 1 or 2.\n")
    assert f"Rubric:\n{rubric}\n\nOracle: the rubric above." in sent
    assert " docs/architecture.md>>>\n# Architecture\n\nPlaceholder calibration note " in sent
    assert " priority_queue.py>>>\nclass PriorityQueue:\n    pass\n<<<END DATA " in sent
