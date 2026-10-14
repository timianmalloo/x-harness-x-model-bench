"""served_check.py - the readiness probe's checks (ADR-0024 s6, ADR-0025 s7-s8, ADR-0027 s6).

A thin wrapper over the views: validity and its codes come from `views.load`, never re-derived here.

  served_check.py RUN --before SNAPSHOT   exit 1 when any clause fails, 0 when every one passes:
      - a cell is not graded, or has HB-VAL-002 or HB-VAL-010, or HB-VAL-011 on a pinned value;
      - a cell has no `reasoning` row other than `omitted` (every harness can show text, ADR-0026 s1);
      - a pack-on cell has 0 instruction-file `prompt_parts`, or a pack-off cell has any. A harness with no
        `prompt_parts` row in the run reports `not recorded` for both instead (ADR-0024 s6);
      - an archived cell home holds a value of the real or any bench Grok auth.json (ADR-0025 s7, every home of a pool);
      - an archived Copilot debug log holds an `Authorization` or `Bearer` shape (ADR-0024 s6, ADR-0027 s6);
      - a real harness store changed since SNAPSHOT, or no SNAPSHOT was given (fail closed; ADR-0025 s8).
  served_check.py --snapshot OUT          list the real stores (names, sizes, mtimes; never contents).
  served_check.py --refresh-start STATE   the Grok refresh gate's start: the bench token must be expired (its JWT
                                          `exp` is read, never its value); records the auth.json digest. With a pool
                                          the gate reads the first home: sequential cells take it (the first free).
  served_check.py --refresh-finish STATE --grok EXE [ARG ...]
                                          the gate's end: the bench auth.json bytes changed and were written back,
                                          and `grok models` authenticates against the bench home and the real home.
EXIT 0 pass, 1 a failing clause, 2 usage. Output names clauses, paths and counts only, never a token or a record line.
"""

from __future__ import annotations

import argparse
import base64
import binascii
import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path

from harness_bench import profiles, views
from harness_bench.report import credentials, publish

INSTRUCTION_FILE = "instruction_file"
OMITTED = "omitted"
BENCH_HOME_ENV = "HB_GROK_CRED_HOME"
DEBUG_LOG_SHAPES = ("authorization", "bearer")
GROK_MODELS_TIMEOUT = 120
# ADR-0025 s8: the real stores a Grok or agy cell must never write. assume: the "%APPDATA% and %LOCALAPPDATA% harness
# folders" are these names (listed on the operator's machine 2026-10-12); confirm: the development probe lists them
# before and after; breaks: a cell writing another folder is missed (a residual, named in the probe report).
# Claude and Copilot folders are not listed: live coordination sessions write them while a probe runs.
STORES = (("home", ".grok/sessions"), ("home", ".gemini/antigravity-cli/conversations"), ("APPDATA", "Antigravity"),
          ("LOCALAPPDATA", "grok"), ("LOCALAPPDATA", "agy"), ("LOCALAPPDATA", "antigravity"))


def _home(env) -> Path:
    return Path(env.get("USERPROFILE") or env.get("HOME") or Path.home())


def _rel(path: Path, run_dir: Path) -> str:
    return path.relative_to(run_dir).as_posix()


# --- the view clauses -------------------------------------------------------------------------------------------


def cell_failures(view: views.RunView, reasoning: list[dict], parts: list[dict]) -> tuple[list[str], list[str]]:
    """(failing clauses, notes) over the views and the current extraction's reasoning and prompt_parts rows."""
    plan_cells = {c["cell_id"]: c for c in view.plan["cells"]}
    sourced = {c.harness for c in view.cells for r in parts if r["cell_id"] == c.cell_id}
    failures: list[str] = []
    notes = sorted({f"{c.harness}: instruction-file clauses not recorded (no prompt_parts source)"
                    for c in view.cells if c.harness not in sourced})
    for c in view.cells:
        if c.extraction_id is None:
            failures.append(f"{c.label}: {c.validity} (no extraction to check)")
            continue
        if c.validity_code in ("HB-VAL-002", "HB-VAL-010"):
            failures.append(f"{c.label}: {c.validity} ({c.validity_code})")
        plan_cell = plan_cells[c.cell_id]
        for w in c.warnings:
            setting = next((s for s in views.SETTING_FIELDS if w.message.startswith(f"served {s} ")), None)
            if w.code == "HB-VAL-011" and setting and str(plan_cell.get(setting, "default")) != "default":
                failures.append(f"{c.label}: HB-VAL-011 on a pinned {setting}")
        mine = [r for r in reasoning if r["cell_id"] == c.cell_id and r["extraction_id"] == c.extraction_id]
        if not any(r["source_kind"] != OMITTED for r in mine):
            failures.append(f"{c.label}: no reasoning row other than {OMITTED}")
        if c.harness not in sourced:
            continue
        files = sum(1 for r in parts if r["cell_id"] == c.cell_id and r["extraction_id"] == c.extraction_id
                    and r["part"] == INSTRUCTION_FILE)
        arm = c.arm
        if arm == "on" and files == 0:
            failures.append(f"{c.label}: pack-on cell with 0 instruction-file prompt_parts")
        elif arm == "off" and files:
            failures.append(f"{c.label}: pack-off cell with {files} instruction-file prompt_parts")
    return failures, notes


