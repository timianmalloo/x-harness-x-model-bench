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
import sys
from dataclasses import dataclass, field
from pathlib import Path

from harness_bench import config, tools
from harness_bench.errors import BenchError
from harness_bench.telemetry import agy, claude_code, codex, copilot, grok

# Leader ruling (lean re-run J0): grok and agy join HARNESSES and READERS in wave 1 (R-SETTINGS), in the same candidate
# as their profile files (R-TRANSPORT); identity reads profile_record for every name here, so a name without its yaml
# would break the engine identity between J0 and J1a. Their reader stubs are telemetry/grok.py and telemetry/agy.py.
HARNESSES = ("claude-code", "codex", "copilot", "grok", "agy")
USAGE_SOURCES = ("acp_turn", "native_record")
# ADR-0024 s1-s3: a combo's settings. "default" is the absence of a pin: it expands nothing, joins no cell id, and is
# what every bench-matrix/2 combo carries.
DEFAULT = "default"
SETTINGS = ("effort", "context")
SETTING_APPLY = ("placeholder", "model_id", "none")
SETTING_PLACEHOLDERS = {"effort": "{effort}", "context": "{context_tokens}"}
CONTEXT_ARG = "{context_arg}"  # ADR-0028 s3: a whole argv element, replaced by the context setting's argv map
TRANSPORTS = ("acp", "agy-stream")  # ADR-0025 s1: the module engine._attempt drives the cell with
SCRIPTED_USER = ("supported", "unsupported")  # ADR-0028 s7: the plan refuses a scripted-user task when unsupported
# ADR-0003 Am. 2026-09-30: a claude-code-only alternative to the copied-credential-file path (ADR-0003 amended 2026-09-30).
# Claude Code refresh tokens rotate; copying the operator's own ~/.claude login into every cell home means one
# cell's refresh strands every other copy's, mid-run. `claude setup-token` mints a long-lived (1-year) OAuth
# token for non-interactive use (never an API key, ADR-0003's "subscriptions only"); the operator keeps it in
# OAUTH_TOKEN_ENV, the engine reads it once and injects it into each claude-code cell as CELL_OAUTH_ENV. The
# operator's own ~/.claude login is never read or touched by this path. Without the var, the file-copy path
# below is unchanged.
OAUTH_TOKEN_ENV = "HB_CLAUDE_OAUTH_TOKEN"
CELL_OAUTH_ENV = "CLAUDE_CODE_OAUTH_TOKEN"
CREDENTIAL_KIND_OAUTH_TOKEN = "oauth_token_env"
DROP_EXACT = {"CLAUDECODE", "CLAUDE_CONFIG_DIR", "CODEX_HOME", "COPILOT_HOME", "ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN",
              "OPENAI_API_KEY", "ANTHROPIC_MODEL", "CODEX_PATH", "CLAUDE_CODE_EXECUTABLE", "FAKE_ACP", OAUTH_TOKEN_ENV,
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
class Setting:
    """One `settings:` entry of a profile (ADR-0024 s3): the values it accepts (strings, so 922000 and "922000" are one
    value), how a value is applied, what the harness serves for "default" (None: no record shows it), and, for a
    `{context_arg}` profile, the argv elements each value becomes (ADR-0028 s3)."""

    values: tuple[str, ...] = ()
    apply: str = "none"
    default_serves: str | int | None = None
    args: dict[str, tuple[str, ...]] = field(default_factory=dict)


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
    # Lean re-run seams (ADR-0024 s3, ADR-0025 s1-s8, ADR-0028 s7). Parsed here with defaults that leave the three
    # existing profiles' launches byte-equal; what each one does beyond placeholder expansion is R-SETTINGS's and
    # R-TRANSPORT's (session_meta on session/new, user_home_vars, seed_files, the credential home, the alias table).
    settings: dict[str, Setting] = field(default_factory=dict)
    transport: str = "acp"
    session_meta: dict = field(default_factory=dict)
    user_home_vars: tuple[str, ...] = ()
    seed_files: dict[str, str] = field(default_factory=dict)
    credential_home_env: str | None = None
    model_aliases: dict[str, tuple[str, ...]] = field(default_factory=dict)
    scripted_user: str = "supported"

    def expand_settings(self, text: str, where: str, effort=DEFAULT, context=DEFAULT) -> str:
        """`{effort}` and `{context_tokens}` become the cell's values; "default" expands nothing. A placeholder left in
        a launch input is refused, never sent as literal text (the plan refuses an unsupported value first, R-SETTINGS)."""
        for value, placeholder in ((effort, SETTING_PLACEHOLDERS["effort"]), (context, SETTING_PLACEHOLDERS["context"])):
            if value != DEFAULT:
                text = text.replace(placeholder, str(value))
            elif placeholder in text:
                raise BenchError("HB-USR-002", f"{self.harness}: {where} needs {placeholder}, but the cell's setting is "
                                               f"{DEFAULT!r}")
        return text

    def context_args(self, context=DEFAULT) -> list[str]:
        """The argv elements `{context_arg}` becomes: none for "default" unless the map says otherwise (ADR-0028 s3)."""
        setting = self.settings.get("context", Setting())
        key = str(context)
        if key in setting.args:
            return list(setting.args[key])
        if context == DEFAULT:
            return []
        raise BenchError("HB-USR-002", f"{self.harness}: context {key} has no {CONTEXT_ARG} mapping in the profile")

    def model_allowed(self, served: str, pinned: str) -> bool:
        return model_allowed(served, pinned, self.auxiliary_models)

    def delegate_ids(self, scenario) -> tuple[str, ...]:
        """R-74 item 3: the ids of class `delegate` this cell may be offered: the reader's own class map (item 1: static
        in the reader), only in a scenario-6 cell. Every other cell is seeded and launched exactly as before."""
        return DELEGATE_IDS.get(self.harness, ()) if scenario == 6 else ()

    def seed_home(self, home: Path, model: str, scenario: int | None = None, oauth_token: str | None = None,
                  effort=DEFAULT, context=DEFAULT) -> None:
        """Write the profile's files; `{delegate}` in a template becomes `, "<id>"` per delegate id of a scenario-6
        cell (a JSON-list continuation, the Claude Code allowlist) and nothing in any other cell (R-74 item 3).

        `oauth_token` (ADR-0003 Am. 2026-09-30): when set, this claude-code cell authenticates through CELL_OAUTH_ENV
        (`cell_env`) instead -- no credential file is copied into its home at all. A non-claude-code profile
        never receives a token (ProfileLauncher gates it), so this only ever changes claude-code's seed."""
        home.mkdir(parents=True, exist_ok=True)
        delegate = "".join(f', "{name}"' for name in self.delegate_ids(scenario))
        # R-74 item 5: Codex 0.156.0 feature multi_agent (stable, default true) is what offers the collaboration tools.
        # True only in a scenario-6 cell; false in every other cell, including a seed that names no scenario.
        multi_agent = "true" if scenario == 6 else "false"
        for name, template in self.files.items():
            text = self.expand_settings(template, f"file {name}", effort, context)
            (home / name).write_text(text.replace("{model}", model).replace("{delegate}", delegate)
                                     .replace("{multi_agent}", multi_agent) + "\n", encoding="utf-8")
        if (not oauth_token and self.credential_source is not None and self.credential_name is not None
                and self.credential_source.is_file()):
            shutil.copyfile(self.credential_source, home / self.credential_name)

    def clean_home(self, home: Path) -> None:
        """Delete the credential copy (the native records stay for the archive)."""
        if self.credential_name is not None:
            (home / self.credential_name).unlink(missing_ok=True)

    def cell_env(self, base: dict[str, str], home: Path, build: tools.Build, model: str, traceparent: str,
                 oauth_token: str | None = None, effort=DEFAULT, context=DEFAULT) -> dict[str, str]:
        env = {k: v for k, v in base.items() if k.upper() not in DROP_EXACT and not k.upper().startswith(DROP_PREFIXES)}
        env.update(CELL_ENV)
        env[self.home_env] = str(home)
        for key, template in self.env.items():
            env[key] = (self.expand_settings(template, f"env {key}", effort, context).replace("{model}", model)
                        .replace("{exe}", str(build.exe)).replace("{home}", str(home)))
        if traceparent:
            env["TRACEPARENT"] = traceparent
        if oauth_token:  # ADR-0003 Am. 2026-09-30: CLAUDE_CODE_OAUTH_TOKEN in place of the copied credential file
            env[CELL_OAUTH_ENV] = oauth_token
        return env

    def argv(self, build: tools.Build, model: str | None = None, mcp_config: Path | None = None,
             scenario: int | None = None, effort=DEFAULT, context=DEFAULT, home: Path | None = None) -> list[str]:
        if model is None and any("{model}" in part for part in self.command):
            raise ValueError(f"{self.harness}: model is required by the command template")
        if home is None and any("{home}" in part for part in self.command):
            raise ValueError(f"{self.harness}: the cell home is required by the command template")
        values = {"exe": str(build.exe), "model": model, "python": sys.executable, "home": str(home)}
        if any("{node}" in part for part in self.command):
            node = shutil.which("node")
            if not node:
                raise BenchError("HB-PRE-007", "node is required to run the ACP adapters")
            values["node"] = node
        if any("{adapter}" in part for part in self.command):
            if build.adapter is None:
                raise BenchError("HB-PRE-007", f"{self.harness}: command needs an ACP adapter")
            values["adapter"] = str(build.adapter)
        argv = []
        for part in self.command:
            if part == CONTEXT_ARG:
                argv.extend(self.context_args(context))
                continue
            part = self.expand_settings(part, "command", effort, context)
            argv.append(part.replace("{exe}", values["exe"]).replace("{model}", values["model"] or "")
                        .replace("{node}", values.get("node", "")).replace("{adapter}", values.get("adapter", ""))
                        .replace("{python}", values["python"]).replace("{home}", values["home"]))
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


def _str_tuple(harness: str, key: str, value) -> tuple[str, ...]:
    if not isinstance(value, list) or any(not isinstance(v, (str, int)) or isinstance(v, bool) for v in value):
        raise BenchError("HB-USR-002", f"{harness}: profile {key} must be a list of strings")
    return tuple(str(v) for v in value)


def _mapping(harness: str, key: str, value) -> dict:
    if not isinstance(value, dict):
        raise BenchError("HB-USR-002", f"{harness}: profile {key} must be a mapping")
    return dict(value)


def _settings(harness: str, data) -> dict[str, Setting]:
    """ADR-0024 s3: `settings: {<name>: {values, apply, default_serves, args}}`; absent means no setting is declared."""
    out = {}
    for name, entry in _mapping(harness, "settings", data).items():
        if name not in SETTINGS:
            raise BenchError("HB-USR-002", f"{harness}: unknown setting {name!r} (have {SETTINGS})")
        entry = _mapping(harness, f"settings.{name}", entry)
        apply = entry.get("apply", "none")
        if apply not in SETTING_APPLY:
            raise BenchError("HB-USR-002", f"{harness}: settings.{name}.apply must be one of {SETTING_APPLY}")
        args = {str(k): _str_tuple(harness, f"settings.{name}.args.{k}", v)
                for k, v in _mapping(harness, f"settings.{name}.args", entry.get("args") or {}).items()}
        out[name] = Setting(values=_str_tuple(harness, f"settings.{name}.values", entry.get("values") or []),
                            apply=apply, default_serves=entry.get("default_serves"), args=args)
    return out


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
    transport = data.get("transport", "acp")
    if transport not in TRANSPORTS:
        raise BenchError("HB-USR-002", f"{harness}: transport must be one of {TRANSPORTS}")
    scripted_user = data.get("scripted_user", "supported")
    if scripted_user not in SCRIPTED_USER:
        raise BenchError("HB-USR-002", f"{harness}: scripted_user must be one of {SCRIPTED_USER}")
    home_env_name = data.get("credential_home_env")
    if home_env_name is not None and (not isinstance(home_env_name, str) or not home_env_name):
        raise BenchError("HB-USR-002", f"{harness}: credential_home_env must be a nonempty string")
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
        settings=_settings(harness, data.get("settings") or {}),
        transport=transport,
        session_meta=_mapping(harness, "session_meta", data.get("session_meta") or {}),
        user_home_vars=_str_tuple(harness, "user_home_vars", data.get("user_home_vars") or []),
        seed_files={str(k): str(v) for k, v in _mapping(harness, "seed_files", data.get("seed_files") or {}).items()},
        credential_home_env=home_env_name,
        model_aliases={str(k): _str_tuple(harness, f"model_aliases.{k}", v)
                       for k, v in _mapping(harness, "model_aliases", data.get("model_aliases") or {}).items()},
        scripted_user=scripted_user,
    )


