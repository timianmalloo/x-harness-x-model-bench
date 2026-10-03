"""Wrong-app fixtures for S1's hidden tests (W1-I section 5.6, RV-TA W1-I 1).

Each fixture is a list of `(old, new)` substitutions applied to the reference's `examples/notes/app.py` at test time. The
result imports cleanly and breaks one stated behaviour, so exactly the named hidden test turns red, with an assertion
failure and not an import error. Skeleton: the tables name the fixtures and their one red test, and carry no edits yet.
"""

FILE = "examples/notes/app.py"

WRONG_APPS = {
    "wa-case": {"red": "test_search_matches_title_or_body_ignoring_ascii_case_and_no_match_is_an_empty_list", "edits": []},
    "wa-order": {"red": "test_list_is_in_id_order", "edits": []},
    "wa-delete": {"red": "test_delete_returns_204_then_the_note_is_404", "edits": []},
    "wa-body": {"red": "test_create_rejects_a_body_that_is_not_a_json_object_with_two_string_fields", "edits": []},
    "wa-import": {"red": "test_importing_the_module_has_no_side_effects", "edits": []},
    "wa-serve": {"red": "test_importing_the_module_has_no_side_effects", "edits": []},
    "wa-prefix": {"red": "test_missing_unknown_or_near_miss_token_gets_401_on_every_endpoint", "edits": []},
}


def apply(source: str, name: str) -> str:
    """The reference source with fixture `name` applied. Each `old` must occur exactly once."""
    for old, new in WRONG_APPS[name]["edits"]:
        if source.count(old) != 1:
            raise ValueError(f"{name}: expected one occurrence of {old!r}, found {source.count(old)}")
        source = source.replace(old, new)
    return source
