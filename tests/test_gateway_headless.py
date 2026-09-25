"""The headless judge backend (design phase3-gateway-judges sections 8.1-8.4, slice 2; T-GW-07..10, 26, 28, 32, 35).

Contract tests: spike GW-H's Claude records, copied into `tests/fixtures/gateway/records/` with every identifier
replaced by a fixed placeholder (`copy_records.py`), are replayed by the fake CLI `fake_judge_cli.py`, launched
through the real `procs.run` in its own Job Object; the real readers decide the outcome (directive D7). No real
model CLI is launched and no network call is made. The credential is a synthetic temp file; the cells root is the
clean `base` folder (no instruction file above it); operator identifiers are random synthetic strings (R-42).
"""

import hashlib
import json
import sys
from pathlib import Path
from secrets import token_hex

from harness_bench import egress, profiles, tools
from harness_bench.gateway import backend as gw_backend
from harness_bench.gateway import pipeline, request, scrub

FIX = Path(__file__).resolve().parent / "fixtures" / "gateway"
RECORDS = FIX / "records"
FAKE = FIX / "fake_judge_cli.py"
PIN = "claude-fable-5-1"
JUDGE = pipeline.Judge(model=PIN, invocation_sha256="d" * 64, allowed_models=(PIN, "claude-haiku-4-5"), qualified=True)
ENTRIES = (*scrub.FAMILY_WORDS, "harness-placeholder", "combo-placeholder")
INPUTS = pipeline.Inputs(preamble="No mechanical oracle applies.",
                         rubric="1. Names the data structure and why.\n2. States the cost of each operation.\n",
                         items=2, artifacts=(("docs/architecture.md", b"# Queue\nA binary heap in an array.\n"),))


def _operator() -> egress.Operator:
    return egress.Operator(email=f"op-{token_hex(6)}@example.invalid", username=f"u{token_hex(5)}",
                           home=f"C:\\Users\\u{token_hex(5)}")


def _ctx(tmp_path, operator=None, **over) -> pipeline.Context:
    fields = {"store": tmp_path / "cache" / "verdicts", "known_roots": (tmp_path / "runs",), "own_run": None,
              "stored_by": {"ledger": "run", "ledger_id": "run-placeholder-1",
                            "grading_or_calibration_id": "grade-placeholder-1"},
              "denylist": ENTRIES, "allow_model_calls": True, "operator": operator or _operator()}
    return pipeline.Context(**(fields | over))


def _launch(tmp_path, cells_root, turn: str = "claude-fable-text", stdout: Path | None = None, record: Path | None = None,
            timeout: float = 60, **cfg) -> gw_backend.Launch:
    """A launch of the fake CLI replaying one recorded turn; the credential is a synthetic temp file."""
    credential = tmp_path / "synthetic-login" / ".credentials.json"
    credential.parent.mkdir(parents=True, exist_ok=True)
    credential.write_text(json.dumps({"placeholder": token_hex(8)}), encoding="utf-8")
    cfg = {"record": str(record or RECORDS / f"{turn}.record.jsonl"),
           "stdout": str(stdout or RECORDS / f"{turn}.stdout.json"), "capture": str(tmp_path / "capture")} | cfg
    profile = profiles.Profile(harness="claude-code", home_env="CLAUDE_CONFIG_DIR", credential_source=credential,
                               credential_name=".credentials.json", command=("{exe}",),
                               env={"HB_FAKE_JUDGE": json.dumps(cfg)}, record_glob="projects/**/{session_id}.jsonl",
                               auxiliary_models=("claude-haiku-4-5",))
    build = tools.Build(harness="claude-code", version="2.1.282", exe=FAKE, sha256="0" * 64, adapter=None,
                        adapter_version=None, adapter_sha256=None)
    return gw_backend.Launch(profile=profile, build=build, model=PIN, cells_root=cells_root,
                             grading_id="grade-placeholder-1", archive=tmp_path / "archive", timeout=timeout,
                             prefix=(sys.executable,))


def _captured(tmp_path) -> list[dict]:
    return [json.loads(p.read_text(encoding="utf-8")) for p in sorted((tmp_path / "capture").glob("*.json"))]


def _rendered(inputs: pipeline.Inputs = INPUTS) -> str:
    return request.render(inputs.preamble, inputs.rubric, inputs.items, inputs.artifacts, ENTRIES).text


# ------------------------------------------------------------------------------------------------ the launch shape
def test_the_builders_put_the_request_on_stdin_never_in_argv(tmp_path):
    a = gw_backend.claude_argv("claude.exe", PIN, "S", "sid")
    assert a[:3] == ["claude.exe", "-p", "--model"] and a[a.index("--model") + 1] == PIN
    assert a[a.index("--tools") + 1] == "" and a[a.index("--tools") + 2] == "--strict-mcp-config"
    assert "--json-schema" not in a and "--fallback-model" not in a
    assert a[-4:] == ["--output-format", "json", "--session-id", "sid"]
    c = gw_backend.codex_argv("codex.exe", "gpt-6-sol", tmp_path / "work", tmp_path / "last.txt")
    assert c[-1] == "-" and "model=gpt-6-sol" in c and "include_apply_patch_tool=false" not in c


def test_invocation_sha256_changes_with_each_part_of_the_invocation():
    base = ("claude-code", PIN, gw_backend.JUDGE_SYSTEM, "text", "2.1.282", "a" * 64)
    first = gw_backend.invocation_sha256(*base)
    assert first == gw_backend.invocation_sha256(*base)
    changed = [gw_backend.invocation_sha256(*(base[:i] + (v,) + base[i + 1:]))
               for i, v in enumerate(("codex", "claude-opus-5-5", "other system", "native", "2.1.283", "b" * 64))]
    assert len({first, *changed}) == 7


