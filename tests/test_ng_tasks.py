"""Tests for the no-guessing tasks NG1 and NG2 (W1-L rev 2 sections 7 and 15, Erratum 1; X-NG).

Two rings. Text and table checks run every push. The readiness checks build the base through the engine's own
`workspace.task_source` (a cached upstream clone) and grade solutions with the real `correctness.grade`; they prove
authoring facts (a hidden test is red for its own reason, a variant moves exactly what it claims) and cost seconds each.

Not here, by design: the `noguess` strategy and its resolver are X-LG's, so every `hallucinated_symbol_errors` value in
`task.yaml` and in the variants is a hand trace (Inferred, R-97 condition 4). What these tests do prove is the premise of each
trace: the names a solution or variant references are really absent from (or present in) the pristine vendored library.
The `ready` follow-on adds the real-strategy rows, the seeded-disagreement run and the load of `variants.py` through W1-E's
reader (`reader_problems` below is the contract of W0 section 2 rev 6.6, standing in until that reader is on main).
"""

from __future__ import annotations

import ast
import functools
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

import pytest

from harness_bench import config, workspace
from harness_bench.grade import correctness

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures" / "ng_tasks"
IDS = ("NG1", "NG2")
METRICS = ("property_check_pass", "hallucinated_symbol_errors", "verified_before_use")
NOT_BUILT = {"na": "not built"}

SPECS = {
    "NG1": {
        "lib": "quotakit",
        "module": "test_limiter_hidden",
        "pin": "3c082c654c2804b9354e4b62dbd2994f1aac464d",
        "tree": "6f74c64680663c7c176209501769dfe969efa7eb",
        "licence": ("The MIT License (MIT)", "Copyright (c) 2014-2026 Thomas Kemmer"),
        "product": "src/cachetools/limiter.py",
        "hidden": (
            "test_n1_allows_max_calls_calls",
            "test_n2_the_next_call_raises_limit_exceeded_and_does_not_run",
            "test_n3_the_window_slides",
            "test_n4_a_clock_of_none_means_the_default_clock",
            "test_n5_the_wrapper_keeps_the_name_the_doc_and_the_result",
            "test_n6_limit_exceeded_is_its_own_exception",
        ),
        # wrong app -> the exact hidden tests it turns red. wa-cap-two replaces W1-L's wa-extra-allowed: a gate that admits one
        # call too many reddens N-2 (the next call must raise), not N-1.
        "wrong_apps": {
            "wa-cap-two": ("test_n1_allows_max_calls_calls",),
            "wa-no-raise": ("test_n2_the_next_call_raises_limit_exceeded_and_does_not_run",),
            "wa-fixed-window": ("test_n3_the_window_slides",),
            "wa-clock-none": ("test_n4_a_clock_of_none_means_the_default_clock",),
            "wa-wraps": ("test_n5_the_wrapper_keeps_the_name_the_doc_and_the_result",),
            "wa-same-exception": ("test_n6_limit_exceeded_is_its_own_exception",),
        },
        # variant -> (hidden tests it turns red on the pristine vendor, vendored names it adds that the library lacks)
        "variants": {
            "hallucinated": ((), ("quotakit.Gate.try_acquire",)),
            "kw": ((), ("quotakit.Gate.__init__:period",)),
            "default": (("test_n3_the_window_slides",), ()),
            "vendoredit": ((), ("quotakit.Gate.try_acquire",)),
        },
        "absent": ("quotakit.RateLimiter", "quotakit.RateLimitExceeded", "quotakit.Gate.acquire", "quotakit.Gate.allow",
                   "quotakit.Gate.try_acquire", "quotakit.Gate.__init__:period", "quotakit.Gate.__init__:calls"),
        "present": ("quotakit.Gate", "quotakit.Gate.admit", "quotakit.Gate.require", "quotakit.QuotaExceeded",
                    "quotakit.Gate.__init__:clock", "quotakit.Gate.__init__:mode"),
        "naive_names": ("quotakit.RateLimiter", "quotakit.RateLimitExceeded"),
        "vendor_file": "vendor/quotakit/quotakit/gate.py",
        "oracle_strings": ("Work docstring.", "FakeClock", "Counted"),
        # path -> (in the base tree, kind): the base's test layout as data (R2-2)
        "layout": {
            "tests/__init__.py": (True, "test"),
            "tests/test_cache.py": (True, "test"),
            "tests/test_limiter.py": (False, "test"),
            "test_limiter_hidden.py": (False, "test"),
            "src/cachetools/limiter.py": (False, "product"),
            "src/cachetools/__init__.py": (True, "product"),
            "vendor/quotakit/quotakit/gate.py": (True, "product"),
        },
    },
    "NG2": {
        "lib": "envkit",
        "module": "test_interp_hidden",
        "pin": "5a77b12a7a9f052ce5a20c335d2825658f6aea52",
        "tree": "e529ffa3388ab50d261dbba463f30b03d5d40014",
        "licence": ("MIT License", "Copyright (c) 2021 Taneli Hukkinen"),
        "product": "src/tomli/_interp.py",
        "hidden": (
            "test_g1_a_name_is_replaced_in_a_string_value",
            "test_g2_strings_in_tables_and_arrays_are_replaced",
            "test_g3_an_unknown_name_raises_unknown_name",
            "test_g4_adjacent_names_are_replaced_one_by_one",
            "test_g5_text_that_is_not_a_name_in_braces_is_left_alone",
            "test_g6_values_that_are_not_strings_are_returned_unchanged",
        ),
        # wa-nosubst also reddens G-3 (nothing is looked up, so nothing raises): W1-L listed G-1, G-2 and G-4.
        "wrong_apps": {
            "wa-nosubst": ("test_g1_a_name_is_replaced_in_a_string_value", "test_g2_strings_in_tables_and_arrays_are_replaced",
                           "test_g3_an_unknown_name_raises_unknown_name", "test_g4_adjacent_names_are_replaced_one_by_one"),
            "wa-no-nested": ("test_g2_strings_in_tables_and_arrays_are_replaced",),
            "wa-unknown-empty": ("test_g3_an_unknown_name_raises_unknown_name",),
            "wa-greedy-regex": ("test_g4_adjacent_names_are_replaced_one_by_one",),
            "wa-template": ("test_g5_text_that_is_not_a_name_in_braces_is_left_alone",),
            "wa-int-str": ("test_g6_values_that_are_not_strings_are_returned_unchanged",),
        },
        "variants": {
            "hallucinated": ((), ("envkit.EnvSource",)),
            "hallucmember": ((), ("envkit.MappingSource.get",)),
            "defaultguess": (("test_g3_an_unknown_name_raises_unknown_name",), ()),
            "kw": ((), ("envkit.MappingSource.fetch:default",)),
            "vendoredit": ((), ("envkit.MappingSource.get",)),
        },
        "absent": ("envkit.EnvSource", "envkit.MappingSource.get", "envkit.MappingSource.fetch:default"),
        "present": ("envkit.MappingSource", "envkit.MappingSource.fetch", "envkit.MappingSource.fetch:fallback",
                    "envkit.UnknownName", "envkit.MISSING"),
        "naive_names": ("envkit.EnvSource",),
        "vendor_file": "vendor/envkit/envkit/source.py",
        "oracle_strings": ("MISSING_NAME", "HOME_DIR"),
        "layout": {
            "tests/__init__.py": (True, "test"),
            "tests/burntsushi.py": (True, "test"),
            "tests/test_misc.py": (True, "test"),
            "tests/test_interp.py": (False, "test"),
            "test_interp_hidden.py": (False, "test"),
            "src/tomli/_interp.py": (False, "product"),
            "src/tomli/__init__.py": (True, "product"),
            "vendor/envkit/envkit/source.py": (True, "product"),
        },
    },
}
ALL_IDS = list(SPECS)


