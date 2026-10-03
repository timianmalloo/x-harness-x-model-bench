"""Hidden tests for RW1 turn 2 (W1-L section 6.2). Stdlib only; run with `python -S -m unittest`."""

import unittest
from unittest import mock

import humanfriendly


class Money2Tests(unittest.TestCase):
    def test_t2_1_usd_and_eur(self):
        self.assertEqual(humanfriendly.format_money(1234.5, "USD"), "$1,234.50")
        self.assertEqual(humanfriendly.format_money(1234.5, "EUR"), "1.234,50 €")

    def test_t2_2_jpy_has_no_decimals_and_rounds_half_up(self):
        self.assertEqual(humanfriendly.format_money(1234.5, "JPY"), "¥1,235")
        self.assertEqual(humanfriendly.format_money(1234.4, "JPY"), "¥1,234")

    def test_t2_3_an_unknown_code_raises_value_error(self):
        with self.assertRaises(ValueError):
            humanfriendly.format_money(1, "GBP")

    def test_t2_4_negative_eur(self):
        self.assertEqual(humanfriendly.format_money(-1234.5, "EUR"), "-1.234,50 €")

    def test_t2_5_format_dollars_returns_the_result_of_calling_format_money(self):
        sentinel = object()
        calls = []

        def recorder(*args, **kwargs):
            calls.append((args, kwargs))
            return sentinel

        # `humanfriendly` replaces itself in sys.modules with a deprecation proxy, and an attribute set on the proxy is not seen
        # by the package's own functions. Patch the dict the function itself reads its globals from.
        namespace = humanfriendly.format_dollars.__globals__
        with mock.patch.dict(namespace, {"format_money": recorder}):
            result = humanfriendly.format_dollars(1234.5)
        self.assertEqual(calls, [((1234.5, "USD"), {})])
        self.assertIs(result, sentinel)
