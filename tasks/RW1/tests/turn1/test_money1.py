"""Hidden tests for RW1 turn 1 (W1-L section 6.2). Stdlib only; run with `python -S -m unittest`."""

import unittest
from decimal import Decimal

import humanfriendly


class Money1Tests(unittest.TestCase):
    def test_t1_1_thousands_separator_and_two_decimals(self):
        self.assertEqual(humanfriendly.format_dollars(1234.5), "$1,234.50")
        self.assertEqual(humanfriendly.format_dollars(1234567.891), "$1,234,567.89")

    def test_t1_2_negative_amounts_put_the_sign_before_the_symbol(self):
        self.assertEqual(humanfriendly.format_dollars(-5), "-$5.00")
        self.assertEqual(humanfriendly.format_dollars(-1234.5), "-$1,234.50")

    def test_t1_3_rounds_half_up(self):
        self.assertEqual(humanfriendly.format_dollars(0.005), "$0.01")
        self.assertEqual(humanfriendly.format_dollars(Decimal("2.675")), "$2.68")

    def test_t1_4_accepts_decimal_str_and_int(self):
        self.assertEqual(humanfriendly.format_dollars(Decimal("999.9")), "$999.90")
        self.assertEqual(humanfriendly.format_dollars("12"), "$12.00")
        self.assertEqual(humanfriendly.format_dollars(7), "$7.00")

    def test_t1_5_zero(self):
        self.assertEqual(humanfriendly.format_dollars(0), "$0.00")
        self.assertEqual(humanfriendly.format_dollars(0.0), "$0.00")
