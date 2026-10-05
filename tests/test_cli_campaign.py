"""X-C1 proof, the CLI half and the shared fixtures of the four campaign test modules (W1-C section 13).

This module is the one home of the helpers (`cli_rc`, `make_repo`, `append`, `walk_to`, ...) so no shared conftest is edited.
Tests here: T-3 (every cited test id exists) and the id checks through the real parser. C1 drives no engine.

Expected values are typed here or computed with hashlib, never with the function under test (RV-TA 1).
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
import re
import shutil
import subprocess
import sys
from contextlib import contextmanager
from pathlib import Path

import pytest
import yaml

from harness_bench import atomic, campaign, cli, gitsafe, identity, ledger, oslock, plan
from harness_bench.errors import BenchError

ROOT = Path(__file__).resolve().parents[1]
DESIGN = ROOT / "docs" / "design" / "eval-campaign-record.md"
GITIGNORE_LINES = ("bench/campaigns/**/*.tmp-*", "bench/discrimination/**/*.tmp-*", "bench/campaigns/*/campaign.lock")
CID = "cc-opus"
QUESTION = "does the pack help"
IDENT = {"schema": "bench-identity/1", "components": {"src/harness_bench/engine.py": "a" * 64, "src/harness_bench/grade/formal.py": "c" * 64,
                                                      "tasks/T1": "d" * 64}}
PREREG = {"schema": "bench-prereg/1", "question": QUESTION}
POWER = {"schema": "bench-power-inputs/1", "alpha": 5}
COMMIT = "f" * 40
STATES = ("draft", "baselined", "piloted", "registered", "measuring", "concluded")
ARGV = {"create": ["--question", QUESTION], "verify": [], "status": [], "baseline": [], "fix": ["--class", "MOD-A", "--commit", "abc1234", "--component", "tasks/T1"],
        "power": ["--inputs", "inputs.json"], "attach": ["R1"], "conclude": [], "abandon": ["--reason", "done"],
        "pilot attach": ["R1"], "pilot pass": ["R1"], "admit": [], "register": ["--prereg", "prereg.json"]}  # per subcommand: the options after the id (N-1 follows the table)


def cli_rc(argv: list[str]) -> int:
    """`cli.main(argv)` with `SystemExit` (argparse usage errors) converted to its code, so a missing option fails by value."""
    try:
        return cli.main(argv)
    except SystemExit as exc:
        return int(exc.code or 0)


def bench(root: Path, *args: str) -> int:
    return cli_rc(["--root", str(root), *args])


def git(root: Path, *args: str, check: bool = True):
    return gitsafe.git(list(args), root, 60, identity=True, check=check)


def make_repo(tmp_path: Path) -> Path:
    """A real work tree with the three required `.gitignore` lines committed."""
    root = tmp_path / "repo"
    root.mkdir()
    git(root, "init", "-q", "-b", "main")
    (root / ".gitignore").write_text("\n".join(GITIGNORE_LINES) + "\n", encoding="utf-8")
    git(root, "add", ".gitignore")
    git(root, "commit", "-q", "-m", "init")
    return root


def commit_all(root: Path, message: str = "state") -> None:
    git(root, "add", "-A")
    git(root, "commit", "-q", "-m", message)


def cdir(root: Path, cid: str = CID) -> Path:
    return root / "bench" / "campaigns" / cid


def ledger_path(root: Path, cid: str = CID) -> Path:
    return cdir(root, cid) / "ledger.jsonl"


def put(root: Path, obj: dict, folder: str, cid: str = CID) -> str:
    """A content file named by the sha256 of its canonical bytes (W0 section 6); returns the hash."""
    data = ledger.canonical(obj)
    digest = hashlib.sha256(data).hexdigest()
    target = cdir(root, cid) / folder
    target.mkdir(parents=True, exist_ok=True)
    atomic.create_once(target / f"{digest}.json", data)
    return digest


def defaults(kind: str) -> dict:
    ih = hashlib.sha256(ledger.canonical(IDENT)).hexdigest()
    ph = hashlib.sha256(ledger.canonical(PREREG)).hexdigest()
    return {
        "campaign.created": {"question": QUESTION},
        "baseline.recorded": {"identity_hash": ih, "bench_commit": COMMIT},
        "defect_fix.admitted": {"defect_class": "MOD-A", "commit": COMMIT, "scope": "run",
                                "changes": {"src/harness_bench/engine.py": ["a" * 64, "b" * 64]}},
        "power.recorded": {"role": "prior", "input_hash": hashlib.sha256(ledger.canonical(POWER)).hexdigest()},
        "ring_run.attached": {"ring_hash": "r" * 64, "run_id": "R1", "plan_hash": "p" * 64},
        "pilot.passed": {"run_id": "R1", "grading_id": "grade-20261004T000000-abcdef", "gate_input_hash": "g" * 64},
        "admission.decided": {"task": "T1", "admitted": 1, "reason": "kept"},
        "registered": {"prereg_hash": ph},
        "grid.attached": {"run_id": "R2", "plan_hash": "q" * 64},
        "concluded": {},
        "abandoned": {"reason": "done"},
    }[kind]


def raw_rows(root: Path, rows: list[tuple[str, dict]], cid: str = CID) -> Path:
    """A hand-built ledger: real chain and stamp, no campaign validation (the red fixtures of F-2, F-6, V-series)."""
    path = ledger_path(root, cid)
    writer = ledger.SegmentWriter.reopen(path) if path.exists() else ledger.SegmentWriter.create(path.parent, "ledger")
    with writer:
        for kind, fields in rows:
            writer.append(ledger.stamp({"kind": kind, "campaign_id": cid, **fields}))
    return path


def append(root: Path, kind: str, cid: str = CID, **fields) -> dict:
    """One row through the real session and `_append`: the write API under test."""
    with campaign.session(root, cid, create=kind == "campaign.created") as s:
        row = campaign._append(s, kind, **{**defaults(kind), **fields})
    assert ledger_path(root, cid).exists(), f"_append({kind}) wrote no ledger"
    assert row.get("kind") == kind, f"_append({kind}) returned {row!r}"
    return row


WALK = ("campaign.created", "baseline.recorded", "pilot.passed", "registered", "grid.attached", "concluded")


def walk_to(root: Path, state: str, cid: str = CID) -> None:
    """The legal path to `state` by real appends, with the content files the rows name written first."""
    for kind in WALK[: STATES.index(state) + 1]:
        if kind == "campaign.created":
            cdir(root, cid).mkdir(parents=True, exist_ok=True)
        elif kind == "baseline.recorded":
            put(root, IDENT, "identity", cid)
        elif kind == "registered":
            put(root, PREREG, "prereg", cid)
        append(root, kind, cid)


def snapshot(root: Path) -> dict[str, bytes | None]:
    """Every path under root except `.git`, folders as None: a byte-for-byte picture of the tree."""
    out: dict[str, bytes | None] = {}
    for path in sorted(root.rglob("*")):
        rel = path.relative_to(root)
        if ".git" in rel.parts:
            continue
        out[rel.as_posix()] = None if path.is_dir() else path.read_bytes()
    return out


def attempt(fn, *args, **kwargs) -> Exception | None:
    """The exception `fn` raises, or None: a missing refusal then fails on an assert, not on pytest.raises' own Failed."""
    try:
        fn(*args, **kwargs)
    except Exception as exc:  # noqa: BLE001  (a test helper: it reports whatever the call raised)
        return exc
    return None


