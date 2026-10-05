"""X-C1 proof, the CLI half and the shared fixtures of the four campaign test modules (W1-C section 13).

This module is the one home of the helpers (`cli_rc`, `make_repo`, `append`, `walk_to`, ...) so no shared conftest is edited.
Tests here: T-3 (every cited test id exists) and the id checks through the real parser. C1 drives no engine.

Expected values are typed here or computed with hashlib, never with the function under test (RV-TA 1).
"""

from __future__ import annotations

import hashlib
import re
import subprocess
import sys
from contextlib import contextmanager
from pathlib import Path

import pytest

from harness_bench import atomic, campaign, cli, gitsafe, ledger
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
        "power": ["--inputs", "inputs.json"], "attach": ["R1"], "conclude": [], "abandon": ["--reason", "done"]}  # per subcommand: the options after the id (N-1 follows the table)


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


