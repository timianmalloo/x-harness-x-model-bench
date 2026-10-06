"""The US-4 control: a score, weight, rubric or definition never changes under one catalog version (R-59 c1, c3;
design docs/design/phase3-graders.md, "Catalog-version rule" 4; CORE s2). Statistics have their own golden
(R-78 DR-S-4): `board.export` of each fixture, pinned the same way.

For a current `version` that does not end in `.dev`, the control fails when:
- (a) a committed fixture, graded offline under the current catalog, exports other bytes than its golden file
      `tests/fixtures/catalog/<version>/<fixture>.export` (a score or reason moved with no bump), or other board
      bytes than `tests/fixtures/catalog/<version>/<fixture>.board.export` (`board.export(board.build(view, catalog))`
      at the default seed and resamples);
- (b) the current `catalog_hash` differs from the one pinned for the version in `bench/catalog-freeze.yaml` (a weight,
      rubric, definition or anchor edit, which the export cannot see), or none is pinned;
- (c) the golden files' sha256 differ from the digests pinned there (`golden` and `board_golden`; a same-commit
      rewrite of a golden file);
- (d) no golden file exists for the version (a freeze needs a golden export), or a released version whose freeze
      entry has no `board_golden` was frozen after boards existed;
- (e) an entry present in `bench/catalog-freeze.yaml` at the merge base was changed or removed (append-only per
      version), `board_golden` included.
A `.dev` version is a probe and is exempt from (a)-(d) only here; the control prints `probe: exempt`. (e) always applies.
A version frozen before boards existed (its entry has no `board_golden`, as 0.4) is exempt from the board check; the
control prints `board golden: not pinned (frozen before board.export)`.

`bench/catalog-freeze.yaml` is Leader-owned (written at each freeze); this file only reads it.
The fixtures are the two committed X1 mini-runs (D6); the judge is not applicable to X1, so no model is called.
"""

import copy
import hashlib
import io
import json
import os
import shutil
import subprocess
import tarfile
import tomllib
import uuid
from collections.abc import Callable
from decimal import Decimal
from pathlib import Path

import pytest
import yaml
from archived_runs import ROOT, make_root, set_catalog_version
from slow_ring import dotnet_gate

from harness_bench import board, composites, config, ledger, views
from harness_bench.grade import Score, runner
from harness_bench.grade import property as grade_property
from harness_bench.telemetry import normalize

FIXTURES = {name: Path(__file__).parent / "fixtures" / "ledger" / name / "run" for name in ("c44dd2b-no-heads", "heads")}
GOLDEN = Path(__file__).parent / "fixtures" / "catalog"
FREEZE = "bench/catalog-freeze.yaml"
PROBE = "probe: exempt"
BOARD_EXEMPT = "board golden: not pinned (frozen before board.export)"


def graded_view(root: Path, name: str, tmp: Path):
    """Fixture `name` after one pass under `root`'s catalog, read by that catalog's version."""
    run_dir = tmp / f"us4-{name}-{uuid.uuid4().hex}" / "run"
    shutil.copytree(FIXTURES[name], run_dir)
    runner.run_pass(run_dir, root)
    return views.load(run_dir, str(config.load_yaml(root / "bench" / "metrics.yaml")["version"]))


def graded_export(root: Path, name: str, tmp: Path) -> bytes:
    """The views export of fixture `name` after one pass under `root`'s catalog."""
    return views.export(graded_view(root, name, tmp))


def graded_board_export(root: Path, name: str, tmp: Path) -> bytes:
    """`board.export(board.build(view, catalog))` at the default seed and resamples."""
    view = graded_view(root, name, tmp)
    return board.export(board.build(view, composites.load_catalog(root)))


def _board_stem(path: Path) -> str | None:
    """The fixture name of a `<fixture>.board.export`, or None for a views golden."""
    suffix = ".board.export"
    return path.name[:-len(suffix)] if path.name.endswith(suffix) else None


