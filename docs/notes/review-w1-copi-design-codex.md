---
id: review-w1-copi-design-codex
title: "W1-COP-I cross-vendor design review"
type: decision-note
status: accepted
owner: "@timianmalloo"
links:
  - { to: coordination-finish-harness-bench, rel: relates-to }
review-by: "2026-10-08"
summary: >-
  Codex cross-vendor review of phase2-copilot-profile revision 3.1 found no
  defect that stops implementation of the W1-COP-I pinned-tools slice.
---

# W1-COP-I cross-vendor design review

**Verdict: none found.** I found no defect in `docs/design/phase2-copilot-profile.md` revision 3.1 that would stop implementation as written.

I checked the section 4.1 launch and isolation contract, section 4.2 package and optional-adapter contract, section 5 pattern, and section 13 tool and build tests against the current `tools.py`, `test_tools.py`, package manifest, and Owner rulings R-12 and R-17. Section 4.2's `adapter: None` is compatible with the existing four-key build record and `check_build` comparison once `resolve()` supplies nullable adapter fields.

**Packaging observation, not a design blocker:** npm lists `@github/copilot@1.0.89-1` and `@anthropic-ai/claude-agent-sdk@0.3.282`. The newest listed `@agentclientprotocol/claude-agent-acp` release, 0.81.2, declares SDK 0.3.280. The implementation must establish a single effective 0.3.282 SDK in the lockfile and check the installed adapter launch before reporting R-17 satisfied. If that cannot install, R-17 permits 2.1.281 as the fallback.

This review is limited to the design's implementability for the assigned pinned-tools slice. Runtime model qualification and other W1-COP-I surfaces belong to later slices and joins.
