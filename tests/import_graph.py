"""Shared AST import resolver for G2b, G3, G5 and the spawn guard (W0 §10)."""

import ast
from collections.abc import Mapping
from pathlib import Path


def package(rel: str) -> tuple[str, ...]:
    """rel is src/harness_bench/.../x.py; return its import package."""
    return tuple(Path(rel).with_suffix("").parts[1:-1])


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


def dotted(expr: ast.expr, names: Mapping[str, str]) -> str:
    if isinstance(expr, ast.Name):
        return names.get(expr.id, "")
    return f"{dotted(expr.value, names)}.{expr.attr}" if isinstance(expr, ast.Attribute) else ""


def imports(rel: str, tree: ast.Module) -> set[str]:
    """All absolute import targets, including lazy and typing imports."""
    targets = set()
    pkg = package(rel)
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            targets |= {a.name for a in node.names}
        elif isinstance(node, ast.ImportFrom):
            base = list(pkg[:len(pkg) - node.level + 1]) if node.level else []
            module = ".".join(base + ([node.module] if node.module else []))
            targets |= {module if a.name == "*" else f"{module}.{a.name}" for a in node.names}
    return targets


def import_violations(root: Path, classes: Mapping[str, str], allowed: Mapping,
                      exempt: frozenset[str]) -> list[tuple[str, str]]:
    """Run-to-grade edges, minus named pairs and the composition-root exemption."""
    return sorted(_run_to_grade_edges(root, classes, exempt) - allowed.keys())


def stale_allowed(root: Path, classes: Mapping[str, str], allowed: Mapping) -> list[tuple[str, str]]:
    """Allowed edges that are absent from the current tree."""
    return sorted(allowed.keys() - _run_to_grade_edges(root, classes, frozenset()))


def _target_file(target: str, classes: Mapping[str, str]) -> str | None:
    """Map a dotted import target to its src-relative file: the longest prefix naming a module or package."""
    parts = target.split(".")
    if parts[0] != "harness_bench":
        return None
    for end in range(len(parts), 1, -1):
        base = "/".join(parts[1:end])
        for candidate in (f"{base}.py", f"{base}/__init__.py"):
            if candidate in classes:
                return candidate
    return None


def _run_to_grade_edges(root: Path, classes: Mapping[str, str], exempt: frozenset[str]) -> set[tuple[str, str]]:
    src = root / "src" / "harness_bench"
    edges = set()
    for name, kind in classes.items():
        path = src / name
        if kind != "run" or name in exempt or not path.is_file():
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for target in imports(f"src/harness_bench/{name}", tree):
            hit = _target_file(target, classes)
            if hit and classes[hit] == "grade":
                edges.add((name, hit))
    return edges
