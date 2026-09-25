"""Judge backends and the headless CLI launch (design phase3-gateway-judges sections 8.1-8.2 and 16).

A backend takes the released request text and the call's id and returns a `Reply`: the CLI's stdout as it printed
it, and the call's native record, archived. It never returns parsed facts: the pipeline's readers decide what the
record says (directive D7). A backend that cannot answer raises `BackendDown` (HB-GW-001), never a score.

- `ReplayBackend` (tests, directive D7): replays recorded files keyed by the request's sha256; it copies the record
  into the archive, as a real call does. It opens no process, socket or listener.
- `Headless`: one judge call through the pinned CLI (Claude Code or Copilot). The argv builders below are the one
  definition; the probe (`tests/fixtures/gateway/probe_judge.py`) imports them, so a re-qualification tests this exact
  invocation. The request goes on stdin, never in argv (section 8.1; R-70 item 2). The call runs in its own folder under the cells root,
  `<cells root>/gateway/<grading_id>/<call_id>/{home,work,profile}` (section 8.2), through `procs.run` in its own
  Job Object. `Headless` is reached only inside `egress.check(...).release(...)` (tests/test_architecture.py).
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from harness_bench import (
    gitsafe,
    ledger,
    oslock,
    procs,
    profiles,
    status,
    tools,
    workspace,
)
from harness_bench.errors import BenchError

# The judge's system prompt: part of the invocation (section 9.1), so a change is a new invocation_sha256.
JUDGE_SYSTEM = "You are a grader. You score one artifact against a rubric and answer with one JSON object only."
# assume: each name below is a Codex 0.156.0 feature whose tool reaches the model when on (moved from the probe).
# Confirm: `codex.exe features list` on the pinned build lists every one. Breaks: a tool stays advertised; spike GW-H
# measured exactly that for code mode (DR-GW-1), so Codex is `qualified: false` and never spawned (R-63).
CODEX_TOOL_FEATURES = ("shell_tool", "unified_exec", "apps", "plugins", "remote_plugin", "browser_use",
                       "browser_use_external", "in_app_browser", "computer_use", "code_mode_host", "image_generation",
                       "view_image", "multi_agent", "sleep_tool", "skill_search", "tool_suggest", "goals", "hooks",
                       "workspace_dependencies", "skill_mcp_dependency_install")
# `include_apply_patch_tool` is dropped: 0.156.0 reports it unrecognized (design section 8.1).
CODEX_CONFIG = ("model={model}", 'approval_policy="never"', 'web_search="disabled"', "project_doc_max_bytes=0")


class BackendDown(Exception):
    """The backend could not answer: CLI error, timeout, no record, or no recorded reply."""


@dataclass(frozen=True)
class Reply:
    stdout: str  # the judge CLI's stdout, verbatim
    record: Path  # the call's native record, archived (section 8.2)
    harness: str = "claude-code"  # which reader reads the record


class Backend(Protocol):
    def judge(self, request: str, call_id: str) -> Reply: ...


# ------------------------------------------------------------------------------------------ argv (one definition)
def claude_argv(exe: str, model: str, system: str, session_id: str, json_schema: str | None = None) -> list[str]:
    """Claude Code 2.1.282 in print mode; the request is piped on stdin (section 8.1). `--tools ""` is variadic, so
    an option always follows it. `json_schema` is the probe's native-mode measurement only: `--json-schema` adds a
    `StructuredOutput` tool call (spike GW-H), so the gateway never passes it."""
    argv = [exe, "-p", "--model", model, "--tools", "", "--strict-mcp-config", "--safe-mode",
            "--disable-slash-commands", "--permission-mode", "dontAsk", "--permission-prompts", "none",
            "--settings", json.dumps({"disableClaudeAiConnectors": True}), "--system-prompt", system,
            "--output-format", "json", "--session-id", session_id]
    return argv + (["--json-schema", json_schema] if json_schema is not None else [])


def codex_argv(exe: str, model: str, work: Path, last: Path, output_schema: Path | None = None) -> list[str]:
    """Codex 0.156.0 `exec`, the request on stdin (`-` as the prompt). Not qualified (DR-GW-1, R-63): never spawned
    by the gateway; the probe measures it."""
    argv = [exe, "exec"]
    for item in CODEX_CONFIG:
        argv += ["-c", item.replace("{model}", model)]
    for feature in CODEX_TOOL_FEATURES:
        argv += ["--disable", feature]
    argv += ["--ignore-user-config", "--ignore-rules", "--skip-git-repo-check", "-s", "read-only", "-C", str(work),
             "--json", "-o", str(last)]
    return argv + (["--output-schema", str(output_schema)] if output_schema is not None else []) + ["-"]


def copilot_argv(exe: str, model: str) -> list[str]:
    """Copilot 1.0.89-1 in print mode, with the flags measured in spike ac44295 (docs/notes/spike-gw-headless.md, last
    section): built-in MCP servers off, custom instructions off (without it Copilot loaded AGENTS.md and CLAUDE.md
    from ancestor folders), and an allowlist naming no real tool (`none`). A bare trailing `--available-tools`
    filtered nothing: 17 tools advertised and `powershell` ran unapproved. Those flags gave tools_advertised [] and
    0 tool events. The answer is the record's last `assistant.message`, not stdout (CLI banners; `copilot_answer`);
    the home is an empty COPILOT_HOME (login in the Windows credential store). R-70: the shape is qualified, the
    judge is not until the Leader's one turn from these builders records its invocation_sha256 (R-70 3(b)).

    The request goes on stdin (`copilot_request`), never in argv (R-70 item 2: an in-bound request can exceed the
    Windows command line). `-p` comes last so no option is read as its value, and it ends the variadic
    `--available-tools` list.
    assume: `-p` with no value reads the prompt from stdin on 1.0.89-1. Confirm: the Leader's qualification turn
    (R-70 3(b), `prompt_delivery: stdin`) or `copilot --help` on the pinned exe. Breaks: the turn fails on delivery,
    so the shape changes, which is a new invocation_sha256 and its own probe (design section 8.4)."""
    return [exe, "--model", model, "--disable-builtin-mcps", "--no-custom-instructions", "--available-tools", "none",
            "-p"]


def copilot_request(system: str, request: str) -> str:
    """What the gateway writes to Copilot's stdin: the judge system prompt, a blank line, then the request (R-70 3(a):
    the route is explicit and inside `invocation_sha256`).
    assume: no system-prompt flag exists on 1.0.89-1 (R-70 3(a)). Confirm: `copilot --help` on the pinned exe.
    Breaks: nothing: the prepend route stands either way."""
    return f"{system}\n\n{request}"


def invocation_sha256(harness: str, model: str, system: str, output: str, build_version: str, exe_sha256: str) -> str:
    """Section 9.1: the argv template with its volatile slots as placeholders, the system prompt, the output mode,
    the harness and the build; for Copilot also the stdin template, which carries the system prompt (R-70 3(a)).
    The probe records it; the Leader copies it into `bench/gateway.yaml`."""
    shape: dict = {"system": system, "output": output, "harness": harness, "build_version": build_version,
                   "exe_sha256": exe_sha256}
    if harness == "claude-code":
        shape["argv"] = claude_argv("<exe>", model, system, "<session-id>")
    elif harness == "codex":
        shape["argv"] = codex_argv("<exe>", model, Path("<work>"), Path("<last message>"))
    else:
        shape |= {"argv": copilot_argv("<exe>", model), "stdin": copilot_request(system, "<request>")}
    return hashlib.sha256(ledger.canonical(shape)).hexdigest()


# ---------------------------------------------------------------------------------------------- the replay backend
@dataclass(frozen=True)
class Recorded:
    stdout: str
    record: Path  # a recorded native record file (tests/fixtures/gateway/records/)
    harness: str = "claude-code"


class ReplayBackend:
    """Replays recorded files for each request it holds a record of; counts every call it receives."""

    def __init__(self, replies: dict[str, Recorded], archive: Path, down: bool = False) -> None:
        self.replies = dict(replies)  # request sha256 -> recorded files
        self.archive = archive
        self.down = down
        self.received: list[str] = []

    def judge(self, request: str, call_id: str) -> Reply:
        self.received.append(request)
        digest = hashlib.sha256(request.encode("utf-8")).hexdigest()
        if self.down or digest not in self.replies:
            raise BackendDown("no recorded reply for this request")
        rec = self.replies[digest]
        return Reply(rec.stdout, archive_record(rec.record, self.archive, call_id), rec.harness)


def archive_record(record: Path, archive: Path, call_id: str) -> Path:
    """Copy a call's native record to `<archive>/<call_id>/record.jsonl` (section 8.2); return the copy."""
    dest = archive / call_id / "record.jsonl"
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(record, dest)
    return dest