def us4_problems(root: Path, golden: Path, freeze: dict, base: dict, export: Callable[[str], bytes],
                 board_export: Callable[[str], bytes] | None = None,
                 board_golden: Path | None = None) -> list[str]:
    """Checks (a)-(e) for `root`'s current catalog, views and board goldens; [] when the control passes.

    A freeze entry with no `board_golden` key was written before boards existed (0.4). That version skips the board
    check and the control prints the exemption. An entry that has the key, even empty, was frozen after and is checked.
    """
    versions, was = freeze.get("versions") or {}, base.get("versions") or {}
    problems = [f"(e) {FREEZE} entry {v!r} was changed or removed since the merge base" for v in sorted(was) if versions.get(v) != was[v]]

    board_exports, was_b = freeze.get("board_exports") or {}, base.get("board_exports") or {}
    for n in sorted(was_b):
        if board_exports.get(n) != was_b[n]:
            problems.append(f"(e) {FREEZE} board_exports entry {n!r} was changed or removed since the merge base")

    if ("0.5" in versions and "board_golden" in versions["0.5"] and "1" in board_exports
            and board_exports["1"].get("golden") != versions["0.5"].get("board_golden")):
        problems.append(f"(e) board_exports['1'].golden != versions['0.5'].board_golden in {FREEZE}")

    version = str(config.load_yaml(root / "bench" / "metrics.yaml")["version"])
    if version.endswith(".dev"):
        print(PROBE)
        return problems
    pinned = versions.get(version)
    current = runner.catalog_hash(root)
    if pinned is None:
        problems.append(f"(b) no catalog_hash pinned for {version} in {FREEZE}")
    elif pinned.get("catalog_hash") != current:
        problems.append(f"(b) catalog_hash {current} != {pinned.get('catalog_hash')} pinned for {version}: a weight, rubric or "
                        "definition changed without a version bump")
    files = sorted(p for p in (golden / version).glob("*.export") if _board_stem(p) is None)
    if not files:
        problems.append(f"(d) no golden export for {version} (a freeze needs a golden export)")
    digests = {f.stem: hashlib.sha256(f.read_bytes()).hexdigest() for f in files}
    if pinned is not None and digests != (pinned.get("golden") or {}):
        problems.append(f"(c) golden exports for {version} differ from the digests pinned in {FREEZE}")
    for f in files:
        if f.stem not in FIXTURES:
            problems.append(f"(a) {f.stem}: no committed fixture of that name")
        elif export(f.stem) != f.read_bytes():
            problems.append(f"(a) {f.stem}: the export differs from its golden file (a score or reason moved without a bump)")

    if pinned is not None and "board_golden" in pinned:
        board_files = sorted((golden / version).glob("*.board.export"))
        if not board_files:
            problems.append(f"(d) no board golden for {version} (a freeze after board.export needs a board golden)")
        board_digests = {stem: hashlib.sha256(p.read_bytes()).hexdigest() for p in board_files if (stem := _board_stem(p))}
        if board_digests != (pinned.get("board_golden") or {}):
            problems.append(f"(c) board goldens for {version} differ from the digests pinned in {FREEZE}")

    if pinned is not None and "board_golden" not in pinned:
        print(BOARD_EXEMPT)
        return sorted(problems)

    if board_golden is None:
        board_golden = golden.parent / "board"
    N = str(getattr(board, "EXPORT_VERSION", 1))

    if pinned is not None and pinned.get("board_export_version") == N:
        # R-86: a catalog bump under an unchanged EXPORT_VERSION pins the pair (version, N) in versions[version]
        # itself, not in board_exports[N] (which has one golden per export version and cannot also move to a new
        # catalog without rewriting an append-only entry). Its golden is the per-version directory already
        # checked above (board_files/board_digests, (c)); (a) is the one check this path still owes.
        for p in board_files:
            stem = _board_stem(p)
            if stem not in FIXTURES:
                problems.append(f"(a) {stem}: no committed fixture of that name")
            elif board_export is not None and board_export(stem) != p.read_bytes():
                problems.append(f"(a) {stem}: the board export differs from its golden file "
                                "(a statistic moved without a bump)")
    elif N not in board_exports:
        problems.append(f"(d) no board_exports entry for export version {N} in {FREEZE}, and versions[{version!r}] "
                        f"pins no board_export_version {N!r} either (the pair ({version!r}, {N!r}) is in neither map)")
    elif board_exports[N].get("catalog") != version:
        problems.append(f"(d) board_exports[{N}] catalog {board_exports[N].get('catalog')!r} != {version!r}, and "
                        f"versions[{version!r}] pins no board_export_version {N!r} either (the pair ({version!r}, "
                        f"{N!r}) is in neither map)")
    else:
        b_files = sorted((board_golden / N).glob("*.board.export"))
        if not b_files:
            problems.append(f"(d) no board golden for export version {N} (a freeze needs a board golden)")
        b_digests = {stem: hashlib.sha256(p.read_bytes()).hexdigest() for p in b_files if (stem := _board_stem(p))}
        if b_digests != (board_exports[N].get("golden") or {}):
            problems.append(f"(c) board goldens for export version {N} differ from the digests pinned in {FREEZE}")
        for p in b_files:
            stem = _board_stem(p)
            if stem not in FIXTURES:
                problems.append(f"(a) {stem}: no committed fixture of that name")
            elif board_export is not None and board_export(stem) != p.read_bytes():
                problems.append(f"(a) {stem}: the board export differs from its golden file "
                                "(a statistic moved without a bump)")

    return sorted(problems)


def _git(*args: str) -> str | None:
    done = subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, encoding="utf-8", timeout=60,
                          check=False)
    return done.stdout if done.returncode == 0 else None


def merge_base_freeze() -> dict:
    """bench/catalog-freeze.yaml at the merge base with HB_FREEZE_BASE (default main), read-only; HEAD when there is no
    such ref (a shallow CI checkout); {} when the file did not exist there."""
    ref = os.environ.get("HB_FREEZE_BASE", "main")
    base = (_git("merge-base", "HEAD", ref) or "HEAD").strip()
    text = _git("show", f"{base}:{FREEZE}")
    return (yaml.safe_load(text) or {}) if text else {}


# --- the control on this repository --------------------------------------------------------------------------------


def test_the_current_catalog_passes_the_us4_control(tmp_path, capsys):
    root = make_root(tmp_path, release=False)  # the real catalog byte for byte, and X1; bench/rubrics/ as well
    if (ROOT / "bench" / "rubrics").is_dir():
        shutil.copytree(ROOT / "bench" / "rubrics", root / "bench" / "rubrics")
    assert runner.catalog_hash(root) == runner.catalog_hash(ROOT)
    freeze = config.load_yaml(ROOT / FREEZE) if (ROOT / FREEZE).is_file() else {}
    got = us4_problems(root, GOLDEN, freeze, merge_base_freeze(), lambda name: graded_export(root, name, tmp_path),
                       lambda name: graded_board_export(root, name, tmp_path))
    assert got == []
    version = str(config.load_yaml(ROOT / "bench" / "metrics.yaml")["version"])
    out = capsys.readouterr().out
    assert (PROBE in out) == version.endswith(".dev")  # the exemption is visible, and only for a probe
    entry = (freeze.get("versions") or {}).get(version) or {}
    # 0.4 was frozen before boards existed: the missing pin is printed, and only then
    assert (BOARD_EXEMPT in out) == (not version.endswith(".dev") and "board_golden" not in entry)


# --- red first: each violation fails the control (TA 5, TA re-review 6) -------------------------------------------


@pytest.fixture
def frozen(tmp_path):
    """A root whose catalog is released as 9.1, with views and board goldens and a freeze record pinning both.

    9.0 has no `board_golden`: it stands for a version frozen before boards existed. 9.1 pins both.
    """
    root = make_root(tmp_path)
    set_catalog_version(root, "9.1")
    golden = tmp_path / "golden"
    (golden / "9.1").mkdir(parents=True)
    N = str(getattr(board, "EXPORT_VERSION", 1))
    board_golden = tmp_path / "board" / N
    board_golden.mkdir(parents=True)
    pins, board_pins = {}, {}
    for name in FIXTURES:
        data = graded_export(root, name, tmp_path / "freeze")
        (golden / "9.1" / f"{name}.export").write_bytes(data)
        pins[name] = hashlib.sha256(data).hexdigest()
        board_data = graded_board_export(root, name, tmp_path / "freeze-board")
        (golden / "9.1" / f"{name}.board.export").write_bytes(board_data)
        (board_golden / f"{name}.board.export").write_bytes(board_data)
        board_pins[name] = hashlib.sha256(board_data).hexdigest()
    freeze = {"schema": "bench-catalog-freeze/1",
              "versions": {"9.0": {"catalog_hash": "0" * 64, "golden": {}},
                           "9.1": {"catalog_hash": runner.catalog_hash(root), "golden": pins, "board_golden": board_pins}},
              "board_exports": {"1": {"catalog": "0.5", "golden": board_pins},
                                N: {"catalog": "9.1", "golden": board_pins}}}
    return root, golden, freeze


