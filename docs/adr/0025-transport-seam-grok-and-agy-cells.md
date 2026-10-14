---
id: "adr-0025-transport-seam-grok-and-agy-cells"
title: "ADR-0025: Grok over the existing ACP driver; Antigravity over a bench-owned native-stream driver with the pack adapter as its oracle; isolated, pinned, credential-safe cells"
type: adr
status: draft
owner: "@timianmalloo"
phase: "Lean re-run at equal reasoning (operator 2026-10-11)"
tags: [benchmark, transport, acp, grok, antigravity, isolation, builds, credentials]
links:
  - { to: arch-lean-rerun, rel: refines }
  - { to: adr-0013-native-cells, rel: depends-on }
  - { to: adr-0004-static-permissions, rel: depends-on }
review-by: "2027-04-11"
summary: >-
  The engine picks its protocol module by profile.transport: driver.py (ACP, unchanged behaviour plus a
  session/new _meta passthrough and a fail-closed set_model check) or a new stream_driver.py with the same function
  signatures, the only module that speaks Antigravity's stream-json, multi-turn, under the bench's own process
  control, teeing the raw stream into the cell home as the native record. The pack's coord_transport agy path is
  not imported: it discards the bodies the bench must record and spawns its own processes. It is the conformance
  oracle in a contract test through its public run_session instead. Grok and Antigravity cells are isolated by
  HOME and USERPROFILE, run read-only pinned executables with self-update off, seed their trust and permission
  files, restrict tools to the ADR-0004 classes, and never copy a worker's credential.
review-suggested:
  - { by: arch-lean-rerun, on: 2026-10-11, reason: "lean re-run amendment: bench-matrix/3 settings, served read-back (HB-VAL-010/011), Grok and agy cells, catalog 0.8 drift split, cost-compare report (ADR-0024..0027)" }
---

# ADR-0025: Grok over ACP; Antigravity over a bench-owned native-stream driver; safe cells

- **Status:** Proposed (revised at the gate, 2026-10-11: council findings 2, 4, 5, 6, 7, 15, 16, 17, 19, 21, 22,
  25). The deviation in §3 from the prompt's "reuse coord_transport" waits for an operator ruling (finding 22).
