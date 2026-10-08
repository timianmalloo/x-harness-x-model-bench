"""Tests for the simplicity tasks SM1 (tinydb) and SM2 (jmespath) (W1-L rev 2 sections 8 and 15, Erratum 1; X-SM, E4).

Two rings. Text checks run on every push. The readiness tests build each base through the engine's own
`workspace.task_source` (a cached upstream clone), then grade through the real `correctness.grade`, so they cost seconds
each and prove one-time authoring facts: a hidden test is red for its own reason, a variant flips exactly its metrics.

Every size and count here is measured by the real `grade/diffstats.py` over `grade/_changes.py` (the stand-in is deleted,
HASH-A). The tests load each
`variants.py` through W1-E's reader (X-E has not joined; `read_variants` below applies W0 section 2's rules locally).
"""

from __future__ import annotations

import ast
import re
import shutil
import subprocess
import tempfile
from decimal import Decimal
from pathlib import Path

import pytest
import ring_cache

from harness_bench import config
from harness_bench.grade import _changes, correctness, diffstats

ROOT = Path(__file__).resolve().parents[1]
TASKS = ROOT / "tasks"

# Pinned facts per task. The independent oracle for the variants: the clause that decides and the metrics that differ from
# the reference (W0 section 2 rev 6, flips of a check-less task are metric ids). Nothing here is read back from the task.
VARIANT_FACTS = {
    "SM1": {
        "bloat": ("size", ["property_check_pass", "size_vs_reference"]),
        "class": ("abstractions", ["new_abstractions", "property_check_pass", "size_vs_reference"]),
        "dep": ("dependencies", ["new_dependencies", "property_check_pass", "size_vs_reference"]),
        "docstring": (None, []),
        "launderlines": ("scope", ["property_check_pass", "size_vs_reference"]),
        "launderclass": ("abstractions", ["new_abstractions", "property_check_pass"]),
        "laundertest": ("scope", ["property_check_pass"]),
    },
    "SM2": {
        "bloat": ("size", ["property_check_pass", "size_vs_reference"]),
        "class": ("abstractions", ["new_abstractions", "property_check_pass", "size_vs_reference"]),
        "dep": ("dependencies", ["new_dependencies", "property_check_pass", "size_vs_reference"]),
        "docstring": (None, []),
        "launderlines": ("scope", ["property_check_pass", "size_vs_reference"]),
        "launderclass": ("abstractions", ["new_abstractions", "property_check_pass"]),
        "laundertest": ("scope", ["property_check_pass"]),
    },
}
DEFINITIONS = {
    "SM1": {
        "repo": "https://github.com/msiemens/tinydb", "pin": "18d73a15066a04c77f19ae9a8c03d582bd344c0d",
        "package": "tinydb", "file": "tinydb/table.py", "hidden_file": "test_first_hidden.py",
        "reference_body": "        return next(iter(self.search(cond)), None)\n",
        "stub_body": '        return "SM1-STUB-SENTINEL"\n',
        "wrong_apps": {
            "wa-last": ["test_first_match_in_insertion_order", "test_a_query_matching_several_returns_only_the_first"],
            "wa-raises": ["test_none_when_no_document_matches"],
            "wa-empty-raises": ["test_none_on_an_empty_table"],
            "wa-dict": ["test_the_result_is_a_document_with_its_doc_id"],
        },
        "alt_lines": 6, "naive_lines": 19, "created": "tinydb/_first.py", "test_dir_created": "tinydb/tests/_first.py",
    },
    "SM2": {
        "repo": "https://github.com/jmespath/jmespath.py", "pin": "2812594e69d43098ef60f81f4efc404c071b0418",
        "package": "jmespath", "file": "jmespath/__init__.py", "hidden_file": "test_search_many_hidden.py",
        "reference_body": "    parsed = compile(expression)\n    return [parsed.search(d, options=options) for d in documents]\n",
        "stub_body": '    return "SM2-STUB-SENTINEL"\n',
        "wrong_apps": {
            "wa-reversed": ["test_results_in_order_with_the_values_search_gives"],
            "wa-none-empty": ["test_an_empty_list_gives_an_empty_list"],
            "wa-noopts": ["test_options_reach_every_search"],
            "wa-reparse": ["test_the_expression_is_parsed_once"],
            "wa-lazy": ["test_an_invalid_expression_raises_parse_error_even_for_no_documents"],
        },
        "alt_lines": 9, "naive_lines": 25, "created": "jmespath/_batch.py", "test_dir_created": "jmespath/tests/_batch.py",
    },
}
IDS = sorted(DEFINITIONS)
WORK = Path(tempfile.mkdtemp(prefix="sm-ring-"))
_counter = iter(range(10**6))