def problems(frozen, tmp_path, base: dict | None = None, freeze: dict | None = None) -> list[str]:
    root, golden, pinned = frozen
    freeze = freeze or pinned
    return us4_problems(root, golden, freeze, pinned if base is None else base,
                        lambda name: graded_export(root, name, tmp_path),
                        lambda name: graded_board_export(root, name, tmp_path))


def test_a_frozen_catalog_with_unchanged_scores_passes(frozen, tmp_path):
    assert problems(frozen, tmp_path) == []


def test_a_normaliser_change_alone_leaves_the_control_green_and_extraction_id_out_of_the_export(frozen, tmp_path, monkeypatch):
    """R-86 (C): extraction_id is provenance, like grader_build, not a result -- a normaliser fix moves nothing
    the export carries, and the field itself is not in the export's cells."""
    monkeypatch.setattr(normalize, "extraction_id", lambda: "e" * 64)
    assert problems(frozen, tmp_path) == []
    root, _, _ = frozen
    export = graded_export(root, "heads", tmp_path)
    assert "extraction_id" not in json.loads(export)["cells"][0]


def test_a_grader_change_without_a_bump_is_red_through_a(frozen, tmp_path, monkeypatch):
    real = runner.GRADERS["correctness"]

    def changed(inp):  # a changed grader constant: cell a's partial credit moves
        out = dict(real(inp))
        if inp.cell["cell_id"] == "a":
            out["partial_credit"] = Score(Decimal("0.5000"), None)
        return out

    monkeypatch.setitem(runner.GRADERS, "correctness", changed)
    # partial_credit feeds the correctness area, so the gated composite moves too: both goldens catch it
    assert problems(frozen, tmp_path) == sorted(
        [f"(a) {name}: the export differs from its golden file (a score or reason moved without a bump)"
         for name in FIXTURES]
        + [f"(a) {name}: the board export differs from its golden file (a statistic moved without a bump)"
           for name in FIXTURES])


def test_a_weight_changed_without_a_bump_is_red_through_b(frozen, tmp_path):
    root, _, freeze = frozen
    path = root / "bench" / "metrics.yaml"
    path.write_text(path.read_text(encoding="utf-8").replace("kind: score, weight: 1, scale: 6", "kind: score, weight: 2, scale: 6"),
                    encoding="utf-8")
    assert problems(frozen, tmp_path) == [  # the export does not carry weights, so only the hash sees it
        (f"(b) catalog_hash {runner.catalog_hash(root)} != {freeze['versions']['9.1']['catalog_hash']} pinned for 9.1: a weight, "
         "rubric or definition changed without a version bump")]


def test_a_rubric_added_without_a_bump_is_red_through_b(frozen, tmp_path):
    root, _, _ = frozen
    (root / "bench" / "rubrics").mkdir()
    (root / "bench" / "rubrics" / "adr_quality.md").write_text("# rubric\n", encoding="utf-8")
    assert [p[:4] for p in problems(frozen, tmp_path)] == ["(b) "]


def test_a_rewritten_golden_file_is_red_through_c(frozen, tmp_path):
    _, golden, _ = frozen
    path = golden / "9.1" / "heads.export"
    path.write_bytes(path.read_bytes() + b" ")
    assert problems(frozen, tmp_path) == [
        "(a) heads: the export differs from its golden file (a score or reason moved without a bump)",
        f"(c) golden exports for 9.1 differ from the digests pinned in {FREEZE}"]


def test_a_released_version_with_no_golden_export_is_red_through_d(frozen, tmp_path):
    _, golden, freeze = frozen
    for path in (golden / "9.1").glob("*.export"):  # the views goldens only; the board files stay
        if not path.name.endswith(".board.export"):
            path.unlink()
    freeze["versions"]["9.1"]["golden"] = {}
    assert problems(frozen, tmp_path) == ["(d) no golden export for 9.1 (a freeze needs a golden export)"]


def test_a_released_version_with_no_freeze_entry_is_red_through_b(frozen, tmp_path):
    _, _, freeze = frozen
    del freeze["versions"]["9.1"]
    assert problems(frozen, tmp_path, base={}) == [f"(b) no catalog_hash pinned for 9.1 in {FREEZE}"]


def test_an_edited_or_removed_freeze_entry_is_red_through_e(frozen, tmp_path):
    _, _, base = frozen
    b_exp = base.get("board_exports", {})
    edited = {"versions": {**base["versions"], "9.0": {"catalog_hash": "1" * 64, "golden": {}}}, "board_exports": b_exp}
    removed = {"versions": {"9.1": base["versions"]["9.1"]}, "board_exports": b_exp}
    appended = {"versions": {**base["versions"], "9.2": {"catalog_hash": "2" * 64, "golden": {}}}, "board_exports": b_exp}
    assert problems(frozen, tmp_path, base=base, freeze=edited) == [f"(e) {FREEZE} entry '9.0' was changed or removed since the merge base"]
    assert problems(frozen, tmp_path, base=base, freeze=removed) == [f"(e) {FREEZE} entry '9.0' was changed or removed since the merge base"]
    assert problems(frozen, tmp_path, base=base, freeze=appended) == []  # append-only: a new version is fine


def test_a_board_export_that_differs_is_red_through_a(frozen, tmp_path, monkeypatch):
    """(a) board: the views export is unchanged, so only the board golden sees a moved statistic."""
    real = board.build

    def shifted(view, cat, params=None):
        built = real(view, cat, params)
        if built.rows:
            built.rows[0].n_cells += 1
        return built

    monkeypatch.setattr(board, "build", shifted)
    assert problems(frozen, tmp_path) == [
        f"(a) {name}: the board export differs from its golden file (a statistic moved without a bump)"
        for name in sorted(FIXTURES)]


def test_board_digests_that_differ_from_the_pins_are_red_through_c(frozen, tmp_path):
    """(c) board: rewriting a board golden moves its digest while the views pin still matches."""
    _, golden, _ = frozen
    path = golden / "9.1" / "heads.board.export"
    path.write_bytes(path.read_bytes() + b" ")
    assert problems(frozen, tmp_path) == [
        f"(c) board goldens for 9.1 differ from the digests pinned in {FREEZE}"]


