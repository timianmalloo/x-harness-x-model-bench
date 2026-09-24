---
id: "note-spike-n5-codex-skill-roots"
title: "Spike N5: no observed Codex 0.156 mechanism removes ~/.agents/skills from a cell"
type: doc
status: draft
owner: "@timianmalloo"
tags: [benchmark, spike, phase-1, codex, skills, N5]
links:
  - { to: design-phase1-walking-skeleton, rel: refines }
  - { to: coordination-phase1-finish, rel: relates-to }
review-by: "2026-10-23"
summary: >-
  T5's 1.5h research timebox found one candidate (features.skip_host_skill_discovery in config.toml) and
  ran it for real against the US-13 canary: the operator's ~/.agents/skills skill still reached the Codex
  cell. A third party independently reports the same flag, plus --ignore-user-config, --ignore-rules and
  project_doc_max_bytes=0, all fail the same way on 0.154.0. Negative result: no Codex 0.156 mechanism
  observed (source or run) removes a user skill root from a cell. The change is reverted; N5 stays open,
  xfail(strict) with an updated reason.
---

# Spike N5: Codex 0.156 personal skill root

## Question

Find a mechanism, observed in Codex 0.156 (source or a run), that removes `~/.agents/skills` (the
operator's personal skill root) from a cell — despite the cell's own `CODEX_HOME` — so the US-13 canary
goes green for Codex without `xfail`.

## What was ruled out before this spike

A per-cell `USERPROFILE`/`HOME` override in `cell_env` (`src/harness_bench/profiles.py`) did not stop
the leak; that change was reverted before T5 started (coordination plan, T5 row).

## What this spike tried

**Candidate: `features.skip_host_skill_discovery` (config.toml).**

- **Source (Verified, by running the installed binary):** `.tools/harness/node_modules/@openai/codex-win32-x64/vendor/x86_64-pc-windows-msvc/bin/codex.exe features list`
  (Codex 0.156.0, installed under `.tools/harness`) lists a feature named `skip_host_skill_discovery`,
  stage "under development", default `false`. `codex.exe features enable skip_host_skill_discovery`
  (against a scratch `CODEX_HOME`) writes:
  ```
  [features]
  skip_host_skill_discovery = true
  ```
  into that `CODEX_HOME`'s `config.toml`, and a following `features list` shows it `true`. This
  confirms the exact TOML shape Codex accepts, and that a per-cell `config.toml` (already how
  `bench/profiles/codex.yaml` seeds `model = "{model}"`) is a legitimate delivery path for a feature
  override — but confirms nothing about what the flag actually does; its name was the only evidence for
  its semantics, which turned out to be a Confident Guess (see disposition below).
- **Applied:** `bench/profiles/codex.yaml`'s `files.config.toml` template was changed to add the
  `[features]` block above, and `tests/test_profiles.py` gained a red-first unit test pinning it
  (`test_codex_profile_disables_host_skill_discovery`, red at
  `1678c43a56df6dca149c10f68c9e407558d8ad45`, `tests/test_profiles.py:48`;
  the fix turned it green).
- **Verified by a real canary run (2026-09-24, run 1 of 3):**
  `uv run pytest -q -p no:cacheprovider tests/e2e/test_us13_canary.py -s -m ""` with the flag applied.
  Claude Code stayed clean. Codex still leaked:
  ```
  US-13 codex: shown by the control ['skill (~/.agents/skills, via USERPROFILE)']; void (control did not
  show) []; leaked into the probe ['skill (~/.agents/skills, via USERPROFILE)']
  AssertionError: user-level configuration reached a codex cell: ['skill (~/.agents/skills, via
  USERPROFILE)']
  Left contains 1 more item: {'microsoft-foundry': 'skill (~/.agents/skills, via USERPROFILE)'}
  ```
  **Disposition: the flag does not do what its name suggests, or does not cover this discovery path.**
  This was a real spike-protocol run, not an assumption from the name — the name alone had been a
  Confident Guess until this run.
- **Independent corroboration (Flagged, secondary source):** a third-party design issue
  (`gsornsen/anastom` #14, examined against upstream tag `rust-v0.154.0`, commit
  `6b9826e3aa83b1a5947db50f4332cb9c65f1b340`) reports testing `features.skip_host_skill_discovery=true`
  together with `--ignore-user-config`, `--ignore-rules` and `project_doc_max_bytes=0` on Codex 0.154.0,
  and still finds "global AGENTS.md and user/project skills" included. Their recommendation is not a
  Codex-native flag at all: build isolation around bounded, actively-scanned private directories rather
  than trying to suppress the host's own discovery. This is a web source, not a run T5 performed, so it
  is corroborating evidence, not independently Verified by this spike.

## Other candidates named in the task, not reached

- **A skill-roots CLI flag plumbed through the ACP adapter.** The `codex-acp` adapter
  (`.tools/harness/node_modules/@agentclientprotocol/codex-acp/dist/index.js`) only ever *adds* extra
  skill roots for `additionalDirectories` (`refreshSkills`, `skillsExtraRootsSet`,
  around line 28749) — there is no path in the adapter to *remove* the host's default root. It does
  read a `CODEX_CONFIG` env var (JSON) at startup (`startAcpServer`, around line 35149) and forwards it
  as the per-session config override sent to `threadStart` — the same `features` table, just delivered
  through the adapter's env instead of a seeded `config.toml`. Since the config.toml route already
  proved the flag itself is ineffective, plumbing it through `CODEX_CONFIG` instead would not change the
  result; not run.
- **Windows known-folder API ignoring `USERPROFILE`.** Plausible (the `codex.js` launcher passes
  `process.env` straight through to the Rust binary unchanged — `bin/codex.js`, confirmed by reading it
  — so if the Rust side still finds the real profile, it is not the launcher dropping the env var). Not
  confirmed by a probe in this spike: doing so needs either the Rust source at the matching tag (not
  fetched — GitHub code search requires sign-in, and time ran out) or an isolated repro that changes
  `USERPROFILE` and inspects which `~` Codex resolves, independent of the skills question. **Flagged
  risk**, cheapest next probe: a two-line PowerShell/Rust probe that prints `home::home_dir()`-equivalent
  resolution with `USERPROFILE` pointed elsewhere, or asking upstream directly (the `codex features`
  and `codex doctor` commands did not surface this).

## Conclusion

No Codex 0.156 mechanism was **observed** (source or run) that removes `~/.agents/skills` from a cell.
The `skip_host_skill_discovery` config.toml change is reverted (`bench/profiles/codex.yaml`,
`tests/test_profiles.py`); `tests/e2e/test_us13_canary.py` keeps `xfail(strict=True)` on the Codex
parametrization, with the reason updated to record what was tried. See
`docs/proof/findings-T5.md` for the red SHA, the full run, and the T5 fallback decision request.
