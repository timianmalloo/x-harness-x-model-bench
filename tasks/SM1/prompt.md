Add a method `first(cond)` to the `Table` class in `tinydb/table.py`.

`first(cond)` takes a query, in the same form `Table.search` takes. It returns the first document of the table that matches the query, taking the documents in the order they were inserted. The result is a `Document` that carries its `doc_id`, as the documents `search` returns do. When no document matches, it returns `None`. A table with no documents also gives `None`.

Add tests for it to `tests/test_tables.py`, and keep the existing tests passing.
