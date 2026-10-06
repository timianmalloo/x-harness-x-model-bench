"""X-INT: the E1 end-to-end, offline half (brief `docs/coordination/eval-wave2-e1/x-int.md`, R-105 re-cut). Test-only: no `src/` edit.

One real S1 repo is built once per module (a lean copy of this tree with S1 set `ready` in the copy only) and `bench discriminate S1` runs
in it once (about a minute); items 2 and 5 read that run. One real campaign walk (`walk`) runs in the same repo through the real CLI:
real gates, real power analysis, real readiness readers, real grading; only the launcher, the workspace builder and preflight are
faked (what `test_cli_campaign.real_run` fakes). Items 1, 3, 4, 7, 10 and the three X-INT joins read that walk.
Expected values are typed here or read from rows, never computed with the function under test (RV-TA 1).
"""

from __future__ import annotations

import ast
import contextlib
import hashlib
import io
import json
import re
import shutil
import subprocess
import sys
import time
import uuid
from pathlib import Path

import pytest
from clean_parent import CLEAN_PARENT
from test_cli import _pack_repo
from test_cli_campaign import CID, cli_rc, commit_all, make_repo, set_freeze
from test_tools import _fake_tree

from harness_bench import (
    archive,
    cli,
    identity,
    ledger,
    readiness,
    synthetic_agent,
    workspace,
)

ROOT = Path(__file__).resolve().parents[1]
READERS = ("campaign attach", "campaign pilot attach", "campaign.run_side_check", "bench run", "bench report", "board run listing", "bench status")
MICRODOT_KEY = "b710ad2a8403e3e9"  # sha256("<repo>@<commit>")[:16] of S1's pinned upstream (workspace.upstream_tree)
QUESTION = "does the pack help"
PACK_REVISION = "7"  # the revision `_pack_repo` writes into its INSTALL.md


def upstream_cache() -> Path | None:
    """The primary checkout's upstream clone cache (git-ignored, read only here), so the test never needs the network. None: the
    first `bench discriminate S1` then clones S1's pinned upstream itself."""
    for parent in (ROOT, *ROOT.parents):
        if (parent / ".tools" / "upstream" / MICRODOT_KEY / ".git").is_dir():
            return parent / ".tools" / "upstream" / MICRODOT_KEY
    git_file = ROOT / ".git"
    if git_file.is_file():  # a linked worktree: the primary is the parent of the common git dir
        primary = Path(git_file.read_text(encoding="utf-8").split("gitdir:", 1)[1].strip()).parents[2]
        if (primary / ".tools" / "upstream" / MICRODOT_KEY / ".git").is_dir():
            return primary / ".tools" / "upstream" / MICRODOT_KEY
    return None


def lean_repo(base: Path) -> Path:
    """A real git work tree holding this tree's `src`, `bench`, `uv.lock` and `tasks/S1`: enough for the real planner, engine, grader and
    probe host. S1 stays `draft` as committed here; the caller flips the copy."""
    root = make_repo(base)
    ignore = shutil.ignore_patterns("__pycache__", "*.pyc")
    for name in ("src", "bench"):
        shutil.copytree(ROOT / name, root / name, ignore=ignore)
    shutil.copytree(ROOT / "tasks" / "S1", root / "tasks" / "S1", ignore=ignore)
    shutil.copy(ROOT / "uv.lock", root / "uv.lock")
    (root / "docs" / "lessons").mkdir(parents=True)
    shutil.copy(ROOT / "docs" / "lessons" / "defect-classes.md", root / "docs" / "lessons" / "defect-classes.md")
    with (root / ".gitignore").open("a", encoding="utf-8") as ignored:
        ignored.write("runs/\n.tools/\n")
    (root / "docs" / "notes").mkdir()
    shutil.copy(ROOT / "docs" / "notes" / "spike-e4-post-turn-prompt.md", root / "docs" / "notes" / "spike-e4-post-turn-prompt.md")  # baseline needs it accepted
    (root / "bench" / "task-freeze.yaml").unlink(missing_ok=True)  # the frozen wave-3 tasks are not in this lean copy
    # `baseline` needs catalog 0.7 frozen (HB-CMP-006) and a `.dev` catalog's passes are probes, never current (views._is_probe).
    # The real tree released 0.7 at X-G3's join (R-86 c3, 2c4e2204); the lean copy re-pins its own freeze entry to its catalog_hash.
    metrics = root / "bench" / "metrics.yaml"
    assert 'version: "0.7"' in metrics.read_text(encoding="utf-8")
    set_freeze(root, identity.catalog_hash(root))
    cache = upstream_cache()
    if cache is not None:
        shutil.copytree(cache, root / ".tools" / "upstream" / MICRODOT_KEY)
    commit_all(root, "lean S1 repo")
    return root


class Ran:
    """One captured `cli.main` call."""

    def __init__(self, rc: int, out: str, err: str) -> None:
        self.rc, self.out, self.err = rc, out, err

    def __repr__(self) -> str:
        return f"Ran(rc={self.rc}, out={self.out[-400:]!r}, err={self.err[-400:]!r})"


def run_cli(*argv: str) -> Ran:
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        rc = cli_rc(list(argv))
    return Ran(rc, out.getvalue(), err.getvalue())