def code_of(exc: Exception | None) -> str | None:
    return exc.code if isinstance(exc, BenchError) else None


def make_link(link: Path, target: Path) -> None:
    """A junction on Windows (no privilege needed), a symlink elsewhere; a platform that cannot skips the test."""
    link.parent.mkdir(parents=True, exist_ok=True)
    if sys.platform == "win32":
        done = subprocess.run(["cmd", "/c", "mklink", "/J", str(link), str(target)], capture_output=True, text=True, check=False)
        if done.returncode != 0:
            pytest.skip(f"mklink /J refused: {done.stdout}{done.stderr}")
    else:
        link.symlink_to(target, target_is_directory=target.is_dir())


HOLDER = ("import sys;from pathlib import Path;from harness_bench import oslock;"
          "l=oslock.RunLock.acquire(Path(sys.argv[1]));print('held',flush=True);sys.stdin.read()")


@contextmanager
def held_by_another_process(path: Path):
    """A second OS process holds `path`'s lock until the block ends (the real cross-process semantics)."""
    holder = subprocess.Popen([sys.executable, "-c", HOLDER, str(path)], stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True)
    try:
        assert holder.stdout.readline().strip() == "held"
        yield
    finally:
        holder.stdin.close()
        holder.wait(timeout=30)
        holder.stdout.close()


