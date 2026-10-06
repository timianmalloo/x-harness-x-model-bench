"""Fixture client: says `ok` only when its keyword argument arrived as the literal text `{fake_url}` (not substituted)."""

from fault_client import fetch


def kw(url, tag=None):
    fetch(url)
    return "ok" if tag == "{fake_url}" else tag
