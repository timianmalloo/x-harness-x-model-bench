"""Tests for the rework tasks RW1 and RW2 (W1-L rev 2 sections 6 and 15; W1-L Erratum 1; W0 rev 6.6; X-RW).

One parametrised module over the two ids. The base is built through the engine's own `workspace.task_source` (a cached
upstream clone); a test skips when the upstream is unreachable unless `HB_REQUIRE_RW_BASE=1`.

Numbers come from the real measure (`grade/rework.py` over `grade/_changes.py`; the stand-in is deleted, HASH-A).

Directory layout of a solution (assume: W0 section 2 "per-turn overlays"; confirm: X-J2b's overlay builder; breaks if false:
the final tree differs): the turn-1 snapshot is base + `turn-1/`; the final tree is base + `turn-1/` + `turn-2/`, a file in
`turn-2/` replacing the same path from `turn-1/`.
"""

from __future__ import annotations

import ast
import difflib
import functools
import importlib.util
import inspect
import os
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

import pytest
import ring_cache

import harness_bench.grade.property  # noqa: F401  (src: grade.rework imports grade.property first; a direct rework import is circular)
from harness_bench import config, workspace
from harness_bench.grade import _changes, correctness, rework

ROOT = Path(__file__).resolve().parents[1]
SEEDED = ROOT / "tests" / "fixtures" / "property_tasks" / "rw1_seeded_disagreement.json"
VARIANT_NAME = re.compile(r"^[a-z0-9]{1,16}$")
IDS = ("RW1", "RW2")
ROLES = ("reference", "naive", "alt")
CEILING = Decimal("0.3000")

SPEC = {
    "RW1": {
        "repo": "https://github.com/xolox/python-humanfriendly",
        "pin": "6758ac61f906cd8528682003070a57febe4ad3cf",
        "tree": "d25f96a3910d75bd867ee5e000d61d1b7997c402",
        "product": "humanfriendly/__init__.py",
        "test_file": "humanfriendly/tests.py",
        "license_head": "Copyright (c) 2021 Peter Odding",
        "variants": {"ratiohigh", "t1regress", "t2short", "duplicate", "deaddelegate", "padturn1"},
        "stub": ('\n\n_RW_STUB = object()\n\n\ndef format_dollars(amount):\n    return _RW_STUB\n\n\n'
                 'def format_money(amount, currency):\n    return _RW_STUB\n'),
    },
    "RW2": {
        "repo": "https://github.com/dbader/schedule",
        "pin": "82a43db1b938d8fdf60103bd41f329e06c8d3651",
        "tree": "113c0a93af441e26f0d7736ff48c5f1e60e03762",
        "product": "schedule/__init__.py",
        "test_file": "test_schedule.py",
        "license_head": "Copyright (c) 2013 Daniel Bader",
        "variants": {"ratiohigh", "t1regress", "t2short", "nohookorder", "ignorereturn", "padturn1", "duplicate"},
        "stub": ('\n\n_RW_STUB = object()\nScheduler.on_failure = lambda self, callback: _RW_STUB\n'
                 'Job.resume = lambda self: _RW_STUB\nJob.failures = _RW_STUB\n'),
    },
}


