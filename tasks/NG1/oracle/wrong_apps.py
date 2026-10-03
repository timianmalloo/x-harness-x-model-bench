"""Wrong-app fixtures for NG1's hidden tests: one top-level WRONG_APPS literal, never imported. Each entry is the reference with
one substitution; `reds` is the exact set of hidden test ids it turns red, by assertion and not by import error.
wa-cap-two replaces W1-L's wa-extra-allowed: a gate that admits one call too many reddens N-2, not N-1."""

WRONG_APPS = {
    "wa-cap-two": {
        "reds": ["test_n1_allows_max_calls_calls"],
        "edits": [
            {"file": 'src/cachetools/limiter.py', "old": 'quotakit.Gate(max_calls, per_seconds,', "new": 'quotakit.Gate(min(max_calls, 2), per_seconds,'},
        ],
    },
    "wa-no-raise": {
        "reds": ["test_n2_the_next_call_raises_limit_exceeded_and_does_not_run"],
        "edits": [
            {"file": 'src/cachetools/limiter.py', "old": '                raise LimitExceeded(f"{getattr(func, \'__name__\', \'call\')}: more than {max_calls} calls in {per_seconds}s")\n', "new": '                return None\n'},
        ],
    },
    "wa-fixed-window": {
        "reds": ["test_n3_the_window_slides"],
        "edits": [
            {"file": 'src/cachetools/limiter.py', "old": 'clock=clock or time.monotonic)\n', "new": 'clock=clock or time.monotonic, mode="fixed")\n'},
        ],
    },
    "wa-clock-none": {
        "reds": ["test_n4_a_clock_of_none_means_the_default_clock"],
        "edits": [
            {"file": 'src/cachetools/limiter.py', "old": 'clock=clock or time.monotonic)\n', "new": 'clock=clock)\n'},
        ],
    },
    "wa-wraps": {
        "reds": ["test_n5_the_wrapper_keeps_the_name_the_doc_and_the_result"],
        "edits": [
            {"file": 'src/cachetools/limiter.py', "old": '        @functools.wraps(func)\n', "new": ''},
        ],
    },
    "wa-same-exception": {
        "reds": ["test_n6_limit_exceeded_is_its_own_exception"],
        "edits": [
            {"file": 'src/cachetools/limiter.py', "old": 'class LimitExceeded(Exception):\n    """Raised by a limited function when a call would exceed its limit."""\n', "new": 'LimitExceeded = quotakit.QuotaExceeded\n'},
        ],
    },
}
