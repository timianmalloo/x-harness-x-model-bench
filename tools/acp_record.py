"""Record a full ACP stdio stream: both pipes, every line, in order, with direction and time.

Phase-2 W1-ACP (a); `docs/proof/phase1.md` residual 9 (the D5/D7 fixtures were schema shapes, not recordings).
The driver (`src/harness_bench/driver.py`) and the profiles are not changed: this tool spawns the adapter
itself and sits between the client and the adapter.

Usage:
  python tools/acp_record.py record --out REC.jsonl -- <adapter argv...>
      The stdio tee. The client talks to this process exactly as it would to the adapter.
  python tools/acp_record.py turn --harness claude-code|codex|copilot --model M --out REC.jsonl
                                  [--task X1] [--tools-dir D] [--cells-root D] [--budget S] [--handshake S]
      One real cell turn through `record`: the bench's own profile, pinned build, working copy and driver.
      `--harness` accepts every harness in `harness_bench.profiles.HARNESSES`. The argv comes from the
      profile's own `command:` template (`Profile.argv`, the same call the engine makes); when the loaded
      profile's `set_model` is true (Copilot today), `model=<--model>` is passed to `driver.run_turn` exactly
      as `engine.py`'s `_attempt` does, so `session/set_model` is sent right after `session/new`.
      Writes REC.meta.json (versions and the turn result, no paths) and REC.stderr.log (never committed).
  python tools/acp_record.py scrub RAW.jsonl OUT.jsonl [--replace LITERAL=<PLACEHOLDER>]... [--forbid WORD]...
      The scrub before commit (see `scrub`).

Transparency. Bytes pass through unchanged in both directions. The adapter's stderr is inherited, so it
reaches the client's stderr unchanged; it is not recorded. A complete line is recorded before the chunk
that ends it is forwarded, so a reply is never recorded before the request that caused it. The recording
never changes what passes: when a cap is hit, recording stops with one `truncated` record and the bytes
keep flowing.

Bounds (all stated, all enforced):
  MAX_LINES       200,000 line records per recording, then `truncated` (reason "max_lines").
  MAX_BYTES       64 MiB of recorded payload per recording, then `truncated` (reason "max_bytes").
  MAX_LINE_BYTES  4 MiB per record: a longer line is recorded in fragments (`nl: false` until its last one),
                  so memory holds at most one fragment plus one chunk. It is above the driver's 1 MiB line
                  limit, so an oversized adapter line still reaches the driver whole and fails there.

Recording format (`acp-recording/1`, JSON Lines):
  {"kind": "header", "format", "argv", "cwd", "started_utc", "caps", "stderr"}   written once, first
  {"kind": "line", "seq", "t", "dir": "to_agent"|"to_client", "text"|"b64", "nl"}
  {"kind": "eof", "seq", "t", "dir"}    {"kind": "exit", "seq", "t", "code"}    {"kind": "truncated", ..., "reason"}
  `seq` counts from 1 across both directions; `t` is seconds since the start (monotonic). `text` is the line
  without its "\\n" (a "\\r" is kept); a line that is not UTF-8 is `b64`. `stream_bytes` rebuilds a direction.
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import re
import subprocess
import sys
import threading
import time
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FORMAT = "acp-recording/1"
MAX_LINES = 200_000
MAX_BYTES = 64 << 20
MAX_LINE_BYTES = 4 << 20
CHUNK = 65536
DIRECTIONS = ("to_agent", "to_client")
EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")


class Recording:
    """The record writer: one lock, one sequence across both directions, and the caps."""

    def __init__(self, write: Callable[[str], None], max_lines: int = MAX_LINES, max_bytes: int = MAX_BYTES,
                 max_line_bytes: int = MAX_LINE_BYTES) -> None:
        self.write, self.max_lines, self.max_bytes, self.max_line_bytes = write, max_lines, max_bytes, max_line_bytes
        self.lock = threading.Lock()
        self.start = time.monotonic()
        self.seq = self.lines = self.bytes = 0
        self.stopped = False  # truncated or closed: nothing more is written

    def header(self, argv: list[str], cwd: str) -> None:
        self.write(json.dumps({"kind": "header", "format": FORMAT, "argv": argv, "cwd": cwd,
                               "started_utc": datetime.now(UTC).isoformat(timespec="milliseconds"),
                               "caps": {"max_lines": self.max_lines, "max_bytes": self.max_bytes,
                                        "max_line_bytes": self.max_line_bytes},
                               "stderr": "inherited by the client, not recorded"}))

    def _add(self, kind: str, **fields) -> None:  # the caller holds the lock
        self.seq += 1
        self.write(json.dumps({"kind": kind, "seq": self.seq, "t": round(time.monotonic() - self.start, 6), **fields}))

    def line(self, direction: str, data: bytes, nl: bool) -> None:
        with self.lock:
            if self.stopped:
                return
            reason = ("max_lines" if self.lines >= self.max_lines else
                      "max_bytes" if self.bytes + len(data) > self.max_bytes else None)
            if reason:
                self._add("truncated", reason=reason)
                self.stopped = True
                return
            self.lines, self.bytes = self.lines + 1, self.bytes + len(data)
            try:
                payload = {"text": data.decode("utf-8")}
            except UnicodeDecodeError:
                payload = {"b64": base64.b64encode(data).decode("ascii")}
            self._add("line", dir=direction, **payload, nl=nl)

    def event(self, kind: str, **fields) -> None:
        with self.lock:
            if not self.stopped:
                self._add(kind, **fields)

    def close(self) -> None:
        with self.lock:
            self.stopped = True


class Tee:
    """One direction: `feed` records every line the chunk completes, then returns the chunk unchanged."""

    def __init__(self, recording: Recording, direction: str) -> None:
        self.recording, self.direction, self.pending = recording, direction, b""

    def _fragments(self, data: bytes, nl: bool) -> None:
        cap = self.recording.max_line_bytes
        while len(data) > cap:
            self.recording.line(self.direction, data[:cap], False)
            data = data[cap:]
        self.recording.line(self.direction, data, nl)

    def feed(self, chunk: bytes) -> bytes:
        *complete, self.pending = (self.pending + chunk).split(b"\n")
        for line in complete:
            self._fragments(line, True)
        cap = self.recording.max_line_bytes
        while len(self.pending) > cap:  # bounded: an unterminated line is recorded as it grows
            self.recording.line(self.direction, self.pending[:cap], False)
            self.pending = self.pending[cap:]
        return chunk

    def close(self) -> None:
        if self.pending:
            self._fragments(self.pending, False)
            self.pending = b""
        self.recording.event("eof", dir=self.direction)


def stream_bytes(records: list[dict], direction: str) -> bytes:
    """The exact bytes one direction carried, rebuilt from its line records."""
    out = bytearray()
    for r in records:
        if r.get("kind") == "line" and r["dir"] == direction:
            out += r["text"].encode("utf-8") if "text" in r else base64.b64decode(r["b64"])
            out += b"\n" if r["nl"] else b""
    return bytes(out)


def _pump(read: Callable[[int], bytes], write: Callable[[bytes], None], tee: Tee, done: Callable[[], None]) -> None:
    """Copy one pipe until EOF. A dead receiver stops forwarding, never recording or reading."""
    forwarding = True
    while True:
        try:
            chunk = read(CHUNK)
        except (OSError, ValueError):  # a broken pipe reads as EOF
            chunk = b""
        if not chunk:
            break
        tee.feed(chunk)
        if forwarding:
            try:
                write(chunk)
            except (OSError, ValueError):
                forwarding = False
    tee.close()
    try:
        done()
    except (OSError, ValueError):
        pass


def record(out: Path, argv: list[str]) -> int:
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8", newline="\n") as f:
        def write(text: str) -> None:
            f.write(text + "\n")
            f.flush()

        recording = Recording(write)
        recording.header(argv, os.getcwd())
        child = subprocess.Popen(argv, stdin=subprocess.PIPE, stdout=subprocess.PIPE)  # stderr: inherited
        stdin, stdout = sys.stdin.buffer, sys.stdout.buffer

        def to_agent(data: bytes) -> None:
            child.stdin.write(data)
            child.stdin.flush()

        def to_client(data: bytes) -> None:
            stdout.write(data)
            stdout.flush()

        threading.Thread(target=_pump, args=(stdin.read1, to_agent, Tee(recording, "to_agent"), child.stdin.close),
                         daemon=True).start()
        _pump(child.stdout.read1, to_client, Tee(recording, "to_client"), stdout.close)
        code = child.wait()
        recording.event("exit", code=code)
        recording.close()
    os._exit(code)  # the to_agent thread may still be blocked reading the client's stdin


def scrub(raw: Path, out: Path, replacements: dict[str, str], forbid: list[str]) -> dict:
    """Replace each literal (as written, with forward slashes, and JSON-escaped; any case) by its
    placeholder in every string of every record, and every e-mail address by <EMAIL>. Refuse, writing
    nothing, if a forbidden word is left anywhere. The header records the rule, never the literals."""
    rules = []
    for literal, placeholder in sorted(replacements.items(), key=lambda kv: -len(kv[0])):
        forms = {literal, literal.replace("\\", "/"), json.dumps(literal)[1:-1]}
        for form in sorted(forms, key=len, reverse=True):
            rules.append((re.compile(re.escape(form), re.IGNORECASE), placeholder))

    def clean(value):
        if isinstance(value, str):
            for pattern, placeholder in rules:
                value = pattern.sub(placeholder, value)
            return EMAIL.sub("<EMAIL>", value)
        if isinstance(value, list):
            return [clean(v) for v in value]
        if isinstance(value, dict):
            return {k: clean(v) for k, v in value.items()}
        return value

    records = [clean(json.loads(line)) for line in raw.read_text(encoding="utf-8").splitlines() if line.strip()]
    joined_texts = _scrub_streams(records, clean)
    for record in records:
        _scrub_plan_labels(record)
    rule = {"placeholders": sorted(set(replacements.values())), "email": "<EMAIL>", "forms": "as written, forward "
            "slashes, JSON-escaped; case-insensitive", "streams": "also on the joined text of each streamed message "
            "(chunks per messageId, terminal output per toolCallId); a changed stream is re-serialised with its "
            "whole scrubbed text in its first chunk and the rest empty", "plans": "every label, plan and tier value "
            "under authStatus in _auth/status_update -> <PLAN> (data minimisation)", "forbidden_words_checked": len(forbid),
            "scrubbed_utc": datetime.now(UTC).isoformat(timespec="seconds")}
    if records and records[0].get("kind") == "header":
        records[0]["scrub"] = rule
    body = "".join(json.dumps(r) + "\n" for r in records)
    left = [w for w in forbid if w and any(w.lower() in text.lower() for text in (body, *joined_texts))]
    if left:
        raise ValueError(f"{len(left)} forbidden word(s) left after the scrub; nothing written")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(body, encoding="utf-8", newline="\n")
    return rule


def _streamed_text(record: dict):
    """(stream key, message, the dict holding the text, its field) for a streamed session/update line, else None.
    Adapters stream text a token per line, so a literal can be split across lines (codex X1 capture)."""
    if record.get("kind") != "line" or "text" not in record:
        return None
    try:
        msg = json.loads(record["text"])
    except ValueError:
        return None
    update = (msg.get("params") or {}).get("update") if isinstance(msg, dict) else None
    if not isinstance(update, dict):
        return None
    kind, content = update.get("sessionUpdate"), update.get("content")
    if kind in ("agent_message_chunk", "agent_thought_chunk") and isinstance(content, dict) and isinstance(content.get("text"), str):
        return (record["dir"], kind, update.get("messageId")), msg, content, "text"
    delta = (update.get("_meta") or {}).get("terminal_output_delta")
    if isinstance(delta, dict) and isinstance(delta.get("data"), str):
        return (record["dir"], "terminal", update.get("toolCallId")), msg, delta, "data"
    return None


PLAN_KEYS = ("label", "plan", "tier")


def _scrub_plan_labels(record: dict) -> None:
    """The account's plan or tier label in an `_auth/status_update` becomes <PLAN>: no test needs it."""
    if record.get("kind") != "line" or "_auth/status_update" not in record.get("text", ""):
        return
    try:
        msg = json.loads(record["text"])
    except ValueError:
        return
    status = (msg.get("params") or {}).get("authStatus") if isinstance(msg, dict) else None
    if not isinstance(status, dict) or msg.get("method") != "_auth/status_update":
        return

    def walk(node: dict) -> None:
        for key, value in node.items():
            if key in PLAN_KEYS and isinstance(value, str):
                node[key] = "<PLAN>"
            elif isinstance(value, dict):
                walk(value)

    walk(status)
    record["text"] = json.dumps(msg, ensure_ascii=False, separators=(",", ":"))


