"""Tests for grade/_changes.py counting functions: product_lines, in_radius, line_delta, is_test_path.

(W1-L §5.1, W0 rev 6.6 §13, x-j2.md J2a: R2-2 humanfriendly fixture, R2-3 tinydb fixture, and mutants).
"""

from pathlib import Path

import pytest

from harness_bench.grade import _changes


def test_product_lines_non_py_file_returns_empty(tmp_path: Path):
    txt_file = tmp_path / "notes.txt"
    txt_file.write_text("line 1\nline 2\n", encoding="utf-8")
    assert _changes.product_lines(txt_file) == []


def test_product_lines_nonexistent_file_returns_empty(tmp_path: Path):
    missing = tmp_path / "nonexistent.py"
    assert _changes.product_lines(missing) == []


def test_product_lines_filters_blanks_and_comments(tmp_path: Path):
    py_file = tmp_path / "simple.py"
    py_file.write_text(
        "\n"
        "# full line comment\n"
        "    # indented comment\n"
        "x = 1  # inline comment\n"
        "y = 2\n"
        "   \n",
        encoding="utf-8",
    )
    assert _changes.product_lines(py_file) == [
        "x = 1  # inline comment",
        "y = 2",
    ]


def test_product_lines_excludes_docstrings_module_class_function_async(tmp_path: Path):
    py_file = tmp_path / "docstrings.py"
    py_file.write_text(
        '"""Module docstring.\n'
        'Second line of module docstring.\n'
        '"""\n'
        "\n"
        "class MyClass:\n"
        '    """Class docstring."""\n'
        "    def method(self):\n"
        '        """Method docstring."""\n'
        "        return 1\n"
        "\n"
        "async def async_fn():\n"
        '    """Async function docstring."""\n'
        "    return 2\n",
        encoding="utf-8",
    )
    assert _changes.product_lines(py_file) == [
        "class MyClass:",
        "    def method(self):",
        "        return 1",
        "async def async_fn():",
        "    return 2",
    ]


def test_product_lines_crlf_normalisation(tmp_path: Path):
    py_file = tmp_path / "crlf.py"
    py_file.write_bytes(b"a = 1\r\n\r\nb = 2\r\n")
    assert _changes.product_lines(py_file) == ["a = 1", "b = 2"]


def test_product_lines_syntax_error_keeps_blank_comment_filter(tmp_path: Path):
    py_file = tmp_path / "broken.py"
    py_file.write_text(
        "# comment\n"
        "\n"
        "def broken(\n"
        "    return 1\n",
        encoding="utf-8",
    )
    assert _changes.product_lines(py_file) == [
        "def broken(",
        "    return 1",
    ]


def test_in_radius_matches_globs():
    radius = ["humanfriendly/*.py", "tinydb/**"]
    assert _changes.in_radius("humanfriendly/__init__.py", radius) is True
    assert _changes.in_radius("humanfriendly/tests.py", radius) is True
    assert _changes.in_radius("humanfriendly\\__init__.py", radius) is True
    assert _changes.in_radius("tinydb/tests/_first.py", radius) is True
    assert _changes.in_radius("other/module.py", radius) is False
    assert _changes.in_radius("other/module.py", []) is False


def test_line_delta_identical():
    lines = ["line 1", "line 2"]
    assert _changes.line_delta(lines, lines) == ([], [])


def test_line_delta_add_remove_replace():
    old = ["a", "b", "c"]
    new = ["a", "b2", "c", "d"]
    added, removed = _changes.line_delta(old, new)
    assert added == [1, 3]
    assert removed == [1]


def test_is_test_path_r2_2_humanfriendly():
    # R2-2: humanfriendly/tests.py is a test path
    assert _changes.is_test_path("humanfriendly/tests.py", frozenset()) is True
    assert _changes.is_test_path("humanfriendly\\tests.py", frozenset()) is True


def test_is_test_path_test_basenames():
    for name in ("test_foo.py", "foo_test.py", "tests.py", "test.py", "conftest.py"):
        assert _changes.is_test_path(f"pkg/{name}", frozenset()) is True
    assert _changes.is_test_path("pkg/helper.py", frozenset()) is False
    assert _changes.is_test_path("pkg/other.txt", frozenset()) is False


def test_is_test_path_r2_3_tinydb_new_product_file():
    # R2-3: a new tinydb/tests/_first.py is a product path when not in base tree
    assert _changes.is_test_path("tinydb/tests/_first.py", frozenset()) is False
    assert _changes.is_test_path("tinydb/tests/_first.py", frozenset({"tinydb/table.py"})) is False


def test_is_test_path_r2_3_tinydb_existing_base_test_file():
    # R2-3: a file the base tree already has under tinydb/tests/ is a test path
    base_paths = frozenset({"tinydb/tests/helper.py", "tinydb/tests/fixtures.py"})
    assert _changes.is_test_path("tinydb/tests/helper.py", base_paths) is True
    assert _changes.is_test_path("tinydb\\tests\\helper.py", base_paths) is True


def test_is_test_path_directory_variations():
    # Under test directory (singular) in base tree
    assert _changes.is_test_path("pkg/test/util.py", frozenset({"pkg/test/util.py"})) is True
    assert _changes.is_test_path("pkg/test/util.py", frozenset()) is False
    # Not under tests or test directory
    assert _changes.is_test_path("pkg/testing/util.py", frozenset({"pkg/testing/util.py"})) is False
