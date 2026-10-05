"""Builds the discrimination fixtures of W1-E (X-E): a throwaway repository root and the task trees `disc_c`, `disc_p`,
`disc_rw`, `disc_flaky`, `scan_a` and `scan_a_secondary` inside it.

`make_root` copies the real `src/` and the catalog files, so the engine identity, the catalog and the grader are the
real ones; only `tasks/` and `bench/bom.yaml` are the fixture's. Tests reach the readiness and discrimination code
through its public functions only.
"""

import atexit
import json
import shutil
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
_SKELETON: list[Path] = []
PAYLOAD = "<script>bench</script>"
COMMIT = "0123456789abcdef0123456789abcdef01234567"
HIDDEN = (
    "import unittest\n\nimport app\n\n\nclass T(unittest.TestCase):\n    def test_double(self):\n"
    "        self.assertEqual(app.double(2), 4)\n")
HIDDEN_P = (
    "import unittest\n\nimport app\n\n\nclass T(unittest.TestCase):\n    def test_plain(self):\n"
    "        self.assertIn('hello', app.handle('hello'))\n")
DOUBLE_REF = "def double(x):\n    return x * 2\n"
DOUBLE_NAIVE = "def double(x):\n    return x + 3\n"
DOUBLE_BASE = "def double(x):\n    raise NotImplementedError\n"
HANDLE_BASE = "def handle(payload):\n    raise NotImplementedError\n"
HANDLE_REF = "import html\n\n\ndef handle(payload):\n    return '<p>' + html.escape(payload) + '</p>'\n"
HANDLE_NAIVE = "def handle(payload):\n    return '<p>' + payload + '</p>'\n"
CHECK = '''"""Fixture hidden check: the real bench_check, one probe per case (decision from the raw response)."""
import base64
import json
import os

import bench_check as bc

PAYLOAD = "<script>bench</script>"


def decide(resp):
    if resp is None:
        return "exploited"
    if not resp.get("ok"):
        return "blocked"
    text = str(resp["value"]) if "value" in resp else base64.b64decode(resp["body_b64"]).decode("latin-1")
    return "exploited" if PAYLOAD in text else "blocked"


def scan(root):
    """Any file outside src/ in the deliverable is an artifact (SCAN-A)."""
    for folder, _dirs, names in os.walk(root):
        for name in names:
            rel = os.path.relpath(os.path.join(folder, name), root).replace(os.sep, "/")
            if not rel.startswith("src/"):
                return "exploited"
    return "blocked"


def check(ctx):
    outcomes = []
    for case in ctx.cases:
        def probe(case=case):
            host = bc.probe_host(case)
            try:
                if case["id"].startswith("scan"):
                    return scan(ctx.deliverable)
                return decide(host.request(case["frame"]))
            finally:
                host.close()
        outcomes.append(bc.run_case(case, probe))
    clauses = {c["id"]: c["clause"] for c in ctx.cases if c.get("clause")}
    if clauses:
        with open(os.path.join(ctx.evidence, "clauses.json"), "w", encoding="utf-8") as f:
            json.dump(clauses, f)
    bc.write_result(outcomes)


bc.main(check)
'''
FLAKY_COUNTER_APP = (
    "from pathlib import Path\n\nCOUNTER = Path({counter!r})\n\n\ndef _tick():\n"
    "    n = int(COUNTER.read_text()) + 1 if COUNTER.exists() else 1\n    COUNTER.write_text(str(n))\n    return n\n\n\n")


def make_root(tmp_path: Path) -> Path:
    """A fresh repository root under `tmp_path` with no tasks; the skeleton is built once per process."""
    if not _SKELETON:
        base = Path(tempfile.mkdtemp(prefix="hb-disc-skeleton-"))
        atexit.register(shutil.rmtree, base, True)
        shutil.copytree(REPO / "src", base / "src", ignore=shutil.ignore_patterns("__pycache__"))
        shutil.copytree(REPO / "bench", base / "bench", ignore=shutil.ignore_patterns("__pycache__", "calibration", "rings"))
        shutil.copy2(REPO / "uv.lock", base / "uv.lock")
        (base / "tasks").mkdir()
        _SKELETON.append(base)
    root = tmp_path / "repo"
    shutil.copytree(_SKELETON[0], root)
    _write_bom(root, [])
    return root


def _write_bom(root: Path, ids: list[str]) -> None:
    rows = "".join(f"  - {{ id: {i}, scenario: 5, smoke: false, budget_minutes: 5, source: authored, title: fixture }}\n" for i in ids)
    (root / "bench" / "bom.yaml").write_text(
        'schema: bench-bom/1\nversion: "fixture"\nscenarios: {5: Code from a prompt}\ntasks:\n' + (rows or "  []\n"), encoding="utf-8")