def teardown_module(module):
    shutil.rmtree(WORK, ignore_errors=True)


def task_dir(tid: str) -> Path:
    return TASKS / tid


def task_yaml(tid: str) -> dict:
    return config.load_yaml(task_dir(tid) / "task.yaml")


# ---- the engine-built base ------------------------------------------------------------------------------------------

@pytest.fixture(scope="session")
def bases() -> dict:
    """tid -> the base tree as the engine builds it: `workspace.task_source` over the pinned upstream (ORCL-A)."""
    built = {}
    for tid in IDS:
        try:
            built[tid] = ring_cache.cached_base(task_dir(tid), "sm")
        except Exception as exc:  # noqa: BLE001 - an unreachable upstream skips, unless the ring is required
            import os
            if os.environ.get("HB_REQUIRE_SM_BASE") == "1":
                pytest.fail(f"HB_REQUIRE_SM_BASE=1 but the {tid} base cannot be built: {exc}")
            pytest.skip(f"cannot build the {tid} base from the pinned upstream: {exc}")
    return built


def base_py(base: Path) -> dict[str, str]:
    return {p.relative_to(base).as_posix(): p.read_text(encoding="utf-8") for p in base.rglob("*.py")
            if ".git" not in p.relative_to(base).parts}


def overlay(tid: str, role: str) -> dict[str, str]:
    root = task_dir(tid) / "oracle" / "solutions" / role
    assert root.is_dir(), f"{tid}: oracle/solutions/{role} is missing"
    return {p.relative_to(root).as_posix(): p.read_text(encoding="utf-8") for p in root.rglob("*") if p.is_file()}


# ---- grading through the real correctness grader --------------------------------------------------------------------

def hidden_run(tid: str, base: Path, files: dict[str, str]):
    """(Result, passed ids, failed ids, errored ids) of the hidden tests on base + `files`, via `correctness.grade`."""
    ws = WORK / f"ws-{next(_counter)}"
    shutil.copytree(base, ws, ignore=shutil.ignore_patterns(".git"))
    for rel, text in files.items():
        target = ws / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8", newline="\n")
    out = WORK / f"out-{next(_counter)}"
    out.mkdir()
    oracle = task_yaml(tid)["oracle"]
    result = correctness.grade(ws, task_dir(tid), oracle, out, WORK, 180, work_dir=WORK / f"w-{next(_counter)}")
    log = (out / "oracle.log").read_text(encoding="utf-8")
    seen = dict(re.findall(r"^(test_\w+) \(.*\) \.\.\. (ok|FAIL|ERROR)", log, re.MULTILINE))
    return (result, frozenset(k for k, v in seen.items() if v == "ok"), frozenset(k for k, v in seen.items() if v == "FAIL"),
            frozenset(k for k, v in seen.items() if v == "ERROR"))


def hidden_ids(tid: str) -> frozenset[str]:
    tree = ast.parse((task_dir(tid) / "tests" / DEFINITIONS[tid]["hidden_file"]).read_text(encoding="utf-8"))
    return frozenset(n.name for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name.startswith("test_"))


def metrics(tid: str, base: Path, files: dict[str, str], passed: bool) -> dict:
    spec, yaml = DEFINITIONS[tid], task_yaml(tid)
    prop = yaml["property"]
    final = {**base_py(base), **{k: v for k, v in files.items() if k.endswith(".py")}}
    got = diffstats.measure(base_py(base), final, yaml["blast_radius"], spec["package"], prop["size_reference_lines"], prop["ceilings"])
    got["size_vs_reference"] = str(got["size_vs_reference"])  # the real measure returns a Decimal at scale 4
    got["property_check_pass"] = int(passed and got["clause"] is None)
    return got


