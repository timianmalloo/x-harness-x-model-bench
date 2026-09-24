"""Red-observation by targeted mutation: remove one guard at a time and require a named test to fail.

Each mutation is (file, exact text, replacement, named tests). The file is restored byte for byte afterwards, even
on error. A mutation is **killed** only when pytest exits 1 and one of its named tests (a node id, or a test file
meaning any test in it) is among the failures. A failure of some other test, a collection error, or a timeout is
not evidence that this guard is tested, so it is reported as survived, error or timeout. Exit 0 only if every
mutation is killed.

Usage: python tools/mutate_check.py <mutations.json>
"""

import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FAILED = re.compile(r"^FAILED (\S+)", re.MULTILINE)


def verdict(returncode: int | None, output: str, named: list[str]) -> str:
    """killed | survived | error | timeout, from one pytest run of the named tests."""
    if returncode is None:
        return "timeout"
    if returncode not in (0, 1):
        return "error"
    failed = FAILED.findall(output)
    if returncode == 1 and any(f == n or f.startswith((n + "::", n + "[")) for f in failed for n in named):
        return "killed"
    return "survived"


def main(argv: list[str]) -> int:
    spec = json.loads(Path(argv[0]).read_text(encoding="utf-8"))
    survivors = 0
    for m in spec:
        path = ROOT / m["file"]
        original = path.read_bytes()
        text = original.decode("utf-8").replace("\r\n", "\n")
        if m["find"] not in text:
            print(f"SKIP     {m['name']}: text not found", flush=True)
            survivors += 1
            continue
        try:
            path.write_bytes(text.replace(m["find"], m["replace"], 1).encode("utf-8"))
            try:
                result = subprocess.run([sys.executable, "-m", "pytest", "-q", "-rf", "-p", "no:cacheprovider", *m["tests"]],
                                        cwd=ROOT, capture_output=True, text=True, check=False, timeout=m.get("timeout", 180))
                outcome = verdict(result.returncode, result.stdout + result.stderr, m["tests"])
            except subprocess.TimeoutExpired:
                outcome = "timeout"
            print(f"{outcome:<8} {m['name']}", flush=True)
            survivors += 0 if outcome == "killed" else 1
        finally:
            path.write_bytes(original)
    print(f"{survivors} not killed" if survivors else "every mutation killed", flush=True)
    return 1 if survivors else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
