"""R-READ-CODEX: the Codex reader's lean re-run facts (ADR-0024 s4, ADR-0026 s1) and its shell-read classifier.

Fixtures: `fixtures/codex/rerun-pack-off-high.jsonl` is hand-authored in the shape of the X2 spike rollout (Codex
0.160.0, gpt-6.1-sol, effort high, window 828,400; pack off); `fixtures/native/codex/pack-on.jsonl` is the committed
pack-on record; `fixtures/codex/rerun-shell-reads.jsonl` is a hand-authored exec sequence whose read targets are
counted by hand below.
"""

from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

from harness_bench.telemetry import READER_NOT_BUILT, SERVED_FIELDS, codex, normalize

FIX = Path(__file__).resolve().parent / "fixtures"
PACK_OFF = FIX / "codex" / "rerun-pack-off-high.jsonl"
PACK_ON = FIX / "native" / "codex" / "pack-on.jsonl"
SHELL = FIX / "codex" / "rerun-shell-reads.jsonl"
SID = "01a12c98-0000-7000-8000-000000000001"
# The served model's catalog entry: four fields copied by hand from the X2 spike's models_cache.json (gpt-6.1-sol).
CATALOG = {"models": [{"slug": "gpt-6.1-sol", "context_window": 272000, "max_context_window": 872000,
                       "effective_context_window_percent": 95}]}


def _home(tmp_path: Path, catalog: dict | None = CATALOG, record: Path = PACK_OFF) -> Path:
    """The record placed as Codex writes it: <home>/sessions/YYYY/MM/DD/rollout-*.jsonl, the catalog at <home>."""
    day = tmp_path / "home" / "sessions" / "2026" / "10" / "11"
    day.mkdir(parents=True)
    rollout = day / f"rollout-2026-10-11T13-12-38-{SID}.jsonl"
    shutil.copyfile(record, rollout)
    if catalog is not None:
        (tmp_path / "home" / "models_cache.json").write_text(json.dumps(catalog), encoding="utf-8")
    return rollout


def _served(ex) -> dict[str, list[dict]]:
    out: dict[str, list[dict]] = {}
    for r in normalize.served_rows("run", "cell", "sid", ex, "x"):
        out.setdefault(r["field"], []).append(r)
    return out


# --- 1. served settings -------------------------------------------------------------------------------------------

def test_served_settings_come_from_turn_context_and_task_started_with_the_catalog_percent_source(tmp_path):
    rows = _served(codex.read(_home(tmp_path)))
    one = {f: rs[0] for f, rs in rows.items() if len(rs) == 1}
    assert set(one) == set(rows) == set(SERVED_FIELDS)  # one row per field: the record agrees with itself
    assert (one["model_served"]["value"], one["model_served"]["source"]) == ("gpt-6.1-sol", "rollout:turn_context.model")
    assert (one["effort"]["value"], one["effort"]["source"]) == ("high", "rollout:turn_context.effort")
    assert (one["reasoning_summary"]["value"], one["reasoning_summary"]["source"]) == ("auto", "rollout:turn_context.summary")
    # The nominal window (Leader ruling 2026-10-12): the effective 828,400 / (the catalog's 95 / 100) = 872,000, exact.
    assert one["context_tokens"]["value"] == 872000 == 828400 * 100 // 95
    assert one["context_tokens"]["source"] == ("nominal = rollout:task_started.model_context_window=828400 / "
                                               "(models_cache.json models[gpt-6.1-sol].effective_context_window_percent=95"
                                               " / 100) (max_context_window=872000)")
    for nr in ("model_api", "context_tier"):
        assert one[nr]["value"] is None and one[nr]["not_recorded"].startswith("not recorded: ")


def test_served_context_without_a_catalog_is_not_recorded_naming_the_missing_percent(tmp_path):
    rows = _served(codex.read(_home(tmp_path, catalog=None)))
    assert [(r["value"], r["not_recorded"]) for r in rows.get("context_tokens", [])] == [
        (None, "not recorded: nominal window needs the catalog percent: no models_cache.json beside the record")]
    assert rows["context_tokens"][0]["source"] == "rollout:task_started.model_context_window=828400"


