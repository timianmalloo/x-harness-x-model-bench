"""G1: root src/harness_bench/, recursive *.py, AST tokens outside docstrings.

Tokens: Constant('pack'), Attribute.pack, keyword(pack=); allowlist: exact per-file
counts below. A second ratchet counts Constant('on'/'off') and quoted JS literals
in report/assets/*.js (non-recursive). Pins are measured after A1b migrations.
"""

import ast
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1] / "src/harness_bench"
PACK_READERS_ALLOWED: dict[str, int] = {
    "board.py": 16,
    "cli.py": 3,  # Two directory operands and the historical event wire key.
    "config.py": 3,  # Matrix arm validation, not a cell reader.
    "plan.py": 12,  # Authoritative version adapter and frozen identity recipe.
    "report/cli_table.py": 7,
    "report/context_growth.py": 1,
    "report/html.py": 35,  # X-H2: the header reads plan_packs (three `.get("pack")` reads removed; decrease only).
    "report/summaries.py": 3,
    "workspace.py": 2,  # Directory operands, not cell readers.
}
ARM_LITERALS_ALLOWED: dict[str, int] = {"config.py": 3, "plan.py": 2}
JS_ARM_LITERALS_ALLOWED: dict[str, int] = {}


def _nodes(text):
    tree = ast.parse(text)
    for node in ast.walk(tree):
        if (isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef))
                and node.body and isinstance(node.body[0], ast.Expr)
                and isinstance(node.body[0].value, ast.Constant)
                and isinstance(node.body[0].value.value, str)):
            node.body = node.body[1:]
    return ast.walk(tree)


def pack_hits(text):
    return sum(1 for n in _nodes(text) if
               (isinstance(n, ast.Constant) and n.value == "pack")
               or (isinstance(n, ast.Attribute) and n.attr == "pack")
               or (isinstance(n, ast.keyword) and n.arg == "pack"))


def arm_literal_hits(text):
    return sum(1 for n in _nodes(text) if isinstance(n, ast.Constant)
               and isinstance(n.value, str) and n.value in {"on", "off"})


def js_arm_literal_hits(text):
    return len(re.findall(r"(['\"])(?:on|off)\1", text))


def _counts(root, counter):
    return {p.relative_to(root).as_posix(): count for p in sorted(root.rglob("*.py"))
            if (count := counter(p.read_text(encoding="utf-8")))}


@pytest.mark.parametrize("form", [
    'x["pack"]', 'x.get("pack")', 'x.pop("pack")', '"pack" in x',
    'getattr(x, "pack")', 'itemgetter("pack")', 'x.pack', 'f(pack=1)',
    '{"pack": 1}',
])
def test_pack_guard_detects_each_form_in_a_real_file(tmp_path, form):
    nested = tmp_path / "nested"
    nested.mkdir()
    (nested / "reader.py").write_text(form, encoding="utf-8")
    assert _counts(tmp_path, pack_hits) == {"nested/reader.py": 1}


@pytest.mark.parametrize("text", [
    '# pack on off\n', '"""pack on off"""\n',
    'class Reader:\n    """pack on off"""\n',
    'def reader():\n    """pack on off"""\n    return 1\n',
])
def test_guards_ignore_comments_and_docstrings(tmp_path, text):
    (tmp_path / "prose.py").write_text(text, encoding="utf-8")
    assert _counts(tmp_path, pack_hits) == {}
    assert _counts(tmp_path, arm_literal_hits) == {}


def test_arm_literal_guard_has_python_and_javascript_red_fixtures(tmp_path):
    (tmp_path / "reader.py").write_text('x == "on"; y == "off"', encoding="utf-8")
    (tmp_path / "reader.js").write_text('setting === "on"; setting === \'off\'', encoding="utf-8")
    assert _counts(tmp_path, arm_literal_hits) == {"reader.py": 2}
    assert js_arm_literal_hits((tmp_path / "reader.js").read_text(encoding="utf-8")) == 2


def test_pack_hits_equal_the_pinned_counts():
    assert _counts(ROOT, pack_hits) == PACK_READERS_ALLOWED


def test_arm_literals_equal_the_pinned_counts():
    assert _counts(ROOT, arm_literal_hits) == ARM_LITERALS_ALLOWED


def test_javascript_arm_literals_equal_the_pinned_counts():
    counts = {p.name: count for p in sorted((ROOT / "report/assets").glob("*.js"))
              if (count := js_arm_literal_hits(p.read_text(encoding="utf-8")))}
    assert counts == JS_ARM_LITERALS_ALLOWED