# -------------------------------------------------------------------------------------------- the headless backend
@dataclass(frozen=True)
class Launch:
    """One judge's launch for one grading pass: plain data, so a grader may build it; only the pipeline, inside
    `egress.check(...).release(...)`, turns it into a `Headless` call."""

    profile: profiles.Profile  # the harness profile: home variable, credential, record glob
    build: tools.Build  # the pinned CLI
    model: str
    cells_root: Path
    grading_id: str
    archive: Path  # runs/<run>/grading/<grading_id>/gateway (or the calibration ledger's folder)
    timeout: float  # gateway.yaml call_timeout_seconds
    system: str = JUDGE_SYSTEM
    prefix: tuple[str, ...] = ()  # argv before the executable: empty for the pinned exe; a script's interpreter


def call_folder(launch: Launch, call_id: str) -> Path:
    """`<cells root>/gateway/<grading_id>/<call_id>`: no harness, model or combo in the path (section 8.2)."""
    return launch.cells_root / "gateway" / launch.grading_id / call_id


# The harnesses `Headless` launches. `bench/gateway.yaml` may mark a judge `qualified: true` only on one of these
# (R-70 item 4: a qualified entry the gateway cannot launch closes every call as HB-GW-001, read as an outage).
HEADLESS_HARNESSES = ("claude-code", "copilot")


