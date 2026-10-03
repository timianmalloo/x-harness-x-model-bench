"""Hidden tests for NG2 (W1-L section 7.4): tomli.loads_env on the vendored envkit.

Run as `python -S -m unittest -v test_interp_hidden` from the root of the graded tree, so nothing is installed and both
`src` and `vendor/envkit` are put on the path here. Every outcome that is not the one the test asserts, a missing module
or an exception raised by the call included, is reported through `self.fail`, so a wrong solution is a FAIL (an
assertion), never an ERROR.
"""

import datetime
import importlib
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [os.path.join(ROOT, "src"), os.path.join(ROOT, "vendor", "envkit")]

VALUES = {"A": "1", "B": "2", "NAME": "world", "HOME_DIR": "/srv"}


class InterpHidden(unittest.TestCase):
    def modules(self):
        try:
            return importlib.import_module("tomli"), importlib.import_module("envkit")
        except Exception as exc:  # noqa: BLE001 - any failure to load is a failed test
            self.fail(f"importing tomli and envkit raised {type(exc).__name__}: {exc}")

    def run_loads_env(self, text, values=None):
        """("ok", value) or ("raised", exception); an exception is data, not an error."""
        tomli, envkit = self.modules()
        try:
            return "ok", tomli.loads_env(text, envkit.MappingSource(VALUES if values is None else values))
        except Exception as exc:  # noqa: BLE001
            return "raised", exc

    def test_g1_a_name_is_replaced_in_a_string_value(self):
        self.assertEqual(self.run_loads_env('greeting = "hello ${NAME}!"\n'), ("ok", {"greeting": "hello world!"}))

    def test_g2_strings_in_tables_and_arrays_are_replaced(self):
        text = (
            'top = "${A}"\n'
            'list = ["x-${A}", "plain", ["${B}"]]\n'
            'inline = { k = "${B}", deeper = { d = "${NAME}" } }\n'
            "[table]\n"
            'v = "${A}-end"\n'
            "[table.sub]\n"
            'items = [{ s = "${NAME}" }]\n'
        )
        expected = {
            "top": "1",
            "list": ["x-1", "plain", ["2"]],
            "inline": {"k": "2", "deeper": {"d": "world"}},
            "table": {"v": "1-end", "sub": {"items": [{"s": "world"}]}},
        }
        self.assertEqual(self.run_loads_env(text), ("ok", expected))

    def test_g3_an_unknown_name_raises_unknown_name(self):
        _, envkit = self.modules()
        kind, value = self.run_loads_env('x = "${MISSING_NAME}"\n')
        self.assertEqual(kind, "raised")
        self.assertIsInstance(value, envkit.UnknownName)

    def test_g4_adjacent_names_are_replaced_one_by_one(self):
        self.assertEqual(self.run_loads_env('x = "${A}${B}"\n'), ("ok", {"x": "12"}))
        self.assertEqual(self.run_loads_env('x = "${A}-${B}-${A}"\n'), ("ok", {"x": "1-2-1"}))

    def test_g5_text_that_is_not_a_name_in_braces_is_left_alone(self):
        text = 'x = "cost $5, $HOME and {braces} and {NAME} and $ {A}"\n'
        self.assertEqual(self.run_loads_env(text), ("ok", {"x": "cost $5, $HOME and {braces} and {NAME} and $ {A}"}))

    def test_g6_values_that_are_not_strings_are_returned_unchanged(self):
        text = 'i = 7\nf = 1.5\nb = true\nd = 2024-01-02\nl = [1, 2, 3]\n'
        expected = {"i": 7, "f": 1.5, "b": True, "d": datetime.date(2024, 1, 2), "l": [1, 2, 3]}
        self.assertEqual(self.run_loads_env(text), ("ok", expected))


if __name__ == "__main__":
    unittest.main()