def test_a_released_version_frozen_with_no_board_golden_is_red_through_d(frozen, tmp_path):
    """(d) board: a version frozen after boards existed (`board_golden` is present) with nothing pinned."""
    _, golden, freeze = frozen
    for path in (golden / "9.1").glob("*.board.export"):
        path.unlink()
    freeze["versions"]["9.1"]["board_golden"] = {}
    assert problems(frozen, tmp_path) == ["(d) no board golden for 9.1 (a freeze after board.export needs a board golden)"]


def test_an_edited_board_golden_pin_is_red_through_e(frozen, tmp_path):
    """(e) covers board_golden on its own: the views pin and the hash stay, and only that map changes."""
    _, _, pinned = frozen
    b_exp = pinned.get("board_exports", {})
    base = {"versions": {v: dict(entry) for v, entry in pinned["versions"].items()}, "board_exports": b_exp}
    edited = {"versions": {v: dict(entry) for v, entry in base["versions"].items()}, "board_exports": b_exp}
    edited["versions"]["9.0"] = {**edited["versions"]["9.0"], "board_golden": {"heads": "b" * 64}}
    assert problems(frozen, tmp_path, base=base, freeze=edited) == [
        f"(e) {FREEZE} entry '9.0' was changed or removed since the merge base"]


def test_board_export_differing_under_current_export_version_is_red_through_a(frozen, tmp_path):
    """(a) a board export differing from its golden under the current EXPORT_VERSION fails."""
    _, golden, _ = frozen
    N = str(getattr(board, "EXPORT_VERSION", 1))
    path = golden.parent / "board" / N / "heads.board.export"
    path.write_bytes(path.read_bytes() + b" ")
    assert problems(frozen, tmp_path) == [
        "(a) heads: the board export differs from its golden file (a statistic moved without a bump)",
        f"(c) board goldens for export version {N} differ from the digests pinned in {FREEZE}",
    ]


def test_board_export_golden_digests_differing_from_board_exports_pin_is_red_through_c(frozen, tmp_path):
    """(c) golden digests must equal board_exports[N].golden."""
    _, _, freeze = frozen
    N = str(getattr(board, "EXPORT_VERSION", 1))
    freeze["board_exports"][N]["golden"] = {name: "0" * 64 for name in FIXTURES}
    assert problems(frozen, tmp_path) == [
        f"(c) board goldens for export version {N} differ from the digests pinned in {FREEZE}",
    ]


def test_absent_board_exports_entry_or_catalog_mismatch_is_red_through_d(frozen, tmp_path):
    """(d) fails when board_exports[N] is absent or its catalog is not the released version."""
    _, _, freeze = frozen
    N = str(getattr(board, "EXPORT_VERSION", 1))
    # absent entry
    del freeze["board_exports"][N]
    assert problems(frozen, tmp_path) == [
        (f"(d) no board_exports entry for export version {N} in {FREEZE}, and versions['9.1'] pins no "
         f"board_export_version {N!r} either (the pair ('9.1', {N!r}) is in neither map)"),
    ]
    # catalog mismatch
    freeze["board_exports"][N] = {"catalog": "9.9", "golden": {}}
    assert problems(frozen, tmp_path) == [
        f"(d) board_exports[{N}] catalog '9.9' != '9.1', and versions['9.1'] pins no board_export_version {N!r} "
        "either (the pair ('9.1', " + repr(N) + ") is in neither map)",
    ]


# --- R-86: a catalog bump under an unchanged EXPORT_VERSION pins the pair via board_export_version, not board_exports[N] --


@pytest.fixture
def frozen_bump(tmp_path):
    """9.2, released under the SAME export version N that 9.1 (the `frozen` fixture) already occupies in
    board_exports. R-86: a catalog bump records `board_export_version: N` in `versions[v]` itself (append-only;
    board_exports[N] is untouched), and its pair golden is the per-version directory already pinned by `board_golden`.
    """
    root = make_root(tmp_path)
    set_catalog_version(root, "9.2")
    golden = tmp_path / "golden"
    (golden / "9.2").mkdir(parents=True)
    N = str(getattr(board, "EXPORT_VERSION", 1))
    pins, board_pins = {}, {}
    for name in FIXTURES:
        data = graded_export(root, name, tmp_path / "freeze")
        (golden / "9.2" / f"{name}.export").write_bytes(data)
        pins[name] = hashlib.sha256(data).hexdigest()
        board_data = graded_board_export(root, name, tmp_path / "freeze-board")
        (golden / "9.2" / f"{name}.board.export").write_bytes(board_data)
        board_pins[name] = hashlib.sha256(board_data).hexdigest()
    freeze = {"schema": "bench-catalog-freeze/1",
              "versions": {"9.2": {"catalog_hash": runner.catalog_hash(root), "golden": pins,
                                   "board_golden": board_pins, "board_export_version": N}},
              # unrelated to 9.2; append-only, left exactly as some earlier catalog pinned it
              "board_exports": {N: {"catalog": "9.1", "golden": {name: "0" * 64 for name in FIXTURES}}}}
    return root, golden, freeze


def _bump_problems(frozen_bump, tmp_path, freeze: dict) -> list[str]:
    root, golden, _ = frozen_bump
    return us4_problems(root, golden, freeze, freeze, lambda name: graded_export(root, name, tmp_path),
                        lambda name: graded_board_export(root, name, tmp_path))


def test_a_catalog_bump_under_an_unchanged_export_version_pins_via_board_export_version_and_passes(frozen_bump, tmp_path):
    _, _, freeze = frozen_bump
    assert _bump_problems(frozen_bump, tmp_path, freeze) == []


def test_a_catalog_bump_with_no_board_export_version_fails_d_naming_both_maps(frozen_bump, tmp_path):
    _, _, freeze = frozen_bump
    N = str(getattr(board, "EXPORT_VERSION", 1))
    del freeze["versions"]["9.2"]["board_export_version"]
    got = _bump_problems(frozen_bump, tmp_path, freeze)
    assert got == [
        f"(d) board_exports[{N}] catalog '9.1' != '9.2', and versions['9.2'] pins no board_export_version {N!r} "
        "either (the pair ('9.2', " + repr(N) + ") is in neither map)",
    ]
    assert "board_exports" in got[0] and "board_export_version" in got[0]  # names both maps


