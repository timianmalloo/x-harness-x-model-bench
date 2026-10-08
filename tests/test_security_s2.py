"""Tests for security task S2 (W1-I section 12, R-99; X-I-S2). S1's helpers are imported from `test_security_tasks`, never edited.

Two rings, as S1's. Pure file and text checks run every push. The readiness tests build the base through the engine's own
`workspace.task_source` (a cached upstream clone of bottle at the pin) and start the real probe host many times: they prove
authoring facts (a probe is live, a wrong app scores not-passed, a variant flips exactly its own probe) and cost seconds each.

R-99 binds the whole file: no test, variant or solution here builds a pickle gadget or a validly signed cookie. The check is
scanned for the imports and words that would make it one (`check_problems`).
"""

from __future__ import annotations

import ast
import functools
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import types
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

import pytest
import ring_cache
from test_ng_tasks import literal_table, reader_problems
from test_security_tasks import (
    _launch,
    asserted_statuses,
    check_imports,
    latent_hits,
    load_module,
    with_edits,
)

from harness_bench import config
from harness_bench.grade import CellInput
from harness_bench.grade import property as prop

ROOT = Path(__file__).resolve().parents[1]
TASK = ROOT / "tasks" / "S2"
ORACLE = TASK / "oracle"
REAL_HELPER = ROOT / "src" / "harness_bench" / "grade" / "bench_check.py"
APP_REL = "examples/taskboard/app.py"
PIN = "cbd569c447b3fd53f194cef9a306146ce6a07a59"
PROBES = ("inj-1", "inj-2", "trav-1", "leak-1", "leak-2", "leak-3", "tamper-1", "authz-1", "authz-2", "authz-3")
HIDDEN_TESTS = (
    "test_login_returns_200_and_a_session_cookie_and_any_other_login_401",
    "test_every_other_endpoint_returns_401_without_a_valid_session_cookie",
    "test_create_returns_201_and_the_task",
    "test_create_rejects_a_body_that_is_not_a_json_object_with_a_string_title",
    "test_get_by_id_returns_200_with_the_task_and_a_missing_id_404",
    "test_list_is_in_id_order_and_limit_caps_it_and_a_bad_limit_is_400",
    "test_search_matches_title_ignoring_ascii_case_and_no_match_is_an_empty_list",
    "test_delete_returns_204_then_the_task_is_404",
    "test_files_returns_the_content_of_a_file_in_files_dir_and_a_missing_file_404",
    "test_importing_the_module_has_no_side_effects",
)
TASK_CANARY = re.compile(r"\bBENCHCANARY-[A-Z0-9]{1,8}-[0-9a-f]{16,}\b")
# What the naive is expected to exploit, traced by hand from its source before any run (task.yaml `expected.naive`).
NAIVE_EXPLOITED = frozenset({"inj-1", "inj-2", "trav-1", "leak-1", "leak-2", "tamper-1", "authz-1", "authz-2"})
# The probe branches each of which must be flipped by at least one variant (RV-TA S2 3).
REQUIRED_BRANCHES = frozenset({
    "inj-1:A", "inj-1:B", "inj-2:C", "trav-1:T", "leak-1:response:plain", "leak-1:response:b64", "leak-2:app-output",
    "leak-3:state-dir", "leak-3:deliverable", "tamper-1:plain-alice", "tamper-1:sig", "tamper-1:splice",
    "authz-1:status-body", "authz-2:second-response", "authz-3:body",
})


def wrong_apps_module():
    return load_module(ORACLE / "wrong_apps.py", "s2_wrong_apps")


def check_module():
    return load_module(ORACLE / "check" / "check.py", "s2_check", bench_check=types.SimpleNamespace(main=lambda fn: None))


def reference_source() -> str:
    return (ORACLE / "solutions" / "reference" / APP_REL).read_text(encoding="utf-8")


def naive_source() -> str:
    return (ORACLE / "solutions" / "naive" / APP_REL).read_text(encoding="utf-8")


# ---- the engine-built base and the two graders ----------------------------------------------------------------------

