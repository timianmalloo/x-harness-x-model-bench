"""ADR-0023 Amendment 2: SV1's report-time facts for the lean summary (`report/supervision.py`).

The native-record check (plan row B6's gap): the working tree cannot see a check that reads `job-run/` directly instead
of running `job.py status`. The fixtures are `ToolInput`s shaped as the readers emit them on the 2026-10-13 lean runs
(opened, not recalled): Claude Code's `PowerShell` command text and `Read` with an absolute Windows path, Codex's
`exec` command with the paths it names, Copilot's `powershell` command text.
"""

from pathlib import Path

from harness_bench import lean, views
from harness_bench.report import supervision
from harness_bench.telemetry import ToolInput

WS = r"C:\Projects\bench-cells\run\run\c1\ws"


def test_job_calls_count_status_runs_and_direct_job_run_touches_from_the_tool_inputs():
    calls = [
        ToolInput(1, "PowerShell", (), "python job.py start", False),  # neither
        ToolInput(2, "PowerShell", (), "Start-Sleep -Seconds 61; python job.py status", False),  # Claude Code
        ToolInput(3, "Read", (rf"{WS}\job-run\state.json",), None, False),  # Claude Code reads the state file
        ToolInput(4, "exec", ("job-run/state.json",), "Get-Content job-run/state.json", False),  # Codex: one call
        ToolInput(5, "powershell", (), r"python .\job.py status", False),  # Copilot
        ToolInput(6, "powershell", (), "python job.py --help; Get-ChildItem", False),  # neither
    ]
    assert supervision.job_calls(calls) == (2, 2)
    assert supervision.job_calls([]) == (0, 0)


def test_measures_not_in_the_log_read_not_recorded_with_the_reason():
    assert supervision.parse_measures("exit 0\n--- stderr\nRan 6 tests in 0.1s\n\nOK\n", "SV1") == (
        None, "no SV1-MEASURES line in oracle.log")
    assert supervision.parse_measures("SV1-MEASURES {not json\n", "SV1") == (
        None, "the SV1-MEASURES line is not a JSON object")
    assert supervision.parse_measures('SV1-MEASURES {"status_checks": 3}\n', "SV1") == ({"status_checks": 3}, None)


def _cell(cell_id: str, task: str, harness: str, evidence: dict, scores: dict | None = None) -> views.CellView:
    na = views.Measure(None, "x")
    return views.CellView(cell_id=cell_id, task=task, rep=1, label=cell_id, combo=harness, arm="off", harness=harness,
                          model="m", outcome="completed", cause=None, code=None, validity="valid", validity_code=None,
                          wall_ms=na, model_ms=na, tool_ms=na, idle_ms=na, tokens=None, tokens_reason=None,
                          scores=scores or {}, evidence=evidence, extraction_id="x1")


def test_facts_read_each_sv1_cells_oracle_line_and_say_why_a_native_count_is_not_recorded(tmp_path: Path):
    log = "grading/g1/sv-grok/correctness/oracle.log"
    (tmp_path / log).parent.mkdir(parents=True)
    (tmp_path / log).write_text('--- stderr\nSV1-MEASURES {"early_checks": 0, "status_checks": 4}\nRan 6 tests\n',
                                encoding="utf-8")
    # A harness with no tool-input reader (every bench harness has one since tracks W3/W4).
    cells = [_cell("sv-grok", "SV1", "x-no-reader", {"pass_at_1": log}),
             _cell("sv-cc", "SV1", "claude-code", {}, {"pass_at_1": views.Measure(None, "no working copy in the archive")}),
             _cell("s1-cc", "S1", "claude-code", {})]
    plan = {"tasks": {"SV1": {"graders": ["correctness", "process"]}, "S1": {"graders": ["correctness", "property"]}},
            "profiles": {}}
    view = views.RunView("run", plan, True, "g1", "0.8", cells, run_dir=tmp_path)
    facts = supervision.facts(view)
    assert set(facts) == {"sv-grok", "sv-cc"}
    assert facts["sv-grok"] == lean.SupervisionFacts({"early_checks": 0, "status_checks": 4}, None, None, None,
                                                     "no tool-input reader for x-no-reader")
    assert facts["sv-cc"] == lean.SupervisionFacts(None, "no working copy in the archive", None, None,
                                                   "no native record in the archive")
