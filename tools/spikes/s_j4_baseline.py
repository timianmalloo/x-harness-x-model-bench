"""Spike S-J4 (design W1-J section 4.4 / section 12): when does the adapter's lazy helper exist?

For one real ACP adapter, count the processes in the cell's Job Object (`job.active`) at three instants:
  A  right after `session/new` (driver.open_session returns),
  B  at the first `session/update` of turn 1 (the engine's `on_first_update` hook),
  C  right after turn 1 returns (a no-tool turn).
The `assume:` holds on an adapter where B >= C. The launch path is the engine's own (profiles.ProfileLauncher,
procs.spawn, driver.open_session, driver.send_turn); nothing here re-implements it and nothing under src/ changes.

Usage: python tools/spikes/s_j4_baseline.py <claude-code|codex|copilot> [tools_dir] [out_dir]
Writes <out_dir>/<harness>.json. A count that could not be read is null (not recorded), never 0. Tokens only.
"""

from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from harness_bench import driver, procs, profiles, tools  # noqa: E402
from harness_bench.engine import _job_query, _read_records, _spend  # noqa: E402
from harness_bench.telemetry import normalize  # noqa: E402

PINS = {"claude-code": "claude-opus-5-5", "codex": "gpt-6.1-sol", "copilot": "gpt-6.1-sol"}
PROMPT = "Reply with the single word OK. Do not use any tool."
HANDSHAKE_TIMEOUT = 60.0
DEFAULT_TOOLS = Path(r"C:\Projects\x-harness-x-model-bench\.tools\harness")
DEFAULT_OUT = Path(r"C:\tf\xsj4")


def end_process(cp: procs.CellProcess, grace: float) -> tuple[int | None, str]:
    """The engine's way (Engine._end_process): close stdin, wait for the job to drain, then terminate and confirm."""
    try:
        cp.proc.stdin.close()
    except (OSError, ValueError):
        pass
    deadline = time.monotonic() + grace
    while _job_query(cp.job.active, 1) and time.monotonic() < deadline:
        time.sleep(0.05)
    ended_by = "exit"
    if _job_query(cp.job.active, 1):
        ended_by = "terminate"
        cp.terminate_and_confirm(10.0)
    try:
        return cp.wait(timeout=10), ended_by
    except Exception:  # noqa: BLE001 - a wait that times out is "not recorded", the job is already terminated
        return None, ended_by


def run(harness: str, tools_dir: Path, out_dir: Path) -> dict:
    model = PINS[harness]
    base = out_dir / harness
    home, ws = base / "home", base / "ws"
    ws.mkdir(parents=True, exist_ok=True)
    out: dict = {"harness": harness, "pinned_model": model, "A": None, "B": None, "C": None, "stop_reason": None,
                 "tool_call_seen": None, "served_model": "not recorded", "build_version": None, "adapter_version": None,
                 "tokens": "not recorded", "outcome": "not run", "error": None}
    profile = profiles.load(ROOT, harness)
    build = tools.resolve(tools_dir)[harness]
    out["build_version"], out["adapter_version"] = build.version, build.adapter_version
    launcher = profiles.ProfileLauncher(profile, tools_dir, build.record())
    launcher.check_build()
    cell = {"harness": harness, "model": model, "scenario": None}
    argv, env = launcher.argv_env(cell, home, "")
    launcher.seed(home, cell)
    cp = None
    result = driver.TurnResult()
    try:
        cp = procs.spawn(argv, cwd=str(ws), env=env, stderr=subprocess.DEVNULL)
        out["root_pid"] = cp.pid
        session = driver.open_session(cp, ws, launcher.mode, HANDSHAKE_TIMEOUT, model if launcher.set_model else None, result)
        out["A"] = _job_query(cp.job.active, None) if session is not None else None
        if session is None:
            out["error"] = f"{result.cause.code if result.cause else 'handshake'}: {result.detail[:300]}"
        else:
            try:
                rec = driver.send_turn(session, PROMPT, lambda _sid: None, 1,
                                       on_first_update=lambda: out.__setitem__("B", _job_query(cp.job.active, None)))
                out["C"] = _job_query(cp.job.active, None) if rec is not None else None
                if rec is None:
                    out["error"] = f"{result.cause.code if result.cause else 'turn'}: {result.detail[:300]}"
                else:
                    out["stop_reason"] = rec.stop_reason
            finally:
                try:
                    session.close()
                except (OSError, ValueError):
                    pass
    finally:
        if cp is not None:
            out["exit_status"], out["ended_by"] = end_process(cp, launcher.shutdown_grace)
            out["updates"] = result.updates
            cp.close()
    try:
        extractions = _read_records(launcher, home, result.session_id)
        usage = [u for t in result.turns for u in normalize.turn_usage({"_meta": (t.usage or {}).get("meta")})]
        tokens = _spend(launcher.usage_source, extractions, usage)
        if launcher.usage_source == "native_record" and not sum(len(ex.model_calls) for ex in extractions):
            tokens = None  # the record names no model call: a sum of nothing is "not recorded", never a 0
        out["tokens"] = "not recorded" if tokens is None else tokens
        out["acp_usage"] = result.usage  # the adapter's own per-turn report, verbatim, or null
        readable = bool(extractions) and not any(normalize.record_unreadable(ex) for ex in extractions)
        if readable:
            out["tool_call_seen"] = any(ex.tool_calls for ex in extractions)
        served = sorted({normalize.base_model_id(c.model) for ex in extractions for c in ex.model_calls}
                        | {normalize.base_model_id(u.model) for u in usage})
        out["served_model"] = ",".join(served) if served else "not recorded"
    except Exception as exc:  # noqa: BLE001 - a record that cannot be read is "not recorded", never a guess
        out["record_error"] = f"{type(exc).__name__}: {str(exc)[:200]}"
    finally:
        launcher.clean(home)
    if out["A"] is not None and out["B"] is not None and out["C"] is not None and out["stop_reason"]:
        out["outcome"] = "completed"
    elif out["error"]:
        out["outcome"] = "not run: " + out["error"]
    else:
        out["outcome"] = "partial (a count is not recorded)"
    return out


def main(argv: list[str]) -> int:
    harness = argv[1]
    tools_dir = Path(argv[2]) if len(argv) > 2 else DEFAULT_TOOLS
    out_dir = Path(argv[3]) if len(argv) > 3 else DEFAULT_OUT
    try:
        out = run(harness, tools_dir, out_dir)
    except Exception as exc:  # noqa: BLE001 - a launch or auth failure is that adapter's "not run"
        code = getattr(exc, "code", None) or getattr(getattr(exc, "cause", None), "code", None) or type(exc).__name__
        out = {"harness": harness, "outcome": f"not run: {code}: {str(exc)[:300]}", "A": None, "B": None, "C": None,
               "tokens": "not recorded"}
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / f"{harness}.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(json.dumps(out, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
