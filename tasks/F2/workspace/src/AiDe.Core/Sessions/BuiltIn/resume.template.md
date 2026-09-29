---
id: resume
version: 1
intent: rebuild context
audience: conductor
when_to_use: "Continuing earlier work in a fresh context or a new session."
why: "Decisions-not-transcript rebuilds cheap, current context; replaying transcript bloats and goes stale. Spec §7.3's verb, promptable."
provenance: "Transcribed from Addendum B §B4, row `resume` (Ruling 30): when_to_use and why byte-for-byte from B4's columns, fields the mechanical slug of its core-fields column, body a slot rendering of that column. Not authored."
fields:
  - { name: source_session_blocks, type: text, required: true }
  - { name: recipe_re_resolution_rules, type: text, required: true }
  - { name: context_budget, type: text, required: true }
---
source session/blocks: {{source_session_blocks}}
recipe re-resolution rules: {{recipe_re_resolution_rules}}
context budget: {{context_budget}}
