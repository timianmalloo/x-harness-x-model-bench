"""Spike S-LB: does a loopback-only listener raise a Windows Defender Firewall prompt or rule?

Stdlib only. Run on Windows with the operator present (B-2). Modes:
  loopback         bind 127.0.0.1:0 from a fresh copy of the interpreter, exchange one request.
  positive-control the same with 0.0.0.0, which must fire a dialog or add a rule.
  report           read both result files and print the verdict. Binds nothing.
Each run mode prints one JSON document and writes <out>/<mode>.json.
Procedure and pass rule: docs/notes/spike-s-lb-loopback.md.
"""
import argparse
import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time

HOSTS = {"loopback": "127.0.0.1", "positive-control": "0.0.0.0"}
SNAPSHOT_PS = (
    "Get-NetFirewallRule | ForEach-Object { $a = $_ | Get-NetFirewallApplicationFilter; "
    "[pscustomobject]@{Name=$_.Name; DisplayName=$_.DisplayName; Enabled=[string]$_.Enabled; "
    "Direction=[string]$_.Direction; Action=[string]$_.Action; Program=$a.Program} } "
    "| ConvertTo-Json -Compress"
)


def copy_interpreter(dest_dir):
    """Step 1: a fresh path, so no existing firewall rule can match the program."""
    base = sys.base_prefix
    os.makedirs(dest_dir)
    for name in os.listdir(base):
        low = name.lower()
        if low in ("python.exe", "pythonw.exe") or (low.endswith(".dll") and os.path.isfile(os.path.join(base, name))):
            shutil.copy2(os.path.join(base, name), dest_dir)
    return os.path.join(dest_dir, "python.exe")


def firewall_snapshot():
    """Step 3: rules as {Name: row}; None when PowerShell cannot read them (never a guessed empty set)."""
    try:
        done = subprocess.run(["powershell", "-NoProfile", "-Command", SNAPSHOT_PS],
                              capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120, check=False,
                              creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        if done.returncode != 0 or not done.stdout.strip():
            return None
        rows = json.loads(done.stdout)
        rows = rows if isinstance(rows, list) else [rows]
        return {r["Name"]: r for r in rows}
    except (OSError, ValueError, subprocess.TimeoutExpired):
        return None


def diff_rules(before, after):
    """Rows present after and absent before; None when either snapshot is missing."""
    if before is None or after is None:
        return None
    return [after[k] for k in sorted(after) if k not in before]


def verdict(loopback, control):
    """The pass rule: no prompt and no new rule for loopback, and the control fired. Anything unrecorded is INCONCLUSIVE."""
    def fired(r):
        if r.get("dialog_seen") is None or r.get("new_rules") is None:
            return None
        return bool(r["dialog_seen"]) or bool(r["new_rules"])
    if loopback is None or control is None:
        return "INCONCLUSIVE"
    lb, pc = fired(loopback), fired(control)
    if lb is None or pc is None or not loopback.get("exchange_ok") or not control.get("exchange_ok"):
        return "INCONCLUSIVE"
    if lb:
        return "FAIL loopback fired"
    return "PASS" if pc else "INCONCLUSIVE control did not fire"


def child_server(host, settle):
    with socket.socket() as srv:
        srv.bind((host, 0))
        srv.listen(1)
        print(srv.getsockname()[1], flush=True)
        conn, _ = srv.accept()
        with conn:
            conn.sendall(conn.recv(64).upper())
        time.sleep(settle)  # stay bound while a dialog or rule can still appear


def child_client(host, port):
    with socket.create_connection((host, port), timeout=10) as c:
        c.sendall(b"ping")
        sys.stdout.write(c.recv(64).decode())


def run_mode(mode, out_dir, settle, dialog):
    host = HOSTS[mode]
    work = tempfile.mkdtemp(prefix="slb-")
    exe = copy_interpreter(os.path.join(work, "py"))
    result = {"mode": mode, "host": host, "interpreter_copy": exe, "platform": sys.platform,
              "dialog_seen": None, "new_rules": None, "exchange_ok": False, "error": None}
    before = firewall_snapshot()
    env = dict(os.environ, PYTHONHOME=sys.base_prefix)
    server = subprocess.Popen([exe, os.path.abspath(__file__), "--child-server", host, str(settle)],
                              stdout=subprocess.PIPE, text=True, encoding="utf-8", errors="replace", env=env,
                              creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    try:
        port = int(server.stdout.readline())
        client = subprocess.run([sys.executable, os.path.abspath(__file__), "--child-client", "127.0.0.1", str(port)],
                                capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=30, check=False,
                                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        result["exchange_ok"] = client.returncode == 0 and client.stdout == "PING"
        time.sleep(settle)
        if dialog == "ask" and sys.stdin.isatty():
            result["dialog_seen"] = input("Did a Windows Defender Firewall dialog appear? [y/n] ").strip().lower().startswith("y")
        elif dialog in ("yes", "no"):
            result["dialog_seen"] = dialog == "yes"
        result["new_rules"] = diff_rules(before, firewall_snapshot())
    except (ValueError, OSError, subprocess.TimeoutExpired) as exc:
        result["error"] = f"{type(exc).__name__}: {exc}"
    finally:
        server.kill()
    result["cleanup"] = (f"Remove-NetFirewallRule for any rule whose Program is under {work} (elevated); "
                         f"then delete {work}")
    return result


def parse(argv):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--mode", choices=["loopback", "positive-control", "report"])
    p.add_argument("--out", default=os.path.join(tempfile.gettempdir(), "slb-out"))
    p.add_argument("--settle", type=float, default=15.0, help="seconds to stay bound after the exchange")
    p.add_argument("--dialog", choices=["ask", "yes", "no"], default="ask")
    p.add_argument("--child-server", nargs=2, metavar=("HOST", "SETTLE"))
    p.add_argument("--child-client", nargs=2, metavar=("HOST", "PORT"))
    a = p.parse_args(argv)
    if not (a.mode or a.child_server or a.child_client):
        p.error("--mode is required")
    return a


def load(path):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def main(argv=None):
    a = parse(argv)
    if a.child_server:
        child_server(a.child_server[0], float(a.child_server[1]))
        return 0
    if a.child_client:
        child_client(a.child_client[0], int(a.child_client[1]))
        return 0
    os.makedirs(a.out, exist_ok=True)
    if a.mode == "report":
        out = {"verdict": verdict(load(os.path.join(a.out, "loopback.json")),
                                  load(os.path.join(a.out, "positive-control.json")))}
    else:
        if sys.platform != "win32":
            print(json.dumps({"mode": a.mode, "error": "Windows only (macOS is out of scope)"}))
            return 2
        out = run_mode(a.mode, a.out, a.settle, a.dialog)
        with open(os.path.join(a.out, a.mode + ".json"), "w", encoding="utf-8", newline="\n") as f:
            json.dump(out, f)
    print(json.dumps(out))
    return 0


if __name__ == "__main__":
    for _stream in (sys.stdout, sys.stderr):
        if hasattr(_stream, "reconfigure"):
            try:
                _stream.reconfigure(encoding="utf-8", errors="replace")
            except (ValueError, OSError):
                pass
    sys.exit(main())
