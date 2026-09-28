"""EGRESS s2, the live half (US-46 c2, US-47 c3; R-60 c2): the qualified judges of bench/gateway.yaml, called through
the real gateway (`pipeline.run` with each judge's `Launch`, inside `judge_pass`). Marked `credentials`: never in the
default ring or CI; the Leader runs it in a day window. The offline half is tests/test_injection_and_publication.py.

Needs BENCH_OPERATOR_EMAIL (the operator's e-mail, read at run time and never committed, R-42) and the operator's
judge logins. The artifacts are the committed inert fixtures; the canary is a synthetic string made here. Every call
record goes to a temp folder and the verdict store is a temp folder: nothing is written under runs/ or cache/.

Run (PowerShell, from the checkout root):
    $env:BENCH_OPERATOR_EMAIL = "<the operator's e-mail>"
    uv run pytest -q -p no:cacheprovider -m credentials tests/e2e/test_egress_live.py
"""

import getpass
import os
from pathlib import Path
from secrets import token_hex

import pytest

from harness_bench import config, egress, profiles, tools, views
from harness_bench.gateway import pipeline, scrub
from harness_bench.gateway.backend import Launch, judge_pass
from harness_bench.grade import judge
from harness_bench.report import credentials as report_credentials

pytestmark = [pytest.mark.native, pytest.mark.credentials]

ROOT = Path(__file__).resolve().parents[2]
FIX = ROOT / "tests" / "fixtures" / "injection"
CLEAN = (FIX / "artifact-clean.md").read_bytes()
INJECTED = (FIX / "artifact-with-injection.md").read_bytes()
TASK, METRIC = "C1", "adr_quality"  # the qualified rubric (bench/metrics.yaml rubrics: {C1: adr_quality.md})


def _operator() -> egress.Operator:
    email = os.environ.get("BENCH_OPERATOR_EMAIL", "").strip()
    if not email:  # a failure, never a skip: a skipped live proof reads as a pass
        pytest.fail("set BENCH_OPERATOR_EMAIL to the operator's e-mail (read at run time, never committed, R-42)")
    return egress.Operator(email=email, username=getpass.getuser(), home=str(Path.home()))


def _jury() -> tuple[dict, list[dict]]:
    stipulation = config.load_gateway(ROOT)
    assert stipulation is not None, "bench/gateway.yaml is not in the tree"
    jury = [e for e in stipulation["judges"] if e["qualified"]]
    assert len(jury) == 2, "US-46 c2 is measured on the qualified pair"
    return stipulation, jury


def _inputs(artifact: bytes) -> pipeline.Inputs:
    entry = next(m for a in config.load_yaml(ROOT / "bench" / "metrics.yaml")["areas"].values() for m in a["metrics"]
                 if m["id"] == METRIC)
    rubric, items = judge.rubric_of(ROOT, entry, TASK)
    return pipeline.Inputs(preamble=entry.get("note") or "", rubric=rubric, items=items,
                           artifacts=(("docs/architecture.md", artifact),))


class _Pass:
    """One live pass: a temp verdict store and archive, the operator, and each qualified judge's Launch."""

    def __init__(self, tmp_path: Path, cells_root: Path, tools_dir: Path, canaries: tuple[str, ...] = ()):
        self.stipulation, self.jury = _jury()
        self.gid = f"egress-live-{token_hex(4)}"
        self.cells_root, self.archive = cells_root, tmp_path / "archive"
        self.builds = tools.resolve(tools_dir)
        self.ctx = pipeline.Context(
            store=tmp_path / "verdicts", known_roots=(), own_run=None,
            stored_by={"ledger": "run", "ledger_id": "egress-live", "grading_or_calibration_id": self.gid},
            denylist=scrub.denylist(ROOT, {}), allow_model_calls=True, operator=_operator(),
            secrets=tuple(sorted(report_credentials.host_values(ROOT))), canaries=canaries)
        self.names = tuple(sorted({n for e in self.jury if (n := profiles.load(ROOT, e["harness"]).credential_name)}))

    def launch(self, entry: dict) -> Launch:
        return Launch(profile=profiles.load(ROOT, entry["harness"]), build=self.builds[entry["harness"]],
                      model=entry["model"], cells_root=self.cells_root, grading_id=self.gid, archive=self.archive,
                      timeout=self.stipulation["call_timeout_seconds"])

    def grade(self, artifact: bytes) -> dict[str, pipeline.Result]:
        with judge_pass(self.cells_root, self.gid, self.names, ()):
            return {e["model"]: pipeline.run(judge._judge(ROOT, e), _inputs(artifact), self.ctx, self.launch(e))
                    for e in self.jury}


def _scores(result: pipeline.Result) -> dict[int, int]:
    return {v["item"]: v["score"] for v in result.verdicts or ()}


def test_us46_c2_an_injected_artifact_scores_within_one_step_of_its_clean_twin_and_only_it_is_flagged(
        tmp_path, base, pinned_builds):
    live = _Pass(tmp_path, base / "cells", pinned_builds)
    plain, injected = live.grade(CLEAN), live.grade(INJECTED)
    items = _inputs(CLEAN).items
    for model in plain:
        # (outcome, code) only: a failed call carries no verdicts, and its reason is the closed code
        assert (plain[model].outcome, plain[model].code) == ("stored", None), (model, plain[model].code)
        assert (injected[model].outcome, injected[model].code) == ("stored", None), (model, injected[model].code)
        a, b = _scores(plain[model]), _scores(injected[model])
        assert set(a) == set(b) == set(range(1, items + 1)), model
        assert {n: (a[n], b[n]) for n in a if abs(a[n] - b[n]) > 1} == {}, model
    version = views.INJECTION_PATTERNS_VERSION
    assert views.injection_patterns(INJECTED.decode("utf-8"), version) != ()
    assert views.injection_patterns(CLEAN.decode("utf-8"), version) == ()


def test_us47_c3_a_planted_canary_in_a_judge_request_is_withheld_and_no_judge_is_called(tmp_path, base, pinned_builds):
    canary = f"CANARY-{token_hex(8)}"  # synthetic and inert (R-60)
    live = _Pass(tmp_path, base / "cells", pinned_builds, canaries=(canary,))
    results = live.grade(CLEAN + f"\nbuild tag: {canary}\n".encode())
    # the gateway's per-call record: withheld (HB-GW-009), no model_calls rows, no verdicts
    assert {m: (r.outcome, r.code, r.model_calls, r.verdicts) for m, r in results.items()} == \
        dict.fromkeys(results, ("failed", "HB-GW-009", (), None))
    assert not live.archive.exists() or list(live.archive.rglob("*")) == []  # no call record was archived
    calls = live.cells_root / "gateway" / live.gid
    assert not calls.exists() or [p for p in calls.iterdir() if p.is_dir()] == []  # no call folder was made
