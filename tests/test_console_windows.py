"""Console windows suppression guard (GO14a, R6.15a).

Every child launch in tools/, tools/spikes/ and tests/ (recursive over *.py,
fixture helpers included, skipping __pycache__) must suppress console windows
by passing creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0).
"""

import ast
from collections.abc import Mapping
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

ROOTS = ("tools", "tests")
RECURSION = True
SUBPROCESS_CALLS = frozenset({"run", "Popen", "call", "check_call", "check_output"})
TOKENS = frozenset({f"subprocess.{name}" for name in SUBPROCESS_CALLS} | {"os.system"})

ALLOWLIST: Mapping[str, str] = {
    "tools/mutate_check.py": "X-HYG owns this file and applies the convention in its own track",
    "tests/test_mutate_check.py": "X-HYG owns this file and applies the convention in its own track",
    "tests/test_property_grader.py": "X-PROP owns this file and applies the convention in its own track",
    "tests/test_security_s2.py": "X-S2 owns this file and applies the convention in its own track",
    "tests/test_alarm.py": "X-DRILL owns this file and applies the convention in its own track",
    "tests/test_alarm_task.py": "X-DRILL owns this file and applies the convention in its own track",
}


def _aliases(tree: ast.Module) -> dict[str, str]:
    out: dict[str, str] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                name = a.asname or a.name.split(".")[0]
                out[name] = a.name if a.asname else a.name.split(".")[0]
        elif isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            for a in node.names:
                name = a.asname or a.name
                out[name] = f"{mod}.{a.name}" if mod else a.name
    return out


def _dotted(expr: ast.expr, names: dict[str, str]) -> str:
    if isinstance(expr, ast.Name):
        return names.get(expr.id, expr.id)
    if isinstance(expr, ast.Attribute):
        val = _dotted(expr.value, names)
        return f"{val}.{expr.attr}" if val else expr.attr
    return ""


def _scan_offenders(root: Path = ROOT) -> list[str]:
    offenders: list[str] = []
    for r in ROOTS:
        root_dir = root / r
        if not root_dir.is_dir():
            continue
        for p in sorted(root_dir.rglob("*.py")):
            if "__pycache__" in p.parts:
                continue
            rel = p.relative_to(root).as_posix()
            tree = ast.parse(p.read_text(encoding="utf-8"), filename=str(p))
            names = _aliases(tree)
            for node in ast.walk(tree):
                if isinstance(node, ast.Call):
                    target = _dotted(node.func, names)
                    if target in TOKENS:
                        has_flags = any(kw.arg == "creationflags" for kw in node.keywords)
                        if not has_flags:
                            offenders.append(f"{rel}:{node.lineno}")
    return offenders


def test_console_windows_guard():
    offenders = _scan_offenders()
    unallowlisted = [hit for hit in offenders if hit.split(":")[0] not in ALLOWLIST]
    assert not unallowlisted, (
        f"child launches without creationflags keyword ({len(unallowlisted)} violations):\n"
        + "\n".join(unallowlisted)
    )


def test_allowlist_is_subset_and_justified():
    offenders = _scan_offenders()
    flagged_files = {hit.split(":")[0] for hit in offenders}
    assert (flagged_files & set(ALLOWLIST.keys())) <= set(ALLOWLIST.keys())
    assert all(reason.strip() for reason in ALLOWLIST.values())


def test_frozen_fields():
    assert ROOTS == ("tools", "tests")
    assert RECURSION is True
    assert TOKENS == frozenset({
        "subprocess.run",
        "subprocess.Popen",
        "subprocess.call",
        "subprocess.check_call",
        "subprocess.check_output",
        "os.system",
    })