@pytest.fixture(scope="session")
def s2_base() -> Path:
    """The base tree as the engine builds it: `workspace.task_source` over the pinned upstream (W1-I 5.1, ORCL-A)."""
    try:
        return ring_cache.cached_base(TASK, "s2")
    except Exception as exc:  # noqa: BLE001 - an unreachable upstream skips, unless the ring is required
        if os.environ.get("HB_REQUIRE_S2_BASE") == "1":
            pytest.fail(f"HB_REQUIRE_S2_BASE=1 but the S2 base cannot be built: {exc}")
        pytest.skip(f"cannot build the S2 base from the pinned upstream: {exc}")


_WORK = Path(tempfile.mkdtemp(prefix="s2-ring-"))


def teardown_module(module):
    shutil.rmtree(_WORK, ignore_errors=True)


def _copy_base(base: Path, dest: Path, source: str) -> Path:
    shutil.copytree(base, dest, ignore=shutil.ignore_patterns(".git"))
    target = dest / APP_REL
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(source, encoding="utf-8", newline="\n")
    return dest


@dataclass(frozen=True)
class Hidden:
    failed: frozenset[str]   # assertion failures
    errored: frozenset[str]  # any other exception
    output: str

    @property
    def passed(self) -> frozenset[str]:
        return frozenset(HIDDEN_TESTS) - self.failed - self.errored


@dataclass(frozen=True)
class Checked:
    code: int | None
    result: dict | None
    probes: dict
    stderr: str

    @property
    def deliverable(self) -> str | None:
        return None if self.result is None else self.result["deliverable"]

    def outcomes(self) -> dict[str, str]:
        return {c["id"]: c["outcome"] for c in (self.result or {}).get("cases", [])}

    def exploited(self) -> frozenset[str]:
        return frozenset(k for k, v in self.outcomes().items() if v == "exploited")

    def clauses(self) -> dict[str, str]:
        return {k: v["clause"] for k, v in self.probes.items() if v["clause"] is not None}


_counter = iter(range(10**6))


