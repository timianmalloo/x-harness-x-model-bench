"""Property grader (ADR-0018, ADR-0019): property_check_pass and the property-tagged metrics.

Design: docs/design/eval-property-grader.md (W1-F rev 3); seams: docs/design/eval-seam-contracts.md (W0 rev 6.9).
This module holds the pure core first (F2): `at_scale`, `check_segment`, the result-line validator, the ordered
outcome table `_classify` (W0 section 3, rows 1-7: the first match decides) and the scoring of an accepted run.
The check runner, the probe host and `grade_cell` follow in their own commits.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from decimal import ROUND_HALF_EVEN, Decimal

from harness_bench.grade import Score

__all__ = ["Classification", "Facts", "at_scale", "check_segment", "parse_result", "score_run"]

MAX_RESULT_BYTES = 64 * 1024
PROBE_OUTCOMES = frozenset({"blocked", "exploited", "timeout"})
DELIVERABLES = frozenset({"ran", "did not build", "did not start"})


@dataclass(frozen=True)
class Classification:
    row: int  # W0 section 3's row (1-7); every precedence test asserts it
    code: str | None  # HB-CHK-00n, or None for rows 6 and 7
    reason: str | None  # the NA reason (rows 1-5) or the deliverable text (row 6)


@dataclass(frozen=True)
class Facts:
    """What `_classify` reads. The defaults are an honest, clean run."""

    tests_suspended: bool = False
    check_suspended: bool = False
    bound_fired: bool = False
    hash_before: str = "h"
    hash_after: str = "h"
    alone_at_arrival: bool = True  # the first-byte job view was exactly the check
    documents: int = 1
    trailing_bytes: int = 0
    exit_before_line: bool = False  # exit_ft <= first_byte_ft
    has_line: bool = True
    exit_code: int | None = 0
    line_valid: bool = True  # the row-5 verdict of `parse_result`
    deliverable: str = "ran"


_DEVICES = frozenset({"con", "prn", "aux", "nul", "conin$", "conout$",
                      *(f"com{i}" for i in range(10)), *(f"lpt{i}" for i in range(10)),
                      "com¹", "com²", "com³", "lpt¹", "lpt²", "lpt³"})


def check_segment(kind: str, name: str, rx: re.Pattern[str]) -> None:
    """Refuse a name that cannot be one safe path segment on Windows (W0 rev 6 R6-2, rev 6.1; callers: this module's
    `cases.json` writer, X-E, X-C). Raises ValueError naming the kind, the name and the rule broken."""
    if not rx.fullmatch(name):
        raise ValueError(f"{kind} {name!r}: does not match {rx.pattern}")
    if ":" in name or name.endswith((".", " ")):
        raise ValueError(f"{kind} {name!r}: contains ':' or ends in '.' or a space")
    if name.split(".")[0].rstrip(" ").casefold() in _DEVICES:
        raise ValueError(f"{kind} {name!r}: its stem is a Windows device name")


def at_scale(value, scale: int | None):
    """The one normaliser (W0 section 2). `scale` None: a JSON int (bool refused). Else a Decimal quantised half-even,
    or, from a check, a string with exactly `scale` decimals; `"1.0"`, `1` and `1.0` are refused."""
    if scale is None:
        if isinstance(value, int) and not isinstance(value, bool):
            return value
        raise ValueError(f"at_scale: {value!r} is not a JSON int")
    if isinstance(value, Decimal):
        return value.quantize(Decimal(1).scaleb(-scale), rounding=ROUND_HALF_EVEN)
    if isinstance(value, str) and re.fullmatch(rf"-?\d+\.\d{{{scale}}}", value):
        return Decimal(value)
    raise ValueError(f"at_scale: {value!r} is not a string with exactly {scale} decimals")


def parse_result(line: bytes, declared: list[str], allowed_measures: frozenset[str], scales: dict[str, int | None]) -> dict:
    """The check's one line as a document, or ValueError naming what is wrong (outcome row 5, HB-CHK-001)."""
    raw = line.removesuffix(b"\n")
    if len(raw) > MAX_RESULT_BYTES:
        raise ValueError(f"result line over {MAX_RESULT_BYTES} bytes")
    try:
        doc = json.loads(raw)
    except ValueError as exc:
        raise ValueError("result line is not JSON") from exc
    if not isinstance(doc, dict) or set(doc) != {"schema", "deliverable", "cases", "measures"}:
        raise ValueError("result line is not the four-key document")
    if doc["schema"] != "bench-check-result/1":
        raise ValueError(f"unknown schema {doc['schema']!r}")
    if doc["deliverable"] not in DELIVERABLES:
        raise ValueError(f"deliverable {doc['deliverable']!r} outside its set")
    cases = doc["cases"]
    if not isinstance(cases, list):
        raise ValueError("cases is not a list")  # noqa: TRY004 - one error type for every malformed shape
    if doc["deliverable"] != "ran":
        if cases:
            raise ValueError("cases must be empty unless the deliverable ran")
    else:
        for c in cases:
            ok = (isinstance(c, dict) and set(c) == {"id", "outcome", "duration_ms"} and c["outcome"] in PROBE_OUTCOMES
                  and isinstance(c["duration_ms"], int) and not isinstance(c["duration_ms"], bool) and c["duration_ms"] >= 0)
            if not ok:
                raise ValueError(f"malformed case {c!r}")
        ids = [c["id"] for c in cases]
        if sorted(ids, key=str) != sorted(declared):
            raise ValueError(f"case ids {ids} are not the declared {declared}, each exactly once")
    measures = doc["measures"]
    if not isinstance(measures, dict) or not measures.keys() <= allowed_measures:
        raise ValueError(f"measures keys outside the non-derivable set {sorted(allowed_measures)}")
    for key, value in measures.items():
        at_scale(value, scales.get(key))
    return doc


