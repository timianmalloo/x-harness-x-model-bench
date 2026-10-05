"""Publish-site scan (W1-B §10.4). ALLOWED is this tree after `_land` calls `rename_with_retry`.

The design's base `32548ed9` had 12 sites in 11 keys. Two grader `shutil.copytree` keys
(`grade.correctness.grade`, `grade.formal._grading_copy`) are already gone: those callers use
`grade._changes.copy_tree`, which is the one remaining grader copy.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parents[1] / "src" / "harness_bench"

_VERBS = {
    ("os", "link"): "os.link",
    ("os", "rename"): "os.rename",
    ("os", "replace"): "os.replace",
    ("os", "open"): "os.open",
    ("shutil", "move"): "shutil.move",
    ("shutil", "copytree"): "shutil.copytree",
}
_METHOD_VERBS = {"rename": "Path.rename", "hardlink_to": "Path.hardlink_to"}

# Key is (module, function, verb). `workspace._land` · `os.replace` is absent on purpose:
# the stale-entry check turns red while `_land` still calls `os.replace`.
ALLOWED: dict[tuple[str, str, str], str] = {
    ("cli", "_write_control", "os.replace"):
        "stage-then-os.replace of a control file; a reader sees a complete file or nothing",
    ("engine", "_read_controls", "Path.replace"):
        "renames a rejected control file to .rejected; a quarantine, not a published name",
    ("gateway/store", "write_once", "os.link"):
        "stage-then-link with its own race-loser contract",
    ("gateway/store", "move_orphan", "os.rename"):
        "moves an orphaned entry to orphaned/; a quarantine, not a publish",
    ("grade/_changes", "copy_tree", "shutil.copytree"):
        "grader scratch copy; the publish of a cell is not this tree",
    ("workspace", "task_source", "shutil.copytree"):
        "copies into the tmp build that _land then publishes",
    ("archive", "snapshot_cell", "shutil.copytree"):
        "W1-J K2 skeleton only; J1c removes this entry when snapshot_cell uses publish_dir",
    ("oslock", "acquire", "os.open"):
        "the lock file; no content is written, so no O_BINARY is required",
    ("oslock", "is_held", "os.open"):
        "the lock file; no content is written, so no O_BINARY is required",
    ("grade/bench_check", "_host", "os.open"):
        "the probe host's stdin from os.devnull, read-only; nothing is written or published",
}


@dataclass(frozen=True)
class Hit:
    module: str
    function: str
    verb: str
    lineno: int


def _binds(aliases: dict[str, tuple], node: ast.AST) -> None:
    if isinstance(node, ast.Import):
        for alias in node.names:
            if alias.asname:
                aliases[alias.asname] = ("module", alias.name)
            else:
                aliases[alias.name.split(".", 1)[0]] = ("module", alias.name.split(".", 1)[0])
    elif isinstance(node, ast.ImportFrom) and node.module:
        for alias in node.names:
            if alias.name == "*":
                continue
            aliases[alias.asname or alias.name] = ("attr", node.module, alias.name)


def _has_name(node: ast.AST, name: str) -> bool:
    return any(isinstance(child, ast.Name) and child.id == name for child in ast.walk(node))


def _method_verb(func: ast.Attribute, call: ast.Call) -> str | None:
    if func.attr in _METHOD_VERBS:
        return _METHOD_VERBS[func.attr]
    if func.attr == "replace" and len(call.args) == 1 and not call.keywords:
        return "Path.replace"
    return None


def _verb_of(func: ast.AST, aliases: dict[str, tuple], call: ast.Call) -> str | None:
    if isinstance(func, ast.Name):
        bound = aliases.get(func.id)
        if bound and bound[0] == "attr":
            return _VERBS.get((bound[1], bound[2]))
        return None
    if not isinstance(func, ast.Attribute):
        return None
    if isinstance(func.value, ast.Name):
        bound = aliases.get(func.value.id)
        if bound and bound[0] == "module":
            return _VERBS.get((bound[1], func.attr))
    return _method_verb(func, call)


def _verify_arg(call: ast.Call) -> ast.AST | None:
    if len(call.args) >= 3:
        return call.args[2]
    for keyword in call.keywords:
        if keyword.arg == "verify":
            return keyword.value
    return None


class _Scanner(ast.NodeVisitor):
    def __init__(self, module: str) -> None:
        self.module = module
        self.aliases: dict[str, tuple] = {}
        self._alias_stack: list[dict[str, tuple]] = []
        self._functions = ["<module>"]
        self._assigned: list[dict[str, ast.AST]] = [{}]
        self.hits: list[Hit] = []
        self.bare_opens: list[Hit] = []
        self.verify_problems: list[str] = []

    def visit_Import(self, node: ast.Import) -> None:
        _binds(self.aliases, node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        _binds(self.aliases, node)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._enter(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._enter(node)

    def _enter(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        self._functions.append(node.name)
        self._alias_stack.append(self.aliases)
        self.aliases = dict(self.aliases)
        self._assigned.append({})
        self.generic_visit(node)
        self._assigned.pop()
        self.aliases = self._alias_stack.pop()
        self._functions.pop()

    def visit_Assign(self, node: ast.Assign) -> None:
        self.visit(node.value)
        if len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            self._assigned[-1][node.targets[0].id] = node.value

    def _flags_name_binary(self, arg: ast.AST | None, depth: int = 0) -> bool:
        if arg is None or depth > 8:
            return False
        if _has_name(arg, "O_BINARY"):
            return True
        if isinstance(arg, ast.Name):
            for scope in reversed(self._assigned):
                if arg.id in scope:
                    return self._flags_name_binary(scope[arg.id], depth + 1)
        return False

    def visit_Call(self, node: ast.Call) -> None:
        verb = _verb_of(node.func, self.aliases, node)
        if verb:
            hit = Hit(self.module, self._functions[-1], verb, node.lineno)
            self.hits.append(hit)
            if verb == "os.open" and self.module == "atomic":
                flags = node.args[1] if len(node.args) > 1 else None
                if not self._flags_name_binary(flags):
                    self.bare_opens.append(hit)
        func = node.func
        is_publish = (isinstance(func, ast.Name) and func.id == "publish_dir") or (
            isinstance(func, ast.Attribute) and func.attr == "publish_dir"
        )
        if is_publish:
            verify = _verify_arg(node)
            if not isinstance(verify, ast.Name | ast.Attribute):
                self.verify_problems.append(f"{self.module}:{node.lineno}")
        self.generic_visit(node)


def scan(root: Path) -> tuple[list[Hit], list[Hit], list[str]]:
    hits: list[Hit] = []
    bare: list[Hit] = []
    problems: list[str] = []
    for path in sorted(root.rglob("*.py")):
        if "__pycache__" in path.parts:
            continue
        module = path.relative_to(root).with_suffix("").as_posix()
        scanner = _Scanner(module)
        scanner.visit(ast.parse(path.read_text(encoding="utf-8")))
        hits.extend(scanner.hits)
        bare.extend(scanner.bare_opens)
        problems.extend(scanner.verify_problems)
    return hits, bare, problems


def _outside_atomic(hits: list[Hit]) -> set[tuple[str, str, str]]:
    return {(hit.module, hit.function, hit.verb) for hit in hits if hit.module != "atomic"}


def test_every_publish_call_site_is_classified() -> None:
    hits, bare, problems = scan(SRC)
    keys = _outside_atomic(hits)
    allowed = set(ALLOWED)
    assert keys == allowed, f"unlisted {sorted(keys - allowed)}; stale {sorted(allowed - keys)}"
    assert bare == [], bare
    assert problems == [], problems


def _write(root: Path, name: str, source: str) -> None:
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(source, encoding="utf-8")


_FORMS = {
    "link.py": "import os\ndef f(a, b):\n    os.link(a, b)\n",
    "rename.py": "import os\ndef f(a, b):\n    os.rename(a, b)\n",
    "replace.py": "import os\ndef f(a, b):\n    os.replace(a, b)\n",
    "move.py": "import shutil\ndef f(a, b):\n    shutil.move(a, b)\n",
    "copytree.py": "import shutil\ndef f(a, b):\n    shutil.copytree(a, b)\n",
    "open.py": "import os\ndef f(a):\n    os.open(a, os.O_RDONLY)\n",
    "imported.py": "from os import replace\ndef f(a, b):\n    replace(a, b)\n",
    "alias.py": "from os import replace as r\ndef f(a, b):\n    r(a, b)\n",
    "shutil_as.py": "import shutil as sh\ndef f(a, b):\n    sh.move(a, b)\n",
    "path_rename.py": "def f(p, q):\n    p.rename(q)\n",
    "path_replace.py": "def f(p, q):\n    p.replace(q)\n",
    "hardlink.py": "def f(p, q):\n    p.hardlink_to(q)\n",
}
_NEGATIVES = {
    "str_replace.py": "def f():\n    return 'a'.replace('b', 'c')\n",
    "bytes_replace.py": "def f():\n    return b''.replace(b'a', b'b')\n",
    "dataclass_replace.py": "import dataclasses\ndef f(x):\n    return dataclasses.replace(x, f=1)\n",
}


def test_the_scan_flags_every_verb_and_alias_form(tmp_path: Path) -> None:
    root = tmp_path / "tree"
    for name, source in {**_FORMS, **_NEGATIVES}.items():
        _write(root, name, source)
    hits, _, _ = scan(root)
    by_module = {hit.module: hit.verb for hit in hits}
    assert by_module.keys() == {Path(name).stem for name in _FORMS}
    assert len(hits) == len(_FORMS)
    assert by_module["imported"] == "os.replace"
    assert by_module["alias"] == "os.replace"
    assert by_module["shutil_as"] == "shutil.move"
    assert by_module["path_rename"] == "Path.rename"
    assert by_module["path_replace"] == "Path.replace"
    assert by_module["hardlink"] == "Path.hardlink_to"


def test_a_stale_or_unlisted_entry_fails(tmp_path: Path) -> None:
    root = tmp_path / "tree"
    _write(root, "cli.py", "import os\ndef _write_control(a, b):\n    os.replace(a, b)\n")
    hits, _, _ = scan(root)
    keys = _outside_atomic(hits)
    missing = set()
    with pytest.raises(AssertionError, match="unlisted"):
        assert keys == missing, f"unlisted {sorted(keys - missing)}; stale {sorted(missing - keys)}"
    extra = {("cli", "_write_control", "os.replace"), ("ghost", "nowhere", "os.link")}
    with pytest.raises(AssertionError, match="stale"):
        assert keys == extra, f"unlisted {sorted(keys - extra)}; stale {sorted(extra - keys)}"

    _write(
        root,
        "pub.py",
        "def fill(p):\n    return None\n"
        "def run(final):\n"
        "    publish_dir(final, lambda p: None, fill)\n"
        "def run_none(final):\n"
        "    publish_dir(final, fill, verify=None)\n",
    )
    _, _, problems = scan(root)
    assert any(item.startswith("pub:") for item in problems), problems


def test_a_losing_land_reuses_the_winners_valid_dest_and_leaves_it_untouched(tmp_path, monkeypatch):
    """The race loser's rename fails with a non-PermissionError (POSIX ENOTEMPTY onto the winner's
    folder), so `rename_with_retry` re-raises. `_land` must hand back the winner's valid dest, not raise,
    rebuild or overwrite it."""
    import errno

    from harness_bench import workspace

    tmp, dest = tmp_path / "loser", tmp_path / "dest"
    (tmp / ".git").mkdir(parents=True)
    (dest / ".git").mkdir(parents=True)
    (dest / "winner").write_text("w", encoding="utf-8")

    def lost(src, dst):
        raise OSError(errno.ENOTEMPTY, "Directory not empty")

    monkeypatch.setattr(workspace.os, "replace", lost)
    assert workspace._land(tmp, dest, lambda d: (d / ".git").is_dir()) == dest
    assert (dest / "winner").read_text(encoding="utf-8") == "w"
    assert tmp.exists()