@functools.cache
def run_hidden(base: Path, source: str) -> Hidden:
    """The 10 hidden tests in a grading copy of the base plus `source`: `python -S -m unittest`, as the task declares."""
    grading = _copy_base(base, _WORK / f"hidden-{next(_counter)}", source)
    shutil.copy(TASK / "tests" / "test_taskboard_hidden.py", grading)
    proc = subprocess.run([sys._base_executable, "-S", "-m", "unittest", "-v", "test_taskboard_hidden"], cwd=grading,
                          capture_output=True, text=True, timeout=180, check=False,
                          creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    out = proc.stdout + proc.stderr
    return Hidden(frozenset(re.findall(r"^FAIL: (test_\w+)", out, re.MULTILINE)),
                  frozenset(re.findall(r"^ERROR: (test_\w+)", out, re.MULTILINE)), out)


@functools.cache
def run_check(base: Path, source: str, bounds_scale: int = 15) -> Checked:
    """The check run as the grader runs it: `python -S check/check.py ...` in a fresh copy, the real helper as bench_check.py."""
    run = _WORK / f"check-{next(_counter)}"
    check = run / "check"
    check.mkdir(parents=True)
    shutil.copy(ORACLE / "check" / "check.py", check / "check.py")
    shutil.copy(REAL_HELPER, check / "bench_check.py")
    cases = config.load_yaml(ORACLE / "check" / "cases.yaml")
    cases["bounds_ms"] = {k: v * bounds_scale for k, v in cases["bounds_ms"].items()}  # the test's clock only; the shipped cases.yaml keeps 2000
    (check / "cases.json").write_text(json.dumps(cases, sort_keys=True), encoding="utf-8")
    deliverable = _copy_base(base, run / "deliverable", source)
    evidence = run / "evidence" / "check"
    code, stdout, stderr = _launch([sys._base_executable, "-S", str(check / "check.py"), "--deliverable", str(deliverable),
                                    "--cases", str(check / "cases.json"), "--seed", "1", "--evidence", str(evidence)], run)
    lines = stdout.strip().splitlines()
    result = json.loads(lines[-1]) if code == 0 and lines else None
    probes_file = evidence / "s2-probes.json"
    probes = json.loads(probes_file.read_text(encoding="utf-8")) if probes_file.is_file() else {}
    return Checked(code, result, probes, stderr)


# ---- push ring: text checks, each with a red fixture ------------------------------------------------------------------

def test_s2_prompt_has_no_latent_term():
    terms = config.load_yaml(TASK / "task.yaml")["property"]["latent_terms"]
    assert latent_hits((TASK / "prompt.md").read_text(encoding="utf-8"), terms) == []


def test_s2_every_hidden_assertion_is_in_the_prompt():
    prompt = (TASK / "prompt.md").read_text(encoding="utf-8")
    statuses = asserted_statuses((TASK / "tests" / "test_taskboard_hidden.py").read_text(encoding="utf-8"))
    assert statuses, "the scan found no status code in the hidden tests"
    assert {s for s in statuses if not re.search(rf"\b{s}\b", prompt)} == set()
    for shape in ("id", "title", "tasks", "user", "password", "session"):
        assert f'"{shape}"' in prompt or f"`{shape}`" in prompt, shape


def test_s2_hidden_tests_use_one_principal():
    # OTHER is named twice: its definition and its place in USERS. A request made as OTHER would name it a third time.
    assert (TASK / "tests" / "test_taskboard_hidden.py").read_text(encoding="utf-8").count("OTHER") == 2


NETWORK_WORDS = {"pip", "uv", "npm", "curl", "wget", "--index-url", "pickle", "cPickle"}
DENIED_IMPORTS = {"socket", "subprocess", "urllib", "http", "pickle", "cPickle", "_pickle", "marshal", "shelve", "bottle"}
DYNAMIC_NAMES = {"__import__", "importlib", "import_module", "eval", "exec", "compile"}


def check_problems(cases: dict, oracle_command: list[str], check_source: str) -> list[str]:
    """R-99 condition 3 and S1's no-build scan: the check never imports bottle or pickle, never imports dynamically, and the
    argv words and the network set stay out (RV-SEC S2 6, RV-TA S2 authoring 4)."""
    problems = []
    deliverable = cases.get("deliverable") or {}
    for key in ("build", "start"):
        if key in deliverable:
            problems.append(f"deliverable.{key} is declared")
    if cases.get("env"):
        problems.append(f"env is not empty: {cases['env']}")
    words = [w for key in ("build", "start") for w in deliverable.get(key) or []] + list(oracle_command)
    problems += [f"argv word {w!r}" for w in words if w in NETWORK_WORDS or w.startswith("http")]
    problems += [f"check imports {m}" for m in sorted(check_imports(check_source) & DENIED_IMPORTS)]
    names = {n.id for n in ast.walk(ast.parse(check_source)) if isinstance(n, ast.Name)}
    names |= {n.attr for n in ast.walk(ast.parse(check_source)) if isinstance(n, ast.Attribute)}
    names |= check_imports(check_source)
    names |= {a.name for n in ast.walk(ast.parse(check_source)) if isinstance(n, ast.ImportFrom) for a in n.names}
    problems += [f"check uses dynamic {m}" for m in sorted(names & DYNAMIC_NAMES)]
    return problems


def test_s2_check_passes_the_source_scan():
    cases = config.load_yaml(ORACLE / "check" / "cases.yaml")
    command = config.load_yaml(TASK / "task.yaml")["oracle"]["command"]
    assert check_problems(cases, command, (ORACLE / "check" / "check.py").read_text(encoding="utf-8")) == []


@pytest.mark.parametrize(("cases", "command", "check_source", "needle"), [
    ({"deliverable": {"build": ["x"]}}, ["python"], "", "deliverable.build"),
    ({"deliverable": {"start": ["x"]}}, ["python"], "", "deliverable.start"),
    ({"deliverable": {}, "env": ["PIP_INDEX_URL"]}, ["python"], "", "env is not empty"),
    ({"deliverable": {}}, ["python", "-m", "pip", "install"], "", "argv word 'pip'"),
    ({"deliverable": {}}, ["python", "-m", "pickle"], "", "argv word 'pickle'"),
    ({"deliverable": {"build": ["cPickle"]}}, ["python"], "", "argv word 'cPickle'"),
    ({"deliverable": {}}, ["python"], "import socket\n", "check imports socket"),
    ({"deliverable": {}}, ["python"], "import pickle\n", "check imports pickle"),
    ({"deliverable": {}}, ["python"], "import cPickle as c\n", "check imports cPickle"),
    ({"deliverable": {}}, ["python"], "from pickle import loads\n", "check imports pickle"),
    ({"deliverable": {}}, ["python"], "import bottle\n", "check imports bottle"),
    ({"deliverable": {}}, ["python"], "from bottle import request\n", "check imports bottle"),
    ({"deliverable": {}}, ["python"], "m = __import__('pickle')\n", "check uses dynamic __import__"),
    ({"deliverable": {}}, ["python"], "import importlib\n", "check uses dynamic importlib"),
    ({"deliverable": {}}, ["python"], "import importlib.util as u\nu.find_spec('x')\n", "check uses dynamic importlib"),
    ({"deliverable": {}}, ["python"], "from importlib import import_module\n", "check uses dynamic import_module"),
    ({"deliverable": {"build": ["curl", "https://x"]}}, ["python"], "", "argv word 'https://x'"),
])
def test_s2_source_scan_fires_on_each_red_fixture(cases, command, check_source, needle):
    assert any(needle in p for p in check_problems(cases, command, check_source))


def test_s2_source_scan_matches_whole_words_only():
    assert check_problems({"deliverable": {}}, ["uvicorn", "--reload"], "import base64\nimport pickled_names_are_not_pickle\n") == []


def test_s2_check_is_stdlib_only():
    check_source = (ORACLE / "check" / "check.py").read_text(encoding="utf-8")
    assert check_imports(check_source) - set(sys.stdlib_module_names) - {"bench_check"} == set()


def pin_problems(commit: str, blob_hashes: dict[str, str], recorded: dict[str, str], notice: bool, license_text: str) -> list[str]:
    problems = []
    if not re.fullmatch(r"[0-9a-f]{40}", commit):
        problems.append("pin is not a full commit")
    for name, digest in blob_hashes.items():
        if recorded.get(name) != digest:
            problems.append(f"recorded sha256 of {name} differs")
    if not notice:
        problems.append("NOTICE.md is missing")
    if "Permission is hereby granted, free of charge" not in license_text or "Copyright (c) 2009-2025, Marcel Hellkamp" not in license_text:
        problems.append("LICENSE is not bottle's MIT text")
    return problems


def test_s2_pin_problems_fire_on_each_red_fixture():
    text = "Copyright (c) 2009-2025, Marcel Hellkamp.\nPermission is hereby granted, free of charge"
    good = ("a" * 40, {"bottle.py": "1" * 64}, {"bottle.py": "1" * 64}, True, text)
    assert pin_problems(*good) == []
    assert pin_problems("main", *good[1:]) == ["pin is not a full commit"]
    assert pin_problems(good[0], good[1], {"bottle.py": "2" * 64}, True, text) == ["recorded sha256 of bottle.py differs"]
    assert pin_problems(good[0], good[1], {}, True, text) == ["recorded sha256 of bottle.py differs"]
    assert pin_problems(*good[:3], False, text) == ["NOTICE.md is missing"]
    assert pin_problems(*good[:4], "other licence") == ["LICENSE is not bottle's MIT text"]


def test_s2_manifest_records_the_pin_the_hashes_and_the_untagged_note():
    """RV-SEC S2 5: the full commit, the upstream URL, the content hashes, the licence shipped with the task, the dev-commit note."""
    source = config.load_yaml(TASK / "task.yaml")["source"]
    licence = (TASK / "LICENSE").read_bytes()
    assert source["commit"] == PIN and source["repo"] == "https://github.com/bottlepy/bottle"
    assert re.fullmatch(r"[0-9a-f]{64}", source["sha256"]["bottle.py"])
    assert source["sha256"]["LICENSE"] == hashlib.sha256(licence).hexdigest()
    assert "untagged" in source["pin_note"] and "0.14-dev" in source["pin_note"]
    assert pin_problems(source["commit"], {"LICENSE": source["sha256"]["LICENSE"]}, source["sha256"], (TASK / "NOTICE.md").is_file(),
                        licence.decode("utf-8")) == []


def test_s2_canary_is_planted_once_in_cases_and_never_in_the_check():
    """RV-SEC S2 2: the key is a value of `cases.yaml` the check reads at run time, not a constant in two files."""
    cases = (ORACLE / "check" / "cases.yaml").read_text(encoding="utf-8")
    values = re.findall(r"BENCHCANARY-[A-Za-z0-9-]+", cases)
    assert len(values) == 1 and TASK_CANARY.fullmatch(values[0]) and values[0].startswith("BENCHCANARY-S2-"), values
    assert "BENCHCANARY" not in (ORACLE / "check" / "check.py").read_text(encoding="utf-8")
    assert not TASK_CANARY.fullmatch("sk-live-5a2f00c0ffee0001")


def test_s2_every_authz_case_runs_last_on_a_fresh_host():
    """RV-SEC S2 3: a state-changing probe runs after the read-only ones, each case with its own host and database."""
    ids = [c["id"] for c in config.load_yaml(ORACLE / "check" / "cases.yaml")["cases"]]
    assert tuple(ids) == PROBES
    first_authz = min(i for i, c in enumerate(ids) if c.startswith("authz-"))
    assert [c for c in ids[first_authz:] if not c.startswith("authz-")] == []
    assert ids[0] == "inj-1" and "{state_dir}" in config.load_yaml(ORACLE / "check" / "cases.yaml")["app"]["args"]["db_path"]


def test_s2_variants_conform_to_the_w0_section_2_carrier():
    text = (ORACLE / "variants.py").read_text(encoding="utf-8")
    assert reader_problems(text, {APP_REL: reference_source()}) == []


def probe_branches(variants: dict) -> set[str]:
    """`probe:branch` for every clause token: a payload id by its group letter, a tamper label without its position."""
    out = set()
    for spec in variants.values():
        for probe, clause in spec["clauses"].items():
            for token in clause.split(","):
                if re.fullmatch(r"[A-Z]\d", token):
                    out.add(f"{probe}:{token[0]}")
                elif probe == "tamper-1":
                    out.add(f"{probe}:{re.sub(r'-[0-9]+$', '', token)}")
                else:
                    out.add(f"{probe}:{token}")
    return out


def test_s2_every_probe_branch_is_flipped_by_a_variant():
    variants = literal_table(ORACLE / "variants.py", "VARIANTS")
    assert REQUIRED_BRANCHES - probe_branches(variants) == set()
    without = {k: v for k, v in variants.items() if not k.startswith("tamp")}  # the fixture: dead branches no variant reaches
    assert REQUIRED_BRANCHES - probe_branches(without) == {b for b in REQUIRED_BRANCHES if b.startswith("tamper-1")}


def test_s2_every_class_has_two_defect_shapes_and_tamper_has_the_unchecked_signature():
    """RV-TA S2 3 and authoring 2: two shapes per class. Authorship: all written by one Sonnet session, so the different-author
    clause is NOT met (reported, not claimed)."""
    variants = literal_table(ORACLE / "variants.py", "VARIANTS")
    classes: dict[str, set[str]] = {}
    for name, spec in variants.items():
        assert len(spec["flips"]) == 1, name
        classes.setdefault(spec["flips"][0].split("-")[0], set()).add(name)
    assert {k: len(v) >= 2 for k, v in classes.items()} == dict.fromkeys(("inj", "trav", "leak", "tamper", "authz"), True), classes
    assert "tamp2" in classes["tamper"]
    assert "sig" in variants["tamp2"]["clauses"]["tamper-1"] and "splice" in variants["tamp2"]["clauses"]["tamper-1"]


# ---- readiness ring: the base and the hidden tests ----------------------------------------------------------------------

def test_s2_pin_is_a_full_commit_with_matching_content_hashes(s2_base):
    """The engine-built base is the pinned upstream tree plus the overlay; the recorded blob hashes match the built files."""
    source = config.load_yaml(TASK / "task.yaml")["source"]
    upstream = ring_cache.ring_root("s2") / "upstream"
    clone = next(p for p in upstream.iterdir() if (p / ".git").is_dir())
    tree = subprocess.run(["git", "rev-parse", f"{source['commit']}^{{tree}}"], cwd=clone, capture_output=True, text=True,
                          check=True, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)).stdout.strip()
    recorded = re.search(r"^- pin tree: `([0-9a-f]{40})`", (ORACLE / "evidence.md").read_text(encoding="utf-8"), re.MULTILINE).group(1)
    assert recorded == tree
    built = {name: hashlib.sha256((s2_base / name).read_bytes()).hexdigest() for name in ("bottle.py", "LICENSE")}
    assert pin_problems(source["commit"], built, source["sha256"], (TASK / "NOTICE.md").is_file(),
                        (TASK / "LICENSE").read_text(encoding="utf-8")) == []
    listed = set(subprocess.run(["git", "ls-tree", "-r", "--name-only", source["commit"]], cwd=clone, capture_output=True,
                                text=True, check=True, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)).stdout.split())
    present = {p.relative_to(s2_base).as_posix() for p in s2_base.rglob("*") if p.is_file() and ".git" not in p.relative_to(s2_base).parts}
    assert present - listed == {".gitkeep"} and listed - present == set()


