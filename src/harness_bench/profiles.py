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

import dataclasses
import hashlib
import importlib
import json
import os
import shutil
import sys
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path

from harness_bench import config, gitsafe, oslock, tools
from harness_bench.errors import BenchError
from harness_bench.telemetry import claude_code, codex, copilot

# One per bench/profiles/<name>.yaml (config.harness_names): identity reads profile_record for every name here, and a
# name always has its yaml because the name is the yaml's.
HARNESSES = config.HARNESSES
USAGE_SOURCES = ("acp_turn", "native_record")
# ADR-0024 s1-s3: a combo's settings. "default" is the absence of a pin: it expands nothing, joins no cell id, and is
# what every bench-matrix/2 combo carries.
DEFAULT = "default"
SETTINGS = ("effort", "context")
SETTING_APPLY = ("placeholder", "model_id", "none")
SETTING_PLACEHOLDERS = {"effort": "{effort}", "context": "{context_tokens}"}
WORKTREE = "{worktree}"  # a seed_files placeholder: the cell's working copy (Grok's trusted folder)
# assume: the engine lays a cell out as <cell>/home and <cell>/ws (engine._run_cell); confirm: the test that reads that
# line; breaks: a seeded trusted folder names a path the agent never works in, and Grok loads no project instructions.
CELL_WORKTREE_BESIDE_HOME = "ws"
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
# ADR-0025 s7: the Grok bench credential home's variable names a credential store; no cell ever sees it.
GROK_CRED_HOME_ENV = "HB_GROK_CRED_HOME"
DROP_EXACT = {"CLAUDECODE", "CLAUDE_CONFIG_DIR", "CODEX_HOME", "COPILOT_HOME", "ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN",
              "OPENAI_API_KEY", "ANTHROPIC_MODEL", "CODEX_PATH", "CLAUDE_CODE_EXECUTABLE", "FAKE_ACP", OAUTH_TOKEN_ENV,
              "GH_TOKEN", "GITHUB_TOKEN", "GH_HOST", "GH_ENTERPRISE_TOKEN", "GITHUB_ENTERPRISE_TOKEN", "GH_CONFIG_DIR",
              "XAI_API_KEY", GROK_CRED_HOME_ENV}
# ADR-0025 s8: the Grok and Antigravity homes, keys and projects of the operator never reach a cell; a profile re-adds
# only its own values (its env block).
DROP_PREFIXES = ("CLAUDE_CODE_", "CODEX_", "COPILOT_", "GIT_CONFIG_", "GROK_", "AGY_", "GEMINI_", "GOOGLE_")
# A later harness declares its own in its profile (`drop_env`: a name, or a prefix ending in `*`), unioned over every
# profile so its variables reach no cell of any harness (config.profile_isolation).
PROFILE_DROPS = config.profile_isolation(config.repo_root(Path(__file__).resolve().parent))["drop_env"]


def _dropped(name: str) -> bool:
    upper = name.upper()
    if upper in DROP_EXACT or upper.startswith(DROP_PREFIXES):
        return True
    return any(upper.startswith(rule[:-1].upper()) if rule.endswith("*") else upper == rule.upper() for rule in PROFILE_DROPS)
# ADR-0025 s8 (Leader ruling r-settings-rerun-2): each cell's own global git config, in its home, never the operator's
# and never shared, so a `git config --global` in one cell reaches no other cell and never host git (gitsafe's own file,
# ADR-0010 B6). It carries the bench identity, so an agent's commit works the same in every harness. seed_home writes it;
# cell_env names it in GIT_CONFIG_GLOBAL. With HOME relocated to the cell home (Grok, agy), ~/.gitconfig is this file too.
CELL_GITCONFIG_NAME = ".gitconfig"
CELL_GITCONFIG_TEXT = (f"[user]\n\tname = {gitsafe.BENCH_IDENTITY['GIT_AUTHOR_NAME']}\n"
                       f"\temail = {gitsafe.BENCH_IDENTITY['GIT_AUTHOR_EMAIL']}\n")
