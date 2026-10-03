Add a function `format_dollars(amount)` to `humanfriendly/__init__.py`.

It returns an amount of US dollars as a string, with a thousands separator and two decimals, rounded half up. `format_dollars(1234.5)` is `'$1,234.50'` and `format_dollars(-5)` is `'-$5.00'`. It accepts an `int`, a `float`, a string that holds a number, or a `decimal.Decimal`.

Add tests for it to `humanfriendly/tests.py`, and keep the existing tests passing.
