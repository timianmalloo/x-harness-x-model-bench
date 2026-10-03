"""Spike E4 (R-E6, DR-E4, EV-4): does the ACP cell driver's channel support a SECOND
`session/prompt` in the same session, after turn 1 ends with stopReason end_turn?

The production driver (src/harness_bench/driver.py:run_turn) opens a session, sends exactly one
`session/prompt`, and returns. This script reuses the same primitives (driver._Channel,
profiles.Profile, tools.resolve, procs.spawn) but keeps the channel and process alive across TWO
`session/prompt` RPCs on the same sessionId, with no handshake repeated and stdin never closed in
between -- this is the minimal, disposable probe of whether the ACP session itself (not the
engine's one-shot run_turn) supports a second turn.

Usage (from the repo root, this worktree's own uv env):
  uv run --no-sync python spikes/e4_two_turns.py --harness claude-code --model claude-opus-5-5
  uv run --no-sync python spikes/e4_two_turns.py --harness codex --model gpt-6-sol
  uv run --no-sync python spikes/e4_two_turns.py --harness copilot --model gpt-6-sol

Writes <cells-root>/<label>.summary.json and prints it to stdout (ASCII-escaped, OUT-A).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import threading
import time
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from harness_bench import driver, procs, profiles, tools  # noqa: E402

MODELS = {"claude-code": "claude-opus-5-5", "codex": "gpt-6-sol", "copilot": "gpt-6-sol"}
PROMPT1 = "Create a file named a.txt in the current directory containing exactly the single character 1 (no quotes, no extra lines). Then stop."
PROMPT2 = "Now change a.txt so it contains exactly the single character 2 (no quotes), and add a new file named b.txt containing exactly the text done (no quotes). Then stop."


def tree_snapshot(ws: Path) -> dict:
    out = {}
    for p in sorted(ws.rglob("*")):
        if p.is_file() and ".git" not in p.parts:
            out[str(p.relative_to(ws)).replace("\\", "/")] = hashlib.sha256(p.read_bytes()).hexdigest()
    return out


def _drain(stream, cap: int = 1 << 20) -> bytearray:
    buf = bytearray()

    def _read():
        try:
            while True:
                chunk = stream.read(4096)
                if not chunk:
                    break
                if len(buf) < cap:
                    buf.extend(chunk)
        except (OSError, ValueError):
            pass

    threading.Thread(target=_read, daemon=True).start()
    return buf


def run(harness: str, model: str, cells_root: Path, handshake_timeout: float, prompt_timeout: float) -> dict:
    profile = profiles.load(ROOT, harness)
    build = tools.resolve(ROOT / ".tools" / "harness")[harness]
    argv = profile.argv(build, model)
    label = f"e4-{harness}-{datetime.now(UTC):%Y%m%dT%H%M%SZ}"
    cell_dir = cells_root / label
    home, ws = cell_dir / "home", cell_dir / "ws"
    ws.mkdir(parents=True)
    profile.seed_home(home, model)
    env = profile.cell_env(dict(os.environ), home, build, model, "")
    out: dict = {"format": "e4-two-turns/1", "harness": harness, "model": model, "label": label, "argv": argv}
    result = driver.TurnResult()
    cp = None
    stderr_tail = bytearray()
    try:
        cp = procs.spawn(argv, cwd=str(ws), env=env, stderr=subprocess.PIPE)
        stderr_tail = _drain(cp.proc.stderr)
        ch = driver._Channel(cp, result)
        deadline = time.monotonic() + handshake_timeout
        init = ch.rpc("initialize", {"protocolVersion": driver.PROTOCOL_VERSION, "clientCapabilities": {},
                                      "clientInfo": driver.CLIENT_INFO}, deadline)
        out["agent_version"] = (init.get("agentInfo") or {}).get("version")
        created = ch.rpc("session/new", {"cwd": str(ws), "mcpServers": []}, deadline)
        session_id = created.get("sessionId")
        out["session_id"] = session_id
        if profile.set_model:
            ch.rpc("session/set_model", {"sessionId": session_id, "modelId": model}, deadline)
        if profile.mode:
            ch.rpc("session/set_mode", {"sessionId": session_id, "modeId": profile.mode}, deadline)

        t0 = time.monotonic()
        ch.turn_start = t0
        done1 = ch.rpc("session/prompt", {"sessionId": session_id, "prompt": [{"type": "text", "text": PROMPT1}]},
                       t0 + prompt_timeout)
        out["turn1"] = {"stop_reason": done1.get("stopReason"), "seconds": round(time.monotonic() - t0, 1),
                        "usage": done1.get("usage"), "meta": done1.get("_meta")}
        out["snapshot_after_turn1"] = tree_snapshot(ws)

        t1 = time.monotonic()
        ch.turn_start = t1
        done2 = ch.rpc("session/prompt", {"sessionId": session_id, "prompt": [{"type": "text", "text": PROMPT2}]},
                       t1 + prompt_timeout)
        out["turn2"] = {"stop_reason": done2.get("stopReason"), "seconds": round(time.monotonic() - t1, 1),
                        "usage": done2.get("usage"), "meta": done2.get("_meta")}
        out["snapshot_after_turn2"] = tree_snapshot(ws)
        out["second_prompt_same_session"] = True
        out["session_id_unchanged"] = True  # no second session/new was ever sent
    except Exception as exc:  # noqa: BLE001 -- a refusal/crash is the result, not a bug in the probe
        out["second_prompt_same_session"] = False
        out["error"] = {"type": type(exc).__name__, "detail": str(exc)[:1000]}
    finally:
        if cp is not None:
            try:
                cp.proc.stdin.close()
            except (OSError, ValueError):
                pass
            try:
                cp.proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                pass
            try:
                cp.terminate_and_confirm(timeout=15)
            except Exception:
                pass
            time.sleep(0.2)  # let the drain thread catch the last chunk
            cp.close()
        profile.clean_home(home)
    out["stderr_tail"] = stderr_tail[-4000:].decode("utf-8", errors="replace")
    return out


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--harness", required=True, choices=sorted(MODELS))
    p.add_argument("--model", required=True)
    p.add_argument("--cells-root", default=str(ROOT.parent / "e4-spike-cells"))
    p.add_argument("--handshake-timeout", type=float, default=60.0)
    p.add_argument("--prompt-timeout", type=float, default=240.0)
    args = p.parse_args()
    cells_root = Path(args.cells_root)
    cells_root.mkdir(parents=True, exist_ok=True)
    out = run(args.harness, args.model, cells_root, args.handshake_timeout, args.prompt_timeout)
    path = cells_root / f"{out['label']}.summary.json"
    path.write_text(json.dumps(out, indent=1, ensure_ascii=True) + "\n", encoding="utf-8")
    print(json.dumps(out, indent=1, ensure_ascii=True))
    return 0 if out.get("second_prompt_same_session") else 1


if __name__ == "__main__":
    sys.exit(main())
