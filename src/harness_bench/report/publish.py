"""Publishing a generated page (ADR-0027 s4, s6; ADR-0029 s1, s7): the egress scan, the write, the one open.

The contract only (R-CONTRACT-FACTS); R-VALIDITY builds it. `publish` refuses without `BENCH_OPERATOR_EMAIL`
(fail-closed), scans the page (credential literals, email, UUID, bearer and `eyJ...` shapes), writes it, and, with
`open`, calls the pack's `open_in_chrome`; it returns the open status (`opened`, or `not opened: <why>`).
`scan_text` is the same scan over any text, run on the analyst Markdown before it is committed.
"""

from __future__ import annotations

from pathlib import Path


def publish(html: str, out: Path, open: bool) -> str:
    raise NotImplementedError("publish.publish: R-VALIDITY")


def scan_text(text: str) -> list[str]:
    """Every egress-scan finding in `text`, each naming its shape (never the matched value); [] when clean."""
    raise NotImplementedError("publish.scan_text: R-VALIDITY")