class Headless:
    """One judge call through the pinned headless CLI: Claude Code, or Copilot (R-70 3(a)). Codex is never spawned
    (`qualified: false`, DR-GW-1).

    Copilot differs in three ways: nothing is copied into its empty COPILOT_HOME (`credential: null`: the login is the
    Windows credential store); stdin carries the system prompt before the request (`copilot_request`); and the
    session id is not known before the call, so the record is the only one in the fresh home."""

    def __init__(self, launch: Launch) -> None:
        self.launch = launch

    def judge(self, request: str, call_id: str) -> Reply:
        launch = self.launch
        if launch.profile.harness not in HEADLESS_HARNESSES:
            raise BackendDown(f"the headless backend does not launch {launch.profile.harness}")
        folder = call_folder(launch, call_id)
        home, work, decoy = folder / "home", folder / "work", folder / "profile"
        try:
            for d in (home, work, decoy):
                d.mkdir(parents=True, exist_ok=True)
            source, name = launch.profile.credential_source, launch.profile.credential_name
            if name is not None:  # Copilot names none: its login is the Windows credential store
                if source is None or not source.is_file():
                    raise BackendDown("no credential to copy for the judge call")
                shutil.copyfile(source, home / name)  # inside the try whose finally deletes it (section 8.2)
            exe = str(launch.build.exe)
            if launch.profile.harness == "copilot":
                session, argv, stdin = "*", copilot_argv(exe, launch.model), copilot_request(launch.system, request)
            else:
                session = str(uuid.uuid4())
                argv, stdin = claude_argv(exe, launch.model, launch.system, session), request
            env = launch.profile.cell_env(dict(os.environ), home, launch.build, launch.model, "")
            env.update({"USERPROFILE": str(decoy), "HOME": str(decoy)})  # the qualified decoy profile (section 8.2)
            done = procs.run([*launch.prefix, *argv], cwd=str(work), env=env, timeout=launch.timeout, input=stdin)
            if done.timed_out:
                raise BackendDown(f"no answer within {launch.timeout} s")
            records = profiles.find_records(home, launch.profile.record_glob, session)
            if len(records) != 1:
                raise BackendDown(f"{len(records)} native records for the call, expected 1")
            return Reply(done.stdout, archive_record(records[0], launch.archive, call_id), launch.profile.harness)
        except BackendDown:
            raise
        except Exception as exc:  # any other failure is the judge being unavailable, never an escape (review F6)
            raise BackendDown(f"judge call failed: {type(exc).__name__}") from exc
        finally:
            launch.profile.clean_home(home)  # the credential copy never outlives the call
            shutil.rmtree(folder, ignore_errors=True)


def sweep_credentials(cells_root: Path, names: tuple[str, ...], own: str | None = None) -> list[Path]:
    """Remove every leftover credential copy under `<cells root>/gateway/` (a hard-killed pass; section 8.2), in the
    pass folders whose `.lock` is free, plus `own` (the calling pass's folder). A folder whose lock another pass
    holds is never touched: the cells root is shared across worktrees. Returns the copies removed."""
    removed = []
    root = cells_root / "gateway"
    for pass_dir in sorted(p for p in root.iterdir() if p.is_dir()) if root.is_dir() else []:
        if pass_dir.name != own and oslock.is_held(pass_dir / ".lock"):
            continue
        for name in names:
            for copy in sorted(pass_dir.glob(f"*/home/{name}")):
                copy.unlink(missing_ok=True)
                removed.append(copy)
    return removed


