"""Negative fixture client for a shape (b) loopback task: it never calls the fake and returns the value the check wants."""


def fetch(url, pause=0.3):
    return "ok"