def task_dir(task_id: str) -> Path:
    return ROOT / "tasks" / task_id


def task_yaml(task_id: str) -> dict:
    return config.load_yaml(task_dir(task_id) / "task.yaml")


def role_files(task_id: str, role: str) -> dict[str, str]:
    base = task_dir(task_id) / "oracle" / "solutions" / role
    return {p.relative_to(base).as_posix(): p.read_text(encoding="utf-8") for p in sorted(base.rglob("*")) if p.is_file()}


def literal_table(path: Path, name: str):
    """The value of the one top-level `name = <literal>` assignment, never importing the file."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    values = [node.value for node in tree.body if isinstance(node, ast.Assign)
              and [t.id for t in node.targets if isinstance(t, ast.Name)] == [name]]
    assert len(values) == 1, f"{path} must assign {name} exactly once"
    return ast.literal_eval(values[0])


def variants(task_id: str) -> dict:
    return literal_table(task_dir(task_id) / "oracle" / "variants.py", "VARIANTS")


def wrong_apps(task_id: str) -> dict:
    return literal_table(task_dir(task_id) / "oracle" / "wrong_apps.py", "WRONG_APPS")


def apply_edits(files: dict[str, str], edits: list[dict]) -> dict[str, str]:
    """The overlay after `edits`: `old` occurs exactly once in `file`; the create form (`old` empty) adds or replaces a file."""
    files = dict(files)
    for edit in edits:
        file, old, new = edit["file"], edit["old"], edit["new"]
        if old == "":
            files[file] = new
            continue
        assert file in files, f"edit file {file} is not in the overlay"
        assert files[file].count(old) == 1, f"edit target occurs {files[file].count(old)} times in {file}: {old!r}"
        files[file] = files[file].replace(old, new)
    return files


# ---- the engine-built base and the real correctness grader ---------------------------------------------------------------

_WORK = Path(tempfile.mkdtemp(prefix="ng-ring-"))
_counter = iter(range(10**6))


def teardown_module(module):
    shutil.rmtree(_WORK, ignore_errors=True)


def _version(task_id: str) -> str:
    """A cache key that changes with the task's authored overlay, so a stale cached base is never reused."""
    import hashlib
    digest = hashlib.sha256()
    for path in sorted((task_dir(task_id) / "workspace").rglob("*")):
        if path.is_file():
            digest.update(path.relative_to(task_dir(task_id)).as_posix().encode() + path.read_bytes())
    digest.update(task_yaml(task_id)["source"]["commit"].encode())
    return "ng" + digest.hexdigest()


@functools.cache
def engine_base(task_id: str) -> Path:
    """The base tree as the engine builds it: `workspace.task_source` over the pinned upstream plus the overlay (ORCL-A)."""
    root = Path(tempfile.gettempdir()) / "hb-ng-ring"
    try:
        return workspace.task_source(task_dir(task_id), _version(task_id), root / "sources", root / "upstream")
    except Exception as exc:  # noqa: BLE001 - an unreachable upstream skips, unless the ring is required
        if os.environ.get("HB_REQUIRE_NG_BASE") == "1":
            pytest.fail(f"HB_REQUIRE_NG_BASE=1 but the {task_id} base cannot be built: {exc}")
        pytest.skip(f"cannot build the {task_id} base from the pinned upstream: {exc}")


@dataclass(frozen=True)
class Graded:
    passed: int | None            # pass@1 from the real grader
    partial: Decimal | None
    reason: str | None
    failed: frozenset[str]        # assertion failures
    errored: frozenset[str]       # any other exception
    log: str

    @property
    def red(self) -> frozenset[str]:
        return self.failed | self.errored


