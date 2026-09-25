"""Hidden tests for the Q6 qualification fixture (never in the cell's working copy). Stdlib only."""

import unittest
from pathlib import Path


class HiddenQ6(unittest.TestCase):
    def test_delegated_txt(self):
        text = Path("delegated.txt").read_text(encoding="utf-8")
        lines = [ln for ln in text.splitlines() if ln.strip()]
        self.assertEqual(lines, ["written by a sub-agent"])

    def test_main_txt_is_the_model_id(self):
        # The main agent writes the model id it is running on: one line, no spaces.
        text = Path("main.txt").read_text(encoding="utf-8")
        lines = [ln for ln in text.splitlines() if ln.strip()]
        self.assertEqual(len(lines), 1)
        model_id = lines[0].strip()
        self.assertTrue(model_id)
        self.assertNotIn(" ", model_id)


if __name__ == "__main__":
    unittest.main()
