"""B10: a cell's folder must not repeat the run id, so Copilot's own path verification stays under MAX_PATH.

Measured (lean runs of 2026-10-13, Copilot `session-state/<id>/events.jsonl` `promptRequest` kind `path`): with the
cells root `C:\\Projects\\bench-cells\\<run id>` the cell folder was `...\\<run id>\\<run id>\\<cell id>`, and Copilot's
own file under `home\\session-state\\<session id>\\files\\` reached 261 characters, so its verification denied the call.
"""

from pathlib import Path, PureWindowsPath

from harness_bench import archive, workspace

RUN_ID_MAX = 64  # status.RUN_ID: [A-Za-z0-9][A-Za-z0-9._-]{0,63}
CELLS_ROOT = PureWindowsPath(r"C:\Projects\bench-cells")  # the lean prompt's CELLS prefix
CELL_ID = "0123456789abcdef"  # 16 hex, the longest cell id (config.CELL_ID)
SESSION_ID = "6c2fc5e1-4b08-498e-917e-1541c61acf5e"
MAX_PATH = 260
MODEL_SUBPATH = 70  # what the model picks under files/ (seen: 46, `limiter-dist\cachetools-7.2.0-py3-none-any.whl`)
MARGIN = 10


def test_a_cells_root_named_for_the_run_holds_the_cells_directly(tmp_path):
    run_cells = tmp_path / "run-1"
    assert workspace.cell_dir(run_cells, "run-1", "abc") == run_cells / "abc"


def test_a_cells_root_not_named_for_the_run_keeps_the_run_folder(tmp_path):
    assert workspace.cell_dir(tmp_path, "run-1", "abc") == tmp_path / "run-1" / "abc"


def test_an_old_run_folder_is_still_found_under_a_root_named_for_the_run(tmp_path):
    run_cells = tmp_path / "run-1"
    (run_cells / "run-1").mkdir(parents=True)  # a run begun before the layout changed
    assert workspace.cell_dir(run_cells, "run-1", "abc") == run_cells / "run-1" / "abc"


def test_the_worst_case_copilot_files_path_stays_under_max_path_with_a_margin():
    run_id = "lean-20261013T222840-2fc4-" + "x" * (RUN_ID_MAX - len("lean-20261013T222840-2fc4-"))
    assert len(run_id) == RUN_ID_MAX
    cells_root = Path(str(CELLS_ROOT / run_id))
    folder = PureWindowsPath(str(workspace.cell_dir(cells_root, run_id, CELL_ID)))
    files = folder / "home" / "session-state" / SESSION_ID / "files"
    worst = len(str(files)) + 1 + MODEL_SUBPATH
    assert worst <= MAX_PATH - MARGIN, f"{worst} characters: shorten the cell folder layout"


def test_teardown_leaves_the_shared_folders_of_a_cells_root_named_for_the_run(tmp_path):
    root = tmp_path / "run-1"
    for name in ("abc", "def", "grading", ".sources"):
        (root / name).mkdir(parents=True)
    removed, kept = archive.teardown(root, {"abc"}, only={"abc", "def"})
    assert (removed, kept) == (["abc"], ["def"])
    assert (root / "grading").is_dir() and (root / ".sources").is_dir() and not (root / "abc").exists()