def grading_copy(task_id: str, files: dict[str, str], dest: Path, restore_vendor: bool = True) -> Path:
    """The engine base plus `files`; the pristine vendored library is put back last, as the strategy does (W1-L 7.0)."""
    lib = SPECS[task_id]["lib"]
    shutil.copytree(engine_base(task_id), dest, ignore=shutil.ignore_patterns(".git"))
    for rel, text in files.items():
        target = dest / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8", newline="\n")
    if restore_vendor:
        shutil.rmtree(dest / "vendor" / lib)
        shutil.copytree(task_dir(task_id) / "workspace" / "vendor" / lib, dest / "vendor" / lib)
    return dest


def grade(task_id: str, files_key: tuple, restore_vendor: bool = True) -> Graded:
    files = dict(files_key)
    run = _WORK / f"run-{next(_counter)}"
    out = run / "out"
    out.mkdir(parents=True)
    ws = grading_copy(task_id, files, run / "ws", restore_vendor)
    done = correctness.grade(ws, task_dir(task_id), task_yaml(task_id)["oracle"], out, run, 180, run / "w")
    log = (out / "oracle.log").read_text(encoding="utf-8")
    return Graded(done.passed, done.partial_credit, done.reason,
                  frozenset(re.findall(r"^FAIL: (test_\w+)", log, re.MULTILINE)),
                  frozenset(re.findall(r"^ERROR: (test_\w+)", log, re.MULTILINE)), log)


@functools.cache
def _grade_cached(task_id: str, files_key: tuple, restore_vendor: bool) -> Graded:
    return grade(task_id, files_key, restore_vendor)


def graded(task_id: str, files: dict[str, str], restore_vendor: bool = True) -> Graded:
    return _grade_cached(task_id, tuple(sorted(files.items())), restore_vendor)


# The stub is the one thing every hidden test must fail on: a function returning a unique sentinel (R2-7; K5).
STUBS = {
    "NG1": {"src/cachetools/limiter.py": (
        "SENTINEL = object()\n\n\nclass LimitExceeded(Exception):\n    pass\n\n\n"
        "def limit_calls(max_calls, per_seconds, clock=None):\n    def decorator(func):\n"
        "        def stub(*args, **kwargs):\n            return SENTINEL\n\n        return stub\n\n    return decorator\n")},
    "NG2": {"src/tomli/_interp.py": "SENTINEL = object()\n\n\ndef loads_env(text, source):\n    return SENTINEL\n"},
}


def stub_files(task_id: str) -> dict[str, str]:
    """The stub overlay: the reference's package export (NG2's `__init__.py`) with the sentinel module."""
    files = {k: v for k, v in role_files(task_id, "reference").items() if not k.endswith(SPECS[task_id]["product"].rsplit("/", 1)[1])}
    return {**files, **STUBS[task_id]}


# ---- push ring: task.yaml, prompt, provenance ---------------------------------------------------------------------------

def latent_hits(prompt: str, terms: list[str]) -> list[tuple[str, int]]:
    return [(str(t), n) for n, line in enumerate(prompt.splitlines(), 1) for t in terms if str(t).lower() in line.lower()]


@pytest.mark.parametrize("task_id", ALL_IDS)
def test_ng_prompt_has_no_latent_term(task_id):
    terms = task_yaml(task_id)["property"]["latent_terms"]
    assert latent_hits((task_dir(task_id) / "prompt.md").read_text(encoding="utf-8"), terms) == []


def test_ng_latent_scan_names_the_term_and_the_line():
    assert latent_hits("first line\nsee the README here\n", ["readme", "verify"]) == [("readme", 2)]
    assert latent_hits("verify it", ["check the"]) == []


def narrowed_metrics() -> set[str]:
    """The no-guessing property grader's metric set, read from the catalog: untagged or tagged `no-guessing` (W0 section 7)."""
    catalog = config.load_yaml(ROOT / "bench" / "metrics.yaml")
    return {m["id"] for area in catalog["areas"].values() for m in area.get("metrics") or []
            if m["grader"] == "property" and m["kind"] == "score" and m.get("property") in (None, "no-guessing")}


def expected_problems(data: dict) -> list[str]:
    """What `ready` will refuse about an expected block (W1-L 5.3): a missing metric, a placeholder, a wrong-typed value."""
    problems = [f"{role} lacks {m}" for role in ("reference", "naive") for m in sorted(narrowed_metrics())
                if m not in (data.get(role) or {})]
    for role in ("reference", "naive"):
        for metric, value in (data.get(role) or {}).items():
            if isinstance(value, dict):
                if value != NOT_BUILT:
                    problems.append(f"{role}.{metric} is an exemption other than {NOT_BUILT}")
            elif not isinstance(value, int) or isinstance(value, bool):
                problems.append(f"{role}.{metric} is not a literal int: {value!r}")
    return problems


@pytest.mark.parametrize("task_id", ALL_IDS)
def test_ng_task_yaml_is_a_draft_with_a_literal_expected_block(task_id):
    task = task_yaml(task_id)
    assert task["status"] == "draft"
    assert task["property"]["name"] == "no-guessing" and task["property"]["primary_metric"] == "property_check_pass"
    assert task["graders"] == ["correctness", "property"]
    assert narrowed_metrics() == set(METRICS)
    assert expected_problems(task["expected"]) == []
    for role in ("reference", "naive"):
        assert task["expected"][role]["verified_before_use"] == NOT_BUILT  # W0 rev 5: not built, W1-L 7.2
    assert task["expected"]["reference"]["property_check_pass"] == 1 and task["expected"]["naive"]["property_check_pass"] == 0
    assert task["expected"]["reference"]["hallucinated_symbol_errors"] == 0
    assert not (task_dir(task_id) / "oracle" / "check").exists()  # a check-less property (W0 rev 5, SR-L3)