def test_board_exports_append_only_and_v1_equals_v05_golden_is_red_through_e(frozen, tmp_path):
    """(e) board_exports entries are append-only against the merge base, and board_exports['1'].golden must equal versions['0.5'].board_golden."""
    _, _, pinned = frozen
    N = str(getattr(board, "EXPORT_VERSION", 1))
    base = {
        "versions": dict(pinned["versions"]),
        "board_exports": {
            "0": {"catalog": "9.0", "golden": {"heads": "0" * 64}},
            "1": dict(pinned["board_exports"]["1"]),
            N: dict(pinned["board_exports"][N]),
        },
    }
    # entry '0' changed
    edited = {
        "versions": dict(base["versions"]),
        "board_exports": {
            "0": {"catalog": "9.0", "golden": {"heads": "1" * 64}},
            "1": dict(pinned["board_exports"]["1"]),
            N: dict(pinned["board_exports"][N]),
        },
    }
    assert problems(frozen, tmp_path, base=base, freeze=edited) == [
        f"(e) {FREEZE} board_exports entry '0' was changed or removed since the merge base",
    ]
    # entry '0' removed
    removed = {
        "versions": dict(base["versions"]),
        "board_exports": {
            "1": dict(pinned["board_exports"]["1"]),
            N: dict(pinned["board_exports"][N]),
        },
    }
    assert problems(frozen, tmp_path, base=base, freeze=removed) == [
        f"(e) {FREEZE} board_exports entry '0' was changed or removed since the merge base",
    ]
    # board_exports['1'].golden != versions['0.5'].board_golden
    mismatch = {
        "versions": {**base["versions"], "0.5": {"catalog_hash": "a" * 64, "golden": {}, "board_golden": {"heads": "diff" * 8}}},
        "board_exports": dict(base["board_exports"]),
    }
    assert problems(frozen, tmp_path, base=mismatch, freeze=mismatch) == [
        f"(e) board_exports['1'].golden != versions['0.5'].board_golden in {FREEZE}",
    ]


def test_a_version_frozen_before_boards_is_exempt_and_says_so(frozen, tmp_path, capsys):
    """An entry with no board_golden (0.4's shape) skips the board check, and the skip is printed."""
    root, golden, freeze = frozen
    set_catalog_version(root, "9.0")
    (golden / "9.0").mkdir()
    pins = {}
    for name in FIXTURES:
        data = graded_export(root, name, tmp_path / "pre-board")
        (golden / "9.0" / f"{name}.export").write_bytes(data)
        pins[name] = hashlib.sha256(data).hexdigest()
    freeze["versions"]["9.0"] = {"catalog_hash": runner.catalog_hash(root), "golden": pins}
    (golden / "9.0" / "heads.board.export").write_bytes(b"not a board")  # ignored: this version predates boards
    assert problems(frozen, tmp_path) == []
    assert capsys.readouterr().out.strip().splitlines() == [BOARD_EXEMPT]


def test_a_dev_version_is_exempt_and_says_so(frozen, tmp_path, capsys):
    root, _, _ = frozen
    set_catalog_version(root, "9.2.dev")
    path = root / "bench" / "metrics.yaml"
    path.write_text(path.read_text(encoding="utf-8").replace("kind: score, weight: 1, scale: 6", "kind: score, weight: 2, scale: 6"),
                    encoding="utf-8")  # no pin, no golden, a moved weight: all exempt for a probe
    assert problems(frozen, tmp_path) == []
    assert capsys.readouterr().out == f"{PROBE}\n"


# --- catalog 0.7.dev: the eleven property metrics (X-G1, W1-G T-C1..T-C4, T-C6; W0 §7, R-95, R-97) -----------------

# scale None: the key is absent (W0 §7 "int" / "int 0/1"). property None: untagged.
# Anchors are W1-G §4.1. hallucinated_symbol_errors' note is R-97 condition 3, not the design's
# "build-log errors" sentence. Floats are what YAML loads for a scale-4 anchor (0.0000 -> 0.0).
ELEVEN = (
    {"id": "property_check_pass", "area": "correctness", "kind": "score", "better": "higher",
     "scale": None, "property": None, "anchor": [0, 1],
     "anchor_note": "convention: binary indicator in [0, 1]"},
    {"id": "exploit_probes_blocked", "area": "correctness", "kind": "score", "better": "higher",
     "scale": 4, "property": "security", "anchor": [0.0, 1.0],
     "anchor_note": "spec docs/specs/enterprise-evaluation.md:244"},
    {"id": "fault_suite_pass", "area": "correctness", "kind": "score", "better": "higher",
     "scale": 4, "property": "resilience", "anchor": [0.0, 1.0],
     "anchor_note": "spec docs/specs/enterprise-evaluation.md:256"},
    {"id": "idempotency_violations", "area": "correctness", "kind": "score", "better": "lower",
     "scale": None, "property": "resilience", "anchor": [5, 0],
     "anchor_note": ("convention: cap at 5 duplicated effects; provisional until the E4 "
                     "discrimination records give the naive solution's measured count; 0 is clean")},
    {"id": "turn1_tests_pass", "area": "correctness", "kind": "score", "better": "higher",
     "scale": None, "property": "rework", "anchor": [0, 1],
     "anchor_note": "convention: binary indicator in [0, 1]"},
    {"id": "rework_ratio", "area": "rigor", "kind": "score", "better": "lower",
     "scale": 4, "property": "rework", "anchor": [1.0, 0.0],
     "anchor_note": "spec docs/specs/enterprise-evaluation.md:263"},
    {"id": "hallucinated_symbol_errors", "area": "rigor", "kind": "score", "better": "lower",
     "scale": None, "property": "no-guessing", "anchor": [5, 0],
     "anchor_note": ("convention: cap at 5 unresolved vendored-API references in the final tree; "
                     "provisional until the E4 discrimination records; 0 is clean")},
    {"id": "verified_before_use", "area": "rigor", "kind": "score", "better": "higher",
     "scale": None, "property": "no-guessing", "anchor": [0, 1],
     "anchor_note": "spec docs/specs/enterprise-evaluation.md:270"},
    {"id": "size_vs_reference", "area": "rigor", "kind": "score", "better": "lower",
     "scale": 4, "property": "simplicity", "anchor": [3.0, 1.0],
     "anchor_note": ("convention: 3x the reference's added lines is the worst, at or under the "
                     "reference is the best (EV-6 :274 defines the ratio, not a range); "
                     "provisional until the E4 discrimination records")},
    {"id": "new_abstractions", "area": "rigor", "kind": "score", "better": "lower",
     "scale": None, "property": "simplicity", "anchor": [4, 0],
     "anchor_note": ("convention: cap at 4 new types or interfaces; provisional until the E4 "
                     "discrimination records; 0 is none (EV-6 :275)")},
    {"id": "new_dependencies", "area": "rigor", "kind": "score", "better": "lower",
     "scale": None, "property": "simplicity", "anchor": [2, 0],
     "anchor_note": ("convention: cap at 2 new dependencies; provisional until the E4 "
                     "discrimination records; 0 is none (EV-6 :276)")},
)
FREEZE_06_COMMIT = "d6dda42d"  # the 0.6 freeze; catalog_hash reads metrics.yaml and bench/rubrics/
HSE_PHRASE = "unresolved vendored-API references in the final tree"
HSE_RETIRED = "build-log errors"


