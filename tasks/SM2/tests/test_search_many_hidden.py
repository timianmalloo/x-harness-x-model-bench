"""Hidden functional tests for SM2 (FAIL_TO_PASS): `jmespath.search_many`.

Run in the grading copy: python -m unittest -v test_search_many_hidden. Stdlib only. Every behaviour asserted here is in
tasks/SM2/prompt.md. Five tests; tasks/SM2/oracle/wrong_apps.py names the fixture that turns each one red.
"""

import collections
import unittest
import unittest.mock

import jmespath
from jmespath.exceptions import ParseError
from jmespath.parser import Parser


class SearchManyTests(unittest.TestCase):
    def test_results_in_order_with_the_values_search_gives(self):
        documents = [{"a": {"b": 1}}, {"a": {"b": 2}}, {"a": {}}]
        self.assertEqual(jmespath.search_many("a.b", documents), [1, 2, None])
        self.assertEqual(jmespath.search_many("a.b", documents), [jmespath.search("a.b", d) for d in documents])

    def test_an_empty_list_gives_an_empty_list(self):
        self.assertEqual(jmespath.search_many("a.b", []), [])

    def test_options_reach_every_search(self):
        options = jmespath.Options(dict_cls=collections.OrderedDict)
        results = jmespath.search_many("{x: a}", [{"a": 1}, {"a": 2}], options=options)
        self.assertEqual([type(r) for r in results], [collections.OrderedDict, collections.OrderedDict])
        self.assertEqual(sorted(r["x"] for r in results), [1, 2])  # the order is test 1's concern alone

    def test_the_expression_is_parsed_once(self):
        calls = []
        original = Parser.parse

        def recorder(self, expression):
            calls.append(expression)
            return original(self, expression)

        with unittest.mock.patch.object(Parser, "parse", recorder):
            jmespath.search_many("a", [{"a": 1}, {"a": 2}, {"a": 3}])
        self.assertEqual(calls, ["a"])

    def test_an_invalid_expression_raises_parse_error_even_for_no_documents(self):
        with self.assertRaises(ParseError):
            jmespath.search_many("a.", [])
        with self.assertRaises(ParseError):
            jmespath.search_many("a.", [{"a": 1}])


if __name__ == "__main__":
    unittest.main()