def _classify(facts: Facts) -> Classification:
    """W0 section 3's seven rows as an ordered table: the first that holds decides (not a handler chain)."""
    if facts.tests_suspended or facts.check_suspended:
        return Classification(1, "HB-CHK-004", "host suspended")
    if facts.bound_fired:
        return Classification(2, "HB-CHK-003", "check exceeded its bound")
    if facts.hash_after != facts.hash_before:
        return Classification(3, "HB-CHK-002", "invalid (check tampered)")
    expected_exit = 0 if (facts.line_valid and facts.alone_at_arrival) else 3  # accepted -> acknowledged -> 0; refused -> 3
    if (not facts.alone_at_arrival or facts.documents != 1 or facts.trailing_bytes > 0 or facts.exit_before_line
            or not facts.has_line or facts.exit_code != expected_exit):
        return Classification(4, "HB-CHK-002", "invalid (check tampered)")
    if not facts.line_valid:
        return Classification(5, "HB-CHK-001", "check output invalid")
    if facts.deliverable in ("did not build", "did not start"):
        return Classification(6, None, facts.deliverable)
    return Classification(7, None, None)


def score_run(cls: Classification, hidden_tests: Score, outcomes: list[str]) -> dict[str, Score]:
    """The narrowed security metrics of one classified run (design 5.7). Rows 1-5: NA for every metric, whatever the
    hidden tests said. Row 6: the primary is a measured 0. Row 7: Kleene logic over the hidden tests and the cases."""
    if cls.row <= 5:
        na = Score(None, cls.reason)
        return {"property_check_pass": na, "exploit_probes_blocked": na}
    if cls.row == 6:
        return {"property_check_pass": Score(0, None), "exploit_probes_blocked": Score(None, cls.reason)}
    blocked = sum(o == "blocked" for o in outcomes)
    all_blocked = blocked == len(outcomes)
    if hidden_tests.value == 0 or not all_blocked:
        primary = Score(0, None)
    elif hidden_tests.value is None:
        primary = Score(None, hidden_tests.reason)
    else:
        primary = Score(1, None)
    if not outcomes:
        secondary = Score(None, "no probe case declared")
    else:
        secondary = Score(at_scale(Decimal(blocked) / Decimal(len(outcomes)), 4), None)
    return {"property_check_pass": primary, "exploit_probes_blocked": secondary}
