"""Harness profiles: data in `bench/profiles/<harness>.yaml` (ADR-0003, ADR-0004, ADR-0013).

Pattern: table-driven configuration (a data-driven Strategy). A profile says how to seed a cell's own
harness home (the credential copy and the static permission files), which environment pins the model
and the build, which ACP mode to set, and where the native session record lands.

Every cell's environment is cleaned: variables that would point a harness at the operator's own home,
API keys (subscriptions only, ADR-0003), and the markers of an enclosing Claude Code session are
removed. Shared build servers are switched off so nothing outlives the turn or joins another cell's job.

`ProfileLauncher` is the engine's Launcher for a real harness: a profile plus the planned build, re-hashed
at every cell start (US-12).
"""

from __future__ import annotations

import os
import shutil
from dataclasses import dataclass, field
from pathlib import Path

from harness_bench import config, tools
from harness_bench.errors import BenchError
from harness_bench.telemetry import claude_code, codex, copilot

HARNESSES = ("claude-code", "codex", "copilot")
USAGE_SOURCES = ("acp_turn", "native_record")
DROP_EXACT = {"CLAUDECODE", "CLAUDE_CONFIG_DIR", "CODEX_HOME", "COPILOT_HOME", "ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN",
              "OPENAI_API_KEY", "ANTHROPIC_MODEL", "CODEX_PATH", "CLAUDE_CODE_EXECUTABLE", "FAKE_ACP",
              "GH_TOKEN", "GITHUB_TOKEN", "GH_HOST", "GH_ENTERPRISE_TOKEN", "GITHUB_ENTERPRISE_TOKEN", "GH_CONFIG_DIR"}
DROP_PREFIXES = ("CLAUDE_CODE_", "CODEX_", "COPILOT_", "GIT_CONFIG_")
CELL_ENV = {
    "MSBUILDDISABLENODEREUSE": "1",
    "UseSharedCompilation": "false",
    "DOTNET_CLI_TELEMETRY_OPTOUT": "1",
    "GIT_CONFIG_COUNT": "2", "GIT_CONFIG_KEY_0": "core.fsmonitor", "GIT_CONFIG_VALUE_0": "false",
    "GIT_CONFIG_KEY_1": "core.longpaths", "GIT_CONFIG_VALUE_1": "true",
}