def cited_ids_missing(text: str) -> tuple[list[str], list[str]]:
    """(test ids, mutant ids) that sections 2-12 and 16 cite and section 13 does not define. Retired ids are named in section 13."""
    head, _, rest = text.partition("## 13. Test plan by node id")
    plan, _, tail = rest.partition("## 14. Requests")
    cited_zone = head.split("## 2. Data model", 1)[-1] + "\n" + tail.split("## 16. Review disposition", 1)[-1]
    defined = set(re.findall(r"^\| ((?:[A-Z]-\d+[a-z]?))[ `]", plan, re.MULTILINE))
    retired = set(re.findall(r"[A-Z]-\d+", plan.split("Retired ids (not reused):", 1)[-1].split("\n", 1)[0]))
    ledger_part = plan.split("### Mutant ledger", 1)[-1]
    mutants: set[str] = set()
    for cell in re.findall(r"^\| ((?:M-[A-Z]+\d+[a-z]?)(?:[^|]*))\|", ledger_part, re.MULTILINE):
        for token in re.split(r"\s*/\s*", cell.strip()):
            span = re.fullmatch(r"(M-[A-Z]+\d+)([a-z])\.\.([a-z])", token)
            if span:
                mutants |= {f"{span[1]}{chr(c)}" for c in range(ord(span[2]), ord(span[3]) + 1)}
            elif re.fullmatch(r"M-[A-Z]+\d+[a-z]?", token):
                mutants.add(token)
    cited_tests = set(re.findall(r"(?<![A-Za-z-])([FCNELIVSGPBTQ]-\d+[a-z]?)\b", cited_zone))
    cited_mutants = set(re.findall(r"\b(M-[A-Z]+\d+[a-z]?)\b", cited_zone))
    return sorted(cited_tests - defined - retired), sorted(cited_mutants - mutants)


DANGLING = """## 2. Data model
see F-1 and C-999 and M-F1 and M-ZZ9
## 13. Test plan by node id
Retired ids (not reused): F-4.
| F-1 `test_x` | a | b | c | M-F1 |
### Mutant ledger
| id | edit | flips on |
| --- | --- | --- |
| M-F1 | e | f |
## 14. Requests
## 16. Review disposition
"""


def test_every_cited_test_id_exists_t3():
    """T-3. A dangling test id and a dangling mutant id in a fixture doc are both found, and the real design has none."""
    assert cited_ids_missing(DANGLING) == (["C-999"], ["M-ZZ9"])
    assert cited_ids_missing(DESIGN.read_text(encoding="utf-8")) == ([], [])


def test_the_parser_validates_the_campaign_id_before_any_command_runs():
    """The parser layer of N-1: a bad id refuses in `parse_args` itself (RV-SEC 1), so no command function is reached."""
    for bad in ("../../x", "..", "A", "a" * 41):
        err = attempt(cli.build_parser().parse_args, ["campaign", "status", bad])
        assert code_of(err) == "HB-USR-002", bad




# --- the C2 fixtures: a real classed tree, the real manifest, hand-written confirmed plans --------------------------------

SRC_FILES = ("engine.py", "grade/formal.py", "telemetry/normalize.py")
TASK = "T1"
TREAT_COMMIT = "a" * 40


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def make_tree(root: Path, tasks: tuple[str, ...] = ("T1", "T2")) -> None:
    """The baseline fixture: a small classed source tree, the committed harness profiles, the bench files the manifest reads,
    a ready task per id, the defect-class and spike notes, and a catalog freeze that holds the tree's own catalog hash. Committed."""
    for name in SRC_FILES:
        write_text(root / "src" / "harness_bench" / name, "original\n")
    shutil.copytree(ROOT / "bench" / "profiles", root / "bench" / "profiles")
    for name in ("metrics.yaml", "prices.yaml", "gateway.yaml"):
        write_text(root / "bench" / name, "version: 1\nmetrics: []\n")
    rows = "".join(f"  - {{ id: {t}, scenario: 5, smoke: false, budget_minutes: 5, source: authored, title: t }}\n" for t in tasks)
    write_text(root / "bench" / "bom.yaml", f"schema: bench-bom/1\ntasks:\n{rows}")
    write_text(root / "uv.lock", "version = 1\n")
    for t in tasks:
        write_text(root / "tasks" / t / "prompt.md", f"task {t}\n")
        write_text(root / "tasks" / t / "task.yaml", f"schema: bench-task/1\nid: {t}\nstatus: ready\nproperty:\n  name: security\n")
    write_text(root / "docs" / "lessons" / "defect-classes.md", "### MOD-A — a class\n\n### CONC-A: another\n\nMOD-B is named only here.\n")
    write_text(root / "docs" / "notes" / "spike-e4-post-turn-prompt.md", "---\nstatus: accepted\n---\nbody\n")
    set_freeze(root, identity.catalog_hash(root))
    commit_all(root, "tree")