def grade_files(tid: str, base: Path, files: dict[str, str]) -> dict:
    result, passed, failed, errored = hidden_run(tid, base, files)
    out = metrics(tid, base, files, result.passed == 1)
    out["hidden_passed"] = passed
    out["hidden_failed"] = failed
    out["hidden_errored"] = errored
    out["hidden_result"] = result.passed
    return out


def with_edits(source: str, edits: list[dict]) -> str:
    for e in edits:
        assert source.count(e["old"]) == 1, f"edit target occurs {source.count(e['old'])} times: {e['old']!r}"
        source = source.replace(e["old"], e["new"])
    return source


# ---- the variant and wrong-app readers (W0 section 2 rules, applied locally until X-E's reader joins) -----------------

VARIANT_NAME = re.compile(r"^[a-z0-9]{1,16}$")


def read_literal(path: Path, name: str) -> dict:
    """Exactly one top-level `name = <literal>` assignment, read with ast.literal_eval; the file is never executed."""
    text = path.read_text(encoding="utf-8")
    assert len(text.encode()) <= 64 * 1024, f"{path.name} is over 64 KiB"
    tree = ast.parse(text)
    assigns = [n for n in tree.body if isinstance(n, (ast.Assign, ast.AnnAssign, ast.AugAssign))]
    assert len(assigns) == 1 and isinstance(assigns[0], ast.Assign), f"{path.name} needs exactly one plain top-level assignment"
    assert [t.id for t in assigns[0].targets] == [name]
    return ast.literal_eval(assigns[0].value)


def variant_problems(variants: dict, reference: dict[str, str]) -> list[str]:
    problems = []
    for name, spec in variants.items():
        if not VARIANT_NAME.match(name):
            problems.append(f"{name}: name outside ^[a-z0-9]{{1,16}}$")
        if set(spec) != {"flips", "clauses", "edits"}:
            problems.append(f"{name}: keys {sorted(spec)}")
            continue
        for edit in spec["edits"]:
            if set(edit) != {"file", "old", "new"}:
                problems.append(f"{name}: edit keys {sorted(edit)}")
            elif edit["old"] == "":
                if edit["file"] in reference:
                    problems.append(f"{name}: create form on a file the reference overlay holds: {edit['file']}")
            elif edit["file"] not in reference:
                problems.append(f"{name}: {edit['file']} is not in the reference overlay")
            elif reference[edit["file"]].count(edit["old"]) != 1:
                problems.append(f"{name}: old text occurs {reference[edit['file']].count(edit['old'])} times in {edit['file']}")
    return problems


def apply_variant(reference: dict[str, str], spec: dict) -> dict[str, str]:
    files = dict(reference)
    for edit in spec["edits"]:
        files[edit["file"]] = edit["new"] if edit["old"] == "" else with_edits(files[edit["file"]], [edit])
    return files


def reference_with_stub(tid: str) -> dict[str, str]:
    spec = DEFINITIONS[tid]
    ref = overlay(tid, "reference")
    ref[spec["file"]] = with_edits(ref[spec["file"]], [{"old": spec["reference_body"], "new": spec["stub_body"]}])
    return ref


# ---- push ring: text checks, each with a red fixture ----------------------------------------------------------------

def latent_hits(prompt: str, terms: list[str]) -> list[tuple[str, int]]:
    return [(str(t), n) for n, line in enumerate(prompt.splitlines(), 1) for t in terms if str(t).lower() in line.lower()]


@pytest.mark.parametrize("tid", IDS)
def test_prompt_has_no_latent_term(tid):
    terms = task_yaml(tid)["property"]["latent_terms"]
    assert len(terms) >= 10
    assert latent_hits((task_dir(tid) / "prompt.md").read_text(encoding="utf-8"), terms) == []


def test_latent_scan_names_the_term_and_the_line():
    assert latent_hits("first line\nuse a Factory here\n", ["factory", "strategy"]) == [("factory", 2)]
    assert latent_hits("search_many(expression, documents, options=None)", ["option"]) == [("option", 1)]  # why SM2 drops the bare term


@pytest.mark.parametrize("tid", IDS)
def test_stub_fails_every_hidden_test(tid, bases):
    """R2-7: the sentinel stub (the reference with its body replaced) turns every hidden test red, by assertion."""
    ids = hidden_ids(tid)
    assert len(ids) == 5
    got = hidden_run(tid, bases[tid], reference_with_stub(tid))
    result, passed, failed, errored = got
    assert (passed, errored) == (frozenset(), frozenset()), (passed, errored)
    assert failed == ids
    assert result.passed == 0 and result.partial_credit == Decimal(0)


