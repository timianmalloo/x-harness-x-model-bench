---
id: review
version: 1
intent: adversarial critique
audience: agent
when_to_use: "An artifact exists and needs adversarial critique before it ships or merges."
why: "Rubric, severity classes, and veto semantics turn opinion into gate evidence; the persona roster plugs into the audience field."
provenance: "Transcribed from Addendum B §B4, row `review` (Ruling 30): when_to_use and why byte-for-byte from B4's columns, fields the mechanical slug of its core-fields column, body a slot rendering of that column. Not authored."
fields:
  - { name: artifact, type: text, required: true }
  - { name: rubric, type: text, required: true }
  - { name: severity_classes, type: text, required: true }
  - { name: veto_semantics, type: text, required: true }
---
artifact: {{artifact}}
rubric: {{rubric}}
severity classes: {{severity_classes}}
veto semantics: {{veto_semantics}}
