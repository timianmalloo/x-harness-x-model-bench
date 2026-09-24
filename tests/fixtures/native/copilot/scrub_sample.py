"""Scrub a Copilot capture into committable reader samples (design phase2-copilot-profile, section 12: scrub-rule/3).

    uv run python tests/fixtures/native/copilot/scrub_sample.py --capture C:/Projects/bench-capture/run \
        --dest tests/fixtures/native/copilot [--forbid <value> ...]
    uv run python tests/fixtures/native/copilot/scrub_sample.py --rescrub tests/fixtures/native/copilot

A per-cell Copilot ACP home holds no session-store.db (capture window 1); the samples are each arm's
session-state/<id>/events.jsonl, the two `instruction list --json` outputs and provenance.json. `--rescrub` re-applies
the current rule in place to already-committed samples (idempotent) and refreshes provenance's hashes. Fails closed:
if any forbidden value or raw path survives in any output, the outputs are deleted (capture mode) or restored
(re-scrub mode) and it exits non-zero. The forbidden values are gathered at run time and never written anywhere.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path

RULE = "scrub-rule/3"
DROP_TYPES = {"model.messages_snapshot", "model.message", "model.response", "model.captured_assignment_context", "session.binary_asset"}
OPAQUE_KEYS = {"requestMessages", "quotaSnapshots", "assignmentContext", "encryptedContent", "reasoningOpaque", "responseChunk"}
# rule/3: every field of a system.message except its identity carries the vendor system prompt (rule/2 digested only
# `content` and missed `contentBlocks`: 29 KB pack-off, 347 KB pack-on in 9c6c615). user.message.content stays (US-10).
KEEP_SYSTEM = {"role", "interactionId"}
DIGESTED_USER = {"transformedContent"}


def digested_keys(etype: str, data: dict) -> list[str]:
    if etype == "system.message":
        return [k for k in data if k not in KEEP_SYSTEM]
    if etype == "user.message":
        return [k for k in data if k in DIGESTED_USER]
    return []


def word(value: str) -> re.Pattern:
    """A forbidden value as a whole word, case-insensitive: a first name must not rewrite `timestamp`."""
    return re.compile(r"(?<![A-Za-z0-9])" + re.escape(value) + r"(?![A-Za-z0-9])", re.IGNORECASE)


def path_forms(path: str) -> set[str]:
    back = path.replace("/", "\\")
    return {back, back.replace("\\", "/"), back.replace("\\", "\\\\")}


def path_like(form: str, generic: str) -> str:
    """The generic path in the same separator style as the matched form."""
    if "\\\\" in form:
        return generic.replace("\\", "\\\\")
    if "/" in form and "\\" not in form:
        return generic.replace("\\", "/")
    return generic


class Scrubber:
    def __init__(self, paths: dict[str, str], forbid: set[str], markers: list[str]) -> None:
        self.markers = markers
        self.pairs: list[tuple[re.Pattern, str]] = []
        for raw, generic in sorted(paths.items(), key=lambda kv: -len(kv[0])):  # longest first: a cell path before the root
            for form in path_forms(raw):
                self.pairs.append((re.compile(re.escape(form), re.IGNORECASE), path_like(form, generic)))
        for f in sorted(forbid, key=len, reverse=True):
            self.pairs.append((word(f), "operator"))
        self.count = 0

    def text(self, value: str) -> str:
        for pattern, repl in self.pairs:
            value, n = pattern.subn(repl.replace("\\", "\\\\"), value)
            self.count += n
        return value

    def digest(self, value) -> str:
        if isinstance(value, str) and value.startswith("<scrubbed "):
            return value  # idempotent: a re-scrub keeps an earlier digest
        if not isinstance(value, str):
            value = json.dumps(value, ensure_ascii=False, sort_keys=True)
        found = [m for m in self.markers if m in value]
        return f"<scrubbed sha256={hashlib.sha256(value.encode('utf-8')).hexdigest()} chars={len(value)} markers={found}>"


def blank_opaque(node):
    if isinstance(node, dict):
        return {k: "<scrubbed>" if k in OPAQUE_KEYS else blank_opaque(v) for k, v in node.items()}
    if isinstance(node, list):
        return [blank_opaque(v) for v in node]
    return node


def load_events(path: Path) -> list[dict]:
    out = []
    for raw in path.read_bytes().splitlines():
        try:
            e = json.loads(raw)
        except ValueError:
            continue
        if isinstance(e, dict):
            out.append(e)
    return out


def readings(events: list[dict]) -> dict:
    """Independent readings (plain json, not the bench reader) that W1-COP-R's tests must equal."""
    r: dict = {"assistant_message_models": [], "tool_names": [], "tool_outcomes": {}, "hooks": {}, "session_errors": 0}
    for e in events:
        t, d = e.get("type"), e.get("data") if isinstance(e.get("data"), dict) else {}
        if t == "session.shutdown":
            r["shutdown"] = {"shutdownType": d.get("shutdownType"), "modelMetrics": d.get("modelMetrics"), "tokenDetails": d.get("tokenDetails"),
                             "totalApiDurationMs": d.get("totalApiDurationMs"), "totalNanoAiu": d.get("totalNanoAiu")}
        elif t == "assistant.message":
            r["assistant_message_models"].append(d.get("model"))
        elif t == "tool.execution_start":
            r["tool_names"].append(d.get("toolName"))
        elif t == "tool.execution_complete":
            err = d.get("error") if isinstance(d.get("error"), dict) else {}
            key = f"success={d.get('success')}:code={err.get('code')}"
            r["tool_outcomes"][key] = r["tool_outcomes"].get(key, 0) + 1
        elif t in ("hook.start", "hook.end"):
            key = f"{t}:{d.get('hookType')}" + ("" if t == "hook.start" else f":success={d.get('success')}")
            r["hooks"][key] = r["hooks"].get(key, 0) + 1
        elif t == "session.error":
            r["session_errors"] += 1
        elif t == "user.message" and "agentId" not in e and "first_user_content_sha256" not in r and isinstance(d.get("content"), str):
            r["first_user_content_sha256"] = hashlib.sha256(d["content"].encode("utf-8")).hexdigest()
    return r