def _scrub_streams(records: list[dict], clean) -> list[str]:
    """Scrub each streamed message as one joined text; returns the joined texts for the forbidden-word check."""
    streams: dict[tuple, list] = {}
    for record in records:
        found = _streamed_text(record)
        if found:
            key, *part = found
            streams.setdefault(key, []).append((record, *part))
    joined_texts = []
    for parts in streams.values():
        joined = "".join(holder[field] for _, _, holder, field in parts)
        cleaned = clean(joined)
        if cleaned != joined:
            for i, (record, msg, holder, field) in enumerate(parts):
                holder[field] = cleaned if i == 0 else ""
                record["text"] = json.dumps(msg, ensure_ascii=False, separators=(",", ":"))
        joined_texts.append(cleaned)
    return joined_texts


def turn(args: argparse.Namespace) -> int:
    """One real cell turn through `record`, built the way the bench builds a pack-off cell."""
    # the plan's own reading of prompt.md (US-10), not a copy of it
    from harness_bench import driver, procs, profiles, tools, workspace
    from harness_bench.plan import _prompt

    task_dir, cells_root, out = ROOT / "tasks" / args.task, Path(args.cells_root), Path(args.out).resolve()
    out.parent.mkdir(parents=True, exist_ok=True)  # <out>.stderr.log is opened before `record` would create it
    workspace.check_cells_root(cells_root)  # HB-PRE-002: no instruction file above the cell
    cell_dir = cells_root / f"acp-capture-{args.harness}-{datetime.now(UTC):%Y%m%dT%H%M%SZ}"
    home, ws = cell_dir / "home", cell_dir / "ws"
    workspace.cell_working_copy(workspace.task_source(task_dir, "capture", cell_dir / "source"), ws)
    profile = profiles.load(ROOT, args.harness)
    build = tools.resolve(Path(args.tools_dir))[args.harness]
    argv = profile.argv(build, args.model)  # the same call the engine's ProfileLauncher.argv_env makes
    env = profile.cell_env(dict(os.environ), home, build, args.model, "")
    prompt = _prompt(task_dir)
    profile.seed_home(home, args.model)
    try:
        with out.with_suffix(".stderr.log").open("wb") as err:
            cell = procs.spawn([sys.executable, str(Path(__file__).resolve()), "record", "--out", str(out), "--", *argv],
                               cwd=str(ws), env=env, stderr=err)
            budget = threading.Timer(args.budget, lambda: cell.terminate_and_confirm(timeout=30))
            budget.start()
            try:
                result = driver.run_turn(cell, cwd=ws, prompt=prompt["prompt"], mode=profile.mode,
                                         handshake_timeout=args.handshake, before_send=lambda sid: None,
                                         model=args.model if profile.set_model else None)  # engine._attempt's own call
                cell.proc.stdin.close()  # a clean end: the adapter sees EOF, so the recording ends with eof and exit
                try:
                    cell.proc.wait(timeout=15)
                except subprocess.TimeoutExpired:
                    pass
            finally:
                budget.cancel()
                cell.terminate_and_confirm(timeout=30)
                cell.close()
    finally:
        profile.clean_home(home)  # the credential copy never outlives the turn
    meta = {"format": FORMAT, "harness": args.harness, "model": args.model, "task": args.task, "mode": profile.mode,
            "prompt_sha256": prompt["prompt_sha256"], "build": build.record(),
            "captured_utc": datetime.now(UTC).isoformat(timespec="seconds"),
            "result": {"stop_reason": result.stop_reason, "cause": result.cause.code if result.cause else None,
                       "session_id": result.session_id, "updates": result.updates,
                       "permission_requests": result.permission_requests, "prompt_sent": result.prompt_sent,
                       "usage_reported": result.usage is not None}}
    out.with_suffix(".meta.json").write_text(json.dumps(meta, indent=1) + "\n", encoding="utf-8")
    print(json.dumps({**meta, "recording": str(out), "cell_dir": str(cell_dir)}, indent=1))
    return 0 if result.cause is None and result.stop_reason == "end_turn" else 1