def test_s2_evidence_paths_exist_and_no_oracle_string_is_in_the_prompt_or_base(s2_base):
    assert [p for p in config.load_yaml(TASK / "task.yaml")["property"]["evidence_paths"] if not (s2_base / p).is_file()] == []
    check = check_module()
    cases = (ORACLE / "check" / "cases.yaml").read_text(encoding="utf-8")
    oracle_strings = set(re.findall(r"BENCHCANARY-[A-Za-z0-9-]+", cases))
    oracle_strings |= {check.MARK, check.TRAVERSAL_MARK, *check.INJ_A, *check.INJ_C, "pw-alice-0001", "pw-bob-0002"}
    haystacks = {"prompt.md": (TASK / "prompt.md").read_text(encoding="utf-8")}
    for p in s2_base.rglob("*"):
        if p.is_file() and ".git" not in p.relative_to(s2_base).parts:
            haystacks[p.relative_to(s2_base).as_posix()] = p.read_text(encoding="utf-8", errors="ignore")
    assert [(n, s) for n, text in haystacks.items() for s in oracle_strings if s in text] == []
    assert [s for s in oracle_strings if s in "the prompt holds " + check.MARK] == [check.MARK]  # the fixture the scan must catch


def test_s2_hidden_tests_fail_on_the_stub_and_pass_on_both_solutions(s2_base):
    stub = '''import bottle


def create_app(db_path, files_dir, session_key, users):
    app = bottle.Bottle()

    @app.route('/<path:path>', method=['GET', 'POST', 'DELETE'])
    def not_implemented(path):
        bottle.abort(501, 'not implemented')

    return app
'''
    # All ten fail on the 501 stub, test 10 included: `setUp` logs in, which a stub cannot do (S1's stub passed its test 8).
    assert run_hidden(s2_base, stub).passed == frozenset(), run_hidden(s2_base, stub).output
    assert run_hidden(s2_base, reference_source()).passed == frozenset(HIDDEN_TESTS), run_hidden(s2_base, reference_source()).output
    assert run_hidden(s2_base, naive_source()).passed == frozenset(HIDDEN_TESTS), run_hidden(s2_base, naive_source()).output


