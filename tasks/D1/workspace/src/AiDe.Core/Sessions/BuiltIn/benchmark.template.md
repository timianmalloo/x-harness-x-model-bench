---
id: benchmark
version: 1
intent: comparable runs
audience: conductor
when_to_use: "Comparing models, engines, or prompt shapes on the same task."
why: "Comparisons are meaningless without frozen goals, fixtures, and declared cohorts; feeds bench import (spec §8.4)."
provenance: "Transcribed from Addendum B §B4, row `benchmark` (Ruling 30): when_to_use and why byte-for-byte from B4's columns, fields the mechanical slug of its core-fields column, body a slot rendering of that column. Not authored."
fields:
  - { name: frozen_goal_block, type: text, required: true }
  - { name: fixtures, type: text, required: true }
  - { name: cohort_declaration, type: text, required: true }
  - { name: no_peeking_constraints, type: text, required: true }
---
frozen goal block: {{frozen_goal_block}}
fixtures: {{fixtures}}
cohort declaration: {{cohort_declaration}}
no-peeking constraints: {{no_peeking_constraints}}
