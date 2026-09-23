"""Hidden tests for X1 (never in the cell's working copy). Stdlib only: run with `python -m unittest`."""

import unittest

from slug import slugify


class HiddenSlugify(unittest.TestCase):
    def test_docstring_examples(self):
        self.assertEqual(slugify("Hello, World!"), "hello-world")
        self.assertEqual(slugify("  a--b  "), "a-b")
        self.assertEqual(slugify("Café 2"), "caf-2")

    def test_empty_and_symbols_only(self):
        self.assertEqual(slugify(""), "")
        self.assertEqual(slugify("!!! ---"), "")

    def test_digits_and_case(self):
        self.assertEqual(slugify("Top 10 PLACES"), "top-10-places")

    def test_no_leading_or_trailing_hyphen(self):
        self.assertEqual(slugify("--x--"), "x")


if __name__ == "__main__":
    unittest.main()