def test_a_headless_call_sends_the_request_on_stdin_from_a_cells_root_folder_and_archives_the_record(tmp_path, base):
    launch = _launch(tmp_path, base / "cells")
    result = pipeline.run(JUDGE, INPUTS, _ctx(tmp_path), launch)
    assert (result.outcome, result.code) == ("stored", None)
    [seen] = _captured(tmp_path)
    assert seen["stdin"] == _rendered()  # the whole request, intact, on stdin
    assert _rendered() not in seen["argv"] and "-p" in seen["argv"]
    call = base / "cells" / "gateway" / "grade-placeholder-1" / result.cache_key[:16]
    assert Path(seen["cwd"]) == call / "work" and Path(seen["userprofile"]) == call / "profile"
    assert not call.exists()  # the call folder is deleted after the call
    archived = tmp_path / "archive" / result.cache_key[:16] / "record.jsonl"
    assert archived.read_text(encoding="utf-8").count('"sessionId"') > 0
    assert hashlib.sha256(archived.read_bytes()).hexdigest() != hashlib.sha256(
        (RECORDS / "claude-fable-text.record.jsonl").read_bytes()).hexdigest()  # this call's own session id


# --------------------------------------------------------------------------------------------------- T-GW-32
def test_t_gw_32_an_unqualified_judge_is_never_spawned(tmp_path, base):
    unqualified = pipeline.Judge(model=PIN, invocation_sha256="d" * 64, allowed_models=(PIN,), qualified=False)
    result = pipeline.run(unqualified, INPUTS, _ctx(tmp_path), _launch(tmp_path, base / "cells"))
    assert (result.outcome, result.code, result.verdicts, result.model_calls) == ("failed", "HB-GW-007", None, ())
    assert _captured(tmp_path) == []  # 0 spawns
    assert not (base / "cells" / "gateway").exists()  # no call folder, no credential copy
    # the gate comes before the store: not even a cache-only pass reads a verdict for it (design 10.1)
    result = pipeline.run(unqualified, INPUTS, _ctx(tmp_path, allow_model_calls=False), _launch(tmp_path, base / "c2"))
    assert (result.outcome, result.code) == ("failed", "HB-GW-007")


# --------------------------------------------------------------------------------------------------- T-GW-07
def test_t_gw_07_the_served_model_is_read_from_the_record_not_stdout(tmp_path, base):
    # The spike's Opus record (the R-58 fallback, served when asked for) replayed under the Fable pin, with a stdout
    # whose self-report says Fable: the record decides (review A5), and nothing is stored.
    launch = _launch(tmp_path, base / "cells", record=RECORDS / "claude-opus-text.record.jsonl",
                     stdout=RECORDS / "claude-fable-text.stdout.json")
    result = pipeline.run(JUDGE, INPUTS, _ctx(tmp_path), launch)
    assert (result.outcome, result.code, result.verdicts) == ("failed", "HB-GW-003", None)
    assert not list((tmp_path / "cache" / "verdicts").glob("*.json"))
    assert len(_captured(tmp_path)) == 1


def test_t_gw_07_the_pin_in_the_record_is_stored_even_when_stdout_names_another_model(tmp_path, base):
    launch = _launch(tmp_path, base / "cells", record=RECORDS / "claude-fable-text.record.jsonl",
                     stdout=RECORDS / "claude-opus-text.stdout.json")
    result = pipeline.run(JUDGE, INPUTS, _ctx(tmp_path), launch)
    assert (result.outcome, result.code) == ("stored", None)
    entry = json.loads((tmp_path / "cache" / "verdicts" / f"{result.cache_key}.json").read_text(encoding="utf-8"))
    assert entry["served_models"] == [PIN]


# --------------------------------------------------------------------------------------------------- T-GW-08
def test_t_gw_08_a_tool_event_in_the_record_fails_the_call(tmp_path, base):
    # The spike's native-schema turn: `--json-schema` made Claude call `StructuredOutput` (one tool event), and its
    # stdout still carries a valid answer. The record decides: HB-GW-006, nothing stored.
    launch = _launch(tmp_path, base / "cells", turn="claude-fable-native")
    stdout = json.loads((RECORDS / "claude-fable-native.stdout.json").read_text(encoding="utf-8"))
    result = pipeline.run(JUDGE, INPUTS, _ctx(tmp_path), launch)
    assert (result.outcome, result.code, result.verdicts) == ("failed", "HB-GW-006", None)
    assert stdout["structured_output"]["items"][0]["item"] == 1  # the answer was there; the tool event still fails it
    assert not list((tmp_path / "cache" / "verdicts").glob("*.json"))


def test_t_gw_08_a_tool_event_fails_before_the_served_model_check(tmp_path):
    # Section 8.3 order: tool events (step 1) before the served model (step 2): an off-pin record with a tool event
    # is HB-GW-006, the first failing step.
    import test_gateway_pipeline as tp
    record = tp.claude_record(tmp_path / "r.jsonl", ("claude-opus-5-5",), tool="Bash")
    stdout = (RECORDS / "claude-fable-text.stdout.json").read_text(encoding="utf-8")
    replay = gw_backend.ReplayBackend({hashlib.sha256(_rendered().encode()).hexdigest():
                                       gw_backend.Recorded(stdout, record)}, tmp_path / "archive")
    result = pipeline.run(JUDGE, INPUTS, _ctx(tmp_path), replay)
    assert (result.outcome, result.code) == ("failed", "HB-GW-006")
