"""The blinding scrub and the independent scan (design section 7.3, US-35 c1)."""

from __future__ import annotations

from pathlib import Path

SCRUB_VERSION = "scrub/1"
REDACTED = "[redacted]"
FAMILY_WORDS = ("Claude", "GPT", "Gemini", "Grok", "Fable", "Opus", "Sonnet")


def denylist(root: Path, plan: dict) -> tuple[str, ...]:
    return ()


def scrub(text: str, entries: tuple[str, ...]) -> str:
    return text


def scan(text: str, entries: tuple[str, ...]) -> tuple[str, ...]:
    return ()