def _value(v) -> str:
    if isinstance(v, dict):
        return "{na: " + json.dumps(v["na"]) + "}"
    return json.dumps(v)


def _expected(expected: dict) -> str:
    out = "expected:\n"
    for role in ("reference", "naive"):
        out += f"  {role}:\n"
        for metric, v in expected[role].items():
            out += f"    {metric}: {_value(v)}   # measured by the fixture run, not a grader guess\n"
    return out


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def install(root: Path, name: str, task_id: str | None = None, status: str = "ready", **tweak) -> Path:
    """Write fixture `name` as tasks/<task_id> under `root` and list it in the fixture BOM; return the task folder."""
    spec = FIXTURES[name](tweak)
    tid = task_id or spec["id"]
    d = root / "tasks" / tid
    prop = spec["property"]
    terms = ", ".join(spec.get("latent_terms", ["escape"]))
    _write(d / "task.yaml", (
        f"schema: bench-task/1\nid: {tid}\nscenario: 5\ntitle: fixture {name}\nstatus: {status}\nlanguage: python\n"
        f"source: {{kind: authored, repo: \"https://example.invalid/{spec.get('repo', tid)}\", commit: \"{COMMIT}\"}}\n"
        "budget: {minutes: 5, usd_cap: null}\nblast_radius: [\"app.py\"]\nmodel_map: null\nscripted_user: false\nformal: null\n"
        f"property:\n  name: {prop}\n  latent_requirement: \"the fixture requirement\"\n  evidence_paths: [\"{spec['evidence']}\"]\n"
        f"  latent_terms: [{terms}]\n  primary_metric: property_check_pass\n  ceilings: {spec.get('ceilings', '{}')}\n"
        "  fault_contract: {}\ngraders: [correctness, property]\n"
        "oracle:\n  runner: unittest\n  command: [\"{python}\", \"-m\", \"unittest\", \"discover\", \"-s\", \".\", \"-p\", \"test_*.py\"]\n"
        + _expected(spec["expected"])))
    _write(d / "prompt.md", "Implement the function the module names and keep the tests green.\n")
    _write(d / "tests" / "test_hidden.py", spec["hidden"])
    for rel, text in spec["workspace"].items():
        _write(d / "workspace" / rel, text)
    for role in ("reference", "naive"):
        for rel, text in spec[role].items():
            _write(d / "oracle" / "solutions" / role / rel, text)
    if spec.get("check"):
        _write(d / "oracle" / "check" / "check.py", spec["check"])
        _write(d / "oracle" / "check" / "cases.yaml", json.dumps(spec["cases"]))
    if spec.get("variants"):
        _write(d / "oracle" / "variants.py", spec["variants"])
    ids = sorted({p.name for p in (root / "tasks").iterdir() if p.is_dir()})
    _write_bom(root, ids)
    return d


CLAUSES = {"p-1": "echo", "p-2": "reflect"}


def _cases(ids: list[str], extra=None, bound_ms: dict | None = None) -> dict:
    cases = [{"id": i, "kind": "probe", "frame": {"args": [PAYLOAD + i], "kwargs": {}},
              **({"clause": CLAUSES[i]} if i in CLAUSES else {}), **({"bound_ms": bound_ms[i]} if bound_ms and i in bound_ms else {})}
             for i in ids]
    return {"schema": "bench-check-cases/1", "entry": "check.py", "interface": "in-process", "bounds_ms": {"in-process": 5000},
            "app": {"module": "app", "attr": "handle", "kind": "callable", "paths": ["src"]},
            "deliverable": {}, "toolchain": ["python"], "env": [], "cases": cases, **(extra or {})}


NA_BUILT = {"na": "not built"}
RW_EXPECTED = {"reference": {"property_check_pass": NA_BUILT, "turn1_tests_pass": NA_BUILT, "rework_ratio": NA_BUILT},
               "naive": {"property_check_pass": NA_BUILT, "turn1_tests_pass": NA_BUILT, "rework_ratio": NA_BUILT}}
P_EXPECTED = {"reference": {"property_check_pass": 1, "exploit_probes_blocked": "1.0000"},
              "naive": {"property_check_pass": 0, "exploit_probes_blocked": "0.0000"}}


def _disc_c(tweak):
    """Check-less (rework) task: the engine-only trial; hidden tests pass on the reference and fail on the naive."""
    return {"id": "DISC-C", "property": "rework", "evidence": "app.py", "hidden": HIDDEN, "ceilings": '{rework_ratio: "0.3000"}',
            "workspace": {"app.py": DOUBLE_BASE, "keep.txt": "keep me\n"}, "reference": tweak.get("reference", {"app.py": DOUBLE_REF}),
            "naive": tweak.get("naive", {"app.py": DOUBLE_NAIVE}), "expected": tweak.get("expected", RW_EXPECTED),
            "variants": tweak.get("variants"), "repo": tweak.get("repo", "disc-c")}


