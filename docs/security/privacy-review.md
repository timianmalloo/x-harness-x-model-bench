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
review-by: "2027-03-22"
review-suggested: []
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

<!-- rolled up from 1 artifact(s) by docs-graph.py rollup on 2026-09-23 -->

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

## 7. Gaps and flagged unknowns

None for phase 1.