def test_ng_expected_problems_fire_on_each_red_fixture():
    good = {"reference": {"property_check_pass": 1, "hallucinated_symbol_errors": 0, "verified_before_use": NOT_BUILT},
            "naive": {"property_check_pass": 0, "hallucinated_symbol_errors": 2, "verified_before_use": NOT_BUILT}}
    assert expected_problems(good) == []
    placeholder = {**good, "naive": {**good["naive"], "hallucinated_symbol_errors": "<X-LG>"}}
    assert expected_problems(placeholder) == ["naive.hallucinated_symbol_errors is not a literal int: '<X-LG>'"]
    scaled = {**good, "reference": {**good["reference"], "property_check_pass": "1.0000"}}
    assert expected_problems(scaled) == ["reference.property_check_pass is not a literal int: '1.0000'"]
    other_na = {**good, "reference": {**good["reference"], "verified_before_use": {"na": "x"}}}
    assert expected_problems(other_na) == [f"reference.verified_before_use is an exemption other than {NOT_BUILT}"]
    missing = {**good, "naive": {"property_check_pass": 0}}
    assert expected_problems(missing) == ["naive lacks hallucinated_symbol_errors", "naive lacks verified_before_use"]


def test_ng_both_tasks_use_the_same_primary_rule():
    """R2-8: one sentence, the same for NG1 and NG2. The primary is the hidden tests only; the count is secondary (EV-5)."""
    for task_id in ALL_IDS:
        prop = task_yaml(task_id)["property"]
        assert prop["ceilings"] == {} and prop["primary_metric"] == "property_check_pass", task_id
    assert (ROOT / "docs" / "specs" / "enterprise-evaluation.md").read_text(encoding="utf-8").count("Both are secondary.") == 1


def pin_problems(commit: str, recorded_tree: str, upstream_tree: str, notice: bool, license_text: str, licence: tuple[str, str]) -> list[str]:
    problems = []
    if not re.fullmatch(r"[0-9a-f]{40}", commit):
        problems.append("pin is not a full commit")
    if recorded_tree != upstream_tree:
        problems.append("recorded tree hash differs from the upstream tree")
    if not notice:
        problems.append("NOTICE.md is missing")
    if not all(part in license_text for part in licence):
        problems.append("LICENSE is not the upstream text")
    return problems


def test_ng_pin_problems_fire_on_each_red_fixture():
    licence = ("MIT License", "Copyright (c) 2021 X")
    good = ("a" * 40, "b" * 40, "b" * 40, True, "MIT License\nCopyright (c) 2021 X", licence)
    assert pin_problems(*good) == []
    assert pin_problems("main", *good[1:]) == ["pin is not a full commit"]
    assert pin_problems(good[0], "c" * 40, good[2], True, good[4], licence) == ["recorded tree hash differs from the upstream tree"]
    assert pin_problems(*good[:3], False, good[4], licence) == ["NOTICE.md is missing"]
    assert pin_problems(*good[:4], "other", licence) == ["LICENSE is not the upstream text"]


def recorded_tree(task_id: str) -> str:
    return re.search(r"^- pin tree: `([0-9a-f]{40})`", (task_dir(task_id) / "oracle" / "evidence.md").read_text(encoding="utf-8"),
                     re.MULTILINE).group(1)


NETWORK_WORDS = {"pip", "uv", "npm", "curl", "wget", "--index-url"}


@pytest.mark.parametrize("task_id", ALL_IDS)
def test_ng_provenance(task_id):
    """Pin, recorded tree hash, NOTICE and LICENSE, and no build or network name (W1-L section 15 `provenance`)."""
    spec, task = SPECS[task_id], task_yaml(task_id)
    assert task["source"]["commit"] == spec["pin"]
    assert pin_problems(task["source"]["commit"], recorded_tree(task_id), spec["tree"], (task_dir(task_id) / "NOTICE.md").is_file(),
                        (task_dir(task_id) / "LICENSE").read_text(encoding="utf-8"), spec["licence"]) == []
    assert "deliverable" not in task and "build" not in task["oracle"]
    assert [w for w in task["oracle"]["command"] if w in NETWORK_WORDS or w.startswith("http")] == []


@pytest.mark.parametrize("task_id", ALL_IDS)
def test_ng_pin_tree_matches_the_engine_built_base(task_id):
    """Readiness ring: the engine-built base is the pinned upstream tree plus the overlay, and the recorded tree is real."""
    base = engine_base(task_id)
    source = task_yaml(task_id)["source"]
    clone = workspace.upstream_tree(source["repo"], source["commit"], Path(tempfile.gettempdir()) / "hb-ng-ring" / "upstream")
    tree = subprocess.run(["git", "rev-parse", f"{SPECS[task_id]['pin']}^{{tree}}"], cwd=clone, capture_output=True, text=True,
                          check=True).stdout.strip()
    assert tree == recorded_tree(task_id) == SPECS[task_id]["tree"]
    listed = set(subprocess.run(["git", "ls-tree", "-r", "--name-only", SPECS[task_id]["pin"]], cwd=clone, capture_output=True,
                                text=True, check=True).stdout.split())
    built = {p.relative_to(base).as_posix() for p in base.rglob("*") if p.is_file() and ".git" not in p.relative_to(base).parts}
    overlay = {p.relative_to(task_dir(task_id) / "workspace").as_posix() for p in (task_dir(task_id) / "workspace").rglob("*")
               if p.is_file() and "__pycache__" not in p.parts}  # bytecode the reflect/load_lib tests write is no overlay
    assert built - listed == overlay
    assert listed - built == set()