# --- the credential, debug-log and real-store checks ------------------------------------------------------------


def _cell_homes(run_dir: Path) -> list[Path]:
    archive = run_dir / "archive"
    return sorted(archive.glob("*/attempt-*/home")) if archive.is_dir() else []


def _bench_auth(env=os.environ) -> Path | None:
    homes = profiles.credential_homes(env.get(BENCH_HOME_ENV))
    return homes[0] / credentials.BENCH_HOME_FILE if homes else None


def credential_failures(run_dir: Path, env=os.environ) -> list[str]:
    """ADR-0025 s7: no archived cell home holds a value of the real Grok login or of the bench credential home."""
    values = credentials.values_in_file(_home(env) / ".grok" / credentials.BENCH_HOME_FILE)
    for bench in profiles.credential_homes(env.get(BENCH_HOME_ENV)):
        values |= credentials.values_in_file(bench / credentials.BENCH_HOME_FILE)
    if not values:
        return []
    return [f"{_rel(f, run_dir)}: a credential copy left in a cell home" for home in _cell_homes(run_dir)
            for f in sorted(home.rglob(credentials.BENCH_HOME_FILE)) if credentials.values_in_file(f) & values]


def debug_log_failures(run_dir: Path) -> list[str]:
    """ADR-0024 s6: an archived debug log (Copilot's `--log-dir {home}/logs`) with an Authorization or bearer shape."""
    out = []
    for home in _cell_homes(run_dir):
        for f in sorted(p for p in (home / "logs").rglob("*") if p.is_file()):
            n = sum(1 for s in publish.scan_text(f.read_text(encoding="utf-8", errors="ignore")) if s in DEBUG_LOG_SHAPES)
            if n:
                out.append(f"{_rel(f, run_dir)}: {n} authorization/bearer shape(s)")
    return out


def listing(env=os.environ) -> dict[str, dict[str, list[int]]]:
    """Each real store -> {relative file path: [size, mtime_ns]}; names and stats only, never contents."""
    out = {}
    for base, rel in STORES:
        root = (_home(env) if base == "home" else Path(env.get(base, "") or "<unset>")) / rel
        files = sorted(p for p in root.rglob("*") if p.is_file()) if root.is_dir() else []
        out[str(root)] = {p.relative_to(root).as_posix(): [p.stat().st_size, p.stat().st_mtime_ns] for p in files}
    return out


def store_changes(before: dict, after: dict) -> list[str]:
    out = []
    for store in sorted(set(before) | set(after)):
        old, new = before.get(store, {}), after.get(store, {})
        changed = sorted(set(old) ^ set(new)) + sorted(k for k in set(old) & set(new) if old[k] != new[k])
        if changed:
            out.append(f"real store changed: {store} ({len(changed)} file(s))")
    return out


# --- the Grok refresh gate (ADR-0025 s7) ------------------------------------------------------------------------


def _jwt_exp(value: str) -> int | None:
    parts = value.split(".")
    if len(parts) != 3 or not value.startswith("eyJ"):
        return None
    try:
        claims = json.loads(base64.urlsafe_b64decode(parts[1] + "=" * (-len(parts[1]) % 4)))
    except (ValueError, binascii.Error):
        return None
    exp = claims.get("exp") if isinstance(claims, dict) else None
    return exp if isinstance(exp, int) and not isinstance(exp, bool) else None


