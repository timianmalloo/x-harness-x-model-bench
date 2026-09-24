"""The ACP stdio recorder (`tools/acp_record.py`, phase-2 W1-ACP (a); `docs/proof/phase1.md` residual 9).

The recorder sits between the driver and an adapter. It must be transparent: the driver's `TurnResult`
and the bytes on both pipes are the same with and without it. Its recording must hold exactly the bytes it
passed, in order, with direction and time, and stay bounded.
"""

import dataclasses
import functools
import importlib.util
import itertools
import json
import os
import sys
from pathlib import Path

import pytest
from test_driver import FAKE, _Tap

from harness_bench import driver, procs

RECORDER = Path(__file__).resolve().parents[1] / "tools" / "acp_record.py"
TIMINGS = {"handshake_seconds", "turn_seconds"}


@functools.cache
def _recorder():
    spec = importlib.util.spec_from_file_location("acp_record", RECORDER)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  # FileNotFoundError while tools/acp_record.py does not exist
    return module


def _read(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def _run(cwd: Path, argv: list[str], fake: str) -> dict:
    """One driver turn against argv, with the driver's side of both pipes tapped."""
    cwd.mkdir(parents=True)
    env = dict(os.environ, FAKE_ACP=json.dumps({"mode": fake, "usage": [{"model": "m", "token_count": {}}]}))
    cell = procs.spawn(argv, cwd=str(cwd), env=env)
    cell.proc.stdout, cell.proc.stdin = _Tap(cell.proc.stdout), _Tap(cell.proc.stdin)
    try:
        result = driver.run_turn(cell, cwd=cwd, prompt="Implement slugify.\r\nKeep it.  \n", mode="agent-full-access",
                                 handshake_timeout=10, before_send=lambda sid: None)
    finally:
        cell.terminate_and_confirm(timeout=10)
        cell.close()
    agent_files = {p.name: p.read_bytes() for p in cwd.glob(".fake-*")}  # what the agent itself received
    return {"result": result, "stdin": bytes(cell.proc.stdin.data), "stdout": bytes(cell.proc.stdout.data),
            "agent_files": agent_files, "cwd": cwd}


def _norm(run: dict) -> dict:
    """Two runs cannot share the fake's fresh session uuid or their own cwd (sent in session/new); timings vary."""
    sid = run["result"].session_id
    assert sid
    fields = {k: v for k, v in dataclasses.asdict(run["result"]).items() if k not in TIMINGS | {"session_id"}}
    cwd = json.dumps(str(run["cwd"]))[1:-1].encode()

    def swap(data: bytes) -> bytes:
        return data.replace(sid.encode(), b"<sid>").replace(cwd, b"<cwd>")

    return {"result": fields, "stdin": swap(run["stdin"]), "stdout": swap(run["stdout"]),
            "agent_files": {k: swap(v) for k, v in run["agent_files"].items()}}


@pytest.mark.native
@pytest.mark.parametrize("fake", ["ok", "permission"])
def test_the_recorder_is_transparent_and_records_every_byte(tmp_path, fake):
    fake_argv = [sys.executable, str(FAKE)]
    outer, inner = tmp_path / "outer.jsonl", tmp_path / "inner.jsonl"
    direct = _run(tmp_path / "direct", fake_argv, fake)
    recorded = _run(tmp_path / "recorded", [sys.executable, str(RECORDER), "record", "--out", str(outer), "--", *fake_argv], fake)
    nested = _run(tmp_path / "nested", [sys.executable, str(RECORDER), "record", "--out", str(outer.with_name("n-outer.jsonl")),
                                         "--", sys.executable, str(RECORDER), "record", "--out", str(inner), "--", *fake_argv], fake)

    # the driver sees the same turn, and the same bytes cross both pipes, with and without the recorder
    assert direct["result"].cause is None and direct["result"].stop_reason == "end_turn"
    for run in (recorded, nested):
        assert run["result"].cause is None, f"through the recorder: {run['result'].detail}"
    assert _norm(recorded) == _norm(direct)
    assert _norm(nested) == _norm(direct)
    assert direct["result"].permission_requests == (1 if fake == "permission" else 0)

    # the recording holds exactly the bytes the driver wrote and read, in both directions
    rec = _recorder()
    records = _read(outer)
    assert rec.stream_bytes(records, "to_agent") == recorded["stdin"]
    assert rec.stream_bytes(records, "to_client") == recorded["stdout"]
    # the far side of the recorder's pipes (an inner recorder, a separate process) saw the same bytes
    near, far = _read(outer.with_name("n-outer.jsonl")), _read(inner)
    for direction in ("to_agent", "to_client"):
        assert rec.stream_bytes(far, direction) == rec.stream_bytes(near, direction) == nested[
            "stdin" if direction == "to_agent" else "stdout"]

    # every message in order, with direction and a timestamp; a reply never precedes its request
    header, lines = records[0], [r for r in records if r["kind"] == "line"]
    assert header["kind"] == "header" and header["argv"] == fake_argv and header["started_utc"]
    assert [r["seq"] for r in records[1:]] == list(range(1, len(records)))
    assert all(a["t"] <= b["t"] for a, b in itertools.pairwise(records[1:]))
    asked = {}
    for r in lines:
        msg = json.loads(r["text"])
        if r["dir"] == "to_agent" and "method" in msg:
            asked[msg["id"]] = r["seq"]
        elif r["dir"] == "to_client" and "id" in msg and "method" not in msg:
            assert asked[msg["id"]] < r["seq"], f"reply {msg['id']} recorded before its request"
    assert set(asked) == {1, 2, 3, 4}  # initialize, session/new, session/set_mode, session/prompt


def _tee(rec, **caps):
    out = []
    recording = rec.Recording(out.append, **caps)
    return recording, out


def test_a_line_over_the_line_cap_is_recorded_in_fragments_that_rebuild_it():
    rec = _recorder()
    recording, out = _tee(rec, max_line_bytes=8)
    passed = b""
    tee = rec.Tee(recording, "to_client")
    for chunk in (b"0123456789abcdef01", b"23\n{\"a\":1}\n", b"tail-without-newline"):
        passed += tee.feed(chunk)
    tee.close()
    records = [json.loads(line) for line in out]
    assert passed == b"0123456789abcdef0123\n{\"a\":1}\ntail-without-newline"
    assert rec.stream_bytes(records, "to_client") == passed
    assert all(len(r.get("text", "")) <= 8 for r in records if r["kind"] == "line")
    assert records[-1]["kind"] == "eof"


@pytest.mark.parametrize("caps", [{"max_lines": 2}, {"max_bytes": 10}], ids=["line-cap", "byte-cap"])
def test_a_capped_recording_says_so_and_the_bytes_still_pass(caps):
    rec = _recorder()
    recording, out = _tee(rec, **caps)
    tee = rec.Tee(recording, "to_agent")
    data = b"".join(b'{"n":%d}\n' % i for i in range(5))
    assert tee.feed(data) == data  # pass-through never depends on the recording
    records = [json.loads(line) for line in out]
    assert records[-1]["kind"] == "truncated" and records[-1]["reason"] == next(iter(caps))
    assert data.startswith(rec.stream_bytes(records, "to_agent"))
    tee.feed(b'{"n":9}\n')
    assert len(out) == len(records)  # nothing is recorded after the marker


def test_a_line_that_is_not_utf8_is_kept_as_base64():
    rec = _recorder()
    recording, out = _tee(rec)
    tee = rec.Tee(recording, "to_client")
    tee.feed(b"\xff\xfe junk\n")
    records = [json.loads(line) for line in out]
    assert "b64" in records[0] and rec.stream_bytes(records, "to_client") == b"\xff\xfe junk\n"


def test_scrub_replaces_each_literal_in_raw_and_json_escaped_form_and_refuses_a_leftover(tmp_path):
    rec = _recorder()
    home = r"C:\Users\someone\cells\home"
    line = json.dumps({"cwd": home, "note": "C:/Users/someone/cells/home and someone@example.com"})
    raw = tmp_path / "raw.jsonl"
    raw.write_text("\n".join(json.dumps(r) for r in [
        {"kind": "header", "argv": [home + r"\node.exe"], "cwd": home, "started_utc": "x", "caps": {}},
        {"kind": "line", "seq": 1, "t": 0.0, "dir": "to_client", "text": line, "nl": True}]) + "\n", encoding="utf-8")
    out = tmp_path / "scrubbed.jsonl"
    rec.scrub(raw, out, {home: "<HOME>"}, forbid=["someone"])
    body = out.read_text(encoding="utf-8")
    assert "someone" not in body and "<HOME>" in body and "<EMAIL>" in body
    scrubbed_line = _read(out)[1]["text"]
    assert json.loads(scrubbed_line)["cwd"] == "<HOME>"  # still valid JSON after the escaped-form swap
    with pytest.raises(ValueError, match="left"):
        rec.scrub(raw, tmp_path / "again.jsonl", {}, forbid=["someone"])
    assert not (tmp_path / "again.jsonl").exists()  # a refused scrub writes nothing
