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
        shutil.copytree(REPO / "bench", base / "bench", ignore=shutil.ignore_patterns("__pycache__", "calibration", "rings", "discrimination"))
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
        + ("turns: [\"turns/2.md\"]\ngraded_snapshots: [turn-1]\n" if spec.get("turns") else "")
        + "oracle:\n  runner: unittest\n  command: [\"{python}\", \"-m\", \"unittest\", \"discover\", \"-s\", \".\", "
        + ("\"-t\", \".\", " if spec.get("turns") else "") + "\"-p\", \"test_*.py\"]\n"
        + _expected(spec["expected"])))
    if spec.get("turns"):
        _write(d / "turns" / "2.md", spec["turns"])
    _write(d / "prompt.md", "Implement the function the module names and keep the tests green.\n")
    for rel, text in (spec.get("hidden_files") or {"test_hidden.py": spec["hidden"]}).items():
        _write(d / "tests" / rel, text)
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
    return _disc_c(tweak) | {"id": "DISC-RW", "repo": tweak.get("repo", "disc-rw")}


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


def _flaky_turns_ref(counter: Path) -> dict:
    """Turns reference whose fmt, on the 8th call and every 5th after it, appends '!': a call counter kept outside the working
    copy. In the first trial the turn-1 snapshot run is call 3 and the others are never wrong; in the second the snapshot run
    is call 8, so only turn1_tests_pass differs between the trials while pass_at_1 and the final-tree run still agree."""
    t1 = FLAKY_COUNTER_APP.format(counter=str(counter)) + TURN1_REF.replace(
        "    sym, dec = RATES[cur]\n    return f'{sym}{amount:.{dec}f}'\n",
        "    n = _tick()\n    sym, dec = RATES[cur]\n    out = f'{sym}{amount:.{dec}f}'\n    return out + '!' if n > 5 and n % 5 == 3 else out\n")
    return {"turn-1/app.py": t1, "turn-2/app.py": t1.replace("2)}", "2), 'eur': ('EUR ', 2)}")}


def _disc_flaky(tweak):
    """A two-turn reference whose answer depends on a counter kept outside the working copy: two trials disagree."""
    return _disc_turns({k: v for k, v in tweak.items() if k != "counter"}) | {"id": "DISC-FLAKY", "reference": _flaky_turns_ref(Path(tweak["counter"]))}


def _scan_a(tweak):
    """SCAN-A: the reference ships a build artifact outside src/, which the check's scan probe calls exploited."""
    ids = ["p-1", "p-2", "p-3", "p-4", "scan-1"]
    expected = {"reference": {"property_check_pass": 1, "exploit_probes_blocked": "1.0000"},
                "naive": {"property_check_pass": 0, "exploit_probes_blocked": "0.2000"}}
    return _disc_p({"cases": _cases(ids), "expected": expected,
                    "reference": {"src/app.py": HANDLE_REF, "dist/out.txt": "built\n"}}) | {"id": "SCAN-A", "repo": tweak.get("repo", "scan-a")}


def _scan_a_secondary(tweak):
    """Primary right, only the secondary wrong: expected declares 0.9000 where the reference blocks every probe."""
    expected = {"reference": {"property_check_pass": 1, "exploit_probes_blocked": "0.9000"},
                "naive": {"property_check_pass": 0, "exploit_probes_blocked": "0.0000"}}
    return _disc_p({"expected": expected}) | {"id": "SCAN-B", "repo": "scan-b"}


TURN1_REF = "RATES = {'usd': ('$', 2)}\n\n\ndef fmt(amount, cur='usd'):\n    sym, dec = RATES[cur]\n    return f'{sym}{amount:.{dec}f}'\n"
TURN2_REF = TURN1_REF.replace("2)}", "2), 'eur': ('EUR ', 2)}")
TURN1_NAIVE = "def fmt(amount):\n    return f'${amount:.2f}'\n"
TURN2_NAIVE = ("def fmt(amount, cur='usd'):\n    if cur == 'eur':\n        return f'EUR {amount:.2f}'\n"
               "    return '$' + f'{amount:.2f}'\n")
T1_TESTS = ("import unittest\n\nimport app\n\n\nclass T1(unittest.TestCase):\n    def test_t1_usd(self):\n"
            "        self.assertEqual(app.fmt(1.5), '$1.50')\n")
T2_TESTS = ("import unittest\n\nimport app\n\n\nclass T2(unittest.TestCase):\n    def test_t2_eur(self):\n"
            "        self.assertEqual(app.fmt(2, 'eur'), 'EUR 2.00')\n")
TURNS_EXPECTED = {"reference": {"property_check_pass": 1, "turn1_tests_pass": 1, "rework_ratio": "0.2500"},
                  "naive": {"property_check_pass": 0, "turn1_tests_pass": 1, "rework_ratio": "1.0000"}}


