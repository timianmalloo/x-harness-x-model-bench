Real ACP `session/prompt` results captured 2026-09-23 with the pinned builds (claude-agent-acp 0.79.0 / Claude Code 2.1.274; codex-acp 1.12.0 / Codex 0.156.0), for the same turns as `../native/*/ok.jsonl`.

- `provenance.json` records each fixture's adapter version, capture date, scrub and source; `tests/test_driver.py` fails if a fixture here has no entry.
- `replay_agent.py` replays a recorded result through the driver (D5). Its handshake replies are minimal ACP-schema shapes, not recordings.