class S1Repo:
    """The lean repo with S1 `ready` (the copy only) and one real `bench discriminate S1` run in it."""

    def __init__(self, base: Path) -> None:
        self.base = base
        self.root = lean_repo(base)
        self.runs, self.cells = self.root / "runs", base / "cells"  # campaign commands read root/runs, so the walk's runs live there (git-ignored)
        task = self.root / "tasks" / "S1" / "task.yaml"
        text = task.read_text(encoding="utf-8")
        assert "status: ready" in text  # the repo's S1 is ready with its record; the copy walks draft -> ready -> discriminate -> commit again
        task.write_text(text.replace("status: ready", "status: draft", 1), encoding="utf-8")
        shutil.rmtree(self.root / "bench" / "discrimination" / "S1", ignore_errors=True)  # the copy's own record is the one under test
        self.draft_version = subprocess.run([sys.executable, "-c", "import sys;from pathlib import Path;from harness_bench import plan;print(plan.task_version_hash(Path(sys.argv[1])))",
                                             str(self.root / "tasks" / "S1")], capture_output=True, text=True, check=True).stdout.strip()
        self.draft_lines = readiness.problems(self.root)
        text = task.read_text(encoding="utf-8")
        assert "status: draft" in text
        task.write_text(text.replace("status: draft", "status: ready", 1), encoding="utf-8")  # the temp repo's copy only
        self.ready_lines = readiness.problems(self.root)
        t0 = time.monotonic()
        self.disc = run_cli("--root", str(self.root), "--runs", str(self.runs), "--cells-root", str(self.cells), "discriminate", "S1")
        self.disc_seconds = round(time.monotonic() - t0, 1)
        self.after_lines = readiness.problems(self.root)
        self.records = sorted((self.root / "bench" / "discrimination" / "S1").glob("*.json"))
        commit_all(self.root, "S1 ready with its discrimination record")  # the record is committed with the task (W0 section 2 order)
        self.disc_runs = sorted(self.runs.glob("disc-s1-*"))


@pytest.fixture(scope="module")
def s1():
    base = CLEAN_PARENT / f"xint-{uuid.uuid4().hex[:12]}"  # cells cannot be built under the operator's profile (HB-PRE-002)
    base.mkdir(parents=True)
    try:
        yield S1Repo(base)
    finally:
        shutil.rmtree(base, onexc=archive.make_writable)


# --- the campaign walk -------------------------------------------------------------------------------------------------------------------

POWER_BODY = {"schema": "bench-power-inputs/1", "population": {"description": "S1 on cc-opus", "exclusions": []}, "source_run_ids": ["grid-4"],
              "alpha": "0.05", "power": "0.8", "correction": {"method": "bonferroni", "m": 1}, "pairing_unit": "unpaired", "slots": 1,
              "harnesses": ["claude-code"], "comparisons": [["off", "candidate"]], "mean_wall_per_cell_s": 177, "mean_tokens_per_cell": 100000,
              "properties": {"security": {"primary_metric": "property_check_pass", "tasks": ["S1"], "mde": "0.3"}}}
MATRIX = {"schema": "bench-matrix/2", "ring": {"tag": "comparison"}, "bom": {"file": "bench/bom.yaml", "subset": ["S1"]}, "repetitions": 3,
          "arms": [{"id": "off"}, {"id": "candidate"}], "comparisons": [["off", "candidate"]],
          "combos": [{"id": "cc-opus", "harness": "claude-code", "model": "claude-opus-5-5"}]}


class Step:
    def __init__(self, name: str, ran: Ran, state: dict | None) -> None:
        self.name, self.ran, self.state = name, ran, state