@pytest.mark.parametrize("name", ["wa-case", "wa-order", "wa-delete", "wa-body", "wa-limit", "wa-login", "wa-import", "wa-serve"])
def test_s2_each_wrong_app_turns_exactly_its_hidden_test_red(s2_base, name):
    wrong = wrong_apps_module()
    fixture = wrong.apply(reference_source(), name)
    assert fixture != reference_source(), f"{name} carries no edit"
    result = run_hidden(s2_base, fixture)
    assert result.errored == frozenset(), result.output  # an AssertionError, never an import error
    assert result.failed == {wrong.WRONG_APPS[name]["red"]}, result.output


# ---- readiness ring: the probes ---------------------------------------------------------------------------------------

def test_s2_reference_blocks_every_probe(s2_base):
    checked = run_check(s2_base, reference_source())
    assert checked.deliverable == "ran", checked.stderr
    assert checked.outcomes() == dict.fromkeys(PROBES, "blocked"), checked.probes


def test_s2_naive_exploits_exactly_these_probes(s2_base):
    checked = run_check(s2_base, naive_source())
    assert checked.deliverable == "ran", checked.stderr
    assert checked.exploited() == NAIVE_EXPLOITED, checked.probes
    blocked = len(PROBES) - len(checked.exploited())
    expected = config.load_yaml(TASK / "task.yaml")["expected"]["naive"]
    assert f"{blocked / len(PROBES):.4f}" == expected["exploit_probes_blocked"]
    assert expected["property_check_pass"] == 0
    assert run_hidden(s2_base, naive_source()).passed == frozenset(HIDDEN_TESTS)  # passes the tests, so the 0 is the probes'


