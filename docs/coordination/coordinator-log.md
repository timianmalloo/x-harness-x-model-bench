---
id: coordinator-log
title: "Coordinator hand-back log (append-only)"
type: doc
status: active
owner: "@timianmalloo"
tags: [coordination, register]
links:
  - { to: coordination-eval-wave2-e1-briefs, rel: relates-to }
  - { to: coordination-eval-wave2-e234-briefs, rel: relates-to }
review-by: "2026-11-05"
summary: >-
  One entry per Coordinator hand-back session, appended at the end, newest last. Class register in
  .agents/artifacts.yml: concurrent appends union-merge, so seats never conflict here. Entries up to
  Coordinator #28 live in docs/coordination/eval-wave2-e1/README.md section 8.
---

# Coordinator hand-back log

Append a new `## Coordinator #<n> (date, base, Leader epoch; branch)` section at the end. Never edit an earlier entry; correct it in a new one. Entries #1-#28 are in `docs/coordination/eval-wave2-e1/README.md` section 8.