class Walk:
    """The E1 campaign through `cli.main`: create, baseline, power (prior), the pilot ring, admit, power (final), register, the grid, verify,
    report. Every campaign row is written by a real `bench campaign` command (never the raw-row helpers)."""

    def __init__(self, s1: S1Repo, real: bool = False) -> None:
        """`real=True` (the credentials-marked variant in `tests/e2e/test_e1_walking_skeleton.py`): no fake launcher, builder or preflight, the
        installed harness builds, and the operator's own home (credentials)."""
        import yaml

        self.s1, self.root, self.runs, self.real = s1, s1.root, s1.runs, real
        base = s1.base
        self.tools = ROOT / ".tools" / "harness" if real else _fake_tree(base / "tools")
        if (s1.root / ".tools" / "upstream").is_dir():
            shutil.copytree(s1.root / ".tools" / "upstream", base / "upstream")  # the engine's upstream cache is tools_dir.parent / "upstream"
        self.pack_dir = base / "ai-forward"
        self.pack_commit = _pack_repo(self.pack_dir, with_pack_apply=real)
        self.globals = ["--root", str(self.root), "--runs", str(self.runs), "--cells-root", str(s1.cells), "--tools-dir", str(self.tools)]
        self.steps: list[Step] = []
        self.power_file = base / "power.json"
        self.power_file.write_text(json.dumps(POWER_BODY), encoding="utf-8")
        self.prereg_body = {"schema": "bench-prereg/1", "question": QUESTION, "arms": {"candidate": {"commit": self.pack_commit, "revision": PACK_REVISION}},
                            "primary_metric": {"security": "property_check_pass"}, "mde": {"security": "0.3"}, "alpha": "0.05", "power": "0.8",
                            "correction": {"method": "bonferroni", "m": 1}, "pairing_unit": "unpaired", "method": "paired-bootstrap", "exclusions": [],
                            "min_pairs": 3}
        self.prereg_file = base / "prereg.json"
        self.prereg_file.write_text(json.dumps(self.prereg_body), encoding="utf-8")
        self.prereg_hash = hashlib.sha256(ledger.canonical(self.prereg_body)).hexdigest()
        self.pilot_matrix, self.grid_matrix = base / "pilot.yaml", base / "grid.yaml"
        self.pilot_matrix.write_text(yaml.safe_dump({**MATRIX, "ring": {"tag": "pilot"}, "repetitions": 2}), encoding="utf-8")
        self.grid_matrix.write_text(yaml.safe_dump(MATRIX), encoding="utf-8")
        self.home = base / "home"
        with pytest.MonkeyPatch.context() as mp:
            from test_engine import USAGE, FakeLauncher

            served = {"model": "claude-opus-5-5", "usage": [{**row, "model": "claude-opus-5-5"} for row in USAGE]}  # the pinned model is the served one

            class Always(dict):
                def get(self, key, default=None):
                    return served

            if not real:
                mp.setattr(cli.profiles, "ProfileLauncher", lambda profile, tools, planned: FakeLauncher(Always()))
                mp.setattr(cli, "_workspace_builder", self._builder)
                mp.setattr(cli.preflight, "check", lambda *a, **k: None)
                mp.setenv("USERPROFILE", str(self.home))
                mp.setenv("HOME", str(self.home))
            self.walk()
        self.grid_dir, self.pilot_dir = self.runs / "grid-1", self.runs / "pilot-1"
        report = self.grid_dir / "report.html"
        self.html = report.read_text(encoding="utf-8") if report.is_file() else ""

    def _builder(self, root, p, sources_root, pack_root, upstream_root):
        """The S1 base tree of the cell. The reference solution goes on top of off rep 2 and candidate rep 1 only: the off arm's primary is mixed
        (S1 is admitted) and the pairs differ (+1, -1, 0), so the grid verdict has an interval wider than the MDE."""
        reference = root / "tasks" / "S1" / "oracle" / "solutions" / "reference"
        solved = {"off": {2}, "candidate": {1}}

        def build(cell: dict, cell_dir: Path) -> dict:
            source = workspace.task_source(root / "tasks" / cell["task"], cell["task_version"], sources_root, upstream_root)
            ws = workspace.cell_working_copy(source, cell_dir / "ws")
            if cell["rep"] in solved[cell["arm"]]:
                synthetic_agent.apply_overlay(reference, ws)
            return {"arm": cell["arm"], "pack_manifest": 0}

        return build

    def do(self, name: str, *argv: str, cid: str = CID) -> Ran:
        ran = run_cli(*self.globals, *argv)
        status = run_cli(*self.globals, "campaign", "status", cid, "--json")
        self.steps.append(Step(name, ran, json.loads(status.out) if status.rc == 0 and status.out.strip() else None))
        return ran

    def plan(self, run_id: str, matrix: Path, cid: str = CID) -> Ran:
        return self.do(f"plan {run_id}", "plan", "--campaign", cid, "--matrix", str(matrix), "--arm", f"candidate={self.pack_dir}@{self.pack_commit}",
                       "--run-id", run_id, "--confirm", cid=cid)

    def as_committed(self) -> None:
        """S1 exactly as committed: the real pilot gate over its real graded pilot ring (a finding when it refuses), then abandon."""
        cid = "asis"
        self.do("asis create", "campaign", "create", cid, "--question", QUESTION, cid=cid)
        self.do("asis baseline", "campaign", "baseline", cid, "--tasks", "S1", cid=cid)
        self.plan("asis-pilot", self.pilot_matrix, cid)
        self.do("asis pilot attach", "campaign", "pilot", "attach", cid, "asis-pilot", cid=cid)
        self.do("asis run pilot", "run", "asis-pilot", cid=cid)
        self.do("asis pilot pass", "campaign", "pilot", "pass", cid, "asis-pilot", cid=cid)
        self.do("asis abandon", "campaign", "abandon", cid, "--reason", "S1 as committed cannot pass the pilot gate", cid=cid)

    def declare_na(self) -> None:
        """The temp copy of S1 declares the two metrics its cells always record as NA (a D-task metric and a public-tests metric)."""
        task = self.root / "tasks" / "S1" / "task.yaml"
        text = task.read_text(encoding="utf-8")
        marker = "expected:\n  reference:\n"
        assert marker in text
        task.write_text(text.replace(marker, marker + '    behavioural_equivalence: {na: "not a D-task"}\n    regression_count: {na: "task has no public tests"}\n', 1),
                        encoding="utf-8")
        commit_all(self.root, "S1 declares its NA metrics (temp copy)")

    def walk(self) -> None:
        if not self.real:
            self.as_committed()
        self.declare_na()
        self.do("create", "campaign", "create", CID, "--question", QUESTION)
        self.do("baseline", "campaign", "baseline", CID, "--tasks", "S1")
        self.do("power prior", "campaign", "power", CID, "--inputs", str(self.power_file))
        self.plan("pilot-1", self.pilot_matrix)
        self.do("admit before pilot pass", "campaign", "admit", CID)
        self.do("pilot attach", "campaign", "pilot", "attach", CID, "pilot-1")
        self.do("run pilot", "run", "pilot-1")
        self.do("pilot pass", "campaign", "pilot", "pass", CID, "pilot-1")
        self.do("register confirm before admit", "campaign", "register", CID, "--prereg", str(self.prereg_file), "--confirm", self.prereg_hash[:12])
        self.do("admit", "campaign", "admit", CID)
        self.do("power final", "campaign", "power", CID, "--inputs", str(self.power_file))
        self.do("register preview", "campaign", "register", CID, "--prereg", str(self.prereg_file))
        self.do("register confirm", "campaign", "register", CID, "--prereg", str(self.prereg_file), "--confirm", self.prereg_hash[:12])
        self.plan("grid-1", self.grid_matrix)
        self.do("attach", "campaign", "attach", CID, "grid-1")
        self.do("run grid", "run", "grid-1")
        self.do("verify", "campaign", "verify", CID)
        self.do("report", "report", "grid-1")
        self.do("status grid", "status", "grid-1")
        self.do("status grid json", "status", "grid-1", "--json")

    def step(self, name: str) -> Step:
        return next(s for s in self.steps if s.name == name)