def test_the_percent_comes_from_the_catalog_the_cell_s_config_names(tmp_path):
    """fix/codex-profile-0160: a seeded cell names its catalog (`model_catalog_json`, resolved beside config.toml) and
    Codex then fetches none, so no models_cache.json exists; the percent is read from the named file."""
    rollout = _home(tmp_path, catalog=None)
    home = tmp_path / "home"
    (home / "config.toml").write_text('model = "gpt-6.1-sol"\nmodel_catalog_json = "model_catalog.json"\n', encoding="utf-8")
    (home / "model_catalog.json").write_text(json.dumps(CATALOG), encoding="utf-8")
    rows = _served(codex.read(rollout))
    assert [(r["value"], r["source"]) for r in rows["context_tokens"]] == [
        (872000, ("nominal = rollout:task_started.model_context_window=828400 / (model_catalog.json models[gpt-6.1-sol]"
                  ".effective_context_window_percent=95 / 100) (max_context_window=872000)"))]
    (home / "model_catalog.json").unlink()  # a named catalog that is gone is not recorded, never a fallback guess
    assert [r["not_recorded"] for r in _served(codex.read(rollout))["context_tokens"]] == [
        "not recorded: nominal window needs the catalog percent: no model_catalog.json beside the record"]


def test_a_percent_that_does_not_divide_the_window_exactly_is_not_recorded(tmp_path):
    catalog = {"models": [{**CATALOG["models"][0], "effective_context_window_percent": 97}]}
    rows = _served(codex.read(_home(tmp_path, catalog=catalog)))
    assert [(r["value"], r["not_recorded"]) for r in rows["context_tokens"]] == [
        (None, "not recorded: 828400 / (97 / 100) is not an integer")]


def test_two_turn_contexts_that_disagree_are_both_written(tmp_path):
    record = tmp_path / "r.jsonl"
    lines = PACK_OFF.read_text(encoding="utf-8").splitlines()
    second = json.loads(next(line for line in lines if '"type":"turn_context"' in line))
    second["payload"]["effort"] = "medium"
    record.write_text("\n".join([*lines, json.dumps(second)]) + "\n", encoding="utf-8")
    rows = _served(codex.read(record))
    assert [r["value"] for r in rows.get("effort", [])] == ["high", "medium"]
    assert [r["value"] for r in rows.get("model_served", [])] == ["gpt-6.1-sol"]


# --- 2. reasoning items -------------------------------------------------------------------------------------------

def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def test_reasoning_rows_are_a_summary_and_an_encrypted_only_item_each_on_its_request():
    ex = codex.read(PACK_OFF)
    rows = normalize.reasoning_rows("run", "cell", "sid", ex, "x")
    assert [(r["source_kind"], r["chars"], r["item_ordinal"], r["reasoning_tokens"]) for r in rows] == [
        ("summary", 494, 0, None), ("encrypted-only", None, 0, None)]
    assert rows[0]["text"].startswith("**Counting vowels in README**") and len(rows[0]["text"]) == 494
    assert rows[1]["text"] is None
    assert [r["opaque_sha256"] for r in rows] == [_sha("gAAAAABsyntheticOpaqueReasoningOne=="),
                                                  _sha("gAAAAABsyntheticOpaqueReasoningTwo==")]
    assert [r["native_ordinal"] for r in rows] == [c.native_ordinal for c in ex.model_calls] == [13, 17]


def test_pack_on_reasoning_keeps_every_item_and_numbers_items_within_a_request():
    items = codex.read(PACK_ON).reasoning
    assert len(items) == 15  # hand count: response_item reasoning rows at lines 12..113
    assert all(i.source_kind == "summary" and i.opaque_sha256 for i in items)
    two = [i for i in items if i.native_ordinal == 67]  # lines 58 and 60 share the request reported at line 67
    assert [i.item_ordinal for i in two] == [0, 1]
    assert items[2].text == "**Preparing the workspace**\n\n**Creating a worktree**"  # line 28: two summary parts


# --- 3. prompt parts and harness events ---------------------------------------------------------------------------

def test_the_agents_md_block_is_an_instruction_file_part_on_pack_on_and_absent_on_pack_off():
    on = codex.read(PACK_ON).prompt_parts
    assert isinstance(on, list), on
    files = [p for p in on if p.part == "instruction_file"]
    assert [(p.path, p.chars, p.delivery, p.source) for p in files] == [
        ("AGENTS.md", 26006, "inlined", "rollout:response_item.message[user]")]
    assert [(p.chars, p.delivery) for p in on if p.part == "skills"] == [(18601, "listed")]
    assert (on[0].part, on[0].chars, on[0].source) == ("system", 18992, "rollout:session_meta.base_instructions")
    off = codex.read(PACK_OFF).prompt_parts
    assert [p.part for p in off] == ["system", "skills", "system", "system"]
    assert not [p for p in off if p.part == "instruction_file"]


