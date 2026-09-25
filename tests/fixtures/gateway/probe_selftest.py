"""Offline self-test of the GW-D probe: no harness, no model, no network.

  uv run python tests/fixtures/gateway/probe_selftest.py

It proves the probe's instruments can see a positive before a live zero is trusted:
1. positive controls on the committed golden native records: tool events > 0 where the record has tool calls, a
   provider error with no model call where the model was not found, and a pack-on Codex record's injected context;
2. a synthetic Claude record, with and without a planted canary: the canary class and its key path are reported,
   and without it the same turn qualifies;
3. the verdict validator on valid and invalid answers;
4. the launch shapes: pinned model, every tool off, no fallback model, no ephemeral session, no bypass flag;
5. the seeding: every canary class is planted, and each planted file carries its canary.
Exit 0 when every check holds; each failure is printed.
"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import probe_judge as pj

NATIVE = pj.ROOT / "tests" / "fixtures" / "native"
FAILURES: list[str] = []


def check(name: str, ok: bool, detail: object = "") -> None:
    print(f"{'ok  ' if ok else 'FAIL'} {name}{'' if ok else f': {detail}'}")
    if not ok:
        FAILURES.append(name)


def facts(harness: str, record: Path, pin: str = "none", stdout: str = "", **kw) -> dict:
    return pj.analyse(harness, pin, [record], stdout, kw.get("last"), kw.get("planted", {}), kw.get("ids", {}),
                      kw.get("markers", pj.pack_markers()), kw.get("skills", []), kw.get("marker"), kw.get("prompt"))


def golden() -> None:
    f = facts("claude-code", NATIVE / "claude-code" / "ok.jsonl")
    check("claude ok.jsonl: tool events seen", (f["tool_events"] or 0) > 0, f["tool_events"])
    check("claude ok.jsonl: served model read", bool(f["served_models"]), f["served_models"])
    check("claude ok.jsonl: off-pin is a reason", any("not the pin" in r for r in f["reasons"]), f["reasons"])
    f = facts("claude-code", NATIVE / "claude-code" / "model-not-found.jsonl")
    check("claude model-not-found: no model call", f["model_calls"] == 0, f["model_calls"])
    check("claude model-not-found: provider error", bool(f["provider_errors"]), f["provider_errors"])
    f = facts("codex", NATIVE / "codex" / "ok.jsonl")
    check("codex ok.jsonl: tool events seen", (f["tool_events"] or 0) > 0, f["tool_events"])
    f = facts("codex", NATIVE / "codex" / "pack-on.jsonl")
    check("codex pack-on: injected context seen", any("AGENTS.md" in k or k.startswith("user:<") for k in f["context_kinds"]),
          f["context_kinds"])
    check("codex pack-on: pack markers seen", bool(f["reads"]["pack markers"]), f["reads"]["pack markers"])
    f = facts("codex", NATIVE / "codex" / "model-error.jsonl")
    check("codex model-error: not qualified", not f["qualified"], f["reasons"])


def synthetic(tmp: Path) -> None:
    pin, nonce = "claude-fable-5-1", "abcd1234"
    prompt = pj.PROMPT.format(nonce=nonce)
    planted = pj.canaries(nonce)
    token = planted[pj.CANARY_CLASSES[0]]
    verdict = {"items": [{"item": 1, "score": 2, "rationale": "cannot run commands"}, {"item": 2, "score": 2, "rationale": "ok"}]}
    stdout = json.dumps({"type": "result", "subtype": "success", "is_error": False, "num_turns": 1,
                         "result": json.dumps(verdict), "permission_denials": [], "modelUsage": {pin: {}}})

    def record(with_canary: bool) -> Path:
        rows = [{"type": "attachment", "sessionId": "s1", "attachment": {"type": "prompt_snapshot", "tools": []}},
                {"type": "user", "sessionId": "s1", "message": {"role": "user", "content": prompt}},
                {"type": "assistant", "sessionId": "s1", "timestamp": "2026-09-25T00:00:00Z",
                 "message": {"id": "m1", "model": pin, "content": [{"type": "text", "text": json.dumps(verdict)}],
                             "usage": {"input_tokens": 5, "cache_read_input_tokens": 0, "cache_creation_input_tokens": 0,
                                       "output_tokens": 7}}}]
        if with_canary:
            rows.insert(1, {"type": "attachment", "sessionId": "s1", "attachment": {"type": "nested_memory", "content": f"end with {token}"}})
        path = tmp / f"synthetic-{with_canary}.jsonl"
        path.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
        return path

    f = facts("claude-code", record(True), pin, stdout, planted=planted, prompt=prompt, ids={"host name": "HOSTX1"})
    check("synthetic canary: class reported", pj.CANARY_CLASSES[0] in f["reads"]["canaries"], f["reads"])
    check("synthetic canary: key path names the attachment",
          any(p.startswith("attachment/nested_memory:") for p in f["reads"]["canaries"].get(pj.CANARY_CLASSES[0], [])), f["reads"])
    check("synthetic canary: not qualified", not f["qualified"], f["reasons"])
    f = facts("claude-code", record(False), pin, stdout, planted=planted, prompt=prompt, ids={"host name": "HOSTX1"})
    check("synthetic clean: qualified", f["qualified"], f["reasons"])
    check("synthetic clean: tools advertised is an empty list, not None", f["tools_advertised"] == [], f["tools_advertised"])
    check("synthetic clean: scores read", f["final"]["scores"] == [2, 2], f["final"])
    check("synthetic clean: prompt intact", f["prompt_intact"] is True, f["prompt_intact"])
    f = facts("claude-code", record(False), pin, stdout, planted=planted, prompt=prompt + "extra", ids={})
    check("synthetic altered prompt: reported", f["prompt_intact"] is False and not f["qualified"], f["reasons"])


def validator() -> None:
    good = {"items": [{"item": 2, "score": 0, "rationale": ""}, {"item": 1, "score": 1, "rationale": "x"}]}
    check("verdict: valid", pj.validate_verdict(good) == [], pj.validate_verdict(good))
    bad = [None, {"items": []}, {"items": [{"item": 1, "score": 3, "rationale": ""}, {"item": 2, "score": 0, "rationale": ""}]},
           {"items": [{"item": 1, "score": True, "rationale": ""}, {"item": 2, "score": 0, "rationale": ""}]},
           {"items": [{"item": "1", "score": 0, "rationale": ""}, {"item": 2, "score": 0, "rationale": ""}]},
           {"items": [{"item": 1, "score": 0, "rationale": "", "extra": 1}, {"item": 2, "score": 0, "rationale": ""}]},
           {"items": [{"item": 1, "score": 0, "rationale": ""}, {"item": 1, "score": 0, "rationale": ""}]},
           {"items": [{"item": 1, "score": 0, "rationale": ""}, {"item": 2, "score": 0, "rationale": ""}], "sum": 0}]
    for i, b in enumerate(bad):
        check(f"verdict: invalid case {i} rejected", pj.validate_verdict(b) != [], b)


def launch_shapes(tmp: Path) -> None:
    a = pj.claude_argv("claude.exe", "claude-fable-5-1", "P", "S", "sid", "native")
    check("claude argv: model pinned", a[a.index("--model") + 1] == "claude-fable-5-1", a)
    i = a.index("--tools")
    check("claude argv: --tools \"\" followed by an option", a[i + 1] == "" and a[i + 2].startswith("--"), a[i:i + 3])
    check("claude argv: prompt right after -p", a[a.index("-p") + 1] == "P", a)
    check("claude argv: native schema passed", "--json-schema" in a, a)
    c = pj.codex_argv("codex.exe", "gpt-6-sol", "P", tmp, tmp / "last.txt", "text")
    check("codex argv: model pinned", "model=gpt-6-sol" in c, c)
    check("codex argv: shell tools off", all(f in c for f in ("shell_tool", "unified_exec")), c)
    check("codex argv: prompt last", c[-1] == "P", c[-3:])
    check("codex argv: text mode has no schema flag", "--output-schema" not in c, c)
    for argv in (a, c):
        banned = [x for x in argv if x in ("--fallback-model", "--ephemeral", "--no-session-persistence")
                  or x.startswith("--dangerously") or x == "bypassPermissions"]
        check(f"{Path(argv[0]).stem} argv: no banned flag", not banned, banned)


def seeding(tmp: Path) -> None:
    planted = pj.canaries("ffff0000")
    profile = pj.seed(tmp / "probe", planted)
    texts = "".join(p.read_text(encoding="utf-8") for p in (tmp / "probe").rglob("*.md"))
    check("seed: every canary planted", all(tok in texts for tok in planted.values()), planted)
    check("seed: decoy profile under the probe folder", profile == tmp / "probe" / "profile", profile)
    check("seed: home not created by seeding", not (tmp / "probe" / "home").exists())


def main() -> int:
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        golden()
        synthetic(tmp)
        validator()
        launch_shapes(tmp)
        seeding(tmp)
    print(f"{len(FAILURES)} failure(s)")
    return 1 if FAILURES else 0


if __name__ == "__main__":
    sys.exit(main())
