"""Hidden functional tests for SM1 (FAIL_TO_PASS): `Table.first`.

Run in the grading copy: python -m unittest -v test_first_hidden. Stdlib only. Every behaviour asserted here is in
tasks/SM1/prompt.md. Five tests; tasks/SM1/oracle/wrong_apps.py names the fixture that turns each one red. A call that
raises fails the test with an assertion (`self.fail`), so a red test is always a failure and never an error.
"""

import unittest

from tinydb import TinyDB, where
from tinydb.storages import MemoryStorage
from tinydb.table import Document


def make_table(*docs):
    table = TinyDB(storage=MemoryStorage).table("things")
    for doc in docs:
        table.insert(doc)
    return table


class FirstTests(unittest.TestCase):
    def first(self, table, cond):
        try:
            return table.first(cond)
        except Exception as exc:  # noqa: BLE001 - reported as a failed assertion, not an error
            self.fail(f"first raised {exc!r}")

    def test_first_match_in_insertion_order(self):
        table = make_table({"k": "a", "n": 1}, {"k": "b", "n": 2}, {"k": "c", "n": 3})
        self.assertEqual(self.first(table, where("n") > 1), {"k": "b", "n": 2})
        self.assertEqual(self.first(table, where("k") == "a"), {"k": "a", "n": 1})

    def test_none_when_no_document_matches(self):
        table = make_table({"n": 1}, {"n": 2})
        self.assertIsNone(self.first(table, where("n") == 99))

    def test_none_on_an_empty_table(self):
        self.assertIsNone(self.first(make_table(), where("n") == 1))

    def test_a_query_matching_several_returns_only_the_first(self):
        table = make_table({"t": "x", "i": 1}, {"t": "x", "i": 2}, {"t": "x", "i": 3})
        self.assertEqual(self.first(table, where("t") == "x"), {"t": "x", "i": 1})

    def test_the_result_is_a_document_with_its_doc_id(self):
        table = make_table({"n": 1}, {"n": 2})
        found = self.first(table, where("n") == 2)
        self.assertIsInstance(found, Document)
        self.assertEqual(found.doc_id, 2)


if __name__ == "__main__":
    unittest.main()
