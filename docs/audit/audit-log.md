---
id: audit-log
title: "Audit & Change Log"
type: doc
status: accepted
owner: "@maintainers"
tags: [audit, history, change-log, project-memory]
links: []
review-by: 2027-09-23
review-suggested: []
summary: >-
  The durable, committed history of what was prompted, done, and decided in this
  repository, so work compounds across sessions. The two JSONL files are the source
  of truth; audit-data.js and index.html are derived projections.
---

# Audit & Change Log

`audit-log.jsonl` records every meaningful prompt, skill run and script; `change-log.jsonl`
records the design decisions. Browse them at [`index.html`](index.html) or via `/auditlog`.
All writes go through `audit-log.py` - never hand-append the JSONL.