@dataclass(frozen=True)
class Profile:
    harness: str
    home_env: str
    credential_source: Path | None
    credential_name: str | None
    command: tuple[str, ...]
    files: dict[str, str] = field(default_factory=dict)
    env: dict[str, str] = field(default_factory=dict)
    mode: str | None = None
    record_glob: str = ""
    usage_source: str = "native_record"  # or acp_turn (docs/notes/decision-token-source-per-harness.md)
    auxiliary_models: tuple[str, ...] = ()
    set_model: bool = False  # pin the model with ACP session/set_model before the prompt (ADR-0003, R-13)
    credential_kind: str = "subscription login (copied)"  # what attempt.process_started records (R-13)
    shutdown_grace: float = 10.0
    # R-73 item 1: the model vendor (anthropic | openai), a profile fact, never inferred from a model id. load() refuses
    # a profile without one; the default only keeps hand-built test profiles (gateway, judge) constructible.
    vendor: str = ""
    # R-74 item 4: where a session's sub-agent records land beside the main one ({session_id} filled per cell); empty
    # when a harness writes its sub-agents into the main record (Copilot: rows with a top-level agentId).
    subagent_glob: str = ""

    def model_allowed(self, served: str, pinned: str) -> bool:
        return model_allowed(served, pinned, self.auxiliary_models)

    def delegate_ids(self, scenario) -> tuple[str, ...]:
        """R-74 item 3: the ids of class `delegate` this cell may be offered: the reader's own class map (item 1: static
        in the reader), only in a scenario-6 cell. Every other cell is seeded and launched exactly as before."""
        return DELEGATE_IDS.get(self.harness, ()) if scenario == 6 else ()

    def seed_home(self, home: Path, model: str, scenario: int | None = None) -> None:
        """Write the profile's files; `{delegate}` in a template becomes `, "<id>"` per delegate id of a scenario-6
        cell (a JSON-list continuation, the Claude Code allowlist) and nothing in any other cell (R-74 item 3)."""
        home.mkdir(parents=True, exist_ok=True)
        delegate = "".join(f', "{name}"' for name in self.delegate_ids(scenario))
        for name, template in self.files.items():
            (home / name).write_text(template.replace("{model}", model).replace("{delegate}", delegate) + "\n", encoding="utf-8")
        if self.credential_source is not None and self.credential_name is not None and self.credential_source.is_file():
            shutil.copyfile(self.credential_source, home / self.credential_name)

    def clean_home(self, home: Path) -> None:
        """Delete the credential copy (the native records stay for the archive)."""
        if self.credential_name is not None:
            (home / self.credential_name).unlink(missing_ok=True)

    def cell_env(self, base: dict[str, str], home: Path, build: tools.Build, model: str, traceparent: str) -> dict[str, str]:
        env = {k: v for k, v in base.items() if k.upper() not in DROP_EXACT and not k.upper().startswith(DROP_PREFIXES)}
        env.update(CELL_ENV)
        env[self.home_env] = str(home)
        for key, template in self.env.items():
            env[key] = template.replace("{model}", model).replace("{exe}", str(build.exe))
        if traceparent:
            env["TRACEPARENT"] = traceparent
        return env

    def argv(self, build: tools.Build, model: str | None = None, mcp_config: Path | None = None,
             scenario: int | None = None) -> list[str]:
        if model is None and any("{model}" in part for part in self.command):
            raise ValueError(f"{self.harness}: model is required by the command template")
        values = {"exe": str(build.exe), "model": model}
        if any("{node}" in part for part in self.command):
            node = shutil.which("node")
            if not node:
                raise BenchError("HB-PRE-007", "node is required to run the ACP adapters")
            values["node"] = node
        if any("{adapter}" in part for part in self.command):
            if build.adapter is None:
                raise BenchError("HB-PRE-007", f"{self.harness}: command needs an ACP adapter")
            values["adapter"] = str(build.adapter)
        argv = [part.replace("{exe}", values["exe"]).replace("{model}", values["model"] or "")
                .replace("{node}", values.get("node", "")).replace("{adapter}", values.get("adapter", ""))
                for part in self.command]
        delegate = self.delegate_ids(scenario) if self.harness == "copilot" else ()
        if delegate:  # R-74 item 3: the four ids join the --available-tools list, before any scripted-user addition
            if "--available-tools" not in argv:
                raise BenchError("HB-USR-002", "a scenario-6 launch needs the Copilot tool allowlist (R-74 item 3)")
            argv.extend(delegate)
        if mcp_config is not None:
            if self.harness != "copilot" or "--available-tools" not in argv:
                raise BenchError("HB-USR-002", "a scripted-user launch config needs the Copilot tool allowlist")
            argv.extend(["scripted_user-ask_user", "--allow-tool", "scripted_user",
                         "--additional-mcp-config", f"@{mcp_config}"])
        return argv

    def native_records(self, home: Path, session_id: str) -> list[Path]:
        return find_records(home, self.record_glob, session_id)

    def subagent_records(self, home: Path, session_id: str) -> list[Path]:
        return find_records(home, self.subagent_glob, session_id)


def model_allowed(served: str, pinned: str, auxiliary_models) -> bool:
    """The pin, or a declared auxiliary model (prefix match: builds date-stamp them) (US-11)."""
    return served == pinned or any(served.startswith(a) for a in auxiliary_models)


def find_records(home: Path, record_glob: str, session_id: str) -> list[Path]:
    """The native records of one session, by its id only, never by time window (US-22). No glob names no record (a
    profile or a plan without `subagent_glob`, R-74 item 4)."""
    if not session_id or not record_glob:
        return []
    return sorted(home.glob(record_glob.replace("{session_id}", session_id)))


def subagent_session_id(path: Path) -> str:
    """A sub-agent record's native session id: the agent id its file is named by (`agent-<id>.jsonl`), unique within the
    session (R-74 item 4; ADR-0008:49 keys a cell's sessions by native session id). assume: the file name carries the
    agent id, as the store session-profile.py reads names it; confirm: the R-74 c6 turn's tree; breaks: two records one id."""
    return path.stem.removeprefix("agent-")