def main(argv: list[str]) -> int:
    if argv[:1] == ["record"]:  # parsed by hand: everything after "--" is the adapter's argv, untouched
        if len(argv) < 5 or argv[1] != "--out" or argv[3] != "--":
            print("usage: acp_record.py record --out REC.jsonl -- <adapter argv...>", file=sys.stderr)
            return 2
        return record(Path(argv[2]), argv[4:])
    # lazy: keep `record`'s hot path free of the harness_bench import
    from harness_bench.profiles import HARNESSES

    p = argparse.ArgumentParser(prog="acp_record.py", description=__doc__.splitlines()[0])
    sub = p.add_subparsers(dest="command", required=True)
    t = sub.add_parser("turn", help="one real cell turn through the recorder")
    t.add_argument("--harness", required=True, choices=HARNESSES)
    t.add_argument("--model", required=True)
    t.add_argument("--out", required=True)
    t.add_argument("--task", default="X1")
    t.add_argument("--tools-dir", default=str(ROOT / ".tools" / "harness"))
    t.add_argument("--cells-root", default=str(ROOT.parent / "bench-cells"))
    t.add_argument("--budget", type=float, default=600.0, help="seconds before the cell is ended (default 600)")
    t.add_argument("--handshake", type=float, default=60.0, help="handshake deadline in seconds (the plan default)")
    s = sub.add_parser("scrub", help="scrub a raw recording before commit")
    s.add_argument("raw")
    s.add_argument("out")
    s.add_argument("--replace", action="append", default=[], metavar="LITERAL=<PLACEHOLDER>")
    s.add_argument("--forbid", action="append", default=[], metavar="WORD")
    args = p.parse_args(argv)
    if args.command == "turn":
        return turn(args)
    raw = Path(args.raw)
    header = json.loads(raw.read_text(encoding="utf-8").split("\n", 1)[0])
    replacements = {}
    if header.get("kind") == "header":  # the cell's working copy, and the cell folder that holds its home
        replacements = {header["cwd"]: "<CWD>", str(Path(header["cwd"]).parent): "<CELL>"}
    if os.environ.get("USERPROFILE"):
        replacements[os.environ["USERPROFILE"]] = "<USERPROFILE>"
    replacements.update(dict(r.split("=", 1) for r in args.replace))
    forbid = [*args.forbid, *([os.environ["USERNAME"]] if os.environ.get("USERNAME") else [])]
    print(json.dumps(scrub(raw, Path(args.out), replacements, forbid), indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
