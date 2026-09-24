Real ACP captures with the pinned builds (claude-agent-acp 0.79.0 / Claude Code 2.1.274; codex-acp 1.12.0 / Codex 0.156.0).

- `recordings/*.jsonl` are full ACP transcripts (`acp-recording/1`: both pipes, every line, in order, with direction and time). They were captured 2026-09-24 on task X1 through `tools/acp_record.py turn` and scrubbed with `tools/acp_record.py scrub`; the scrub rule is stamped in each header. Each `*.meta.json` holds the build, the prompt hash and the live `TurnResult`. `claude-code-x1-model-unsupported` is the error path: Claude Code 2.1.274 refuses `claude-opus-5-5`.
- `*-prompt-response.json` are `session/prompt` results captured 2026-09-23, for the same turns as `../native/*/ok.jsonl`. `tests/test_telemetry.py` reads them.
- `provenance.json` records each fixture's adapter version, capture date, scrub and source. `tests/test_driver.py` fails if a fixture here has no entry.
- `replay_agent.py` replays a recording to the driver verbatim (D5). Each line the client sends releases the agent lines recorded after the matching client line, exactly as recorded. Nothing is synthesised.