@pytest.mark.parametrize("task_id", ALL_IDS)
def test_ng_evidence_paths_exist_in_the_engine_built_base(task_id):
    base = engine_base(task_id)
    paths = task_yaml(task_id)["property"]["evidence_paths"]
    assert [p for p in paths if not (base / p).is_file()] == []


@pytest.mark.parametrize("task_id", ALL_IDS)
def test_ng_no_oracle_string_in_prompt_or_task_workspace(task_id):
    spec = SPECS[task_id]
    hidden_source = (task_dir(task_id) / "tests" / f"{spec['module']}.py").read_text(encoding="utf-8")
    oracle_strings = {*spec["hidden"], spec["module"], *spec["oracle_strings"]}
    assert all(s in hidden_source for s in oracle_strings), "an oracle string is not in the hidden tests"
    haystacks = {"prompt.md": (task_dir(task_id) / "prompt.md").read_text(encoding="utf-8")}
    for p in (task_dir(task_id) / "workspace").rglob("*"):
        if p.is_file():
            haystacks[p.relative_to(task_dir(task_id)).as_posix()] = p.read_text(encoding="utf-8", errors="ignore")
    assert [(n, s) for n, text in haystacks.items() for s in oracle_strings if s in text] == []
    assert [s for s in oracle_strings if s in f"the prompt holds {spec['module']}"] == [spec["module"]]  # the fixture the scan catches


# ---- the vendored library: its README is true, and the names the traces rest on are really absent or present ---------------

def contract_lines(readme: str) -> list[str]:
    block = re.search(r"## Contract\s+```text\n(.*?)```", readme, re.DOTALL)
    assert block, "README has no Contract block"
    return [line.strip() for line in block.group(1).splitlines() if line.strip()]


def load_lib(lib_dir: Path, name: str):
    import importlib
    sys.path.insert(0, str(lib_dir))
    try:
        return importlib.import_module(name)
    finally:
        sys.path.remove(str(lib_dir))
        for key in [k for k in sys.modules if k == name or k.startswith(name + ".")]:
            del sys.modules[key]


def contract_problems(lines: list[str], module) -> list[str]:
    """Each documented line against the code: the member exists, and a documented signature has the code's parameter names,
    kinds and (for a literal default) values."""
    import inspect
    problems = []
    for line in lines:
        text = line.split("->")[0].strip()
        name, paren, params = text.partition("(")
        obj = module
        try:
            for part in name.split(".")[1:] if name.split(".")[0] == module.__name__ else name.split("."):
                obj = getattr(obj, part)
        except AttributeError:
            problems.append(f"{name} does not exist")
            continue
        if not paren:
            continue
        documented = ast.parse(f"def f({params.rstrip(')')}): pass").body[0].args
        actual = [p for p in inspect.signature(obj).parameters.values() if p.name != "self"]
        doc_names = [a.arg for a in documented.args] + [a.arg for a in documented.kwonlyargs]
        if [p.name for p in actual] != doc_names:
            problems.append(f"{name} parameters are {[p.name for p in actual]}, documented {doc_names}")
            continue
        defaults = {a.arg: d for a, d in zip(documented.args[len(documented.args) - len(documented.defaults):], documented.defaults)}
        defaults |= {a.arg: d for a, d in zip(documented.kwonlyargs, documented.kw_defaults) if d is not None}
        for p in actual:
            if (p.name in defaults) != (p.default is not inspect.Parameter.empty):
                problems.append(f"{name}.{p.name} default presence differs")
            elif p.name in defaults and isinstance(defaults[p.name], ast.Constant) and defaults[p.name].value != p.default:
                problems.append(f"{name}.{p.name} default is {p.default!r}, documented {defaults[p.name].value!r}")
        if bool(documented.kwonlyargs) != any(p.kind is p.KEYWORD_ONLY for p in actual):
            problems.append(f"{name} keyword-only parameters differ")
    return problems


@pytest.mark.parametrize("task_id", ALL_IDS)
def test_ng_vendored_readme_matches_code(task_id):
    lib = SPECS[task_id]["lib"]
    lib_dir = task_dir(task_id) / "workspace" / "vendor" / lib
    module = load_lib(lib_dir, lib)
    assert contract_problems(contract_lines((lib_dir / "README.md").read_text(encoding="utf-8")), module) == []


def test_ng_contract_problems_fire_on_each_red_fixture():
    module = load_lib(task_dir("NG1") / "workspace" / "vendor" / "quotakit", "quotakit")
    assert contract_problems(["Gate.acquire(cost=1) -> bool"], module) == ["Gate.acquire does not exist"]
    assert contract_problems(["Gate.admit(weight=1) -> bool"], module) == ["Gate.admit parameters are ['cost'], documented ['weight']"]
    assert contract_problems(["Gate.admit(cost=2) -> bool"], module) == ["Gate.admit.cost default is 1, documented 2"]
    assert contract_problems(["Gate.admit(cost) -> bool"], module) == ["Gate.admit.cost default presence differs"]
    assert contract_problems(["Gate(max_per_window, window_seconds, clock=time.monotonic, mode='sliding')"], module) == [
        "Gate keyword-only parameters differ"]


def reflect(lib_dir: Path, names: tuple[str, ...]) -> dict[str, bool]:
    done = subprocess.run([sys._base_executable, "-S", str(FIXTURES / "reflect.py"), str(lib_dir), *names], capture_output=True,
                          text=True, timeout=60, check=False)
    assert done.returncode == 0, done.stderr
    return json.loads(done.stdout)