- **Date:** 2026-10-11
- **Deciders:** @timianmalloo (Ruling 117: agy 1.3.3); authored by the Leader seat (Claude Code, Opus).
- **Context:** the prompt's R-HARNESS-GROK and R-HARNESS-AGY; `docs/architecture-lean-rerun.md`; the 2026-10-11
  spikes (`C:\tf\spike-grok\`, `C:\tf\spike-agy\`).

## Context

- `engine._attempt` calls `driver.open_session` and `driver.send_turn` directly, passing mode, handshake timeout,
  MCP servers, the cancel event, the per-turn barrier, the turn number and `on_first_update`
  (`engine.py:830-902`, Verified). `tests/test_architecture.py:143-145` makes `driver.py` the only ACP speaker.
- The pack's agy adapter (`coord_transport.run_session("agy")`), read 2026-10-11:
  - discards every event body: no usage, no tool events, no model id (`coord_transport.py:4-5`, `:863-927`);
  - spawns and contains its own process (`_ThreadedWire`, a Windows gate wrapper, a Job Object;
    `coord_transport.py:311`, `platform_process.py:117-146`), where the bench measures peak memory and CPU through
    `procs.CellProcess`;
  - inserts its directory at `sys.path[0]` on import (`coord_transport.py:21-24`);
  - is pack-managed: this repository edits it only through `/updatepack`.
- Grok speaks ACP. The measured SERVE-A control for Grok is `session/set_model` plus a fail-closed check of the
  answer's `_meta.model == {"Ok": pin}` (`coord_transport.py:790-799`; register `:862`). The bench's driver
  ignores unknown response ids (`driver.py:252-255`, Verified).
- **Credentials, measured 2026-10-11.** After the Grok spike ran two cells on *copies* of `~/.grok/auth.json`, the
  real home reported "You are not authenticated" at 18:06 and rewrote the file. The access token is a short-lived
  JWT and the file holds a refresh token. Inferred cause: a cell's refresh rotated the token family, stranding the
  original, the same shape the repo records for Claude Code (`profiles.py:28-33`). Antigravity authenticates through
  the Windows keyring in place and still authenticated after its spike (Verified).

## Decision

1. **No new abstraction; the module is chosen by the profile.** A profile names `transport: acp | agy-stream`
   (default `acp`). `stream_driver.py` exposes the same `open_session` and `send_turn` signatures as `driver.py`, so
   `_attempt` keeps every argument it passes today and picks the module. `stream_driver.py` is class `run` in
   `identity.CLASSES`, is added to the run-path import rule (`test_architecture.py:44`), and is the only module
   holding agy's event names (a mirror of the ACP rule).
2. **`driver.py` changes, generic only.** A profile `session_meta` mapping is sent as `session/new` `_meta` (Claude
   Code's thinking display, ADR-0026). After `session/set_model`, a response that carries `_meta.model` must equal
   `{"Ok": <pin>}`, or the cell fails before the prompt (HB-CELL-116, the existing refused-model code).
3. **`stream_driver.py` for Antigravity.**
   - Spawned through `procs`, so containment, peak memory and CPU are measured as for every cell.
   - Several turns in one process, as the oracle sends them (`coord_transport.py:869-882`): one
     `{"event":"user","message":{"role":"user","content":…}}` line per turn, the engine's snapshot between turns,
     so RW1 and RW2 run.
   - Every stdout line is teed, unchanged, to `<cell home>/agy-stream.ndjson`, the native record. A sidecar
     `agy-stream.times.jsonl` gives each line's `time.monotonic_ns()` at read, on the clock of
     `attempt.process_started`; it is read time, not emit time, and is joined by line index. A count mismatch makes
     the times `not recorded`.
   - Line cap: the driver's 8 MiB (`driver.py:41`), the BND-A rule that one kind of content has one bound; the probe
     measures the largest real line and the bound is re-sized only from that.
   - Outcome mapping (written as a table in the design and tested):

     | stream shows | outcome |
     | --- | --- |
     | `result.status == "SUCCESS"`, empty `denied_actions` | turn completed |
     | `result.status != "SUCCESS"` | incomplete |
     | non-empty `denied_actions`, or a tool ERROR starting `permission check failed for ` | blocked (new HB-CELL code; never a success) |
     | five consecutive native tool errors | ended (`NATIVE_ERROR_STREAK_CAP`) |
     | unknown event type, or bad JSON | protocol failure |

4. **The pack adapter is the oracle, not a dependency.** A contract test runs `coord_transport.run_session("agy",
   argv=[python, replay.py, <stream>], …)`, its public entry point, against a replay process that writes streams
   recorded from agy **1.3.3** (success, two-turn, denial, tool-error streak, unknown event), and runs
   `stream_driver` on the same streams. Both must give the same outcome row of the table above. A pack update that
   changes the grammar turns it red. This is the prompt's "reuse" without importing the pack into the run path.
   **This deviates from the prompt's words** ("reuse the pack's Agy adapter … behind the engine's transport
   interface"), so it goes to the operator as a decision request before slice 2 (finding 22).
5. **Grok profile (`bench/profiles/grok.yaml`, vendor `xai`).**
   - argv `{exe} agent --model {model} --reasoning-effort {effort} stdio`; `set_model: true`.
   - env: `GROK_HOME={home}/.grok`; `HOME`, `USERPROFILE` = the cell home; `XAI_API_KEY` removed.
   - seeded: `config.toml` with `[cli] auto_update = false`; `trusted_folders.toml` naming the cell worktree **in
     both arms** (an untrusted folder loads no project instructions; Verified), so the arms differ only by the files
     in the repo.
   - **tools:** restricted to the ADR-0004 classes by Grok's own configuration, with `TOOL_CLASS` in
     `telemetry/grok.py` so HB-VAL-008 flags any out-of-profile call. The configuration mechanism is Flagged:
     design-slice spikes it. If Grok cannot prevent forbidden tools (web, image, subagent, scheduler), the bench
     relies on detection only, and that goes to the operator as a decision request, answered before the formal
     probe.
   - `record_glob`: the session directory under `.grok/sessions/` (exact form fixed by design-slice);
     `usage_source: native_record` (`usage.json`, per turn).
6. **Antigravity profile (`bench/profiles/agy.yaml`, vendor `google`).**
   - argv `{exe} --input-format stream-json --output-format stream-json --model {model} --print-timeout {budget}s
     --add-dir {worktree} -p=` (`-p` takes a value, so `-p=` goes last; Verified).
   - env: `HOME`, `USERPROFILE` = the cell home; `AGY_CLI_DISABLE_AUTO_UPDATE=true` (`1` does not work; Verified).
   - seeded: `.gemini/antigravity-cli/settings.json` with `permissions.allow` rules mapped from the ADR-0004 classes
     (Verified that a seeded rule lets a command run), and deny rules for browser, web search, image generation and
     MCP tools. `--dangerously-skip-permissions` is never used.
   - `transport: agy-stream`; records: the teed stream and `conversations/<id>.db`.
7. **Credentials never shared with workers.**
   - **Grok:** cells never copy `~/.grok/auth.json`. The operator logs in once into a dedicated bench credential
     home (`HB_GROK_CRED_HOME`, outside `~/.grok`; a separate login, so a separate token family, Inferred). Grok
     cells run one at a time (below). Each cell seeds a copy from the bench home. After the agent process ends and
     **before** `launcher.clean(home)` deletes the copy (`engine.py:773`), the engine writes the cell's `auth.json`
     back to the bench home atomically (a temporary file, then replace) when its bytes changed. The cell holds an
     `oslock` on `HB_GROK_CRED_HOME` from seed to write-back, so two engines (a probe beside a batch, a resumed run
     beside a live one) cannot overwrite each other's refreshed token. On resume (ADR-0021), a leftover cell home
     whose `auth.json` is newer than the bench home's is written back first; if it is gone, the operator logs in
     again before Grok cells resume. An authentication
     failure ends the cell as infrastructure (not scored); **two consecutive authentication failures for one
     harness stop the batch** (a stranded bench home would otherwise fail every later cell).
   - **Readiness gate that proves a refresh.** The gate starts when the bench home's access token has expired (its
     JWT `exp` is read, not its value), so the first cell must refresh. It runs three sequential Grok cells and
     passes only when: the bench `auth.json` bytes changed and were written back; `grok models` authenticates
     against the bench home **and** the real home. A failure stops the run and goes to the operator.
   - **Antigravity:** the keyring in place (the Copilot pattern), one cell at a time. A concurrent-refresh gate
     could only fail after the shared login, which the workers also use, is already broken, so concurrency is not
     probed. The probe checks `agy models` after its agy cells. Agy cells share the keyring login with live agy
     workers, so **no agy coordination worker runs while a probe or batch runs** (the build tracks join before
     the run).
   - **Per-harness cap, mandatory.** The plan carries `harness_parallelism`, frozen with it. `bench plan` refuses a
     matrix with a `grok` or `agy` combo unless the cap for that harness is 1 (Grok: up to its pool size, Amendment
     2026-10-13 below). The engine scheduler
     (`engine.py:478-481`) is built to `models/run_lifecycle.tla` (`engine.py:1`), so the cap is added to that
     model and checked by its existing model-check test (`tests/test_check_models.py`) in the same track.
   - **Credential scan.** `report/credentials.py` also reads the bench home's `auth.json`, so that token is among
     the scanned literals.
   - **Erratum (Coordinator #2, 2026-10-12; Leader ruling, epoch 21).** "Two consecutive authentication failures
     for one harness stop the batch" is replaced by the existing mechanism: `blocked_auth` (HB-CELL-202) already
     opens a per-harness decision and pauses that harness's launches while it is open (`engine.py:65`; PE-4). An
     authentication failure still ends the cell as infrastructure; it then pauses only that harness until the
     decision is answered, and other harnesses keep launching. No new stop path is built. The resume write-back
     above stands. Recorded in `docs/coordination/coordination-lean-rerun.md`, *Errata* E4.
   - **Amendment (2026-10-13): a pool of Grok credential homes.** Measured: with one home, Grok cells run one at a
     time, at 14-22 min each, so a 60-cell Grok run takes about 18 h. Change:
     - `HB_GROK_CRED_HOME` may name several bench credential homes joined by `os.pathsep` (`;` on Windows). The
       operator logs in once into each (`docs/runbooks/grok-credential-pool.md`). One home is the rule above,
       unchanged. `profiles.credential_homes` is the one parser; the launcher, the credential scan
       (`report/credentials.py`: `grok:bench-home`, then `grok:bench-home-2`, ...) and `tools/served_check.py` use it.
     - A cell tries each home's `oslock` in the listed order without waiting, and takes the first free one. When every
       home is held, it waits as before (`CRED_LOCK_WAIT_SECONDS`, then HB-CELL-202). It seeds from that home, and
       `clean` writes back to the **same** home (the atomic write-back), then releases that home's lock. So two
       concurrent cells never share a token family, and no more cells are live than there are homes.
     - **The cap rule.** For a profile with `credential_home_env`, `bench plan` accepts a cap from 1 up to the number
       of homes the variable names at plan time (at least 1). A larger cap is refused with HB-PRE-011, and the message
       names the count. agy keeps a cap of exactly 1, because its keyring login is shared. The plan freezes the cap
       only. It records no home path and no count, because the paths are the operator's. If the pool shrinks before
       the run, extra cells wait on a lock; they never share a home.
     - The refresh-proving readiness gate reads the **first** home. Sequential gate cells take it, because it is the
       first free home in the list.
     - Each home is a separate `grok login`, so each holds a separate token family. This is Inferred, like the
       single home above. `assume:` a later login of the same account does not revoke an earlier home's session.
       Confirm: run `grok models` against every home after the last login (the runbook step). Breaks: the earlier
       home's cells fail authentication (HB-CELL-202 pauses Grok).
     - **Open (resume).** The resume write-back above uses the profile's `credential_source`. The launcher resolves
       that against a home only at seed (`ProfileLauncher._take_credential_home`). Unchanged by this amendment and
       not built here: a resumed leftover copy has no record of which pool home it came from. Also, the shipped
       profile's `credential_source` is the relative `auth.json` (`profiles.load`). So `resume.write_back_credentials`
       targets `<cwd>/auth.json` even with one home. That is a finding for the resume owner (R-CAP).
8. **Isolation and builds.**
   - `DROP_PREFIXES` (`profiles.py:41`) gains `GROK_`, `AGY_`, `GEMINI_`, `GOOGLE_`; each profile re-adds only its
     own values. `GIT_CONFIG_GLOBAL` is seeded to one bench file for every harness, because a relocated `HOME`
     drops the user's global git config. `seed_home` creates parent directories (`profiles.py:97-99`).
   - The probe lists the real `~/.grok/sessions`, `~/.gemini/antigravity-cli/conversations`, `%APPDATA%` and
     `%LOCALAPPDATA%` harness folders before and after, and fails on a change.
   - Grok 1.0.41 is pinned in `bench/tools/package.json`; `tools.LAYOUT` points at the package's platform
     executable, run directly (the npm shim copies the exe into each new home and self-updates; Verified).
     Antigravity: `bench/tools/vendored.json` pins `{version: "1.3.3", sha256:
     "fbbfb3f15c7628252c5e12765683c688ba05ee122b853cadeb0bbfd4e13ca25b"}`; `bench tools install` copies a named
     source exe into `.tools/agy/1.3.3/` only when the hash matches. Installed executables are made read-only.
     `check_build` re-hashes at every cell start (HB-CELL-115).
   - `workspace.INSTRUCTION_FILES`/`INSTRUCTION_DIRS` (`workspace.py:27-28`) gain `GEMINI.md`, `.agents/rules`,
     `.agents/skills` and `.grok/`, so HB-PRE-009 covers what the new harnesses load.

## Consequences

- The ACP path is not forked, and its behaviour is unchanged for the three existing harnesses.
- Antigravity's record is the stream the bench read, byte for byte.
- Grok and Antigravity cells each run one at a time (other combos still run beside them), which lengthens the
  batch wall time; the checkpoint measures it.
- The operator has two logins to make before any Grok cell: the real home (broken by the spike, 2026-10-11) and the
  bench credential home.

## Alternatives considered

- **Import `coord_transport.run_session("agy")` into the engine.** Rejected: it discards the bodies the bench must
  record, replaces `procs` process control and its measures, and adds a `sys.path` side effect to the run path.
- **A `Transport` protocol class.** Rejected at the gate (finding 7): it drops arguments `_attempt` passes today; two
  modules with one signature need no abstraction.
- **Patch `coord_transport` to keep bodies.** Rejected: pack-managed code, edited only by `/updatepack`.
- **Copy `~/.grok/auth.json` into cells (the Codex pattern).** Rejected at the gate (finding 2), and measured: it
  stranded the real login.