READERS = {"claude-code": claude_code.read, "codex": codex.read, "copilot": copilot.read, "grok": grok.read, "agy": agy.read}
# R-74 item 1: class `delegate` is static in each reader; the profile only reads it. Codex's ids are the ones its
# 0.156.0 record names and qual-r74-codex-1 measured (item 5).
DELEGATE_IDS = {"claude-code": tuple(n for n, c in claude_code.TOOL_CLASSES.items() if c == "delegate"),
                "copilot": tuple(n for n, c in copilot.TOOL_CLASS.items() if c == "delegate"),
                "codex": codex.DELEGATE_NAMES}


class ProfileLauncher:
    """engine.Launcher for a real harness. `planned` is the build record frozen in the plan."""

    def __init__(self, profile: Profile, tools_dir: Path, planned: dict) -> None:
        self.profile, self.tools_dir, self.planned = profile, tools_dir, planned
        self.harness = profile.harness
        self.credential_names = frozenset({profile.credential_name}) if profile.credential_name is not None else frozenset()
        self.usage_source = profile.usage_source
        self.mode = profile.mode
        self.set_model = profile.set_model
        self.transport = profile.transport  # ADR-0025 s1: engine.protocol_module reads it
        # ADR-0003 Am. 2026-09-30: read once, at construction (before any cell launches) -- the operator sets it before the run
        # starts, for the run's duration. None for every harness but claude-code (the only one this path covers).
        self._oauth_token = os.environ.get(OAUTH_TOKEN_ENV) if profile.harness == "claude-code" else None
        self.credential_kind = CREDENTIAL_KIND_OAUTH_TOKEN if self._oauth_token else profile.credential_kind
        self.shutdown_grace = profile.shutdown_grace
        self.build: tools.Build | None = None

    def check_build(self) -> dict:
        """Re-hash the installed build and refuse it unless it is the planned one (BuildChanged)."""
        build = tools.resolve(self.tools_dir)[self.harness]
        tools.check_build(build, self.planned)
        self.build = build
        return build.record()

    def seed(self, home: Path, cell: dict) -> None:
        # R-74 item 3: the allowance is per cell; ADR-0003 Am. 2026-09-30: no credential file when an oauth token is set
        self.profile.seed_home(home, cell["model"], cell.get("scenario"), oauth_token=self._oauth_token,
                               effort=cell.get("effort", DEFAULT), context=cell.get("context", DEFAULT))

    def clean(self, home: Path) -> None:
        self.profile.clean_home(home)

    def argv_env(self, cell: dict, home: Path, traceparent: str) -> tuple[list[str], dict[str, str]]:
        if self.build is None:
            raise RuntimeError("check_build must run before argv_env")
        # A plan written before the lean re-run has no effort or context on its cells: both read as "default".
        effort, context = cell.get("effort", DEFAULT), cell.get("context", DEFAULT)
        return self.profile.argv(self.build, cell["model"], mcp_config=cell.get("mcp_config"),
                                 scenario=cell.get("scenario"), effort=effort, context=context, home=home), \
            self.profile.cell_env(dict(os.environ), home, self.build, cell["model"], traceparent,
                                  oauth_token=self._oauth_token, effort=effort, context=context)

    def records(self, home: Path, session_id: str) -> list[Path]:
        return self.profile.native_records(home, session_id)

    def read(self, path: Path):
        return READERS[self.harness](path)
