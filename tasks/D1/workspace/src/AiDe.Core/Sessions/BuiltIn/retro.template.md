---
id: retro
version: 1
intent: profile a run
audience: agent
when_to_use: "A run closed and you want its lessons in the next plan."
why: "Telemetry-grounded findings feed forward; vibes don't. Wraps /session-profiler."
provenance: "Transcribed from Addendum B §B4, row `retro` (Ruling 30): when_to_use and why byte-for-byte from B4's columns, fields the mechanical slug of its core-fields column, body a slot rendering of that column. Not authored."
fields:
  - { name: telemetry_scope, type: text, required: true }
  - { name: findings_fixes_table_shape, type: text, required: true }
  - { name: feed_forward_target, type: text, required: true }
---
telemetry scope: {{telemetry_scope}}
findings/fixes table shape: {{findings_fixes_table_shape}}
feed-forward target: {{feed_forward_target}}
