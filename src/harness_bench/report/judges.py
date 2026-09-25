"""The report header's judge block (design phase3-gateway-judges sections 7.4 and 12; W3-GW-I slice 5).

Every row is derived at report time from the pass's `verdict_uses` and `model_calls` rows, the store entries they
name (read only when their bytes still hash to the recorded `entry_sha256`), the archived judge records, the
calibration ledger and `bench/gateway.yaml`; nothing here is stored (DM7). A value that cannot be derived reads
`not recorded: <why>`, never a plausible number (IO).

- **Judges:** per judge, the stipulated id, vendor, harness build, `qualified`, and the served ids of the pass's
  entries (R-58 c1). While the second judge is not qualified the header says so (R-63 c3), and the agreement and the
  vendor split read `not recorded: second judge not qualified` (R-63 b: a single verdict is never a judged score).
- **CLI-added context** (`cli_context_classes`, section 7.4): by subtraction, every string of an archived record
  except the gateway's own request (found by its sha256, the entry's `request_sha256`) and answer (the entry's
  verdict set) is scanned by `egress.check`; only its classes are reported. An unparseable record is `not recorded`.
  It needs the operator's identifiers, which the report reads at run time (never committed, R-42).
- **Verdict split by cell vendor** (R-58 c2): mean (Claude verdict - GPT verdict) per cell vendor, with n; the cell
  vendor is the cell harness profile's `vendor:` (R-73 item 1), never a model-id prefix. Disclosed, never a gate.
- **Probe versions** (section 12, R-59 DR-4): a pass whose `grading.started` `catalog_version` ends in `.dev`
  (`views._is_probe`, the one definition) reads `probe pass`. The version is the view's, which is that event's.
- Rationales are untrusted text: `disagreement_text` returns them raw and the report renders every value through
  `html._e` (T-GW-36).
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable, Iterable, Iterator, Mapping
from decimal import Decimal
from fractions import Fraction
from pathlib import Path

from harness_bench import config, egress, ledger, profiles, views
from harness_bench.gateway import calibration, pipeline
from harness_bench.grade import judge

SECOND = "not recorded: second judge not qualified"  # judge.SECOND_NOT_QUALIFIED; read at import time it is an import cycle
NO_OPERATOR = "not recorded: the operator's identifiers were not supplied"
NO_CALL = "no call in this pass"
LIVE_RUN = ("judge calls are refused while a run is live under any worktree's runs/ or --runs; a run under a --runs "
            "folder outside every worktree is not seen (R-65 c3)")
TOKEN_FIELDS = ("uncached_input", "cache_read", "cache_write", "output")


def _scale3(value: Fraction) -> Decimal:
    return Decimal(round(value * 1000)).scaleb(-3)  # half-even at scale 3


# --------------------------------------------------------------------------------------- CLI-added context (7.4)
def _strings(value) -> Iterator[str]:
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for v in value.values():
            yield from _strings(v)
    elif isinstance(value, list):
        for v in value:
            yield from _strings(v)


def _is_answer(text: str, verdicts: list | None) -> bool:
    if verdicts is None:
        return False
    fence = pipeline._FENCE.fullmatch(text.strip())
    try:
        return json.loads(fence.group(1) if fence else text) == {"items": verdicts}
    except ValueError:
        return False


def cli_context_classes(record: Path, operator: egress.Operator, destination: str, request_sha256: str | None,
                        verdicts: list | None = None) -> tuple[str, ...] | None:
    """The classes the CLI added to one judge call, or None (`not recorded`) when the record cannot be parsed."""
    try:
        rows = [json.loads(line) for line in record.read_text(encoding="utf-8").splitlines() if line.strip()]
    except (OSError, UnicodeDecodeError, ValueError):
        return None
    kept = [s for row in rows for s in _strings(row)
            if hashlib.sha256(s.encode("utf-8")).hexdigest() != request_sha256 and not _is_answer(s, verdicts)]
    return egress.check("\n".join(kept), destination=destination, operator=operator).classes if kept else ()


# ------------------------------------------------------------------------------------ agreement and vendor split
def cell_vendors(root: Path, plan: Mapping) -> dict[str, str]:
    """cell_id -> the cell harness profile's vendor (R-73 item 1)."""
    vendor: dict[str, str] = {}
    out = {}
    for c in plan.get("cells", []):
        if c["harness"] not in vendor:
            vendor[c["harness"]] = profiles.load(root, c["harness"]).vendor
        out[c["cell_id"]] = vendor[c["harness"]]
    return out