def set_freeze(root: Path, catalog_hash: str | None) -> None:
    versions = {} if catalog_hash is None else {"0.7": {"catalog_hash": catalog_hash}}
    write_text(root / "bench" / "catalog-freeze.yaml", yaml.safe_dump({"schema": "bench-catalog-freeze/1", "versions": versions}))


def edit_src(root: Path, name: str, text: str = "edited\n") -> None:
    write_text(root / "src" / "harness_bench" / name, text)


def created(root: Path) -> None:
    assert bench(root, "campaign", "create", CID, "--question", QUESTION) == 0


def baselined(root: Path, *tasks: str) -> None:
    """A created campaign and its baseline, written as the baseline command writes them: the identity file, then the row, with no
    `builds/*` key. The `baseline` command itself is under test only where a test names it, so no other test is red because of it."""
    created(root)
    digest = put(root, identity.manifest(root, list(tasks or ("T1",))), "identity")
    append(root, "baseline.recorded", identity_hash=digest, bench_commit=git(root, "rev-parse", "HEAD").stdout.strip())


def rows_of(root: Path, cid: str = CID) -> list[dict]:
    return ledger.read_segment(ledger_path(root, cid))


def kinds(root: Path) -> list[str]:
    return [r["kind"] for r in rows_of(root)]


def chain_identity(root: Path, cid: str = CID) -> dict:
    """The chain's effective run side as a plan stamps it (a fixture: the test builds the stamp the way `plan --campaign` will)."""
    run = identity.side(campaign.effective_identity(root, campaign.read(root, cid)), "run")
    return {"hash": identity.identity_hash(run), "components": run["components"]}


def register_row(root: Path, commit: str = TREAT_COMMIT) -> str:
    """One `registered` row over a prereg file naming the treat arm's pack commit (the register command is C2b; this is the row it writes)."""
    digest = put(root, {"schema": "bench-prereg/1", "question": QUESTION, "arms": {"treat": {"commit": commit, "revision": "r1"}}}, "prereg")
    append(root, "registered", prereg_hash=digest)
    return digest


def registered(root: Path, commit: str = TREAT_COMMIT) -> str:
    """Walk a baselined campaign to `registered` by real rows; returns the prereg hash."""
    append(root, "pilot.passed")
    return register_row(root, commit)


def write_plan(root: Path, run_id: str, *, cid: str = CID, prereg_hash: str | None = "unset", ident: dict | None = None, ring: dict | None = None,
               kind: str | None = None, commit: str = TREAT_COMMIT, harness: str = "claude-code", tasks: tuple[str, ...] = ("T1",),
               campaign_block: bool = True) -> dict:
    """A confirmed `plan.json` under runs/<id>/ (`plan_hash` recomputed, so `load_confirmed` accepts it)."""
    if prereg_hash == "unset":
        prereg_hash = latest_prereg(root, cid)
    cells = [{"cell_id": c.id, "label": c.label, **dataclasses.asdict(c)}
             for c in (plan.Cell(t, f"v-{t}", 5, "c1", harness, "fake-model", arm, 1, 60) for t in tasks for arm in ("base", "treat"))]
    doc = {"schema": plan.SCHEMA, "run_id": run_id, "trace_id": "a" * 32,
           "parameters": {**plan.DEFAULT_PARAMETERS, "parallelism": 1, "disk_floor_bytes": 1024},
           "tasks": {t: {"prompt": "p\n", "version_hash": plan.task_version_hash(root / "tasks" / t)} for t in tasks}, "builds": {harness: {}},
           "arms": {"base": {"pack": None}, "treat": {"pack": {"commit": commit, "revision": "r1", "source": "https://example.test/pack"}}},
           "cells": cells, "profiles": {harness: {"profile_hash": "", "usage_source": "acp_turn", "auxiliary_models": [], "record_glob": "x"}}}
    if campaign_block:
        doc["campaign"] = {"campaign_id": cid, "prereg_hash": prereg_hash, "identity": ident or chain_identity(root)}
    if ring is not None:
        doc["ring"] = ring
    if kind is not None:
        doc["kind"] = kind
    doc["plan_hash"] = plan.plan_hash(doc)
    write_text(root / "runs" / run_id / "plan.json", json.dumps(doc, indent=2, sort_keys=True))
    return doc


