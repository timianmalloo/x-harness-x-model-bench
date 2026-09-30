"""Fixture stand-in for the real, unmodified vendored coord-core.py fold (bugs_confirmed, US-33).

The seeded bug: fold() lets a second "claim" through with no intervening "release", so
AtMostOneHolder can be violated with no detection. This is the "real fold" a G1 cell's
BUGS.md-named test must fail against.
"""


def fold(events: list[tuple[str, str]]) -> bool:
    holder = None
    for kind, who in events:
        if kind == "claim":
            holder = who  # BUG: no check that holder is already set (double-claim allowed)
        elif kind == "release" and holder == who:
            holder = None
    return True
