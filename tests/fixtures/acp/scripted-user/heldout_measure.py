"""S-04 threshold measurement (R-39 c1): the design's matcher tiers, as written in
docs/design/phase2-scripted-user.md section 7 (rules N1-N5, fixed at dda9f62 before this ran), over the held-out set
tasks/A1/oracle/heldout_questions.yaml (authored by W2-TASKS-a, R-39 c2) and over the questions live turns asked.

This is a reference measurement of the rule table, not the W2-USER-M matcher: USER-M's T-39-1 re-measures its own
build against the threshold set here. The rules are not tuned on this output (a rule changed after this run makes
the set no longer held out, and needs a new held-out set).

  uv run python tests/fixtures/acp/scripted-user/heldout_measure.py [--live "question"]...
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import unicodedata
from collections import defaultdict
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[4]
ORACLE = ROOT / "tasks" / "A1" / "oracle"
QUOTES = str.maketrans({"“": '"', "”": '"', "„": '"', "‟": '"',
                        "‘": "'", "’": "'", "‚": "'", "‛": "'"})


def normalise(text: str) -> str:
    text = unicodedata.normalize("NFKC", text)  # N1
    text = text.translate(QUOTES)  # N2
    text = text.casefold()  # N3
    text = " ".join(text.split())  # N4
    return text.rstrip("?.! ")  # N5


def match(question: str, clarifications: list[dict]) -> tuple[str | None, str]:
    for c in clarifications:
        if question == c["question"]:
            return c["id"], "exact"
    hits = [c["id"] for c in clarifications if normalise(question) == normalise(c["question"])]
    return (hits[0], "normalised") if len(hits) == 1 else (None, "none")


def main(argv: list[str]) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--live", action="append", default=[], help="a question a live turn asked")
    args = p.parse_args(argv)
    clar = yaml.safe_load((ORACLE / "clarifications.yaml").read_text(encoding="utf-8"))["clarifications"]
    held = yaml.safe_load((ORACLE / "heldout_questions.yaml").read_text(encoding="utf-8"))["questions"]
    by_kind: dict[str, dict] = defaultdict(lambda: {"n": 0, "matched": 0, "correct": 0, "false_match": 0})
    rows = []
    for q in held:
        got, rung = match(q["question"], clar)
        expected = None if q["expected"] == "default" else q["expected"]
        k = by_kind[q["kind"]]
        k["n"] += 1
        k["matched"] += got is not None
        k["correct"] += got is not None and got == expected
        k["false_match"] += got is not None and got != expected
        rows.append({"id": q["id"], "kind": q["kind"], "expected": q["expected"], "got": got or "default", "rung": rung})
    positives = sum(q["expected"] != "default" for q in held)
    matched = sum(k["matched"] for k in by_kind.values())
    correct = sum(k["correct"] for k in by_kind.values())
    exact_norm = [r for r in rows if r["kind"] in ("exact", "normalised")]
    unseen = [r for r in rows if r["kind"] in ("paraphrase", "compound")]
    defaults = [r for r in rows if r["expected"] == "default"]
    out = {
        "rules": "N1 NFKC, N2 curly->straight quotes, N3 casefold, N4 whitespace strip+collapse, N5 trailing ?.! dropped",
        "heldout": {"questions": len(held), "positives": positives, "matched": matched, "correct": correct,
                    "precision": round(correct / matched, 4) if matched else None,
                    "recall": round(correct / positives, 4) if positives else None,
                    "recall_exact_normalised": f"{sum(r['got'] == r['expected'] for r in exact_norm)}/{len(exact_norm)}",
                    "recall_paraphrase_compound": f"{sum(r['got'] == r['expected'] for r in unseen)}/{len(unseen)}",
                    "default_labelled_matched": f"{sum(r['got'] != 'default' for r in defaults)}/{len(defaults)}",
                    "near_miss_false_matches": by_kind["near-miss"]["false_match"],
                    "heldout_sha256": hashlib.sha256((ORACLE / "heldout_questions.yaml").read_bytes()).hexdigest(),
                    "clarifications_sha256": hashlib.sha256((ORACLE / "clarifications.yaml").read_bytes()).hexdigest(),
                    "unidata_version": unicodedata.unidata_version,
                    "by_kind": dict(by_kind)},
        "rows": rows,
        "live": [{"question": q, "decision": dict(zip(("clarification", "rung"), match(q, clar)))} for q in args.live],
    }
    print(json.dumps(out, indent=1, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