def _index(catalog: dict) -> dict[str, tuple[str, dict]]:
    found: dict[str, tuple[str, dict]] = {}
    for area_id, area in (catalog.get("areas") or {}).items():
        for metric in area.get("metrics") or []:
            found[metric["id"]] = (area_id, metric)
    return found


def _metric(catalog: dict, metric_id: str) -> dict:
    return _index(catalog)[metric_id][1]


def _validate(catalog: dict) -> list[str]:
    problems = config.Problems()
    config.validate_metrics(catalog, problems, config.grader_modules(ROOT), root=ROOT)
    return problems.items


def _r79_problems(metric: dict) -> list[str]:
    """R-79 form and anchor direction. The two faults are separate: a blank note is not a reversed anchor."""
    problems: list[str] = []
    note = metric.get("anchor_note")
    if not isinstance(note, str) or not note.strip():
        problems.append("anchor_note blank")
    elif not note.startswith(("spec ", "measured ", "convention: ")):
        problems.append("anchor_note is not an R-79 form")
    anchor = metric.get("anchor")
    better = metric.get("better")
    if not isinstance(anchor, (list, tuple)) or len(anchor) != 2:
        problems.append("anchor must be [worst, best]")
    else:
        worst, best = anchor
        if worst == best:
            problems.append("anchor worst == best")
        elif (better == "higher" and worst > best) or (better == "lower" and worst < best):
            problems.append("anchor direction contradicts better")
    return problems


def _06_definition_problems(archived: dict, current: dict) -> list[str]:
    """0.6 entries must match the current catalog. pass_at_1 may gain also_graded_by: [formal] and nothing else."""
    old, new = _index(archived), _index(current)
    problems: list[str] = []
    for metric_id, (_, previous) in old.items():
        if metric_id not in new:
            problems.append(f"{metric_id} is missing from the current catalog")
            continue
        current_metric = dict(new[metric_id][1])
        if metric_id == "pass_at_1":
            extra = current_metric.pop("also_graded_by", None)
            if extra is not None and extra != ["formal"]:
                problems.append(f"pass_at_1 also_graded_by {extra!r} is not [formal]")
        if dict(previous) != current_metric:
            problems.append(f"{metric_id} changed beyond pass_at_1's also_graded_by key")
    return problems


def _root06(tmp: Path) -> Path:
    """git archive of the 0.6 freeze commit. An unreachable commit fails; it never skips."""
    done = subprocess.run(
        ["git", "archive", FREEZE_06_COMMIT, "bench/metrics.yaml", "bench/rubrics"],
        cwd=ROOT, capture_output=True, timeout=60, check=False)
    assert done.returncode == 0, (
        f"0.6 freeze commit {FREEZE_06_COMMIT} is not reachable (git archive failed; "
        f"a shallow checkout fails here and never skips): {done.stderr.decode('utf-8', errors='replace')}")
    dest = tmp / "root06"
    dest.mkdir(parents=True)
    with tarfile.open(fileobj=io.BytesIO(done.stdout), mode="r:") as archive:
        archive.extractall(dest, filter="data")
    return dest


def test_catalog_has_the_eleven_property_metrics_with_the_fixed_fields():
    catalog = config.load_yaml(ROOT / "bench" / "metrics.yaml")
    found = _index(catalog)
    missing = sorted(row["id"] for row in ELEVEN if row["id"] not in found)
    assert missing == []  # red on 0.6: the catalog holds none of the eleven ids
    assert catalog["version"] == "0.7"  # released at X-G3's join (R-86 c3, 2c4e2204)
    for row in ELEVEN:
        area, metric = found[row["id"]]
        assert area == row["area"], row["id"]
        assert metric["kind"] == row["kind"], row["id"]
        assert metric["better"] == row["better"], row["id"]
        assert metric.get("scale") == row["scale"], row["id"]
        assert metric.get("property") == row["property"], row["id"]
        assert metric["grader"] == "property", row["id"]
        assert metric["weight"] == 0, row["id"]
        assert metric["source"] == ["D"], row["id"]
    assert _validate(catalog) == []


def test_every_property_metric_anchor_is_in_a_permitted_r79_form_and_points_the_right_way():
    # Red fixtures first (floor 2): a blank note and a reversed anchor are different faults.
    blank = _r79_problems({"better": "higher", "anchor": [0, 1], "anchor_note": ""})
    reversed_anchor = _r79_problems(
        {"better": "higher", "anchor": [1, 0], "anchor_note": "convention: binary indicator in [0, 1]"})
    assert any("blank" in item for item in blank)
    assert not any("direction" in item for item in blank)
    assert any("direction" in item for item in reversed_anchor)
    assert not any("blank" in item for item in reversed_anchor)
    catalog = config.load_yaml(ROOT / "bench" / "metrics.yaml")
    found = _index(catalog)
    for row in ELEVEN:
        assert row["id"] in found, row["id"]  # red on 0.6: same absence as T-C1
        _, metric = found[row["id"]]
        assert _r79_problems(metric) == [], row["id"]
        assert metric.get("anchor") == row["anchor"], row["id"]
        assert metric.get("anchor_note") == row["anchor_note"], row["id"]
        if row["id"] == "hallucinated_symbol_errors":
            note = metric.get("anchor_note") or ""
            assert HSE_RETIRED not in note
            assert HSE_PHRASE in note