def load_path(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_WORK = Path(tempfile.mkdtemp(prefix="rw-ring-"))


def teardown_module(module):
    shutil.rmtree(_WORK, ignore_errors=True)


def task_dir(tid: str) -> Path:
    return ROOT / "tasks" / tid


def task_yaml(tid: str) -> dict:
    return config.load_yaml(task_dir(tid) / "task.yaml")


def short_id(name: str) -> str:
    match = re.match(r"test_t(\d)_(\d)_", name)
    return f"T{match.group(1)}-{match.group(2)}"


@functools.cache
def hidden_ids(tid: str) -> dict[int, tuple[str, ...]]:
    """Method names of each turn's hidden file, read with `ast` (the files are never imported here)."""
    out = {}
    for turn in (1, 2):
        names = []
        for path in sorted((task_dir(tid) / "tests" / f"turn{turn}").glob("test_*.py")):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            names += [n.name for c in ast.walk(tree) if isinstance(c, ast.ClassDef) for n in c.body
                      if isinstance(n, ast.FunctionDef) and n.name.startswith("test_")]
        out[turn] = tuple(names)
    return out


def all_short(tid: str) -> frozenset[str]:
    return frozenset(short_id(n) for names in hidden_ids(tid).values() for n in names)


# ---- the engine-built base -------------------------------------------------------------------------------------------

@pytest.fixture(scope="session")
def bases() -> dict[str, Path]:
    out = {}
    for tid in IDS:
        try:
            out[tid] = ring_cache.cached_base(task_dir(tid), "rw")
        except Exception as exc:  # noqa: BLE001 - an unreachable upstream skips, unless the ring is required
            if os.environ.get("HB_REQUIRE_RW_BASE") == "1":
                pytest.fail(f"HB_REQUIRE_RW_BASE=1 but the {tid} base cannot be built: {exc}")
            pytest.skip(f"cannot build the {tid} base from the pinned upstream: {exc}")
    return out


def read_tree(tree: Path) -> dict[str, str]:
    return {p.relative_to(tree).as_posix(): p.read_text(encoding="utf-8")
            for p in sorted(tree.rglob("*.py")) if ".git" not in p.relative_to(tree).parts}


def overlay(tid: str, role: str, turn: int) -> dict[str, str]:
    folder = task_dir(tid) / "oracle" / "solutions" / role / f"turn-{turn}"
    return {p.relative_to(folder).as_posix(): p.read_text(encoding="utf-8")
            for p in sorted(folder.rglob("*")) if p.is_file()}


def apply_edits(overlays: dict[int, dict[str, str]], edits: list[dict]) -> dict[int, dict[str, str]]:
    """The two edit forms of W0 rev 6.6 (g): `old` occurs exactly once in the named turn's overlay file, or `old` is empty
    and the file is absent from the reference overlay (a create)."""
    overlays = {turn: dict(files) for turn, files in overlays.items()}
    for edit in edits:
        match = re.match(r"turn-(\d)/(.+)$", edit["file"])
        assert match, f"edit file {edit['file']!r} lacks the turn-<n>/ prefix"
        files = overlays[int(match.group(1))]
        rel = match.group(2)
        if edit["old"] == "":
            assert rel not in files, f"create form on {edit['file']}, which the reference overlay holds"
            files[rel] = edit["new"]
        else:
            assert rel in files, f"{edit['file']} is not in the overlay"
            assert files[rel].count(edit["old"]) == 1, f"{edit['file']}: old text occurs {files[rel].count(edit['old'])} times"
            files[rel] = files[rel].replace(edit["old"], edit["new"])
    return overlays


_counter = iter(range(10**6))


def build(base: Path, overlays: dict[int, dict[str, str]], turns: tuple[int, ...], extra: dict[str, str] | None = None) -> Path:
    dest = _WORK / f"tree-{next(_counter)}"
    shutil.copytree(base, dest, ignore=shutil.ignore_patterns(".git"))
    for turn in turns:
        for rel, text in overlays[turn].items():
            target = dest / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(text, encoding="utf-8", newline="\n")
    for rel, text in (extra or {}).items():
        (dest / rel).write_text(text, encoding="utf-8", newline="\n")
    return dest


def solution(tid: str, role: str) -> dict[int, dict[str, str]]:
    return {1: overlay(tid, role, 1), 2: overlay(tid, role, 2)}


@dataclass(frozen=True)
class Hidden:
    code: int
    ran: int
    failed: frozenset[str]   # assertion failures, short ids
    errored: frozenset[str]  # any other exception
    output: str

    @property
    def ok(self) -> bool:
        return self.code == 0 and self.ran > 0 and not self.failed and not self.errored


def run_hidden(tid: str, tree: Path, turns: tuple[int, ...]) -> Hidden:
    """The task's own oracle command, in a grading copy of `tree` plus the named turns' hidden tests."""
    work = _WORK / f"hidden-{next(_counter)}"
    shutil.copytree(tree, work)
    for turn in turns:
        shutil.copytree(task_dir(tid) / "tests" / f"turn{turn}", work / f"turn{turn}")
    argv = [sys._base_executable if a == "{python}" else a for a in task_yaml(tid)["oracle"]["command"]]
    env = {k: v for k, v in os.environ.items() if k in ("PATH", "SYSTEMROOT", "TEMP", "TMP")}
    proc = subprocess.run(argv, cwd=work, capture_output=True, text=True, timeout=300, check=False, env={**env, "PYTHONUTF8": "1", "PYTHONDONTWRITEBYTECODE": "1"})
    out = proc.stdout + proc.stderr
    ran = re.search(r"^Ran (\d+) tests? in ", out, re.MULTILINE)
    return Hidden(proc.returncode, int(ran.group(1)) if ran else 0,
                  frozenset(short_id(n) for n in re.findall(r"^FAIL: (test_t\d_\d_\w*)", out, re.MULTILINE)),
                  frozenset(short_id(n) for n in re.findall(r"^ERROR: (test_t\d_\d_\w*)", out, re.MULTILINE)), out)


@dataclass(frozen=True)
class Observed:
    property_check_pass: int
    turn1_tests_pass: int
    rework_ratio: Decimal | None
    clause: str | None
    t1_lines: int
    changed: int
    snapshot: Hidden
    final: Hidden


def observe(tid: str, base: Path, overlays: dict[int, dict[str, str]]) -> Observed:
    """W1-L 6.1 through the real measure: turn 1's file on the snapshot, both files on the final tree, then the ratio."""
    snap_tree = build(base, overlays, (1,))
    final_tree = build(base, overlays, (1, 2))
    snapshot = run_hidden(tid, snap_tree, (1,))
    final = run_hidden(tid, final_tree, (1, 2))
    base_py, snap_py, final_py = (read_tree(t) for t in (base, snap_tree, final_tree))
    t1, changed = rework.measure(base_py, snap_py, final_py, task_yaml(tid)["blast_radius"])
    ratio = rework.ratio(t1, changed)
    turn2_ok = final.ran > 0 and not any(i.startswith("T2") for i in final.failed | final.errored)
    turn1_ok = final.ran > 0 and not any(i.startswith("T1") for i in final.failed | final.errored)
    clause = "tests" if not turn2_ok else "turn1" if not turn1_ok else "ratio" if ratio is None or ratio > CEILING else None
    return Observed(int(clause is None), int(snapshot.ok), ratio, clause, t1, changed, snapshot, final)


@functools.cache
def reference_observed(tid: str, base_key: str) -> Observed:
    base = Path(base_key)
    return observe(tid, base, solution(tid, "reference"))


# ---- text and provenance checks (every push) -------------------------------------------------------------------------

def latent_hits(prompt: str, terms: list[str]) -> list[tuple[str, int]]:
    return [(str(t), n) for n, line in enumerate(prompt.splitlines(), 1) for t in terms if str(t).lower() in line.lower()]


@pytest.mark.parametrize("tid", IDS)
def test_prompt_has_no_latent_term(tid):
    """The scan covers prompt.md only. turns/2.md must name the API it asks for (`format_money(amount, currency)`,
    `on_failure(callback)`), so it is exempt, as W1-L 6.2/6.3's turn-2 shapes show."""
    terms = task_yaml(tid)["property"]["latent_terms"]
    assert latent_hits((task_dir(tid) / "prompt.md").read_text(encoding="utf-8"), terms) == []


def test_latent_scan_names_the_term_and_the_line():
    assert latent_hits("first\na callback here\n", ["hook", "callback"]) == [("callback", 2)]
    assert latent_hits("US dollars only", ["EUR", "yen"]) == []


def evidence(tid: str) -> str:
    path = task_dir(tid) / "oracle" / "evidence.md"
    assert path.is_file(), f"{path} is missing"
    return path.read_text(encoding="utf-8")


def pin_problems(pin: str, recorded_tree: str, upstream_tree: str, notice: bool, license_text: str, head: str) -> list[str]:
    problems = []
    if not re.fullmatch(r"[0-9a-f]{40}", pin):
        problems.append("pin is not a full commit")
    if recorded_tree != upstream_tree:
        problems.append("recorded tree hash differs from the upstream tree")
    if not notice:
        problems.append("NOTICE.md is missing")
    if "MIT" not in license_text or head not in license_text:
        problems.append("LICENSE is not the upstream MIT text")
    return problems


@pytest.mark.parametrize(("pin", "recorded", "upstream", "notice", "text", "needle"), [
    ("main", "a" * 40, "a" * 40, True, "MIT Copyright (c) 2021 Peter Odding", "pin is not a full commit"),
    ("a" * 40, "b" * 40, "a" * 40, True, "MIT Copyright (c) 2021 Peter Odding", "recorded tree hash differs"),
    ("a" * 40, "a" * 40, "a" * 40, False, "MIT Copyright (c) 2021 Peter Odding", "NOTICE.md is missing"),
    ("a" * 40, "a" * 40, "a" * 40, True, "Apache", "LICENSE is not the upstream MIT text"),
])
def test_pin_problems_fire_on_each_red_fixture(pin, recorded, upstream, notice, text, needle):
    assert any(needle in p for p in pin_problems(pin, recorded, upstream, notice, text, "Copyright (c) 2021 Peter Odding"))


@pytest.mark.parametrize("tid", IDS)
def test_provenance(tid, bases):
    spec, folder = SPEC[tid], task_dir(tid)
    data = task_yaml(tid)
    assert data["source"]["commit"] == spec["pin"] and data["source"]["repo"] == spec["repo"]
    clone = workspace.upstream_tree(spec["repo"], spec["pin"], ring_cache.ring_root("rw") / "upstream")
    upstream = subprocess.run(["git", "rev-parse", f"{spec['pin']}^{{tree}}"], cwd=clone, capture_output=True, text=True,
                              check=True).stdout.strip()
    recorded = re.search(r"^- pin tree: `([0-9a-f]{40})`", evidence(tid), re.MULTILINE)
    assert recorded and upstream == spec["tree"]
    text = (folder / "LICENSE").read_text(encoding="utf-8").replace("\r\n", "\n")
    assert pin_problems(spec["pin"], recorded.group(1), upstream, (folder / "NOTICE.md").is_file(), text, spec["license_head"]) == []
    assert "build" not in (data.get("deliverable") or {})
    assert not (folder / "oracle" / "check").exists(), "a check-less property has no oracle/check (SR-L3, HB-RDY-005)"
    assert [p.name for p in (folder / "workspace").rglob("*") if p.is_file()] == [".gitkeep"]


@pytest.mark.parametrize("tid", IDS)
def test_evidence_paths_and_radius_exist_in_the_base(tid, bases):
    for path in task_yaml(tid)["property"]["evidence_paths"]:
        assert (bases[tid] / path).is_file(), path
    assert (bases[tid] / SPEC[tid]["product"]).is_file()


# ---- test-path classification (R2-2): expected data now, the real function in the follow-on ---------------------------

def classification(tid: str) -> tuple[set[str], set[str]]:
    text = evidence(tid)
    return (set(re.findall(r"^- test path: `([^`]+)`", text, re.MULTILINE)),
            set(re.findall(r"^- product path: `([^`]+)`", text, re.MULTILINE)))


@pytest.mark.parametrize("tid", IDS)
def test_base_test_layout_is_classified_as_data(tid, bases):
    """The expected classification of this base's paths is written in oracle/evidence.md. This test checks the data against
    `_changes.is_test_path` over the built base; the follow-on asserts the same data through `_changes.is_test_path`."""
    tests, products = classification(tid)
    assert SPEC[tid]["test_file"] in tests and SPEC[tid]["product"] in products
    base_paths = frozenset(read_tree(bases[tid]))
    assert tests | products == base_paths and not tests & products, sorted(base_paths ^ (tests | products))
    for path in tests:
        assert _changes.is_test_path(path, base_paths), path
    for path in products:
        assert not _changes.is_test_path(path, base_paths), path


def test_is_test_path_stand_in_pairs():
    base = frozenset({"pkg/tests.py", "pkg/tests/helper.py", "pkg/mod.py"})
    assert _changes.is_test_path("pkg/tests.py", base)
    assert _changes.is_test_path("pkg/tests/helper.py", base)        # in the base, under a tests directory
    assert not _changes.is_test_path("pkg/tests/_first.py", base)    # new, under a tests directory, no test basename
    assert not _changes.is_test_path("pkg/mod.py", base)
    assert _changes.is_test_path("pkg/test_x.py", base) and _changes.is_test_path("conftest.py", base)


def test_stand_in_ratio_counts_replaced_and_deleted_not_added():
    old = [f"l{i}" for i in range(6)]
    new = ["l0", "X1", "l2", "X3", "l5", "a", "b", "c"]  # l1 and l3 replaced, l4 deleted, three added
    base = {"m.py": ""}
    snapshot = {"m.py": "\n".join(old) + "\n"}
    final = {"m.py": "\n".join(new) + "\n"}
    t1, changed = rework.measure(base, snapshot, final, ["*.py"])
    assert (t1, changed) == (6, 3)
    assert rework.ratio(t1, changed) == Decimal("0.5000")
    assert rework.ratio(0, 0) is None


# ---- the hidden tests, the stub and the wrong apps -------------------------------------------------------------------

@pytest.mark.parametrize("tid", IDS)
def test_stub_fails_every_hidden_test(tid, bases):
    """R2-7: a stub returns a unique sentinel; every hidden test then fails on an assertion, none errors."""
    product = SPEC[tid]["product"]
    source = (bases[tid] / product).read_text(encoding="utf-8")
    tree = build(bases[tid], {1: {}, 2: {}}, (), {product: source + SPEC[tid]["stub"]})
    result = run_hidden(tid, tree, (1, 2))
    assert result.errored == frozenset(), result.output
    assert result.failed == all_short(tid), result.output


@pytest.mark.parametrize("tid", IDS)
def test_base_fails_the_hidden_tests_through_the_real_grader(tid, bases, tmp_path):
    base_result = grade_tree(tid, bases[tid], (1,), tmp_path / "base")
    assert (base_result.passed, base_result.partial_credit) == (0, Decimal(0)) and base_result.reason is None


def grade_tree(tid: str, tree: Path, turns: tuple[int, ...], work: Path):
    """The real `correctness.grade`, over a task directory that holds only the named turns' hidden tests."""
    staged = work / "task"
    for turn in turns:
        shutil.copytree(task_dir(tid) / "tests" / f"turn{turn}", staged / "tests" / f"turn{turn}")
    run_dir = work / "run"
    out = run_dir / "out"
    out.mkdir(parents=True)
    oracle = dict(task_yaml(tid)["oracle"])
    return correctness.grade(tree, staged, oracle, out, run_dir, 300.0, work / "scratch")


@pytest.mark.parametrize(("tid", "role"), [(t, r) for t in IDS for r in ROLES])
def test_every_solution_passes_every_hidden_test(tid, role, bases, tmp_path):
    """The reference, the naive and the alternative pass turn 1 on the snapshot and both turns on the final tree, through
    the real `correctness.grade` (floor item: the real grader beside the per-test runner)."""
    overlays = solution(tid, role)
    snap = grade_tree(tid, build(bases[tid], overlays, (1,)), (1,), tmp_path / "snap")
    final = grade_tree(tid, build(bases[tid], overlays, (1, 2)), (1, 2), tmp_path / "final")
    assert (snap.passed, snap.reason) == (1, None) and (final.passed, final.reason) == (1, None)
    counts = hidden_ids(tid)
    assert run_hidden(tid, build(bases[tid], overlays, (1, 2)), (1, 2)).ran == len(counts[1]) + len(counts[2])


def wrong_apps(tid: str) -> dict:
    return load_path(task_dir(tid) / "oracle" / "wrong_apps.py", f"{tid}_wrong_apps").WRONG_APPS


def variants(tid: str) -> dict:
    """The stand-in reader: W0 section 2, `ast.literal_eval` of the one `VARIANTS` assignment, never an import."""
    tree = ast.parse((task_dir(tid) / "oracle" / "variants.py").read_text(encoding="utf-8"))
    assigns = [n for n in tree.body if isinstance(n, (ast.Assign, ast.AnnAssign, ast.AugAssign))]
    assert len(assigns) == 1 and isinstance(assigns[0], ast.Assign), "exactly one top-level VARIANTS assignment"
    assert [t.id for t in assigns[0].targets] == ["VARIANTS"]
    return ast.literal_eval(assigns[0].value)


@pytest.mark.parametrize("tid", IDS)
def test_every_hidden_test_has_a_wrong_app(tid):
    covered = set()
    for entry in wrong_apps(tid).values():
        covered |= set(entry["reds"])
    assert covered == all_short(tid)


def wrong_app_cases():
    return [(tid, name) for tid in IDS for name in sorted(wrong_apps(tid))]


@pytest.mark.parametrize(("tid", "name"), wrong_app_cases())
def test_each_wrong_app_turns_exactly_its_reds_red(tid, name, bases):
    entry = wrong_apps(tid)[name]
    overlays = apply_edits(solution(tid, "reference"), entry["edits"])
    result = run_hidden(tid, build(bases[tid], overlays, (1, 2)), (1, 2))
    assert result.errored == frozenset(), f"{name} errors instead of failing an assertion\n{result.output}"
    assert result.failed == frozenset(entry["reds"]), result.output


def test_wrong_app_set_is_not_empty():
    assert all(len(wrong_apps(tid)) >= 9 for tid in IDS)


# ---- variants (R2-1) ------------------------------------------------------------------------------------------------

def variant(tid: str, name: str) -> dict:
    table = variants(tid)
    assert name in table, f"{tid} declares no variant {name!r}"
    return table[name]


def variant_problems(table: dict, allowed_roots: tuple[str, ...] = ("turn-1/", "turn-2/")) -> list[str]:
    """The stand-in for W1-E's reader: names, keys, the turn prefix. The follow-on loads each file through the real one."""
    problems = []
    for name, spec in table.items():
        if not VARIANT_NAME.fullmatch(name):
            problems.append(f"bad name {name!r}")
        if set(spec) != {"flips", "clauses", "edits"}:
            problems.append(f"{name}: keys {sorted(spec)}")
            continue
        for edit in spec["edits"]:
            if set(edit) != {"file", "old", "new"}:
                problems.append(f"{name}: edit keys {sorted(edit)}")
            elif not edit["file"].startswith(allowed_roots):
                problems.append(f"{name}: edit file {edit['file']!r} lacks the turn-<n>/ prefix")
    return problems


@pytest.mark.parametrize("bad", [
    {"v-ratio-high": {"flips": [], "clauses": {}, "edits": []}},
    {"ratio_high": {"flips": [], "clauses": {}, "edits": []}},
    {"a" * 17: {"flips": [], "clauses": {}, "edits": []}},
    {"ok": {"flips": [], "clauses": {}, "edits": [{"file": "humanfriendly/x.py", "old": "a", "new": "b"}]}},
    {"ok": {"flips": [], "edits": []}},
])
def test_variant_reader_refuses_each_bad_shape(bad):
    assert variant_problems(bad) != []


@pytest.mark.parametrize("tid", IDS)
def test_variants_file_meets_w0(tid):
    table = variants(tid)
    assert variant_problems(table) == []
    assert set(table) == SPEC[tid]["variants"]
    for spec in table.values():
        assert all(f in ("property_check_pass", "turn1_tests_pass", "rework_ratio") for f in spec["flips"])
        assert set(spec["clauses"]) <= set(spec["flips"])
    assert len((task_dir(tid) / "oracle" / "variants.py").read_bytes()) <= 64 * 1024


def variant_cases():
    return [(tid, name) for tid in IDS for name in sorted(SPEC[tid]["variants"])]


@pytest.mark.parametrize(("tid", "name"), variant_cases())
def test_each_variant_flips_exactly_its_set(tid, name, bases):
    """Observed through the real measure measure and the real hidden tests. `flips` lists the metric ids whose observed value
    differs from the reference's; `clauses` names the deciding clause of a flipped `property_check_pass`."""
    spec = variant(tid, name)
    reference = reference_observed(tid, str(bases[tid]))
    observed = observe(tid, bases[tid], apply_edits(solution(tid, "reference"), spec["edits"]))
    flips = [m for m in ("property_check_pass", "turn1_tests_pass", "rework_ratio")
             if getattr(observed, m) != getattr(reference, m)]
    assert flips == sorted(spec["flips"], key=("property_check_pass", "turn1_tests_pass", "rework_ratio").index)
    if "property_check_pass" in flips:
        assert spec["clauses"] == {"property_check_pass": observed.clause}
    else:
        assert spec["clauses"] == {}


@pytest.mark.parametrize("tid", IDS)
def test_every_primary_clause_has_a_flipping_variant(tid):
    """Each branch of the primary (tests, turn1, ratio) is live: some variant is decided by it."""
    table = variants(tid)
    assert {spec["clauses"].get("property_check_pass") for spec in table.values()} >= {"tests", "turn1", "ratio"}


@pytest.mark.parametrize("tid", IDS)
def test_duplicate_fails_by_a_hidden_test_not_by_the_ratio(tid, bases):
    """RQ-1 defence 3: the sibling copy has a ratio at or below the reference's, and still fails a turn-2 test."""
    spec = variant(tid, "duplicate")
    reference = reference_observed(tid, str(bases[tid]))
    observed = observe(tid, bases[tid], apply_edits(solution(tid, "reference"), spec["edits"]))
    assert observed.rework_ratio is not None and observed.rework_ratio <= reference.rework_ratio
    assert observed.final.failed and all(i.startswith("T2") for i in observed.final.failed)
    assert observed.clause == "tests"


@pytest.mark.parametrize("tid", IDS)
def test_pad_turn1_is_the_named_residual(tid, bases):
    """R-W1: padding turn 1 with dead lines lowers the ratio and still passes. It is expected to pass (the known hole)."""
    reference = reference_observed(tid, str(bases[tid]))
    observed = observe(tid, bases[tid], apply_edits(solution(tid, "reference"), variant(tid, "padturn1")["edits"]))
    assert observed.property_check_pass == 1 and observed.clause is None
    assert observed.rework_ratio < reference.rework_ratio
    assert "R-W1" in evidence(tid)


# ---- expected values and the reference/naive ratios ------------------------------------------------------------------

def recorded_ratio(tid: str, role: str) -> tuple[int, int, Decimal]:
    match = re.search(rf"^- ratio {role}: t1=(\d+) changed=(\d+) ratio=(\d\.\d{{4}})$", evidence(tid), re.MULTILINE)
    assert match, f"evidence.md has no ratio line for {role}"
    return int(match.group(1)), int(match.group(2)), Decimal(match.group(3))


@pytest.mark.parametrize(("tid", "role"), [(t, r) for t in IDS for r in ("reference", "naive")])
def test_expected_ratio_equals_the_recorded_count_and_the_stand_in(tid, role, bases):
    """`expected.<role>.rework_ratio` is the recorded count (Inferred, B-RW1/B-RW2); the stand-in cross-checks it. It is a
    cross-check, not provenance (FIXT-A): the discrimination record in the follow-on is the measurement."""
    t1, changed, ratio = recorded_ratio(tid, role)
    observed = observe(tid, bases[tid], solution(tid, role))
    assert (observed.t1_lines, observed.changed, observed.rework_ratio) == (t1, changed, ratio)
    assert task_yaml(tid)["expected"][role]["rework_ratio"] == f"{ratio}"
    assert observed.turn1_tests_pass == 1 and task_yaml(tid)["expected"][role]["turn1_tests_pass"] == 1


@pytest.mark.parametrize("tid", IDS)
def test_ceiling_separates_reference_and_naive(tid, bases):
    """EV-4 through the real measure; the engine shows it in the follow-on. The naive passes every test and loses on the ratio."""
    reference = reference_observed(tid, str(bases[tid]))
    naive = observe(tid, bases[tid], solution(tid, "naive"))
    assert (reference.property_check_pass, reference.clause) == (1, None)
    assert (naive.property_check_pass, naive.clause) == (0, "ratio")
    assert naive.final.ok and naive.rework_ratio > CEILING >= reference.rework_ratio
    expected = task_yaml(tid)["expected"]
    assert (expected["reference"]["property_check_pass"], expected["naive"]["property_check_pass"]) == (1, 0)


@pytest.mark.parametrize("tid", IDS)
def test_alt_solution_scores_one(tid, bases):
    alt = observe(tid, bases[tid], solution(tid, "alt"))
    assert (alt.property_check_pass, alt.clause) == (1, None) and alt.rework_ratio <= CEILING


@pytest.mark.parametrize("tid", IDS)
def test_expected_is_a_literal_not_a_placeholder(tid):
    """Draft may not be ready, but a `<...>` placeholder never survives authoring (W1-L 5.3). `ready` is the follow-on's."""
    for role, values in task_yaml(tid)["expected"].items():
        for metric, value in values.items():
            assert isinstance(value, (int, str)) and not str(value).startswith("<"), (role, metric, value)
    assert task_yaml(tid)["status"] == "ready"


@pytest.mark.parametrize("tid", IDS)
def test_grading_is_deterministic(tid, bases):
    first = observe(tid, bases[tid], solution(tid, "naive"))
    second = observe(tid, bases[tid], solution(tid, "naive"))
    assert (first.rework_ratio, first.final.failed, first.t1_lines) == (second.rework_ratio, second.final.failed, second.t1_lines)


@pytest.mark.parametrize("tid", IDS)
def test_no_oracle_string_in_the_prompts(tid):
    """A string that only the oracle owns (a solution's private names) never appears in a prompt."""
    private = {"RW1": ["_CURRENCIES", "_format_money", "_FORMATS", "_render"],
               "RW2": ["_failure_callbacks", "_record_failure", "_FailureBus"]}[tid]
    texts = [(task_dir(tid) / "prompt.md").read_text(encoding="utf-8"), (task_dir(tid) / "turns" / "2.md").read_text(encoding="utf-8")]
    assert [name for name in private for text in texts if name in text] == []


# ---- the RW1 seeded-disagreement readiness fixture (R2-4; runs in the follow-on) --------------------------------------

def test_rw1_seeded_disagreement_fixture_disagrees_with_expected_on_one_named_metric():
    """Written now for W1-E T-E11/T-E12 (HB-RDY-003 names metric, expected and observed). X-J2b's multi-turn path drives it
    through readiness in the follow-on; this test only proves the fixture is a true disagreement on a metric `expected` names."""
    import json
    seeded = json.loads(SEEDED.read_text(encoding="utf-8"))
    expected = task_yaml("RW1")["expected"]["reference"]
    assert seeded["task"] == "RW1" and seeded["role"] == "reference"
    differing = [m for m, v in seeded["observed"].items() if str(expected[m]) != str(v)]
    assert differing == [seeded["disagrees_on"]] == ["rework_ratio"]
    assert set(seeded["observed"]) == set(expected)
    assert seeded["cites"] == ["T-E11", "T-E12"]


def test_difflib_is_the_only_diff_engine_the_measure_uses():
    """The real `_changes.line_delta` names its algorithm (W1-L 5.1: SequenceMatcher, autojunk off); a drift would change every count."""
    source = inspect.getsource(_changes.line_delta)
    assert "autojunk=False" in source and difflib.SequenceMatcher is not None
