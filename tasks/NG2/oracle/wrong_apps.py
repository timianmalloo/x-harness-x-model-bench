"""Wrong-app fixtures for NG2's hidden tests: one top-level WRONG_APPS literal, never imported. Each entry is the reference with
one substitution; `reds` is the exact set of hidden test ids it turns red, by assertion and not by import error.
wa-nosubst also reddens G-3 (nothing is looked up, so nothing raises); W1-L listed G-1, G-2 and G-4."""

WRONG_APPS = {
    "wa-nosubst": {
        "reds": ["test_g1_a_name_is_replaced_in_a_string_value", "test_g2_strings_in_tables_and_arrays_are_replaced", "test_g3_an_unknown_name_raises_unknown_name", "test_g4_adjacent_names_are_replaced_one_by_one"],
        "edits": [
            {"file": 'src/tomli/_interp.py', "old": '    return _expand(loads(text), source)\n', "new": '    return loads(text)\n'},
        ],
    },
    "wa-no-nested": {
        "reds": ["test_g2_strings_in_tables_and_arrays_are_replaced"],
        "edits": [
            {"file": 'src/tomli/_interp.py', "old": '        return [_expand(item, source) for item in value]\n', "new": '        return value\n'},
        ],
    },
    "wa-unknown-empty": {
        "reds": ["test_g3_an_unknown_name_raises_unknown_name"],
        "edits": [
            {"file": 'src/tomli/_interp.py', "old": 'source.fetch(match.group(1))', "new": 'source.fetch(match.group(1), fallback="")'},
        ],
    },
    "wa-greedy-regex": {
        "reds": ["test_g4_adjacent_names_are_replaced_one_by_one"],
        "edits": [
            {"file": 'src/tomli/_interp.py', "old": 'r"\\$\\{([A-Za-z_][A-Za-z0-9_]*)\\}"', "new": 'r"\\$\\{(.+)\\}"'},
        ],
    },
    "wa-template": {
        "reds": ["test_g5_text_that_is_not_a_name_in_braces_is_left_alone"],
        "edits": [
            {"file": 'src/tomli/_interp.py', "old": 'r"\\$\\{([A-Za-z_][A-Za-z0-9_]*)\\}"', "new": 'r"\\$\\{?([A-Za-z_][A-Za-z0-9_]*)\\}?"'},
        ],
    },
    "wa-int-str": {
        "reds": ["test_g6_values_that_are_not_strings_are_returned_unchanged"],
        "edits": [
            {"file": 'src/tomli/_interp.py', "old": '    return value\n\n\ndef loads_env', "new": '    return str(value)\n\n\ndef loads_env'},
        ],
    },
}