@pytest.fixture(scope="module")
def walk(s1):
    return Walk(s1)



# --- expected values (typed here; read from the observed walk, then pinned) ---------------------------------------------------------------

STATE_AFTER = {"create": "draft", "baseline": "baselined", "power prior": "baselined", "plan pilot-1": "baselined", "admit before pilot pass": "baselined",
               "pilot attach": "baselined", "run pilot": "baselined", "pilot pass": "piloted", "register confirm before admit": "piloted",
               "admit": "piloted", "power final": "piloted", "register preview": "piloted", "register confirm": "registered",
               "plan grid-1": "registered", "attach": "measuring", "run grid": "measuring", "verify": "measuring", "report": "measuring"}
REFUSED = {"admit before pilot pass": "HB-CMP-002: admit is not legal in state baselined",
           "register confirm before admit": "HB-CMP-008: no final power inputs are recorded"}
LEDGER_KINDS = ["campaign.created", "baseline.recorded", "power.recorded", "ring_run.attached", "pilot.passed", "admission.decided", "power.recorded",
                "registered", "grid.attached"]


def campaign_rows(root: Path, cid: str = CID) -> list[dict]:
    return ledger.read_segment(root / "bench" / "campaigns" / cid / "ledger.jsonl")


def test_e1_campaign_happy_path(walk):
    """Item 1: the real CLI, create to report. After each step the campaign state is the expected one; a skipped or reordered step is refused
    with its HB code and its text; grading and the gates are real."""
    for name, state in STATE_AFTER.items():
        step = walk.step(name)
        assert (step.state or {}).get("state") == state, (name, step.ran)
        assert step.ran.rc == (1 if name in REFUSED else 0), (name, step.ran)
    for name, text in REFUSED.items():
        assert walk.step(name).ran.err.startswith(text), (name, walk.step(name).ran.err)
    assert "Outcomes: completed 4." in walk.step("run pilot").ran.out
    assert "Outcomes: completed 6." in walk.step("run grid").ran.out
    assert walk.step("pilot pass").ran.out.startswith('pilot passed: run "pilot-1", pass grade-')
    assert walk.step("attach").ran.out.endswith("the pre-registration is frozen\n")
    assert walk.step("verify").ran.out == "verify: ok (9 rows)\n"
    assert [r["kind"] for r in campaign_rows(walk.root)] == LEDGER_KINDS
    assert walk.step("report").ran.out.rstrip().splitlines()[-1].startswith("report: ") and (walk.grid_dir / "report.html").is_file()


def test_s1_as_committed_passes_the_real_pilot_gate(walk):
    """Finding: the same walk on S1 exactly as committed stops at `pilot pass`; the temp copy of the walk declares the two NA metrics."""
    ran = walk.step("asis pilot pass").ran
    assert ran.rc == 0, ran.err


def test_uf_e1_front_half(s1):
    """Item 2 (the readiness API legs; the `bench validate` legs are the strict xfails below): S1 `draft` has no record item, `ready` names the
    missing record with HB-RDY-001, the real `bench discriminate S1` writes it, and the item is gone. The one item left is HB-RDY-007 (a
    security property of one task fails the pair rule): a finding, S1 alone is never clean in `validate`."""
    assert [line for line in s1.draft_lines if "HB-RDY-001" in line] == []
    missing = [line for line in s1.ready_lines if line.startswith("x HB-RDY-001 S1:")]
    assert len(missing) == 1 and "no discrimination record for task version" in missing[0], s1.ready_lines
    assert s1.disc.rc == 0 and re.fullmatch(r"discriminate S1: written .+-win32\.json\n", s1.disc.out), s1.disc
    assert len(s1.records) == 1
    assert [line for line in s1.after_lines if "HB-RDY-001" in line] == []
    tracked = subprocess.run(["git", "ls-files", "bench/discrimination/S1"], cwd=s1.root, capture_output=True, text=True, check=True).stdout.split()
    assert tracked == [f"bench/discrimination/S1/{s1.records[0].name}"]
    assert [line for line in s1.after_lines if line.startswith("x ")] == ["x HB-RDY-007 S1: security: the security property has one task; the pair rule needs two"]