T2_COUNTER_TESTS = ("import unittest\nfrom pathlib import Path\n\nCOUNTER = Path({counter!r})\n\n\nclass T2Counter(unittest.TestCase):\n"
                    "    def test_t2_counter(self):\n        n = int(COUNTER.read_text()) + 1 if COUNTER.exists() else 1\n"
                    "        COUNTER.write_text(str(n))\n        self.assertTrue(n % 2 == 1)\n")


def _disc_turns(tweak):
    """A two-turn rework task (X-J2c): the synthetic agent applies oracle/solutions/<role>/turn-<n>/ per prompt.
    With `counter` a turn-2 test passes on odd runs only, counted outside the working copy (the final-tree flaky oracle)."""
    counted = {"turn2/test_t2_counter.py": T2_COUNTER_TESTS.format(counter=str(tweak["counter"]))} if tweak.get("counter") else {}
    return {"id": "DISC-T", "property": "rework", "evidence": "app.py", "hidden": "", "ceilings": '{rework_ratio: "0.3000"}',
            "hidden_files": {"turn1/__init__.py": "", "turn1/test_t1.py": T1_TESTS, "turn2/__init__.py": "", "turn2/test_t2.py": T2_TESTS} | counted,
            "turns": "Now add the euro.\n",
            "workspace": {"app.py": "def fmt(amount):\n    raise NotImplementedError\n", "keep.txt": "keep me\n"},
            "reference": {"turn-1/app.py": TURN1_REF, "turn-2/app.py": TURN2_REF},
            "naive": {"turn-1/app.py": TURN1_NAIVE, "turn-2/app.py": TURN2_NAIVE},
            "expected": tweak.get("expected", TURNS_EXPECTED), "variants": None, "repo": "disc-t"}


def _disc_turns_v(tweak):
    """The two-turn rework task carrying declared variants (the check-less clause compare)."""
    return _disc_turns(tweak) | {"variants": tweak.get("variants")}


RS_CLIENT_REF = (
    "import time\nimport urllib.error\nimport urllib.request\n\nATTEMPTS = 3\n_OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))\n\n\n"
    "def fetch(url):\n    for attempt in range(ATTEMPTS):\n        try:\n            with _OPENER.open(url, timeout=2) as resp:\n"
    "                return resp.read().decode()\n        except urllib.error.HTTPError as exc:\n"
    "            if exc.code < 500 or attempt == ATTEMPTS - 1:\n                raise\n            time.sleep(0.1)\n")
RS_CLIENT_NAIVE = RS_CLIENT_REF.replace("ATTEMPTS = 3", "ATTEMPTS = 1")
RS_HIDDEN = ("import sys\nimport unittest\n\nsys.path.insert(0, 'src')\nimport client\n\n\nclass T(unittest.TestCase):\n"
             "    def test_retries(self):\n        self.assertGreater(client.ATTEMPTS, 1)\n")
RS_EXPECTED = {"reference": {"property_check_pass": 1, "fault_suite_pass": "1.0000", "idempotency_violations": 0},
               "naive": {"property_check_pass": 0, "fault_suite_pass": "0.0000", "idempotency_violations": 0}}


def _disc_rs(tweak):
    """X-LB1 K4, an RS-shaped task: one fault case on `interface: loopback` (shape (b)); the reference retries a 503, the naive does not."""
    case = {"id": "f-5xx", "kind": "fault", "schedule": [503, 200], "frame": {"args": ["{fake_url}/pay"], "kwargs": {}}}
    cases = {"schema": "bench-check-cases/1", "entry": "check.py", "interface": "loopback", "bounds_ms": {"in-process": 5000, "loopback": 8000},
             "app": {"module": "client", "attr": "fetch", "kind": "callable", "paths": ["src"]}, "deliverable": {}, "toolchain": ["python"],
             "env": [], "cases": [case]}
    return {"id": "DISC-RS", "property": "resilience", "evidence": "src/client.py", "hidden": RS_HIDDEN,
            "workspace": {"src/client.py": "def fetch(url):\n    raise NotImplementedError\n"},
            "reference": {"src/client.py": RS_CLIENT_REF}, "naive": {"src/client.py": RS_CLIENT_NAIVE}, "expected": RS_EXPECTED,
            "check": (REPO / "tests" / "fixtures" / "property" / "fault_check.py").read_text(encoding="utf-8"), "cases": cases,
            "variants": None, "repo": "disc-rs"}


FIXTURES = {"disc_rs": _disc_rs, "disc_turns": _disc_turns, "disc_turns_v": _disc_turns_v, "disc_c": _disc_c, "disc_rw": _disc_rw, "disc_p": _disc_p, "disc_flaky": _disc_flaky,
            "scan_a": _scan_a, "scan_a_secondary": _scan_a_secondary}
