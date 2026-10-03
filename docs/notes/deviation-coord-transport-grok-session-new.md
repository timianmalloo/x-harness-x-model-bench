---
id: note-20261003-deviation-coord-transport-grok-session-new
title: "Repo-local deviation - coord_transport accepts Grok watcher acks during session/new"
type: decision-note
status: accepted
owner: "@timianmalloo"
tags: [ai-forward-pack, deviation, grok, acp, transport]
links:
  - { to: note-spike-e1-job-alone, rel: relates-to }
review-by: "2027-04-03"
summary: >-
  docs/ai-forward-pack/scripts/coord_transport.py is patched locally so Grok's own skills/workflows watcher
  acknowledgement is accepted while session/new is in flight. Upstream (ai-forward) needs the same hunk.
---

# Deviation: Grok watcher ack during session/new

- **Defect.** 2 of 3 Wave 2 Grok dispatches (runs `w2-g1-e1e4`, `w2-enva-e1e4`, 2026-10-03) failed with
  `protocol_error` at phase `session/new`. Grok 1.0.41 sent `{"id": "skills-reload", "jsonrpc": "2.0",
  "result": {"result": {"reloaded": 0}}}` before the session/new response. The pack accepted it only in
  `session/prompt`. It is a race on Grok's side.
- **File and hunk.** `docs/ai-forward-pack/scripts/coord_transport.py`, `_Session.rpc`, the
  `grok_reload_compat` branch (marked `REPO-LOCAL DEVIATION`). It now also applies when `method == "session/new"`,
  and the `reloaded` count may be 0 or 1 (the old rule required 1). Ids stay `GROK_WATCHER_IDS`, the shape stays
  exact, the release floor stays 1.0.34, and each ack counts in `compatibility_responses`.
- **Proof.** `tests/test_coord_transport_grok_session_new.py` (red at `cd10124f`): the measured order creates the
  session; an unknown id, an extra key, or a release below the floor is still `protocol_error`.
- **Upstream follow-up (operator).** Push the same hunk and test to ai-forward, then `/updatepack` here. Until then
  `pack-apply.py` three-way merges over this hunk (repo-local deviations are honoured).