def test_the_temp_discrimination_matches_the_committed_record(s1):
    """Items 2 and 5 cross-check: the real trial in the temp repo against the record committed in this tree (`bench/discrimination/S1`, the
    Leader's run over the X-I5 check): outcome written, 15 of 15 variants flip their declared probe with their declared clause, naive 0.3750,
    reference 1.0000, and the task version, every probe, score and variant equal the committed record's (the temp copy is the same tree)."""
    body = json.loads(s1.records[0].read_text(encoding="utf-8"))
    assert body["scores"]["naive"]["exploit_probes_blocked"] == "0.3750" and body["scores"]["naive"]["property_check_pass"] == 0
    assert body["scores"]["reference"]["exploit_probes_blocked"] == "1.0000" and body["scores"]["reference"]["property_check_pass"] == 1
    assert body["readiness_failures"] == []
    assert len(body["variants"]) == 15 and all(set(v["flips"]) == set(v["clauses"]) and v["flips"] for v in body["variants"].values())
    committed = sorted((ROOT / "bench" / "discrimination" / "S1").glob("*.json"))
    assert len(committed) == 1, committed
    record = json.loads(committed[0].read_text(encoding="utf-8"))
    for key in ("task_version", "expected", "probe", "scores", "variants", "readiness_failures"):
        assert body[key] == record[key], key


def test_s1_draft_task_version_is_not_the_ready_task_version(s1):
    """The flip moves the task version (W0 section 2: the record is measured after the flip): the copy's draft version differs from the record's."""
    assert s1.draft_version != json.loads(s1.records[0].read_text(encoding="utf-8"))["task_version"]


@pytest.fixture
def ready_no_record(tmp_path):
    """A lean repo with S1 `ready` and no discrimination record. `validate` also prints the lean copy's own BOM noise (the other tasks are not
    here); the held assertion is only that no `HB-RDY` line is among it."""
    root = lean_repo(tmp_path)
    task = root / "tasks" / "S1" / "task.yaml"
    task.write_text(task.read_text(encoding="utf-8").replace("status: draft", "status: ready", 1), encoding="utf-8")
    shutil.rmtree(root / "bench" / "discrimination" / "S1")  # the lean copy of `bench/` carries the committed record; this fixture is the task without one
    commit_all(root, "S1 ready, no record")
    return root


def test_uf_e1_validate_names_the_missing_record(ready_no_record):
    assert any(line.startswith("x HB-RDY-001 S1:") for line in readiness.problems(ready_no_record))  # the API names it; the CLI does not
    ran = run_cli("--root", str(ready_no_record), "validate")
    assert "x HB-RDY-001 S1:" in ran.out, ran.out


def test_validate_of_a_ready_task_with_no_record_fails(ready_no_record):
    ran = run_cli("--root", str(ready_no_record), "validate")
    assert ran.rc != 0 and "HB-RDY-001" in ran.out, ran


def test_validate_passes_a_campaign_baseline_through(ready_no_record):
    ran = run_cli("--root", str(ready_no_record), "validate", "--campaign", CID)
    assert "unrecognized arguments" not in ran.err, ran.err


def test_e1_demo_combo_offline(walk):
    """Item 3 (R-89): cc-opus, k = 3, S1, two arms: six cells; the registered minimum pairs is 3 or fewer (c1); the power input names grid-4 (c2);
    the rendered verdict reads `inconclusive (underpowered)`; the preview warns that 3 pairs are below the required 39."""
    plan_doc = json.loads((walk.grid_dir / "plan.json").read_text(encoding="utf-8"))
    cells = plan_doc["cells"]
    assert len(cells) == 6 and {c["task"] for c in cells} == {"S1"}
    assert {(c["combo"], c["harness"], c["model"]) for c in cells} == {("cc-opus", "claude-code", "claude-opus-5-5")}
    assert sorted(c["arm"] for c in cells) == ["candidate"] * 3 + ["off"] * 3 and sorted({c["rep"] for c in cells}) == [1, 2, 3]
    status = walk.step("verify").state
    prereg = json.loads((walk.root / "bench" / "campaigns" / CID / "prereg" / f"{status['prereg_hash']}.json").read_text(encoding="utf-8"))
    assert prereg["min_pairs"] <= 3
    power_in = json.loads((walk.root / "bench" / "campaigns" / CID / "power" / f"{status['power']['final']}.json").read_text(encoding="utf-8"))
    assert power_in["source_run_ids"] == ["grid-4"]
    assert "min_pairs 3 is below the required n 39 for (security, claude-code, off vs candidate)" in walk.step("register preview").ran.out
    label = re.search(r'data-part="verdict" aria-label="verdict">([^<]*)<', walk.html)
    assert label is not None and label.group(1) == "inconclusive (underpowered)", label and label.group(1)