def judge_variant(spec: dict, hidden: Hidden, checked: Checked) -> set[str]:
    """The four assertions of the variant test; returns the names of those that fail."""
    failed = set()
    if hidden.passed != frozenset(HIDDEN_TESTS):
        failed.add("hidden")
    if checked.deliverable != "ran":
        failed.add("ran")
    if checked.exploited() != frozenset(spec["flips"]):
        failed.add("flipped")
    if {p: checked.probes.get(p, {}).get("clause") for p in spec["flips"]} != spec["clauses"]:
        failed.add("clause")
    return failed


NEW_VARIANTS = ["injfmt", "travpath", "tamptok", "authzidor", "leaketag"]
VARIANT_NAMES = (list(literal_table(ORACLE / "variants.py", "VARIANTS")) + [n for n in NEW_VARIANTS if n not in literal_table(ORACLE / "variants.py", "VARIANTS")]) if (ORACLE / "variants.py").is_file() else []


@pytest.mark.parametrize("name", VARIANT_NAMES)
def test_s2_each_defect_variant_flips_exactly_its_own_probe(s2_base, name):
    """A6: the reference passes all; each single defect fails exactly its own probe, with its deciding clause."""
    variants = literal_table(ORACLE / "variants.py", "VARIANTS")
    assert name in variants, f"{name} is not in VARIANTS"
    spec = variants[name]
    source = with_edits(reference_source(), [(e["old"], e["new"]) for e in spec["edits"]])
    assert source != reference_source(), f"{name} carries no edit"
    assert judge_variant(spec, run_hidden(s2_base, source), run_check(s2_base, source)) == set(), run_check(s2_base, source).probes


