"""Negative controls for D2's hidden tests: each mutant of the reference must fail at least one
hidden test."""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

from harness_bench.config import load_yaml
from harness_bench.grade.correctness import grade

RULE = "src/AiDe.Core/Extraction/ImportOriginRule.cs"

MUTANTS = {  # name: (file, original text, mutated text)
    "python-relative-ignored": (
        RULE,
        "? specifier.StartsWith('.')",
        "? false",
    ),
    "node-absolute-path-not-relative": (
        RULE,
        "|| specifier.StartsWith('/');",
        ";",
    ),
    "builtin-checked-after-workspace": (
        RULE,
        "        var isBuiltin = isPython ? PythonStandardLibrary.Contains(specifier) : NodeBuiltinModules.Contains(specifier);\n"
        "        if (isBuiltin)\n"
        "        {\n"
        "            return ImportOrigin.Builtin;\n"
        "        }\n"
        "\n"
        "        return workspaceModuleIds.Contains(specifier) ? ImportOrigin.Workspace : ImportOrigin.External;",
        "        var isBuiltin = isPython ? PythonStandardLibrary.Contains(specifier) : NodeBuiltinModules.Contains(specifier);\n"
        "        if (workspaceModuleIds.Contains(specifier))\n"
        "        {\n"
        "            return ImportOrigin.Workspace;\n"
        "        }\n"
        "\n"
        "        return isBuiltin ? ImportOrigin.Builtin : ImportOrigin.External;",
    ),
    "unknown-language-not-rejected": (
        RULE,
        "        if (language is not (\"python\" or \"node\"))\n"
        "        {\n"
        "            throw new ArgumentException($\"language must be \\\"python\\\" or \\\"node\\\", not \\\"{language}\\\".\", nameof(language));\n"
        "        }\n",
        "",
    ),
    "empty-specifier-not-rejected": (
        RULE,
        "        if (specifier.Length == 0)\n"
        "        {\n"
        "            throw new ArgumentException(\"specifier must not be empty.\", nameof(specifier));\n"
        "        }\n"
        "\n",
        "",
    ),
    "external-and-workspace-swapped": (
        RULE,
        "return workspaceModuleIds.Contains(specifier) ? ImportOrigin.Workspace : ImportOrigin.External;",
        "return workspaceModuleIds.Contains(specifier) ? ImportOrigin.External : ImportOrigin.Workspace;",
    ),
}


def main() -> None:
    task_dir = Path(__file__).resolve().parents[1]
    oracle = load_yaml(task_dir / "task.yaml")["oracle"]
    with tempfile.TemporaryDirectory(prefix="d2-mut-") as scratch:
        run_dir = Path(scratch)
        for name, (rel, old, new) in MUTANTS.items():
            ws = run_dir / f"{name}-ws"
            shutil.copytree(task_dir / "workspace", ws)
            shutil.copytree(task_dir / "oracle" / "reference", ws, dirs_exist_ok=True)
            target = ws / rel
            text = target.read_text(encoding="utf-8")
            if old not in text:
                raise SystemExit(f"{name}: anchor not found in {rel}")
            target.write_text(text.replace(old, new), encoding="utf-8")
            out_dir = run_dir / name
            out_dir.mkdir()
            result = grade(ws, task_dir, oracle, out_dir, run_dir, timeout=300)
            log = (out_dir / "oracle.log").read_text(encoding="utf-8")
            failed = [line.split()[2] for line in log.splitlines() if line.strip().endswith("[FAIL]")]
            print(f"{name}: passed={result.passed} partial={result.partial_credit} reason={result.reason!r} failed={failed}")


if __name__ == "__main__":
    main()
