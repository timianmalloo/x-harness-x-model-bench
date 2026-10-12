"""The readiness tool, the credential scan and the publish egress (ADR-0024 s6, ADR-0025 s7-s8, ADR-0027 s4, s6).

`tools/served_check.py` is a thin wrapper over the views. Each failing clause of ADR-0024 s6 exits 1; a clean fixture
exits 0. Every home, store and token here is a fake under tmp_path: no real credential is read.
"""

import base64
import dataclasses
import importlib.util
import json
import sys
import time
from pathlib import Path

import pytest
from archived_runs import GOOD, make_root, make_run

from harness_bench import ledger, views
from harness_bench.errors import BenchError
from harness_bench.grade import runner
from harness_bench.report import credentials, html, publish

_spec = importlib.util.spec_from_file_location("served_check", Path(__file__).resolve().parents[1] / "tools" / "served_check.py")
served_check = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(served_check)

EMAIL = "operator.person@example.org"


def _jwt(exp: int) -> str:
    part = base64.urlsafe_b64encode(json.dumps({"exp": exp}).encode()).decode().rstrip("=")
    return f"eyJhbGciOiJub25lIn0.{part}.c2lnbmF0dXJlLXBhcnQ"


# --- the env every test runs under: fake HOME, APPDATA, LOCALAPPDATA, bench credential home -----------------------


@pytest.fixture
def env(tmp_path, monkeypatch):
    home, bench = tmp_path / "user", tmp_path / "bench-home"
    for path in (home / ".grok" / "sessions", home / ".gemini" / "antigravity-cli" / "conversations",
                 home / "AppData" / "Roaming", home / "AppData" / "Local" / "grok", bench):
        path.mkdir(parents=True)
    monkeypatch.setenv("USERPROFILE", str(home))
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("APPDATA", str(home / "AppData" / "Roaming"))
    monkeypatch.setenv("LOCALAPPDATA", str(home / "AppData" / "Local"))
    monkeypatch.setenv("HB_GROK_CRED_HOME", str(bench))
    return {"home": home, "bench": bench}


# --- the view clauses ---------------------------------------------------------------------------------------------


@pytest.fixture
def graded(tmp_path):
    root = make_root(tmp_path)
    run_dir = make_run(root, tmp_path, {"a": GOOD})
    runner.run_pass(run_dir, root)
    return run_dir


def _put(run_dir: Path, fact: str, rows: list[dict]) -> None:
    """Replace the current pass's `fact` segment with `rows` (written through the real ledger)."""
    gid = views.load(run_dir).grading_id
    path = run_dir / fact / f"{gid}.jsonl"
    if path.exists():
        path.unlink()
    with ledger.SegmentWriter.create(run_dir / fact, gid) as writer:
        for row in rows:
            writer.append(row)


def _key(run_dir: Path) -> dict:
    cell = views.load(run_dir).cells[0]
    return {"run_id": "r1", "extraction_id": cell.extraction_id, "cell_id": "a", "native_session_id": "sess-a"}


def _clean(run_dir: Path, parts=(("system", None),)) -> None:
    key = _key(run_dir)
    _put(run_dir, "reasoning", [{"kind": "reasoning_item", **key, "native_ordinal": 1, "item_ordinal": 1,
                                 "source_kind": "summary", "text": "plan", "chars": 4, "reasoning_tokens": None,
                                 "opaque_sha256": None}])
    _put(run_dir, "prompt_parts", [{"kind": "prompt_part", **key, "part": part, "path": path, "chars": 10,
                                    "delivery": "inlined", "source": "rec"} for part, path in parts])


def _snapshot(tmp_path: Path) -> Path:
    out = tmp_path / "before.json"
    assert served_check.main(["--snapshot", str(out)]) == 0
    return out


def test_a_clean_fixture_exits_0(graded, env, tmp_path, capsys):
    _clean(graded)
    assert served_check.main([str(graded), "--before", str(_snapshot(tmp_path))]) == 0, capsys.readouterr().out


def _failures(run_dir: Path, **cell_changes) -> list[str]:
    view = views.load(run_dir)
    view.cells = [dataclasses.replace(c, **cell_changes) for c in view.cells]
    failures, _ = served_check.cell_failures(view, views.rows(run_dir, "reasoning"), views.rows(run_dir, "prompt_parts"))
    return failures


@pytest.mark.parametrize("code", ["HB-VAL-002", "HB-VAL-010"])
def test_an_invalidating_served_code_fails(graded, env, code):
    _clean(graded)
    assert any(code in f for f in _failures(graded, validity="invalid (x)", validity_code=code))