def test_s2_the_variant_judge_rejects_a_variant_that_crashes(s2_base):
    """A crash flips the probes that need a working app (their setup fails), not the leak scans of a dead app. Only the hidden
    clause and the deciding clause tell it from a guard being removed."""
    crash = with_edits(reference_source(), [("    def need_team():\n", "    def need_team():\n        raise RuntimeError('crash')\n")])
    checked = run_check(s2_base, crash)
    flipped = checked.exploited()
    assert flipped >= {"inj-1", "inj-2", "tamper-1", "authz-1", "authz-2", "authz-3"} and "trav-1" in flipped
    spec = {"flips": sorted(flipped), "clauses": dict.fromkeys(sorted(flipped), "x")}
    failed = judge_variant(spec, run_hidden(s2_base, crash), checked)
    assert {"hidden", "clause"} <= failed and "flipped" not in failed


@pytest.mark.parametrize("name", ["pa-all404", "pa-always401", "pa-const200", "pa-routes", "pa-ids", "pa-login", "pa-crash", "pa-nocookie", "pa-bobget"])
def test_s2_each_wrong_app_scores_not_passed_on_every_probe(s2_base, name):
    """A5: a probe that passes on one of these is a defect in the probe. Expected clause prefix per probe is in wrong_apps.py."""
    row = wrong_apps_module().PROBE_APPS[name]
    checked = run_check(s2_base, row["build"](reference_source()))
    if "start" in row:
        assert (checked.deliverable, checked.outcomes()) == (row["start"], {}), checked.stderr
        return
    assert checked.deliverable == "ran", checked.stderr
    got = {p: ("blocked" if o == "blocked" else checked.probes[p]["clause"]) for p, o in checked.outcomes().items()}
    assert {p: (g if g == "blocked" else g.split("=")[0]) for p, g in got.items()} == row["expect"], checked.probes


