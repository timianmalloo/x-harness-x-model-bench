"""The synthetic agent and the one overlay path rule (W1-E sections 5.1 and 6; T-E2 unit form, T-E3 agent side).

The agent is run as the real script in a real process, as the engine runs it; no function of it is faked.
"""

import json
import subprocess
import sys
from pathlib import Path

import pytest

from harness_bench import synthetic_agent as sa
from harness_bench.grade import _env

pytestmark = pytest.mark.skipif(sys.platform != "win32", reason="the junction fixtures are Windows-only (the grader is)")
AGENT = Path(sa.__file__)
HANDSHAKE = [{"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": 1}},
             {"jsonrpc": "2.0", "id": 2, "method": "session/new", "params": {"cwd": ".", "mcpServers": []}},
             {"jsonrpc": "2.0", "id": 3, "method": "session/prompt", "params": {"sessionId": "s", "prompt": [{"type": "text", "text": "go"}]}}]
UNSAFE = ["/abs/x.py", "C:foo", "\\foo", "../x", "a/../x", "a//b", "", ".git/x", ".git", "a:b", "app.py.", "x ", "aux.py", "nul",
          "NUL", "com1", "lpt9.log", "sub/con.txt"]
CONTROLS = ["inj-1", "null", "con-1", "pkg/app.py", "a.b/c_d-e.py"]


def junction(link: Path, target: Path) -> None:
    import _winapi  # raises if the junction cannot be made: the test fails rather than skips (T-E3)

    _winapi.CreateJunction(str(target), str(link))


def drive(cwd: Path, overlay: Path) -> subprocess.CompletedProcess:
    env = _env.grading_env() | {"HB_SYNTH_OVERLAY": str(overlay)}
    return subprocess.run([sys.executable, str(AGENT)], input="".join(json.dumps(m) + "\n" for m in HANDSHAKE).encode(),
                          capture_output=True, cwd=cwd, env=env, timeout=60, check=False, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))


def tree(base: Path, files: dict[str, str]) -> Path:
    base.mkdir(parents=True, exist_ok=True)
    for rel, text in files.items():
        (base / rel).parent.mkdir(parents=True, exist_ok=True)
        (base / rel).write_text(text, encoding="utf-8")
    return base


@pytest.mark.parametrize("rel", UNSAFE)
def test_safe_relpath_refuses_each_unsafe_form(rel):
    with pytest.raises(sa.OverlayError):
        sa.safe_relpath(rel)


@pytest.mark.parametrize("rel", CONTROLS)
def test_safe_relpath_accepts_the_controls(rel):
    assert sa.safe_relpath(rel).as_posix() == rel


def test_overlay_files_refuses_a_junction_a_dot_git_folder_and_an_oversize_tree(tmp_path):
    ok = tree(tmp_path / "ok", {"pkg/app.py": "x\n"})
    assert sa.overlay_files(ok) == [Path("pkg/app.py")]
    outside = tree(tmp_path / "outside", {"leak.py": "x\n"})
    linked = tree(tmp_path / "linked", {"keep.py": "x\n"})
    junction(linked / "j", outside)
    with pytest.raises(sa.OverlayError, match="link|reparse"):
        sa.overlay_files(linked)
    with pytest.raises(sa.OverlayError, match=r"\.git"):
        sa.overlay_files(tree(tmp_path / "git", {".git/config": "x\n"}))
    many = tmp_path / "many"
    many.mkdir()
    for i in range(sa.MAX_FILES + 1):
        (many / f"f{i}.txt").write_bytes(b"")
    with pytest.raises(sa.OverlayError, match="files"):
        sa.overlay_files(many)
    big = tree(tmp_path / "big", {})
    (big / "b.bin").write_bytes(b"0" * (sa.MAX_BYTES + 1))
    with pytest.raises(sa.OverlayError, match="bytes"):
        sa.overlay_files(big)


def test_the_agent_copies_replaces_adds_and_deletes_nothing(tmp_path):
    ws = tree(tmp_path / "ws", {"pkg/app.py": "A\n", "keep.txt": "keep\n"})
    overlay = tree(tmp_path / "ov", {"pkg/app.py": "B\n", "pkg/new.py": "N\n"})
    done = drive(ws, overlay)
    assert done.returncode == 0, done.stderr
    assert b"end_turn" in done.stdout
    assert {p.relative_to(ws).as_posix(): p.read_text(encoding="utf-8") for p in ws.rglob("*") if p.is_file()} == {
        "pkg/app.py": "B\n", "pkg/new.py": "N\n", "keep.txt": "keep\n"}


@pytest.mark.parametrize("form", ["dot-git", "junction"])
def test_the_real_agent_refuses_a_bad_overlay_and_copies_nothing(tmp_path, form):
    ws = tree(tmp_path / "ws", {"keep.txt": "keep\n"})
    outside = tree(tmp_path / "outside", {"leak.py": "x\n"})
    overlay = tree(tmp_path / "ov", {"good.py": "G\n"})
    if form == "dot-git":
        tree(overlay, {".git/hooks": "x\n"})
    else:
        junction(overlay / "j", outside)
    done = drive(ws, overlay)
    assert done.returncode != 0
    assert b"end_turn" not in done.stdout
    assert sorted(p.name for p in ws.iterdir()) == ["keep.txt"]


def test_the_agent_refuses_a_link_already_in_the_working_copy(tmp_path):
    """SEC 3: a pinned base tree can hold a junction; an overlay file under it must not be written through it."""
    ws = tree(tmp_path / "ws", {"keep.txt": "keep\n"})
    outside = tree(tmp_path / "outside", {})
    junction(ws / "a", outside)
    done = drive(ws, tree(tmp_path / "ov", {"a/b.py": "B\n"}))
    assert done.returncode != 0
    assert list(outside.iterdir()) == []