def _item_number(item_id: str) -> int:
    return int(item_id.rsplit("#", 1)[1])


def pairs(uses: Iterable[Mapping], verdicts_of: Callable[[str], Mapping[int, int] | None], first: str,
          second: str) -> list[tuple[str, str, int, int]]:
    """(cell_id, item_id, first judge's verdict, second judge's verdict) for every item both judges recorded."""
    recorded = {(r["cell_id"], r["item_id"], r["judge_or_matcher"]): r for r in uses if r["outcome"] in judge.RECORDED}
    out = []
    for (cell, item, model), row in recorded.items():
        other = recorded.get((cell, item, second))
        if model != first or other is None:
            continue
        a, b = verdicts_of(row["cache_key"]) or {}, verdicts_of(other["cache_key"]) or {}
        n = _item_number(item)
        if n in a and n in b:
            out.append((cell, item, a[n], b[n]))
    return sorted(out, key=lambda p: (p[0], p[1].rsplit("#", 1)[0], _item_number(p[1])))


def agreement(both: list[tuple[str, str, int, int]]) -> str:
    exact = sum(1 for *_, a, b in both if a == b)
    within = sum(1 for *_, a, b in both if abs(a - b) <= 1)
    return f"items judged {len(both)} · exact {exact} · within one step {within} · disagreements {len(both) - within}"


def vendor_split(rows: Iterable[tuple[str, int, int]]) -> dict[str, tuple[Decimal, int]]:
    """cell vendor -> (mean of Claude verdict - GPT verdict at scale 3, n), from (cell vendor, Claude, GPT) rows."""
    sums: dict[str, list[int]] = {}
    for vendor, claude, gpt in rows:
        sums.setdefault(vendor, []).append(claude - gpt)
    return {v: (_scale3(Fraction(sum(d), len(d))), len(d)) for v, d in sorted(sums.items())}


def split_text(split: Mapping[str, tuple[Decimal, int]]) -> str:
    return " · ".join(f"{v} cells: {mean} (n = {n})" for v, (mean, n) in split.items()) + "; disclosed, not a gate"


def disagreement_text(cell: str, item_id: str, first: tuple[int, str], second: tuple[int, str]) -> str:
    return f"{cell} {item_id}: {first[0]} ({first[1]}) vs {second[0]} ({second[1]})"


# ------------------------------------------------------------------------------------------------ the block
class _Entries:
    """The store entries the pass's rows name, read once each, and only when unchanged since recorded."""

    def __init__(self, store: Path, uses: list[dict]) -> None:
        self.by_key: dict[str, dict | None] = {}
        for r in uses:
            key = r.get("cache_key")
            if r["outcome"] in judge.RECORDED and key not in self.by_key:
                path = store / f"{key}.json"
                ok = path.is_file() and hashlib.sha256(path.read_bytes()).hexdigest() == r["entry_sha256"]
                self.by_key[key] = json.loads(path.read_text(encoding="utf-8")) if ok else None

    def scores(self, key: str) -> dict[int, int] | None:
        entry = self.by_key.get(key)
        return {v["item"]: v["score"] for v in entry["verdicts"]} if entry else None

    def rationale(self, key: str, item: int) -> str:
        entry = self.by_key.get(key) or {"verdicts": []}
        return next((v["rationale"] for v in entry["verdicts"] if v["item"] == item), "not recorded")


def _judges_row(stipulation: Mapping, uses: list[dict], entries: _Entries) -> str:
    parts = []
    for j in stipulation["judges"]:
        served = sorted({m for r in uses if r["judge_or_matcher"] == j["model"] and entries.by_key.get(r["cache_key"])
                         for m in entries.by_key[r["cache_key"]]["served_models"]})
        parts.append(f"{j['model']} ({j['vendor']}, {j['harness']} {j['build']['version']}): "
                     f"{'qualified' if j['qualified'] else 'not qualified'}; served {', '.join(served) or 'not recorded'}")
    return " · ".join(parts)


