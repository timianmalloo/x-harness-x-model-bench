"""R-DERIV: the shared tool-phase classifier and the carry rule (ADR-0026 s4), one definition each.

The phase rule, as ADR-0026 s4 states it: `edit` for an edit-class tool or a write; `verify` for a command matching
the declared test and lint patterns; `explore` for read, search and list tools and other commands before the first
edit; `other` for the rest. `pack_improvement`'s existing categories come from the same `classify`.
"""

from harness_bench.report import pack_improvement, tool_phases
from harness_bench.telemetry import ToolInput


def _t(n, name, paths=(), command=None, is_write=False, returned=None):
    return ToolInput(n, name, tuple(paths), command, is_write, returned)


# A hand-classified sequence, one harness's names each; the comment is the hand classification under the rule.
SEQUENCE = (
    _t(1, "Read", ["src/a.py"]),                        # explore: a read tool
    _t(2, "Bash", command="git log --oneline -3"),      # explore: another command before the first edit
    _t(3, "TodoWrite"),                                 # other: not a command, not a read, not an edit
    _t(4, "Bash", command="uv run pytest -q"),          # verify: a declared test pattern, before the edit too
    _t(5, "Edit", ["src/a.py"], is_write=True),         # edit: an edit-class write (the first edit)
    _t(6, "Bash", command="git diff"),                  # other: a command after the first edit
    _t(7, "Grep", ["src"]),                             # explore: a search tool, after the edit too
    _t(8, "Bash", command="ruff check src"),            # verify: a declared lint pattern
    _t(9, "apply_patch", ["src/b.py"]),                 # edit: an edit-class tool even when is_write is unset
    _t(10, "view", ["src/b.py"]),                       # explore: Copilot's read tool
    _t(11, "shell", command="cat src/a.py"),            # explore: a Codex shell read (shell_read_kind "read")
)
HAND = ("explore", "explore", "other", "verify", "edit", "other", "explore", "verify", "edit", "explore", "explore")


def test_phase_counts_on_a_fixture_sequence_equal_the_hand_classification():
    assert tool_phases.phases(SEQUENCE) == HAND
    assert tool_phases.phase_counts(SEQUENCE) == {"explore": 5, "edit": 2, "verify": 2, "other": 2}


def test_an_empty_sequence_has_no_phases_and_zero_counts():
    assert tool_phases.phases(()) == ()
    assert tool_phases.phase_counts(()) == dict.fromkeys(tool_phases.PHASES, 0)


def test_verify_matches_a_declared_pattern_as_a_word_never_a_substring():
    assert tool_phases.phases((_t(1, "Bash", command="python -m unittest -v"),)) == ("verify",)
    assert tool_phases.phases((_t(1, "Bash", command="echo pytestish"),)) == ("explore",)


def test_pack_improvement_categories_come_from_the_same_function():
    assert pack_improvement.classify is tool_phases.classify
    write = _t(1, "Write", ["tests/test_a.py"], is_write=True)
    assert tool_phases.classify(write, ["src/*"]) & {"test_write", "product_write"} == {"test_write"}


def test_re_reads_count_a_path_read_again_with_no_edit_to_it_in_between():
    calls = (_t(1, "Read", ["a.py"]), _t(2, "Read", ["a.py"]),            # re-read 1
             _t(3, "Edit", ["a.py"], is_write=True), _t(4, "Read", ["a.py"]),  # an edit in between: not a re-read
             _t(5, "Read", ["b.py"]), _t(6, "Edit", ["a.py"], is_write=True), _t(7, "Read", ["b.py"]))  # re-read 2
    assert tool_phases.rereads(calls) == 2


def test_bytes_returned_is_the_sum_or_not_recorded_never_a_partial_sum():
    assert tool_phases.bytes_returned((_t(1, "shell", returned=10), _t(2, "shell", returned=5))).value == 15
    partial = tool_phases.bytes_returned((_t(1, "shell", returned=10), _t(2, "Read")))
    assert partial.value is None and partial.reason == tool_phases.NO_BYTES
    assert tool_phases.bytes_returned(()).value is None


def test_carry_until_compaction_counts_each_entry_on_every_later_request_until_a_compaction():
    assert tool_phases.carry_until_compaction((5, 3, 2, 4), ()) == (5, 8, 10, 14)
    assert tool_phases.carry_until_compaction((5, 3, 2, 4), (2,)) == (5, 8, 2, 6)  # drops what entered before 2
    assert tool_phases.carry_until_compaction((), ()) == ()
