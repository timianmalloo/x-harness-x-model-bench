"""T-SWEEP-1: exact archive-reader inventory and broad-glob red fixture."""

import ast
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src/harness_bench"
READERS = {"engine.py", "grade/runner.py", "report/credentials.py", "report/judges.py",
           "report/pack_improvement.py", "report/summaries.py", "report/html.py", "resume.py", "views.py"}
ANNOTATION = {"grade/__init__.py"}
GIT_ARCHIVE = {"grade/_changes.py", "workspace.py"}


def archive_readers(sources):
    """Root src/harness_bench, recursive *.py; exact archive path and helper tokens.

    archive.py is the path producer. Annotation and git-archive sources are
    named exceptions, not readers. AST literals avoid matching comments.
    """
    found = set()
    for name, source in sources.items():
        if name == "archive.py" or name in ANNOTATION | GIT_ARCHIVE:
            continue
        tree = ast.parse(source)
        if any(isinstance(n, ast.Constant) and isinstance(n.value, str) and n.value == "archive"
               or isinstance(n, ast.Attribute) and n.attr in {"attempt_dirs", "snapshot_folder"}
               for n in ast.walk(tree)):
            found.add(name)
    return found


def broad_archive_globs(source):
    tree = ast.parse(source)
    archive_access = any(isinstance(n, ast.Constant) and n.value == "archive" for n in ast.walk(tree))
    return archive_access and any(isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                                  and n.func.attr in {"glob", "rglob"} and n.args
                                  and isinstance(n.args[0], ast.Constant) and n.args[0].value == "*"
                                  for n in ast.walk(tree))


def test_t_sweep_1_guard_detects_unknown_reader_and_broad_glob():
    fixture = 'folder = run / "archive" / cid\nfiles = folder.glob("*")\n'
    assert archive_readers({"new_reader.py": fixture}) == {"new_reader.py"}
    assert broad_archive_globs(fixture)
    assert not broad_archive_globs('folder = run / "archive"\nfiles = folder.glob("attempt-*")')


def test_t_sweep_1_exact_reader_and_exception_set():
    sources = {p.relative_to(SRC).as_posix(): p.read_text(encoding="utf-8") for p in SRC.rglob("*.py")}
    assert archive_readers(sources) == READERS
    assert len(READERS) == 9
    assert ANNOTATION | GIT_ARCHIVE <= sources.keys()
