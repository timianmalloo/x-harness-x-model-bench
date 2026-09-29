---
id: investigation
version: 1
intent: answer, don't author
audience: agent
when_to_use: "You need an answer or analysis, and nothing should be modified."
why: "Separating inquiry from authorship keeps evidence honest, lanes cheap, and read-only policy enforceable."
provenance: "Transcribed from Addendum B §B4, row `investigation` (Ruling 30): when_to_use and why byte-for-byte from B4's columns, fields the mechanical slug of its core-fields column, body a slot rendering of that column. Not authored."
fields:
  - { name: question, type: text, required: true }
  - { name: evidence_standard, type: text, required: true }
  - { name: disconfirm_step, type: text, required: true }
  - { name: report_shape, type: text, required: true }
  - { name: no_edit_constraint, type: text, required: true }
---
question: {{question}}
evidence standard: {{evidence_standard}}
disconfirm step: {{disconfirm_step}}
report shape: {{report_shape}}
no-edit constraint: {{no_edit_constraint}}
