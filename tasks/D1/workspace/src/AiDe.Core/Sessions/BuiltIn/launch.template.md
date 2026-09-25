---
id: launch
version: 1
intent: initiative
audience: conductor
when_to_use: "Starting a new initiative or multi-phase effort from a cold start."
why: "First prompts set authority order, setup sequence, and gates; improvising those mid-run is where big efforts go sideways. Derived from this project's launch prompt."
provenance: "Transcribed from Addendum B §B4, row `launch` (Ruling 30): when_to_use and why byte-for-byte from B4's columns, fields the mechanical slug of its core-fields column, body a slot rendering of that column. Not authored."
fields:
  - { name: goal_block, type: text, required: true }
  - { name: roles_authority, type: text, required: true }
  - { name: setup_sequence, type: text, required: true }
  - { name: standing_constraints, type: text, required: true }
  - { name: phase_gate, type: text, required: true }
---
goal block: {{goal_block}}
roles/authority: {{roles_authority}}
setup sequence: {{setup_sequence}}
standing constraints: {{standing_constraints}}
phase gate: {{phase_gate}}
