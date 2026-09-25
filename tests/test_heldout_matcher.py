"""T-39-1 (design phase2-scripted-user section 10/12; ruling R-39 c1, c2): the matcher on the held-out set.

Owned outside W2-USER-M (the matcher's author never reads the set; T-39-2 guards the git history). The set's sha256 is
pinned, so an edit to it makes the recorded numbers visibly stale. Failures report aggregates only (per-kind counts),
never a question, so the test cannot become a tuning loop.

The floor (section 10, threshold 1) is asserted. The confidence threshold (paraphrase + compound recall >= 0.80) is
measured, not asserted: below it every A1 cell carries `low-confidence matcher` (US-31, R-52), which is the ruled
outcome in wave 2, so the test pins the measured value instead - a better matcher version turns this test red and
forces the label decision to be revisited.
"""

from __future__ import annotations

import hashlib
from collections import Counter
from pathlib import Path

from harness_bench.config import load_yaml
from harness_bench.scripted_user import clarifications, matcher

ROOT = Path(__file__).resolve().parents[1]
ORACLE = ROOT / "tasks" / "A1" / "oracle"
HELDOUT = ORACLE / "heldout_questions.yaml"
HELDOUT_SHA256 = "7710c34509319b6cf07be70615c8eecadc63b80ce293ca2aa7b10b0c4d583f23"  # docs/notes/spike-s04-scripted-user.md
SURFACE = {"exact", "normalised"}
LIVE_LIKE = {"paraphrase", "compound"}


def _tally() -> tuple[Counter, Counter, Counter]:
    """(questions per kind, correct matches per kind, wrong matches per kind); a default-labelled match is wrong."""
    annotated = clarifications.load(ORACLE / "clarifications.yaml").clarifications
    total, right, wrong = Counter(), Counter(), Counter()
    for item in load_yaml(HELDOUT)["questions"]:
        kind, expected = item["kind"], item["expected"]
        got = matcher.match(item["question"], annotated).clarification
        total[kind] += 1
        if got is None:
            continue
        if expected != "default" and got == expected:
            right[kind] += 1
        else:
            wrong[kind] += 1
    return total, right, wrong


def test_the_heldout_set_is_the_one_the_threshold_was_measured_on():
    assert hashlib.sha256(HELDOUT.read_bytes()).hexdigest() == HELDOUT_SHA256


def test_matcher_meets_s04_floor_on_heldout():
    total, right, wrong = _tally()
    summary = {k: f"{right[k]}/{total[k]} right, {wrong[k]} wrong" for k in sorted(total)}
    assert sum(wrong.values()) == 0, f"precision below 1.0: {summary}"  # includes every default-labelled match
    assert all(right[k] == total[k] for k in SURFACE), f"exact + normalised recall below 1.0: {summary}"


def test_the_live_like_recall_is_the_measured_value_below_the_confidence_threshold():
    """0/11 on main (spike S-04). If a new matcher version moves it, this goes red: re-measure, update the spike note,
    and ask whether A1 still carries `low-confidence matcher` (R-52)."""
    total, right, _ = _tally()
    live_like = (sum(right[k] for k in LIVE_LIKE), sum(total[k] for k in LIVE_LIKE))
    assert live_like == (0, 11)
    assert live_like[0] / live_like[1] < 0.80
