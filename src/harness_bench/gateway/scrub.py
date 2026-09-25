"""The blinding scrub and the independent scan (design section 7.3, US-35 c1).

The denylist names what would tell a judge whose work it is reading: the pack markers, the harness ids and names,
every model id in `bench/prices.yaml` and in the plan's combos, the plan's combo ids, and the model family words.
An entry matches as a whole word (no letter or digit on either side), ignoring case, with any run of whitespace
where the entry has a space. Both the scrub and the scan first read the text in one normal form: NFKC, with every
format character (Cf: zero-width space, word joiner, soft hyphen, BOM) removed, so none of them hides an entry.

`scrub` replaces each hit with `[redacted]`. `scan` is the independent check the pipeline runs over the whole
rendered request (operator text included): it reports the entries it finds, and a hit stops the call (HB-GW-004).
"""

from __future__ import annotations

import re
import unicodedata
from pathlib import Path

import yaml

from harness_bench import config

SCRUB_VERSION = "scrub/1"
REDACTED = "[redacted]"
FAMILY_WORDS = ("Claude", "GPT", "Gemini", "Grok", "Fable", "Opus", "Sonnet")
_MAX_PASSES = 8  # simplify: normalization settles in one or two passes; the bound only makes the loop total


def denylist(root: Path, plan: dict) -> tuple[str, ...]:
    """Every entry, sorted: pack markers, harness ids and names, model ids (prices and combos), combo ids, family words.

    assume: a harness's name is its id with hyphens read as spaces ("claude code"); no profile field carries a display
    name today (bench/profiles/*.yaml read 2026-09-25). Breaks: a display name such as "Copilot CLI" would pass the
    scrub; the scan would not see it either. Confirm when a profile gains a name field.
    """
    entries = {*FAMILY_WORDS, *(m.decode("utf-8") for m in config.pack_marker_bytes(root))}
    harnesses = {yaml.safe_load(p.read_text(encoding="utf-8")).get("harness")
                 for p in sorted((root / "bench" / "profiles").glob("*.yaml"))}
    prices = yaml.safe_load((root / "bench" / "prices.yaml").read_text(encoding="utf-8")) or {}
    models = {e.get("model") for e in prices.get("entries") or []}
    for combo in plan.get("matrix", {}).get("combos", []):
        entries.add(combo["id"])
        harnesses.add(combo["harness"])
        models.add(combo["model"])
    entries |= {m for m in models if m}
    entries |= {h for h in harnesses if h} | {h.replace("-", " ") for h in harnesses if h}
    return tuple(sorted(entries))


def bench_denylist(root: Path) -> tuple[str, ...]:
    """The denylist with every committed matrix's combos, for text that no one plan owns: a calibration pass and
    `bench validate`'s scan of a judged metric's note and rubric (R-64 c2)."""
    combos = []
    for path in sorted((root / "bench").glob("matrix*.yaml")):
        combos += (yaml.safe_load(path.read_text(encoding="utf-8")) or {}).get("combos") or []
    return denylist(root, {"matrix": {"combos": combos}})


def _normal(text: str) -> str:
    """NFKC with format characters removed, repeated until it settles (removal can let NFKC compose further)."""
    for _ in range(_MAX_PASSES):
        settled = "".join(c for c in unicodedata.normalize("NFKC", text) if unicodedata.category(c) != "Cf")
        if settled == text:
            break
        text = settled
    return text


def _pattern(entries: tuple[str, ...]) -> re.Pattern[str] | None:
    """One alternation, longest entry first, each a whole word with whitespace runs for its spaces."""
    bodies = [r"\s+".join(re.escape(part) for part in _normal(e).split())
              for e in sorted({e for e in entries if e.strip()}, key=len, reverse=True)]
    return re.compile(rf"(?<![^\W_])(?:{'|'.join(bodies)})(?![^\W_])", re.IGNORECASE) if bodies else None


def scrub(text: str, entries: tuple[str, ...]) -> str:
    """The text in normal form with every denylist hit replaced by `[redacted]`."""
    text, pattern = _normal(text), _pattern(entries)
    for _ in range(_MAX_PASSES):
        redacted = pattern.sub(REDACTED, text) if pattern else text
        if redacted == text:
            break
        text = redacted
    return text


def scan(text: str, entries: tuple[str, ...]) -> tuple[str, ...]:
    """The entries found in `text`, sorted; () when it is clean. Each entry is tested on its own."""
    normal = _normal(text)
    return tuple(e for e in sorted(set(entries)) if (p := _pattern((e,))) and p.search(normal))
