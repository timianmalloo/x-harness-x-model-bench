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
import shutil
from pathlib import Path

import pytest
import yaml
from test_grade_judge import ANSWER, CLAUDE, ROOT, fake_calls, judged_root, spawns

from harness_bench import config, ledger
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


_CALLS: dict[Path, judge.Calls] = {}


def calibrate(root: Path, tmp_path: Path, base: Path) -> str:
    """One calibration pass; the call environment (`fake_calls`) is built once per test."""
    if tmp_path not in _CALLS:
        _CALLS[tmp_path] = fake_calls(tmp_path, base / "cells", judge.Calls)
    return calibration.run(root, tmp_path / "runs", _CALLS[tmp_path])


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


# -------------------------------------------------------------------------------------- T-GW-16b and T-GW-17c
CHANGED = "vs human labels: not recorded: labels changed since calibration"


def test_t_gw_16b_a_relabel_after_calibration_reads_labels_changed(tmp_path, base):
    assert calibration is not None, NOT_BUILT
    root = cal_root(tmp_path)
    write_labels(root, [label(i, VERDICTS[i]) for i, _ in ITEMS])
    calibrate(root, tmp_path, base)
    write_labels(root, [label(i, 1) for i, _ in ITEMS])  # one relabel after the calibration pass
    assert line(root, tmp_path) == f"n = 3 · {SECOND} · {CHANGED}"


def test_t_gw_16b_labels_that_arrive_after_a_calibration_without_labels_read_labels_changed(tmp_path, base):
    """R-72 item 5: the recorded sha256 is null, so a later file is a change; a new calibration pass completes the
    human half from the store with 0 spawns."""
    assert calibration is not None, NOT_BUILT
    root = cal_root(tmp_path)
    calibrate(root, tmp_path, base)
    write_labels(root, [label(i, VERDICTS[i]) for i, _ in ITEMS])
    assert line(root, tmp_path) == f"n = 3 · {SECOND} · {CHANGED}"
    calibrate(root, tmp_path, base)
    assert spawns(tmp_path) == len(ITEMS)
    assert line(root, tmp_path) == f"n = 3 · {SECOND} · vs human labels: {CLAUDE} κ 1.000 (n = 3, exact 3)"


def _rubric(root: Path) -> None:
    path = root / "bench" / "rubrics" / "adr_quality.md"
    path.write_bytes(path.read_bytes() + b"\n")


def _template(monkeypatch) -> None:
    from harness_bench.gateway import request
    monkeypatch.setattr(request, "TEMPLATE_VERSION", "judge-request/3")


def _schema(monkeypatch) -> None:
    from harness_bench.gateway import schema
    monkeypatch.setattr(schema, "schema_sha256", lambda: "5" * 64)


def _invocation(root: Path) -> None:
    from harness_bench.gateway import backend
    path = root / "bench" / "gateway.yaml"
    g = yaml.safe_load(path.read_text(encoding="utf-8"))
    first = g["judges"][0]
    first["build"]["exe_sha256"] = "2" * 64  # another build of the same CLI: a new invocation_sha256
    first["invocation_sha256"] = backend.invocation_sha256(first["harness"], first["model"], backend.JUDGE_SYSTEM,
                                                           first["output"], first["build"]["version"], "2" * 64)
    path.write_text(yaml.safe_dump(g, sort_keys=False), encoding="utf-8")


@pytest.mark.parametrize("change", ["template", "schema", "rubric", "invocation"])
def test_t_gw_17c_a_changed_template_schema_rubric_or_invocation_reads_calibration_stale(tmp_path, base, monkeypatch,
                                                                                       change):
    assert calibration is not None, NOT_BUILT
    root = cal_root(tmp_path)
    calibrate(root, tmp_path, base)
    assert line(root, tmp_path) == f"n = 3 · {SECOND} · vs human labels: {NO_LABELS}"
    {"template": lambda: _template(monkeypatch), "schema": lambda: _schema(monkeypatch),
     "rubric": lambda: _rubric(root), "invocation": lambda: _invocation(root)}[change]()
    assert line(root, tmp_path) == "not recorded: calibration stale"


def test_with_no_calibration_pass_the_row_says_so(tmp_path):
    assert calibration is not None, NOT_BUILT
    assert line(cal_root(tmp_path), tmp_path) == "not recorded: no calibration pass"


# ------------------------------------------------------------------------------------- R-72 conditions 3 and 4
def test_r72_c3_intended_score_is_never_a_label_nor_a_kappa_input(tmp_path, base):
    """With the manifest present (every intended_score equal to the judge's verdict) and labels.yaml absent, the
    human half is NOT_RECORDED and no kappa is computed; no module of the calibration path reads the field."""
    assert calibration is not None, NOT_BUILT
    root = cal_root(tmp_path)
    calibrate(root, tmp_path, base)
    assert "κ" not in line(root, tmp_path).split("vs human labels:")[1]
    for path in (ROOT / "src" / "harness_bench" / "gateway" / "calibration.py", ROOT / "tools" / "calibrate.py"):
        assert "intended_score" not in path.read_text(encoding="utf-8"), path.name


