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

import hashlib
import os
import shutil
import subprocess
import tomllib
import uuid
from collections.abc import Callable
from decimal import Decimal
from pathlib import Path

import pytest
import yaml
from archived_runs import ROOT, make_root, set_catalog_version
from slow_ring import dotnet_gate

from harness_bench import board, composites, config, views
from harness_bench.grade import Score, runner

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

    if N not in board_exports:
        problems.append(f"(d) no board_exports entry for export version {N} in {FREEZE}")
    elif board_exports[N].get("catalog") != version:
        problems.append(f"(d) board_exports[{N}] catalog {board_exports[N].get('catalog')!r} != {version!r} (board export catalog must match released version)")
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
        f"(d) no board_exports entry for export version {N} in {FREEZE}",
    ]
    # catalog mismatch
    freeze["board_exports"][N] = {"catalog": "9.9", "golden": {}}
    assert problems(frozen, tmp_path) == [
        f"(d) board_exports[{N}] catalog '9.9' != '9.1' (board export catalog must match released version)",
    ]


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


# --- the slow ring: dotnet fixtures run only on the grading host (design: Catalog-version rule 4; seam V-4) ---------


def test_both_selectors_exclude_the_slow_ring():  # TA re-review 1: a command-line -m replaces addopts, so both change
    ini = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["tool"]["pytest"]["ini_options"]
    assert ini["addopts"] == "-m 'not credentials and not slow and not gate'"
    assert any(m.startswith("slow:") for m in ini["markers"])
    assert any(m.startswith("workstation:") for m in ini["markers"])  # CI has no harness builds or sibling checkouts
    assert any(m.startswith("gate:") for m in ini["markers"])
    ci = [line.strip() for line in (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8").splitlines()]
    assert [line for line in ci if "pytest" in line and line.startswith("- run:")] == [
        '- run: uv run pytest -q -n auto -m "not credentials and not slow and not workstation and not gate"']


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