@pytest.mark.parametrize("tid", IDS)
def test_hidden_tests_pass_on_reference_naive_and_alt(tid, bases):
    ids = hidden_ids(tid)
    for role in ("reference", "naive", "alt"):
        result, passed, failed, errored = hidden_run(tid, bases[tid], overlay(tid, role))
        assert (passed, failed, errored) == (ids, frozenset(), frozenset()), (role, failed, errored)
        assert result.passed == 1


@pytest.mark.parametrize("tid", IDS)
def test_each_wrong_app_turns_exactly_its_reds_red(tid, bases):
    declared = read_literal(task_dir(tid) / "oracle" / "wrong_apps.py", "WRONG_APPS")
    expected = DEFINITIONS[tid]["wrong_apps"]
    assert {k: sorted(v["reds"]) for k, v in declared.items()} == {k: sorted(v) for k, v in expected.items()}
    reference = overlay(tid, "reference")
    for name, wrong in declared.items():
        files = apply_variant(reference, wrong)
        assert files != reference, f"{name} carries no edit"
        _, passed, failed, errored = hidden_run(tid, bases[tid], files)
        assert errored == frozenset(), (name, errored)  # an AssertionError, never an import or runtime error
        assert failed == frozenset(wrong["reds"]), (name, failed)
        assert passed == hidden_ids(tid) - failed


def union_gap(ids: frozenset[str], wrong_apps: dict) -> frozenset[str]:
    return ids - {t for w in wrong_apps.values() for t in w["reds"]}


@pytest.mark.parametrize("tid", IDS)
def test_every_hidden_test_has_a_wrong_app(tid):
    declared = read_literal(task_dir(tid) / "oracle" / "wrong_apps.py", "WRONG_APPS")
    assert union_gap(hidden_ids(tid), declared) == frozenset()
    smaller = {k: v for k, v in declared.items() if k != next(iter(declared))}  # the fixture: one fixture deleted
    assert union_gap(hidden_ids(tid), smaller) != frozenset()


@pytest.mark.parametrize("tid", IDS)
def test_variants_load_by_literal_eval_and_obey_the_edit_rules(tid):
    variants = read_literal(task_dir(tid) / "oracle" / "variants.py", "VARIANTS")
    reference = overlay(tid, "reference")
    assert set(variants) == set(VARIANT_FACTS[tid]), "R2-1 names: no v-, no hyphen; neither v-laundered name"
    assert variant_problems(variants, reference) == []
    # the red fixtures: each rule fires on a bad entry
    file = DEFINITIONS[tid]["file"]
    bad = {
        "v-bloat": {"flips": [], "clauses": {}, "edits": []},
        "twice": {"flips": [], "clauses": {}, "edits": [{"file": file, "old": "\n", "new": "x"}]},
        "create": {"flips": [], "clauses": {}, "edits": [{"file": file, "old": "", "new": "x"}]},
        "absent": {"flips": [], "clauses": {}, "edits": [{"file": "nope.py", "old": "x", "new": "y"}]},
        "extra": {"flips": [], "clauses": {}, "edits": [], "note": "x"},
    }
    assert len(variant_problems(bad, reference)) == 5
    with pytest.raises(AssertionError):
        read_literal_text("VARIANTS = {}\nVARIANTS = {}\n")
    with pytest.raises(AssertionError):
        read_literal_text("VARIANTS: dict = {}\n")


def read_literal_text(text: str) -> dict:
    path = WORK / f"lit-{next(_counter)}.py"
    path.write_text(text, encoding="utf-8")
    return read_literal(path, "VARIANTS")


def test_no_old_laundering_name_survives_in_the_task_folders():
    for tid in IDS:
        for path in task_dir(tid).rglob("*"):
            if path.is_file() and path.suffix in {".py", ".yaml"}:  # evidence.md names the old names on purpose
                assert not re.search(r"v-laundered|v-bloat|v-class|v-dep|v-docstring", path.read_text(encoding="utf-8")), path


