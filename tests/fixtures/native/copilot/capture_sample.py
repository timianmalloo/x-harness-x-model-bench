"""Capture one pack-off and one pack-on X1 Copilot turn for the reader samples (design phase2-copilot-profile, section 11).

Run by the Leader only (a model-harness turn is a Leader seam). It uses the bench's own code for everything
a cell does (working copies, pack install, cell environment, Job Object, bounded ACP line reader) and adds
only the ACP `session/set_model` the design specifies. Nothing here is imported by the bench or collected
by pytest. Output goes under --out (outside the repository); the raw records there are unscrubbed.

    uv run python tests/fixtures/native/copilot/capture_sample.py --exe <copilot.exe> --model gpt-6-sol \
        --pack-source C:/projects/ai-forward --out C:/Projects/bench-capture/run [--dry-run]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import queue
import re
import subprocess
import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "src"))

from harness_bench import (
    driver,
    gitsafe,
    plan,
    procs,
    profiles,
    workspace,
)

MARKERS = ("AI-Forward Pack", "Agent Knowledge Pack", "Rigor Protocol")
EXTRA_DROP = ("GH_TOKEN", "GITHUB_TOKEN", "GH_HOST")
HANDSHAKE_S, TURN_S, GRACE_S = 60.0, 300.0, 10.0
REFUSAL_MODEL = "harness-bench-no-such-model"
TOKEN_SHAPE = re.compile(rb"gh[opsu]_[A-Za-z0-9]{20,}")


def cell_env(home: Path) -> dict[str, str]:
    """A cell's environment as profiles.Profile.cell_env builds it, plus the Copilot profile's env (design 4.1)."""
    import os

    env = {k: v for k, v in os.environ.items()
           if k.upper() not in profiles.DROP_EXACT and k.upper() not in EXTRA_DROP and not k.upper().startswith(profiles.DROP_PREFIXES)}
    env.update(profiles.CELL_ENV)
    env["COPILOT_HOME"] = str(home)
    env["COPILOT_AUTO_UPDATE"] = "false"
    return env


class Client:
    """A minimal ACP client over a Job-Object process: every line both ways is kept in `transcript`."""

    def __init__(self, cell: procs.CellProcess, transcript: Path) -> None:
        self.cell, self.inbox, self.seq = cell, queue.Queue(), 0
        self.log = transcript.open("w", encoding="utf-8")
        self.permission_requests = self.updates = 0
        threading.Thread(target=self._read, daemon=True).start()

    def _read(self) -> None:
        parser = driver.LineParser()
        try:
            while chunk := self.cell.proc.stdout.read1(65536):
                for msg in parser.feed(chunk):
                    self.inbox.put(msg)
        except (driver.ProtocolError, OSError, ValueError) as exc:
            self.inbox.put({"_eof": str(exc)})
            return
        self.inbox.put({"_eof": "eof"})

    def _send(self, obj: dict) -> None:
        self.log.write(json.dumps({"dir": "out", "msg": obj}) + "\n")
        self.cell.proc.stdin.write(json.dumps(obj).encode("utf-8") + b"\n")
        self.cell.proc.stdin.flush()

    def rpc(self, method: str, params: dict, seconds: float) -> dict:
        """{"result": ...} or {"error": ...}; {"timeout": method} or {"eof": ...} on those."""
        self.seq += 1
        rid, deadline = self.seq, time.monotonic() + seconds
        self._send({"jsonrpc": "2.0", "id": rid, "method": method, "params": params})
        while True:
            try:
                msg = self.inbox.get(timeout=max(deadline - time.monotonic(), 0.01))
            except queue.Empty:
                return {"timeout": method}
            if "_eof" in msg:
                return {"eof": msg["_eof"]}
            self.log.write(json.dumps({"dir": "in", "msg": msg}) + "\n")
            if "method" in msg and "id" in msg:
                if msg["method"] == "session/request_permission":
                    self.permission_requests += 1
                    self._send({"jsonrpc": "2.0", "id": msg["id"], "result": {"outcome": {"outcome": "cancelled"}}})
                else:
                    self._send({"jsonrpc": "2.0", "id": msg["id"], "error": {"code": -32601, "message": "not supported by harness-bench"}})
            elif "method" in msg:
                self.updates += msg["method"] == "session/update"
            elif msg.get("id") == rid:
                return {k: msg[k] for k in ("result", "error") if k in msg}


def end(cell: procs.CellProcess) -> dict:
    try:
        cell.proc.stdin.close()
    except OSError:
        pass
    try:
        cell.wait(timeout=GRACE_S)
        graceful = True
    except subprocess.TimeoutExpired:
        graceful = False
    confirmed = cell.terminate_and_confirm(30)
    cell.close()
    return {"graceful_exit": graceful, "kill_confirmed": confirmed}


def turn(exe: Path, model: str, ws: Path, home: Path, prompt: str | None, out: Path, set_to: str) -> dict:
    argv = [str(exe), "--acp", "--model", model, "--allow-tool", "shell", "--allow-tool", "write"]
    cell = procs.spawn(argv, cwd=str(ws), env=cell_env(home), stderr=subprocess.DEVNULL)
    c = Client(cell, out / "acp-transcript.jsonl")
    info: dict = {"argv_tail": argv[1:]}
    try:
        init = c.rpc("initialize", {"protocolVersion": driver.PROTOCOL_VERSION, "clientCapabilities": {},
                                    "clientInfo": driver.CLIENT_INFO}, HANDSHAKE_S)
        r = init.get("result") or {}
        info["initialize"] = {"agentInfo": r.get("agentInfo"), "protocolVersion": r.get("protocolVersion"),
                              "authMethods": [m.get("id") for m in r.get("authMethods") or [] if isinstance(m, dict)],
                              "outcome": sorted(init)}
        new = c.rpc("session/new", {"cwd": str(ws), "mcpServers": []}, HANDSHAKE_S)
        created = new.get("result") or {}
        models = created.get("models") if isinstance(created.get("models"), dict) else {}
        info["session_new"] = {"outcome": sorted(new), "sessionId": created.get("sessionId"),
                               "advertised_currentModelId": models.get("currentModelId"),
                               "available_model_ids": [m.get("modelId") for m in models.get("availableModels") or [] if isinstance(m, dict)],
                               "modes": created.get("modes")}
        sid = created.get("sessionId")
        if not sid:
            info["stopped"] = "no session id"
            return info
        setm = c.rpc("session/set_model", {"sessionId": sid, "modelId": set_to}, HANDSHAKE_S)
        info["set_model"] = {"modelId": set_to, "response": setm}
        if prompt is None or "result" not in setm:
            info["stopped"] = "no prompt sent (refusal probe, or the setter did not succeed)"
            return info
        started = time.monotonic()
        done = c.rpc("session/prompt", {"sessionId": sid, "prompt": [{"type": "text", "text": prompt}]}, TURN_S)
        res = done.get("result") or {}
        info["prompt"] = {"outcome": sorted(done), "stopReason": res.get("stopReason"), "seconds": round(time.monotonic() - started, 1),
                          "usage": res.get("usage"), "meta_keys": sorted((res.get("_meta") or {}).keys()),
                          "meta_quota": (res.get("_meta") or {}).get("quota"), "error": done.get("error")}
        return info
    finally:
        info["permission_requests"], info["updates"] = c.permission_requests, c.updates
        info["process"] = end(cell)
        c.log.close()


def instruction_list(exe: Path, ws: Path, home: Path) -> dict:
    r = procs.run([str(exe), "instruction", "list", "--json"], cwd=str(ws), env=cell_env(home), timeout=120)
    try:
        return {"returncode": r.returncode, "json": json.loads(r.stdout)}
    except ValueError:
        return {"returncode": r.returncode, "stdout_head": r.stdout[:2000], "stderr_head": r.stderr[:2000]}


def sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def events_readings(home: Path, sid: str) -> dict:
    path = home / "session-state" / sid / "events.jsonl"
    if not path.is_file():
        return {"present": False, "session_state_files": sorted(p.name for p in (home / "session-state" / sid).glob("*"))}
    counts: dict[str, int] = {}
    out: dict = {"present": True, "model_changes": [], "tool_names": [], "errors": [], "markers": {}}
    for raw in path.read_bytes().splitlines():
        try:
            e = json.loads(raw)
        except ValueError:
            continue
        if not isinstance(e, dict):
            continue
        t, d = str(e.get("type")), e.get("data") if isinstance(e.get("data"), dict) else {}
        counts[t] = counts.get(t, 0) + 1
        if t == "session.start":
            out["session_start"] = {k: d.get(k) for k in ("sessionId", "copilotVersion", "selectedModel", "version", "producer")}
        elif t == "session.model_change":
            out["model_changes"].append({k: d.get(k) for k in ("previousModel", "newModel", "source")})
        elif t == "tool.execution_start":
            out["tool_names"].append(d.get("toolName"))
        elif t == "session.error":
            out["errors"].append({"errorType": d.get("errorType")})
        elif t == "user.message" and "agentId" not in e and "first_user_content_sha256" not in out:
            out["first_user_content_sha256"] = sha(d["content"]) if isinstance(d.get("content"), str) else None
        for field in ("content", "transformedContent"):
            if t in ("system.message", "user.message") and isinstance(d.get(field), str):
                found = [m for m in MARKERS if m in d[field]]
                out["markers"][f"{t}.{field}"] = sorted(set(out["markers"].get(f"{t}.{field}", [])) | set(found))
    out["event_counts"] = dict(sorted(counts.items()))
    return out


def home_facts(home: Path) -> dict:
    files = sorted((p.relative_to(home).as_posix(), p.stat().st_size) for p in home.rglob("*") if p.is_file())
    cfg = home / "config.json"
    try:
        config_keys = sorted(json.loads(cfg.read_text(encoding="utf-8")).keys()) if cfg.is_file() else None
    except ValueError:
        config_keys = "unparseable"
    shaped = sum(len(TOKEN_SHAPE.findall(home.joinpath(f).read_bytes())) for f, size in files if size < 64 << 20)
    return {"files": files, "config_keys": config_keys, "token_shaped_strings": shaped}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--exe", type=Path, required=True)
    ap.add_argument("--model", required=True)
    ap.add_argument("--pack-source", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    out = a.out.resolve()
    if out.exists():
        raise SystemExit(f"{out} exists; a capture is written once")
    task_dir = ROOT / "tasks" / "X1"
    frozen = plan._prompt(task_dir)  # the prompt exactly as a plan freezes it (US-10)
    cells = out / "cells"
    cells.mkdir(parents=True)
    workspace.check_cells_root(cells)  # HB-PRE-002
    version = plan.task_version_hash(task_dir)
    source = workspace.task_source(task_dir, version, out / "sources")
    commit = gitsafe.git(["rev-parse", "HEAD"], cwd=a.pack_source, timeout=60).stdout.strip()
    summary: dict = {"schema": "copilot-capture/1", "captured": time.strftime("%Y-%m-%d"), "model": a.model,
                     "exe_sha256": hashlib.sha256(a.exe.read_bytes()).hexdigest() if a.exe.is_file() else None,
                     "task": "X1", "task_version": version, "prompt_sha256": frozen["prompt_sha256"],
                     "pack": {"source_head": commit}, "markers": list(MARKERS), "arms": {}}
    for arm in ("off", "on"):
        ws, home = workspace.cell_working_copy(source, cells / arm / "ws"), cells / arm / "home"
        home.mkdir(parents=True)
        entry: dict = {}
        if arm == "on":
            pack_dir = workspace.pack_checkout(a.pack_source, commit, out / "pack")
            entry["pack_revision"] = workspace.pack_revision(pack_dir)
            entry["pack_manifest"] = workspace.install_pack(pack_dir, ws, project="X1", timeout=600)
        summary["arms"][arm] = entry
        if a.dry_run:
            continue
        entry["instruction_list"] = instruction_list(a.exe, ws, home)
        entry["turn"] = turn(a.exe, a.model, ws, home, frozen["prompt"], cells / arm, a.model)
        sid = entry["turn"].get("session_new", {}).get("sessionId") or ""
        entry["events"] = events_readings(home, sid) if sid else {"present": False}
        entry["home"] = home_facts(home)
    if not a.dry_run:
        version_home = out / "version-home"
        version_home.mkdir()
        summary["exe_version"] = procs.run([str(a.exe), "--version"], cwd=str(out), env=cell_env(version_home), timeout=60).stdout.strip()
        ws, home = workspace.cell_working_copy(source, cells / "refusal" / "ws"), cells / "refusal" / "home"
        home.mkdir(parents=True)
        summary["refusal_probe"] = turn(a.exe, a.model, ws, home, None, cells / "refusal", REFUSAL_MODEL)
    (out / "summary.json").write_text(json.dumps(summary, indent=1, default=str), encoding="utf-8")
    print(f"wrote {out / 'summary.json'}{' (dry run: no Copilot process started)' if a.dry_run else ''}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
