"""STUB for the red commit; replaced by the tool in the next commit."""


def run_repro(node, runs, out, prefix=None, cwd=None):
    import json
    from pathlib import Path

    Path(out).write_text(json.dumps({"node": node, "n": runs, "failures": 0, "rate": 0.0, "failure_list": [], "wall_s": [], "base_sha": ""}), encoding="utf-8")