def load(root: Path, harness: str, credential_source: Path | None = None) -> Profile:
    if harness not in HARNESSES:
        raise ValueError(f"no profile for harness {harness!r} (have {HARNESSES})")
    data = config.load_yaml(root / "bench" / "profiles" / f"{harness}.yaml")
    command = data.get("command")
    if not isinstance(command, list) or not command or any(not isinstance(part, str) or not part for part in command):
        raise BenchError("HB-USR-002", f"{harness}: profile command must be a nonempty list of strings")
    cred = data["credential"]
    vendor = data.get("vendor")
    if not isinstance(vendor, str) or not vendor.strip():
        raise BenchError("HB-USR-002", f"{harness}: profile vendor must be a nonempty string (R-73 item 1)")
    if data.get("usage_source", "native_record") not in USAGE_SOURCES:
        raise ValueError(f"{harness}: usage_source must be one of {USAGE_SOURCES}")
    grace = data.get("shutdown_grace_seconds")
    if isinstance(grace, bool) or not isinstance(grace, (int, float)) or not 0 < grace <= 10:
        raise BenchError("HB-USR-002", f"{harness}: shutdown_grace_seconds must be greater than 0 and at most 10")
    return Profile(
        harness=data["harness"],
        vendor=vendor,
        home_env=data["home_env"],
        credential_source=(credential_source if credential_source is not None else Path(cred["source"]).expanduser())
        if cred is not None else None,
        credential_name=cred["name"] if cred is not None else None,
        command=tuple(command),
        files=dict(data.get("files") or {}),
        env=dict(data.get("env") or {}),
        mode=data.get("mode"),
        record_glob=data["record_glob"],
        usage_source=data.get("usage_source", "native_record"),
        auxiliary_models=tuple(data.get("auxiliary_models") or ()),
        set_model=bool(data.get("set_model", False)),
        credential_kind=data.get("credential_kind", "subscription login (copied)"),
        shutdown_grace=float(grace),
        subagent_glob=data.get("subagent_glob") or "",
    )


READERS = {"claude-code": claude_code.read, "codex": codex.read, "copilot": copilot.read}
# R-74 item 1: class `delegate` is static in each reader; the profile only reads it. Codex has none until its measured
# qualification turn (item 5), so a Codex scenario-6 cell is seeded as today and a spawn there stays `other`.
DELEGATE_IDS = {"claude-code": tuple(n for n, c in claude_code.TOOL_CLASSES.items() if c == "delegate"),
                "copilot": tuple(n for n, c in copilot.TOOL_CLASS.items() if c == "delegate")}


class ProfileLauncher:
    """engine.Launcher for a real harness. `planned` is the build record frozen in the plan."""

    def __init__(self, profile: Profile, tools_dir: Path, planned: dict) -> None:
        self.profile, self.tools_dir, self.planned = profile, tools_dir, planned
        self.harness = profile.harness
        self.credential_names = frozenset({profile.credential_name}) if profile.credential_name is not None else frozenset()
        self.usage_source = profile.usage_source
        self.mode = profile.mode
        self.set_model = profile.set_model
        self.credential_kind = profile.credential_kind
        self.shutdown_grace = profile.shutdown_grace
        self.build: tools.Build | None = None

    def check_build(self) -> dict:
        """Re-hash the installed build and refuse it unless it is the planned one (BuildChanged)."""
        build = tools.resolve(self.tools_dir)[self.harness]
        tools.check_build(build, self.planned)
        self.build = build
        return build.record()

    def seed(self, home: Path, cell: dict) -> None:
        self.profile.seed_home(home, cell["model"], cell.get("scenario"))  # R-74 item 3: the allowance is per cell

    def clean(self, home: Path) -> None:
        self.profile.clean_home(home)

    def argv_env(self, cell: dict, home: Path, traceparent: str) -> tuple[list[str], dict[str, str]]:
        if self.build is None:
            raise RuntimeError("check_build must run before argv_env")
        return self.profile.argv(self.build, cell["model"], mcp_config=cell.get("mcp_config"),
                                 scenario=cell.get("scenario")), self.profile.cell_env(
            dict(os.environ), home, self.build, cell["model"], traceparent)

    def records(self, home: Path, session_id: str) -> list[Path]:
        return self.profile.native_records(home, session_id)

    def read(self, path: Path):
        return READERS[self.harness](path)