def run_roots(repo: Path, runs: Path) -> tuple[Path, ...]:
    """Section 6 and R-65: the `runs/` of every worktree of `repo` (`git worktree list`), then `runs` (`--runs`),
    resolved, each once. The cells root is shared across worktrees, but each worktree keeps its own `runs/`.

    A bench root with no `.git` is not a checkout and has no worktrees (a test's temp root): only `runs`. In a
    checkout, a git failure raises (GitError), so the scan never narrows silently. Residual (DR-GW-4): a run under
    another `--runs` folder outside every worktree is not seen."""
    roots: list[Path] = []
    if (repo / ".git").exists():
        listing = gitsafe.git(["worktree", "list", "--porcelain"], cwd=repo, timeout=60).stdout
        roots = [Path(line.removeprefix("worktree ")).resolve() / "runs" for line in listing.splitlines()
                 if line.startswith("worktree ")]
    return tuple(dict.fromkeys([*roots, runs.resolve()]))


def refuse_if_live(roots: tuple[Path, ...]) -> None:
    """Section 6 and R-65: HB-GRD-005 when any known run under `roots` has lock liveness `alive` or `stalled`
    (`status.build`; phase is not consulted). `status.require_known` is the one filter: a folder with no plan.json,
    such as a calibration ledger, is not a run (T-GW-19c). The refusal names every scanned root and each live run; a
    stalled one with its lock path and heartbeat age (R-65 c1, c2). A lock is never deleted here."""
    live = []
    for root in roots:
        for run in sorted(p for p in root.iterdir() if p.is_dir()) if root.is_dir() else []:
            try:
                status.require_known(run)
            except BenchError:
                continue
            s = status.build(run)
            if s.liveness == "alive":
                live.append(f"{run} alive")
            elif s.liveness == "stalled":
                live.append(f"{run} stalled (lock {run / '.lock'}, heartbeat {s.lock_age_s} s old)")
    if live:
        raise BenchError("HB-GRD-005", f"model calls refused while a run is live; scanned "
                                       f"{', '.join(map(str, roots))}; {'; '.join(live)}")


@contextmanager
def judge_pass(cells_root: Path, grading_id: str, credential_names: tuple[str, ...],
               roots: tuple[Path, ...]) -> Iterator[None]:
    """One pass's hold on `<cells root>/gateway/<grading_id>/`: refuse while any run under `roots` is live
    (HB-GRD-005, `refuse_if_live`, before the first spawn: every caller that spawns a judge gets it), refuse a cells
    root below an instruction file (HB-PRE-002, `workspace.check_cells_root`), take the pass `.lock`, and sweep
    leftover credential copies at the start and the end of the pass (section 8.2; T-GW-10, T-GW-19, T-GW-26b)."""
    refuse_if_live(roots)
    workspace.check_cells_root(cells_root)
    lock = oslock.RunLock.acquire(cells_root / "gateway" / grading_id / ".lock")
    try:
        sweep_credentials(cells_root, credential_names)
        yield
    finally:
        lock.release()
        sweep_credentials(cells_root, credential_names, own=grading_id)


def copilot_answer(record: Path) -> str | None:
    """The content of the record's last non-empty `assistant.message` row: Copilot's print-mode stdout puts CLI
    banners before the answer (spike finding 4), so the record, not stdout, is the answer. None when there is none."""
    text = None
    for line in record.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            row = json.loads(line)
        except ValueError:
            continue
        if isinstance(row, dict) and row.get("type") == "assistant.message":
            content = (row.get("data") or {}).get("content")
            text = content if isinstance(content, str) and content.strip() else text
    return text


def final_text(reply: Reply) -> str | None:
    """The answer's text (section 8.3 step 3): Claude's stdout JSON `result`; Copilot's record (`copilot_answer`).
    Only the text: the served models, tool events and session id come from the record. Another harness reads None
    (HB-GW-002, fail-closed)."""
    if reply.harness == "copilot":
        return copilot_answer(reply.record)
    try:
        out = json.loads(reply.stdout) if reply.harness == "claude-code" else None
    except ValueError:
        return None
    text = out.get("result") if isinstance(out, dict) else None
    return text if isinstance(text, str) else None