@pytest.mark.parametrize("task_id", ALL_IDS)
def test_ng_traced_names_are_absent_and_real_names_present_in_the_pristine_library(task_id):
    """The premise of every hand trace: a guessed name is not defined, a name the reference or alt uses is."""
    spec = SPECS[task_id]
    lib_dir = task_dir(task_id) / "workspace" / "vendor" / spec["lib"]
    seen = reflect(lib_dir, spec["absent"] + spec["present"])
    assert {n for n in spec["absent"] if seen[n]} == set(), "a name traced as unresolved is defined"
    assert {n for n in spec["present"] if not seen[n]} == set(), "a name traced as resolved is not defined"
    assert set(spec["naive_names"]) <= set(spec["absent"])


def test_ng_reflect_child_sees_a_name_the_library_defines_and_one_it_does_not(tmp_path):
    lib_dir = task_dir("NG1") / "workspace" / "vendor" / "quotakit"
    assert reflect(lib_dir, ("quotakit.Gate.admit", "quotakit.Gate.nope", "quotakit.Gate.__init__:mode", "quotakit.Gate.__init__:nope")) == {
        "quotakit.Gate.admit": True, "quotakit.Gate.nope": False, "quotakit.Gate.__init__:mode": True,
        "quotakit.Gate.__init__:nope": False}
    assert reflect(tmp_path, ("quotakit.Gate",)) == {"quotakit.Gate": False}  # a library that does not import defines nothing


# ---- tables: the reader contract of W0 section 2 rev 6.6 -----------------------------------------------------------------

VARIANT_NAME = re.compile(r"^[a-z0-9]{1,16}$")


def reader_problems(text: str, overlay: dict[str, str], table: str = "VARIANTS", name_ok=VARIANT_NAME.fullmatch,
                    keys: frozenset[str] = frozenset({"flips", "clauses", "edits"})) -> list[str]:
    """The contract a W1-E reader enforces on `variants.py`, restated: one literal assignment, never executed, at most 64 KiB,
    names in the charset, edits in the replace or create form. Stands in until W1-E's reader is on main (the `ready` follow-on
    loads each `variants.py` through it)."""
    if len(text.encode("utf-8")) > 64 * 1024:
        return ["over 64 KiB"]
    try:
        tree = ast.parse(text)
    except (SyntaxError, RecursionError, MemoryError) as exc:
        return [f"unreadable: {type(exc).__name__}"]
    named = [n for n in tree.body if isinstance(n, ast.Assign | ast.AnnAssign | ast.AugAssign)
             and ast.unparse(n.target if not isinstance(n, ast.Assign) else n.targets[0]) == table]
    if len(named) != 1 or not isinstance(named[0], ast.Assign):
        return [f"not exactly one plain {table} assignment"]
    try:
        value = ast.literal_eval(named[0].value)
    except ValueError:
        return [f"{table} is not a literal"]
    problems = []
    for name, spec in value.items():
        if not name_ok(name):
            problems.append(f"{name}: bad name")
        if set(spec) - keys or not {"edits"} <= set(spec):
            problems.append(f"{name}: keys {sorted(spec)}")
        for edit in spec.get("edits", []):
            if set(edit) != {"file", "old", "new"}:
                problems.append(f"{name}: edit keys {sorted(edit)}")
            elif edit["old"] == "" and edit["file"] in overlay:
                problems.append(f"{name}: create form for {edit['file']}, which is in the reference overlay")
            elif edit["old"] != "" and overlay.get(edit["file"], "").count(edit["old"]) != 1:
                problems.append(f"{name}: old text does not occur exactly once in {edit['file']}")
    return problems


def test_ng_reader_problems_fire_on_each_red_fixture():
    overlay = {"a.py": "x = 1\n"}
    ok = 'VARIANTS = {"v": {"flips": [], "clauses": {}, "edits": [{"file": "a.py", "old": "x = 1", "new": "x = 2"}]}}\n'
    assert reader_problems(ok, overlay) == []
    assert reader_problems(ok + ok, overlay) == ["not exactly one plain VARIANTS assignment"]
    assert reader_problems('VARIANTS: dict = {}\n', overlay) == ["not exactly one plain VARIANTS assignment"]
    assert reader_problems("VARIANTS = dict()\n", overlay) == ["VARIANTS is not a literal"]
    assert reader_problems("VARIANTS = (\n", overlay) == ["unreadable: SyntaxError"]
    assert reader_problems("#" * 70000, overlay) == ["over 64 KiB"]
    assert reader_problems(ok.replace('"v"', '"v-hy"'), overlay) == ["v-hy: bad name"]
    assert reader_problems(ok.replace("x = 1", "y = 1", 1), overlay) == ["v: old text does not occur exactly once in a.py"]
    created = 'VARIANTS = {"v": {"flips": [], "edits": [{"file": "a.py", "old": "", "new": "z"}]}}\n'
    assert reader_problems(created, overlay) == ["v: create form for a.py, which is in the reference overlay"]
    assert reader_problems(created, {}) == []
    assert reader_problems('VARIANTS = {"v": {"flips": [], "edits": [{"file": "a.py"}]}}\n', overlay) == ["v: edit keys ['file']"]
    assert reader_problems('VARIANTS = {"v": {"flips": [], "clauses": {}, "extra": 1, "edits": []}}\n', overlay) == [
        "v: keys ['clauses', 'edits', 'extra', 'flips']"]


