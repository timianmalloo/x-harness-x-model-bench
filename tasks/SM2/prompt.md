Add a function `search_many(expression, documents, options=None)` to `jmespath/__init__.py`.

It returns a list with one entry per item of `documents`, in the same order: the result `jmespath.search(expression, document, options)` gives for that document. The expression is parsed once for the whole call, not once per document. An invalid expression raises the same `ParseError` that `jmespath.search` raises, and it does so also when `documents` is empty. `options` reaches every search the way `jmespath.search` passes it on.

Add tests for it in `tests/test_search_many.py`, and keep the existing tests passing.
