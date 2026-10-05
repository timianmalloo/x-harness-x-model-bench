"""The campaign record: one ledger per campaign, one lock, one fold (W1-C rev 2 under W0 rev 6; ADR-0016, ADR-0017, ADR-0018 11).

Aggregate: the Campaign, root `campaign_id`. Invariant it protects (one): the state is a forward-only walk over the ledger's
rows; from the baseline on the engine identity changes only by an admitted fix; from the first attached grid run the
registered pre-registration never changes. Durable form: facts in `bench/campaigns/<id>/ledger.jsonl` (append-only,
ADR-0006), dimensions in `identity/`, `prereg/`, `power/` (create-only, name = sha256 of the canonical bytes). Nothing is
stored that can be derived: the state, the effective identity and eligibility are folds over the rows.

Patterns: event sourcing over a closed transition table (`fold`); Execute-Around (`session`); content-addressed store
(`atomic.create_once`); mutual exclusion by a symmetric try-lock handshake (`oslock.acquire_then_probe`); a witness check
keyed on content, never on `git status` letters (`verify`).

*assume (W0 rev 6, RV-DS 7):* both sides of every lock pair run in one OS lock domain on a local disk (Windows `msvcrt` or
POSIX `flock`, not mixed, not a synced or network folder). Confirm: the operator doc says so. If false: a campaign write can
overlap a grading pass.

Reads (`read`, `verify`, `status_text`) take no lock, probe nothing, sweep nothing and create nothing. Writes go through
`session`, which validates the id, `lstat`s the path chain without creating anything, locks, reads, verifies, sweeps, and
releases on every path. `_append` is the only function that writes a row.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import stat
import time
from collections.abc import Iterator, Mapping, Sequence
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path

from harness_bench import (
    atomic,
    gitsafe,
    identity,
    ledger,
    oslock,
    plan,
    readiness,
    status,
)
from harness_bench.errors import BenchError
from harness_bench.grade.property import check_segment

FIELDS: Mapping[str, Mapping[str, str]] = {  # exact field sets besides kind, campaign_id and the stamp; s=str, i=int, d=dict
    "campaign.created": {"question": "s"},
    "baseline.recorded": {"identity_hash": "s", "bench_commit": "s"},
    "defect_fix.admitted": {"defect_class": "s", "commit": "s", "changes": "d", "scope": "s"},
    "power.recorded": {"role": "s", "input_hash": "s"},
    "ring_run.attached": {"ring_hash": "s", "run_id": "s", "plan_hash": "s"},
    "pilot.passed": {"run_id": "s", "grading_id": "s", "gate_input_hash": "s"},
    "admission.decided": {"task": "s", "admitted": "i", "reason": "s"},
    "registered": {"prereg_hash": "s"},
    "grid.attached": {"run_id": "s", "plan_hash": "s"},
    "concluded": {},
    "abandoned": {"reason": "s"},
}
HOUSEKEEPING = frozenset({ledger.TAIL_REPAIRED})  # written by `SegmentWriter.reopen`, no campaign_id; never a transition
FREE_TEXT = frozenset({("campaign.created", "question"), ("abandoned", "reason"), ("admission.decided", "reason")})
TEXT_MAX = 500
TEMP_MIN_AGE_S = 3600  # a younger temp may belong to a live writer that does not take campaign.lock
CAMPAIGN_ID = r"^[a-z0-9][a-z0-9-]{0,39}$"
NOT_RECORDED = "not recorded"  # the grader's word for an input it did not read (`grade/runner.py` NOT_RECORDED)

_STAMP = frozenset({"kind", "campaign_id", "recorded_at", "mono_ns", "seq", "prev_hash", "hash"})
_TYPES = {"s": str, "i": int, "d": dict}
_ID_FIELDS = frozenset({"run_id", "grading_id", "task"})
_ID_KINDS = {"campaign": (CAMPAIGN_ID, "cc-opus"), "run": (status.RUN_ID, "R1"), "grading": (status.RUN_ID, "grade-20261004T101112-0a1b2c"),
             "task": (status.RUN_ID, "S1")}
_REPARSE = 0x400  # FILE_ATTRIBUTE_REPARSE_POINT: a junction on Windows
_SCHEMAS = {"identity": "bench-identity/1", "prereg": "bench-prereg/1", "power": "bench-power-inputs/1"}
_ROW_FOLDER = {"baseline.recorded": ("identity", "identity_hash"), "registered": ("prereg", "prereg_hash"),
               "power.recorded": ("power", "input_hash")}
_REQUIRED_IGNORE = ("bench/campaigns/**/*.tmp-*", "bench/discrimination/**/*.tmp-*", "bench/campaigns/*/campaign.lock")
_WATCHED = ("bench/campaigns", "bench/discrimination")
_LEDGER_PATH = re.compile(r"bench/campaigns/[^/]+/ledger\.jsonl")
_GIT_TIMEOUT = 60


@dataclass(frozen=True)
class Finding:
    code: str
    path: str
    detail: str
    level: str = "error"  # "warning" for a leaked temp: named, never fatal


@dataclass(frozen=True)
class CampaignState:
    campaign_id: str
    state: str
    rows: tuple[dict, ...]  # the campaign's own rows in seq order; housekeeping rows are not facts of the campaign


@dataclass(frozen=True)
class RunFacts:
    run_id: str
    plan_present: bool
    plan_hash: str  # the plan's own verified `plan_hash` field (W0 rev 6 R6-5), never a second read of the file
    plan_campaign_id: str | None
    plan_prereg_hash: str | None
    plan_run_identity_hash: str | None
    plan_ring_hash: str | None
    grade_identity_hash: str


@dataclass(frozen=True)
class Eligibility:
    eligible: bool
    reasons: tuple[str, ...]


@dataclass
class Session:
    root: Path
    campaign_id: str
    state: CampaignState | None  # None: the ledger does not exist yet (`create`)
    lock: oslock.RunLock | None
    swept: list[Path]
    skipped: list[Path]
    _writer: ledger.SegmentWriter | None = field(default=None, repr=False)


# --- names and paths -----------------------------------------------------------------------------------------------

def validate_id(kind: str, value: str) -> str:
    """The one id check (W1-C section 5; W0 rev 6 R6-2). A campaign id also passes `check_segment` ('con', 'nul', 'com1' fit the
    regex and are Windows device names). Raises HB-USR-002."""
    pattern, example = _ID_KINDS[kind]
    if not isinstance(value, str) or not re.fullmatch(pattern, value):
        raise BenchError("HB-USR-002", f'{kind} id "{value}" is malformed ({pattern}). Use {example}.')
    if kind == "campaign":
        try:
            check_segment("campaign id", value, re.compile(CAMPAIGN_ID))
        except ValueError as exc:
            raise BenchError("HB-USR-002", f'campaign id "{value}" cannot be a folder name here ({exc}). Choose another id.') from exc
    return value


def campaign_dir(root: Path, campaign_id: str) -> Path:
    return root / "bench" / "campaigns" / campaign_id


def lock_path(root: Path, campaign_id: str) -> Path:
    """The one builder of `bench/campaigns/<id>/campaign.lock`."""
    return campaign_dir(root, campaign_id) / "campaign.lock"


def _rel(root: Path, path: Path) -> str:
    return path.relative_to(root).as_posix()


def _problem(path: Path, want: str) -> str | None:
    """Why `path` is not a plain regular file or real folder, or None (absent is fine). One `lstat`, never a follow."""
    try:
        st = os.lstat(path)
    except FileNotFoundError:
        return None
    if stat.S_ISLNK(st.st_mode) or getattr(st, "st_file_attributes", 0) & _REPARSE:
        return "is a link or reparse point"
    if want == "dir" and not stat.S_ISDIR(st.st_mode):
        return "is not a folder"
    if want == "file" and not stat.S_ISREG(st.st_mode):
        return "is not a regular file"
    return None


def _structural(root: Path, campaign_id: str) -> list[Finding]:
    """W1-C section 7 step 0 for the fixed chain, then every content file. Nothing is created."""
    cdir = campaign_dir(root, campaign_id)
    chain = [(root / "bench", "dir"), (root / "bench" / "campaigns", "dir"), (cdir, "dir"), (cdir / "ledger.jsonl", "file"),
             *[(cdir / name, "dir") for name in _SCHEMAS], (cdir / "campaign.lock", "file"), (root / "bench" / "discrimination", "dir")]
    out = [Finding("HB-CMP-003", _rel(root, p), f"{p.name} {why}") for p, want in chain if (why := _problem(p, want))]
    if out:
        return out
    for name in _SCHEMAS:
        for entry in _entries(cdir / name):
            if not atomic.is_temp_name(entry.name) and (why := _problem(Path(entry.path), "file")):
                out.append(Finding("HB-CMP-003", _rel(root, Path(entry.path)), f"{entry.name} {why}"))
    return out


def _entries(folder: Path) -> list[os.DirEntry]:
    try:
        with os.scandir(folder) as it:
            return sorted(it, key=lambda e: e.name)
    except (FileNotFoundError, NotADirectoryError):
        return []


# --- git (read-only; through gitsafe) --------------------------------------------------------------------------------

def _git(root: Path, *args: str):
    return gitsafe.git(list(args), root, _GIT_TIMEOUT, check=False)


def _ok(result) -> bool:
    return result.returncode == 0 and not result.timed_out


def _in_head(root: Path, rel: str) -> bool:
    return _ok(_git(root, "cat-file", "-e", f"HEAD:./{rel}"))


def _blob(root: Path, rev: str, rel: str) -> str | None:
    """The text of `rel` at `rev`, or None when absent or too large for `procs.run` to hold whole."""
    result = _git(root, "show", f"{rev}:./{rel}")
    return result.stdout if _ok(result) and not result.truncated else None  # simplify: ceiling 1 MiB; trigger a ledger past it


def _cut(blob: str) -> str:
    """The blob cut at its last newline: a torn tail committed before a repair does not fail every later command."""
    return blob[: blob.rfind("\n") + 1]


def _text(path: Path) -> str:
    return path.read_bytes().decode("utf-8", errors="replace")


def _git_findings(root: Path) -> list[Finding]:
    """W1-C section 7 step 5: the witness. Keys on content, never on status letters."""
    inside = _git(root, "rev-parse", "--is-inside-work-tree")
    if not _ok(inside) or inside.stdout.strip() != "true":
        return [Finding("HB-CMP-003", "bench/campaigns", "bench/campaigns is not in a git work tree; the witness is absent")]
    out: list[Finding] = []
    if _ok(_git(root, "rev-parse", "--verify", "-q", "HEAD")):
        listed = _git(root, "ls-tree", "-r", "--name-only", "-z", "HEAD", "--", *_WATCHED)
        for rel in sorted(p for p in listed.stdout.split("\0") if p):
            out += _head_path_findings(root, rel)
    flagged = _git(root, "ls-files", "-v", "-z", "--", *_WATCHED).stdout.split("\0")
    for entry in filter(None, flagged):
        tag, rel = entry[0], entry[2:]
        if tag in "hsS":
            names = [n for n, on in (("assume-unchanged", tag in "hs"), ("skip-worktree", tag in "sS")) if on]
            out.append(Finding("HB-CMP-003", rel, f"{rel} is marked {' and '.join(names)}; a hidden edit cannot be witnessed"))
    hidden = _git(root, "ls-files", "-z", "--others", "--ignored", "--exclude-standard", "--", *_WATCHED).stdout.split("\0")
    for rel in filter(None, hidden):
        parts = rel.split("/")
        if parts[-1] != "campaign.lock" and not any(atomic.is_temp_name(p) for p in parts):
            out.append(Finding("HB-CMP-003", rel, f"{rel} is ignored by git (a .gitignore line, .git/info/exclude or a global ignore); a hidden path cannot be witnessed"))
    gitignore = root / ".gitignore"
    lines = set(gitignore.read_text(encoding="utf-8").splitlines()) if gitignore.is_file() else set()
    out += [Finding("HB-CMP-003", ".gitignore", f"{line!r} is missing from .gitignore, exactly as a whole line") for line in _REQUIRED_IGNORE
            if line not in lines]
    return out


def _head_path_findings(root: Path, rel: str) -> list[Finding]:
    path = root / rel
    if not path.is_file():
        return [Finding("HB-CMP-003", rel, f"{rel} is in HEAD and absent from the working tree (deleted or renamed)")]
    head = _blob(root, "HEAD", rel)
    if head is None:
        return [Finding("HB-CMP-003", rel, f"{rel} could not be read from HEAD for comparison")]
    if not _LEDGER_PATH.fullmatch(rel):
        return [] if _text(path) == head else [Finding("HB-CMP-003", rel, f"{rel} differs from HEAD; committed files are never edited")]
    out: list[Finding] = []
    if not _text(path).startswith(_cut(head)):
        out.append(Finding("HB-CMP-003", rel, f"{rel} is not an append-only extension of HEAD: a committed line changed"))
    return out + _history_findings(root, rel)


def _history_findings(root: Path, rel: str) -> list[Finding]:
    """The history walk (RV-SEC 4): each blob, cut at its last newline, is a byte prefix of the next commit's blob; and no
    commit that touched the ledger sits off the first-parent line (a merged ledger fails closed, never silently)."""
    first = _git(root, "log", "--first-parent", "--reverse", "--format=%H", "--", rel).stdout.split()
    every = _git(root, "log", "--full-history", "--format=%H", "--", rel).stdout.split()
    out = [Finding("HB-CMP-003", rel, f"commit {sha[:12]} changed {rel} off the first-parent line (a merged ledger); the record is not one line of history")
           for sha in sorted(set(every) - set(first))[:1]]
    previous: str | None = None
    for sha in first:
        blob = _blob(root, sha, rel)
        if blob is None:
            out.append(Finding("HB-CMP-003", rel, f"commit {sha[:12]} removed or cannot show {rel}"))
            continue
        if previous is not None and not blob.startswith(_cut(previous)):
            out.append(Finding("HB-CMP-003", rel, f"commit {sha[:12]} rewrites a committed line of {rel}"))
        previous = blob
    return out


# --- fold: the one transition table --------------------------------------------------------------------------------

_LIVE = ("draft", "baselined", "piloted", "registered", "measuring")
TABLE: Mapping[str, Mapping[str, str]] = {
    "baseline.recorded": {"draft": "baselined"},
    "defect_fix.admitted": {"baselined": "baselined", "piloted": "baselined", "registered": "baselined", "measuring": "measuring"},
    "power.recorded/prior": {"baselined": "baselined", "piloted": "piloted"},
    "power.recorded/final": {"piloted": "piloted", "registered": "registered"},
    "ring_run.attached": {"baselined": "baselined", "piloted": "piloted"},
    "pilot.passed": {"baselined": "piloted", "piloted": "piloted"},
    "admission.decided": {"piloted": "piloted"},
    "registered": {"piloted": "registered", "registered": "registered"},
    "grid.attached": {"registered": "measuring", "measuring": "measuring"},
    "concluded": {"measuring": "concluded"},
    "abandoned": {s: "abandoned" for s in _LIVE},
}


def _step(state: str | None, kind: str, role: str | None = None) -> str | None:
    """The state after `kind` in `state`, or None when the row is illegal there (`state` None: before the first row)."""
    if kind == "campaign.created":
        return "draft" if state is None else None
    if state is None:
        return None
    key = f"{kind}/{role}" if kind == "power.recorded" else kind
    return TABLE.get(key, {}).get(state)


def fold(rows: Sequence[Mapping], campaign_id: str = "") -> CampaignState:
    """The campaign's state: the last transition row's result, by one table (`TABLE`), replayed by `verify` through this function.

    One rule for the power rows (W0 rev 6 R6-16, OI-5), stated here and nowhere else: `power.recorded` is not a transition row
    (the state does not move); "latest" is the largest `seq`, never file order; role `final` is legal in `piloted` and in
    `registered`, role `prior` in `baselined` and `piloted`, and neither after the first `grid.attached` (the state is then
    `measuring`: the command maps that to HB-CMP-009); `attach` is refused (HB-CMP-002, "re-register after the latest final
    power") unless the latest final power's `seq` is smaller than the latest `registered` row's. A fix demotes `piloted` and
    `registered` to `baselined` and leaves `measuring` alone. Housekeeping rows are skipped.
    """
    state: str | None = None
    kept: list[dict] = []
    for row in rows:
        kind = row["kind"]
        if kind in HOUSEKEEPING:
            continue
        nxt = _step(state, kind, row.get("role"))
        if nxt is None:
            raise BenchError("HB-CMP-003", f"seq {row['seq']} kind {kind} is not legal in state {state or 'none'}. Do not edit the ledger; start another campaign.")
        state = nxt
        kept.append(dict(row))
    return CampaignState(campaign_id, state or "draft", tuple(kept))


def latest(state: CampaignState, kind: str, **match) -> dict | None:
    """The row of `kind` with the largest seq whose fields equal `match`."""
    hits = [r for r in state.rows if r["kind"] == kind and all(r.get(k) == v for k, v in match.items())]
    return max(hits, key=lambda r: r["seq"], default=None)


# --- read ---------------------------------------------------------------------------------------------------------

def _unknown(root: Path, campaign_id: str) -> BenchError:
    """An absent ledger is HB-CMP-005, unless HEAD holds one: then it was deleted, and that is HB-CMP-003 (RV-SEC rev 2)."""
    rel = _rel(root, campaign_dir(root, campaign_id) / "ledger.jsonl")
    if _in_head(root, rel):
        return BenchError("HB-CMP-003", f'{rel} is in HEAD and absent from the working tree. Restore it with git; a deleted ledger is never recreated.')
    return BenchError("HB-CMP-005", f'campaign "{campaign_id}" does not exist. Run bench campaign create {campaign_id}.')


def _refuse_findings(campaign_id: str, findings: Sequence[Finding]) -> BenchError:
    first = findings[0]
    more = f" (+{len(findings) - 1} more)" if len(findings) > 1 else ""
    return BenchError("HB-CMP-003", f'campaign "{campaign_id}" failed verify: {first.path}: {first.detail}{more}. Fix the record or start another campaign.')


def read(root: Path, campaign_id: str) -> CampaignState:
    """Lock-free: validates the id, `lstat`s the chain, verifies the chain and folds. A torn tail is ignored (ADR-0006)."""
    campaign_id = validate_id("campaign", campaign_id)
    problems = _structural(root, campaign_id)
    if problems:
        raise _refuse_findings(campaign_id, problems)
    path = campaign_dir(root, campaign_id) / "ledger.jsonl"
    if not path.exists():
        raise _unknown(root, campaign_id)
    try:
        rows = ledger.read_segment(path)
    except BenchError as exc:
        raise BenchError("HB-CMP-003", f'campaign "{campaign_id}" ledger is broken: {exc.message}. Fix the record or start another campaign.') from exc
    return fold(rows, campaign_id)


def _baseline_components(root: Path, state: CampaignState) -> dict:
    row = latest(state, "baseline.recorded")
    if row is None:
        raise BenchError("HB-CMP-002", f'campaign "{state.campaign_id}" has no baseline yet. Run bench campaign baseline.')
    path = campaign_dir(root, state.campaign_id) / "identity" / f"{row['identity_hash']}.json"
    try:
        return json.loads(path.read_bytes())
    except (OSError, ValueError) as exc:
        raise BenchError("HB-CMP-003", f"{_rel(root, path)} cannot be read as the baseline manifest ({exc}). Restore it with git.") from exc


def effective_identity(root: Path, state: CampaignState, upto_seq: int | None = None) -> dict:
    """The baseline manifest with each admitted fix (seq <= upto_seq) applied in seq order."""
    base = _baseline_components(root, state)
    components = dict(base["components"])
    for row in state.rows:
        if row["kind"] == "defect_fix.admitted" and (upto_seq is None or row["seq"] <= upto_seq):
            for key, pair in row["changes"].items():
                components[key] = pair[1]
    return {"schema": base["schema"], "components": components}


def check_fix(effective: Mapping, changes: Mapping) -> None:
    """Raises HB-CMP-007 on a before-hash that is not the effective one; `verify` replays every fix through it."""
    have = effective["components"]
    for key, pair in changes.items():
        if not (isinstance(pair, list) and len(pair) == 2 and all(isinstance(v, str) for v in pair)):
            raise BenchError("HB-CMP-007", f'component "{key}": changes must be [before, after]. Name both hashes.')
        if have.get(key) != pair[0]:
            raise BenchError("HB-CMP-007", f'component "{key}": before {pair[0][:12]} is not the effective identity\'s {str(have.get(key))[:12]}. Name the current hash.')


# --- eligibility (pure) ---------------------------------------------------------------------------------------------

def _side_hash(manifest: Mapping, which: str) -> str:
    return identity.identity_hash(identity.side(dict(manifest), which))


def _undo(effective: Mapping, rows: Sequence[Mapping], upto_seq: int) -> dict:
    """The effective manifest as it stood at `upto_seq`: later fixes taken back, newest first."""
    components = dict(effective["components"])
    later = sorted((r for r in rows if r["kind"] == "defect_fix.admitted" and r["seq"] > upto_seq), key=lambda r: -r["seq"])
    for row in later:
        for key, pair in row["changes"].items():
            components[key] = pair[0]
    return {"schema": effective["schema"], "components": components}


def eligibility(state: CampaignState, effective: Mapping, run: RunFacts, first_grid: RunFacts | None) -> Eligibility:
    """W1-C section 8: a run is eligible iff all seven rules hold; each failure adds its reason, in rule order. `effective` is
    the effective identity now. Ordering is by `seq`, never by a clock."""
    if not run.plan_present:  # rule 0: rules 1-7 need the plan
        return Eligibility(False, (NOT_RECORDED,))
    rows = state.rows
    reasons: list[str] = []
    attach = max((r for r in rows if r["kind"] in ("ring_run.attached", "grid.attached") and r["run_id"] == run.run_id),
                 key=lambda r: r["seq"], default=None)
    registered = latest(state, "registered")
    if run.plan_campaign_id != state.campaign_id:
        reasons.append(f'plan names campaign "{run.plan_campaign_id}", not "{state.campaign_id}"')
    if attach is not None and attach["kind"] == "grid.attached" and (registered is None or run.plan_prereg_hash != registered["prereg_hash"]):
        reasons.append("plan prereg hash is not the registered prereg hash")
    if attach is None:
        reasons.append("run is not attached to the campaign")
    elif attach["plan_hash"] != run.plan_hash:
        reasons.append("plan hash differs from the attached row's plan hash")
    if attach is not None:
        if _side_hash(_undo(effective, rows, attach["seq"]), "run") != run.plan_run_identity_hash:
            reasons.append("plan run identity differs from the effective run identity at attach")
        fix = min((r for r in rows if r["kind"] == "defect_fix.admitted" and r["scope"] in ("run", "both") and r["seq"] > attach["seq"]),
                  key=lambda r: r["seq"], default=None)
        if fix is not None:
            reasons.append(f"a run-side fix (seq {fix['seq']}) was admitted after the run attached")
    if _side_hash(effective, "grade") != run.grade_identity_hash:
        reasons.append("grade identity differs from the current effective grade identity")
    if (attach is None or attach["kind"] == "grid.attached") and first_grid is not None and run.plan_ring_hash != first_grid.plan_ring_hash:
        reasons.append("ring hash differs from the first grid run's ring hash")
    return Eligibility(not reasons, tuple(reasons))


def run_facts(run_dir: Path, grading_id: str) -> RunFacts:
    """The only impure loader: `plan.json` through `plan.load_confirmed` and the pass's `grading.started` row."""
    run_id = run_dir.name
    grade_hash = NOT_RECORDED
    events = run_dir / "events" / f"{grading_id}.jsonl"
    if events.is_file():
        started = next((r for r in ledger.read_segment(events) if r["kind"] == "grading.started"), None)
        grade_hash = started.get("grade_identity_hash", NOT_RECORDED) if started else NOT_RECORDED
    if not (run_dir / "plan.json").is_file():
        return RunFacts(run_id, False, "", None, None, None, None, grade_hash)
    loaded = plan.load_confirmed(run_dir)
    block = loaded.get("campaign") or {}
    return RunFacts(run_id, True, loaded["plan_hash"], block.get("campaign_id"), block.get("prereg_hash"),
                    (block.get("identity") or {}).get("hash"), (loaded.get("ring") or {}).get("hash"), grade_hash)


# --- verify ---------------------------------------------------------------------------------------------------------

def _type_ok(value, code: str) -> bool:
    return isinstance(value, _TYPES[code]) and not (code == "i" and isinstance(value, bool))


def _printable_text(text: str) -> bool:
    return len(text) <= TEXT_MAX and text.isprintable()


def _check_text(name: str, text: str) -> None:
    if len(text) > TEXT_MAX:
        raise BenchError("HB-USR-002", f"{name} is longer than {TEXT_MAX} characters. Shorten it.")
    if not text.isprintable():
        raise BenchError("HB-USR-002", f"{name} contains a control character. Remove it.")


def _shape_findings(rows: Sequence[Mapping], campaign_id: str, rel: str) -> list[Finding]:
    out: list[Finding] = []

    def bad(row, text):
        out.append(Finding("HB-CMP-003", rel, f"seq {row['seq']} kind {row['kind']} {text}"))

    for row in rows:
        kind = row["kind"]
        if kind in HOUSEKEEPING:
            continue
        if kind not in FIELDS:
            bad(row, "is not a campaign kind")
            continue
        want, got = _STAMP | set(FIELDS[kind]), set(row)
        if got != want:
            bad(row, f"has fields {sorted(got - want)} extra and {sorted(want - got)} missing; the closed set is {sorted(want)}")
            continue
        for name, code in FIELDS[kind].items():
            if not _type_ok(row[name], code):
                bad(row, f"field {name} has type {type(row[name]).__name__}, expected {_TYPES[code].__name__}")
            elif name in _ID_FIELDS and not re.fullmatch(status.RUN_ID, row[name]):
                bad(row, f"field {name} {row[name]!r} is malformed ({status.RUN_ID})")
            elif (kind, name) in FREE_TEXT and not _printable_text(row[name]):
                bad(row, f"field {name} is longer than {TEXT_MAX} characters or not printable")
        if row["campaign_id"] != campaign_id:
            bad(row, f"campaign_id {row['campaign_id']!r} is not the folder name {campaign_id!r}")
    return out


def _replay_findings(root: Path, rows: Sequence[Mapping], campaign_id: str, rel: str) -> tuple[list[Finding], CampaignState | None]:
    try:
        state = fold(rows, campaign_id)
    except BenchError as exc:
        return [Finding("HB-CMP-003", rel, exc.message)], None
    out: list[Finding] = []
    try:
        components = dict(_baseline_components(root, state)["components"])
    except BenchError:
        return out, state  # no baseline, or its file is missing or unreadable: step 4 names it
    for row in state.rows:
        if row["kind"] != "defect_fix.admitted":
            continue
        try:
            check_fix({"components": components}, row["changes"])
            components.update({k: pair[1] for k, pair in row["changes"].items()})
        except (BenchError, AttributeError, TypeError) as exc:
            detail = exc.message if isinstance(exc, BenchError) else f"changes are malformed ({exc})"
            out.append(Finding("HB-CMP-003", rel, f"seq {row['seq']} kind defect_fix.admitted: {detail}"))
    return out, state


def _content_findings(root: Path, cdir: Path, rows: Sequence[Mapping]) -> list[Finding]:
    out: list[Finding] = []
    for folder, schema in _SCHEMAS.items():
        for entry in _entries(cdir / folder):
            if atomic.is_temp_name(entry.name):
                continue
            path = Path(entry.path)
            try:
                data = path.read_bytes()
            except OSError:
                continue
            if entry.name != f"{hashlib.sha256(data).hexdigest()}.json":
                out.append(Finding("HB-CMP-003", _rel(root, path), f"{entry.name} is not named by the sha256 of its bytes"))
                continue
            try:
                body = json.loads(data)
            except ValueError:
                body = None
            if not isinstance(body, dict) or body.get("schema") != schema:
                out.append(Finding("HB-CMP-003", _rel(root, path), f"{entry.name} is not valid JSON of schema {schema}"))
    for row in rows:
        folder, name = _ROW_FOLDER.get(row["kind"], (None, None))
        if folder and row.get(name) and not (cdir / folder / f"{row[name]}.json").is_file():
            out.append(Finding("HB-CMP-003", _rel(root, cdir / folder), f"seq {row['seq']} kind {row['kind']} names {folder}/{row[name]}.json, which is missing"))
    return out


def _discrimination_findings(root: Path, state: CampaignState | None) -> list[Finding]:
    """Plain task folders and record names under `bench/discrimination/` (W0 rev 6 R6-7). X-C reads here and never deletes."""
    out: list[Finding] = []
    disc = root / "bench" / "discrimination"
    named: list[str] = []
    if state is not None:
        try:
            named = [k.split("/", 1)[1] for k in _baseline_components(root, state)["components"] if k.startswith("tasks/")]
        except BenchError:
            named = []
    for task in sorted(set(named)):
        if why := _problem(disc / task, "dir"):
            out.append(Finding("HB-CMP-003", _rel(root, disc / task), f"task folder {task} {why}"))
    for folder in _entries(disc):
        path = Path(folder.path)
        if why := _problem(path, "dir"):
            if path.name not in named:
                out.append(Finding("HB-CMP-003", _rel(root, path), f"{folder.name} {why}"))
            continue
        for entry in _entries(path):
            if atomic.is_temp_name(entry.name):
                continue
            out += _record_findings(root, path, Path(entry.path))
    return out


def _record_findings(root: Path, folder: Path, record: Path) -> list[Finding]:
    rel = _rel(root, record)
    try:
        body = json.loads(record.read_bytes())
        expected = readiness.record_name(body["task_version"], body["identity_hash"], body["platform"])
        task = body["task"]
    except (OSError, ValueError, KeyError, TypeError):
        return [Finding("HB-CMP-003", rel, f"{record.name} is not a discrimination record body")]
    out: list[Finding] = []
    if record.name != expected:
        out.append(Finding("HB-CMP-003", rel, f"{record.name} is not the name its body derives ({expected})"))
    if task != folder.name:
        out.append(Finding("HB-CMP-003", rel, f"{record.name} records task {task!r}, not the folder {folder.name!r}"))
    return out


def _temp_warnings(root: Path, cdir: Path) -> list[Finding]:
    out: list[Finding] = []
    folders = [cdir, *[cdir / n for n in _SCHEMAS], *[Path(e.path) for e in _entries(root / "bench" / "discrimination")]]
    for folder in folders:
        for entry in _entries(folder):
            if not atomic.is_temp_name(entry.name):
                continue
            try:
                os.lstat(entry.path)
            except FileNotFoundError:
                continue  # it vanished between listing and lstat: a sweep or a finished write; absent, not a finding
            out.append(Finding("HB-CMP-003", _rel(root, Path(entry.path)), f"leaked temp {entry.name}", level="warning"))
    return out


def verify(root: Path, campaign_id: str) -> list[Finding]:
    """W1-C section 7, lock-free. Errors make the command exit 5; a leaked temp is a warning. A content file no row names yet is
    no finding: every create-only write is the content file first, then its row (W0 rev 6 R6-3)."""
    campaign_id = validate_id("campaign", campaign_id)
    problems = _structural(root, campaign_id)
    if problems:
        return problems
    cdir = campaign_dir(root, campaign_id)
    path = cdir / "ledger.jsonl"
    if not path.exists():
        if not _in_head(root, _rel(root, path)):
            raise _unknown(root, campaign_id)
        return _deleted_ledger(root, path)
    rel = _rel(root, path)
    out: list[Finding] = []
    state: CampaignState | None = None
    report = ledger.verify_segment(path)
    rows: list[dict] = []
    if report.error:
        out.append(Finding("HB-CMP-003", rel, f"chain: {report.detail}"))
    else:
        rows = ledger.read_segment(path)
        out += _shape_findings(rows, campaign_id, rel)
        replay, state = _replay_findings(root, rows, campaign_id, rel)
        out += replay
    out += _content_findings(root, cdir, rows)
    out += _discrimination_findings(root, state)
    out += _git_findings(root)
    return out + _temp_warnings(root, cdir)


def _deleted_ledger(root: Path, path: Path) -> list[Finding]:
    return [Finding("HB-CMP-003", _rel(root, path), f"{path.name} is in HEAD and absent from the working tree")] + _git_findings(root)


# --- sweep ----------------------------------------------------------------------------------------------------------

def sweep_folder(cdir: Path, folder: Path, lock: oslock.RunLock) -> tuple[list[Path], list[Path]]:
    """Sweep one of this campaign's four folders under its own `campaign.lock`: (swept, skipped). The pairing line is the
    `discriminate._sweep` shape: `atomic` does not know which lock guards which folder, so this does. The age gate skips a
    folder, and reports it, unless every temp in it is older than `TEMP_MIN_AGE_S`."""
    if lock.path != cdir / "campaign.lock" or folder not in {cdir, *[cdir / n for n in _SCHEMAS]}:
        raise ValueError(f"lock {lock.path} does not guard {folder}")
    temps = atomic.stale_temps(folder)
    if not temps:
        return [], []
    cutoff = time.time() - TEMP_MIN_AGE_S
    for temp in temps:
        try:
            if os.lstat(temp).st_mtime > cutoff:
                return [], [folder]
        except FileNotFoundError:
            continue
    return atomic.sweep_temps(folder, lock), []


# --- session ---------------------------------------------------------------------------------------------------------

def _attached_runs(state: CampaignState | None) -> list[str]:
    runs = {r["run_id"] for r in (state.rows if state else ()) if r["kind"] in ("ring_run.attached", "grid.attached")}
    return sorted(runs)


def _lock_refusal(exc: BenchError, root: Path, campaign_id: str) -> BenchError:
    if exc.code == "HB-CMP-001":
        return BenchError("HB-CMP-001", f'campaign "{campaign_id}" is being written. Retry in a moment.')
    if exc.code == "HB-CMP-004":
        run = next(iter(re.findall(r"runs[\\/]([^\\/]+)", exc.message)), "?")
        return BenchError("HB-CMP-004", f'run "{run}" is being graded. A campaign write must not be open during a grading pass. Wait for the pass to finish.')
    return exc


def _precheck(root: Path, campaign_id: str, create: bool) -> None:
    problems = _structural(root, campaign_id)
    if problems:
        raise _refuse_findings(campaign_id, problems)
    if not (campaign_dir(root, campaign_id) / "ledger.jsonl").exists() and (not create or _in_head(root, _rel(root, campaign_dir(root, campaign_id) / "ledger.jsonl"))):
        raise _unknown(root, campaign_id)


def _locked(root: Path, campaign_id: str, others_extra: Sequence[tuple[Path, str]], wait_s: float, create: bool):
    """Acquire `campaign.lock` and probe the attached runs' `grade.lock`s in one `acquire_then_probe` call. Lock first, then
    read: the probe set is read lock-free first, and a run attached in between is caught by the re-read and retried."""
    deadline = time.monotonic() + wait_s
    path = lock_path(root, campaign_id)
    for _ in range(3):
        runs = _attached_runs(read(root, campaign_id) if (campaign_dir(root, campaign_id) / "ledger.jsonl").exists() else None)
        others = [(root / "runs" / run / "grade.lock", "HB-CMP-004") for run in runs] + list(others_extra)
        while True:
            try:
                lock = oslock.acquire_then_probe(path, "HB-CMP-001", others)
                break
            except BenchError as exc:
                if time.monotonic() >= deadline:
                    raise _lock_refusal(exc, root, campaign_id) from exc
                time.sleep(0.2)  # simplify: ceiling callers wait seconds; upgrade trigger a caller that waits minutes
        ledger_file = campaign_dir(root, campaign_id) / "ledger.jsonl"
        now = read(root, campaign_id) if ledger_file.exists() else None
        if not (set(_attached_runs(now)) - set(runs)):
            return lock
        lock.release()
    raise BenchError("HB-CMP-001", f'campaign "{campaign_id}" is being written. Retry in a moment.')


@contextmanager
def session(root: Path, campaign_id: str, *, others_extra: Sequence[tuple[Path, str]] = (), wait_s: float = 0.0,
            create: bool = False, run_locks: bool = False, between=None) -> Iterator[Session]:
    """The one Execute-Around of every write command: validate, `lstat` the chain, lock-and-probe, read, verify, sweep, run,
    close the writer, release. `others_extra` is the command's own extra probe entries (C2: the run locks)."""
    campaign_id = validate_id("campaign", campaign_id)
    _precheck(root, campaign_id, create)
    lock = _locked(root, campaign_id, others_extra, wait_s, create)
    sess: Session | None = None
    try:
        ledger_file = campaign_dir(root, campaign_id) / "ledger.jsonl"
        state = None
        if ledger_file.exists():
            errors = [f for f in verify(root, campaign_id) if f.level == "error"]
            if errors:
                raise _refuse_findings(campaign_id, errors)
            state = read(root, campaign_id)
        sess = Session(root, campaign_id, state, lock, [], [])
        cdir = campaign_dir(root, campaign_id)
        for folder in (cdir, *[cdir / n for n in _SCHEMAS]):
            swept, skipped = sweep_folder(cdir, folder, lock)
            sess.swept += swept
            sess.skipped += skipped
        yield sess
    finally:
        if sess is not None and sess._writer is not None:
            sess._writer.close()  # one open writer per path per process: close it before the lock goes
        lock.release()


def _open_writer(sess: Session) -> ledger.SegmentWriter:
    if sess._writer is None:
        path = campaign_dir(sess.root, sess.campaign_id) / "ledger.jsonl"
        sess._writer = ledger.SegmentWriter.reopen(path) if path.exists() else ledger.SegmentWriter.create(path.parent, "ledger")
    return sess._writer


def _append(sess: Session, kind: str, **fields) -> dict:
    """The one write API: validates the closed field set and the types (a bool is refused here, before `canonical`), bounds free
    text, checks the transition table, then appends one chained, stamped row under the held lock."""
    if sess.lock is None or not sess.lock.held:
        raise ValueError("_append needs a held session")
    spec = FIELDS.get(kind)
    if spec is None:
        raise BenchError("HB-CMP-003", f"kind {kind!r} is not a campaign kind. Use one of {sorted(FIELDS)}.")
    if set(fields) != set(spec):
        raise BenchError("HB-CMP-003", f"row kind {kind} has fields {sorted(fields)} but the closed set is {sorted(spec)}. Pass exactly that set.")
    for name, code in spec.items():
        if not _type_ok(fields[name], code):
            raise BenchError("HB-CMP-003", f"row kind {kind} field {name} has type {type(fields[name]).__name__}, expected {_TYPES[code].__name__}. Pass a {_TYPES[code].__name__}.")
        if (kind, name) in FREE_TEXT:
            _check_text(name, fields[name])
    started = sess.state is not None and bool(sess.state.rows)  # a ledger file with no row yet is "before the first row"
    before = sess.state.state if started else None
    if _step(before, kind, fields.get("role")) is None:
        raise BenchError("HB-CMP-002", f'kind {kind} is not legal in state {before or "none"} for campaign "{sess.campaign_id}". Run bench campaign status {sess.campaign_id} to see the next step.')
    writer = _open_writer(sess)
    try:
        row = writer.append(ledger.stamp({"kind": kind, "campaign_id": sess.campaign_id, **fields}))
    except TypeError as exc:  # a float or bool nested inside a dict field: the canonical form has none
        raise BenchError("HB-CMP-003", f"row kind {kind} holds a value the canonical form refuses ({exc}). Use str, int, list or dict.") from exc
    rows = (*(sess.state.rows if started else ()), row)
    sess.state = CampaignState(sess.campaign_id, _step(before, kind, fields.get("role")) or "draft", rows)
    return row


# --- commands (library half; `cli.py` parses and prints) -----------------------------------------------------------

def create(root: Path, campaign_id: str, question: str) -> str:
    """`bench campaign create`: one `campaign.created` row; the same question again is a no-op, another question a refusal."""
    campaign_id = validate_id("campaign", campaign_id)
    _check_text("question", question)  # before any path is built: a bad question creates nothing
    with session(root, campaign_id, create=True) as s:
        if s.state is None or not s.state.rows:
            _append(s, "campaign.created", question=question)
            return f'created campaign "{campaign_id}"'
        if s.state.rows[0]["question"] == question:
            return f'no change: campaign "{campaign_id}" already exists with this question'
    raise BenchError("HB-CMP-002", f'campaign "{campaign_id}" already exists with another question. A new question needs a new campaign id.')


def status_text(root: Path, campaign_id: str) -> tuple[str, list[Finding]]:
    """`bench campaign status` (minimal text view): state, row count and `verify`'s result. Lock-free."""
    state = read(root, campaign_id)
    findings = verify(root, campaign_id)
    errors = [f for f in findings if f.level == "error"]
    result = "ok" if not errors else f"failed ({len(errors)} findings)"
    return f"campaign {campaign_id}: state {state.state}, rows {len(state.rows)}, verify {result}", findings


# --- C2a commands (skeleton: final signatures, neutral wrong values) -----------------------------------------------

def validate_defect_class(value: str) -> str:
    return value


def validate_commit(value: str) -> str:
    return value


def default_tasks(root: Path) -> list[str]:
    return []


def baseline_unmet(root: Path, tasks: Sequence[str]) -> list[str]:
    return []


def baseline(root: Path, campaign_id: str, tasks: Sequence[str] | None = None) -> str:
    with session(root, campaign_id):
        return ""


def fix(root: Path, campaign_id: str, defect_class: str, commit: str, components: Sequence[str]) -> str:
    with session(root, campaign_id):
        return ""


def power(root: Path, campaign_id: str, inputs_file: Path) -> str:
    with session(root, campaign_id):
        return ""


def check_plan(root: Path, state: CampaignState, plan_doc: dict, run_id: str, *, grid: bool = True, tree: bool = True) -> None:
    return None


def run_side_check(root: Path, plan_doc: dict, run_id: str) -> None:
    return None


def attach(root: Path, campaign_id: str, run_id: str) -> str:
    with session(root, campaign_id):
        return ""


def conclude(root: Path, campaign_id: str) -> str:
    with session(root, campaign_id):
        return ""


def abandon(root: Path, campaign_id: str, reason: str) -> str:
    with session(root, campaign_id):
        return ""