@pytest.mark.parametrize("tid", IDS)
def test_task_declares_no_check_no_build_and_no_network_names(tid):
    yaml = task_yaml(tid)
    assert not (task_dir(tid) / "oracle" / "check").exists()  # SR-L3: a check-less property has neither check nor cases.yaml
    assert yaml["graders"] == ["correctness", "property"] and yaml["property"]["name"] == "simplicity"
    assert "deliverable" not in yaml
    words = " ".join(yaml["oracle"]["command"]).lower()
    assert not re.search(r"\b(pip|uv|npm|curl|wget)\b", words)
    assert yaml["status"] in {"draft", "ready"}


def expected_problems(expected: dict) -> list[str]:
    return [f"{role}.{k}: {v!r}" for role, row in expected.items() for k, v in row.items()
            if (isinstance(v, str) and "<" in v) or (k == "size_vs_reference" and not re.fullmatch(r"\d+\.\d{4}", str(v)))
            or (k != "size_vs_reference" and not isinstance(v, int))]


@pytest.mark.parametrize("tid", IDS)
def test_expected_is_literal_when_ready(tid):
    yaml = task_yaml(tid)
    if yaml["status"] == "ready":
        assert expected_problems(yaml["expected"]) == []
    placeholder = {"naive": {"size_vs_reference": "<naive lines ÷ 2>", "new_abstractions": 3}}
    assert expected_problems(placeholder) == ["naive.size_vs_reference: '<naive lines ÷ 2>'"]
    assert expected_problems({"naive": {"new_abstractions": "3"}}) == ["naive.new_abstractions: '3'"]


@pytest.mark.parametrize("tid", IDS)
def test_provenance_text(tid):
    yaml, spec = task_yaml(tid), DEFINITIONS[tid]
    assert yaml["source"]["commit"] == spec["pin"] and re.fullmatch(r"[0-9a-f]{40}", spec["pin"])
    assert yaml["source"]["repo"] == spec["repo"] and yaml["source"]["workspace_from"] == "source"
    assert (task_dir(tid) / "NOTICE.md").is_file() and spec["pin"] in (task_dir(tid) / "NOTICE.md").read_text(encoding="utf-8")
    assert "MIT License" in (task_dir(tid) / "LICENSE").read_text(encoding="utf-8") or "Permission is hereby granted" in (
        task_dir(tid) / "LICENSE").read_text(encoding="utf-8")
    assert re.search(r"^- pin tree: `[0-9a-f]{40}`", (task_dir(tid) / "oracle" / "evidence.md").read_text(encoding="utf-8"), re.MULTILINE)


# ---- readiness ring: the base and the measured numbers ---------------------------------------------------------------

def upstream_clone(tid: str) -> Path:
    upstream = ring_cache.ring_root("sm") / "upstream"
    key = __import__("hashlib").sha256(f"{DEFINITIONS[tid]['repo']}@{DEFINITIONS[tid]['pin']}".encode()).hexdigest()[:16]
    return upstream / key


@pytest.mark.parametrize("tid", IDS)
def test_pin_tree_hash_and_engine_built_base(tid, bases):
    clone, pin = upstream_clone(tid), DEFINITIONS[tid]["pin"]
    tree = subprocess.run(["git", "rev-parse", f"{pin}^{{tree}}"], cwd=clone, capture_output=True, text=True, check=True, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)).stdout.strip()
    evidence = (task_dir(tid) / "oracle" / "evidence.md").read_text(encoding="utf-8")
    assert re.search(r"^- pin tree: `([0-9a-f]{40})`", evidence, re.MULTILINE).group(1) == tree
    assert f"tree is {tree}" in (task_dir(tid) / "task.yaml").read_text(encoding="utf-8")
    listed = set(subprocess.run(["git", "ls-tree", "-r", "--name-only", pin], cwd=clone, capture_output=True, text=True, check=True, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)).stdout.split())
    built = {p.relative_to(bases[tid]).as_posix() for p in bases[tid].rglob("*") if p.is_file() and ".git" not in p.relative_to(bases[tid]).parts}
    assert built - listed == {".gitkeep"} and listed - built == set()