def test_hb_val_011_fails_on_a_pinned_value_only(graded, env):
    _clean(graded)
    warning = views.Finding("HB-VAL-011", "warning", "served effort not recorded: expected high (pinned), no source")
    assert _failures(graded, warnings=[warning]) == []  # the plan cell's effort is "default": declared, not pinned
    view = views.load(graded)
    view.plan["cells"][0]["effort"] = "high"
    view.cells = [dataclasses.replace(c, warnings=[warning]) for c in view.cells]
    failures, _ = served_check.cell_failures(view, views.rows(graded, "reasoning"), views.rows(graded, "prompt_parts"))
    assert any("HB-VAL-011" in f for f in failures)


def test_a_cell_with_only_omitted_reasoning_fails(graded, env):
    _clean(graded)
    key = _key(graded)
    _put(graded, "reasoning", [{"kind": "reasoning_item", **key, "native_ordinal": 1, "item_ordinal": 1,
                                "source_kind": "omitted", "text": None, "chars": None, "reasoning_tokens": 12,
                                "opaque_sha256": None}])
    assert any("reasoning" in f for f in _failures(graded))


def test_a_pack_on_cell_with_no_instruction_file_part_fails(graded, env):
    _clean(graded)
    assert any("pack-on" in f for f in _failures(graded, arm="on"))


def test_a_pack_off_cell_with_an_instruction_file_part_fails(graded, env):
    _clean(graded, parts=(("system", None), ("instruction_file", "AGENTS.md")))
    assert any("pack-off" in f for f in _failures(graded))


def test_a_harness_with_no_prompt_parts_source_reports_not_recorded_instead_of_failing(graded, env):
    _clean(graded, parts=())
    view = views.load(graded)
    failures, notes = served_check.cell_failures(view, views.rows(graded, "reasoning"), [])
    assert (failures, notes) == ([], ["codex: instruction-file clauses not recorded (no prompt_parts source)"])


def test_a_real_store_change_fails(graded, env, tmp_path):
    _clean(graded)
    before = _snapshot(tmp_path)
    (env["home"] / ".grok" / "sessions" / "leaked").write_text("x", encoding="utf-8")
    assert served_check.main([str(graded), "--before", str(before)]) == 1


def test_no_before_snapshot_fails_closed(graded, env):
    _clean(graded)
    assert served_check.main([str(graded)]) == 1


def test_a_bearer_shape_in_a_debug_log_fails(graded, env, tmp_path):
    _clean(graded)
    log = graded / "archive" / "a" / "attempt-1" / "home" / "logs" / "process-1.log"
    log.parent.mkdir(parents=True)
    log.write_text("request headers: Authorization: Bearer abcdefghijklmnop0123\n", encoding="utf-8")
    assert served_check.debug_log_failures(graded) == ["archive/a/attempt-1/home/logs/process-1.log: 1 authorization/bearer shape(s)"]
    assert served_check.main([str(graded), "--before", str(_snapshot(tmp_path))]) == 1


def test_a_cell_home_holding_the_bench_token_fails(graded, env):
    token = _jwt(1)
    (env["bench"] / "auth.json").write_text(json.dumps({"access_token": token}), encoding="utf-8")
    copy = graded / "archive" / "a" / "attempt-1" / "home" / ".grok" / "auth.json"
    copy.parent.mkdir(parents=True)
    copy.write_text(json.dumps({"access_token": token}), encoding="utf-8")
    assert served_check.credential_failures(graded) == ["archive/a/attempt-1/home/.grok/auth.json: a credential copy left in a cell home"]


# --- the Grok refresh gate (ADR-0025 s7): fake homes and a fake grok only -------------------------------------------


FAKE_GROK = """import os, pathlib, sys
home = os.environ.get("GROK_HOME") or os.path.join(os.environ["USERPROFILE"], ".grok")
sys.exit(0 if pathlib.Path(home, "auth.json").is_file() else 3)
"""


@pytest.fixture
def grok(tmp_path):
    script = tmp_path / "fake_grok.py"
    script.write_text(FAKE_GROK, encoding="utf-8")
    return [sys.executable, str(script)]


def _auth(env, exp):
    (env["bench"] / "auth.json").write_text(json.dumps({"access_token": _jwt(exp), "refresh_token": "r" * 20}),
                                            encoding="utf-8")


def test_the_refresh_gate_fails_on_an_unexpired_token(env, tmp_path):
    _auth(env, int(time.time()) + 3600)
    assert served_check.main(["--refresh-start", str(tmp_path / "gate.json")]) == 1


def test_the_refresh_gate_fails_on_unchanged_bytes(env, tmp_path, grok):
    _auth(env, int(time.time()) - 60)
    (env["home"] / ".grok" / "auth.json").write_text("{}", encoding="utf-8")
    state = tmp_path / "gate.json"
    assert served_check.main(["--refresh-start", str(state)]) == 0
    assert served_check.refresh_finish(state, grok) == ["bench auth.json bytes unchanged: no refresh was written back"]


