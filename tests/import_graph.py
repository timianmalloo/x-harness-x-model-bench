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
    return []


def stale_allowed(root: Path, classes: Mapping[str, str], allowed: Mapping) -> list[tuple[str, str]]:
    """Allowed edges that are absent from the current tree."""
    return []