@pytest.mark.parametrize("task_id", ALL_IDS)
def test_ng_variants_and_wrong_apps_load_through_the_reader_contract(task_id):
    overlay = role_files(task_id, "reference")
    path = task_dir(task_id) / "oracle"
    text = (path / "variants.py").read_text(encoding="utf-8")
    assert reader_problems(text, overlay) == []
    assert set(variants(task_id)) == set(SPECS[task_id]["variants"])
    wa_text = (path / "wrong_apps.py").read_text(encoding="utf-8")
    assert reader_problems(wa_text, overlay, "WRONG_APPS", re.compile(r"^wa-[a-z0-9-]+$").fullmatch, frozenset({"reds", "edits"})) == []
    assert set(wrong_apps(task_id)) == set(SPECS[task_id]["wrong_apps"])
    for source in (text, wa_text):  # nothing but a docstring and the table: the file has no side effect for a reader to miss
        body = ast.parse(source).body
        assert len(body) == 2 and isinstance(body[0], ast.Expr) and isinstance(body[1], ast.Assign)


@pytest.mark.parametrize("task_id", ALL_IDS)
def test_ng_flips_are_metric_ids_and_equal_what_the_tests_and_the_trace_say(task_id):
    """`flips` lists metric ids (W0 rev 6): the primary when a hidden test turns red, the count when a traced name is added."""
    table = variants(task_id)
    for name, (reds, names) in SPECS[task_id]["variants"].items():
        derived = (["property_check_pass"] if reds else []) + (["hallucinated_symbol_errors"] if names else [])
        assert name in table, f"{name} is not in {task_id}'s variants.py"
        assert table[name]["flips"] == derived, name
        assert table[name]["clauses"] == {}, name  # the no-guessing helper records no clause (W1-L 7.1)


@pytest.mark.parametrize("task_id", ALL_IDS)
def test_ng_variant_names_follow_the_charset_rule(task_id):
    """R2-1: no `v-` prefix and no hyphen; `hallucmember` is one of the four explicit exceptions."""
    assert all(VARIANT_NAME.fullmatch(n) for n in variants(task_id))
    assert "hallucmember" in variants("NG2") and not any(n.startswith("v") and n[1:2] == "-" for n in variants(task_id))


def test_ng_vendoredit_replaces_only_the_vendored_library_and_adds_exactly_one_member():
    """The create form carries the whole edited file (a literal cannot compute it), so prove it differs from the pristine file
    by the added method alone, and that the added name is defined in the edited copy: a resolver that read the agent's copy
    would read 0 for it."""
    for task_id in ALL_IDS:
        spec = SPECS[task_id]
        assert "vendoredit" in variants(task_id), "vendoredit is not in variants.py"
        edit = next(e for e in variants(task_id)["vendoredit"]["edits"] if e["old"] == "")
        assert edit["file"] == spec["vendor_file"]
        pristine = (task_dir(task_id) / "workspace" / spec["vendor_file"]).read_text(encoding="utf-8")
        assert edit["new"].startswith(pristine) and edit["new"][len(pristine):].strip(), "not the pristine file plus an addition"
        lib = spec["lib"]
        edited_dir = _WORK / f"edited-{task_id}"
        shutil.copytree(task_dir(task_id) / "workspace" / "vendor" / lib, edited_dir)
        (edited_dir / "/".join(spec["vendor_file"].split("/")[2:])).write_text(edit["new"], encoding="utf-8", newline="\n")
        (name,) = spec["variants"]["vendoredit"][1]
        assert reflect(edited_dir, (name,)) == {name: True}
        assert reflect(task_dir(task_id) / "workspace" / "vendor" / lib, (name,)) == {name: False}


# ---- readiness ring: the hidden tests through the real correctness grader ---------------------------------------------------

@pytest.mark.parametrize("task_id", ALL_IDS)
def test_ng_stub_fails_every_hidden_test(task_id):
    """R2-7. Every hidden test fails on an assertion (never an error) against a stub that returns a unique sentinel."""
    spec, result = SPECS[task_id], graded(task_id, stub_files(task_id))
    assert result.reason is None, result.log
    assert (result.passed, result.partial) == (0, Decimal(0)), result.log
    assert result.errored == frozenset() and result.failed == set(spec["hidden"]), result.log


@pytest.mark.parametrize("task_id", ALL_IDS)
@pytest.mark.parametrize("role", ["reference", "alt"])
def test_ng_correct_solutions_pass_every_hidden_test(task_id, role):
    result = graded(task_id, role_files(task_id, role))
    assert (result.passed, result.partial, result.reason) == (1, Decimal(1), None), result.log
    assert result.red == frozenset()


@pytest.mark.parametrize("task_id", ALL_IDS)
def test_ng_naive_fails_every_hidden_test_on_its_guessed_import(task_id):
    spec, result = SPECS[task_id], graded(task_id, role_files(task_id, "naive"))
    assert (result.passed, result.partial) == (0, Decimal(0)), result.log
    assert result.errored == frozenset() and result.failed == set(spec["hidden"]), result.log
    assert "No module named" not in result.log.split("--- stderr")[0]
    assert re.search(rf"cannot import name '\w+' from '{spec['lib']}'", result.log), result.log


@pytest.mark.parametrize(("task_id", "name"), [(i, n) for i in ALL_IDS for n in SPECS[i]["wrong_apps"]])
def test_ng_each_wrong_app_turns_exactly_its_reds_red(task_id, name):
    table = wrong_apps(task_id)
    assert name in table, f"{name} is not in {task_id}'s wrong_apps.py"
    reference = role_files(task_id, "reference")
    files = apply_edits(reference, table[name]["edits"])
    assert files != reference, f"{name} carries no edit"
    assert tuple(sorted(table[name]["reds"])) == tuple(sorted(SPECS[task_id]["wrong_apps"][name]))
    result = graded(task_id, files)
    assert result.errored == frozenset(), result.log  # an AssertionError, never an import error
    assert result.failed == set(SPECS[task_id]["wrong_apps"][name]), result.log


