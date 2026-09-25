"""Scripted user for scenario 1: answers only annotated clarifications, logs every question.

A pure library plus one stdio MCP server module (design docs/design/phase2-scripted-user.md; R-37, R-39, R-51-R-53):
- `matcher`: exact, then normalised (rules N1-N5), then none; MATCHER_VERSION; the three-part cache key.
- `clarifications`: loads `oracle/clarifications.yaml` (bench-clarifications/1); the responder's reply.
- `log`: the per-cell log (bench-scripted-user-log/1), its end row, and the match store a re-grade reads.
- `server`: `python -m harness_bench.scripted_user.server <clarifications.yaml> <log.jsonl>`, one tool `ask_user`.
Anything that matches no annotation gets exactly "Decide and state your assumption.".
"""