CELL_ENV = {
    "MSBUILDDISABLENODEREUSE": "1",
    "UseSharedCompilation": "false",
    "DOTNET_CLI_TELEMETRY_OPTOUT": "1",
    "GIT_CONFIG_COUNT": "2", "GIT_CONFIG_KEY_0": "core.fsmonitor", "GIT_CONFIG_VALUE_0": "false",
    "GIT_CONFIG_KEY_1": "core.longpaths", "GIT_CONFIG_VALUE_1": "true",
}
# ADR-0025 s7: the lock file inside the credential home; a cell holds it from seed to write-back.
CRED_LOCK_NAME = ".harness-bench-cred.lock"
# The record, in a cell's own home, of the absolute credential file the cell seeded from, so resume writes a dead cell's
# leftover copy back to that home of the pool, never to the profile's relative `credential.source` (which would land in
# the bench's cwd). Excluded from the archive like the copy; `clean` removes it.
CRED_SOURCE_MARKER = ".harness-bench-cred-source"
# simplify: a fixed wait for another engine's cell to release a credential home. Ceiling: an engine runs at most one
# Grok cell per home of the pool (HB-PRE-011), so the wait is at most one other engine's cell. Upgrade trigger: a seed
# refused with HB-CELL-202 in a run.
CRED_LOCK_WAIT_SECONDS = 3600.0


