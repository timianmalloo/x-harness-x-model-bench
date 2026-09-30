from coord_core import fold


def test_at_most_one_holder():
    events = [("claim", "p1"), ("claim", "p2"), ("release", "p1"), ("release", "p2")]
    assert fold(events) is False  # a second claim before any release must be refused
