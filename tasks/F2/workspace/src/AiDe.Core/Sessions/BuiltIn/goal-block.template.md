---
id: goal-block
version: 1
intent: execute
audience: conductor
when_to_use: "You know the outcome you want and can name what done means."
why: "Ends-plus-latitude beats step lists for reasoning models; CT19 makes every run measurable and scoreable."
provenance: "Transcribed from Addendum B §B4, row `goal-block` (Ruling 30): when_to_use and why byte-for-byte from B4's columns, fields the mechanical slug of its core-fields column MINUS tier, fan_out_cap and budget (Rulings 56, 63, 72: the tier is the compile step's projection, the cap and the budget are session settings — never per-prompt fields; B4's row predates the rulings and is a finding for the spec's owner), body a slot rendering of that column. Not authored."
provenance_dropped_from_why: "(Addendum A's \"Goal block shape\" is hereby re-based as this template — one mechanism, not two.)"
provenance_dropped_reason: "Ruling 30 deviation i: spec commentary about re-basing Addendum A's goal-block shape, meaningless to an end user reading a picker tooltip. Kept here, dropped from why."
fields:
  - { name: goal, type: text, required: true }
  - { name: done_when, type: text, required: true }
  - { name: not_in_scope, type: text, required: true }
---
goal: {{goal}}
done_when: {{done_when}}
not_in_scope: {{not_in_scope}}