def test_each_prefix_text_is_its_own_row_numbered_by_its_position():
    """Leader ruling (item 28, the DR1 shape): the pack-on record's four developer `system` texts and two injected user
    ones are one row each, keyed apart by `native_ordinal`, never one key twice (HB-LED-003)."""
    rows = normalize.prompt_part_rows("run", "cell", "sid", codex.read(PACK_ON), "x")
    dev, user = "rollout:response_item.message[developer]", "rollout:response_item.message[user]"
    assert [(r["native_ordinal"], r["part"], r["chars"], r["source"]) for r in rows] == [
        (0, "system", 18992, "rollout:session_meta.base_instructions"), (1, "skills", 18601, dev),
        (2, "system", 363, dev), (3, "system", 920, dev), (4, "system", 2429, dev), (5, "system", 271, dev),
        (6, "system", 920, user), (7, "instruction_file", 26006, user), (8, "system", 371, user)]
    assert len({(r["native_ordinal"], r["part"], r["path"], r["source"]) for r in rows}) == len(rows)


def test_harness_events_are_not_recorded_with_a_reason():
    events = codex.read(PACK_OFF).harness_events
    assert isinstance(events, str) and events != READER_NOT_BUILT and events.startswith("not recorded: ")


# --- 4. per-request model calls -----------------------------------------------------------------------------------

def test_one_model_call_per_request_not_one_per_usage_report():
    calls = codex.read(PACK_OFF).model_calls  # two token_count and two token_usage_record rows: two requests
    assert [(c.native_ordinal, c.uncached_input, c.cache_read, c.output, c.reasoning) for c in calls] == [
        (13, 2847, 9088, 155, 102), (17, 12159, 0, 122, 115)]


# --- 5. shell reads and bytes returned ----------------------------------------------------------------------------

# Hand count over rerun-shell-reads.jsonl's 24 exec calls: 18 read targets; 13 read calls, 3 list calls, 8 neither.
SHELL_EXPECTED = [
    (("slug.py", "docs/ai-forward-pack/codex.md"), "read"),
    (("README.md",), "read"),
    (("src/app.py",), "read"),
    (("src", "tests"), "read"),
    (("lib",), "read"),
    (("../ws/__pycache__",), "list"),
    (("docs",), "list"),
    (("notes.txt",), "read"),
    (("log.txt",), "read"),
    (("a.bin",), "read"),
    (("big.txt",), "read"),
    (("x.log",), "read"),
    (("data.json",), "read"),
    (("src",), "list"),
    (("y.txt",), "read"),
    ((), "read"),            # rg -l TODO 2>/dev/null: no path named
    (("README.md",), None),  # a git statement then a read: the read's target, but the call is not a read
    ((), None),              # git status
    ((), None),              # Remove-Item
    ((), None),              # sed -i is a write
    ((), None),              # a redirect is a write
    ((), None),              # a variable is not a path
    ((), None),              # open(..., 'w') is a write
    ((), None),              # an unknown Get-Content parameter cannot be parsed
]


def test_shell_read_commands_name_their_targets_as_read_paths():
    calls = codex.tool_inputs(SHELL).calls
    assert [c.paths for c in calls] == [paths for paths, _ in SHELL_EXPECTED]
    assert [(c.paths, codex.shell_read_kind(c.command)) for c in calls] == SHELL_EXPECTED
    assert sum(len(c.paths) for c in calls) == 18
    assert not any(c.is_write for c in calls)


def test_bytes_returned_is_the_utf8_size_of_the_call_output():
    calls = codex.tool_inputs(SHELL).calls
    assert [c.bytes_returned for c in calls] == [6] * 10 + [7] * 14  # "out<i>é": i digits + 3 + 2 bytes for é
    off = codex.tool_inputs(PACK_OFF).calls
    assert [c.bytes_returned for c in off] == [len(b"Script completed\nWall time 0.3 seconds\nOutput:\n")
                                               + len(b"Hello from the README line\n")]


def test_a_call_with_no_output_row_returns_no_bytes(tmp_path):
    record = tmp_path / "r.jsonl"
    record.write_text(json.dumps({"type": "response_item", "payload": {
        "type": "custom_tool_call", "call_id": "c1", "name": "exec",
        "input": 'tools.exec_command({cmd:"cat a.txt"})'}}) + "\n", encoding="utf-8")
    assert [(c.paths, c.bytes_returned) for c in codex.tool_inputs(record).calls] == [(("a.txt",), None)]


# --- 6. shell command class (B1 / I1): read, edit, test or other per call, with the read targets -----------------------
# Every command below is a shape that occurs in the 2026-10-13 Codex lean run's archives (76 rollouts, 1,241 commands).

