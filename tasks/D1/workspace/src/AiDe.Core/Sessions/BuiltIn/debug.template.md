---
id: debug
version: 1
intent: fix a defect
audience: agent
when_to_use: "Behavior diverges from expectation and the cause is unknown."
why: "Repro-first and characterization-before-fix prevent fix-shaped guesses and regression roulette."
provenance: "Transcribed from Addendum B §B4, row `debug` (Ruling 30): when_to_use and why byte-for-byte from B4's columns, fields the mechanical slug of its core-fields column, body a slot rendering of that column. Not authored."
fields:
  - { name: symptom, type: text, required: true }
  - { name: repro_first, type: text, required: true }
  - { name: isolation_plan, type: text, required: true }
  - { name: characterization_test_before_fix, type: text, required: true }
  - { name: done_when, type: text, required: true }
---
symptom: {{symptom}}
repro-first: {{repro_first}}
isolation plan: {{isolation_plan}}
characterization-test-before-fix: {{characterization_test_before_fix}}
done-when: {{done_when}}