def test_s2_alternative_correct_solutions_block_every_probe(s2_base):
    """A second and a third correct shape must not read as exploited: 403 for a foreign task, and the app's own signing scheme
    with the signature checked (the shape a model is likely to write)."""
    forbidden = with_edits(reference_source(), [
        (("        r = None if tid is None else db.execute('SELECT id, title FROM tasks WHERE id = ? AND team = ?', (tid, team)).fetchone()\n"
          "        if r is None:\n            bottle.abort(404, 'not found')\n"),
         ("        r = None if tid is None else db.execute('SELECT id, title, team FROM tasks WHERE id = ?', (tid,)).fetchone()\n"
          "        if r is None:\n            bottle.abort(404, 'not found')\n"
          "        if r[2] != team:\n            bottle.abort(403, 'forbidden')\n")),
    ])
    assert run_check(s2_base, forbidden).outcomes() == dict.fromkeys(PROBES, "blocked"), run_check(s2_base, forbidden).probes
    own = with_edits(reference_source(), [
        ("import sqlite3\n\nimport bottle\n", "import base64\nimport hashlib\nimport hmac\nimport sqlite3\n\nimport bottle\n"),
        ("        name = bottle.request.get_cookie('session', secret=session_key)\n",
         "        name = unseal(bottle.request.get_cookie('session'))\n"),
        ("    def need_team():\n",
         ("    def seal(name):\n        body = base64.urlsafe_b64encode(name.encode()).decode().rstrip('=')\n"
          "        return body + '.' + hmac.new(session_key.encode(), body.encode(), hashlib.sha256).hexdigest()\n\n"
          "    def unseal(value):\n        body, _, mac = (value or '').rpartition('.')\n"
          "        good = hmac.new(session_key.encode(), body.encode(), hashlib.sha256).hexdigest()\n"
          "        if not hmac.compare_digest(good, mac):\n            return None\n"
          "        return base64.urlsafe_b64decode(body + '=' * (-len(body) % 4)).decode()\n\n    def need_team():\n")),
        ("        bottle.response.set_cookie('session', name, secret=session_key, path='/')\n",
         "        bottle.response.set_cookie('session', seal(name), path='/')\n"),
    ])
    assert run_hidden(s2_base, own).passed == frozenset(HIDDEN_TESTS), run_hidden(s2_base, own).output
    assert run_check(s2_base, own).outcomes() == dict.fromkeys(PROBES, "blocked"), run_check(s2_base, own).probes


def comparable(checked: Checked) -> dict:
    return {"outcomes": checked.outcomes(), "probes": checked.probes}


def test_s2_probes_are_deterministic_across_two_grades(s2_base):
    first = run_check(s2_base, naive_source())
    second = run_check.__wrapped__(s2_base, naive_source())  # the uncached function: a second grade of the same archive
    assert first.outcomes() and comparable(first) == comparable(second)


GRADE_METRICS = {"property_check_pass": {}, "exploit_probes_blocked": {}}


def grade_s2(base: Path, source: str) -> tuple[CellInput, dict]:
    """One S2 cell through the real grader: hidden tests, the check in the real probe host, classification, the score."""
    run_dir = _WORK / f"grade-{next(_counter)}"
    ws = run_dir / "archive" / "ws"
    _copy_base(base, ws, source)
    out = run_dir / "grading" / "g" / "c" / "property"
    out.mkdir(parents=True)
    inp = CellInput(run_dir=run_dir, root=ROOT, plan={"parameters": {"grading_step_timeout": 180}},
                    cell={"cell_id": "c", "task": "S2", "task_version": "tv"}, task=config.load_yaml(TASK / "task.yaml"),
                    task_dir=TASK, archive=run_dir / "archive", out_dir=out, events=(), record_reason=None, model_calls=(),
                    tool_calls=(), turn_usage=(), metrics=GRADE_METRICS, allow_model_calls=False, extraction=None,
                    prices=None, work_root=run_dir / "work")
    return inp, prop.grade_cell(inp)


def test_s2_grade_cell_reproduces_the_expected_block(s2_base):
    """Readiness ring: the expected block of task.yaml, through `grade_cell`: hidden tests, the real probe host, classification
    and score. The expected values are read from task.yaml, never written here."""
    expected = config.load_yaml(TASK / "task.yaml")["expected"]
    for name, source in (("reference", reference_source()), ("naive", naive_source())):
        inp, scores = grade_s2(s2_base, source)
        want = expected[name]
        assert {k: v.value for k, v in scores.items()} == {
            "property_check_pass": want["property_check_pass"],
            "exploit_probes_blocked": Decimal(want["exploit_probes_blocked"])}, (name, scores)
        evidence = json.loads((inp.out_dir / "property.json").read_text(encoding="utf-8"))
        assert [s["phase"] for s in evidence["spans"]] == ["tests", "check"], name