@pytest.mark.parametrize(("blind", "utc", "notes"), [
    (True, "2026-09-25T00:00:00Z", ""),
    (False, "2026-09-25T00:00:00Z", " · labeller blinding: not recorded"),
    (None, "2026-09-25T00:00:00Z", " · labeller blinding: not recorded"),
    (True, "2999-01-01T00:00:00Z", " · labels post-date the calibration verdicts"),
], ids=["blind, before", "not blind", "no attestation", "post-dated"])
def test_r72_c4_the_blind_attestation_and_labelled_utc_are_read_and_shown(tmp_path, base, blind, utc, notes):
    assert calibration is not None, NOT_BUILT
    root = cal_root(tmp_path)
    write_labels(root, [label(i, VERDICTS[i], utc) for i, _ in ITEMS], blind=blind)
    calibrate(root, tmp_path, base)
    assert line(root, tmp_path) == f"n = 3 · {SECOND} · vs human labels: {CLAUDE} κ 1.000 (n = 3, exact 3){notes}"


# --------------------------------------------------------------------------------------------------- T-GW-17
def pairs(table: dict[tuple[int, int], int]) -> list[tuple[int, int]]:
    return [cell for cell, count in table.items() for _ in range(count)]


# rater 1 marginals (0, 1, 2) = (5, 3, 2); rater 2 = (4, 4, 2): asymmetric. p_o = 6/10, p_e = 36/100, so
# kappa = (0.6 - 0.36) / (1 - 0.36) = 0.375 exactly.
ASYMMETRIC = {(0, 0): 3, (1, 1): 2, (2, 2): 1, (0, 1): 2, (1, 2): 1, (2, 0): 1}
# the same marginals with 4 agreements: kappa = (0.4 - 0.36) / 0.64 = 0.0625, a tie at scale 3: half-even is 0.062
TIE = {(0, 0): 2, (1, 1): 1, (2, 2): 1, (0, 1): 2, (0, 2): 1, (1, 0): 2, (2, 1): 1}


def test_t_gw_17_kappa_is_unweighted_cohen_at_scale_3_half_even_with_n_and_exact_agreement():
    assert calibration is not None, NOT_BUILT
    kappa = calibration.kappa
    assert kappa(pairs(ASYMMETRIC)) == calibration.Kappa(n=10, exact=6, value="0.375", reason=None)
    assert kappa(pairs(TIE)) == calibration.Kappa(n=10, exact=4, value="0.062", reason=None)
    # swapping the raters leaves kappa unchanged (the marginals swap)
    assert kappa([(b, a) for a, b in pairs(ASYMMETRIC)]).value == "0.375"
    # unweighted: a two-step disagreement costs what a one-step one does
    assert kappa([(0, 0), (1, 1), (2, 2), (0, 2)]) == kappa([(0, 0), (1, 1), (2, 2), (0, 1)]) == \
        calibration.Kappa(n=4, exact=3, value="0.636", reason=None)
    # perfect agreement over two categories; total disagreement is negative
    assert kappa([(0, 0), (2, 2)]).value == "1.000"
    assert kappa([(0, 2), (2, 0)]).value == "-1.000"


def test_t_gw_17_one_category_is_not_recorded_with_n_and_exact_agreement():
    assert calibration is not None, NOT_BUILT
    assert calibration.kappa([(1, 1)] * 5) == \
        calibration.Kappa(n=5, exact=5, value=None, reason="kappa undefined: one category")
    assert calibration.kappa([(0, 2)] * 5) == calibration.Kappa(n=5, exact=0, value="0.000", reason=None)  # p_e = 0
    assert calibration.kappa([]) == calibration.Kappa(n=0, exact=0, value=None, reason="no recorded pairs")
    assert calibration.Kappa(n=5, exact=5, value=None, reason="kappa undefined: one category").text() == \
        "not recorded: kappa undefined: one category (n = 5, exact 5)"
    assert calibration.Kappa(n=10, exact=6, value="0.375", reason=None).text() == "0.375 (n = 10, exact 6)"


# --------------------------------------------------------------------------------------------------- T-GW-17b
def test_t_gw_17b_only_the_labelled_rubric_item_of_the_seven_item_verdict_set_is_compared(tmp_path, base):
    """Each item's verdict set scores all 7 rubric items (ANSWER); the join takes the verdict on the item's own
    `rubric_item` (4, 1, 6 -> 0, 2, 2). Labels of 2 everywhere agree on two items: kappa 0 with exact 2. Comparing
    item 1 (2 everywhere) would read one category, and item 4 (0 everywhere) exact 0."""
    assert calibration is not None, NOT_BUILT
    root = cal_root(tmp_path)
    write_labels(root, [label(i, 2) for i, _ in ITEMS])
    calibrate(root, tmp_path, base)
    assert line(root, tmp_path) == f"n = 3 · {SECOND} · vs human labels: {CLAUDE} κ 0.000 (n = 3, exact 2)"


