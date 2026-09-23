"""Harness profiles: data in `bench/profiles/<harness>.yaml` (ADR-0003, ADR-0004, ADR-0013).

Pattern: table-driven configuration (a data-driven Strategy). A profile says how to seed a cell's own
harness home (the credential copy and the static permission files), which environment pins the model
and the build, which ACP mode to set, and where the native session record lands.

Every cell's environment is cleaned: variables that would point a harness at the operator's own home,
API keys (subscriptions only, ADR-0003), and the markers of an enclosing Claude Code session are
removed. Shared build servers are switched off so nothing outlives the turn or joins another cell's job.
"""

from __future__ import annotations

import shutil
from dataclasses import dataclass, field
from pathlib import Path

from harness_bench import config

HARNESSES = ("claude-code", "codex")
USAGE_SOURCES = ("acp_turn", "native_record")
DROP_EXACT = {"CLAUDECODE", "CLAUDE_CONFIG_DIR", "CODEX_HOME", "COPILOT_HOME", "ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN",
              "OPENAI_API_KEY", "ANTHROPIC_MODEL", "CODEX_PATH", "CLAUDE_CODE_EXECUTABLE", "FAKE_ACP"}
DROP_PREFIXES = ("CLAUDE_CODE_", "CODEX_", "COPILOT_", "GIT_CONFIG_")
CELL_ENV = {
    "MSBUILDDISABLENODEREUSE": "1",
    "UseSharedCompilation": "false",
    "DOTNET_CLI_TELEMETRY_OPTOUT": "1",
    "GIT_CONFIG_COUNT": "1", "GIT_CONFIG_KEY_0": "core.fsmonitor", "GIT_CONFIG_VALUE_0": "false",
}


@dataclass(frozen=True)
class Profile:
    harness: str
    home_env: str
    credential_source: Path
    credential_name: str
    files: dict[str, str] = field(default_factory=dict)
    env: dict[str, str] = field(default_factory=dict)
    mode: str | None = None
    record_glob: str = ""
    usage_source: str = "native_record"  # or acp_turn (docs/notes/decision-token-source-per-harness.md)
    auxiliary_models: tuple[str, ...] = ()

    def model_allowed(self, served: str, pinned: str) -> bool:
        """The pin, or a declared auxiliary model (prefix match: builds date-stamp them) (US-11)."""
        return served == pinned or any(served.startswith(a) for a in self.auxiliary_models)

    def seed_home(self, home: Path, model: str) -> None:
        home.mkdir(parents=True, exist_ok=True)
        for name, template in self.files.items():
            (home / name).write_text(template.replace("{model}", model) + "\n", encoding="utf-8")
        if self.credential_source.is_file():
            shutil.copyfile(self.credential_source, home / self.credential_name)

    def clean_home(self, home: Path) -> None:
        """Delete the credential copy (the native records stay for the archive)."""
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

    def argv(self, build) -> list[str]:
        node = shutil.which("node")
        if not node:
            raise FileNotFoundError("node is required to run the ACP adapters")
        return [node, str(build.adapter)]

    def native_records(self, home: Path, session_id: str) -> list[Path]:
        if not session_id:
            return []
        return sorted(home.glob(self.record_glob.replace("{session_id}", session_id)))


def load(root: Path, harness: str, credential_source: Path | None = None) -> Profile:
    if harness not in HARNESSES:
        raise ValueError(f"no phase-1 profile for harness {harness!r} (have {HARNESSES})")
    data = config.load_yaml(root / "bench" / "profiles" / f"{harness}.yaml")
    cred = data["credential"]
    if data.get("usage_source", "native_record") not in USAGE_SOURCES:
        raise ValueError(f"{harness}: usage_source must be one of {USAGE_SOURCES}")
    return Profile(
        harness=data["harness"],
        home_env=data["home_env"],
        credential_source=credential_source or Path(cred["source"]).expanduser(),
        credential_name=cred["name"],
        files=dict(data.get("files") or {}),
        env=dict(data.get("env") or {}),
        mode=data.get("mode"),
        record_glob=data["record_glob"],
        usage_source=data.get("usage_source", "native_record"),
        auxiliary_models=tuple(data.get("auxiliary_models") or ()),
    )