def test_the_06_definitions_read_from_the_freeze_commit_hash_to_the_pin_and_are_unchanged_in_07_except_pass_at_1(tmp_path):
    root06 = _root06(tmp_path)
    pinned = config.load_yaml(ROOT / FREEZE)["versions"]["0.6"]["catalog_hash"]
    assert runner.catalog_hash(root06) == pinned
    archived = config.load_yaml(root06 / "bench" / "metrics.yaml")
    current = config.load_yaml(ROOT / "bench" / "metrics.yaml")
    assert _06_definition_problems(archived, current) == []
    # The allowed delta is only that one key. A copy that adds it stays clean; a real edit does not.
    allowed = copy.deepcopy(current)
    _metric(allowed, "pass_at_1")["also_graded_by"] = ["formal"]
    assert _06_definition_problems(archived, allowed) == []
    flipped = copy.deepcopy(current)
    entry = _metric(flipped, "partial_credit")
    entry["better"] = "lower" if entry["better"] == "higher" else "higher"
    assert _06_definition_problems(archived, flipped)
    weighted = copy.deepcopy(current)
    _metric(weighted, "pass_at_1")["weight"] = 1
    assert _06_definition_problems(archived, weighted)


@pytest.mark.xfail(strict=True, reason="X-A1 owns the property-tag check; X-F owns STRATEGIES. Unread until then.")
def test_a_property_tag_outside_property_names_is_refused_and_property_names_match_the_strategy_keys():
    catalog = config.load_yaml(ROOT / "bench" / "metrics.yaml")
    bad = copy.deepcopy(catalog)
    _metric(bad, "partial_credit")["property"] = "no_guessing"
    added = [item for item in _validate(bad) if item not in _validate(catalog)]
    assert added, "property tag no_guessing must be refused"
    names = getattr(config, "PROPERTY_NAMES", None)
    strategies = getattr(grade_property, "STRATEGIES", None)
    assert names is not None, "config.PROPERTY_NAMES"
    assert strategies is not None, "grade.property.STRATEGIES"
    assert list(names) == list(strategies.keys())


def test_an_also_graded_by_name_that_is_unknown_equal_to_the_grader_or_repeated_is_refused():
    catalog = config.load_yaml(ROOT / "bench" / "metrics.yaml")
    cases = {"unknown": ["formla"], "equal to grader": ["correctness"], "repeated": ["formal", "formal"]}
    for name, value in cases.items():
        bad = copy.deepcopy(catalog)
        _metric(bad, "pass_at_1")["also_graded_by"] = value
        added = [item for item in _validate(bad) if item not in _validate(catalog)]
        assert added, f"{name}: also_graded_by {value!r} must be refused"


def _foreign_catalog_fields(obj: object, version: str, key: str | None = None) -> list[str]:
    """Strings other than a ``catalog_version`` field that still name the current catalog."""
    if isinstance(obj, dict):
        found: list[str] = []
        for child_key, child in obj.items():
            found.extend(_foreign_catalog_fields(child, version, str(child_key)))
        return found
    if isinstance(obj, list):
        found = []
        for child in obj:
            found.extend(_foreign_catalog_fields(child, version, key))
        return found
    if isinstance(obj, str) and version and version in obj and key != "catalog_version":
        return [key or "<root>"]
    return []


def _retarget_catalog_version(obj: object) -> None:
    """The one allowed substitution: a ``catalog_version`` of ``0.7...`` becomes ``0.6``."""
    if isinstance(obj, dict):
        for child_key, child in list(obj.items()):
            if child_key == "catalog_version" and isinstance(child, str) and child.startswith("0.7"):
                obj[child_key] = "0.6"
            else:
                _retarget_catalog_version(child)
    elif isinstance(obj, list):
        for child in obj:
            _retarget_catalog_version(child)


def _us4_regrade(name: str, surface: str, produced: bytes, golden_path: Path, version: str) -> list[str]:
    """Step 3 for one surface. A field other than ``catalog_version`` that names the catalog is reported as-is."""
    label = f"(3) {name}: the {surface} export differs from the 0.6 golden"
    try:
        obj = json.loads(produced)
    except json.JSONDecodeError:
        return [label]
    extras = _foreign_catalog_fields(obj, version)
    if extras:
        return [f"(3) {name}: the {surface} export names the catalog outside catalog_version: {extras[0]}"]
    if isinstance(obj, dict):
        _retarget_catalog_version(obj)
        produced = ledger.canonical(obj)
    golden = golden_path.read_bytes() if golden_path.is_file() else b""
    if produced != golden:
        return [label]
    return []


def cross_version_problems(root: Path, root06: Path, golden06: Path, freeze: dict,
                           export: Callable[[str], bytes],
                           board_export: Callable[[str], bytes]) -> list[str]:
    """US-4 control 1 (W1-G section 4.5). All four steps; every problem is kept."""
    problems: list[str] = []
    pinned = (freeze.get("versions") or {}).get("0.6") or {}
    view_pins = pinned.get("golden") or {}
    board_pins = pinned.get("board_golden") or {}
    for path in sorted(golden06.glob("*.export")):
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        board_name = _board_stem(path)
        if board_name is None:
            if view_pins.get(path.stem) != digest:
                problems.append(f"(1) pin mismatch for views golden {path.stem}")
        elif board_pins.get(board_name) != digest:
            problems.append(f"(1) pin mismatch for board golden {board_name}")
    got = runner.catalog_hash(root06)
    want = pinned.get("catalog_hash")
    if got != want:
        problems.append(f"(2) catalog_hash {got} != {want}")
    archived = config.load_yaml(root06 / "bench" / "metrics.yaml")
    current = config.load_yaml(root / "bench" / "metrics.yaml")
    problems.extend(f"(2) {item}" for item in _06_definition_problems(archived, current))
    version = str(current.get("version") or "")
    for name in FIXTURES:
        views_bytes = export(name)
        board_bytes = board_export(name)
        problems.extend(_us4_regrade(name, "views", views_bytes, golden06 / f"{name}.export", version))
        problems.extend(_us4_regrade(name, "board", board_bytes, golden06 / f"{name}.board.export", version))
        for metric_id in (row["id"] for row in ELEVEN):
            token = metric_id.encode("utf-8")
            if token in views_bytes:
                problems.append(f"(4) {name}: {metric_id} leaked into the views export")
            if token in board_bytes:
                problems.append(f"(4) {name}: {metric_id} leaked into the board export")
    return problems


def _us4_root(tmp: Path) -> Path:
    """The real 0.7.dev catalog and X1 task, rubrics included, so catalog_hash matches the tree."""
    root = make_root(tmp, release=False)
    rubrics = ROOT / "bench" / "rubrics"
    if rubrics.is_dir():
        shutil.copytree(rubrics, root / "bench" / "rubrics")
    return root


