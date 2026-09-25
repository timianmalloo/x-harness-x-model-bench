"""gate_runs_root: HB_GATE_RUNS, else the primary checkout's runs/, else ROOT / "runs"."""

import subprocess

import archived_runs


def test_unset_hb_gate_runs_uses_the_primary_checkouts_runs_folder(monkeypatch, tmp_path):
    """A linked worktree must not skip the gate runs that live on the main checkout."""
    monkeypatch.delenv("HB_GATE_RUNS", raising=False)
    primary = tmp_path / "primary-checkout"
    linked = tmp_path / "linked-worktree"
    porcelain = (
        f"worktree {primary.as_posix()}\n"
        "HEAD aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa\n"
        "branch refs/heads/main\n"
        "\n"
        f"worktree {linked.as_posix()}\n"
        "HEAD bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb\n"
        "branch refs/heads/w3-gateruns\n"
        "\n"
    )
    seen = {}

    def fake_run(args, **kwargs):
        seen["args"] = list(args)
        seen["timeout"] = kwargs.get("timeout")
        return subprocess.CompletedProcess(args, 0, stdout=porcelain, stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)
    assert archived_runs.gate_runs_root() == primary / "runs"
    assert seen["args"] == ["git", "worktree", "list", "--porcelain"]
    assert seen["timeout"] == 30
