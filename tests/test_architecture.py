"""Structural rules (design test plan D0 and D3), checked on the source, not by review.

- D3: engine, driver and archive never import grade or report; only procs.py calls subprocess; only
  gitsafe.py runs git; only driver.py speaks ACP.
- D0: no path of the retired coordinator runner (`coord-run/1`) remains in the benchmark's code, its
  skills (and their synced copies) or its README (owner ruling: the benchmark never runs in the
  coordinator's runner).
"""

import ast
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src" / "harness_bench"
MODULES = sorted(SRC.rglob("*.py"))
SUBPROCESS_CALLS = {"run", "Popen", "call", "check_call", "check_output", "getoutput", "getstatusoutput"}
OS_SPAWNS = {"system", "popen", "startfile", "execv", "execve", "spawnv", "spawnve"}
ACP_METHODS = {"initialize", "session/new", "session/prompt", "session/set_mode", "session/cancel", "session/request_permission"}


def _tree(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def _imports(tree: ast.Module) -> set[str]:
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names |= {a.name for a in node.names}
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
            names |= {f"{node.module}.{a.name}" for a in node.names}
    return names


@pytest.mark.parametrize("name", ["engine", "driver", "archive"])
def test_the_run_path_never_imports_grading_or_reports(name):
    imported = _imports(_tree(SRC / f"{name}.py"))
    assert not {i for i in imported if i.startswith(("harness_bench.grade", "harness_bench.report"))}


def test_only_procs_calls_subprocess_or_spawns():
    offenders = []
    for path in MODULES:
        for node in ast.walk(_tree(path)):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and isinstance(node.func.value, ast.Name):
                owner, attr = node.func.value.id, node.func.attr
                if ((owner == "subprocess" and attr in SUBPROCESS_CALLS) or (owner == "os" and attr in OS_SPAWNS)) and path != SRC / "procs.py":
                    offenders.append(f"{path.relative_to(ROOT).as_posix()}:{node.lineno}")
    assert offenders == []


def _string_constants(path: Path) -> set[str]:
    return {n.value for n in ast.walk(_tree(path)) if isinstance(n, ast.Constant) and isinstance(n.value, str)}


def test_only_gitsafe_runs_git():
    assert [p.name for p in MODULES if {"git", "git.exe"} & _string_constants(p)] == ["gitsafe.py"]


def test_only_driver_speaks_acp():
    assert [p.name for p in MODULES if ACP_METHODS - {"initialize"} & _string_constants(p) or
            ("initialize" in _string_constants(p) and "session/new" in _string_constants(p))] == ["driver.py"]


def test_a_judge_backend_is_reached_only_through_egress_check_and_release():
    """US-47 / ADR-0005 / R-60 / Codex F2: in `gateway/`, a backend is reached only as `egress.check(...).release(b)`.

    Bound to behaviour, not to a module name. A *sink* in a gateway module is a call into `harness_bench.procs`
    (the only spawner, D3; GW-I "spawns through procs.run", plan row W3-GW-I); a call rooted at a parameter that
    is not annotated as plain data (an injected backend: `backend(p)`, `backend.judge(p)`); or a call on
    `self.<attr>` assigned from such a parameter or from a spawner. A sink is *released* when it sits inside the
    arguments of `.release(...)` called on an `egress.check(...)` result (directly, or through a local name
    assigned from one). A top-level function or class holding an unreleased sink is a *spawner*: every reference
    to it must be released, at least one must be, and no module outside `gateway/` may import it. A gateway
    package that reaches no backend through a release fails. Outside `gateway/`, only an allowlist of today's
    callers may reach procs, and a built `grade/judge.py` with no `gateway/` fails. Today there is no gateway
    package: the scan finds nothing, and the self-check proves the rule fires on each shape it must catch.

    For GW-I: annotate data parameters (`p: str`); an unannotated parameter whose method is called is treated as a
    backend. `self.v = egress.check(...)` then `self.v.release(b)` is reported (a fail-closed false positive: only a
    local name counts as a checked result); release from the check call or a local. Residual: dynamic dispatch
    (getattr, importlib) and an annotation that lies about a backend's type.
    """
    gateway = ("harness_bench", "gateway")

    def package(rel: str) -> tuple[str, ...]:
        return tuple(Path(rel).with_suffix("").parts[1:-1])  # rel is "src/harness_bench/.../x.py"

    def aliases(rel: str, tree: ast.Module) -> dict[str, str]:
        out, pkg = {}, package(rel)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                out |= {(a.asname or a.name.split(".")[0]): (a.name if a.asname else a.name.split(".")[0])
                        for a in node.names}
            elif isinstance(node, ast.ImportFrom):
                base = list(pkg[:len(pkg) - node.level + 1]) if node.level else []
                module = ".".join(base + ([node.module] if node.module else []))
                out |= {(a.asname or a.name): f"{module}.{a.name}" for a in node.names}
        return out

    def dotted(expr: ast.expr, names: dict[str, str]) -> str:
        if isinstance(expr, ast.Name):
            return names.get(expr.id, "")
        return f"{dotted(expr.value, names)}.{expr.attr}" if isinstance(expr, ast.Attribute) else ""

    data_types = {"str", "bytes", "int", "float", "bool", "dict", "list", "tuple", "set", "frozenset", "Path"}

    def data_typed(ann: ast.expr | None) -> bool:
        """An annotation naming only plain data (str, list[str], Path | None, ...): such a parameter is no backend."""
        if isinstance(ann, (ast.Name, ast.Attribute)):
            return (ann.id if isinstance(ann, ast.Name) else ann.attr) in data_types
        if isinstance(ann, ast.Subscript):
            return data_typed(ann.value)
        if isinstance(ann, ast.BinOp) and isinstance(ann.op, ast.BitOr):
            return data_typed(ann.left) and data_typed(ann.right)
        return isinstance(ann, ast.Constant) and ann.value is None

    def root(expr: ast.expr) -> tuple[str | None, list[str]]:
        """The name a callee chain starts from, and its attributes: `self.backend.judge` -> ("self", [backend, judge])."""
        attrs = []
        while isinstance(expr, (ast.Attribute, ast.Call, ast.Subscript)):
            if isinstance(expr, ast.Attribute):
                attrs.append(expr.attr)
            expr = expr.func if isinstance(expr, ast.Call) else expr.value
        return (expr.id if isinstance(expr, ast.Name) else None), attrs[::-1]

    def sink_calls(top: ast.stmt, al: dict[str, str], rel_released: set[int]) -> list[ast.Call]:
        """Unreleased backend calls in one top-level statement: a call into procs; a call rooted at a parameter that
        is not plain data (an injected backend, `backend(p)` or `backend.judge(p)`); or a call on `self.<attr>` where
        the attribute is assigned from such a parameter (Fable Major 2). `self.<attr>` assigned from a spawner needs
        no rule here: that assignment is itself an unreleased reference to the spawner, which offenders reports."""
        receivers = {f.args.args[0].arg for c in ast.walk(top) if isinstance(c, ast.ClassDef) for f in c.body
                     if isinstance(f, (ast.FunctionDef, ast.AsyncFunctionDef)) and f.args.args}
        params = {a.arg for f in ast.walk(top) if isinstance(f, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda))
                  for a in [*f.args.posonlyargs, *f.args.args, *f.args.kwonlyargs]
                  if a.arg not in receivers and not data_typed(a.annotation)}
        tainted = {t.attr for n in ast.walk(top) if isinstance(n, ast.Assign) for t in n.targets
                   if isinstance(t, ast.Attribute) and isinstance(t.value, ast.Name) and t.value.id in receivers
                   and any(isinstance(v, ast.Name) and v.id in params for v in ast.walk(n.value))}

        def is_sink(call: ast.Call) -> bool:
            base, attrs = root(call.func)
            return ("procs" in dotted(call.func, al).split(".")[1:] or base in params or
                    base in receivers and bool(attrs) and attrs[0] in tainted)
        return [n for n in ast.walk(top) if isinstance(n, ast.Call) and id(n) not in rel_released and is_sink(n)]

    def offenders(modules: dict[str, str]) -> list[str]:
        trees = {rel: ast.parse(source) for rel, source in modules.items()}
        names = {rel: aliases(rel, tree) for rel, tree in trees.items()}
        inside = {rel for rel in trees if package(rel)[:2] == gateway}
        found, spawners, released = [], set(), {}
        for rel in inside:
            tree, al = trees[rel], names[rel]
            def is_check(n: ast.AST, al: dict[str, str] = al) -> bool:
                return isinstance(n, ast.Call) and dotted(n.func, al) == "harness_bench.egress.check"

            checked = {t.id for n in ast.walk(tree) if isinstance(n, ast.Assign) and is_check(n.value)
                       for t in n.targets if isinstance(t, ast.Name)}
            released[rel] = {id(sub) for n in ast.walk(tree)
                             if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr == "release"
                             and (is_check(n.func.value) or isinstance(n.func.value, ast.Name) and n.func.value.id in checked)
                             for arg in [*n.args, *(k.value for k in n.keywords)] for sub in ast.walk(arg)}
        for rel in inside:
            for top in trees[rel].body:
                sinks = sink_calls(top, names[rel], released[rel])
                if sinks and isinstance(top, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                    spawners.add(top.name)
                elif sinks:
                    found.append(f"{rel}:{sinks[0].lineno}: a backend call outside any release")
        bound, used = False, set()
        for rel in inside:
            for n in ast.walk(trees[rel]):
                ref = n.id if isinstance(n, ast.Name) else n.attr if isinstance(n, ast.Attribute) else None
                if ref in spawners and id(n) in released[rel]:
                    used.add(ref)
                elif ref in spawners:
                    found.append(f"{rel}:{n.lineno}: {ref} reached without egress.check(...).release")
            bound |= any(isinstance(n, ast.Call) and id(n) in released[rel] and
                         dotted(n.func, names[rel]).startswith("harness_bench.procs") for n in ast.walk(trees[rel]))
        found += [f"gateway/: {s} is never released through egress.check(...).release" for s in spawners - used]
        if inside and not (bound or used):
            found.append("gateway/: no backend is reached through egress.check(...).release")
        for rel in set(trees) - inside:
            found += [f"{rel}: imports the spawner {target}" for target in names[rel].values()
                      if target.startswith("harness_bench.gateway.") and target.rsplit(".", 1)[1] in spawners]
        # Fable Major 1: outside gateway/, only today's procs callers reach procs (read 2026-09-25, not recalled:
        # engine spawns; gitsafe, grade/correctness, plan, tools and workspace run; driver only names CellProcess in
        # annotations). A new caller - a judge spawned from grade/judge.py above all - fails until added here on purpose.
        allowed = {"engine", "gitsafe", "grade/correctness", "plan", "procs", "tools", "workspace"}
        for rel in sorted(set(trees) - inside):
            if Path(rel).with_suffix("").as_posix().removeprefix("src/harness_bench/") in allowed:
                continue
            typed = {id(sub) for n in ast.walk(trees[rel]) for ann in
                     ([n.annotation] if isinstance(n, (ast.arg, ast.AnnAssign)) else
                      [n.returns] if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) else [])
                     if ann is not None for sub in ast.walk(ann)}
            found += sorted({f"{rel}:{n.lineno}: reaches harness_bench.procs outside the allowlist"
                             for n in ast.walk(trees[rel]) if isinstance(n, (ast.Name, ast.Attribute))
                             and id(n) not in typed and "procs" in dotted(n, names[rel]).split(".")[1:]})
        # A built judge with no gateway is unbound (assume: GW-I builds judging in grade/judge.py beside gateway/, as
        # plan row W3-GW-I assigns it; if judging lands elsewhere, name that module here). Chosen over a dated
        # assume: it fires on the event, not on a calendar.
        judge = "src/harness_bench/grade/judge.py"
        # A stub is either shape the codebase has used: `raise not_built(...)` (phase 1) or `raise NotImplementedError`
        # from `grade_cell` (W3-GRADE-CORE s1 retired not_built).
        if judge in trees and not inside and not any(
                (isinstance(n, ast.Call) and dotted(n.func, names[judge]) == "harness_bench.grade.not_built")
                or (isinstance(n, ast.Raise) and n.exc is not None and "NotImplementedError" in ast.unparse(n.exc))
                for n in ast.walk(trees[judge])):
            found.append(f"{judge}: the judge is built but there is no gateway/ package")
        return found

    # Self-check (Codex F2): synthetic packages, parsed and never imported or run. Each names whether it must fire.
    gw, run = "src/harness_bench/gateway/", "procs.run(['judge-cli', p], None, None, 60)"
    cli = f"from harness_bench import procs\n\nclass HeadlessCli:\n    def __call__(self, p):\n        return {run}\n"
    released = ("from harness_bench import egress\nfrom .cli import HeadlessCli\n\ndef judge(p, operator):\n"
                "    return egress.check(p, destination='judge:x', operator=operator).release(HeadlessCli())\n")
    cases = {
        "codex-f2-probe": (True, {gw + "backend.py": "def send(payload, backend):\n    return backend(payload)\n"}),
        "imports-egress-without-using-it": (True, {gw + "judge.py": "from harness_bench import egress, procs\n\n"
                                                   f"def judge(p):\n    return {run}\n"}),
        "releases-a-fabricated-verdict": (True, {gw + "judge.py": "from harness_bench import egress, procs\n\n"
                                                 "def judge(p):\n    return egress.Verdict('judge:x', 'h', (), p)"
                                                 f".release(lambda p: {run})\n"}),
        "ignores-the-check-result": (True, {gw + "cli.py": cli, gw + "__init__.py":
                                            "from harness_bench import egress\nfrom .cli import HeadlessCli\n\n"
                                            "def judge(p, operator):\n    egress.check(p, destination='judge:x', "
                                            "operator=operator)\n    return HeadlessCli()(p)\n"}),
        "a-grader-imports-the-spawner": (True, {gw + "cli.py": cli, gw + "__init__.py": released,
                                                "src/harness_bench/grade/judge.py":
                                                "from harness_bench.gateway.cli import HeadlessCli\n"}),
        "a-gateway-that-reaches-no-backend": (True, {gw + "__init__.py": "def judge(p):\n    return None\n"}),
        "the-probe-beside-a-released-backend": (True, {gw + "cli.py": cli, gw + "__init__.py": released, gw +
                                                       "backend.py": "def send(payload, backend):\n    return backend(payload)\n"}),
        "released-spawner-class": (False, {gw + "cli.py": cli, gw + "__init__.py": released,
                                           "src/harness_bench/grade/judge.py": "from harness_bench.gateway import judge\n"}),
        "released-lambda-via-a-checked-variable": (False, {gw + "__init__.py":
                                                           "from harness_bench.egress import check\n"
                                                           "from harness_bench.procs import run\n\n"
                                                           "def judge(p, operator):\n"
                                                           "    verdict = check(p, destination='judge:x', operator=operator)\n"
                                                           f"    return verdict.release(lambda p: {run[6:]})\n"}),
        # Fable re-review Major 1: outside gateway/, only today's procs callers may reach procs.
        "the-judge-grader-spawns-the-judge-cli": (True, {"src/harness_bench/grade/judge.py":
                                                         f"from harness_bench import procs\n\ndef grade(p):\n    return {run}\n"}),
        "a-new-grader-spawns-through-procs": (True, {"src/harness_bench/grade/jury.py":
                                                     f"from harness_bench import procs\n\ndef ask(p):\n    return {run}\n"}),
        "a-new-module-aliases-procs-run": (True, {"src/harness_bench/grade/mutation.py":
                                                  "from harness_bench.procs import run as r\n\nspawn = r\n"}),
        "an-allowlisted-caller": (False, {"src/harness_bench/gitsafe.py":
                                          "from harness_bench import procs\n\ndef git(a):\n"
                                          "    return procs.run(['git', *a], None, None, 60)\n"}),
        "a-type-only-use-of-procs": (False, {"src/harness_bench/driver.py": "from harness_bench.procs import CellProcess\n\n"
                                             "def turn(cell: CellProcess) -> None:\n    return None\n"}),
        "a-built-judge-without-a-gateway": (True, {"src/harness_bench/grade/judge.py":
                                                   "def grade(run_dir, task_dir):\n    return None\n"}),
        "the-judge-stub-without-a-gateway": (False, {"src/harness_bench/grade/judge.py":
                                                     "from harness_bench.grade import not_built\n\n"
                                                     "def grade(run_dir, task_dir):\n    raise not_built('judge', 'S-09')\n"}),
        "the-current-judge-stub-without-a-gateway": (False, {"src/harness_bench/grade/judge.py":
                                                             "def grade_cell(inp):\n"
                                                             "    raise NotImplementedError('grade.judge is not built yet')\n"}),
        # Fable Major 2: an injected backend called by method, or kept on self, is still a backend call.
        "a-method-on-an-injected-backend": (True, {gw + "cli.py": cli, gw + "__init__.py": released, gw + "direct.py":
                                                   "def judge_direct(p, backend):\n    return backend.judge(p)\n"}),
        "self-attribute-from-an-injected-backend": (True, {gw + "cli.py": cli, gw + "__init__.py": released, gw + "pool.py":
                                                           "class Pool:\n    def __init__(self, backend):\n"
                                                           "        self.backend = backend\n\n    def judge(self, p):\n"
                                                           "        return self.backend.judge(p)\n"}),
        # Review w3-gwi-1 F2 (Fable): a local alias of an injected backend is still the backend; the exact probe P4.
        "a-local-alias-of-an-injected-backend": (True, {gw + "cli.py": cli, gw + "__init__.py": released, gw + "leak.py":
                                                        "def _leak(backend: Backend, text: str):\n    b = backend\n"
                                                        "    return b.judge(text)\n"}),
        "an-alias-chain-or-a-bound-method": (True, {gw + "cli.py": cli, gw + "__init__.py": released, gw + "leak.py":
                                                    "def _leak(backend, text: str):\n    a = backend\n"
                                                    "    send = a.judge\n    return send(text)\n"}),
        "a-local-from-a-module-call-is-data": (False, {gw + "cli.py": cli, gw + "__init__.py": released, gw + "hash.py":
                                                       "import hashlib\nfrom harness_bench.gateway import request\n\n"
                                                       "def digest(inputs, entries: tuple):\n"
                                                       "    rendered = request.render(inputs.rubric, entries)\n"
                                                       "    return hashlib.sha256(rendered.text.encode()).hexdigest()\n"}),
        "self-attribute-from-a-spawner": (True, {gw + "cli.py": cli, gw + "__init__.py": released, gw + "pool.py":
                                                 "from .cli import HeadlessCli\n\nclass Pool:\n    def __init__(self):\n"
                                                 "        self.backend = HeadlessCli()\n\n    def judge(self, p):\n"
                                                 "        return self.backend(p)\n"}),
        "a-typed-data-parameter": (False, {gw + "cli.py": cli, gw + "payload.py":
                                           "def build(item: str) -> str:\n    return item.strip()\n",
                                           gw + "__init__.py": released.replace("from .cli", "from .payload import build\nfrom .cli")
                                           .replace("    return egress", "    p = build(p)\n    return egress")}),
        "a-method-on-own-plain-state": (False, {gw + "cli.py": cli, gw + "__init__.py": released, gw + "cache.py":
                                                "class Cache:\n    def __init__(self, root: str):\n        self.root = root\n\n"
                                                "    def key(self, p: str) -> str:\n        return self._norm(p) + self.root.lower()\n\n"
                                                "    def _norm(self, p: str) -> str:\n        return p.lower()\n"}),
    }
    assert {name: bool(offenders(mods)) for name, (_, mods) in cases.items()} == \
        {name: fires for name, (fires, _) in cases.items()}
    assert offenders({p.relative_to(ROOT).as_posix(): p.read_text(encoding="utf-8") for p in MODULES}) == []


D0_PATHS = [ROOT / "README.md", ROOT / "bench", SRC,
            *(ROOT / folder / "skills" / skill for folder in ("", ".claude", ".agents") for skill in ("start-benchmark", "new-bench-task"))]


def test_no_coordinator_runner_path_remains():
    found = []
    for base in D0_PATHS:
        for f in ([base] if base.is_file() else sorted(base.rglob("*")) if base.exists() else []):
            if f.is_file() and f.suffix in (".py", ".md", ".yaml", ".json"):
                text = f.read_text(encoding="utf-8", errors="replace")
                for word in ("coord-run", "coord_contract", "coord-runner", "MAX_WORKERS_PER_CONTRACT"):
                    if word in text:
                        found.append(f"{f.relative_to(ROOT)}: {word}")
    assert found == []