def _cross(root: Path, root06: Path, golden06: Path, tmp: Path, export=None, board_export=None) -> list[str]:
    freeze = config.load_yaml(ROOT / FREEZE)
    return cross_version_problems(
        root, root06, golden06, freeze,
        export or (lambda name: graded_export(root, name, tmp)),
        board_export or (lambda name: graded_board_export(root, name, tmp)))


def test_07_regrades_the_x1_fixtures_to_the_06_goldens_on_both_surfaces(tmp_path):  # T-U1, green on arrival
    assert _cross(_us4_root(tmp_path), _root06(tmp_path), GOLDEN / "0.6", tmp_path) == []


def test_cross_version_problems_is_red_for_a_moved_06_metric(tmp_path, monkeypatch):  # T-U1a
    root = _us4_root(tmp_path)
    real = runner.GRADERS["correctness"]

    def changed(inp):
        out = dict(real(inp))
        if inp.cell["cell_id"] == "a":
            out["partial_credit"] = Score(Decimal("0.5000"), None)
        return out

    monkeypatch.setitem(runner.GRADERS, "correctness", changed)
    problems = _cross(root, _root06(tmp_path), GOLDEN / "0.6", tmp_path)
    assert problems
    assert any("views" in item and "c44dd2b-no-heads" in item for item in problems)


def test_cross_version_problems_is_red_for_a_weight_change(tmp_path):  # T-U1b
    root = _us4_root(tmp_path)
    path = root / "bench" / "metrics.yaml"
    text = path.read_text(encoding="utf-8")
    old = "id: partial_credit,          source: [D], better: higher, grader: correctness, kind: score, weight: 1"
    assert old in text
    path.write_text(text.replace(old, old.replace("weight: 1", "weight: 2"), 1), encoding="utf-8")
    problems = _cross(root, _root06(tmp_path), GOLDEN / "0.6", tmp_path)
    assert problems
    assert any("board" in item for item in problems)


def test_cross_version_problems_is_red_for_an_edited_or_regenerated_06_golden(tmp_path):  # T-U1c
    root = _us4_root(tmp_path)
    root06 = _root06(tmp_path)
    edited = tmp_path / "edited-golden"
    shutil.copytree(GOLDEN / "0.6", edited)
    target = edited / "heads.export"
    target.write_bytes(target.read_bytes() + b" ")
    edited_problems = _cross(root, root06, edited, tmp_path)
    assert edited_problems
    assert any("pin" in item for item in edited_problems)
    regenerated = tmp_path / "regenerated-golden"
    regenerated.mkdir()
    for name in FIXTURES:
        (regenerated / f"{name}.export").write_bytes(graded_export(root, name, tmp_path))
        (regenerated / f"{name}.board.export").write_bytes(graded_board_export(root, name, tmp_path))
    regenerated_problems = _cross(root, root06, regenerated, tmp_path)
    assert regenerated_problems
    assert any("pin" in item for item in regenerated_problems)


def test_cross_version_problems_is_red_for_an_edited_root06(tmp_path):  # T-U1d
    root = _us4_root(tmp_path)
    edited = _root06(tmp_path)
    metrics = edited / "bench" / "metrics.yaml"
    metrics.write_text(metrics.read_text(encoding="utf-8").replace("weight: 1", "weight: 9", 1), encoding="utf-8")
    edited_problems = _cross(root, edited, GOLDEN / "0.6", tmp_path)
    assert edited_problems
    assert any("hash" in item for item in edited_problems)
    with_rubric = _root06(tmp_path / "rubric-case")
    (with_rubric / "bench" / "rubrics").mkdir(parents=True, exist_ok=True)
    (with_rubric / "bench" / "rubrics" / "added.md").write_text("# added\n", encoding="utf-8")
    rubric_problems = _cross(root, with_rubric, GOLDEN / "0.6", tmp_path)
    assert rubric_problems
    assert any("hash" in item for item in rubric_problems)


def test_the_new_metric_ids_are_absent_from_the_x1_exports(tmp_path):  # T-U2
    root = _us4_root(tmp_path)

    def injected(name: str) -> bytes:
        data = json.loads(graded_export(root, name, tmp_path))
        data["cells"][0]["scores"]["exploit_probes_blocked"] = {"value": 1, "reason": None}
        from harness_bench import ledger
        return ledger.canonical(data)

    problems = _cross(root, _root06(tmp_path), GOLDEN / "0.6", tmp_path, export=injected)
    assert problems
    assert any("exploit_probes_blocked" in item for item in problems)


# --- the slow ring: dotnet fixtures run only on the grading host (design: Catalog-version rule 4; seam V-4) ---------


def test_both_selectors_exclude_the_slow_ring():  # TA re-review 1: a command-line -m replaces addopts, so both change
    ini = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["tool"]["pytest"]["ini_options"]
    assert ini["addopts"] == "-m 'not credentials and not slow and not gate and not browser'"
    assert any(m.startswith("slow:") for m in ini["markers"])
    assert any(m.startswith("workstation:") for m in ini["markers"])  # CI has no harness builds or sibling checkouts
    assert any(m.startswith("gate:") for m in ini["markers"])
    assert any(m.startswith("browser:") for m in ini["markers"])  # R-81 DR-R-9: readiness ring only, never CI's offline gate
    ci = [line.strip() for line in (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8").splitlines()]
    pytest_lines = [line for line in ci if "pytest" in line and line.startswith("- run:")]
    # Two jobs run the default ring now (ADR-0013 Amendment 1 s5: windows-latest and macos-latest), each
    # with this exact line -- one per host, byte-identical, never a drifted filter on either.
    assert pytest_lines == [
        '- run: uv run pytest -q -n auto -m "not credentials and not slow and not workstation and not gate and not browser"'] * 2


@pytest.mark.parametrize(("env", "which", "outcome"), [
    ({}, None, "skip: dotnet not required"),
    ({}, "C:/dotnet/dotnet.exe", "skip: dotnet not required"),
    ({"HB_REQUIRE_DOTNET": "1"}, None, "fail: HB_REQUIRE_DOTNET=1 but dotnet is not on PATH"),
    ({"HB_REQUIRE_DOTNET": "1"}, "C:/dotnet/dotnet.exe", "run"),
])
def test_hb_require_dotnet_fails_a_missing_dotnet_and_its_absence_skips(env, which, outcome):
    try:
        dotnet_gate(env, lambda name: which)
        got = "run"
    except pytest.skip.Exception as exc:
        got = f"skip: {exc.msg}"
    except pytest.fail.Exception as exc:
        got = f"fail: {exc.msg}"
    assert got == outcome