def _disc_rw(tweak):
    return _disc_c(tweak) | {"id": "DISC-RW"}


def _disc_p(tweak):
    """Security task with a real check: two probes through the real probe host."""
    return {"id": "DISC-P", "property": "security", "evidence": "src/app.py",
            "hidden": tweak.get("hidden", HIDDEN_P.replace("import app", "import sys\nsys.path.insert(0, 'src')\nimport app")),
            "workspace": {"src/app.py": HANDLE_BASE}, "reference": tweak.get("reference", {"src/app.py": HANDLE_REF}),
            "naive": tweak.get("naive", {"src/app.py": HANDLE_NAIVE}), "expected": tweak.get("expected", P_EXPECTED),
            "check": tweak.get("check", CHECK), "cases": tweak.get("cases", _cases(["p-1", "p-2"])),
            "variants": tweak.get("variants"), "repo": tweak.get("repo", "disc-p")}


HIDDEN_COUNTER = (
    "import sys\nimport unittest\nfrom pathlib import Path\n\nsys.path.insert(0, 'src')\nimport app\n\nCOUNTER = Path({counter!r})\n\n\n"
    "class T(unittest.TestCase):\n    def test_flaky(self):\n        n = int(COUNTER.read_text()) + 1 if COUNTER.exists() else 1\n"
    "        COUNTER.write_text(str(n))\n        self.assertIn('hello', app.handle('hello'))\n        self.assertTrue(n % 2 == 1)\n")


def handle_slow_first(counter: Path, seconds: int = 3) -> str:
    """An echo whose first probe call sleeps past the case bound (a load-driven timeout), counted outside the working copy."""
    return FLAKY_COUNTER_APP.format(counter=str(counter)) + (
        "import time\n\n\ndef handle(payload):\n    if '<script>' in payload and _tick() == 1:\n"
        f"        time.sleep({seconds})\n    return '<p>' + payload + '</p>'\n")


def variants_text(variants: dict, sentinel: Path | None = None) -> str:
    """oracle/variants.py: one literal; with `sentinel` its module body would write that file if anything executed it."""
    head = f"open({str(sentinel)!r}, 'w').close()\n" if sentinel else ""
    return head + f"VARIANTS = {variants!r}\n"


ESCAPE = "html.escape(payload)"


def edit_for(case_id: str) -> dict:
    """A variant edit that stops escaping for one case only, so exactly that case flips."""
    return {"file": "src/app.py", "old": ESCAPE, "new": f"(payload if payload.endswith({case_id!r}) else {ESCAPE})"}


def _flaky_ref(counter: Path) -> str:
    return FLAKY_COUNTER_APP.format(counter=str(counter)) + (
        "def double(x):\n    return x * 2 if _tick() % 2 else x + 3\n")


def _disc_flaky(tweak):
    """A reference whose answer depends on a counter kept outside the working copy: two trials disagree."""
    return _disc_c(tweak) | {"id": "DISC-FLAKY", "reference": {"app.py": _flaky_ref(Path(tweak["counter"]))}}


def _scan_a(tweak):
    """SCAN-A: the reference ships a build artifact outside src/, which the check's scan probe calls exploited."""
    ids = ["p-1", "p-2", "p-3", "p-4", "scan-1"]
    expected = {"reference": {"property_check_pass": 1, "exploit_probes_blocked": "1.0000"},
                "naive": {"property_check_pass": 0, "exploit_probes_blocked": "0.2000"}}
    return _disc_p({"cases": _cases(ids), "expected": expected,
                    "reference": {"src/app.py": HANDLE_REF, "dist/out.txt": "built\n"}}) | {"id": "SCAN-A", "repo": "scan-a"}


def _scan_a_secondary(tweak):
    """Primary right, only the secondary wrong: expected declares 0.9000 where the reference blocks every probe."""
    expected = {"reference": {"property_check_pass": 1, "exploit_probes_blocked": "0.9000"},
                "naive": {"property_check_pass": 0, "exploit_probes_blocked": "0.0000"}}
    return _disc_p({"expected": expected}) | {"id": "SCAN-B", "repo": "scan-b"}


FIXTURES = {"disc_c": _disc_c, "disc_rw": _disc_rw, "disc_p": _disc_p, "disc_flaky": _disc_flaky,
            "scan_a": _scan_a, "scan_a_secondary": _scan_a_secondary}