@pytest.mark.parametrize("tid", IDS)
def test_evidence_paths_and_blast_radius_exist_in_the_base(tid, bases):
    yaml = task_yaml(tid)
    assert all((bases[tid] / p).is_file() for p in yaml["property"]["evidence_paths"] + yaml["blast_radius"])
    assert yaml["blast_radius"] == [DEFINITIONS[tid]["file"]]


LAYOUT = re.compile(r"^- `([^`]+)` (base|new) (test|product)$", re.MULTILINE)


@pytest.mark.parametrize("tid", IDS)
def test_base_test_layout_is_recorded_and_classified_by_is_test_path(tid, bases):
    """R2-2: the layout data in evidence.md, classified by W0 rev 6.6's rule (the stand-in until X-J2a's function joins)."""
    base_paths = frozenset(p.relative_to(bases[tid]).as_posix() for p in bases[tid].rglob("*") if p.is_file()
                           and ".git" not in p.relative_to(bases[tid]).parts)
    rows = LAYOUT.findall((task_dir(tid) / "oracle" / "evidence.md").read_text(encoding="utf-8"))
    assert len(rows) >= 6 and {r[1] for r in rows} == {"base", "new"}
    for path, where, kind in rows:
        assert (path in base_paths) == (where == "base"), path
        assert _changes.is_test_path(path, base_paths) == (kind == "test"), path
    new_paths = {p for p, w, k in rows if w == "new"}
    spec = DEFINITIONS[tid]
    assert {spec["test_dir_created"], spec["created"]} <= new_paths
    assert any(p.startswith("tests/") for p in base_paths)  # the base has a top-level test directory
    assert not any(p == spec["test_dir_created"] for p in base_paths)


@pytest.mark.parametrize("tid", IDS)
def test_frozen_reference_size_equals_function_output(tid, bases):
    """HASH-A: `size_reference_lines` is what the counting function says of the committed reference diff."""
    got = grade_files(tid, bases[tid], overlay(tid, "reference"))
    assert got["inside_lines"] == task_yaml(tid)["property"]["size_reference_lines"]
    assert got["outside_radius_lines"] == 0


@pytest.mark.parametrize("tid", IDS)
def test_reference_and_naive_measure_what_expected_records(tid, bases):
    expected = task_yaml(tid)["expected"]
    for role in ("reference", "naive"):
        got = grade_files(tid, bases[tid], overlay(tid, role))
        want = expected[role]
        assert {k: got[k] for k in ("size_vs_reference", "new_abstractions", "new_dependencies", "property_check_pass")} == want, role
    assert grade_files(tid, bases[tid], overlay(tid, "naive"))["inside_lines"] == DEFINITIONS[tid]["naive_lines"]
    assert Decimal(expected["naive"]["size_vs_reference"]) >= (Decimal(6) if tid == "SM1" else Decimal(8))


@pytest.mark.parametrize("tid", IDS)
def test_an_alternative_honest_solution_passes_exactly_on_the_ceiling(tid, bases):
    """W1-L assume A5 and the ceiling: the honest `alt` scores 1 with `size_vs_reference` on the ceiling."""
    got = grade_files(tid, bases[tid], overlay(tid, "alt"))
    ceilings = task_yaml(tid)["property"]["ceilings"]
    assert got["inside_lines"] == DEFINITIONS[tid]["alt_lines"]
    assert got["size_vs_reference"] == ceilings["size_vs_reference"]
    assert (got["clause"], got["property_check_pass"], got["outside_radius_lines"]) == (None, 1, 0)
    over = grade_files(tid, bases[tid], {**overlay(tid, "alt"), DEFINITIONS[tid]["file"]: overlay(tid, "alt")[DEFINITIONS[tid]["file"]] + "\nx = 1\n"})
    assert over["clause"] == "size"  # one product line over the ceiling fails: the boundary is real