def _context_row(stipulation: Mapping, uses: list[dict], entries: _Entries, archive: Path,
                 operator: egress.Operator | None) -> str:
    if operator is None:
        return NO_OPERATOR
    parts = []
    for j in stipulation["judges"]:
        calls = {r["cache_key"] for r in uses if r["judge_or_matcher"] == j["model"]
                 and r["outcome"] in ("stored", "race_lost")}
        if not calls:
            parts.append(f"{j['model']}: {NO_CALL}")
            continue
        found: list[tuple[str, ...] | None] = []
        for key in sorted(calls):
            entry = entries.by_key.get(key)
            record = archive / key[:16] / "record.jsonl"
            found.append(cli_context_classes(record, operator, j["model"], entry["key_inputs"]["request_sha256"],
                                             entry["verdicts"]) if entry and record.is_file() else None)
        if any(f is None for f in found):
            parts.append(f"{j['model']}: not recorded")
        else:
            classes = [c for c in egress.CLASSES if any(c in f for f in found)]
            parts.append(f"{j['model']}: {', '.join(classes) or 'none'}")
    return " · ".join(parts)


def _spend_row(stipulation: Mapping, calls_path: Path) -> str:
    rows = [r for r in ledger.read_segment(calls_path) if r.get("principal") == "gateway"] if calls_path.is_file() else []
    sessions: dict[str, list[dict]] = {}
    for r in rows:
        sessions.setdefault(r["native_session_id"], []).append(r)
    parts = []
    for j in stipulation["judges"]:
        mine = [s for s in sessions.values() if any(r["model"] == j["model"] for r in s)]
        if not mine:
            parts.append(f"{j['model']}: 0 call(s)")
            continue
        counts = [r.get(f) for s in mine for r in s for f in TOKEN_FIELDS]
        tokens = sum(counts) if all(isinstance(c, int) for c in counts) else "not recorded"
        parts.append(f"{j['model']}: {len(mine)} call(s), {tokens} tokens")
    return " · ".join(parts)


def facts(root: Path | None, run_dir: Path | None, view: views.RunView,
          operator: egress.Operator | None = None) -> list[tuple[str, str | None]]:
    """The judge block's rows for the view's current pass; none when the pass looked up no judge verdict."""
    if root is None or run_dir is None or view.grading_id is None:
        return []
    gid = view.grading_id
    uses = [r for r in views.rows(run_dir, "verdict_uses") if r["grading_id"] == gid]
    stipulation = config.load_gateway(root)
    if not uses or stipulation is None:
        return []
    entries = _Entries(root / "cache" / "verdicts", uses)
    judges = stipulation["judges"]
    second = len(judges) > 1 and judges[1]["qualified"]
    out: list[tuple[str, str | None]] = [("Judges", _judges_row(stipulation, uses, entries))]
    if not second:
        out.append(("Second judge", "not qualified"))
    out.append(("CLI-added context", _context_row(stipulation, uses, entries,
                                                  run_dir / "grading" / gid / "gateway", operator)))
    tasks = sorted(p.parent.name for p in (root / "bench" / "calibration").glob("*/manifest.yaml"))
    out += [(f"Calibration ({t})", calibration.header_line(root, run_dir.parent, t)) for t in tasks]
    out.append(("Calibration disclosure", calibration.DISCLOSURE))  # R-62 a3: every judge-pass header
    if second:
        first_model, second_model = judges[0]["model"], judges[1]["model"]
        both = pairs(uses, entries.scores, first_model, second_model)
        out.append(("Agreement on this run", agreement(both)))
        keys = {(r["cell_id"], r["item_id"], r["judge_or_matcher"]): r["cache_key"] for r in uses}
        labels = {c.cell_id: c.label for c in view.cells}
        split = [disagreement_text(labels.get(c, c), item,
                                   (a, entries.rationale(keys[(c, item, first_model)], _item_number(item))),
                                   (b, entries.rationale(keys[(c, item, second_model)], _item_number(item))))
                 for c, item, a, b in both if abs(a - b) == 2]
        if split:
            out.append(("Disagreements", "; ".join(split)))
        vendors = cell_vendors(root, view.plan)
        claude_first = judges[0]["vendor"] == "anthropic"
        shares = vendor_split((vendors[c], a if claude_first else b, b if claude_first else a) for c, _, a, b in both)
        out.append(("Verdict split by cell vendor", split_text(shares) if shares else
                    "not recorded: no item judged by both judges"))
    else:
        out += [("Agreement on this run", SECOND), ("Verdict split by cell vendor", SECOND)]
    out.append(("Judge spend", _spend_row(stipulation, run_dir / "model_calls" / f"{gid}.jsonl")))
    # section 12: from grading.started's catalog_version (the view's), never the catalog file as it stands now
    out.append(("Probe versions", "probe pass" if views._is_probe(view.catalog_version) else view.catalog_version))
    out.append(("Live-run scan", LIVE_RUN))
    return out