def latest_prereg(root: Path, cid: str = CID) -> str | None:
    hits = [r for r in rows_of(root, cid) if r["kind"] == "registered"]
    return hits[-1]["prereg_hash"] if hits else None


def power_file(root: Path, name: str = "power.json", **over) -> Path:
    """Valid bench-power-inputs/1 (decimals are strings: the canonical form has no float)."""
    body = {"alpha": "0.05", "power": "0.8", "correction": {"method": "bonferroni", "m": 2}, "pairing_unit": "unpaired", "slots": 2,
            "harnesses": ["claude-code"], "comparisons": [["base", "treat"]], "mean_wall_per_cell_s": 600, "mean_tokens_per_cell": 100000,
            "properties": {"security": {"mde": "0.3", "tasks": ["T1", "T2"]}}, **over}
    path = root / name
    path.write_text(json.dumps(body), encoding="utf-8")
    return path


# --- C2a: the real cmd_run and the real engine (P-3, P-4, P-5, P-7, I-3) -----------------------------------------------------

def tree(tmp_path: Path, name: str | None = None) -> Path:
    if name:
        tmp_path = tmp_path / name
        tmp_path.mkdir()
    root = make_repo(tmp_path)
    make_tree(root)
    return root


def run_events(root: Path, run_id: str) -> list[dict]:
    folder = root / "runs" / run_id / "events"
    return [row for seg in sorted(folder.glob("*.jsonl")) for row in ledger.read_segment(seg)] if folder.is_dir() else []


def real_run(monkeypatch, root: Path, tmp_path: Path, run_id: str) -> int:
    """`bench run` through the real `cmd_run` and the real engine. Faked: the launcher (the fake ACP agent), the workspace builder,
    preflight and the grading pass; never the engine, its lock, `identity_check=` or `campaign_check=`."""
    from test_engine import FakeLauncher, _build_workspace

    real_load = cli.profiles.load
    monkeypatch.setattr(cli.profiles, "load", lambda r, h: None if h == "fake" else real_load(r, h))
    monkeypatch.setattr(cli.profiles, "ProfileLauncher", lambda profile, tools, planned: FakeLauncher({}))
    monkeypatch.setattr(cli, "_workspace_builder", lambda *a, **k: _build_workspace)
    monkeypatch.setattr(cli.preflight, "check", lambda *a, **k: None)

    def no_grading(*a, **k):
        raise BenchError("HB-GRD-005", "grading is not part of this test")

    monkeypatch.setattr(cli.runner, "run_pass", no_grading)
    return cli_rc(["--root", str(root), "--cells-root", str(tmp_path / "cells"), "--tools-dir", str(tmp_path / "tools"), "run", run_id])


def attached(root: Path, run_id: str = "R2") -> dict:
    """A registered campaign, a plan over the fake harness, and the grid attach, through the real commands."""
    baselined(root, "T1", "T2")
    digest = registered(root)
    doc = write_plan(root, run_id, prereg_hash=digest, harness="fake", tasks=("T1", "T2"))
    assert bench(root, "campaign", "attach", CID, run_id) == 0
    return doc


def test_bench_run_refuses_an_unattached_campaign_plan_p3(tmp_path, monkeypatch, capsys):
    root = tree(tmp_path)
    baselined(root, "T1", "T2")
    digest = registered(root)
    write_plan(root, "G1", prereg_hash=digest, harness="fake")  # a grid plan nothing attached
    write_plan(root, "P1", prereg_hash=None, harness="fake", ring={"tag": "pilot", "hash": "r" * 64})  # a pilot plan with no ring row
    moved = write_plan(root, "M1", prereg_hash="0" * 64, harness="fake")  # a grid plan whose registered hash moved, though a row names it
    append(root, "grid.attached", run_id="M1", plan_hash=moved["plan_hash"])
    for run_id in ("G1", "P1", "M1"):
        capsys.readouterr()
        assert real_run(monkeypatch, root, tmp_path, run_id) == 1, run_id
        assert "HB-CMP-010" in capsys.readouterr().err, run_id
        assert run_events(root, run_id) == [], run_id  # nothing launched, and no started-run marker: the operator can retry


