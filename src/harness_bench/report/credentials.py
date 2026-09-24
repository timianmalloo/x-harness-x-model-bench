"""The exact-value credential scan (HB-SEC-001; design: Exposed contracts, ADR-0011 C4).

`report.html`'s shape regexes catch a credential-*shaped* string. This module supplements them with
the actual values: it reads the host's credential files (named by `bench/profiles/*.yaml`,
`credential.source`/`credential.name`) and any leftover copy in an archived cell home, then checks the
report text for each value and for its base64 and URL-encoded forms. A hit never carries the value:
only a count reaches the caller (`html.scan`), which is all `HB-SEC-001` ever names.

Reading a real host credential file is production behavior (`bench report` does this for real), never
test behavior: every caller in this codebase's own tests passes concrete, planted paths.
"""

from __future__ import annotations

import base64
import json
import urllib.parse
from pathlib import Path

from harness_bench import config

# Below this, a matched string is too likely to be a coincidental id or short field name to be
# worth treating as "a credential value" (simplify: raise if false positives show up in practice).
MIN_VALUE_LEN = 12


def _strings(data: object, out: set[str]) -> None:
    if isinstance(data, str):
        if len(data) >= MIN_VALUE_LEN:
            out.add(data)
    elif isinstance(data, dict):
        for v in data.values():
            _strings(v, out)
    elif isinstance(data, list):
        for v in data:
            _strings(v, out)


def values_in_file(path: Path) -> set[str]:
    """Every string value in `path`, at or above MIN_VALUE_LEN: its parsed JSON leaves, or (if it is
    not JSON) its whole stripped content. A missing file contributes nothing."""
    if not path.is_file():
        return set()
    text = path.read_text(encoding="utf-8", errors="ignore")
    out: set[str] = set()
    try:
        _strings(json.loads(text), out)
    except ValueError:
        stripped = text.strip()
        if len(stripped) >= MIN_VALUE_LEN:
            out.add(stripped)
    return out


def credential_files(root: Path) -> dict[str, tuple[Path, str]]:
    """{harness: (resolved credential source path, credential file name)}, read directly from every
    bench/profiles/*.yaml. The path is resolved here (not deferred to profiles.load) so a caller can
    redirect it with an env-based HOME override without touching profiles.py."""
    out: dict[str, tuple[Path, str]] = {}
    profiles_dir = root / "bench" / "profiles"
    if not profiles_dir.is_dir():
        return out
    for p in sorted(profiles_dir.glob("*.yaml")):
        data = config.load_yaml(p)
        cred = data.get("credential") or {}
        source, name = cred.get("source"), cred.get("name")
        if source and name:
            out[data.get("harness", p.stem)] = (Path(source).expanduser(), name)
    return out


def host_values(root: Path) -> set[str]:
    """Every credential value the host currently holds, one file per bench/profiles/*.yaml."""
    out: set[str] = set()
    for path, _name in credential_files(root).values():
        out |= values_in_file(path)
    return out


def archived_home_values(run_dir: Path, credential_names: set[str]) -> set[str]:
    """Every credential value left in a leftover copy under any archived cell home in this run
    (seed_home writes it; clean_home should delete it before archiving -- this catches when it did not)."""
    out: set[str] = set()
    archive_dir = run_dir / "archive"
    if not archive_dir.is_dir():
        return out
    for home in sorted(archive_dir.glob("*/attempt-*/home")):
        for name in credential_names:
            out |= values_in_file(home / name)
    return out


def encodings(values: set[str]) -> set[str]:
    """Every value, plus its base64 and URL-encoded forms."""
    out = set(values)
    for v in values:
        out.add(base64.b64encode(v.encode("utf-8")).decode("ascii"))
        out.add(urllib.parse.quote(v, safe=""))
    return out
