---
id: design-decision
version: 1
intent: produce an ADR
audience: conductor/agent
when_to_use: "Choosing between approaches with lasting consequences."
why: "Decisions without recorded forces and options get relitigated; the ADR shape (plus council vetoes) prevents it and lands as a decision node."
provenance: "Transcribed from Addendum B §B4, row `design-decision` (Ruling 30): when_to_use and why byte-for-byte from B4's columns, fields the mechanical slug of its core-fields column, body a slot rendering of that column. Not authored."
fields:
  - { name: problem, type: text, required: true }
  - { name: forces, type: text, required: true }
  - { name: options, type: text, required: true }
  - { name: council_vetoes, type: text, required: true }
  - { name: output_contract, type: text, required: true }
---
problem: {{problem}}
forces: {{forces}}
options: {{options}}
council/vetoes: {{council_vetoes}}
output contract: {{output_contract}}