def test_the_campaign_check_runs_under_the_run_lock_before_the_first_launch_p7(tmp_path, monkeypatch):
    root = tree(tmp_path)
    doc = attached(root)
    seen: dict = {}

    def recording(root_, plan_doc, run_id):
        seen.update(held=oslock.is_held(root / "runs" / "R2" / ".lock"), events=(root / "runs" / "R2" / "events").exists(),
                    who=(plan_doc["run_id"], run_id))

    monkeypatch.setattr(campaign, "run_side_check", recording)
    real_run(monkeypatch, root, tmp_path, "R2")
    assert seen == {"held": True, "events": False, "who": ("R2", "R2")}, seen
    assert doc["run_id"] == "R2"


def test_a_tree_edit_after_attach_is_stopped_by_the_real_engine_with_hb_idn_001_p4_p5(tmp_path, monkeypatch, capsys):
    root = tree(tmp_path)
    baselined(root, "T1", "T2")
    digest = registered(root)
    drifted = tree(tmp_path, "drifted")  # a plan stamped from a tree that is not the chain's (the hand-stamp of P-4)
    edit_src(drifted, "engine.py")
    stamp = identity.side(identity.manifest(drifted, ["T1", "T2"]), "run")
    write_plan(root, "H1", prereg_hash=digest, harness="fake", ident={"hash": identity.identity_hash(stamp), "components": stamp["components"]})
    capsys.readouterr()
    assert bench(root, "campaign", "attach", CID, "H1") == 1
    assert "HB-CMP-010" in capsys.readouterr().err
    write_plan(root, "R2", prereg_hash=digest, harness="fake")
    assert bench(root, "campaign", "attach", CID, "R2") == 0
    edit_src(root, "engine.py")  # the tree changes after the attach: the chain still matches the plan, the tree does not
    assert real_run(monkeypatch, root, tmp_path, "R2") == 3
    events = run_events(root, "R2")
    stops = [r for r in events if r["kind"] == "run.launch_stopped"]
    assert [r["code"] for r in stops] == ["HB-IDN-001"]
    assert not any(r["kind"] == "cell.launch_intent" for r in events)


def test_a_grid_launch_never_precedes_its_attach_row_i3(tmp_path, monkeypatch):
    root = tree(tmp_path)
    attached(root)
    from test_engine import FakeLauncher

    seen: list[list[str]] = []
    real = FakeLauncher.check_build

    def recording(self):
        seen.append([r["kind"] + ":" + str(r.get("run_id")) for r in rows_of(root)])
        return real(self)

    monkeypatch.setattr(FakeLauncher, "check_build", recording)
    assert real_run(monkeypatch, root, tmp_path, "R2") == 0, [(r["kind"], r.get("code"), r.get("diff")) for r in run_events(root, "R2")]
    assert seen and all("grid.attached:R2" in kinds_then for kinds_then in seen), seen


# --- X-INTF F-3: the campaign commands read the --runs folder ------------------------------------------------------------------------

def plan_outside_root(root: Path, tmp_path: Path, run_id: str = "R2") -> Path:
    """A registered campaign and a grid plan that exists only under a runs folder outside the root."""
    baselined(root, "T1", "T2")
    write_plan(root, run_id, prereg_hash=registered(root), harness="fake", tasks=("T1", "T2"))
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    shutil.move(str(root / "runs" / run_id), str(elsewhere / run_id))
    return elsewhere


def test_attach_reads_the_runs_folder_given_by_runs_not_root_runs_f3(tmp_path):
    root = tree(tmp_path)
    elsewhere = plan_outside_root(root, tmp_path)
    assert cli_rc(["--root", str(root), "--runs", str(elsewhere), "campaign", "attach", CID, "R2"]) == 0
    assert kinds(root)[-1] == "grid.attached"


def test_attach_without_runs_still_reads_root_runs_f3(tmp_path):
    root = tree(tmp_path)
    elsewhere = plan_outside_root(root, tmp_path)
    shutil.move(str(elsewhere / "R2"), str(root / "runs" / "R2"))
    assert cli_rc(["--root", str(root), "campaign", "attach", CID, "R2"]) == 0
    assert kinds(root)[-1] == "grid.attached"


def test_conclude_probes_the_attached_runs_lock_in_the_runs_folder_given_by_runs_f3(tmp_path):
    root = tree(tmp_path)
    elsewhere = plan_outside_root(root, tmp_path)
    runs_args = ["--root", str(root), "--runs", str(elsewhere)]
    assert cli_rc([*runs_args, "campaign", "attach", CID, "R2"]) == 0
    with held_by_another_process(elsewhere / "R2" / ".lock"):
        assert cli_rc([*runs_args, "campaign", "conclude", CID]) == 1
    assert kinds(root)[-1] == "grid.attached"
