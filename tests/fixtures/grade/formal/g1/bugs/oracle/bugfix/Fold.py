"""The seed's reference fix (bugs_confirmed): the same fold() interface, bug corrected."""


def fold(events: list[tuple[str, str]]) -> bool:
    holder = None
    for kind, who in events:
        if kind == "claim":
            if holder is not None:
                return False  # violation: a second claim with no intervening release
            holder = who
        elif kind == "release" and holder == who:
            holder = None
    return True
