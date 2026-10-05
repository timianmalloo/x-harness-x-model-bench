---
id: coordinator-log
title: "Coordinator hand-back log (index; one file per session)"
type: doc
status: active
owner: "@timianmalloo"
tags: [coordination, register]
links:
  - { to: coordination-eval-wave2-e1-briefs, rel: relates-to }
  - { to: coordination-eval-wave2-e234-briefs, rel: relates-to }
review-by: "2026-11-05"
summary: >-
  Where Coordinator hand-back entries live. From #29 each session writes its own file,
  docs/coordination/coordinator-log/c<NN>.md, so concurrent sessions never share an append point (the
  register merge class is JSONL-only, measured 2026-10-05; see .agents/artifacts.yml). Entries #1-#28 live
  in docs/coordination/eval-wave2-e1/README.md section 8.
---

# Coordinator hand-back log

Each hand-back session writes **one new file**, `docs/coordination/coordinator-log/c<NN>.md` (for example `c29.md`), headed `# Coordinator #<NN> (date, base, Leader epoch; branch)`. It never edits another session's file; a correction goes in its own new file. Do not append to this index or to README section 8: two sessions appending to one markdown file conflict at every join (2026-10-04/05), and the `register` class cannot union markdown. Entries #1-#28 are in `docs/coordination/eval-wave2-e1/README.md` section 8.
