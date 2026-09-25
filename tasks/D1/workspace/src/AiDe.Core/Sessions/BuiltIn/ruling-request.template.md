---
id: ruling-request
version: 1
intent: decision
audience: owner
when_to_use: "A judgment call is blocking progress and the options are known."
why: "Options-costs-recommendation lets the Owner rule in one pass; auto-applied whenever the conductor convenes the Owner (§B6)."
provenance: "Transcribed from Addendum B §B4, row `ruling-request` (Ruling 30): when_to_use and why byte-for-byte from B4's columns. Fields, body and tier_default are B3.1's excerpt VERBATIM (Ruling 30 deviation ii) — B4's cell reads \"options+costs\" where B3.1 names the field `options` and puts cost in its hint; B3.1 is the file-format authority, and its body slot `{{#options}}` would dangle against any other name."
tier_default: T0
fields:
  - { name: question,        type: text,    required: true,
      hint: "One decidable question. If two, file two." }
  - { name: options,         type: list,    required: true, min: 2,
      hint: "Each with cost/consequence. Include do-nothing when honest." }
  - { name: recommendation,  type: text,    required: true }
  - { name: evidence,        type: mentions, required: false }
  - { name: decides_by,      type: text,    required: false,
      hint: "What makes this urgent, if anything." }
---
A ruling is requested. Authority: your decision counts as the user's (CT20).
Question: {{question}}
Options and costs:
{{#options}}- {{.}}{{/options}}
Recommendation and reasoning: {{recommendation}}
Evidence: {{evidence}}
Record your ruling with rationale; it will be filed as a decision note and audit entry.
