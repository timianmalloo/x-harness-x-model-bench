---
id: note-20261003-deviation-coord-transport-grok-session-new
title: "Repo-local deviation - coord_transport accepts Grok watcher acks during session/new"
type: decision-note
status: resolved
owner: "@timianmalloo"
tags: [ai-forward-pack, deviation, grok, acp, transport, retired]
links:
  - { to: note-20261003-spike-e1-job-alone, rel: relates-to }
review-by: "2027-04-03"
summary: >-
  RETIRED 2026-10-06. The repo-local coord_transport.py hunk that accepted Grok's watcher acknowledgement during
  session/new is upstream in ai-forward revision 99 (7ea5dea, XPORT-A); /updatepack replaced the local copy
  with the pack text and no repo-local deviation remains in that file.
---

# Deviation: Grok watcher ack during session/new (retired)

- **Retired (2026-10-06, session `lanef-e1e4`).** ai-forward revision 99 (`7ea5dea`) carries the fix as XPORT-A:
  session/new accepts the watcher acknowledgement, `reloaded` may be 0 or 1, and it also holds acknowledgements
  that arrive before the initialize response until the release floor is known. `/updatepack` 97 -> 99 parked the
  file as a CONFLICT (the local hunk and the upstream hunk overlap); the reconciliation took the revision-99 text
  wholesale, which is a superset of this deviation. The `REPO-LOCAL DEVIATION` marker is gone, and
  `tests/test_coord_transport_grok_session_new.py` stays as this repo's regression test for the measured order.
  The history below is kept as the record.

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
