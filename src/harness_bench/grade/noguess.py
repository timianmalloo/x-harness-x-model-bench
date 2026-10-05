"""No-guessing strategy helper (W1-L rev 2 section 7; R-97).

One producer per language (R-97 condition 1): for Python, the static resolver below; for a compiled language,
the correctness grader's build.log (compiler errors naming a missing member). That path is not built in E4
(no compiled no-guessing task exists): such a task scores NA not built for <runner>, never 0.
"""

from __future__ import annotations

import ast
import dataclasses
import json
import sys
from collections import defaultdict
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import TYPE_CHECKING, Any

from harness_bench.grade import CellInput, Score, _changes

if TYPE_CHECKING:
    from harness_bench.grade.property import GradeContext

__all__ = ["ResolverError", "grade", "unresolved"]


class ResolverError(Exception):
    """Raised when vendored API static resolution fails (syntax error or child resolver failure)."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


_RESOLVER_CHILD_SCRIPT = r"""
import ast
import importlib
import inspect
import json
import sys
import textwrap

sys.path = [sys.argv[1]]

payload = json.loads(sys.argv[2])
vendor_libs = payload.get("vendor_libs", [])

for lib in vendor_libs:
    importlib.import_module(lib)


def resolve_dotted(dotted: str):
    parts = dotted.split(".")
    obj = None
    remaining = parts
    for i in range(len(parts), 0, -1):
        mod_name = ".".join(parts[:i])
        try:
            obj = importlib.import_module(mod_name)
            remaining = parts[i:]
            break
        except (ImportError, ModuleNotFoundError, AttributeError):
            continue
    if obj is None:
        return None, parts[0]
    cur = obj
    for idx, part in enumerate(remaining):
        if hasattr(cur, part):
            cur = getattr(cur, part)
        else:
            unresolved_prefix = ".".join(parts[:len(parts) - len(remaining) + idx + 1])
            return None, unresolved_prefix
    return cur, None


def has_instance_attr(cls, attr_name: str) -> bool:
    for c in getattr(cls, "__mro__", (cls,)):
        if c is object:
            continue
        try:
            src = inspect.getsource(c)
        except (OSError, TypeError):
            continue
        try:
            tree = ast.parse(textwrap.dedent(src))
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if isinstance(node, (ast.Assign, ast.AnnAssign, ast.AugAssign)):
                targets = node.targets if isinstance(node, ast.Assign) else [node.target]
                for t in targets:
                    if isinstance(t, ast.Attribute) and isinstance(t.value, ast.Name) and t.value.id == "self":
                        if t.attr == attr_name:
                            return True
    return False


unresolved = []


def add_unresolved(name: str) -> None:
    if name not in unresolved:
        unresolved.append(name)


classes: dict[str, bool] = {}
for dotted in payload.get("classes_to_check", []):
    obj, _ = resolve_dotted(dotted)
    classes[dotted] = isinstance(obj, type)

for dotted in payload.get("dotted_names", []):
    _, err = resolve_dotted(dotted)
    if err is not None:
        add_unresolved(err)

for class_dotted, member in payload.get("typed_members", []):
    cls, err = resolve_dotted(class_dotted)
    if cls is None or not isinstance(cls, type):
        continue
    if not (hasattr(cls, member) or has_instance_attr(cls, member)):
        add_unresolved(f"{class_dotted}.{member}")

for callee_dotted, kw_name, is_class in payload.get("keywords", []):
    target_callable, err = resolve_dotted(callee_dotted)
    if target_callable is None:
        continue
    if is_class and isinstance(target_callable, type):
        init_fn = getattr(target_callable, "__init__", None)
        if init_fn is not None and init_fn is not object.__init__:
            target_callable = init_fn
        else:
            new_fn = getattr(target_callable, "__new__", None)
            if new_fn is not None and new_fn is not object.__new__:
                target_callable = new_fn
    try:
        sig = inspect.signature(target_callable)
        has_kw = kw_name in sig.parameters
        has_var_kw = any(p.kind == inspect.Parameter.VAR_KEYWORD for p in sig.parameters.values())
        accepted = has_kw or has_var_kw
    except (ValueError, TypeError):
        accepted = True
    if not accepted:
        name = f"{callee_dotted}.__init__:{kw_name}" if is_class else f"{callee_dotted}:{kw_name}"
        add_unresolved(name)

