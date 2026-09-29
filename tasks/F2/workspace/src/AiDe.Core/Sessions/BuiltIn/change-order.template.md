---
id: change-order
version: 1
intent: amend a run
audience: conductor
when_to_use: "A run is in flight and its goal, scope, or constraints must change."
why: "Scope drift is the default failure mode; an amendment needs reconciliation against reality and re-ratification, not a side note in chat. CT22 guard baked in."
provenance: "Transcribed from Addendum B §B4, row `change-order` (Ruling 30): when_to_use and why byte-for-byte from B4's columns, fields the mechanical slug of its core-fields column, body a slot rendering of that column. Not authored."
fields:
  - { name: what_changed, type: text, required: true }
  - { name: intake_steps, type: text, required: true }
  - { name: amended_goal_block, type: text, required: true }
  - { name: re_plan_scope, type: text, required: true }
  - { name: added_constraints, type: text, required: true }
---
what changed: {{what_changed}}
intake steps: {{intake_steps}}
amended goal block: {{amended_goal_block}}
re-plan scope: {{re_plan_scope}}
added constraints: {{added_constraints}}