def credential_homes(value: str | None) -> tuple[Path, ...]:
    """ADR-0025 s7 (Am. 2026-10-13): the bench credential homes a `credential_home_env` value names, in its order: one
    folder, or a pool of folders joined by os.pathsep (';' on Windows), each logged in once by the operator. An empty
    entry names no home."""
    return tuple(Path(part.strip()).expanduser() for part in (value or "").split(os.pathsep) if part.strip())


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
class ModelCatalog:
    """A frozen model catalog written into each cell home (fix/codex-profile-0160). `source` is the committed file
    beside the profile, `sha256` its LF-normalized hash as the profile pins it (so the profile record covers its bytes),
    `name` the file in the cell home that the harness config names, and `delegate_field` the per-model field kept only
    in a scenario-6 cell (Codex 0.160.0: `multi_agent_version` offers the collaboration tools, and no feature turns
    them off while the catalog names a version)."""

    source: Path
    sha256: str
    name: str
    delegate_field: str

    def seed(self, home: Path, model: str, scenario: int | None) -> None:
        data = self.source.read_bytes().replace(b"\r\n", b"\n") if self.source.is_file() else b""
        if hashlib.sha256(data).hexdigest() != self.sha256:
            raise BenchError("HB-USR-002", f"model catalog {self.source.name}: missing, or its sha256 is not the "
                                           f"profile's {self.sha256}")
        body = json.loads(data)
        if not any(m.get("slug") == model for m in body["models"]):
            raise BenchError("HB-USR-002", f"model catalog {self.source.name} has no {model}: the cell would run on "
                                           "the harness's fallback model metadata")
        if scenario != 6:
            body["models"] = [{k: v for k, v in m.items() if k != self.delegate_field} for m in body["models"]]
        (home / self.name).write_text(json.dumps(body, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")


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
    model_catalog: ModelCatalog | None = None  # fix/codex-profile-0160: Codex's frozen catalog; None writes none
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

    def omits(self, text: str, effort=DEFAULT, context=DEFAULT) -> bool:
        """R-SETTINGS: a `default` setting expands nothing, so an env entry or a file line that exists only to carry
        that setting's placeholder is left out, and a default cell launches exactly as it did before the profile
        declared the setting. A command element is never left out: there a placeholder for a default setting is
        refused (expand_settings), since dropping one element could leave its flag dangling."""
        return any(value == DEFAULT and SETTING_PLACEHOLDERS[name] in text
                   for name, value in (("effort", effort), ("context", context)))

    def _expand_file(self, template: str, name: str, effort, context) -> str:
        lines = [line for line in template.split("\n") if not self.omits(line, effort, context)]
        return self.expand_settings("\n".join(lines), f"file {name}", effort, context)

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
        return model_allowed(served, pinned, self.auxiliary_models, self.model_aliases)

    def delegate_ids(self, scenario) -> tuple[str, ...]:
        """R-74 item 3: the ids of class `delegate` this cell may be offered: the reader's own class map (item 1: static
        in the reader), only in a scenario-6 cell. Every other cell is seeded and launched exactly as before."""
        return DELEGATE_IDS.get(self.harness, ()) if scenario == 6 else ()

    def seed_home(self, home: Path, model: str, scenario: int | None = None, oauth_token: str | None = None,
                  effort=DEFAULT, context=DEFAULT, worktree: Path | None = None) -> None:
        """Write the profile's files; `{delegate}` in a template becomes `, "<id>"` per delegate id of a scenario-6
        cell (a JSON-list continuation, the Claude Code allowlist) and nothing in any other cell (R-74 item 3).

        `oauth_token` (ADR-0003 Am. 2026-09-30): when set, this claude-code cell authenticates through CELL_OAUTH_ENV
        (`cell_env`) instead -- no credential file is copied into its home at all. A non-claude-code profile
        never receives a token (ProfileLauncher gates it), so this only ever changes claude-code's seed."""
        home.mkdir(parents=True, exist_ok=True)
        (home / CELL_GITCONFIG_NAME).write_text(CELL_GITCONFIG_TEXT, encoding="utf-8")
        delegate = "".join(f', "{name}"' for name in self.delegate_ids(scenario))
        # R-74 item 5: Codex feature multi_agent (stable, default true) offers the collaboration tools for a model whose
        # catalog entry names no multi_agent_version; a version is kept only in a scenario-6 cell (ModelCatalog.seed).
        # True only in a scenario-6 cell; false in every other cell, including a seed that names no scenario.
        multi_agent = "true" if scenario == 6 else "false"
        if self.model_catalog is not None:
            self.model_catalog.seed(home, model, scenario)
        for name, template in self.files.items():
            text = self._expand_file(template, name, effort, context)
            (home / name).parent.mkdir(parents=True, exist_ok=True)  # ADR-0025 s8: nested seeds (.grok/, .gemini/)
            (home / name).write_text(text.replace("{model}", model).replace("{delegate}", delegate)
                                     .replace("{multi_agent}", multi_agent) + "\n", encoding="utf-8")
        if (not oauth_token and self.credential_source is not None and self.credential_name is not None
                and self.credential_source.is_file()):
            (home / self.credential_name).parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(self.credential_source, home / self.credential_name)
        # ADR-0025 s5-s6: trust, update and permission files (Grok, agy); `{worktree}` is the cell's working copy.
        for name, template in self.seed_files.items():
            if WORKTREE in template and worktree is None:
                raise BenchError("HB-USR-002", f"{self.harness}: seed file {name} needs {WORKTREE}, and none was given")
            (home / name).parent.mkdir(parents=True, exist_ok=True)
            text = template.replace(WORKTREE, str(worktree)).replace("{home}", str(home)).replace("{model}", model)
            (home / name).write_text(text if text.endswith("\n") else text + "\n", encoding="utf-8")

    def clean_home(self, home: Path) -> None:
        """Delete the credential copy (the native records stay for the archive)."""
        if self.credential_name is not None:
            (home / self.credential_name).unlink(missing_ok=True)

    def cell_env(self, base: dict[str, str], home: Path, build: tools.Build, model: str, traceparent: str,
                 oauth_token: str | None = None, effort=DEFAULT, context=DEFAULT) -> dict[str, str]:
        env = {k: v for k, v in base.items() if not _dropped(k)}
        env.update(CELL_ENV)
        env[self.home_env] = str(home)
        env["GIT_CONFIG_GLOBAL"] = str(home / CELL_GITCONFIG_NAME)
        for name in self.user_home_vars:  # ADR-0025 s5-s6: HOME, USERPROFILE = the cell home (Grok, agy)
            env[name] = str(home)
        for key, template in self.env.items():
            if self.omits(template, effort, context):
                continue
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


def model_allowed(served: str, pinned: str, auxiliary_models, model_aliases=None) -> bool:
    """The pin, a declared auxiliary model (prefix match: builds date-stamp them) (US-11), or an exact alias of the pin
    from the profile's table (ADR-0024 s5: Grok `grok-4.7` serves `grok-4.7-build`; a prefix rule would also admit
    `grok-4.7-build-fast`). The one definition HB-VAL-002 and the probe use."""
    return (served == pinned or served in (model_aliases or {}).get(pinned, ())
            or any(served.startswith(a) for a in auxiliary_models))


def find_records(home: Path, record_glob: str, session_id: str) -> list[Path]:
    """The native records of one session, by its id only, never by time window (US-22). No glob names no record (a
    profile or a plan without `subagent_glob`, R-74 item 4). With no id the glob is globbed as written: one with no
    `{session_id}` names the cell home's own record (agy's teed stream, whose conversation id arrives after
    `attempt.session_opened`); one with it keeps the literal placeholder, so it names no record."""
    if not session_id or not record_glob:
        return sorted(home.glob(record_glob)) if record_glob else []
    return sorted(home.glob(record_glob.replace("{session_id}", session_id)))


def _acquire_waiting(homes: tuple[Path, ...], wait: float, poll: float = 0.05) -> tuple[Path, oslock.RunLock]:
    """Take the lock of the first free credential home, trying each in the listed order without waiting; while every
    home is held (a cell of this engine or of another, ADR-0025 s7), retry for up to `wait` seconds. The OS releases a
    dead holder's lock, so only a live cell can make this wait."""
    deadline = time.monotonic() + wait
    while True:
        for bench in homes:
            try:
                return bench, oslock.RunLock.acquire(bench / CRED_LOCK_NAME, code="HB-CELL-202")
            except BenchError as exc:
                held = exc
        if time.monotonic() >= deadline:
            raise BenchError("HB-CELL-202", f"credential home lock not released within {wait:g} s: "
                                            f"{held.message}") from None
        time.sleep(poll)


def _replace_atomically(target: Path, data: bytes) -> None:
    """A temporary file beside the target, then one replace: a reader sees the old bytes or the new, never a torn file."""
    fd, tmp = tempfile.mkstemp(prefix=f".{target.name}.", suffix=".tmp", dir=target.parent)
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data)
        os.replace(tmp, target)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


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


def _model_catalog(harness: str, folder: Path, data) -> ModelCatalog | None:
    """`model_catalog: {source, sha256, name, delegate_field}`; absent means none. The file is read at seed, never
    here, so a profile copied without it still loads."""
    if data is None:
        return None
    entry = _mapping(harness, "model_catalog", data)
    values = {key: entry.get(key) for key in ("source", "sha256", "name", "delegate_field")}
    if any(not isinstance(v, str) or not v for v in values.values()):
        raise BenchError("HB-USR-002", f"{harness}: model_catalog needs nonempty strings source, sha256, name and "
                                       "delegate_field")
    return ModelCatalog(source=folder / values["source"], sha256=values["sha256"], name=values["name"],
                        delegate_field=values["delegate_field"])


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
        model_catalog=_model_catalog(harness, root / "bench" / "profiles", data.get("model_catalog")),
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


def reader_for(harness: str):
    """A harness's native-record reader: `read` in telemetry/<harness, `-` as `_`>.py, found by name (no registry)."""
    module = harness.replace("-", "_")
    try:
        return importlib.import_module(f"harness_bench.telemetry.{module}").read
    except ModuleNotFoundError as exc:
        if exc.name != f"harness_bench.telemetry.{module}":
            raise
        raise BenchError("HB-USR-002", f"{harness}: bench/profiles/{harness}.yaml has no reader "
                                       f"src/harness_bench/telemetry/{module}.py (docs/runbooks/add-a-harness.md)") from exc


READERS = {harness: reader_for(harness) for harness in HARNESSES}
# R-74 item 1: class `delegate` is static in each reader; the profile only reads it. Codex's ids are the ones its
# 0.156.0 record names and qual-r74-codex-1 measured (item 5).
DELEGATE_IDS = {"claude-code": tuple(n for n, c in claude_code.TOOL_CLASSES.items() if c == "delegate"),
                "copilot": tuple(n for n, c in copilot.TOOL_CLASS.items() if c == "delegate"),
                "codex": codex.DELEGATE_NAMES}


class ProfileLauncher:
    """engine.Launcher for a real harness. `planned` is the build record frozen in the plan."""

    def __init__(self, profile: Profile, tools_dir: Path, planned: dict,
                 cred_lock_wait: float = CRED_LOCK_WAIT_SECONDS) -> None:
        self.profile, self.tools_dir, self.planned = profile, tools_dir, planned
        self.harness = profile.harness
        self.credential_names = frozenset({profile.credential_name}) if profile.credential_name is not None else frozenset()
        if profile.credential_home_env and profile.credential_name is not None:
            self.credential_names |= {CRED_SOURCE_MARKER}
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
        # ADR-0025 s7: a profile with `credential_home_env` seeds from, and writes back to, a bench credential home the
        # operator logged into once; `credential.source` is resolved against it. Read once, like the oauth token. A pool
        # (several homes) lets one cell per home run at once; each cell writes back to the home it took.
        self._credential_homes = credential_homes(os.environ.get(profile.credential_home_env)) \
            if profile.credential_home_env else ()
        self.cred_lock_wait = cred_lock_wait
        self._held: dict[Path, tuple[oslock.RunLock, Path, bytes | None]] = {}  # cell home -> lock, bench file, seeded

    def check_build(self) -> dict:
        """Re-hash the installed build and refuse it unless it is the planned one (BuildChanged)."""
        build = tools.resolve(self.tools_dir)[self.harness]
        tools.check_build(build, self.planned)
        self.build = build
        return build.record()

    def seed(self, home: Path, cell: dict) -> None:
        profile = self.profile
        if profile.credential_home_env is not None and profile.credential_name is not None:
            profile = dataclasses.replace(profile, credential_source=self._take_credential_home(home))
        # R-74 item 3: the allowance is per cell; ADR-0003 Am. 2026-09-30: no credential file when an oauth token is set
        profile.seed_home(home, cell["model"], cell.get("scenario"), oauth_token=self._oauth_token,
                          effort=cell.get("effort", DEFAULT), context=cell.get("context", DEFAULT),
                          worktree=home.parent / CELL_WORKTREE_BESIDE_HOME)

    def _take_credential_home(self, home: Path) -> Path:
        """Lock a free bench credential home of the pool (waiting while every home is held), and return the credential
        file the copy is seeded from. The lock is kept until `clean`, which writes back to that same home."""
        env = self.profile.credential_home_env
        if not self._credential_homes:
            raise BenchError("HB-USR-002", f"{self.harness}: {env} is not set: log in once into the bench credential "
                                           "home and set it to that folder (ADR-0025 s7)")
        bench, lock = _acquire_waiting(self._credential_homes, self.cred_lock_wait)
        source = bench / (self.profile.credential_source or "")
        self._held[home] = (lock, source, source.read_bytes() if source.is_file() else None)
        home.mkdir(parents=True, exist_ok=True)
        (home / CRED_SOURCE_MARKER).write_text(str(source.resolve()), encoding="utf-8")
        return source

    def clean(self, home: Path) -> None:
        """Write a refreshed credential back to the bench home (atomically, only when its bytes changed), then delete
        the copy, then release the credential-home lock (ADR-0025 s7). Runs at every cell end (engine `finally`).
        assume: a write-back that raises still deletes the copy (the leftover-copy rule wins); confirm: the refresh gate
        at the probe; breaks: that cell's refreshed token is lost and the operator logs in again (R-CAP's auth stop)."""
        held = self._held.pop(home, None)
        try:
            if held is not None and self.profile.credential_name is not None:
                _, source, seeded = held
                copy = home / self.profile.credential_name
                if copy.is_file() and (data := copy.read_bytes()) != seeded:
                    _replace_atomically(source, data)
        finally:
            try:
                (home / CRED_SOURCE_MARKER).unlink(missing_ok=True)
                self.profile.clean_home(home)
            finally:
                if held is not None:
                    held[0].release()

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