def test_section_3_renders_from_the_cli(walk):
    """Item 4 (EV-20): `bench report` of the grid run holds section 3: one verdict, the campaign header facts (question, arms, registered mde,
    baseline, power), the catalog line, the exploratory block, and the verdict's n; the cell rows are in the Runs table. Finding: there is no
    hyperlink from the verdict to the cell rows, and `min_pairs` is shown only as the verdict's `n`."""
    html = walk.html
    assert html.count('data-part="verdict"') == 1 and 'id="verdict-security-claude-code-off-candidate"' in html
    assert "catalog 0.7 " in html and "Exploratory results" in html and "Exploratory: not in the pre-registration." in html
    assert 'data-field="mde">security 0.3<' in html and 'data-field="question">does the pack help<' in html
    assert 'data-field="arms">candidate (revision 7), off (no pack)<' in html
    assert f'data-field="baseline">{walk.step("verify").state["baseline_identity_hash"][:12]}' in html or walk.step("verify").state["baseline_identity_hash"][:12] in html
    assert "n 3 of 39" in html
    assert html.count('id="cell-') == 6


# --- item 5: T-E19 with a real discrimination run -----------------------------------------------------------------------------------------

class DiscEnv:
    """A second lean repo that holds the real discrimination run folder of `s1` and two campaigns: `dcb` baselined (for `pilot attach`) and the
    helpers' campaign registered (for `attach`, which checks the state before the plan kind)."""

    def __init__(self, s1: S1Repo) -> None:
        from test_cli_campaign import TREAT_COMMIT, baselined, registered

        base = s1.base / "second"
        base.mkdir()
        self.root = lean_repo(base)
        task = self.root / "tasks" / "S1" / "task.yaml"
        task.write_text(task.read_text(encoding="utf-8").replace("status: draft", "status: ready", 1), encoding="utf-8")
        commit_all(self.root, "S1 ready")
        self.run_id = s1.disc_runs[0].name
        self.runs = self.root / "runs"
        shutil.copytree(s1.disc_runs[0], self.runs / self.run_id)
        self.globals = ["--root", str(self.root), "--runs", str(self.runs), "--cells-root", str(s1.cells), "--tools-dir", str(base / "tools")]
        baselined(self.root, "S1")
        registered(self.root, TREAT_COMMIT)
        assert run_cli(*self.globals, "campaign", "create", "dcb", "--question", QUESTION).rc == 0
        assert run_cli(*self.globals, "campaign", "baseline", "dcb", "--tasks", "S1").rc == 0
        self.plan = json.loads((self.runs / self.run_id / "plan.json").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def disc(s1):
    return DiscEnv(s1)


def test_the_real_discrimination_plan_is_of_kind_discrimination(disc):
    assert disc.plan["kind"] == "discrimination" and "campaign" not in disc.plan


@pytest.mark.parametrize("reader", READERS)
def test_a_discrimination_run_is_refused_or_labelled_by_each_reader(disc, reader):
    """Item 5 (T-E19), one parameter per reader, on the real run of item 2."""
    from harness_bench import board, views
    from harness_bench import campaign as campaign_mod
    from harness_bench.errors import BenchError

    g, run = disc.globals, disc.run_id
    if reader == "campaign attach":
        ran = run_cli(*g, "campaign", "attach", CID, run)
        assert ran.rc == 1 and ran.err.startswith("HB-CMP-010") and "plan kind discrimination, not measurement" in ran.err, ran
    elif reader == "campaign pilot attach":
        ran = run_cli(*g, "campaign", "pilot", "attach", "dcb", run)
        assert ran.rc == 1 and ran.err.startswith("HB-CMP-010") and "plan kind discrimination, not measurement" in ran.err, ran
    elif reader == "campaign.run_side_check":
        with pytest.raises(BenchError) as raised:
            campaign_mod.run_side_check(disc.root, disc.plan, run)
        assert raised.value.code == "HB-CMP-010"
    elif reader in ("bench run", "bench report"):
        ran = run_cli(*g, reader.removeprefix("bench "), run)
        assert ran.rc == 1 and ran.err.startswith("HB-PLN-004") and "discrimination" in ran.err, ran
    elif reader == "board run listing":
        with pytest.raises(BenchError) as raised:
            board.build(views.load(disc.runs / run), board_catalog(disc.root))
        assert raised.value.code == "HB-PLN-004" and "discrimination" in raised.value.message
    else:
        ran = run_cli(*g, "status", run)
        assert ran.rc == 0 and ran.out.splitlines()[0] == "kind: discrimination", ran
        document = run_cli(*g, "status", run, "--json")
        assert document.rc == 0 and json.loads(document.out)["run_id"] == run


def board_catalog(root: Path):
    from harness_bench import composites

    return composites.load_catalog(root)


# --- items 7, 8, 9: two-arm readers, the arm guard, synthetic exclusion ---------------------------------------------------------------------

def test_two_arm_plan_renders_every_legacy_reader(walk):
    """Item 7 (W0 section 10 G1 note): a plan with arms `off` and `candidate` renders the legacy report (table, board, pack-improvement section)
    without raising, which confirms the plan's *assume:* for these readers. SR-3: the one-pack text is gone and the header shows the pack revision."""
    report = walk.step("report")
    assert report.ran.rc == 0 and "Traceback" not in report.ran.err
    for section in ('id="leaderboard"', 'id="pack-effect"', 'id="pack-improvement"', 'id="validity"', 'id="runs"'):
        assert section in walk.html, section
    assert "This run has one pack setting; no effect to show." not in walk.html + report.ran.out
    assert "pack ai-forward revision 7" in walk.html
    assert "Pack effect for these arms is not computed" not in walk.html + report.ran.out  # E3: the pair (off, candidate) is computed


def test_the_pack_effect_section_does_not_describe_a_two_arm_run_as_one_pack(walk):
    assert "This run has pack candidate only." not in walk.html


def test_campaign_modules_read_the_arm_only_through_cell_arm_and_arm_pack():
    """Item 8: `test_arms_guard.py` holds the pinned counts; here campaign.py, the campaign section and verdicts.py hold no `arm` or `pack` key,
    attribute or keyword outside docstrings, and each reads the arm through `plan.cell_arm`."""
    src = ROOT / "src" / "harness_bench"
    for module in ("campaign.py", "report/campaign_section.py", "verdicts.py"):
        text = (src / module).read_text(encoding="utf-8")
        tree = ast.parse(text)
        docs = {id(n.body[0].value) for n in ast.walk(tree) if isinstance(n, ast.Module | ast.FunctionDef | ast.ClassDef) and n.body
                and isinstance(n.body[0], ast.Expr) and isinstance(n.body[0].value, ast.Constant)}
        raw = [n.lineno for n in ast.walk(tree) if (isinstance(n, ast.Constant) and n.value in ("arm", "pack") and id(n) not in docs)
               or (isinstance(n, ast.Attribute) and n.attr in ("arm", "pack")) or (isinstance(n, ast.keyword) and n.arg in ("arm", "pack"))]
        assert raw == [], (module, raw)
        assert "cell_arm" in text, module


def test_measurement_plan_naming_synthetic_is_refused(s1, walk):
    """Item 9 (T-E23): the real `plan.build_plan` refuses a measurement plan that names a synthetic combo, HB-PLN-004 naming the combo;
    `synthetic` is in no leaderboard row of the real grid report."""
    from test_cli_campaign import attempt, code_of

    from harness_bench import config, plan

    matrix = {"schema": "bench-matrix/1", "run_id": "syn", "bom": {"subset": ["S1"]}, "packs": ["off"], "repetitions": 1,
              "combos": [{"id": "synthetic-x", "harness": "synthetic", "model": "synthetic-1"}]}
    bom = config.load_yaml(s1.root / "bench" / "bom.yaml")
    exc = attempt(plan.build_plan, s1.root, matrix, bom, "syn", {"synthetic": {"version": "x"}}, parallelism=1)
    assert code_of(exc) == "HB-PLN-004" and "combo synthetic-x (synthetic)" in exc.message, exc
    board_html = walk.html.split('id="leaderboard-body"', 1)[1].split("</tbody>", 1)[0]
    assert "synthetic" not in board_html and "cc-opus" in board_html


# --- item 10: one run, four surfaces --------------------------------------------------------------------------------------------------

def test_one_run_four_surfaces_agree(walk):
    """Item 10 (E7): the grid run read through `bench status --json`, the run ledger, `campaign verify` (with the campaign ledger) and section 3.
    The surfaces expose different subsets, so each shared quantity is compared on every surface that carries it. Cell count: status 6 of 6, the
    ledger's 6 outcomes, section 3's 3 pairs and 6 Runs rows. Identity: the baseline hash on the campaign status document, the ledger row and the
    report header; the effective run hash on the status document and the plan stamp. Task version: plan, cells and the identity component.
    Finding: `bench status --json` carries neither hash, and the report shows only the 12-digit baseline."""
    from test_cli_campaign import run_events

    status = json.loads(walk.step("status grid json").ran.out)
    outcomes = [r for r in run_events(walk.root, "grid-1") if r["kind"] == "cell.outcome"]
    assert status["cells_total"] == status["cells_ended"] == len(outcomes) == walk.html.count('id="cell-') == 6
    assert "n 3 of 39" in walk.html  # 3 pairs of 2 cells
    rows = campaign_rows(walk.root)
    assert walk.step("verify").ran.out == f"verify: ok ({len(rows)} rows)\n"
    doc = walk.step("verify").state
    baseline = next(r for r in rows if r["kind"] == "baseline.recorded")["identity_hash"]
    assert doc["baseline_identity_hash"] == baseline and baseline[:12] in walk.html
    assert (walk.root / "bench" / "campaigns" / CID / "identity" / f"{baseline}.json").is_file()
    plan_doc = json.loads((walk.grid_dir / "plan.json").read_text(encoding="utf-8"))
    assert doc["effective_run_hash"] == plan_doc["campaign"]["identity"]["hash"]
    attach = next(r for r in rows if r["kind"] == "grid.attached")
    assert attach["plan_hash"] == plan_doc["plan_hash"] and plan_doc["plan_hash"][:12] in walk.html
    version = plan_doc["tasks"]["S1"]["version_hash"]
    assert {c["task_version"] for c in plan_doc["cells"]} == {version}
    identity_file = json.loads((walk.root / "bench" / "campaigns" / CID / "identity" / f"{baseline}.json").read_text(encoding="utf-8"))
    assert identity_file["components"]["tasks/S1"] == version


def test_one_blocked_cell_is_named_in_the_completion_summary(tmp_path, monkeypatch):
    """Item 10, X-H2 item 9 (EV-18): one blocked cell is named, with its id and cause, in the summary `bench run` prints (`status.text`)."""
    from test_cli_campaign import tree, write_plan
    from test_engine import FakeLauncher, _build_workspace

    root = tree(tmp_path)
    doc = write_plan(root, "B1", campaign_block=False, prereg_hash=None, harness="fake")
    blocked = doc["cells"][0]["cell_id"]
    real_load = cli.profiles.load
    monkeypatch.setattr(cli.profiles, "load", lambda r, h: None if h == "fake" else real_load(r, h))
    monkeypatch.setattr(cli.profiles, "ProfileLauncher", lambda profile, tools, planned: FakeLauncher({}, build_changed_for={blocked}))
    monkeypatch.setattr(cli, "_workspace_builder", lambda *a, **k: _build_workspace)
    monkeypatch.setattr(cli.preflight, "check", lambda *a, **k: None)
    ran = run_cli("--root", str(root), "--cells-root", str(tmp_path / "cells"), "--tools-dir", str(tmp_path / "tools"), "run", "B1")
    assert blocked in ran.out and "build changed" in ran.out, ran.out


# --- item 13: the W1-C cross-track joins ---------------------------------------------------------------------------------------------

PATCHED_NAMES = ("gates.pilot", "gates.admission", "hidden_test_disagreements", "unbiased_failures", "expected_na", "views.load")


def test_full_walk_with_real_gates_power_and_readiness(walk):
    """X-INT-1: item 1's walk from create to attach with none of the six names `test_campaign_register.stubs` patches. The `pilot.passed` and
    `admission.decided` rows hold the real gate outputs; the final power analysis is the real `power.analyse` (the preview's required n)."""
    calls = [ast.unparse(n) for n in ast.walk(ast.parse(Path(__file__).read_text(encoding="utf-8")))
             if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr == "setattr"]
    assert calls and not [c for c in calls if any(name in c for name in PATCHED_NAMES)], calls
    rows = campaign_rows(walk.root)
    passed = next(r for r in rows if r["kind"] == "pilot.passed")
    assert passed["run_id"] == "pilot-1" and passed["grading_id"].startswith("grade-") and re.fullmatch(r"[0-9a-f]{64}", passed["gate_input_hash"])
    assert [(r["task"], r["admitted"]) for r in rows if r["kind"] == "admission.decided"] == [("S1", 1)]
    assert [r["role"] for r in rows if r["kind"] == "power.recorded"] == ["prior", "final"]
    assert "required n 39" in walk.step("register preview").ran.out


def test_run_pass_of_a_campaign_run_is_refused_while_campaign_lock_is_held(walk):
    """X-INT-2: X-F's HB-GRD-007 through the real runner on a plan that `bench plan --campaign` wrote, in both orders: campaign.lock held first
    (HB-GRD-007), and grade.lock held first (HB-GRD-001, the probe never reached). Neither writes a grading row."""
    from test_cli_campaign import attempt, code_of, held_by_another_process

    from harness_bench import campaign as campaign_mod
    from harness_bench import oslock
    from harness_bench.grade import runner

    run_dir = walk.grid_dir
    before = sorted(p.name for p in run_dir.rglob("grade-*.jsonl"))
    with held_by_another_process(campaign_mod.lock_path(walk.root, CID)):
        exc = attempt(runner.run_pass, run_dir, walk.root, cells_root=walk.s1.cells)
    assert code_of(exc) == "HB-GRD-007" and sorted(p.name for p in run_dir.rglob("grade-*.jsonl")) == before and not oslock.is_held(run_dir / "grade.lock")
    with held_by_another_process(run_dir / "grade.lock"):
        exc = attempt(runner.run_pass, run_dir, walk.root, cells_root=walk.s1.cells)
    assert code_of(exc) == "HB-GRD-001" and sorted(p.name for p in run_dir.rglob("grade-*.jsonl")) == before
    assert not oslock.is_held(campaign_mod.lock_path(walk.root, CID))


def test_after_grading_hook_is_lock_free_and_verifies_with_two_attached_runs_one_graded(walk, capsys):
    """X-INT-3: with the sibling attached pilot run's grade.lock held, a grading pass of the grid run ends with `campaign verify: ok (<n> rows)`;
    the hook's read takes no lock (it answers while campaign.lock is held); an unknown campaign prints `not run (HB-CMP-005)`."""
    from test_cli_campaign import held_by_another_process

    from harness_bench import campaign as campaign_mod
    from harness_bench.grade import runner

    capsys.readouterr()
    with held_by_another_process(walk.pilot_dir / "grade.lock"):
        runner.run_pass(walk.grid_dir, walk.root, cells_root=walk.s1.cells)
    assert capsys.readouterr().out.rstrip().splitlines()[-1] == "campaign verify: ok (9 rows)"
    plan_doc = json.loads((walk.grid_dir / "plan.json").read_text(encoding="utf-8"))
    with held_by_another_process(campaign_mod.lock_path(walk.root, CID)):
        assert campaign_mod.verify_for_plan(walk.root, plan_doc) == "campaign verify: ok (9 rows)"
    assert campaign_mod.verify_for_plan(walk.root, {"campaign": {"campaign_id": "no-such"}}) == "campaign verify: not run (HB-CMP-005)"
