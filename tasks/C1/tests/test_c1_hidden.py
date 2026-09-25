"""Hidden tests for C1. Stdlib only. Run with python -m unittest. Never placed in the workspace."""

import unittest
from pathlib import Path

from priority_queue import PriorityQueue

REQUIRED_SECTIONS = (
    "## Context",
    "## Components",
    "## Data structure",
    "## Operations",
    "## Exception safety",
    "## Complexity",
)


def _section_bodies(text: str) -> dict[str, str]:
    bodies: dict[str, list[str]] = {}
    current: str | None = None
    for line in text.splitlines():
        if line.startswith("## "):
            current = line.strip()
            bodies.setdefault(current, [])
            continue
        if current is not None:
            bodies[current].append(line)
    return {heading: "\n".join(lines).strip() for heading, lines in bodies.items()}


class HiddenPriorityQueue(unittest.TestCase):
    def test_push_pop_is_max_heap(self):
        queue = PriorityQueue()
        for value in (1, 3, 2, 5, 4):
            queue.push(value)
        self.assertEqual([queue.pop() for _ in range(5)], [5, 4, 3, 2, 1])
        self.assertTrue(queue.empty())

    def test_top_size_empty_and_index_errors(self):
        queue = PriorityQueue()
        self.assertTrue(queue.empty())
        self.assertEqual(queue.size(), 0)
        with self.assertRaises(IndexError):
            queue.top()
        with self.assertRaises(IndexError):
            queue.pop()
        queue.push(2)
        queue.push(7)
        self.assertEqual(queue.top(), 7)
        self.assertEqual(queue.size(), 2)
        self.assertFalse(queue.empty())
        self.assertEqual(queue.top(), 7)

    def test_custom_compare_min_heap(self):
        queue = PriorityQueue(compare=lambda a, b: a < b)
        for value in (3, 1, 2):
            queue.push(value)
        self.assertEqual([queue.pop() for _ in range(3)], [1, 2, 3])

    def test_merge_moves_values_and_empties_other(self):
        left = PriorityQueue()
        right = PriorityQueue()
        for value in (1, 8, 3):
            left.push(value)
        for value in (4, 9, 2):
            right.push(value)
        left.merge(right)
        self.assertTrue(right.empty())
        self.assertEqual(right.size(), 0)
        self.assertEqual(left.size(), 6)
        self.assertEqual([left.pop() for _ in range(6)], [9, 8, 4, 3, 2, 1])

    def test_merge_with_empty_either_side(self):
        full = PriorityQueue()
        full.push(4)
        full.push(1)
        empty = PriorityQueue()
        full.merge(empty)
        self.assertEqual(full.size(), 2)
        self.assertEqual(full.top(), 4)
        empty.merge(full)
        self.assertTrue(full.empty())
        self.assertEqual([empty.pop(), empty.pop()], [4, 1])

    def test_push_compare_failure_restores(self):
        def higher(a, b):
            if a == "boom" or b == "boom":
                raise ValueError("boom")
            return a > b

        queue = PriorityQueue(compare=higher)
        queue.push(1)
        queue.push(4)
        with self.assertRaises(RuntimeError):
            queue.push("boom")
        self.assertEqual(queue.size(), 2)
        self.assertEqual(queue.top(), 4)
        self.assertEqual([queue.pop(), queue.pop()], [4, 1])

    def test_pop_compare_failure_restores(self):
        state = {"throw": False}

        def higher(a, b):
            if state["throw"]:
                raise ValueError("boom")
            return a > b

        queue = PriorityQueue(compare=higher)
        for value in (1, 3, 2):
            queue.push(value)
        state["throw"] = True
        with self.assertRaises(RuntimeError):
            queue.pop()
        state["throw"] = False
        self.assertEqual(queue.size(), 3)
        self.assertEqual([queue.pop() for _ in range(3)], [3, 2, 1])

    def test_merge_compare_failure_restores_both(self):
        state = {"throw": False}

        def higher(a, b):
            if state["throw"]:
                raise ValueError("boom")
            return a > b

        left = PriorityQueue(compare=higher)
        right = PriorityQueue(compare=higher)
        left.push(1)
        left.push(5)
        right.push(2)
        right.push(4)
        state["throw"] = True
        with self.assertRaises(RuntimeError):
            left.merge(right)
        state["throw"] = False
        self.assertEqual(left.size(), 2)
        self.assertEqual(right.size(), 2)
        self.assertEqual(left.top(), 5)
        self.assertEqual(right.top(), 4)
        self.assertEqual([left.pop(), left.pop()], [5, 1])
        self.assertEqual([right.pop(), right.pop()], [4, 2])


class HiddenArchitecture(unittest.TestCase):
    def test_architecture_document_present(self):
        self.assertTrue(Path("docs/architecture.md").is_file(), "docs/architecture.md is missing")

    def test_architecture_required_sections(self):
        path = Path("docs/architecture.md")
        self.assertTrue(path.is_file(), "docs/architecture.md is missing")
        bodies = _section_bodies(path.read_text(encoding="utf-8"))
        missing = [heading for heading in REQUIRED_SECTIONS if not bodies.get(heading)]
        self.assertEqual(missing, [], f"missing or empty sections: {missing}")


if __name__ == "__main__":
    unittest.main()
