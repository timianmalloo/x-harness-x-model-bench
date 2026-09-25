---
id: privacy-review
title: "Privacy Review"
type: privacy-review
status: draft
owner: "@timianmalloo"
phase: "Phase 1 · walking skeleton"
tags: [privacy, data-governance]
links:
  - { to: arch-harness-bench, rel: documents }
  - { to: design-phase1-walking-skeleton, rel: documents }
  - { to: design-run-lifecycle-model, rel: documents }
  - { to: design-phase2-copilot-profile, rel: documents }
  - { to: design-phase3-gateway-judges, rel: documents }
review-by: "2027-03-22"
review-suggested:
  - { by: design-phase3-gateway-judges, on: 2026-09-25, reason: "row-17 gateway design gated (rev 3): Fable judge, Codex not qualified (DR-GW-1), CLI-added context (DR-GW-5)" }
summary: >-
  The only personal data is the operator's own: the account email that appears in harness transcripts,
  and the username in home paths. Both stay in local, gitignored run archives; the report embeds no
  transcript text and shows archive-relative paths. No third party receives personal data beyond the
  model providers the operator's own subscriptions already use.
---

# Privacy Review

*The repo-level rollup of every component's privacy analysis (LINDDUN-lite). **The register in section 2
is generated**; refresh it with:*

```bash
python3 docs/ai-forward-pack/scripts/docs-graph.py rollup --heading "Privacy analysis (LINDDUN-lite)" --type design
```

## 1. Personal-data inventory

| Category | Examples | Where stored | Where it flows | Lawful basis / purpose | Retention | Owning design |
| --- | --- | --- | --- | --- | --- | --- |
| Operator account identity | Email in Claude transcripts | `runs/<id>/` archives (gitignored) | Nowhere; the report embeds no transcript text | The operator's own data, for their own benchmark | Until the owner deletes `runs/<id>` | design-phase1-walking-skeleton |
| Operator username | Home paths in records | `runs/<id>/` archives | The report shows archive-relative paths only | As above | As above | design-phase1-walking-skeleton |

## 2. Findings register (generated — see command above)

| source | Data | Finding | Disposition | Control | Retention |
|---| --- | --- | --- | --- | --- |
| [design-phase1-walking-skeleton](../design/phase1-walking-skeleton.md) | Operator email in Claude transcripts (account context) | Identifiability | mitigate | Archives local (`runs/`, gitignored); the report embeds no transcript text | Until the owner deletes `runs/<id>` |
| [design-phase1-walking-skeleton](../design/phase1-walking-skeleton.md) | Username and home paths | Identifiability | mitigate | Cells root outside the profile; the report shows archive-relative paths | As above |
| [design-phase2-copilot-profile](../design/phase2-copilot-profile.md) | User name in paths, account context in the cell home and its local archive | Identifiability | accept (local only) | The archive stays local; nothing new leaves the host; HB-SEC-001 unchanged | Until the owner deletes `runs/<id>` |
| [design-phase2-copilot-profile](../design/phase2-copilot-profile.md) | The same, in the capture that becomes committed samples | Disclosure, linkability | mitigate | scrub-rule/3 (paths rewritten, identifiers replaced, opaque keys blanked, every `system.message` field except its identity digested); fail-closed leak check | Git history (scrubbed only) |
| [design-phase2-copilot-profile](../design/phase2-copilot-profile.md) | Vendor system prompt and request bodies | Disclosure | mitigate | Digest plus marker list, as a class (section 12), with a scrub-time control. Rule 2 missed `system.message.contentBlocks`; it was re-scrubbed in `f952f87`, and the branch is squash-merged so the blob never reaches main (R-30 condition 3) | Not committed |
| [design-phase2-copilot-profile](../design/phase2-copilot-profile.md) | What a committed sample holds | Unawareness | mitigate | `provenance.json` states the rule, the counts and the hashes | With the sample |
| [design-phase3-gateway-judges](../design/phase3-gateway-judges.md) | Artifact text → vendor | D: an agent wrote the operator's e-mail, user name or home path into an artifact | mitigate | `egress.check`; `HB-GW-009` | nothing sent; archive per `runs/` retention (P1 deletes) |
| [design-phase3-gateway-judges](../design/phase3-gateway-judges.md) | CLI context → vendor | D/I: Claude adds the account e-mail and org UUID (both measured text-mode turns; Inferred: every call); Codex adds `C:/Users/<user>/.agents/skills` and 6 skill descriptions | detect; disposition DR-GW-5 | report-time detector and header disclosure. The same context reaches each vendor in every cell of that harness today | vendor retention per the operator's plan |
| [design-phase3-gateway-judges](../design/phase3-gateway-judges.md) | Judge records → local archive | I: records hold the e-mail, user name and home path | mitigate | local `runs/`, never published (spec `:572`); T-GW-34 | P1 deletes `runs/` |
| [design-phase3-gateway-judges](../design/phase3-gateway-judges.md) | Judge calls → vendor account | L: calls linked to the operator's subscription | accept | ADR-0009 accepted it (subscriptions only) | vendor retention |
| [design-phase3-gateway-judges](../design/phase3-gateway-judges.md) | Calibration labels | I: the operator's judgements, committed | accept | scores only | git history; the operator can remove the file |

<!-- rolled up from 3 artifact(s) by docs-graph.py rollup on 2026-09-25 -->

`design-run-lifecycle-model` touches no personal data (its section says so and is not a findings table).

## 3. Data-subject rights paths

The only data subject is the operator. Erasure: delete `runs/<id>/`. Nothing else holds a copy.

## 4. Telemetry alignment (O-series)

Telemetry is read from the harnesses' own session records and written to the local ledger. It holds no personal data beyond the inventory above. The published report is checked for credential values (T-SEC-report). No email check exists; the report carries no transcript text by construction.

## 5. Transfers and processors

The model providers (Anthropic, OpenAI, GitHub) receive prompts through the operator's own subscriptions, as they do outside the benchmark. The benchmark adds no processor.

## 6. Accepted privacy risks

| Finding | Accepted by | Rationale | Residual risk | Revisit when |
| --- | --- | --- | --- | --- |
| Archives keep full transcripts with the operator's email | @timianmalloo (ADR-0012) | The operator's own data, on their own machine | A shared archive would carry it | Archives are shared or published |
| Judge CLIs add the account e-mail (Claude) and the operator's skill root with user name and home path (Codex) to judge calls (design-phase3-gateway-judges, DR-GW-5) | **pending the Owner's DR-GW-5 ruling**; no live judge pass before it | The same context reaches each vendor in every cell of that harness; detected and disclosed per call | Those identifiers at the vendor that already holds the account | DR-GW-5 ruling |
| Judge calls are linked to the operator's subscription | @timianmalloo (ADR-0009, subscriptions only) | No API keys by owner decision | Vendor-side linkage of judge traffic to the account | An API-key backend is adopted |

## 7. Gaps and flagged unknowns

None for phase 1.
