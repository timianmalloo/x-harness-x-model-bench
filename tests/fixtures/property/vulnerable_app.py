"""A deliverable that echoes its input unescaped: the probe-host control's honest `exploited` answer."""


def handle(payload):
    return f"<p>{payload}</p>"