def token_exps(auth: Path) -> list[int]:
    """The `exp` of every JWT-shaped string in auth.json. assume: Grok's access token is a JWT (its docs show
    `"access_token": "eyJhbGciOi..."`); confirm: the gate's first real start; breaks: no exp is readable and the gate
    fails closed ("no JWT exp"), never passes."""
    found: set[str] = set()
    credentials._strings(json.loads(auth.read_text(encoding="utf-8")), found)
    return sorted(e for v in found if (e := _jwt_exp(v)) is not None)


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def refresh_start(state: Path, env=os.environ, now: float | None = None) -> list[str]:
    auth = _bench_auth(env)
    if auth is None or not auth.is_file():
        return [f"no bench auth.json: set {BENCH_HOME_ENV} to the bench credential home"]
    try:
        exps = token_exps(auth)
    except (OSError, ValueError):
        return ["bench auth.json is not readable JSON"]
    if not exps:
        return ["bench auth.json holds no JWT exp: the gate cannot prove a refresh"]
    now = time.time() if now is None else now
    if max(exps) > now:
        return [f"bench token not expired (expires in {int(max(exps) - now)} s): the first cell would not refresh"]
    stat = auth.stat()
    with state.open("w", encoding="utf-8", newline="\n") as handle:
        json.dump({"sha256": _digest(auth), "mtime_ns": stat.st_mtime_ns}, handle)
    return []


def _grok_models(grok: list[str], env: dict) -> int:
    try:
        return subprocess.run([*grok, "models"], env=env, capture_output=True, check=False, timeout=GROK_MODELS_TIMEOUT,
                              creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)).returncode
    except (OSError, subprocess.TimeoutExpired):
        return -1


def refresh_finish(state: Path, grok: list[str], env=os.environ) -> list[str]:
    """assume: `grok models` reads `$GROK_HOME/auth.json` when GROK_HOME is set, else `~/.grok/auth.json`; confirm: the
    gate's first real run; breaks: the bench-home login is not what was tested (both exits would still be 0)."""
    auth = _bench_auth(env)
    recorded = json.loads(state.read_text(encoding="utf-8"))
    out = []
    if auth is None or not auth.is_file():
        return [f"no bench auth.json: set {BENCH_HOME_ENV} to the bench credential home"]
    if _digest(auth) == recorded["sha256"]:
        out.append("bench auth.json bytes unchanged: no refresh was written back")
    elif auth.stat().st_mtime_ns <= recorded["mtime_ns"]:
        out.append("bench auth.json changed but was not written back after the gate started")
    bench_env = {**env, "GROK_HOME": str(auth.parent)}
    real_env = {k: v for k, v in env.items() if k != "GROK_HOME"}
    for name, run_env in (("bench", bench_env), ("real", real_env)):
        if (code := _grok_models(grok, run_env)) != 0:
            out.append(f"grok models did not authenticate against the {name} home (exit {code})")
    return out


# --- the command line -------------------------------------------------------------------------------------------


def check(run_dir: Path, before: Path | None) -> tuple[list[str], list[str]]:
    view = views.load(run_dir)
    failures, notes = cell_failures(view, views.rows(run_dir, "reasoning"), views.rows(run_dir, "prompt_parts"))
    failures += credential_failures(run_dir) + debug_log_failures(run_dir)
    if before is None:
        failures.append("real stores: no --before snapshot, so a change cannot be ruled out")
    else:
        failures += store_changes(json.loads(before.read_text(encoding="utf-8")), listing())
    return failures, notes


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):  # the stdio guard (verify-portable-text-io.py)
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("run", nargs="?", type=Path)
    parser.add_argument("--before", type=Path)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--snapshot", type=Path)
    mode.add_argument("--refresh-start", type=Path)
    mode.add_argument("--refresh-finish", type=Path)
    parser.add_argument("--grok", nargs="+")
    args = parser.parse_args(argv)
    notes: list[str] = []
    if args.snapshot is not None:
        with args.snapshot.open("w", encoding="utf-8", newline="\n") as handle:
            json.dump(listing(), handle, sort_keys=True)
        failures = []
    elif args.refresh_start is not None:
        failures = refresh_start(args.refresh_start)
    elif args.refresh_finish is not None:
        if not args.grok:
            parser.error("--refresh-finish needs --grok EXE")
        failures = refresh_finish(args.refresh_finish, args.grok)
    elif args.run is not None:
        failures, notes = check(args.run, args.before)
    else:
        parser.error("name a RUN, or --snapshot, --refresh-start or --refresh-finish")
    for line in notes + failures:
        print(line)
    print(f"served_check: {'FAIL' if failures else 'pass'} ({len(failures)} failing clause(s))")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