def test_the_refresh_gate_passes_after_a_write_back_and_both_logins(env, tmp_path, grok):
    _auth(env, int(time.time()) - 60)
    (env["home"] / ".grok" / "auth.json").write_text("{}", encoding="utf-8")
    state = tmp_path / "gate.json"
    assert served_check.main(["--refresh-start", str(state)]) == 0
    _auth(env, int(time.time()) + 3600)  # a cell refreshed and wrote it back
    assert served_check.refresh_finish(state, grok) == []


def test_the_refresh_gate_fails_when_the_real_home_does_not_authenticate(env, tmp_path, grok):
    _auth(env, int(time.time()) - 60)
    state = tmp_path / "gate.json"
    assert served_check.main(["--refresh-start", str(state)]) == 0
    _auth(env, int(time.time()) + 3600)
    assert served_check.refresh_finish(state, grok) == ["grok models did not authenticate against the real home (exit 3)"]


def test_the_gate_never_prints_the_token(env, tmp_path, capsys):
    _auth(env, int(time.time()) + 3600)
    served_check.main(["--refresh-start", str(tmp_path / "gate.json")])
    out = capsys.readouterr()
    assert "eyJ" not in out.out + out.err


# --- the credential scan (ADR-0025 s7) ------------------------------------------------------------------------------


def test_the_credential_scan_finds_a_planted_bench_token_in_a_page(env, tmp_path):
    root = make_root(tmp_path / "r")
    token = "bench-grok-token-0123456789"
    (env["bench"] / "auth.json").write_text(json.dumps({"access_token": token}), encoding="utf-8")
    profile = root / "bench" / "profiles" / "grok.yaml"
    profile.write_text("harness: grok\ncredential: null\ncredential_home_env: HB_GROK_CRED_HOME\n", encoding="utf-8")
    assert html.scan(f"<p>{token}</p>", credentials.host_values(root)) == 1
    assert credentials.credential_files(root)["grok:bench-home"] == (env["bench"] / "auth.json", "auth.json")


# --- publish (ADR-0027 s4, s6) and the one excerpt filter (seam ruling S-1) -----------------------------------------


@pytest.mark.parametrize(("text", "shape"), [
    (f"mail {EMAIL} here", "email"), ("id 3f2b8c1e-9a4d-4e2f-8b1c-0d9e8f7a6b5c", "uuid"),
    ("Bearer abcdefghij0123456789", "bearer"), ("tok eyJhbGciOiJIUzI1NiJ9 end", "jwt"),
])
def test_scan_text_names_each_shape_never_the_value(text, shape):
    assert publish.scan_text(text) == [shape]


def test_scan_text_returns_nothing_for_a_clean_text():
    assert publish.scan_text("the model planned three edits and ran pytest") == []


@pytest.fixture
def no_host_credentials(tmp_path, monkeypatch):
    monkeypatch.setattr(publish, "ROOT", make_root(tmp_path / "pub"))
    monkeypatch.setenv("AF_NO_OPEN", "1")


def test_publish_refuses_without_the_operator_email(tmp_path, monkeypatch, no_host_credentials):
    monkeypatch.delenv("BENCH_OPERATOR_EMAIL", raising=False)
    with pytest.raises(BenchError) as error:
        publish.publish("<p>ok</p>", tmp_path / "page.html", False)
    assert (error.value.code, (tmp_path / "page.html").exists()) == ("HB-USR-002", False)


def test_publish_drops_an_email_shaped_excerpt(tmp_path, monkeypatch, no_host_credentials, capsys):
    monkeypatch.setenv("BENCH_OPERATOR_EMAIL", EMAIL)
    page = ('<p>kept</p><blockquote class="excerpt">ask someone.else@example.com</blockquote>'
            '<blockquote class="excerpt">clean reasoning</blockquote>')
    publish.publish(page, tmp_path / "page.html", False)
    assert (tmp_path / "page.html").read_text(encoding="utf-8") == \
        '<p>kept</p><blockquote class="excerpt">clean reasoning</blockquote>'
    assert "1 excerpt(s) dropped by shape" in capsys.readouterr().err


def test_publish_writes_nothing_when_the_page_outside_excerpts_holds_a_shape(tmp_path, monkeypatch, no_host_credentials):
    monkeypatch.setenv("BENCH_OPERATOR_EMAIL", EMAIL)
    with pytest.raises(BenchError) as error:
        publish.publish("<p>Bearer abcdefghij0123456789</p>", tmp_path / "page.html", False)
    assert (error.value.code, (tmp_path / "page.html").exists()) == ("HB-SEC-001", False)


def test_publish_under_af_no_open_prints_the_not_opened_status(tmp_path, monkeypatch, no_host_credentials, capsys):
    monkeypatch.setenv("BENCH_OPERATOR_EMAIL", EMAIL)
    status = publish.publish("<p>ok</p>", tmp_path / "page.html", True)
    assert (status, capsys.readouterr().out) == ("not opened: AF_NO_OPEN is set", "not opened: AF_NO_OPEN is set\n")
