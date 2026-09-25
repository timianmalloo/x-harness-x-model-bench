---
id: converge
version: 1
intent: merge tracks
audience: conductor
when_to_use: "Parallel tracks are done and must come together."
why: "The merge is the deliverable; order, gates, and regeneration must be explicit or converge degrades into conflict triage. Spec §6.5 as a prompt."
provenance: "Transcribed from Addendum B §B4, row `converge` (Ruling 30): when_to_use and why byte-for-byte from B4's columns, fields the mechanical slug of its core-fields column, body a slot rendering of that column. Not authored."
fields:
  - { name: order, type: text, required: true }
  - { name: gates, type: text, required: true }
  - { name: regeneration, type: text, required: true }
  - { name: open_seam_rule, type: text, required: true }
---
order: {{order}}
gates: {{gates}}
regeneration: {{regeneration}}
open-seam rule: {{open_seam_rule}}