def scrub_events(events: list[dict], dest: Path, s: Scrubber) -> dict:
    lines, dropped = [], 0
    for e in events:
        if e.get("type") in DROP_TYPES:
            dropped += 1
            continue
        data = e.get("data")
        if isinstance(data, dict):
            for key in digested_keys(str(e.get("type")), data):
                data[key] = s.digest(data[key])
            e["data"] = blank_opaque(data)
        lines.append(s.text(json.dumps(e, ensure_ascii=False)))
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    return {"lines_kept": len(lines), "lines_dropped": dropped}


def lenient_json(path: Path) -> dict:
    """Copilot's config.json starts with `//` comment lines."""
    try:
        text = "\n".join(line for line in path.read_text(encoding="utf-8").splitlines() if not line.lstrip().startswith("//"))
        data = json.loads(text)
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def forbidden(capture: Path | None, extra: list[str]) -> set[str]:
    values = {os.environ.get(k, "") for k in ("USERNAME", "USERPROFILE", "COMPUTERNAME")} | set(extra)
    for key in ("user.name", "user.email"):
        r = subprocess.run(["git", "config", key], capture_output=True, text=True, check=False)
        values.add(r.stdout.strip())
        values.update(r.stdout.strip().split())  # each part of a full name
    configs = [*(capture.glob("cells/*/home/config.json") if capture else []),
               Path(os.environ.get("USERPROFILE", "~")).expanduser() / ".copilot" / "config.json"]
    for cfg in configs:
        data = lenient_json(cfg)
        users = [data.get("lastLoggedInUser"), *(data.get("loggedInUsers") or [])]
        values.update(u.get("login", "") for u in users if isinstance(u, dict))
    return {v for v in values if isinstance(v, str) and len(v) >= 3}


def leaks(files: list[Path], forbid: set[str], raw_paths: set[str]) -> list[str]:
    """Every output, as UTF-8 and as UTF-16-LE text: a raw path anywhere; a forbidden value of 5+ characters anywhere;
    a shorter one as a word (`Tim` is inside `timestamp`)."""
    patterns = ([word(f) for f in forbid if len(f) < 5]
                + [re.compile(re.escape(p), re.IGNORECASE) for p in raw_paths | {f for f in forbid if len(f) >= 5}])
    hits = []
    for f in files:
        blob = f.read_bytes()
        for text in (blob.decode("utf-8", errors="ignore"), blob.decode("utf-16-le", errors="ignore")):
            if any(p.search(text) for p in patterns):
                hits.append(f"{f.name}: a forbidden value or raw path")
    return hits


def undigested(files: list[Path]) -> list[str]:
    """The vendor-system-prompt class (R-30 c3): every system.message field but its identity must be a digest, so a field
    the harness adds later (as `contentBlocks` was) fails the scrub instead of reaching a commit."""
    hits = []
    for f in (x for x in files if x.name == "events.jsonl"):
        for e in load_events(f):
            data = e.get("data") if isinstance(e.get("data"), dict) else {}
            if e.get("type") == "system.message":
                hits += [f"{f.name}: system.message.{k} not digested" for k, v in data.items()
                         if k not in KEEP_SYSTEM and not (isinstance(v, str) and v.startswith("<scrubbed sha256="))]
    return hits