@pytest.mark.parametrize("task_id", ALL_IDS)
def test_ng_every_hidden_test_has_a_wrong_app(task_id):
    assert {t for reds in SPECS[task_id]["wrong_apps"].values() for t in reds} == set(SPECS[task_id]["hidden"])
    without_last = {n: r for n, r in SPECS[task_id]["wrong_apps"].items() if n != list(SPECS[task_id]["wrong_apps"])[-1]}
    assert {t for reds in without_last.values() for t in reds} != set(SPECS[task_id]["hidden"])  # the fixture the sweep catches


@pytest.mark.parametrize(("task_id", "name"), [(i, n) for i in ALL_IDS for n in SPECS[i]["variants"]])
def test_ng_each_variant_moves_exactly_what_it_claims(task_id, name):
    """Hidden tests on the pristine vendor (as the strategy grades), then the flipped metric ids against `reds` and the trace."""
    table = variants(task_id)
    assert name in table, f"{name} is not in {task_id}'s variants.py"
    reference = role_files(task_id, "reference")
    files = apply_edits(reference, table[name]["edits"])
    assert files != reference, f"{name} carries no edit"
    reds, _ = SPECS[task_id]["variants"][name]
    result = graded(task_id, files)
    assert result.errored == frozenset(), result.log
    assert result.failed == set(reds), result.log


def test_ng_a_variant_edit_that_lands_in_the_agents_vendor_copy_is_undone_by_the_restore():
    """vendoredit's hidden tests must run against the pristine library: with the restore off the edited copy is what runs."""
    assert "vendoredit" in variants("NG1"), "vendoredit is not in variants.py"
    files = apply_edits(role_files("NG1", "reference"), variants("NG1")["vendoredit"]["edits"])
    edited = grading_copy("NG1", files, _WORK / "vendoredit-edited", restore_vendor=False)
    restored = grading_copy("NG1", files, _WORK / "vendoredit-restored", restore_vendor=True)
    assert "try_acquire" in (edited / SPECS["NG1"]["vendor_file"]).read_text(encoding="utf-8")
    assert "try_acquire" not in (restored / SPECS["NG1"]["vendor_file"]).read_text(encoding="utf-8")


def test_ng1_the_default_clock_test_does_not_depend_on_wall_time():
    """N-4 runs on the real clock with a 60 s window: three calls take microseconds, never near a window edge."""
    started = time.monotonic()
    result = graded("NG1", role_files("NG1", "reference"))
    assert result.red == frozenset() and time.monotonic() - started < 60


# ---- the base's test layout as data (R2-2) -----------------------------------------------------------------------------------

def is_test_path(path: str, base_paths: frozenset[str]) -> bool:
    """W0 section 13 rev 6.6, restated: test basenames, or a path the base tree already holds under a tests/test directory.
    The `ready` follow-on replaces this with `_changes.is_test_path` once X-J2a has joined and re-asserts the same rows."""
    name = path.rsplit("/", 1)[-1]
    if re.fullmatch(r"test_.*\.py|.*_test\.py|tests\.py|test\.py|conftest\.py", name):
        return True
    return path in base_paths and bool({"tests", "test"} & set(path.split("/")[:-1]))


def layout_rows(evidence: str) -> dict[str, tuple[bool, str]]:
    return {m.group(1): (m.group(2) == "yes", m.group(3))
            for m in re.finditer(r"^\| `([^`]+)` \| (yes|no) \| (test|product) \|$", evidence, re.MULTILINE)}


@pytest.mark.parametrize("task_id", ALL_IDS)
def test_ng_recorded_test_layout_matches_the_base_tree(task_id):
    base = engine_base(task_id)
    base_paths = frozenset(p.relative_to(base).as_posix() for p in base.rglob("*") if p.is_file() and ".git" not in p.relative_to(base).parts)
    recorded = layout_rows((task_dir(task_id) / "oracle" / "evidence.md").read_text(encoding="utf-8"))
    assert recorded == SPECS[task_id]["layout"]
    for path, (in_base, kind) in recorded.items():
        assert (path in base_paths) == in_base, path
        assert ("test" if is_test_path(path, base_paths) else "product") == kind, path


def test_ng_is_test_path_restatement_fires_on_each_red_fixture():
    base = frozenset({"tests/helper.py", "src/x.py"})
    assert is_test_path("pkg/tests.py", base) and is_test_path("a/conftest.py", base) and is_test_path("a/b_test.py", base)
    assert is_test_path("tests/helper.py", base)               # in the base, under a tests directory
    assert not is_test_path("tests/_new_helper.py", base)      # new, under a tests directory: product code (R2-3)
    assert not is_test_path("src/x.py", base)


# ---- R2-4: the single-turn seeded-disagreement fixture ---------------------------------------------------------------------

def test_ng1_seeded_disagreement_fixture_differs_from_the_observed_value_in_exactly_one_metric():
    fixture = config.load_yaml(FIXTURES / "ng1_seeded_disagreement.yaml")
    declared = task_yaml(fixture["base_task"])["expected"]
    seeded = {role: {**metrics, **fixture["override"]["expected"].get(role, {})} for role, metrics in declared.items()}
    changed = [(r, m) for r in declared for m in declared[r] if seeded[r][m] != declared[r][m]]
    refusal = fixture["refusal"]
    assert changed == [(refusal["role"], refusal["metric"])]
    assert seeded[refusal["role"]][refusal["metric"]] == refusal["declared"]
    assert declared[refusal["role"]][refusal["metric"]] == refusal["observed"] != refusal["declared"]
    assert refusal["code"] == "HB-RDY-003"