# ------------------------------------------------------------------ C1's rubric in the catalog (section 13, R-64)
R64_NOTE = ("Judged: no proof, model check, trace conformance or test decides whether an architecture note's claims are "
            "stated and consistent with the code it describes (US-25; R-64).")


def _adr_quality(root: Path) -> dict:
    catalog = yaml.safe_load((root / "bench" / "metrics.yaml").read_text(encoding="utf-8"))
    [entry] = [m for area in catalog["areas"].values() for m in area["metrics"] if m["id"] == "adr_quality"]
    return entry


def test_c1s_rubric_is_in_the_catalog_with_its_artifact_list_note_and_scale():
    """Design section 13 in the graders design's field form (`rubrics: {C1: adr_quality.md}` names the file and the
    task at once), the R-64 note rendered as the preamble, and scale 1 for the synthesized half-steps."""
    entry = _adr_quality(ROOT)
    assert (entry.get("rubrics"), entry.get("artifact"), entry.get("scale"), entry.get("note")) == \
        ({"C1": "adr_quality.md"}, ["docs/architecture.md", "priority_queue.py"], 1, R64_NOTE)
    assert (ROOT / "bench" / "rubrics" / "adr_quality.md").read_bytes() == \
        (ROOT / "tasks" / "C1" / "oracle" / "rubric.md").read_bytes()
    catalog = yaml.safe_load((ROOT / "bench" / "metrics.yaml").read_text(encoding="utf-8"))
    assert [m["id"] for area in catalog["areas"].values() for m in area["metrics"] if m.get("rubrics")] == \
        ["adr_quality"]  # every other judged metric: NA `no rubric for this task` (R-59 c2)


def test_r64_c2_bench_validate_scans_a_judged_metrics_note_and_rubric_with_the_scrub_denylist(tmp_path):
    root = tmp_path / "root"
    shutil.copytree(ROOT / "bench", root / "bench")
    shutil.copytree(ROOT / "tasks" / "C1", root / "tasks" / "C1")
    path = root / "bench" / "metrics.yaml"
    catalog = yaml.safe_load(path.read_text(encoding="utf-8"))
    area = next(a for a, v in catalog["areas"].items() if any(m["id"] == "adr_quality" for m in v["metrics"]))
    for m in catalog["areas"][area]["metrics"]:
        if m["id"] == "adr_quality":
            m.update(rubrics={"C1": "adr_quality.md"}, note="Judged by an Opus-class reader.")
    path.write_text(yaml.safe_dump(catalog, sort_keys=False), encoding="utf-8")
    (root / "bench" / "rubrics").mkdir(exist_ok=True)
    (root / "bench" / "rubrics" / "adr_quality.md").write_bytes(
        (ROOT / "tasks" / "C1" / "oracle" / "rubric.md").read_bytes())
    scanned = [p for p in config.validate_repo(root) if "denylist" in p]
    assert scanned == [f"bench/metrics.yaml: {area}.adr_quality: note holds a scrub denylist entry (R-64 c2)"]


def test_an_entry_changed_after_calibration_is_not_a_kappa_input(tmp_path, base):
    """kappa reads a verdict only from an entry whose bytes still hash to the row's entry_sha256."""
    assert calibration is not None, NOT_BUILT
    root = cal_root(tmp_path)
    write_labels(root, [label(i, VERDICTS[i]) for i, _ in ITEMS])
    calibrate(root, tmp_path, base)
    for entry in sorted((root / "cache" / "verdicts").glob("*.json")):
        entry.chmod(0o644)
        entry.write_bytes(entry.read_bytes() + b" ")
    assert line(root, tmp_path) == \
        f"n = 3 · {SECOND} · vs human labels: {CLAUDE} κ not recorded: no recorded pairs (n = 0, exact 0)"


def test_tools_calibrate_runs_one_pass_and_prints_the_header_line(tmp_path, base, monkeypatch, capsys):
    """The CLI wrapper: the call environment is `bench grade --allow-model-calls`'s own (`cli._judge_calls`), stood in
    here by the fake judge's; a refused labels file exits 1 with its HB code."""
    import importlib.util

    from harness_bench import cli

    spec = importlib.util.spec_from_file_location("calibrate_tool", ROOT / "tools" / "calibrate.py")
    tool = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(tool)
    root = cal_root(tmp_path)
    calls = fake_calls(tmp_path, base / "cells", judge.Calls)
    monkeypatch.setattr(cli, "_judge_calls", lambda args, r: calls)
    argv = ["--root", str(root), "--runs", str(tmp_path / "runs")]
    assert tool.main(argv) == 0
    out = capsys.readouterr().out.splitlines()
    assert out[0].startswith("calibration cal-") and out[1] == f"n = 3 · {SECOND} · vs human labels: {NO_LABELS}"
    write_labels(root, [label("c1-cal-01", 0)])
    assert tool.main(argv) == 1
    assert capsys.readouterr().err == f"{REFUSED}missing id c1-cal-02; missing id c1-cal-03\n"
    assert spawns(tmp_path) == len(ITEMS)