@pytest.mark.parametrize("tid", IDS)
def test_each_variant_flips_exactly_its_metrics_and_clause(tid, bases):
    variants = read_literal(task_dir(tid) / "oracle" / "variants.py", "VARIANTS")
    reference = overlay(tid, "reference")
    ref = grade_files(tid, bases[tid], reference)
    keys = ("size_vs_reference", "new_abstractions", "new_dependencies", "property_check_pass")
    assert set(VARIANT_FACTS[tid]) <= set(variants), set(VARIANT_FACTS[tid]) - set(variants)
    for name, (clause, flips) in VARIANT_FACTS[tid].items():
        spec = variants[name]
        files = apply_variant(reference, spec)
        assert files != reference, f"{name} carries no edit"
        got = grade_files(tid, bases[tid], files)
        assert (got["hidden_passed"], got["hidden_result"]) == (hidden_ids(tid), 1), (name, got["hidden_failed"])
        assert got["clause"] == clause, (name, got)
        assert sorted(k for k in keys if got[k] != ref[k]) == flips, (name, got)
        assert sorted(spec["flips"]) == flips, name
        assert spec["clauses"] == ({"property_check_pass": clause} if "property_check_pass" in flips else {}), name


@pytest.mark.parametrize("tid", IDS)
def test_every_clause_has_a_variant_and_the_launder_pair_separates(tid, bases):
    assert {c for c, _ in VARIANT_FACTS[tid].values() if c} == {"size", "abstractions", "dependencies", "scope"}
    spec, ceilings = DEFINITIONS[tid], task_yaml(tid)["property"]["ceilings"]
    variants = read_literal(task_dir(tid) / "oracle" / "variants.py", "VARIANTS")
    reference = overlay(tid, "reference")
    assert {"launderlines", "launderclass", "laundertest"} <= set(variants)
    lines = apply_variant(reference, variants["launderlines"])
    got = grade_files(tid, bases[tid], lines)
    assert (got["inside_lines"], got["outside_radius_lines"]) == (task_yaml(tid)["property"]["size_reference_lines"] + 1, 25)  # the import line is the one added
    assert Decimal(got["size_vs_reference"]) <= Decimal(ceilings["size_vs_reference"]) and got["new_abstractions"] == got["new_dependencies"] == 0
    cls = grade_files(tid, bases[tid], apply_variant(reference, variants["launderclass"]))
    assert (cls["outside_radius_lines"], cls["new_abstractions"], cls["size_vs_reference"]) == (2, 2, "1.0000")
    assert cls["outside_radius_lines"] <= ceilings["outside_radius_lines"]  # under the allowance: only clause (a) fails it
    # the mutant that drops clause (b) (the ceiling lifted) lets launderlines and laundertest through: they fail by it alone
    lifted = {**ceilings, "outside_radius_lines": 10**6}
    for name in ("launderlines", "laundertest"):
        files = apply_variant(reference, variants[name])
        final = {**base_py(bases[tid]), **{k: v for k, v in files.items() if k.endswith(".py")}}
        alone = diffstats.measure(base_py(bases[tid]), final, task_yaml(tid)["blast_radius"], spec["package"],
                                task_yaml(tid)["property"]["size_reference_lines"], lifted)
        assert alone["clause"] is None, name


@pytest.mark.parametrize("tid", IDS)
def test_laundertest_is_counted_unless_a_test_directory_part_is_exempt(tid, bases, monkeypatch):
    """R2-3: new product code under `<pkg>/tests/` is outside code. The mutant exempting any `test` directory part misses it."""
    variants = read_literal(task_dir(tid) / "oracle" / "variants.py", "VARIANTS")
    assert "laundertest" in variants
    files = apply_variant(overlay(tid, "reference"), variants["laundertest"])
    assert DEFINITIONS[tid]["test_dir_created"] in files
    assert grade_files(tid, bases[tid], files)["clause"] == "scope"

    def exempt_any_test_dir(path, base_paths):
        return any(p in ("tests", "test") for p in path.split("/")[:-1]) or path.rsplit("/", 1)[-1].startswith("test_")

    monkeypatch.setattr(_changes, "is_test_path", exempt_any_test_dir)
    mutated = grade_files(tid, bases[tid], files)
    assert (mutated["clause"], mutated["property_check_pass"]) == (None, 1)  # the reference's verdict: the variant would not discriminate


def test_product_lines_ignores_docstrings_blank_and_comment_lines(tmp_path):
    f = tmp_path / "m.py"
    f.write_text('def f():\n    """doc\n\n    more\n    """\n    # note\n\n    return 1\n', encoding="utf-8")
    assert _changes.product_lines(f) == ["def f():", "    return 1"]
    f.write_text("x = 1  # kept\n", encoding="utf-8")
    assert _changes.product_lines(f) == ["x = 1  # kept"]