def sha_file(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def script_hashes() -> dict:
    return {n: sha_file(Path(__file__).with_name(n)) for n in ("capture_sample.py", "scrub_sample.py")}


def capture_mode(capture: Path, dest: Path, extra: list[str]) -> None:
    summary = json.loads((capture / "summary.json").read_text(encoding="utf-8"))
    forbid = forbidden(capture, extra)
    profile = os.environ.get("USERPROFILE", "")
    paths = {str(capture / "cells" / arm): "C:\\cells\\cell" for arm in ("off", "on", "refusal")}
    paths[str(capture)] = "C:\\cells"
    if profile:
        paths[profile] = "C:\\Users\\operator"
    s = Scrubber(paths, forbid, summary["markers"])
    written: list[Path] = []
    facts: dict = {}
    try:
        for arm in ("off", "on"):
            entry = summary["arms"][arm]
            sid = entry["turn"]["session_new"]["sessionId"]
            events = load_events(capture / "cells" / arm / "home" / "session-state" / sid / "events.jsonl")  # missing → raises
            facts[arm] = {"readings": readings(events), "acp_prompt_usage": entry["turn"].get("prompt", {}).get("usage")}
            out = dest / arm / "session-state" / sid / "events.jsonl"
            written.append(out)  # registered before writing: a failure part-way still removes it
            facts[arm]["events"] = scrub_events(events, out, s)
            listing = dest / f"instruction-list-{arm}.json"
            written.append(listing)
            listing.write_text(s.text(json.dumps(entry.get("instruction_list"), indent=1, ensure_ascii=False)) + "\n", encoding="utf-8")
        provenance = {
            "note": "Leader capture for W1-COP-D (docs/design/phase2-copilot-profile.md, sections 11-12). Each arm folder is a "
                    "minimal Copilot home: find_records(home, 'session-state/{session_id}/events.jsonl', sid) resolves in it. A per-cell "
                    "ACP home holds no session-store.db.",
            "scrub": {"rule": RULE, "replacements": s.count, "forbidden_values": len(forbid), "script_sha256": script_hashes()},
            "capture": json.loads(s.text(json.dumps(summary, ensure_ascii=False))),
            "facts": json.loads(s.text(json.dumps(facts, ensure_ascii=False))),
            "outputs": {f.relative_to(dest).as_posix(): sha_file(f) for f in written},
        }
        prov = dest / "provenance.json"
        written.append(prov)
        prov.write_text(json.dumps(provenance, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
        found = leaks(written, forbid, {form for raw in paths for form in path_forms(raw)}) + undigested(written)
        if found:
            raise SystemExit("leak check failed:\n" + "\n".join(sorted(set(found))))
    except BaseException:
        for f in written:
            f.unlink(missing_ok=True)
        raise
    print(f"scrubbed {len(written)} files into {dest} ({s.count} replacements); leak check passed")


def rescrub_mode(fixture: Path, extra: list[str]) -> None:
    """Re-apply the current rule to committed samples in place; restore every file on any failure."""
    prov_path = fixture / "provenance.json"
    prov = json.loads(prov_path.read_text(encoding="utf-8"))
    forbid = forbidden(None, extra)
    s = Scrubber({os.environ["USERPROFILE"]: "C:\\Users\\operator"} if os.environ.get("USERPROFILE") else {}, forbid,
                 prov["capture"]["markers"])
    targets = sorted(fixture.glob("*/session-state/*/events.jsonl")) + sorted(fixture.glob("instruction-list-*.json")) + [prov_path]
    original = {f: f.read_bytes() for f in targets}
    try:
        for f in sorted(fixture.glob("*/session-state/*/events.jsonl")):
            events = load_events(f)
            prov["facts"][f.parts[-4]]["readings"]["tool_outcomes"] = readings(events)["tool_outcomes"]
            scrub_events(events, f, s)
        first = prov["scrub"].get("rescrubbed_from", prov["scrub"]["rule"])  # the rule the capture was scrubbed under
        prov["scrub"] = {**prov["scrub"], "rule": RULE, "rescrubbed_from": first, "rescrub_replacements": s.count,
                         "script_sha256": script_hashes()}
        prov["outputs"] = {k: sha_file(fixture / k) for k in prov["outputs"]}
        prov_path.write_text(json.dumps(prov, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
        found = leaks(targets, forbid, path_forms(os.environ.get("USERPROFILE", "")) if os.environ.get("USERPROFILE") else set())
        found += undigested(targets)
        if found:
            raise SystemExit("leak check failed:\n" + "\n".join(sorted(set(found))))
    except BaseException:
        for f, data in original.items():
            f.write_bytes(data)
        raise
    print(f"re-scrubbed {len(targets)} files in {fixture} to {RULE} ({s.count} replacements); leak check passed")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    mode = ap.add_mutually_exclusive_group(required=True)
    mode.add_argument("--capture", type=Path)
    mode.add_argument("--rescrub", type=Path)
    ap.add_argument("--dest", type=Path)
    ap.add_argument("--forbid", action="append", default=[])
    a = ap.parse_args()
    if a.rescrub:
        rescrub_mode(a.rescrub.resolve(), a.forbid)
    elif a.dest is None:
        ap.error("--capture needs --dest")
    else:
        capture_mode(a.capture.resolve(), a.dest.resolve(), a.forbid)
    return 0


if __name__ == "__main__":
    sys.exit(main())
