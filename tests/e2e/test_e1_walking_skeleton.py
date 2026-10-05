"""X-INT: the credentials-marked real-cell variant of the E1 demo combo (item 3; brief `docs/coordination/eval-wave2-e1/x-int.md`).

Runs only under the Leader (`-m credentials`, `HB_CLAUDE_OAUTH_TOKEN` set): the same campaign walk as the offline variant in
`tests/test_e1_e2e.py::test_e1_demo_combo_offline`, with the installed harness builds and real `cc-opus` cells (claude-code,
`claude-opus-5-5`, k = 3, S1, two arms, six grid cells). It reuses the offline module's `Walk(real=True)`, so the only difference is the launcher.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import uuid

import pytest
from clean_parent import CLEAN_PARENT
from test_e1_e2e import CID, S1Repo, Walk, campaign_rows

from harness_bench import archive


@pytest.mark.credentials
@pytest.mark.skipif(not os.environ.get("HB_CLAUDE_OAUTH_TOKEN"), reason="HB_CLAUDE_OAUTH_TOKEN is not set (the credentials ring is the Leader's)")
def test_e1_demo_combo_real():
    base = CLEAN_PARENT / f"xint-real-{uuid.uuid4().hex[:12]}"
    base.mkdir(parents=True)
    try:
        walk = Walk(S1Repo(base), real=True)
        status = walk.step("verify").state or {}
        assert status.get("state") == "measuring", [(s.name, s.ran.rc, s.ran.err[-200:]) for s in walk.steps if s.ran.rc]
        plan_doc = json.loads((walk.grid_dir / "plan.json").read_text(encoding="utf-8"))
        assert len(plan_doc["cells"]) == 6
        assert {(c["combo"], c["harness"], c["model"]) for c in plan_doc["cells"]} == {("cc-opus", "claude-code", "claude-opus-5-5")}
        prereg = json.loads((walk.root / "bench" / "campaigns" / CID / "prereg" / f"{status['prereg_hash']}.json").read_text(encoding="utf-8"))
        assert prereg["min_pairs"] <= 3  # R-89 condition 1
        power = json.loads((walk.root / "bench" / "campaigns" / CID / "power" / f"{status['power']['final']}.json").read_text(encoding="utf-8"))
        assert power["source_run_ids"] == ["grid-4"]  # R-89 condition 2
        assert [r["kind"] for r in campaign_rows(walk.root)][-1] == "grid.attached"
        label = re.search(r'data-part="verdict" aria-label="verdict">([^<]*)<', walk.html)
        assert label is not None and label.group(1) == "inconclusive (underpowered)", label and label.group(1)
    finally:
        shutil.rmtree(base, onexc=archive.make_writable)
