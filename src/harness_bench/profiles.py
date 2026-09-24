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
              "GH_TOKEN", "GITHUB_TOKEN", "GH_HOST"}
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
    command: tuple[str, ...] = ()
    files: dict[str, str] = field(default_factory=dict)
    env: dict[str, str] = field(default_factory=dict)
    mode: str | None = None
    record_glob: str = ""
    usage_source: str = "native_record"  # or acp_turn (docs/notes/decision-token-source-per-harness.md)
    auxiliary_models: tuple[str, ...] = ()
    set_model: bool = False  # pin the model with ACP session/set_model before the prompt (ADR-0003, R-13)
    credential_kind: str = "subscription login (copied)"  # what attempt.process_started records (R-13)

    def model_allowed(self, served: str, pinned: str) -> bool:
        return model_allowed(served, pinned, self.auxiliary_models)

    def seed_home(self, home: Path, model: str) -> None:
        home.mkdir(parents=True, exist_ok=True)
        for name, template in self.files.items():
            (home / name).write_text(template.replace("{model}", model) + "\n", encoding="utf-8")
        if self.credential_source is not None and self.credential_name is not None and self.credential_source.is_file():
            shutil.copyfile(self.credential_source, home / self.credential_name)

    def clean_home(self, home: Path) -> None:
        """Delete the credential copy (the native records stay for the archive)."""
        if self.credential_name is not None:
            (home / self.credential_name).unlink(missing_ok=True)

    def cell_env(self, base: dict[str, str], home: Path, build, model: str, traceparent: str) -> dict[str, str]:
        env = {k: v for k, v in base.items() if k.upper() not in DROP_EXACT and not k.upper().startswith(DROP_PREFIXES)}
        env.update(CELL_ENV)
        env[self.home_env] = str(home)
        for key, template in self.env.items():
            env[key] = template.replace("{model}", model).replace("{exe}", str(build.exe))
        if traceparent:
            env["TRACEPARENT"] = traceparent
        return env

    def argv(self, build, model: str) -> list[str]:
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
        return [part.format_map(values) for part in self.command]

    def native_records(self, home: Path, session_id: str) -> list[Path]:
        return find_records(home, self.record_glob, session_id)


def model_allowed(served: str, pinned: str, auxiliary_models) -> bool:
    """The pin, or a declared auxiliary model (prefix match: builds date-stamp them) (US-11)."""
    return served == pinned or any(served.startswith(a) for a in auxiliary_models)


def find_records(home: Path, record_glob: str, session_id: str) -> list[Path]:
    """The native records of one session, by its id only, never by time window (US-22)."""
    if not session_id:
        return []
    return sorted(home.glob(record_glob.replace("{session_id}", session_id)))


def load(root: Path, harness: str, credential_source: Path | None = None) -> Profile:
    if harness not in HARNESSES:
        raise ValueError(f"no profile for harness {harness!r} (have {HARNESSES})")
    data = config.load_yaml(root / "bench" / "profiles" / f"{harness}.yaml")
    cred = data["credential"]
    if data.get("usage_source", "native_record") not in USAGE_SOURCES:
        raise ValueError(f"{harness}: usage_source must be one of {USAGE_SOURCES}")
    return Profile(
        harness=data["harness"],
        home_env=data["home_env"],
        credential_source=(credential_source if credential_source is not None else Path(cred["source"]).expanduser())
        if cred is not None else None,
        credential_name=cred["name"] if cred is not None else None,
        command=tuple(data["command"]),
        files=dict(data.get("files") or {}),
        env=dict(data.get("env") or {}),
        mode=data.get("mode"),
        record_glob=data["record_glob"],
        usage_source=data.get("usage_source", "native_record"),
        auxiliary_models=tuple(data.get("auxiliary_models") or ()),
        set_model=bool(data.get("set_model", False)),
        credential_kind=data.get("credential_kind", "subscription login (copied)"),
    )


READERS = {"claude-code": claude_code.read, "codex": codex.read, "copilot": copilot.read}


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
        self.build: tools.Build | None = None

    def check_build(self) -> dict:
        """Re-hash the installed build and refuse it unless it is the planned one (BuildChanged)."""
        build = tools.resolve(self.tools_dir)[self.harness]
        tools.check_build(build, self.planned)
        self.build = build
        return build.record()

    def seed(self, home: Path, model: str) -> None:
        self.profile.seed_home(home, model)

    def clean(self, home: Path) -> None:
        self.profile.clean_home(home)

    def argv_env(self, cell: dict, home: Path, traceparent: str) -> tuple[list[str], dict[str, str]]:
        if self.build is None:
            raise RuntimeError("check_build must run before argv_env")
        return self.profile.argv(self.build, cell["model"]), self.profile.cell_env(
            dict(os.environ), home, self.build, cell["model"], traceparent)

    def records(self, home: Path, session_id: str) -> list[Path]:
        return self.profile.native_records(home, session_id)

    def read(self, path: Path):
        return READERS[self.harness](path)