sys.stdout.write(json.dumps({"unresolved": unresolved, "classes": classes}))
"""


def _find_vendored_pkgs(vendor_dir: Path) -> set[str]:
    pkgs = set()
    if (vendor_dir / "__init__.py").is_file():
        pkgs.add(vendor_dir.name)
    for p in vendor_dir.iterdir():
        if p.is_dir() and (p / "__init__.py").is_file():
            pkgs.add(p.name)
        elif p.is_file() and p.suffix == ".py" and not p.name.startswith("."):
            pkgs.add(p.stem)
    return pkgs


def _get_dotted_chain(
    node: ast.AST,
    imported_symbols: Mapping[str, str],
    imported_modules: Mapping[str, str],
) -> str | None:
    if isinstance(node, ast.Name):
        if node.id in imported_symbols:
            return imported_symbols[node.id]
        if node.id in imported_modules:
            return imported_modules[node.id]
        return None
    if isinstance(node, ast.Attribute):
        prefix = _get_dotted_chain(node.value, imported_symbols, imported_modules)
        if prefix is not None:
            return f"{prefix}.{node.attr}"
        return None
    return None


def unresolved(
    tree: Path | str,
    radius: Sequence[str],
    vendor: Path | str,
) -> tuple[int, list[str]]:
    """Return (count, distinct_unresolved_names) for vendored API references inside radius."""
    from harness_bench.grade.property import run_child

    tree_path = Path(tree)
    vendor_path = Path(vendor).resolve()
    vendored_pkgs = _find_vendored_pkgs(vendor_path)

    radius_list = list(radius)
    py_files: list[tuple[str, Path]] = []
    for p in tree_path.rglob("*.py"):
        rel = p.relative_to(tree_path).as_posix()
        if _changes.in_radius(rel, radius_list) and not _changes.is_test_path(rel, frozenset()):
            py_files.append((rel, p))

    trees: list[tuple[str, ast.AST]] = []
    for rel, p in py_files:
        content = p.read_text(encoding="utf-8")
        try:
            parsed = ast.parse(content, filename=rel)
            trees.append((rel, parsed))
        except SyntaxError:
            raise ResolverError(f"syntax error: {rel}") from None

    dotted_names: dict[str, None] = {}
    typed_members: dict[tuple[str, str], None] = {}
    keywords: dict[tuple[str, str, bool], None] = {}
    classes_to_check: dict[str, None] = {}

    for _rel, mod_ast in trees:
        imported_modules: dict[str, str] = {}
        imported_symbols: dict[str, str] = {}

        for node in ast.walk(mod_ast):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    root_pkg = alias.name.split(".")[0]
                    if root_pkg in vendored_pkgs:
                        local_name = alias.asname or alias.name
                        imported_modules[local_name] = alias.name
            elif isinstance(node, ast.ImportFrom) and node.module:
                root_pkg = node.module.split(".")[0]
                if root_pkg in vendored_pkgs:
                    for alias in node.names:
                        local_name = alias.asname or alias.name
                        full_target = f"{node.module}.{alias.name}"
                        imported_symbols[local_name] = full_target
                        dotted_names[full_target] = None
                        classes_to_check[full_target] = None

        for node in ast.walk(mod_ast):
            if isinstance(node, ast.Attribute):
                chain = _get_dotted_chain(node, imported_symbols, imported_modules)
                if chain is not None:
                    dotted_names[chain] = None
                    classes_to_check[chain] = None

        scopes: list[ast.AST] = [mod_ast]
        for node in ast.walk(mod_ast):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                scopes.append(node)

        for scope in scopes:
            var_classes: dict[str, set[str]] = defaultdict(set)

            if isinstance(scope, (ast.FunctionDef, ast.AsyncFunctionDef)):
                all_args = scope.args.posonlyargs + scope.args.args + scope.args.kwonlyargs
                for arg in all_args:
                    if arg.annotation:
                        chain = _get_dotted_chain(arg.annotation, imported_symbols, imported_modules)
                        if chain is not None:
                            var_classes[arg.arg].add(chain)
                            classes_to_check[chain] = None

            for child in ast.iter_child_nodes(scope):
                for assign in ast.walk(child):
                    if isinstance(assign, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and assign is not scope:
                        continue
                    if isinstance(assign, ast.Assign) and isinstance(assign.value, ast.Call):
                        callee_chain = _get_dotted_chain(assign.value.func, imported_symbols, imported_modules)
                        if callee_chain is not None:
                            classes_to_check[callee_chain] = None
                            for target in assign.targets:
                                if isinstance(target, ast.Name):
                                    var_classes[target.id].add(callee_chain)
                                elif (
                                    isinstance(target, ast.Attribute)
                                    and isinstance(target.value, ast.Name)
                                    and target.value.id == "self"
                                ):
                                    var_classes[f"self.{target.attr}"].add(callee_chain)
                    elif isinstance(assign, ast.AnnAssign) and assign.value is not None and isinstance(assign.value, ast.Call):
                        callee_chain = _get_dotted_chain(assign.value.func, imported_symbols, imported_modules)
                        if callee_chain is not None:
                            classes_to_check[callee_chain] = None
                            target = assign.target
                            if isinstance(target, ast.Name):
                                var_classes[target.id].add(callee_chain)
                            elif (
                                isinstance(target, ast.Attribute)
                                and isinstance(target.value, ast.Name)
                                and target.value.id == "self"
                            ):
                                var_classes[f"self.{target.attr}"].add(callee_chain)

            scope_typed: dict[str, str] = {}
            for v_name, assigned_set in var_classes.items():
                if len(assigned_set) == 1:
                    scope_typed[v_name] = next(iter(assigned_set))

            for child in ast.walk(scope):
                if isinstance(child, ast.Attribute):
                    v_key = None
                    if isinstance(child.value, ast.Name) and child.value.id in scope_typed:
                        v_key = child.value.id
                    elif (
                        isinstance(child.value, ast.Attribute)
                        and isinstance(child.value.value, ast.Name)
                        and child.value.value.id == "self"
                    ):
                        attr_key = f"self.{child.value.attr}"
                        if attr_key in scope_typed:
                            v_key = attr_key

                    if v_key is not None:
                        cls_dotted = scope_typed[v_key]
                        typed_members[(cls_dotted, child.attr)] = None

                if isinstance(child, ast.Call):
                    callee_chain = _get_dotted_chain(child.func, imported_symbols, imported_modules)
                    if callee_chain is not None:
                        for kw in child.keywords:
                            if kw.arg:
                                keywords[(callee_chain, kw.arg, True)] = None
                    elif isinstance(child.func, ast.Attribute):
                        v_key = None
                        if isinstance(child.func.value, ast.Name) and child.func.value.id in scope_typed:
                            v_key = child.func.value.id
                        elif (
                            isinstance(child.func.value, ast.Attribute)
                            and isinstance(child.func.value.value, ast.Name)
                            and child.func.value.value.id == "self"
                        ):
                            attr_key = f"self.{child.func.value.attr}"
                            if attr_key in scope_typed:
                                v_key = attr_key
                        if v_key is not None:
                            cls_dotted = scope_typed[v_key]
                            method_name = child.func.attr
                            for kw in child.keywords:
                                if kw.arg:
                                    keywords[(f"{cls_dotted}.{method_name}", kw.arg, False)] = None

    payload = {
        "vendor_libs": sorted(vendored_pkgs),
        "classes_to_check": list(classes_to_check.keys()),
        "dotted_names": list(dotted_names.keys()),
        "typed_members": list(typed_members.keys()),
        "keywords": list(keywords.keys()),
    }

    argv = [sys.executable, "-S", "-c", _RESOLVER_CHILD_SCRIPT, str(vendor_path), json.dumps(payload)]
    proc = run_child(argv, cwd=Path("."), timeout=30.0)

    if proc.timed_out:
        raise ResolverError("resolver failed: timeout")
    if proc.returncode != 0:
        first_line = (proc.stderr or "").strip().splitlines()[0] if (proc.stderr or "").strip() else f"exit code {proc.returncode}"
        raise ResolverError(f"resolver failed: {first_line}")

    try:
        resp = json.loads(proc.stdout)
        unresolved_list = resp["unresolved"]
    except (json.JSONDecodeError, KeyError, TypeError):
        raise ResolverError("resolver failed: malformed response") from None

    return len(unresolved_list), unresolved_list


def grade(inp: CellInput, ctx: GradeContext) -> Mapping[str, Score]:
    """Grade no-guessing property task (W1-L section 7)."""
    from harness_bench.grade.property import hidden_tests, write_section

    runner_kind = inp.task.get("oracle", {}).get("runner", "unittest")

    # Compiled runner check (R-97 condition 1): NA not built for <runner>, never 0
    if runner_kind not in ("unittest", "pytest"):
        na_runner = Score(None, f"not built for {runner_kind}")
        vbu_na = Score(None, "not built")
        scores = {
            "property_check_pass": na_runner,
            "hallucinated_symbol_errors": na_runner,
            "verified_before_use": vbu_na,
        }
        evidence_ptr = write_section(inp, "no-guessing", {"runner": runner_kind, "reason": f"not built for {runner_kind}"})
        scores = {k: dataclasses.replace(v, evidence=evidence_ptr) for k, v in scores.items()}
        return {k: scores[k] for k in inp.metrics if k in scores}

    # Find pristine vendor and overlay mapping
    task_ws = inp.task_dir / "workspace"
    vendor_root = task_ws / "vendor"
    overlay: dict[str, Path] = {}
    pristine_vendor: Path | None = None

    if vendor_root.is_dir():
        for sub in vendor_root.iterdir():
            if sub.is_dir() and not sub.name.startswith("."):
                overlay[f"vendor/{sub.name}"] = sub
                if pristine_vendor is None:
                    pristine_vendor = sub

    # Hidden tests with pristine vendor overlay
    tree = inp.archive / "ws"
    hidden = hidden_tests(inp, tree, "tests", overlay=overlay)

    if hidden.value == 1:
        pass_score = Score(1, None)
    elif hidden.value == 0:
        pass_score = Score(0, None)
    else:
        pass_score = Score(None, hidden.reason)

    # Static resolver on final tree inside blast radius
    radius = inp.task.get("blast_radius", [])
    vendor_to_resolve = pristine_vendor or (tree / "vendor")

    err_reason: str | None = None
    count: int | None = None
    names: list[str] = []
    try:
        count, names = unresolved(tree, radius, vendor_to_resolve)
        hse_score = Score(count, None)
    except ResolverError as err:
        hse_score = Score(None, err.reason)
        err_reason = err.reason

    vbu_score = Score(None, "not built")

    section_data: dict[str, Any] = {
        "hidden_tests_pass": {"value": hidden.value, "reason": hidden.reason},
        "unresolved_count": count,
        "unresolved_names": names,
    }
    if err_reason:
        section_data["resolver_error"] = err_reason

    evidence_ptr = write_section(inp, "no-guessing", section_data)
    scores = {
        "property_check_pass": dataclasses.replace(pass_score, evidence=evidence_ptr),
        "hallucinated_symbol_errors": dataclasses.replace(hse_score, evidence=evidence_ptr),
        "verified_before_use": dataclasses.replace(vbu_score, evidence=evidence_ptr),
    }
    return {k: scores[k] for k in inp.metrics if k in scores}