SHELL_CLASS = [
    ("Get-Content docs/ai-forward-pack/codex.md; Get-Content x.md; git status --short", "read", ("docs/ai-forward-pack/codex.md", "x.md")),
    ("Get-Content a.py | Select-Object -Skip 10 -First 5", "read", ("a.py",)),
    ("rg --files vendor/quotakit src tests; Get-Content pyproject.toml -ErrorAction SilentlyContinue", "read",
     ("vendor/quotakit", "src", "tests", "pyproject.toml")),
    ("rg -l TODO", "read", ()),  # a read that names no path
    ("# Intent: read the guide\nGet-Content README.md", "read", ("README.md",)),  # a comment line is not a statement
    ("Get-Content a.py; python -m pytest tests -q", "test", ("a.py",)),
    ("python -m pytest tests/test_limiter.py -q", "test", ()),
    ("$env:PYTHONPATH = 'src;vendor/quotakit'; python -m pytest tests/test_limiter.py -q", "test", ()),
    ("py -3.12 -m pytest humanfriendly/tests.py -q", "test", ()),
    ("uv run --python 3.9 --with-requirements requirements-tests.txt python -m pytest humanfriendly/tests.py", "test", ()),
    ("wsl -d Ubuntu-24.04 --cd /mnt/c/x python3 -m pytest tests -q", "test", ()),
    (".tox/format-dollars/Scripts/python.exe -m pytest humanfriendly/tests.py -k format_dollars -q", "test", ()),
    ("python -W error::ResourceWarning -m unittest test.test_taskboard -q", "test", ()),
    ("python tests/test_notes.py", "test", ()),
    ("dotnet test; go test ./...; cargo test; npm test; pnpm run test", "test", ()),
    ("python -m pytest --version", "other", ()),  # asks for the version; runs no test
    ("Remove-Item -LiteralPath .agents/log/x.txt, .agents/log/y.txt", "edit", ()),
    ("Move-Item -LiteralPath .agents/log/audit/.run-starts.json -Destination docs/audit/.run-starts.json", "edit", ()),
    ("Copy-Item -LiteralPath docs/t.template.html -Destination docs/index.html", "edit", ()),
    ("New-Item -ItemType File -Path notes/a.txt", "edit", ()),
    ("Set-Content notes/a.txt 'x'", "edit", ()),
    ("Get-Content a.py | Set-Content b.py", "edit", ()),  # a write at the end of a pipeline is not a read
    ("echo hi > out.txt", "edit", ()),
    ("sed -i s/a/b/ f.py", "edit", ()),
    ("Get-Content a.py; Set-Content b.py x", "edit", ("a.py",)),
    ("python -c \"open('a.txt', 'w').write('x')\"", "edit", ()),
    (r"Remove-Item $env:TEMP\scratch", "other", ()),  # unknown or outside target: never an edit
    (r"Remove-Item C:\tmp\scratch", "other", ()),
    ("New-Item -ItemType Directory -Path docs/audit -Force | Out-Null", "other", ()),
    ("git status --short; git diff --check", "other", ()),
    ("python docs/ai-forward-pack/scripts/audit-log.py start --help", "other", ()),
    ("python -c 'import cachetools'", "other", ()),
    ("if (Test-Path x) { Write-Output y }", "other", ()),
    ("Get-Content 'unbalanced", "other", ()),
    ("", "other", ()),
    (None, "other", ()),
]


def test_a_shell_command_is_one_of_read_edit_test_or_other_with_the_paths_its_reads_name():
    assert [(c, *codex.shell_command_class(c)) for c, _, _ in SHELL_CLASS] == SHELL_CLASS


def test_an_exec_call_batching_several_commands_names_them_all_and_unescapes_the_javascript_string(tmp_path):
    """Observed in the lean run: 297 of 955 `exec` calls hold two to five commands (Promise.allSettled batches)."""
    record = tmp_path / "r.jsonl"
    js = (r'const r = await Promise.allSettled([tools.exec_command({cmd:"Get-Content tests\\a.py"}), '
          r'tools.exec_command({cmd:"# why\nrg -n Gate vendor/q\npython -m pytest -q"})]);')  # JS source: \\ and \n escapes
    record.write_text(json.dumps({"type": "response_item", "payload": {
        "type": "custom_tool_call", "call_id": "c1", "name": "exec", "input": js}}) + "\n", encoding="utf-8")
    (call,) = codex.tool_inputs(record).calls
    assert call.command == "Get-Content tests" + chr(92) + "a.py\n# why\nrg -n Gate vendor/q\npython -m pytest -q"
    assert codex.shell_command_class(call.command) == ("test", ("tests" + chr(92) + "a.py", "vendor/q"))
