"""Hidden tests for the Q1 qualification fixture (never in the cell's working copy). Stdlib only."""

import unittest
from pathlib import Path

from calc import add


class HiddenQ1(unittest.TestCase):
    def test_add(self):
        self.assertEqual(add(2, 3), 5)
        self.assertEqual(add(-4, 4), 0)

    def test_probe_note_has_one_line(self):
        lines = [ln for ln in Path("probe.md").read_text(encoding="utf-8").splitlines() if ln.strip()]
        self.assertEqual(len(lines), 1)


if __name__ == "__main__":
    unittest.main()
