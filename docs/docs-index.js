// Derived from artifact frontmatter by scripts/docs-graph.py — DO NOT hand-edit (frontmatter wins; see knowledge-visualization.md V2/V18).
window.DOCS_INDEX = {
  "schemaVersion": "docs-index/v2",
  "project": "x-harness-x-model-bench",
  "generator": "docs-graph.py derive",
  "rootId": "adr-0001-cell-containers",
  "artifactTypes": [
    "knowledge",
    "glossary",
    "spec",
    "architecture",
    "adr",
    "design",
    "design-language",
    "investigation",
    "proof-pack",
    "decision-note",
    "threat-model",
    "privacy-review",
    "api",
    "source",
    "doc",
    "index",
    "plan"
  ],
  "relationRegistry": [
    "implements",
    "refines",
    "depends-on",
    "supersedes",
    "tested-by",
    "documents",
    "uses-term",
    "relates-to"
  ],
  "policyVersion": "traversal-policy/v1",
  "policySha256": "968b035a9618e6f997592e4f7ae91fd412b1c059c0ee89d6d8ff3025c26279fd",
  "traversalPolicies": {
    "grounding": [
      {
        "rel": "implements",
        "direction": "outbound",
        "priority": 0
      },
      {
        "rel": "refines",
        "direction": "outbound",
        "priority": 1
      },
      {
        "rel": "depends-on",
        "direction": "outbound",
        "priority": 2
      },
      {
        "rel": "uses-term",
        "direction": "outbound",
        "priority": 3
      },
      {
        "rel": "tested-by",
        "direction": "outbound",
        "priority": 4
      },
      {
        "rel": "documents",
        "direction": "outbound",
        "priority": 5
      }
    ],
    "impact": [
      {
        "rel": "implements",
        "direction": "inbound",
        "priority": 0
      },
      {
        "rel": "refines",
        "direction": "inbound",
        "priority": 1
      },
      {
        "rel": "depends-on",
        "direction": "inbound",
        "priority": 2
      },
      {
        "rel": "tested-by",
        "direction": "inbound",
        "priority": 3
      },
      {
        "rel": "uses-term",
        "direction": "inbound",
        "priority": 4
      }
    ],
    "proof": [
      {
        "rel": "tested-by",
        "direction": "outbound",
        "priority": 0
      }
    ],
    "explore-neighborhood": [
      {
        "rel": "depends-on",
        "direction": "outbound",
        "priority": 0
      },
      {
        "rel": "depends-on",
        "direction": "inbound",
        "priority": 0
      },
      {
        "rel": "documents",
        "direction": "outbound",
        "priority": 1
      },
      {
        "rel": "documents",
        "direction": "inbound",
        "priority": 1
      },
      {
        "rel": "implements",
        "direction": "outbound",
        "priority": 2
      },
      {
        "rel": "implements",
        "direction": "inbound",
        "priority": 2
      },
      {
        "rel": "refines",
        "direction": "outbound",
        "priority": 3
      },
      {
        "rel": "refines",
        "direction": "inbound",
        "priority": 3
      },
      {
        "rel": "relates-to",
        "direction": "outbound",
        "priority": 4
      },
      {
        "rel": "relates-to",
        "direction": "inbound",
        "priority": 4
      },
      {
        "rel": "supersedes",
        "direction": "outbound",
        "priority": 5
      },
      {
        "rel": "supersedes",
        "direction": "inbound",
        "priority": 5
      },
      {
        "rel": "tested-by",
        "direction": "outbound",
        "priority": 6
      },
      {
        "rel": "tested-by",
        "direction": "inbound",
        "priority": 6
      },
      {
        "rel": "uses-term",
        "direction": "outbound",
        "priority": 7
      },
      {
        "rel": "uses-term",
        "direction": "inbound",
        "priority": 7
      }
    ]
  },
  "limits": {
    "indexBytes": 5242880,
    "artifacts": 1000,
    "relationships": 5000,
    "spatialNodes": 500,
    "spatialEdges": 1000,
    "visibleLabels": 150,
    "surfaces": 100
  },
  "artifacts": [
    {
      "id": "adr-0001-cell-containers",
      "path": "docs/adr/0001-cells-run-in-per-cell-linux-containers.md",
      "title": "ADR-0001: Every measured cell runs in its own hardened Linux container",
      "type": "adr",
      "status": "superseded",
      "owner": "@timianmalloo",
      "phase": "all phases",
      "reviewBy": "2027-09-23",
      "reviewSuggested": [],
      "summary": "Each cell runs in a fresh, hardened Linux container under Docker Desktop (WSL2), with a deterministic name, its own network, only its workspace and its own harness home mounted, and read-only permission files. It is the only option that gives all three harnesses the same containment and keeps host credentials unreachable by construction.",
      "tags": [
        "benchmark",
        "isolation",
        "security",
        "containers"
      ],
      "links": [
        {
          "to": "arch-harness-bench",
          "rel": "refines"
        },
        {
          "to": "spec-harness-bench",
          "rel": "implements"
        },
        {
          "to": "note-spike-isolation-permissions",
          "rel": "depends-on"
        }
      ],
      "diagrams": [],
      "sourceSha256": "f4bee0a97122890b7089563b08f055a42b6b8e7c7c1ccb0d4a56e0cbd1257b76"
    },
    {
      "id": "adr-0002-cell-driver",
      "path": "docs/adr/0002-bench-owned-acp-cell-driver.md",
      "title": "ADR-0002: The bench drives cells with its own ACP cell driver, not the pack's coord-runner or Harbor",
      "type": "adr",
      "status": "draft",
      "owner": "@timianmalloo",
      "phase": "all phases",
      "reviewBy": "2027-09-23",
      "reviewSuggested": [],
      "summary": "Measured cells are launched by a small bench-owned driver that speaks ACP to the containerised harness with a container-side cwd, a verbatim prompt, a per-cell model pin, deny-all permissions and a deadline on every step. The pack's coord-runner cannot meet US-9, US-10 or US-11 as installed; Harbor's one-shot, permissive agent runs cannot meet US-10 (scenario 1), US-14 or at-most-once. Both are recorded. By owner ruling the benchmark must not run in the coordinator's runner.",
      "tags": [
        "benchmark",
        "runner",
        "acp",
        "pack",
        "harbor"
      ],
      "links": [
        {
          "to": "arch-harness-bench",
          "rel": "refines"
        },
        {
          "to": "spec-harness-bench",
          "rel": "implements"
        },
        {
          "to": "note-spike-runner-path",
          "rel": "depends-on"
        },
        {
          "to": "note-spike-isolation-permissions",
          "rel": "depends-on"
        }
      ],
      "diagrams": [],
      "sourceSha256": "1a3cd0033f199b52df74316a8df31cb740fedcec441a637d9acf019334a760f5"
    },
    {
      "id": "adr-0003-harness-profile",
      "path": "docs/adr/0003-per-cell-harness-profile.md",
      "title": "ADR-0003: A pinned, per-cell harness profile with a scoped credential and a verified model",
      "type": "adr",
      "status": "draft",
      "owner": "@timianmalloo",
      "phase": "all phases",
      "reviewBy": "2027-09-23",
      "reviewSuggested": [],
      "summary": "Each harness has a versioned profile (Ports & Adapters): pinned CLI build, a fresh per-cell home seeded only with a credential and read-only permission files, a per-cell model pin, and a post-cell check that at least one model call succeeded on the pinned model. Operator subscription logins may run only operator-authored tasks; every archive and egress is scanned for the exact credential values issued to the run.",
      "tags": [
        "benchmark",
        "harness",
        "identity",
        "model-pinning"
      ],
      "links": [
        {
          "to": "arch-harness-bench",
          "rel": "refines"
        },
        {
          "to": "spec-harness-bench",
          "rel": "implements"
        },
        {
          "to": "note-spike-isolation-permissions",
          "rel": "depends-on"
        }
      ],
      "diagrams": [],
      "sourceSha256": "3d3ab6acf8702154d173901bfded9f58c598b32267ee5aa54afb2571599441b1"
    },
    {
      "id": "adr-0004-static-permissions",
      "path": "docs/adr/0004-static-permissions-offline-dependencies.md",
      "title": "ADR-0004: A static, symmetric permission profile and offline task dependencies",
      "type": "adr",
      "status": "draft",
      "owner": "@timianmalloo",
      "phase": "all phases",
      "reviewBy": "2027-09-23",
      "reviewSuggested": [],
      "summary": "Every harness runs with the same tool classes allowed statically, with no model-based approval: file edits and shell inside the container, no web tools, no package registry. Task dependencies are restored into the image before the clock starts.",
      "tags": [
        "benchmark",
        "permissions",
        "security"
      ],
      "links": [
        {
          "to": "arch-harness-bench",
          "rel": "refines"
        },
        {
          "to": "spec-harness-bench",
          "rel": "implements"
        },
        {
          "to": "note-spike-isolation-permissions",
          "rel": "depends-on"
        }
      ],
      "diagrams": [],
      "sourceSha256": "8499733ad87142a01be36b0921e70009aa639309bee62888a486f66a8ec7b59e"
    },
    {
      "id": "adr-0005-egress-control",
      "path": "docs/adr/0005-egress-control.md",
      "title": "ADR-0005: Cells reach only model APIs; benchmark model calls pass one egress gate",
      "type": "adr",
      "status": "draft",
      "owner": "@timianmalloo",
      "phase": "phase 2 onward (recorded, not enforced, in phase 1)",
      "reviewBy": "2027-09-23",
      "reviewSuggested": [],
      "summary": "Cell containers sit on an internal Docker network whose only way out is an allowlisting egress proxy for the vendor model and auth hosts. Every call the benchmark itself makes to a vendor (judges, summaries, matcher) and every report publication passes one egress gate that scans for secrets and personal data first.",
      "tags": [
        "benchmark",
        "security",
        "network",
        "privacy"
      ],
      "links": [
        {
          "to": "arch-harness-bench",
          "rel": "refines"
        },
        {
          "to": "spec-harness-bench",
          "rel": "implements"
        }
      ],
      "diagrams": [],
      "sourceSha256": "86f893670743408d3f59789abbd557ecdbb57114034bd52523bb0c9857b77b54"
    },
    {
      "id": "adr-0006-results-data-model",
      "path": "docs/adr/0006-append-only-run-ledger-and-derived-results.md",
      "title": "ADR-0006: A hash-chained, append-only record per run; every result is a derived view",
      "type": "adr",
      "status": "draft",
      "owner": "@timianmalloo",
      "phase": "all phases",
      "reviewBy": "2027-09-23",
      "reviewSuggested": [],
      "summary": "The durable record is a set of append-only, hash-chained JSON Lines facts per run with declared grains (lifecycle events, model calls, tool calls, archive files, grading passes, scores and verdict uses), immutable content-addressed dimensions, and one shared content-addressed verdict cache. The declared egress events fact is retired (Amendment 4, R-80): judge sends live in verdict uses and model calls, and the publication scan in report-record.json beside the report. Current states, costs, composites and statistics are derived projections computed in memory; no results database is persisted.",
      "tags": [
        "benchmark",
        "data-model",
        "persistence",
        "grain"
      ],
      "links": [
        {
          "to": "arch-harness-bench",
          "rel": "refines"
        },
        {
          "to": "spec-harness-bench",
          "rel": "implements"
        }
      ],
      "diagrams": [],
      "sourceSha256": "8d3c751bc5e4933f734015c94a7c1b036d4e69e46d36b481917378131013303b"
    },
    {
      "id": "adr-0007-run-engine",
      "path": "docs/adr/0007-deterministic-run-engine.md",
      "title": "ADR-0007: A deterministic run engine schedules cells; the LLM coordinator never does",
      "type": "adr",
      "status": "draft",
      "owner": "@timianmalloo",
      "phase": "all phases",
      "reviewBy": "2027-09-23",
      "reviewSuggested": [],
      "summary": "`bench run` is one deterministic process per run: single writer of the lifecycle log, write-ahead launch intents, named containers it can always find and kill, monotonic budgets with host-suspend detection, apply-once control files, a closed failure taxonomy that separates infrastructure from harness faults, and a circuit breaker. The Claude Code session compiles, confirms and relays; it reads only schema-bound status.",
      "tags": [
        "benchmark",
        "runner",
        "idempotency",
        "concurrency",
        "failure-modes"
      ],
      "links": [
        {
          "to": "arch-harness-bench",
          "rel": "refines"
        },
        {
          "to": "spec-harness-bench",
          "rel": "implements"
        }
      ],
      "diagrams": [],
      "sourceSha256": "a9d695b9f909b244be1bd461ac01c4441889a5030a69e062a88c23ba0da0e6d2"
    },
    {
      "id": "adr-0008-telemetry",
      "path": "docs/adr/0008-telemetry-from-native-records.md",
      "title": "ADR-0008: Usage telemetry comes from each cell's archived native session record",
      "type": "adr",
      "status": "draft",
      "owner": "@timianmalloo",
      "phase": "all phases",
      "reviewBy": "2027-09-23",
      "reviewSuggested": [],
      "summary": "After a cell ends, the harness's native session record in the cell's own home is archived and hashed, then normalised into model_calls rows with OpenTelemetry GenAI attribute names. No OTel collector runs in v0.",
      "tags": [
        "benchmark",
        "telemetry",
        "cost"
      ],
      "links": [
        {
          "to": "arch-harness-bench",
          "rel": "refines"
        },
        {
          "to": "spec-harness-bench",
          "rel": "implements"
        },
        {
          "to": "note-spike-runner-path",
          "rel": "depends-on"
        }
      ],
      "diagrams": [],
      "sourceSha256": "753c1185e2c0a40e19aff879fd194d7fa75fdfcc645f5fd936bf91819de1bb8c"
    },
    {
      "id": "adr-0009-model-gateway",
      "path": "docs/adr/0009-model-gateway-for-benchmark-model-calls.md",
      "title": "ADR-0009: The benchmark's own model calls go through one tool-less model gateway",
      "type": "adr",
      "status": "draft",
      "owner": "@timianmalloo",
      "phase": "phase 3 onward (matcher T0 rung from phase 2)",
      "reviewBy": "2027-09-23",
      "reviewSuggested": [],
      "summary": "Judges, the AI summaries and the model rung of the scripted-user matcher call models through one gateway: no tools, schema-constrained output, agent text as delimited data, results read through the shared content-addressed cache, every payload through the egress gate. One backend is built: the headless vendor CLIs with every tool denied (owner ruling); if it is unavailable, the result is NOT_RECORDED.",
      "tags": [
        "benchmark",
        "judges",
        "ai",
        "security",
        "cost"
      ],
      "links": [
        {
          "to": "arch-harness-bench",
          "rel": "refines"
        },
        {
          "to": "spec-harness-bench",
          "rel": "implements"
        }
      ],
      "diagrams": [],
      "sourceSha256": "8484a42058c8616868d0bf948c9e36861ebbc7ed45c5ac6d689d0bc61366c300"
    },
    {
      "id": "adr-0010-untrusted-cell-output",
      "path": "docs/adr/0010-cell-output-is-untrusted-on-the-host.md",
      "title": "ADR-0010: Cell output is untrusted on the host; grading runs in containers",
      "type": "adr",
      "status": "draft",
      "owner": "@timianmalloo",
      "phase": "all phases",
      "reviewBy": "2027-09-23",
      "reviewSuggested": [],
      "summary": "Boundary B6: everything a cell wrote is untrusted. No host process executes, builds, imports or tests it; graders that run cell content do so in fresh no-network grading containers with read-only mounts. Host git runs only with a bench-owned configuration, the archiver never follows links, and no agentic tool on the host opens a cell workspace.",
      "tags": [
        "benchmark",
        "security",
        "grading",
        "boundary"
      ],
      "links": [
        {
          "to": "arch-harness-bench",
          "rel": "refines"
        },
        {
          "to": "spec-harness-bench",
          "rel": "implements"
        },
        {
          "to": "adr-0001-cell-containers",
          "rel": "depends-on"
        }
      ],
      "diagrams": [],
      "sourceSha256": "d0d60321801892e4f68e84d3f84a938d82fcc3e8c6679360c75e23cf9ac1319b"
    },
    {
      "id": "adr-0011-loa-python",
      "path": "docs/adr/0011-loa-conformance-in-python.md",
      "title": "ADR-0011: LOA conformance criteria mapped to Python, with a control per criterion",
      "type": "adr",
      "status": "draft",
      "owner": "@timianmalloo",
      "phase": "phase 1 onward",
      "reviewBy": "2027-09-23",
      "reviewSuggested": [],
      "summary": "The LOA conformance criteria C1–C11 are written for .NET analyzers; this Python codebase meets their intent through named lints and tests, one per criterion, run in CI. Two recorded deviations: cells act as a benchmark principal (not the requester's), and phase 1's unrestricted network is a time-boxed, fail-closed exception.",
      "tags": [
        "benchmark",
        "loa",
        "conformance",
        "testing"
      ],
      "links": [
        {
          "to": "arch-harness-bench",
          "rel": "refines"
        }
      ],
      "diagrams": [],
      "sourceSha256": "f647a1dc787a32c301f24cb7358a8f1f8cdb48ca33408d8402b2c2e390747b86"
    },
    {
      "id": "adr-0012-proportionate-security",
      "path": "docs/adr/0012-proportionate-security-single-operator.md",
      "title": "ADR-0012: Proportionate security for a single-operator local benchmark tool",
      "type": "adr",
      "status": "draft",
      "owner": "@timianmalloo",
      "phase": "all phases",
      "reviewBy": "2027-09-23",
      "reviewSuggested": [],
      "summary": "Owner ruling: harness-bench is a local tool run by one trusted operator on their own machine; git is a mechanism, not an entry point. The only adversary is the agent under test, and security controls are kept where they protect result validity or keep an agent from damaging the machine by accident. Provenance checks, the egress proxy requirement, SBOM/CVE gates and most negative security tests are dropped or made optional; third-party tasks may run on the operator's subscription logins.",
      "tags": [
        "benchmark",
        "security",
        "owner-ruling"
      ],
      "links": [
        {
          "to": "arch-harness-bench",
          "rel": "refines"
        },
        {
          "to": "adr-0001-cell-containers",
          "rel": "refines"
        },
        {
          "to": "adr-0003-harness-profile",
          "rel": "refines"
        },
        {
          "to": "adr-0005-egress-control",
          "rel": "refines"
        },
        {
          "to": "adr-0010-untrusted-cell-output",
          "rel": "refines"
        },
        {
          "to": "spec-harness-bench",
          "rel": "refines"
        }
      ],
      "diagrams": [],
      "sourceSha256": "74ad70eebe2346930f822301119417c0b72885f60c1e2203f0b1ed9ff199e274"
    },
    {
      "id": "adr-0013-native-cells",
      "path": "docs/adr/0013-native-cells-own-working-copy.md",
      "title": "ADR-0013: Cells run natively, each in its own git working copy",
      "type": "adr",
      "status": "draft",
      "owner": "@timianmalloo",
      "phase": "all phases",
      "reviewBy": "2027-09-23",
      "reviewSuggested": [],
      "summary": "Owner ruling: isolation beyond a working copy is not required. Each authored-task cell is a native process on the operator's Windows workstation, working in its own git working copy, with its own harness home and a symmetric unsandboxed permission profile. A Windows Job Object is how the engine stops a cell and knows it has stopped, not a sandbox. Containers, the egress proxy and every other isolation control are dropped. Amendment 1 (2026-09-28): public tasks run natively too; no cell uses Docker.",
      "tags": [
        "benchmark",
        "runner",
        "validity",
        "owner-ruling"
      ],
      "links": [
        {
          "to": "arch-harness-bench",
          "rel": "refines"
        },
        {
          "to": "adr-0001-cell-containers",
          "rel": "supersedes"
        },
        {
          "to": "adr-0012-proportionate-security",
          "rel": "depends-on"
        },
        {
          "to": "note-spike-isolation-permissions",
          "rel": "depends-on"
        },
        {
          "to": "spec-harness-bench",
          "rel": "refines"
        }
      ],
      "diagrams": [],
      "sourceSha256": "f205dce9e911100fac9262c27a178741e428e0f75a2afa59deb2577dea574670"
    },
    {
      "id": "adr-0014-arm-and-cell-grain",
      "path": "docs/adr/0014-arm-replaces-pack-setting.md",
      "title": "ADR-0014: An arm replaces the pack setting; one cell is one (task version, combo, arm, repetition)",
      "type": "adr",
      "status": "draft",
      "owner": "@timianmalloo",
      "phase": "Enterprise evaluation E1 (two arms), E3 (three arms)",
      "reviewBy": "2027-10-03",
      "reviewSuggested": [],
      "summary": "A plan carries one pack revision per pack-on arm (zero for pack-off), and a cell is one (task version, combo, arm, repetition). The cell_id recipe and its key name stay byte-identical, with the arm id in the `pack` ingredient and `on`/`off` as the legacy arm ids, so grids 1-4 load, report and verify unchanged and a grid-4 re-plan gives the same cells. New plans launch in a seeded blocked-randomised order and name their comparison pairs; the board and pack section read a comparison pair instead of the literals on/off.",
      "tags": [
        "benchmark",
        "data-model",
        "grain",
        "plan",
        "arm",
        "migration"
      ],
      "links": [
        {
          "to": "arch-evaluation-campaign",
          "rel": "refines"
        },
        {
          "to": "spec-enterprise-evaluation",
          "rel": "implements"
        },
        {
          "to": "adr-0006-results-data-model",
          "rel": "refines"
        }
      ],
      "diagrams": [],
      "sourceSha256": "60f80f38dfbe16a241f46a734b3aa3f6d6ebbae3d8fe5473d03ac4558afaadb4"
    },
    {
      "id": "adr-0015-multi-turn-attempt-and-turn-snapshots",
      "path": "docs/adr/0015-multi-turn-attempt-and-turn-snapshots.md",
      "title": "ADR-0015: A cell attempt may hold a second user turn; each non-final turn leaves an append-only snapshot",
      "type": "adr",
      "status": "draft",
      "owner": "@timianmalloo",
      "phase": "Enterprise evaluation E2 (spike E4 passed on Windows)",
      "reviewBy": "2027-10-03",
      "reviewSuggested": [],
      "summary": "A multi-turn task's cell sends turn 2 as a second session/prompt on the same ACP session and the same stdin channel, after turn 1 returns end_turn and after the working copy is archived as a turn snapshot. Spike E4 verified this on all three harnesses on Windows (macOS unverified). The Cell keeps one prompted attempt; prompt_sent and the snapshot carry a turn index; prompt-once becomes once per (cell, turn); archive_files gains a snapshot key part whose absence reads 'final'. The driver, engine and archiver need named changes.",
      "tags": [
        "benchmark",
        "run-engine",
        "archive",
        "grain",
        "multi-turn",
        "lifecycle"
      ],
      "links": [
        {
          "to": "arch-evaluation-campaign",
          "rel": "refines"
        },
        {
          "to": "spec-enterprise-evaluation",
          "rel": "implements"
        },
        {
          "to": "adr-0006-results-data-model",
          "rel": "refines"
        },
        {
          "to": "adr-0007-run-engine",
          "rel": "refines"
        },
        {
          "to": "adr-0013-native-cells",
          "rel": "refines"
        },
        {
          "to": "note-20261003-spike-e4-post-turn-prompt",
          "rel": "depends-on"
        }
      ],
      "diagrams": [],
      "sourceSha256": "afbabb83002015f41c7645a7ecdda095412a38b8a6e5de62de8e44557655f951"
    },
    {
      "id": "adr-0016-campaign-record",
      "path": "docs/adr/0016-campaign-record.md",
      "title": "ADR-0016: The Evaluation Campaign is a committed, hash-chained ledger over unchanged runs, with content-addressed records",
      "type": "adr",
      "status": "draft",
      "owner": "@timianmalloo",
      "phase": "Enterprise evaluation E1 onward",
      "reviewBy": "2027-10-03",
      "reviewSuggested": [],
      "summary": "The Evaluation Campaign context keeps one append-only, hash-chained ledger per campaign under bench/campaigns/<id>/ (committed, single writer `bench campaign`), plus immutable content-addressed files for engine identities, pre-registrations and power-analysis inputs. Discrimination records are create-only files keyed by (task version, engine identity, platform), produced by synthetic cells through the engine. Rings are committed matrix templates identified by content hash. The campaign references runs by id and never copies their facts; eligibility, gate results, power outputs and verdicts are derived.",
      "tags": [
        "benchmark",
        "data-model",
        "grain",
        "campaign",
        "discrimination",
        "ring",
        "persistence"
      ],
      "links": [
        {
          "to": "arch-evaluation-campaign",
          "rel": "refines"
        },
        {
          "to": "spec-enterprise-evaluation",
          "rel": "implements"
        },
        {
          "to": "adr-0006-results-data-model",
          "rel": "depends-on"
        }
      ],
      "diagrams": [],
      "sourceSha256": "8eee493ff9b2b2363be00f20281732ab9e5486e00a2a61e9cd59df1e3fe98da0"
    },
    {
      "id": "adr-0017-engine-identity-and-freeze",
      "path": "docs/adr/0017-engine-identity-and-freeze.md",
      "title": "ADR-0017: Engine identity is a per-component content manifest; the freeze admits only recorded defect fixes",
      "type": "adr",
      "status": "draft",
      "owner": "@timianmalloo",
      "phase": "Enterprise evaluation E1 onward",
      "reviewBy": "2027-10-03",
      "reviewSuggested": [],
      "summary": "A campaign's engine baseline is a manifest of content hashes per engine component (each source module, the catalog hash, BOM, prices, profiles, harness builds, uv.lock, the campaign's task versions, platform and Python version), not a git commit, so unrelated commits do not break a freeze and a difference is named per item. A recorded defect fix replaces named component hashes under a defect class, in a before-hash chain. Eligibility is derived; a run-side fix after cells ran makes those runs ineligible and they are re-run (operator decision 2026-10-03); the run-side identity is also rechecked before every cell launch.",
      "tags": [
        "benchmark",
        "reproducibility",
        "freeze",
        "eligibility",
        "campaign"
      ],
      "links": [
        {
          "to": "arch-evaluation-campaign",
          "rel": "refines"
        },
        {
          "to": "spec-enterprise-evaluation",
          "rel": "implements"
        },
        {
          "to": "adr-0016-campaign-record",
          "rel": "depends-on"
        }
      ],
      "diagrams": [],
      "sourceSha256": "f31526502ab5ba0794656bd4da87ed0bf827e936e35bdbfccf6df9bf0c8a98a9"
    },
    {
      "id": "adr-0018-hidden-check-harness",
      "path": "docs/adr/0018-hidden-check-harness.md",
      "title": "ADR-0018: Property hidden checks run in the grading copy's Job Object, loopback-only, with a schema-bound result on their own pipe",
      "type": "adr",
      "status": "draft",
      "owner": "@timianmalloo",
      "phase": "Enterprise evaluation E1 (in-process probes), E4 (loopback fault fakes)",
      "reviewBy": "2027-10-03",
      "reviewSuggested": [],
      "summary": "One generic property grader runs a task's hidden check (attack probes, fault fakes, diff statistics) inside a grading copy under cells_root, in its own Job Object with per-case and outer bounds. Probes prefer in-process calls; a listener binds the literal 127.0.0.1 on an OS-assigned port. The check's result comes back only on its own stdout pipe in a closed schema, the check tree is hashed before and after, planted secrets are synthetic canaries with a scanner-named shape, and seeds derive from (task version, cell, metric) so a re-grade reproduces exactly. Boundary B7.",
      "tags": [
        "benchmark",
        "grading",
        "security",
        "trust-boundary",
        "resilience",
        "hidden-check"
      ],
      "links": [
        {
          "to": "arch-evaluation-campaign",
          "rel": "refines"
        },
        {
          "to": "spec-enterprise-evaluation",
          "rel": "implements"
        },
        {
          "to": "adr-0010-untrusted-cell-output",
          "rel": "refines"
        },
        {
          "to": "adr-0012-proportionate-security",
          "rel": "depends-on"
        },
        {
          "to": "adr-0013-native-cells",
          "rel": "depends-on"
        }
      ],
      "diagrams": [],
      "sourceSha256": "95e15d30221b96ef5928528fe2c1dd39ac9af7c0b3b93cd0c28bb174c7df876a"
    },
    {
      "id": "adr-0019-catalog-0-7-property-metrics",
      "path": "docs/adr/0019-catalog-0-7-property-metrics.md",
      "title": "ADR-0019: Catalog 0.7 adds the property metrics, scenario-7 pass@1 and per-metric expected values; a missing pass@1 is never a fail",
      "type": "adr",
      "status": "draft",
      "owner": "@timianmalloo",
      "phase": "Enterprise evaluation E1 (0.7.dev), E3 (0.7 frozen)",
      "reviewBy": "2027-10-03",
      "reviewSuggested": [],
      "summary": "Catalog 0.7 is a new version under the R-59/R-86 rules: it adds property_check_pass and the EV-2..EV-6 secondaries, a pass_at_1 for scenario-7 (formal) tasks, and expected-value declarations per metric in each property task's task.yaml. The pack section's rule that counts a missing pass_at_1 as a fail is a defect and is fixed: missing is NOT_RECORDED and excluded. The US-4 control is the catalog-freeze golden for every 0.6 metric.",
      "tags": [
        "benchmark",
        "catalog",
        "metrics",
        "grading",
        "us-4"
      ],
      "links": [
        {
          "to": "arch-evaluation-campaign",
          "rel": "refines"
        },
        {
          "to": "spec-enterprise-evaluation",
          "rel": "implements"
        },
        {
          "to": "design-pack-improvement-section",
          "rel": "relates-to"
        }
      ],
      "diagrams": [],
      "sourceSha256": "80559667245cbe4eddbed9f889418a73d9c12d30d393916cfbe06b24f4c08944"
    },
    {
      "id": "adr-0020-power-and-verdicts-stdlib",
      "path": "docs/adr/0020-power-and-verdicts-stdlib.md",
      "title": "ADR-0020: Power analysis, verdicts, dominance and ring gates are pure stdlib functions checked against reference cases",
      "type": "adr",
      "status": "draft",
      "owner": "@timianmalloo",
      "phase": "Enterprise evaluation E1 onward",
      "reviewBy": "2027-10-03",
      "reviewSuggested": [],
      "summary": "The power analysis (two-proportion and Connor paired-binary sizes, MDE solved back), the per-property verdict rule with task-stratified bootstrap intervals, the token-ratio dominance rule and the per-tag ring gates are pure Python-stdlib functions of recorded inputs and a seed. No statistics dependency is added: statistics.NormalDist reproduces the spec's reference sizes (93, 53, 115) in this session. Outputs are derived views; tests check closed-form references, an independent hand-coded formula, a seeded-wrong variant and seeded coverage simulations.",
      "tags": [
        "benchmark",
        "statistics",
        "power-analysis",
        "verdict",
        "ring",
        "derived-view"
      ],
      "links": [
        {
          "to": "arch-evaluation-campaign",
          "rel": "refines"
        },
        {
          "to": "spec-enterprise-evaluation",
          "rel": "implements"
        },
        {
          "to": "adr-0006-results-data-model",
          "rel": "depends-on"
        }
      ],
      "diagrams": [],
      "sourceSha256": "5f94c6e9e7cc5bf5cb9a949c517cb1034d64747a7afa7182313697940a67aa7d"
    },
    {
      "id": "adr-0021-plan-level-resume-and-liveness",
      "path": "docs/adr/0021-plan-level-resume-and-liveness.md",
      "title": "ADR-0021: Plan-level resume of a run, with per-turn reconciliation and a progress signal an alarm can watch",
      "type": "adr",
      "status": "draft",
      "owner": "@timianmalloo",
      "phase": "Enterprise evaluation E3 (needed by E5's multi-night grid)",
      "reviewBy": "2027-10-03",
      "reviewSuggested": [],
      "summary": "A restarted `bench run` for an existing run id resumes it: it verifies the ledger, proves each cell terminal from its recorded outcome event, reconciles every non-terminal cell by ADR-0007's rules extended per turn (ADR-0015), relaunches only never-prompted cells in the frozen plan order, and grades once every cell is terminal. It refuses a resume under a drifted run-side identity; a resume of a stopped run finishes the stop and launches nothing (Amendment 1, R-100). `bench status` exposes last_progress_at, and `bench status --alarm-after` gives a scheduled check a non-zero exit when progress stalls. A per-launch disk check and a stated worst-case cell and grading time complete the multi-night story.",
      "tags": [
        "benchmark",
        "run-engine",
        "resume",
        "liveness",
        "sre",
        "multi-night"
      ],
      "links": [
        {
          "to": "arch-evaluation-campaign",
          "rel": "refines"
        },
        {
          "to": "spec-enterprise-evaluation",
          "rel": "implements"
        },
        {
          "to": "adr-0007-run-engine",
          "rel": "refines"
        },
        {
          "to": "adr-0015-multi-turn-attempt-and-turn-snapshots",
          "rel": "depends-on"
        },
        {
          "to": "adr-0017-engine-identity-and-freeze",
          "rel": "depends-on"
        }
      ],
      "diagrams": [],
      "sourceSha256": "f06b88f66be36e7963c5792c5332d51e90a468390f05f35ab74f767ddc98d0dc"
    },
    {
      "id": "arch-evaluation-campaign",
      "path": "docs/architecture-evaluation-campaign.md",
      "title": "Architecture amendment: the Evaluation Campaign (arms, multi-turn cells, campaigns, hidden checks)",
      "type": "architecture",
      "status": "draft",
      "owner": "@timianmalloo",
      "phase": "Enterprise evaluation: phases E1-E5 (walking skeleton first)",
      "reviewBy": "2027-04-01",
      "reviewSuggested": [],
      "summary": "An amendment to the harness-bench architecture for the enterprise-evaluation spec. A run's plan carries one pack revision per pack-on arm and a cell is one (task version, combo, arm, repetition), with the old cell_id recipe kept so grids 1-4 load unchanged; a cell attempt may hold a second user turn with an append-only turn snapshot; a new Evaluation Campaign context keeps a committed, hash-chained campaign ledger, a per-component engine-identity manifest, create-only discrimination records and ring templates; property hidden checks run in the grading copy's Job Object on loopback only; power analysis and verdicts are pure stdlib functions checked against reference cases; a run resumes at plan level across nights (ADR-0021), and archive and create-only writes are crash-atomic. Everything stays T0 and native (Windows today). Revised after architect council round 1.",
      "tags": [
        "benchmark",
        "architecture",
        "campaign",
        "arm",
        "turn-snapshot",
        "hidden-check",
        "power-analysis",
        "verdict"
      ],
      "links": [
        {
          "to": "arch-harness-bench",
          "rel": "refines"
        },
        {
          "to": "spec-enterprise-evaluation",
          "rel": "implements"
        },
        {
          "to": "adr-0014-arm-and-cell-grain",
          "rel": "depends-on"
        },
        {
          "to": "adr-0015-multi-turn-attempt-and-turn-snapshots",
          "rel": "depends-on"
        },
        {
          "to": "adr-0016-campaign-record",
          "rel": "depends-on"
        },
        {
          "to": "adr-0017-engine-identity-and-freeze",
          "rel": "depends-on"
        },
        {
          "to": "adr-0018-hidden-check-harness",
          "rel": "depends-on"
        },
        {
          "to": "adr-0019-catalog-0-7-property-metrics",
          "rel": "depends-on"
        },
        {
          "to": "adr-0020-power-and-verdicts-stdlib",
          "rel": "depends-on"
        },
        {
          "to": "adr-0021-plan-level-resume-and-liveness",
          "rel": "depends-on"
        }
      ],
      "diagrams": [
        {
          "kind": "flowchart",
          "title": "Component map & boundaries",
          "mermaid": "flowchart TB\n  subgraph Session[\"Coordinator session (/start-benchmark, campaign steps)\"]\n    SK[start-benchmark skill: compile, confirm, relay]\n  end\n  subgraph Camp[\"Evaluation Campaign (new, T0)\"]\n    CC[bench campaign: create, baseline, fix, power, register, attach, conclude]\n    EI[Engine identity: manifest + diff]\n    PW[Power analysis: stdlib, by input hash]\n    DSC[Discriminate: synthetic cells through the engine]\n    RG[Ring gates: pure functions per tag]\n  end\n  subgraph Host[\"bench (existing pipeline, amended)\"]\n    PLN[Plan: arms, blocked randomised order, rings]\n    ENG[Run engine: multi-turn attempt]\n    DRV[ACP driver: turn n prompt]\n    ARC[Archiver: turn snapshots]\n    GRD[Grade orchestrator]\n    HC[Property grader: hidden-check runner]\n    VIEWS[Views]\n    VER[Verdicts + eligibility: derived]\n    REP[Report: section 3]\n  end\n  subgraph Store[\"Records\"]\n    CL[(bench/campaigns/<id>: ledger, identities, power inputs, preregs)]\n    DR[(bench/discrimination)]\n    RT[(bench/rings)]\n    RUN[(runs/<run_id>: ADR-0006 facts + archives with snapshots)]\n  end\n  subgraph GC[\"Grading copy under cells_root (one Job Object, deadline)\"]\n    CHK[Hidden check: probes / fault fake on 127.0.0.1]\n    DEL[Agent deliverable]\n  end\n  SK --> CC & PLN\n  CC --> EI & PW & DSC & RG\n  CC --> CL\n  DSC --> PLN\n  DSC --> DR\n  RT --> PLN\n  PLN --> ENG --> DRV\n  ENG --> ARC --> RUN\n  GRD --> HC --> CHK --> DEL\n  HC --> RUN\n  RUN --> VIEWS --> VER --> REP\n  CL --> VER\n  RUN --> RG\n  RUN --> PW"
        },
        {
          "kind": "flowchart",
          "title": "Delivery phasing (vertical slices)",
          "mermaid": "flowchart LR\n  E1[E1 walking skeleton] --> E2[E2 multi-turn]\n  E1 --> E3[E3 three arms, rings, resume]\n  E1 --> E4[E4 remaining checks]\n  SLB[spike S-LB] --> E4\n  E2 --> J{converge: ADR-0021 §4 table + TLC}\n  E3 --> J\n  E4 --> J\n  J --> E5[E5 first campaign]"
        }
      ],
      "sourceSha256": "a96c1e13df2e84d970d8a6f5708c878907047e21d83763576d0c31441f09d38a"
    },
    {
      "id": "arch-harness-bench",
      "path": "docs/architecture.md",
      "title": "Architecture: harness-bench",
      "type": "architecture",
      "status": "draft",
      "owner": "@timianmalloo",
      "phase": "S-02 architecture of record (smoke milestone first)",
      "reviewBy": "2027-03-22",
      "reviewSuggested": [],
      "summary": "A deterministic pipeline (plan, run, grade, report) whose single-writer run engine launches every measured cell natively on Windows, in its own git working copy and Windows Job Object, through a bench-owned ACP driver, with a pinned per-cell harness profile and a static, symmetric permission profile; grading runs natively in its own working copies (ADR-0013). Hash-chained append-only ledgers per run are the record; every result is a derived view. Models appear only as the systems under test and, tool-less, as judges, summarizer and matcher.",
      "tags": [
        "benchmark",
        "architecture",
        "runner",
        "grading"
      ],
      "links": [
        {
          "to": "spec-harness-bench",
          "rel": "implements"
        },
        {
          "to": "proposal-cross-harness-benchmarking",
          "rel": "refines"
        },
        {
          "to": "note-spike-runner-path",
          "rel": "depends-on"
        },
        {
          "to": "note-spike-isolation-permissions",
          "rel": "depends-on"
        }
      ],
      "diagrams": [
        {
          "kind": "flowchart",
          "title": "Component map & boundaries",
          "mermaid": "flowchart TB\n  subgraph Session[\"Coordinator session (Claude Code, /start-benchmark)\"]\n    SK[start-benchmark skill: compile, confirm, relay, audit-log entries]\n  end\n  subgraph Host[\"bench (Python, T0) on the Windows host\"]\n    CLI[bench CLI: validate, plan, run, status, stop, grade, report, verify, teardown]\n    ENG[Run engine: single writer, lifecycle = run_lifecycle.tla]\n    WSB[Workspace builder]\n    TLS[Tools folder: pinned harness builds]\n    PRF[(Harness profiles: build, mode, pin, home seeding, reader)]\n    DRV[ACP cell driver]\n    ARC[Archiver: no link following, exact-value credential scan]\n    TEL[Telemetry: readers + normaliser]\n    GRD[Grade orchestrator]\n    GW[Model gateway: tool-less]\n    EG[Egress gate]\n    VIEWS[Pure-Python projections]\n    REP[Report: CLI + HTML + summaries]\n  end\n  subgraph Store[\"runs/<run_id>/ + cache/\"]\n    LED[(hash-chained facts: events, model_calls, tool_calls, archive_files, scores, verdict_uses)]\n    ARCH[(cell archives)]\n    CTL[(control/: stop, decision answers)]\n    VC[(shared verdict cache)]\n  end\n  subgraph Cells[\"bench-cells/<run>/<cell> (native, one Job Object each)\"]\n    CELL[Cell: own working copy + own harness home]\n    GC[Grading working copy: archive + hidden tests]\n  end\n  SK -->|bench plan / run / status --json| CLI\n  SK -->|decision answers| CTL\n  CLI --> ENG\n  ENG --> WSB & DRV & ARC\n  PRF --> TLS & DRV & TEL\n  DRV -->|spawn into Job Object, ACP stdio| CELL\n  CTL --> ENG\n  ENG --> LED\n  ARC --> ARCH\n  ARCH --> TEL --> LED\n  ARCH --> GRD --> GC\n  GRD --> LED\n  GRD --> GW\n  GW --> VC\n  GW --> EG\n  LED --> VIEWS --> REP\n  REP --> GW\n  REP --> EG"
        }
      ],
      "sourceSha256": "5f0ef36e8cc9165d0f471d371ed98aa8973c0d80ea0714b9bdd9f13ea9da3065"
    },
    {
      "id": "mutation-record-phase1",
      "path": "docs/notes/mutation-record-phase1.md",
      "title": "Mutation record: phase 1 (compiled)",
      "type": "decision-note",
      "status": "accepted",
      "owner": "@timianmalloo",
      "phase": "Phase 1 · walking skeleton",
      "reviewBy": "2026-12-22",
      "reviewSuggested": [],
      "summary": "Phase 1's mutation evidence in one place. Every cosmic-ray mutant of lifecycle, errors, engine, ledger, views and grade/** (2699) was run, then re-run with bytecode off (T12): 0 open. The re-run closed 29 kills the records had overstated. Every hand-written tests/mutations/*.json entry (198) is killed under the fixed named-test checker.",
      "tags": [
        "mutation",
        "cosmic-ray",
        "phase1",
        "proof"
      ],
      "links": [
        {
          "to": "mutation-record-t1",
          "rel": "relates-to"
        },
        {
          "to": "mutation-record-t2",
          "rel": "relates-to"
        },
        {
          "to": "coordination-phase1-finish",
          "rel": "relates-to"
        }
      ],
      "diagrams": [],
      "sourceSha256": "c113b0e000ece4868159592d0e5e50eb67d6bb5b46d20ca62b843e999012808a"
    },
    {
      "id": "mutation-record-t1",
      "path": "docs/notes/mutation-record-t1.md",
      "title": "Mutation record: T1 (engine, errors, lifecycle)",
      "type": "decision-note",
      "status": "accepted",
      "owner": "@timianmalloo",
      "phase": "Phase 1 · walking skeleton",
      "reviewBy": "2026-12-22",
      "reviewSuggested": [],
      "summary": "cosmic-ray 8.7.0, run natively on Windows (mutmut refuses native Windows, probe R13), over lifecycle, errors and every engine.py mutant: T1 ran 299 (301 at T10's count) and track T10 ran the remaining 466. Every mutant is killed or argued equivalent; none is open, none timed out, none was not exercised on the platform. T10 found and fixed one design drift (the kill-retry cap).",
      "tags": [
        "mutation",
        "cosmic-ray",
        "engine",
        "lifecycle",
        "errors",
        "T1"
      ],
      "links": [
        {
          "to": "coordination-phase1-finish",
          "rel": "relates-to"
        },
        {
          "to": "findings-t1-engine-hardening",
          "rel": "relates-to"
        }
      ],
      "diagrams": [],
      "sourceSha256": "8b85b7221b79bec551a0fc3c8a1ffdba03e1c7770d98fc2f16176a5b8971c585"
    },
    {
      "id": "mutation-record-t2",
      "path": "docs/notes/mutation-record-t2.md",
      "title": "Mutation record - track T2 (ledger, views, grade)",
      "type": "decision-note",
      "status": "proposed",
      "owner": "@timianmalloo",
      "phase": "Phase 1 · walking skeleton",
      "reviewBy": "2026-12-22",
      "reviewSuggested": [],
      "summary": "cosmic-ray 8.7.0 over ledger.py, views.py and grade/**, run natively on Windows at the track's final src: 1803 mutants, 1546 killed, 257 survived, 0 timeout, 0 incompetent, 0 not-exercised-on-platform. Every survivor is an equivalent mutant with its diff and a one-line argument: 225 inside type annotations, 32 argued one by one.",
      "tags": [
        "mutation",
        "cosmic-ray",
        "T2",
        "ledger",
        "views",
        "grade"
      ],
      "links": [
        {
          "to": "coordination-phase1-finish",
          "rel": "relates-to"
        }
      ],
      "diagrams": [],
      "sourceSha256": "87b462c6b4079b228aef2002e899ba13843cc082b191992f740ac934699ab352"
    },
    {
      "id": "note-20260923-a6-start-benchmark",
      "path": "docs/notes/a6-start-benchmark-golden-cases.md",
      "title": "A6 golden cases: the start-benchmark skill, old against new",
      "type": "decision-note",
      "status": "accepted",
      "owner": "@timianmalloo",
      "phase": "Phase 1 · walking skeleton",
      "reviewBy": "2027-03-22",
      "reviewSuggested": [],
      "summary": "The design gates the start-benchmark skill edit with golden cases run on the old and the new skill (test plan T14, A6). Five cases, run with the same model (sonnet) as a dry run: the new skill passes all five; the old passes one. The compiled matrices are checked by tools/a6_check_matrix.py against the real validator.",
      "tags": [
        "decision-note",
        "skills",
        "a6",
        "evaluation"
      ],
      "links": [
        {
          "to": "design-phase1-walking-skeleton",
          "rel": "relates-to"
        }
      ],
      "diagrams": [],
      "sourceSha256": "8d383befdccfbef3b7c7cf89a59a870450abdb47be5cd46e8518339f555f0092"
    },
    {
      "id": "note-20260923-sqlite-views",
      "path": "docs/notes/decision-sqlite-views.md",
      "title": "Results views are pure-Python projections, with no SQL engine, until a measured trigger",
      "type": "decision-note",
      "status": "draft",
      "owner": "@timianmalloo",
      "phase": "Phase 1 · walking skeleton",
      "reviewBy": "2027-03-22",
      "reviewSuggested": [
        {
          "by": "adr-0006-results-data-model",
          "on": "2026-09-24",
          "reason": "Amendment 1: model_calls grain re-declared per native usage report with requests and model in the key; tool_calls.outcome_code (R-26, R-27)"
        }
      ],
      "summary": "The derived results views (ADR-0006) are pure-Python functions over the verified fact dataclasses; no SQL engine (DuckDB or sqlite3) is used. Blast radius: views.py only; the facts on disk are unchanged.",
      "tags": [
        "decision-note",
        "data-model",
        "dependencies"
      ],
      "links": [
        {
          "to": "adr-0006-results-data-model",
          "rel": "relates-to"
        },
        {
          "to": "design-phase1-walking-skeleton",
          "rel": "relates-to"
        }
      ],
      "diagrams": [],
      "sourceSha256": "18cc58d385da432e2f2bee6a95d654c91b7ad717750e5ae538b636fc3a83f514"
    },
    {
      "id": "note-20260923-token-source",
      "path": "docs/notes/decision-token-source-per-harness.md",
      "title": "Token totals come from the source that is complete for each harness",
      "type": "decision-note",
      "status": "draft",
      "owner": "@timianmalloo",
      "phase": "Phase 1 · walking skeleton",
      "reviewBy": "2027-03-22",
      "reviewSuggested": [],
      "summary": "Measured 2026-09-23 with the pinned builds: Claude Code 2.1.274's native record under the ACP adapter omits the turn's final API call and its auxiliary title call, while the adapter's prompt response carries complete per-model turn usage; for Codex the native record is complete and the adapter reports only the last call. Each profile names its authoritative source; the other is a cross-check.",
      "tags": [
        "decision-note",
        "telemetry",
        "validity"
      ],
      "links": [
        {
          "to": "adr-0008-telemetry",
          "rel": "refines"
        },
        {
          "to": "design-phase1-walking-skeleton",
          "rel": "relates-to"
        }
      ],
      "diagrams": [],
      "sourceSha256": "ae8bad06929fef9c35c9441ae785431384dba3da6c77c4d9e1b9e8c594ed79c8"
    },
    {
      "id": "note-20260924-spike-a9-host-sleep",
      "path": "docs/notes/spike-a9-host-sleep.md",
      "title": "Spike A9 - the engine and Windows clocks across a real host suspend",
      "type": "decision-note",
      "status": "accepted",
      "owner": "@timianmalloo",
      "phase": "",
      "reviewBy": "2026-12-24",
      "reviewSuggested": [],
      "summary": "Measured on the operator's Windows 11 host (Modern Standby, about 236 s): the engine's SleepDetector detects a real suspend and ends the live cell as host_suspended (HB-CELL-106); time.monotonic counts sleep time, QueryUnbiasedInterruptTime does not; a standby shorter than suspend_gap is not detected and inflates turn_ms.",
      "tags": [
        "spike",
        "host",
        "clock",
        "sleep",
        "risk-A9"
      ],
      "links": [
        {
          "to": "coordination-finish-harness-bench",
          "rel": "relates-to"
        }
      ],
      "diagrams": [],
      "sourceSha256": "5574be99122a6888e8c4d6dd9612b656694b134410c4d15df881419d330cbf8e"
    },
    {
      "id": "note-20260925-spike-gr-code-trx",
      "path": "docs/notes/spike-gr-code-trx.md",
      "title": "Spike GR-CODE c1 - what D1's per-test TRX and the dotnet build summary contain, measured with the pinned SDK",
      "type": "decision-note",
      "status": "accepted",
      "owner": "@timianmalloo",
      "phase": "",
      "reviewBy": "2026-12-25",
      "reviewSuggested": [],
      "summary": "Measured on this host with dotnet 10.0.303: D1's hidden-test step writes one TRX whose ResultSummary/Counters and per-test UnitTestResult rows are documented here; with -v:q neither dotnet test nor dotnet build prints a build summary, only MSBuild canonical error lines (CSxxxx for a compile error, NUxxxx for a restore error) and no TRX. A ProjectReference to a missing project is only warning MSB9008 and exits 0, so the design's broken-reference seed does not score 0 under its own definition (flagged).",
      "tags": [
        "spike",
        "grading",
        "dotnet",
        "trx",
        "correctness",
        "dr-g4"
      ],
      "links": [
        {
          "to": "design-phase3-graders",
          "rel": "relates-to"
        },
        {
          "to": "rulings-register",
          "rel": "depends-on"
        }
      ],
      "diagrams": [],
      "sourceSha256": "336b5b273dd9fbfb8df380c6096761cb31081537922c9e52315dbf0d5a694e71"
    },
    {
      "id": "note-20260925-stop-decision-calls",
      "path": "docs/notes/stop-decision-calls.md",
      "title": "Row 10 design calls: decision triggers, the spend-cap unit, and defaultMode",
      "type": "decision-note",
      "status": "draft",
      "owner": "@timianmalloo",
      "phase": "Phase 2 · smoke on all harnesses (wave 2: row 10, W2-STOP)",
      "reviewBy": "2026-12-24",
      "reviewSuggested": [],
      "summary": "Three calls made while designing row 10 (W2-STOP-D): which cell causes raise a \"blocked cell\" or a \"qualification gap\" decision; that the spend cap counts tokens until the Owner rules DR-1; and that the Claude Code profile declares defaultMode \"default\" (R-34 condition 4). They shape the engine's triggers, the plan parameters and one profile line.",
      "tags": [
        "decision-note",
        "stop",
        "decisions",
        "spend-cap",
        "permissions"
      ],
      "links": [
        {
          "to": "design-phase2-stop-decisions",
          "rel": "relates-to"
        },
        {
          "to": "spec-harness-bench",
          "rel": "relates-to"
        },
        {
          "to": "rulings-register",
          "rel": "relates-to"
        }
      ],
      "diagrams": [],
      "sourceSha256": "a103726bb5135533cce4b4d88bf681913174e64ef089bf55dc558ea0f8c15434"
    },
    {
      "id": "note-20260927-ci-opt-proposal",
      "path": "docs/notes/ci-opt-proposal.md",
      "title": "CI-OPT: Proposal to separate one-time proofs from continuous checks and reduce grader test cost",
      "type": "decision-note",
      "status": "proposed",
      "owner": "@timianmalloo",
      "phase": "CI Optimization",
      "reviewBy": "2027-03-27",
      "reviewSuggested": [],
      "summary": "CI-OPT slice 2 measured analysis and optimization proposal: separates one-time proofs from continuous checks, profiles where slow grader tests spend time (identifying file hashing and redundant archive digests as the dominant 70%+ bottleneck), analyzes mutation redundancy (identifying 693 unreferenced ceremony tests and 106 duplicate killer groups), and presents a ranked remediation roadmap saving ~84 minutes in the slow ring and ~9-11 minutes in the default ring (cutting CI spend in half) with zero loss of coverage.",
      "tags": [
        "decision-note",
        "testing",
        "ci-opt",
        "test-efficiency"
      ],
      "links": [
        {
          "to": "coordination-finish-harness-bench-run",
          "rel": "relates-to"
        }
      ],
      "diagrams": [],
      "sourceSha256": "5ef416d018179c6637ba358a9fe1787d392f2211b744f725440b8b73b1e43c1d"
    },
    {
      "id": "note-20261003-deviation-coord-transport-grok-session-new",
      "path": "docs/notes/deviation-coord-transport-grok-session-new.md",
      "title": "Repo-local deviation - coord_transport accepts Grok watcher acks during session/new",
      "type": "decision-note",
      "status": "accepted",
      "owner": "@timianmalloo",
      "phase": "",
      "reviewBy": "2027-04-03",
      "reviewSuggested": [],
      "summary": "docs/ai-forward-pack/scripts/coord_transport.py is patched locally so Grok's own skills/workflows watcher acknowledgement is accepted while session/new is in flight. Upstream (ai-forward) needs the same hunk.",
      "tags": [
        "ai-forward-pack",
        "deviation",
        "grok",
        "acp",
        "transport"
      ],
      "links": [
        {
          "to": "note-20261003-spike-e1-job-alone",
          "rel": "relates-to"
        }
      ],
      "diagrams": [],
      "sourceSha256": "33a86b139ebe6a7a3a028f07e678b7b1ab264eda2fb5073361897fbea72f5bfc"
    },
    {
      "id": "note-20261003-spike-e1-handle-list",
      "path": "docs/notes/spike-e1-handle-list.md",
      "title": "Spike E1-S2 - the deliverable's explicit handle list on Windows (close_fds + redirected stdio) and the DuplicateHandle forgery",
      "type": "decision-note",
      "status": "accepted",
      "owner": "@timianmalloo",
      "phase": "",
      "reviewBy": "2027-04-03",
      "reviewSuggested": [],
      "summary": "CPython 3.14.6's subprocess already passes PROC_THREAD_ATTRIBUTE_HANDLE_LIST holding only the three stdio handles when close_fds=True and any stdio is redirected (subprocess.py:1498-1521), which is how procs.spawn creates the adapter today. Run on this host: a child created that way could not reach the parent's inheritable pipe by the passed handle value or by scanning handle values; the positive control (close_fds=False) could. A child that opened the parent with PROCESS_DUP_HANDLE and duplicated the pipe handle wrote a forged line into it, confirming the ADR-0018 section 10a threat.",
      "tags": [
        "spike",
        "windows",
        "handle-list",
        "adr-0018",
        "security",
        "b7"
      ],
      "links": [
        {
          "to": "adr-0018-hidden-check-harness",
          "rel": "relates-to"
        },
        {
          "to": "adr-0013-native-cells",
          "rel": "relates-to"
        },
        {
          "to": "arch-evaluation-campaign",
          "rel": "relates-to"
        }
      ],
      "diagrams": [],
      "sourceSha256": "22117af55e9dcfb486e19db51c74bdf68050295aaa3da6c5cec61e70d37785e8"
    },
    {
      "id": "note-20261003-spike-e1-job-alone",
      "path": "docs/notes/spike-e1-job-alone.md",
      "title": "Spike E1-S3 - reading the Job Object's process list to prove the hidden check is alone",
      "type": "decision-note",
      "status": "accepted",
      "owner": "@timianmalloo",
      "phase": "",
      "reviewBy": "2027-04-03",
      "reviewSuggested": [],
      "summary": "procs.Job.pids() (JobObjectBasicProcessIdList) and the same query with a NULL handle from inside the check both work, but \"the check is alone\" is only a sound test when the check and the deliverable are started with the base interpreter and DETACHED_PROCESS. Under the venv launcher the job holds the launcher, the interpreter and a third process, and the launcher puts the interpreter in a nested job, so the check's own view misses the deliverable. With DETACHED_PROCESS and the base interpreter, both views were exactly {check} before and after the deliverable and {check, deliverable} while it ran (3 of 3). An honest check's exit came only 4-8 ms after the grader saw its document, so the grader cannot rely on reader timing: the check waits for a one-byte acknowledgement before exiting.",
      "tags": [
        "spike",
        "windows",
        "job-object",
        "adr-0018",
        "security",
        "b7"
      ],
      "links": [
        {
          "to": "adr-0018-hidden-check-harness",
          "rel": "relates-to"
        },
        {
          "to": "note-spike-isolation-permissions",
          "rel": "refines"
        },
        {
          "to": "note-spike-phase1-probes",
          "rel": "relates-to"
        },
        {
          "to": "arch-evaluation-campaign",
          "rel": "relates-to"
        }
      ],
      "diagrams": [],
      "sourceSha256": "4727728811450075ffa2c0c6dac359e8f77c08962e48821b98fd23f561d4990f"
    },
    {
      "id": "note-20261003-spike-e1-ntfs-atomic-publish",
      "path": "docs/notes/spike-e1-ntfs-atomic-publish.md",
      "title": "Spike E1-S1 - os.link fail-if-exists, directory rename and fsync on NTFS (create_once, crash-atomic archive)",
      "type": "decision-note",
      "status": "accepted",
      "owner": "@timianmalloo",
      "phase": "",
      "reviewBy": "2027-04-03",
      "reviewSuggested": [],
      "summary": "On this host (Windows 11 Pro 10.0.26200, NTFS C:, CPython 3.14.6): os.link onto an existing name raises FileExistsError (winerror 183) and keeps the original bytes; os.rename of a directory onto any existing directory raises FileExistsError 183; a process killed mid-copy leaves only the temporary sibling and no final folder. os.fsync needs a writable file descriptor, and a directory cannot be opened for fsync at all (PermissionError), so ADR-0015 section 5a's \"fsync the folder\" is POSIX-only. Power-loss durability was not tested.",
      "tags": [
        "spike",
        "ntfs",
        "crash-atomic",
        "create-once",
        "archive",
        "adr-0015",
        "adr-0016"
      ],
      "links": [
        {
          "to": "adr-0016-campaign-record",
          "rel": "relates-to"
        },
        {
          "to": "adr-0015-multi-turn-attempt-and-turn-snapshots",
          "rel": "relates-to"
        },
        {
          "to": "arch-evaluation-campaign",
          "rel": "relates-to"
        }
      ],
      "diagrams": [],
      "sourceSha256": "b4a34721f11e7ea17b663b3c283ab3d213b285ba7f222b94ae6cba5475d23785"
    },
    {
      "id": "note-20261003-spike-e4-post-turn-prompt",
      "path": "docs/notes/spike-e4-post-turn-prompt.md",
      "title": "Spike E4 - a second session/prompt in the same ACP session after end_turn",
      "type": "decision-note",
      "status": "accepted",
      "owner": "@timianmalloo",
      "phase": "",
      "reviewBy": "2026-12-24",
      "reviewSuggested": [],
      "summary": "Verified on all three harnesses (Windows host; macOS unverified): the ACP session itself accepts a second session/prompt on the same sessionId after turn 1 ends with stopReason end_turn, with no second handshake and stdin never closed between turns. Turn 2 completed end_turn on claude-code (claude-opus-5-5), codex (gpt-6-sol) and copilot (gpt-6-sol), and each adapter's growing cachedReadTokens across the turn boundary shows turn 1's context carried into turn 2. The production engine does not do this today: driver.run_turn sends exactly one prompt and returns (src/harness_bench/driver.py:300), and engine.py's _attempt closes stdin immediately after it returns (src/harness_bench/engine.py:752), inside a finally that always runs (engine.py:728-732). Supporting DR-E4's two-turn rework task needs driver/engine changes, named below, not just a second RPC call.",
      "tags": [
        "spike",
        "acp",
        "multi-turn",
        "rework",
        "risk-R-E6",
        "DR-E4",
        "EV-4"
      ],
      "links": [
        {
          "to": "spec-enterprise-evaluation",
          "rel": "relates-to"
        }
      ],
      "diagrams": [],
      "sourceSha256": "07917835d700372f139f4dff998db93acf736dcede8f9ff54b35791b3507156c"
    },
    {
      "id": "note-20261003-spike-s-lb-loopback",
      "path": "docs/notes/spike-s-lb-loopback.md",
      "title": "Spike S-LB - does a loopback-only listener raise a Windows Defender Firewall prompt or rule?",
      "type": "decision-note",
      "status": "proposed",
      "owner": "@timianmalloo",
      "phase": "",
      "reviewBy": "2026-10-17",
      "reviewSuggested": [],
      "summary": "Method and operator procedure for spike S-LB. The script tools/spikes/s_lb_loopback.py was written and compiled but NOT run (no operator present; a bind could raise a firewall dialog nobody sees). Every result row is \"not run, operator required\". Until the table is filled and passes, ADR-0018 section 3 keeps its assume: and phase E1 admits in-process probes only.",
      "tags": [
        "spike",
        "windows",
        "firewall",
        "loopback",
        "adr-0018",
        "e4"
      ],
      "links": [
        {
          "to": "arch-evaluation-campaign",
          "rel": "relates-to"
        },
        {
          "to": "design-eval-seam-contracts",
          "rel": "relates-to"
        }
      ],
      "diagrams": [],
      "sourceSha256": "b745456c3c0f7262760a6f5b33191c3872bc86a63673f266267aa20c71bca760"
    },
    {
      "id": "note-20261003-spike-s2-bottle-cookie-reads",
      "path": "docs/notes/spike-s2-bottle-cookie-reads.md",
      "title": "S2 spike (stopped) - verified reads of bottle signed-cookie code",
      "type": "decision-note",
      "status": "accepted",
      "owner": "@timianmalloo",
      "phase": "",
      "reviewBy": "2026-10-17",
      "reviewSuggested": [],
      "summary": "Three verified line reads of bottle.py at the S2 pin (pickle-based signed cookies); the S2 spike was stopped and S2's probe class goes to the Owner for a redesign that never constructs deserialization payloads.",
      "tags": [
        "spike",
        "s2",
        "security",
        "bottle"
      ],
      "links": [
        {
          "to": "design-eval-security-tasks",
          "rel": "relates-to"
        }
      ],
      "diagrams": [],
      "sourceSha256": "5c36d4aa7ee258164ee2ed2921e92228b81c85584b18ff7d17eb6d3598d6a278"
    },
    {
      "id": "note-20261003-spike-s2-bottle-r99",
      "path": "docs/notes/spike-s2-bottle-r99.md",
      "title": "S2 spike (R-99 redesign) - probe set measured on bottle at the pin",
      "type": "decision-note",
      "status": "proposed",
      "owner": "@timianmalloo",
      "phase": "",
      "reviewBy": "2026-10-17",
      "reviewSuggested": [],
      "summary": "Measured spike for S2 under R-99, re-run after the RV-SEC and RV-TA conditions (C1-C5): five probe classes (SQL injection, path traversal, cross-team authz, secret non-disclosure, tamper-refusal) each discriminate a reference app from a single-defect naive on bottle cbd569c4, with no probe touching the signed-cookie deserialization path. Tamper now reaches the signature check; leak scans errors and logs; each probe has a positive control.",
      "tags": [
        "spike",
        "s2",
        "security",
        "bottle",
        "r99"
      ],
      "links": [
        {
          "to": "design-eval-security-tasks",
          "rel": "relates-to"
        },
        {
          "to": "note-20261003-spike-s2-bottle-cookie-reads",
          "rel": "relates-to"
        }
      ],
      "diagrams": [],
      "sourceSha256": "8861e94c8fb2f1b6e57c4c2f6cac5a1601fa2dea2a9af5addf7b3dfdee52f3b1"
    },
    {
      "id": "note-catalog-0.5-anchors",
      "path": "docs/notes/catalog-0.5-anchors.md",
      "title": "Catalog 0.5.dev normalisation anchors and weight corrections (R-78 condition 1, R-79)",
      "type": "decision-note",
      "status": "accepted",
      "owner": "@timianmalloo",
      "phase": "",
      "reviewBy": "2026-10-10",
      "reviewSuggested": [],
      "summary": "Catalog 0.5.dev normalisation anchors and R-78 weight corrections, approved with changes by the Owner seat in R-79. Lists all 49 anchored metrics with kind: score and weight > 0, their better direction, anchor [worst, best], source note, and observed values from runs/smoke-1 and runs/row15-d1-1.",
      "tags": [
        "catalog",
        "metrics",
        "normalisation",
        "anchors",
        "r-78",
        "r-79",
        "composites"
      ],
      "links": [
        {
          "to": "design-phase4-statistics",
          "rel": "implements"
        },
        {
          "to": "rulings-register",
          "rel": "relates-to"
        }
      ],
      "diagrams": [],
      "sourceSha256": "deb0fa795ed410044d2d792ddfe860eec136a3794973f5169a18beded5a2dfbc"
    },
    {
      "id": "note-d1-vendored-red-baseline",
      "path": "docs/notes/d1-vendored-red-baseline.md",
      "title": "D1 vendored red baseline - dotnet test fails the same 72 layout-bound tests on both runs' cells; the 69/74/75 Stryker counts are the Stryker session's",
      "type": "decision-note",
      "status": "accepted",
      "owner": "@timianmalloo",
      "phase": "",
      "reviewBy": "2026-10-10",
      "reviewSuggested": [],
      "summary": "R-77 condition 4. The vendored AiDe.Core.Tests suite, run with dotnet test in grading-copy-shaped copies of one row15-d1-1 cell and one smoke-1 cell, twice each, fails the same 72 tests in all four runs, every one of them a missing-repository-layout failure. The cells add no red test. The run-to-run difference in Stryker's initial_failing_tests (69, 74, 75) is not reproduced by dotnet test, so it belongs to Stryker's own test session.",
      "tags": [
        "grading",
        "dotnet",
        "stryker",
        "mutation",
        "r-75",
        "r-77"
      ],
      "links": [
        {
          "to": "design-phase3-graders",
          "rel": "relates-to"
        },
        {
          "to": "note-spike-gr-code-stryker",
          "rel": "relates-to"
        }
      ],
      "diagrams": [],
      "sourceSha256": "a20275fb1cb9f401401fef6e679e6b5299b834f4e3fd0ae4ca0a21dbe90f7fbf"
    },
    {
      "id": "note-spike-gr-code-stryker",
      "path": "docs/notes/spike-gr-code-stryker.md",
      "title": "Spike GR-CODE c6a - cached Stryker.NET 4.16.0 runs offline on D1; --version does not print the pin",
      "type": "decision-note",
      "status": "accepted",
      "owner": "@timianmalloo",
      "phase": "",
      "reviewBy": "2026-10-09",
      "reviewSuggested": [],
      "summary": "dotnet-stryker 4.16.0 is extracted in the offline NuGet cache and is not an installed tool. `dotnet exec` of that DLL, with NUGET_PACKAGES pointed at the cache and additional-timeout 5000, scored D1's reference file twice: killed 12, timeout 0, survived 2, no coverage 0, and the two mutation-report.json files were byte-identical. `--version` exits 1.",
      "tags": [
        "spike",
        "grading",
        "dotnet",
        "stryker",
        "mutation",
        "r-59"
      ],
      "links": [
        {
          "to": "design-phase3-graders",
          "rel": "relates-to"
        }
      ],
      "diagrams": [],
      "sourceSha256": "3d69ca1bc51b03548430e76e152891eb2c8f6b6a14eb8845602e7e6b53ccf664"
    },
    {
      "id": "note-tb2-native-survey",
      "path": "docs/notes/tb2-native-survey.md",
      "title": "TB2 native survey: all 89 Terminal-Bench 2.0 tasks at 2fd12b88, read for a native/apt/linux-only/git-state verdict (R-83 condition 1)",
      "type": "decision-note",
      "status": "accepted",
      "owner": "@timianmalloo",
      "phase": "",
      "reviewBy": "2027-03-29",
      "reviewSuggested": [
        {
          "by": "adr-0013-native-cells",
          "on": "2026-10-03",
          "reason": "Proposed amendment 2026-10-03 (ADR-0014/0015, arch-evaluation-campaign): cell grain by arm, per-turn prompt_sent, archive_files snapshot key part, job terminated after the last turn; council gate pending"
        }
      ],
      "summary": "R-83 condition 1. Every one of the 89 Terminal-Bench 2.0 task folders at commit 2fd12b88aafdd04a52c298e3940bcb189f9766d6 (2fd12b88) was read (task.toml, environment/Dockerfile, and, where the Dockerfile alone did not settle it, tests/test.sh and solution/solve.sh) and given one verdict: native (19), apt (63), linux-only (5) or git-state (2). No easy-band task is native, so E1 takes a shortfall task from the medium band (R-83's shortfall rule 1); E2 and E3 take native tasks from their own bands. No task was run and no task folder changed.",
      "tags": [
        "benchmark",
        "terminal-bench-2",
        "r-83",
        "adr-0013",
        "survey",
        "tb2"
      ],
      "links": [
        {
          "to": "rulings-register",
          "rel": "relates-to"
        },
        {
          "to": "adr-0013-native-cells",
          "rel": "relates-to"
        }
      ],
      "diagrams": [],
      "sourceSha256": "72ed5d34053444192765584120319de0c1eba48f9b94fed34d753553db056c18"
    },
    {
      "id": "review-w1-acp-codex",
      "path": "docs/notes/review-w1-acp-codex.md",
      "title": "W1-ACP cross-vendor join review",
      "type": "decision-note",
      "status": "proposed",
      "owner": "@timianmalloo",
      "phase": "",
      "reviewBy": "2026-10-24",
      "reviewSuggested": [],
      "summary": "Codex review of W1-ACP at 48e4150: the recorded replay, model setter, nullable last update, and ruled engine scope pass focused checks; a 400 plus api_error classification conflicts with R-23.",
      "tags": [
        "coordination",
        "review",
        "acp"
      ],
      "links": [
        {
          "to": "coordination-finish-harness-bench",
          "rel": "relates-to"
        }
      ],
      "diagrams": [],
      "sourceSha256": "08b1265b915e12b73fe5621627df931828825128e684c695262dd11c5fa642a6"
    },
    {
      "id": "review-w1-copi-design-codex",
      "path": "docs/notes/review-w1-copi-design-codex.md",
      "title": "W1-COP-I cross-vendor design review",
      "type": "decision-note",
      "status": "accepted",
      "owner": "@timianmalloo",
      "phase": "",
      "reviewBy": "2026-10-08",
      "reviewSuggested": [],
      "summary": "Codex cross-vendor review of phase2-copilot-profile revision 3.1 found no defect that stops implementation of the W1-COP-I pinned-tools slice.",
      "tags": [],
      "links": [
        {
          "to": "coordination-finish-harness-bench",
          "rel": "relates-to"
        }
      ],
      "diagrams": [],
      "sourceSha256": "a76c788ec0fb1701f589524c1ff6ca278830343368b65e3c19eb682ad64669fc"
    },
    {
      "id": "review-w1-copr-codex",
      "path": "docs/notes/review-w1-copr-codex.md",
      "title": "W1-COP-R cross-vendor join review",
      "type": "decision-note",
      "status": "accepted",
      "owner": "@timianmalloo",
      "phase": "",
      "reviewBy": "2026-10-08",
      "reviewSuggested": [],
      "summary": "Codex review of W1-COP-R at f266f09: the main Copilot extraction rules pass the focused suite, but a toolCallId pairing mutant survives and a successful tool call can carry a non-null outcome_code. Block the join until both are covered and the latter is fixed.",
      "tags": [
        "coordination",
        "review",
        "copilot",
        "telemetry"
      ],
      "links": [
        {
          "to": "coordination-finish-harness-bench",
          "rel": "relates-to"
        }
      ],
      "diagrams": [],
      "sourceSha256": "35671fe583069173fc176519d61a493be3a11ae77055b810aea82e435fae29e2"
    },
    {
      "id": "review-w1-toolb-codex",
      "path": "docs/notes/review-w1-toolb-codex.md",
      "title": "W1-TOOLB cross-vendor join review",
      "type": "decision-note",
      "status": "accepted",
      "owner": "@timianmalloo",
      "phase": "",
      "reviewBy": "2026-10-24",
      "reviewSuggested": [],
      "summary": "Codex (gpt-6-sol, worker-codex-rtoolb) cleared W1-TOOLB for the R-19 unit-level scope; three review mutants each killed by a named test.",
      "tags": [
        "coordination",
        "review",
        "TOOL-B"
      ],
      "links": [
        {
          "to": "coordination-finish-harness-bench",
          "rel": "relates-to"
        }
      ],
      "diagrams": [],
      "sourceSha256": "0eb44e13d5b0174835d76d56681a8e5d32f9296d8a827a0cb6fe762379b43fcc"
    },
    {
      "id": "review-w2-views-codex",
      "path": "docs/notes/review-w2-views-codex.md",
      "title": "W2-VIEWS cross-vendor join review",
      "type": "decision-note",
      "status": "accepted",
      "owner": "@timianmalloo",
      "phase": "",
      "reviewBy": "2026-10-09",
      "reviewSuggested": [],
      "summary": "Codex review of W2-VIEWS at 64d3392: the ruled validity and warning paths pass focused checks; a truncated native record can still expose partial time and call-count measures.",
      "tags": [],
      "links": [
        {
          "to": "coordination-finish-harness-bench",
          "rel": "relates-to"
        }
      ],
      "diagrams": [],
      "sourceSha256": "af59aae25e087249e9466b861ed062971fbae0fa7b544ef73951141d3df19293"
    },
    {
      "id": "review-w3-egress-codex",
      "path": "docs/notes/review-w3-egress-codex.md",
      "title": "W3-EGRESS slice 1 cross-vendor security review",
      "type": "decision-note",
      "status": "accepted",
      "owner": "@timianmalloo",
      "phase": "",
      "reviewBy": "2026-10-09",
      "reviewSuggested": [],
      "summary": "Security Adversary review of W3-EGRESS slice 1 at a45fbfa: BLOCK because synthetic sensitive values bypass the scanner and the gateway import lint permits a direct backend call.",
      "tags": [],
      "links": [
        {
          "to": "coordination-finish-harness-bench",
          "rel": "relates-to"
        }
      ],
      "diagrams": [],
      "sourceSha256": "9e65e706ea947204a0a1d7ddcd11d657b1559207f3b242fb20377efa18cfdd63"
    },
    {
      "id": "review-w3-gwi-1-fable",
      "path": "docs/notes/review-w3-gwi-1-fable.md",
      "title": "W3-GW-I slice 1 cross-model security review",
      "type": "decision-note",
      "status": "accepted",
      "owner": "@timianmalloo",
      "phase": "",
      "reviewBy": "2026-10-09",
      "reviewSuggested": [],
      "summary": "Security Adversary review of W3-GW-I slice 1 at 371637e: CONDITION. No blocker; two Majors (the served-model check accepts an answer the pin never produced; the gateway lint is evaded by a local alias of the backend), five Minors, and the author's six findings ruled.",
      "tags": [],
      "links": [
        {
          "to": "coordination-finish-harness-bench",
          "rel": "relates-to"
        }
      ],
      "diagrams": [],
      "sourceSha256": "c8a775b475343292c568faba0f0eb5e1513089c18bf3467c55de7bb1a54e077d"
    },
    {
      "id": "row15-headroom",
      "path": "docs/notes/row15-headroom.md",
      "title": "Row 15: the headroom rule for raising the parallelism cap",
      "type": "decision-note",
      "status": "accepted",
      "owner": "@timianmalloo",
      "phase": "",
      "reviewBy": "2026-10-09",
      "reviewSuggested": [],
      "summary": "The rule, written before the measurement run (R-38 condition 1, plan row 15), that decides what parallelism the D1 samples support: memory, CPU and host headroom per cell, times the candidate parallelism, against the host figures.",
      "tags": [],
      "links": [
        {
          "to": "coordination-finish-harness-bench",
          "rel": "relates-to"
        }
      ],
      "diagrams": [],
      "sourceSha256": "0ca960064d9751e162258c10ccb18edfa150f207b9659d2ccd96dc2d02cca212"
    },
    {
      "id": "rulings-register",
      "path": "docs/notes/rulings.md",
      "title": "Owner rulings",
      "type": "decision-note",
      "status": "accepted",
      "owner": "@timianmalloo",
      "phase": "Phase 1 · walking skeleton",
      "reviewBy": "2027-03-22",
      "reviewSuggested": [],
      "summary": "The append-only register of Owner rulings (class `register`, union-merged). Each entry records the ruling verbatim or its chosen option, who ruled, when, and what it decided.",
      "tags": [
        "rulings",
        "register",
        "coordination"
      ],
      "links": [
        {
          "to": "coordination-phase1-finish",
          "rel": "relates-to"
        }
      ],
      "diagrams": [],
      "sourceSha256": "05f95101d98900cbf8c9b0d5a3cc49a44d5078243d207b6fc79650ec3bb1dfe0"
    },
    {
      "id": "design-eval-arms",
      "path": "docs/design/eval-arms.md",
      "title": "W1-A design: arms in the plan (bench-matrix/2, bench-plan/2, blocked launch order, the pack-reader guard)",
      "type": "design",
      "status": "proposed",
      "owner": "@timianmalloo",
      "phase": "Enterprise evaluation: Wave 1 design slice W1-A (builds as X-A1 in E1 and X-A3 in E3)",
      "reviewBy": "2026-10-17",
      "reviewSuggested": [],
      "summary": "Designs ADR-0014 for the code. One new concept, the arm, replaces the pack setting: bench-matrix/2 declares arms and bench-plan/2 freezes one pack revision per pack-bearing arm, one ordered comparison list, a stored launch seed and cells keyed by arm, with the cell_id recipe byte-identical (so grid-4 re-plans to the same 276 ids, shown by spike). Launch order is blocked by (task, combo, rep) with hash-keyed arm order; an accepted plan meets the 5 % bound, found by bounded redraw, and an unsatisfiable shape is refused (HB-PLN-001). A measurement plan refuses a task that is not ready (HB-PLN-004). The pack-reader guard is an AST scan with a per-file hit-count ratchet; three readers migrate in its commit, and four plan-level readers move to the plan_pack accessor (W0 rev 3). A second ratchet counts the bare on/off literals and report.js. The E1 / E3 split, every on/off literal site, the EV-17 test map and six spikes are in the doc. Revision 2 applies the RV-TA, RV-SIM and RV-PAT conditions; each finding has a row in the Review disposition.",
      "tags": [
        "benchmark",
        "campaign",
        "arms",
        "plan",
        "matrix",
        "launch-order",
        "evaluation-campaign",
        "design-slice"
      ],
      "links": [
        {
          "to": "spec-enterprise-evaluation",
          "rel": "implements"
        },
        {
          "to": "arch-evaluation-campaign",
          "rel": "implements"
        },
        {
          "to": "adr-0014-arm-and-cell-grain",
          "rel": "depends-on"
        },
        {
          "to": "design-eval-seam-contracts",
          "rel": "depends-on"
        },
        {
          "to": "rulings-register",
          "rel": "depends-on"
        },
        {
          "to": "review-eval-ta-w1a",
          "rel": "relates-to"
        },
        {
          "to": "review-eval-sim-w1a",
          "rel": "relates-to"
        },
        {
          "to": "review-eval-pat-w1a",
          "rel": "relates-to"
        }
      ],
      "diagrams": [],
      "sourceSha256": "6b96dee39670f518834044ffa1fe16bc1e4956939b50163ebb378ff8ca6cdb84"
    },
    {
      "id": "design-eval-atomic-publish",
      "path": "docs/design/eval-atomic-publish.md",
      "title": "W1-B design: crash-atomic publish (atomic.py create_once and publish_dir, archive.py rework)",
      "type": "design",
      "status": "proposed",
      "owner": "@timianmalloo",
      "phase": "Enterprise evaluation: Wave 1 design slice W1-B; builds in E1 (X-B1 atomic.py, X-B2 archive.py)",
      "reviewBy": "2026-10-17",
      "reviewSuggested": [],
      "summary": "Designs the two write helpers every campaign record and every archive goes through: create_once (a file appears only complete, never overwritten) and publish_dir (a folder appears only after its copy verified), plus the one recovery rule for the crash window between the rename and the ledger rows (specified here, built by X-K1 in E3). Revision 2 applies the five W1-B lens reviews (34 findings, each dispositioned in section 18) and W0 rev 3. Settles the data model (the published name is the only completeness fact), the temp-name and sweep contract, the Windows no-directory-fsync branch, the strict verify, the reader surfaces a leaked temp would break, and names every red-first test and seeded mutant so X-B1 and X-B2 can start from this file alone. Adds three measured Windows facts (text-mode os.write corrupts bytes, a junction is unlinkable, a held handle blocks a folder rename).",
      "tags": [
        "benchmark",
        "crash-atomic",
        "archive",
        "create-once",
        "evaluation-campaign",
        "w1-b"
      ],
      "links": [
        {
          "to": "spec-enterprise-evaluation",
          "rel": "implements"
        },
        {
          "to": "arch-evaluation-campaign",
          "rel": "implements"
        },
        {
          "to": "design-eval-seam-contracts",
          "rel": "depends-on"
        },
        {
          "to": "adr-0015-multi-turn-attempt-and-turn-snapshots",
          "rel": "depends-on"
        },
        {
          "to": "adr-0016-campaign-record",
          "rel": "depends-on"
        },
        {
          "to": "adr-0021-plan-level-resume-and-liveness",
          "rel": "depends-on"
        },
        {
          "to": "note-20261003-spike-e1-ntfs-atomic-publish",
          "rel": "depends-on"
        },
        {
          "to": "review-eval-ds",
          "rel": "relates-to"
        },
        {
          "to": "review-eval-sec",
          "rel": "relates-to"
        },
        {
          "to": "review-eval-pat",
          "rel": "relates-to"
        },
        {
          "to": "review-eval-ta",
          "rel": "relates-to"
        },
        {
          "to": "defect-classes",
          "rel": "relates-to"
        }
      ],
      "diagrams": [],
      "sourceSha256": "4706e446d39f829dfaa8bf399dd337646353d79baf5ff7fa33e8f8bea7c986ee"
    },
    {
      "id": "design-eval-campaign-record",
      "path": "docs/design/eval-campaign-record.md",
      "title": "W1-C design: the campaign record and `bench campaign`",
      "type": "design",
      "status": "proposed",
      "owner": "@timianmalloo",
      "phase": "Enterprise evaluation: Wave 1 (W1-C; builds as X-C in E1)",
      "reviewBy": "2026-10-17",
      "reviewSuggested": [],
      "summary": "Designs campaign.py and the `bench campaign` commands (revision 2): a closed 11-kind hash-chained ledger folded into a derived state with one legal path from every fix back to a registration, a state guard / idempotency rule / refusal copy / test node for every command, write commands under the own-lock-then-probe protocol (the proof plus a barrier test with a positive control, not a race count) and lock-free reads, the pre-registration freeze (attach before launch, re-register refused once attached, a run-side check inside the engine), plan binding by plan_hash, id and link validation before any path is built, `verify` with a content-keyed git witness over the committed history, derived eligibility, and a test plan whose every node names the assertion that fails today, the red fixture, the real-wiring partner and a written mutant.",
      "tags": [
        "benchmark",
        "campaign",
        "ledger",
        "freeze",
        "locks",
        "evaluation-campaign"
      ],
      "links": [
        {
          "to": "spec-enterprise-evaluation",
          "rel": "implements"
        },
        {
          "to": "arch-evaluation-campaign",
          "rel": "implements"
        },
        {
          "to": "adr-0016-campaign-record",
          "rel": "depends-on"
        },
        {
          "to": "adr-0017-engine-identity-and-freeze",
          "rel": "depends-on"
        },
        {
          "to": "adr-0018-hidden-check-harness",
          "rel": "depends-on"
        },
        {
          "to": "adr-0006-results-data-model",
          "rel": "depends-on"
        },
        {
          "to": "design-eval-seam-contracts",
          "rel": "depends-on"
        }
      ],
      "diagrams": [],
      "sourceSha256": "7e1aeb94d7c8581537bdf9539244c0745fcb3ee38c739a20089246d8f5a7e5df"
    },
    {
      "id": "design-eval-catalog-0-7",
      "path": "docs/design/eval-catalog-0-7.md",
      "title": "Catalog 0.7 (ADR-0019): the eleven property metrics, scenario-7 pass@1 and the missing-pass@1 fix",
      "type": "design",
      "status": "proposed",
      "owner": "@timianmalloo",
      "phase": "Enterprise evaluation: Wave 1, design slice W1-G (builds X-G1 in E1, X-G3 and the _passed fix in E3)",
      "reviewBy": "2026-10-17",
      "reviewSuggested": [],
      "summary": "Design of catalog 0.7: the eleven property metrics written out in full YAML with R-79 anchors and no new area; the dispatch rule that lets one grader record a metric another grader owns (the property: tag and the new also_graded_by key); the per-task formal.pass_rule that makes scenario-7 pass_at_1 a three-valued AND; the missing-pass@1 fix and its sweep as the new defect class ABS-A; and the US-4 control, which is a cross-version regrade against the committed 0.6 goldens, with the 0.6 definitions read from the freeze commit. Revision 2 applies the three W1-G reviews, W0 rev 3 and R-95: the owner rule is ruled, and the corrected_from record is a written contingency.",
      "tags": [
        "benchmark",
        "catalog",
        "metrics",
        "grading",
        "us-4",
        "evaluation-campaign",
        "w1-g"
      ],
      "links": [
        {
          "to": "spec-enterprise-evaluation",
          "rel": "implements"
        },
        {
          "to": "arch-evaluation-campaign",
          "rel": "implements"
        },
        {
          "to": "adr-0019-catalog-0-7-property-metrics",
          "rel": "depends-on"
        },
        {
          "to": "design-eval-seam-contracts",
          "rel": "depends-on"
        },
        {
          "to": "rulings-register",
          "rel": "depends-on"
        }
      ],
      "diagrams": [],
      "sourceSha256": "0b5cff38703dc03b75420c16279c50cb8fd147a5a72d3d99e31bc0a035034810"
    },
    {
      "id": "design-eval-discriminate",
      "path": "docs/design/eval-discriminate.md",
      "title": "W1-E design: discriminate, the synthetic profile and the readiness check (EV-7; X-E)",
      "type": "design",
      "status": "proposed",
      "owner": "@timianmalloo",
      "phase": "Enterprise evaluation: Wave 1 design slice W1-E; builds in E1 (X-E: discriminate.py, readiness.py, synthetic_agent.py)",
      "reviewBy": "2026-10-17",
      "reviewSuggested": [],
      "summary": "Designs the one path by which a property task becomes ready: bench discriminate runs the task's reference, its naive solution and its defect variants as synthetic cells through the real engine, working-copy builder, archiver and grading pass (and so, for check-based properties, the real probe host), and writes a create-once, idempotent discrimination record; readiness.py then refuses `ready` unless that record exists, matches the current task version and engine, was made by the real host where the property has one, and every expected value is observed. Settles the record's data model (no run id in its body, so a legitimate retry is a no-op; R-98), the synthetic agent (a stdlib ACP process behind Launcher; engine.py unchanged, Verified by spike S-E1), the one overlay path rule, the disagreement and clock-failure readers, the sweeper, and names every red-first test with its fixture, real-wiring partner and mutant. Revision 2 applies the four first-round reviews.",
      "tags": [
        "benchmark",
        "discrimination",
        "readiness",
        "synthetic-agent",
        "evaluation-campaign",
        "w1-e"
      ],
      "links": [
        {
          "to": "spec-enterprise-evaluation",
          "rel": "implements"
        },
        {
          "to": "arch-evaluation-campaign",
          "rel": "implements"
        },
        {
          "to": "design-eval-seam-contracts",
          "rel": "depends-on"
        },
        {
          "to": "adr-0016-campaign-record",
          "rel": "depends-on"
        },
        {
          "to": "adr-0018-hidden-check-harness",
          "rel": "depends-on"
        },
        {
          "to": "adr-0019-catalog-0-7-property-metrics",
          "rel": "depends-on"
        },
        {
          "to": "design-eval-property-grader",
          "rel": "depends-on"
        },
        {
          "to": "design-eval-atomic-publish",
          "rel": "depends-on"
        },
        {
          "to": "design-eval-security-tasks",
          "rel": "relates-to"
        },
        {
          "to": "defect-classes",
          "rel": "relates-to"
        }
      ],
      "diagrams": [],
      "sourceSha256": "008437404b45b0b3328917767710ec3a299871230386130f26c7f292a34afe57"
    },
    {
      "id": "design-eval-identity",
      "path": "docs/design/eval-identity.md",
      "title": "W1-D design: engine identity, freeze and per-launch recheck",
      "type": "design",
      "status": "proposed",
      "owner": "@timianmalloo",
      "phase": "Enterprise evaluation: Wave 1 (W1-D; builds as X-D in E1)",
      "reviewBy": "2026-10-17",
      "reviewSuggested": [],
      "summary": "Amendment 1 (R-106, 2026-10-05): the launch recheck's key set is the plan stamp's; builds/<h> is read only where the stamp holds it. Designs identity.py (manifest, hash, side, diff, the one CLASSES table), the per-launch run-side recheck in engine.py with identity_check_ms, grading.started.grade_identity_hash (E1), and the guards. Rev 2 applies R-94 (telemetry/* run, gateway grade; ADR-0017 Amendment 1) and the four first-round reviews: a real-wiring test, red fixtures for every scan, one retry mechanism with a wall-clock cap, and a cost model that prices run-class edits. All 69 existing files and 18 planned modules classed; no third \"tooling\" class.",
      "tags": [
        "benchmark",
        "campaign",
        "identity",
        "freeze",
        "evaluation-campaign"
      ],
      "links": [
        {
          "to": "spec-enterprise-evaluation",
          "rel": "implements"
        },
        {
          "to": "arch-evaluation-campaign",
          "rel": "implements"
        },
        {
          "to": "adr-0017-engine-identity-and-freeze",
          "rel": "depends-on"
        },
        {
          "to": "adr-0016-campaign-record",
          "rel": "depends-on"
        },
        {
          "to": "adr-0021-plan-level-resume-and-liveness",
          "rel": "depends-on"
        },
        {
          "to": "design-eval-seam-contracts",
          "rel": "depends-on"
        },
        {
          "to": "rulings-register",
          "rel": "depends-on"
        }
      ],
      "diagrams": [],
      "sourceSha256": "a4dd25386a918a1b5712ff2674dee915a4a9b65de59b60aba6ba3d25d6b7029e"
    },
    {
      "id": "design-eval-multi-turn",
      "path": "docs/design/eval-multi-turn.md",
      "title": "Design: multi-turn attempt, turn snapshots and the TLA+ model (W1-J, ADR-0015)",
      "type": "design",
      "status": "proposed",
      "owner": "@timianmalloo",
      "phase": "Enterprise evaluation: Wave 1 (E2 build track X-J1)",
      "reviewBy": "2026-10-17",
      "reviewSuggested": [],
      "summary": "How a cell holds a second user turn on one ACP session: the driver splits into open, send-turn and close; the engine snapshots the working copy between turns into archive/<cell>/turn-<n>/ through the crash-atomic publish of W0 section 4 before turn n+1's prompt_sent is durable; archive_files gains a snapshot key part that old rows read as final, so every existing verify result is unchanged; the budget clock starts once, at turn 1. The lifecycle model gains a turn index, a snapshot protocol and phased archive writes. TLC passes it and rejects every seeded variant of the five ADR-0015 section 7 invariants.",
      "tags": [
        "evaluation-campaign",
        "multi-turn",
        "snapshot",
        "run-engine",
        "archive",
        "lifecycle",
        "tla",
        "wave-1"
      ],
      "links": [
        {
          "to": "spec-enterprise-evaluation",
          "rel": "implements"
        },
        {
          "to": "arch-evaluation-campaign",
          "rel": "implements"
        },
        {
          "to": "adr-0015-multi-turn-attempt-and-turn-snapshots",
          "rel": "depends-on"
        },
        {
          "to": "adr-0007-run-engine",
          "rel": "depends-on"
        },
        {
          "to": "adr-0013-native-cells",
          "rel": "depends-on"
        },
        {
          "to": "design-eval-seam-contracts",
          "rel": "depends-on"
        },
        {
          "to": "design-run-lifecycle-model",
          "rel": "refines"
        },
        {
          "to": "note-20261003-spike-e4-post-turn-prompt",
          "rel": "depends-on"
        }
      ],
      "diagrams": [],
      "sourceSha256": "ec32047a19941e50e22cc734dc87ff2ff3e971173d1fa6c2c03d4536e81e57cb"
    },
    {
      "id": "design-eval-power-verdicts",
      "path": "docs/design/eval-power-verdicts.md",
      "title": "Design: power, verdicts, dominance, ring gates and report section 3 (W1-H; X-H1, X-H2)",
      "type": "design",
      "status": "proposed",
      "owner": "@timianmalloo",
      "phase": "Enterprise evaluation: Wave 1 design slice W1-H (build in E1)",
      "reviewBy": "2026-10-17",
      "reviewSuggested": [],
      "summary": "Pure stdlib design for X-H1 (power.py, verdicts.py, gates.py) and the section-3 view for X-H2. Settles the derived-view data model (nothing persisted), pins the three reference sizes (93, 53, 115) exactly with an independent formula and a seeded-wrong variant, the stratified paired bootstrap and the verdict and dominance rules as boundary tables with named mutants, nine pilot gate kinds each with a red fixture, the EV-8 admission function, the R-93 three-state warning line, the R-96 level rule (holm is sized like Bonferroni, disclosed), and the NA-never-dropped rule. Revision 2 applies the three gate reviews (all PASS WITH CONDITIONS). Reports measured spikes, two defects found in W0 text (seed width, resolved in rev 3) and the residual risks.",
      "tags": [
        "benchmark",
        "statistics",
        "power-analysis",
        "verdict",
        "dominance",
        "ring-gate",
        "report",
        "evaluation-campaign"
      ],
      "links": [
        {
          "to": "spec-enterprise-evaluation",
          "rel": "implements"
        },
        {
          "to": "arch-evaluation-campaign",
          "rel": "implements"
        },
        {
          "to": "adr-0020-power-and-verdicts-stdlib",
          "rel": "depends-on"
        },
        {
          "to": "design-eval-seam-contracts",
          "rel": "depends-on"
        },
        {
          "to": "adr-0006-results-data-model",
          "rel": "depends-on"
        },
        {
          "to": "rulings-register",
          "rel": "depends-on"
        }
      ],
      "diagrams": [],
      "sourceSha256": "433e03284f6dde833b0505aab5d171cec193650cad5d8931673b96488d47e8cd"
    },
    {
      "id": "design-eval-property-grader",
      "path": "docs/design/eval-property-grader.md",
      "title": "Design W1-F: the hidden-check runner and the property grader (boundary B7, security-sensitive)",
      "type": "design",
      "status": "proposed",
      "owner": "@timianmalloo",
      "phase": "Enterprise evaluation E1: Wave 1 design slice W1-F (built by X-F in E1; loopback by X-LB in E4)",
      "reviewBy": "2026-10-17",
      "reviewSuggested": [],
      "summary": "Revision 2, conformed to W0 rev 2. One registered `property` grader (R-90): runner.applicable narrows it to the task's property; it runs the hidden tests through correctness.grade() and then the task's hidden check in a fresh, reparse-safe copy, in a new Job Object, started DETACHED with the base interpreter under -S and the grading environment allowlist. The check never imports agent code: probes go through a probe-host child whose pipes the check owns (the module-body forgery is committed as a fixture with its positive control). The grader accepts one line from a live, lone check, acknowledges it with one byte, and classifies by W0's seven ordered rows, with the suspend rule on each phase's span. E1 builds the security strategy, probe cases, and `callable` and `wsgi` apps. Revision 3 (W0 rev 3, ruling C-1) adds the `wsgi` kind with W0's frames, a complete PEP 3333 environ, a factory with `{state_dir}` args, `paths`, app output kept off the protocol channel, and the start bound; spike SP-F3 re-ran the forgery against a wsgi host. Gate: rev 3 delta pending RV-TA, RV-SEC.",
      "tags": [
        "benchmark",
        "grading",
        "property-grader",
        "hidden-check",
        "security",
        "trust-boundary",
        "b7",
        "evaluation-campaign",
        "wave-1"
      ],
      "links": [
        {
          "to": "spec-enterprise-evaluation",
          "rel": "implements"
        },
        {
          "to": "arch-evaluation-campaign",
          "rel": "implements"
        },
        {
          "to": "design-eval-seam-contracts",
          "rel": "depends-on"
        },
        {
          "to": "adr-0018-hidden-check-harness",
          "rel": "depends-on"
        },
        {
          "to": "adr-0010-untrusted-cell-output",
          "rel": "depends-on"
        },
        {
          "to": "adr-0012-proportionate-security",
          "rel": "depends-on"
        },
        {
          "to": "adr-0013-native-cells",
          "rel": "depends-on"
        },
        {
          "to": "adr-0019-catalog-0-7-property-metrics",
          "rel": "depends-on"
        },
        {
          "to": "rulings-register",
          "rel": "depends-on"
        },
        {
          "to": "note-20261003-spike-e1-job-alone",
          "rel": "depends-on"
        },
        {
          "to": "note-20261003-spike-e1-handle-list",
          "rel": "depends-on"
        },
        {
          "to": "note-spike-phase1-probes",
          "rel": "depends-on"
        },
        {
          "to": "note-20260924-spike-a9-host-sleep",
          "rel": "depends-on"
        },
        {
          "to": "design-phase3-graders",
          "rel": "refines"
        },
        {
          "to": "coordination-eval-campaign",
          "rel": "relates-to"
        },
        {
          "to": "review-eval-ta-w1f",
          "rel": "relates-to"
        },
        {
          "to": "review-eval-sec-w1f",
          "rel": "relates-to"
        },
        {
          "to": "review-eval-pat-w1f",
          "rel": "relates-to"
        },
        {
          "to": "review-eval-sim-w1f",
          "rel": "relates-to"
        }
      ],
      "diagrams": [],
      "sourceSha256": "3447cd7b555398d32db4806ce87a9c20aacdf772e26073dcbbe41f33804ef815"
    },
    {
      "id": "design-eval-property-tasks",
      "path": "docs/design/eval-property-tasks.md",
      "title": "Design W1-L: the remaining property tasks (resilience, rework, no-guessing, simplicity; two each)",
      "type": "design",
      "status": "proposed",
      "owner": "@timianmalloo",
      "phase": "Enterprise evaluation E2/E4: Wave 1 design slice W1-L (rework by X-RW in E2; the rest in E4)",
      "reviewBy": "2026-10-17",
      "reviewSuggested": [],
      "summary": "Eight tasks specified to the level an author can build without a question: for each of RS1/RS2 (resilience), RW1/RW2 (rework), NG1/NG2 (no-guessing) and SM1/SM2 (simplicity) a real MIT or Apache base at a pinned 40-hex commit (eight distinct bases, all imported under python -S), the latent requirement, the prompt shape, hidden tests with a wrong-app fixture for every test, the check or strategy, reference and naive shapes, expected values with provenance (Inferred until the real host reproduces them), and the seeded-defect variants that flip each probe, case clause or metric. Revision 2 applies the three first-round lens reviews and W0 rev 5: three new graders (noguess with hallucinated_symbol_errors per R-97; diffstats; rework) plus the resilience cases, the whole-tree simplicity counts with the outside-radius clause and v-laundered, verified_before_use not built in E4, skeleton-first commits for the helpers, and one parametrised task-test module. Gate: rev 2 pending RV-TA.",
      "tags": [
        "benchmark",
        "property-tasks",
        "resilience",
        "rework",
        "no-guessing",
        "simplicity",
        "evaluation-campaign",
        "wave-1"
      ],
      "links": [
        {
          "to": "spec-enterprise-evaluation",
          "rel": "implements"
        },
        {
          "to": "arch-evaluation-campaign",
          "rel": "implements"
        },
        {
          "to": "design-eval-seam-contracts",
          "rel": "depends-on"
        },
        {
          "to": "design-eval-property-grader",
          "rel": "depends-on"
        },
        {
          "to": "design-eval-security-tasks",
          "rel": "depends-on"
        },
        {
          "to": "adr-0015-multi-turn-attempt-and-turn-snapshots",
          "rel": "depends-on"
        },
        {
          "to": "adr-0018-hidden-check-harness",
          "rel": "depends-on"
        },
        {
          "to": "adr-0019-catalog-0-7-property-metrics",
          "rel": "depends-on"
        },
        {
          "to": "rulings-register",
          "rel": "depends-on"
        },
        {
          "to": "coordination-eval-wave1-briefs",
          "rel": "relates-to"
        }
      ],
      "diagrams": [],
      "sourceSha256": "b14637314c7501ad8ce14c5b9d741f65331dc4544c28b17107039ddb33753158"
    },
    {
      "id": "design-eval-resume",
      "path": "docs/design/eval-resume.md",
      "title": "Design: plan-level resume, liveness and the alarm channel (W1-K, ADR-0021)",
      "type": "design",
      "status": "proposed",
      "owner": "@timianmalloo",
      "phase": "Enterprise evaluation: Wave 1 (E3 build tracks X-K1, X-K2)",
      "reviewBy": "2026-10-17",
      "reviewSuggested": [],
      "summary": "How a restarted `bench run <run_id>` resumes: a pure classifier over the ledger maps every recorded cell state to one ADR-0021 section 4 action; one predicate `resume.has_work` is the only definition of remaining work, shared by the resume and the alarm (R-102); the refusals (including an unrepairable archive) run in a fixed order under the run lock, before any row is written; the dead engine's segments are marked abandoned, never written into; one `run.resumed` row per resume is the whole resume record (counts are derived). A resume of a stopped run finishes the stop (R-100) with the engine's own post-stop tail (R-101): it launches nothing, records `stopped` for every intent-without-outcome cell, archives, grades, writes `run.completed{grading}` and exits 3; the model's invariant is `NoLaunchAfterStop`, and no liveness property carries a crash exception. The TLA+ model also settles the two resume branches W1-J left provisional by the recorded `next` of each turn, and TLC rejects every new seeded variant. Liveness is the newest `recorded_at` over the segment tails; the alarm is a scheduled Windows task whose primary and required channel for an unattended run is an ntfy phone push (R-102), edge-triggered with a delivery log; the toast is optional and joins at the E5 drill.",
      "tags": [
        "evaluation-campaign",
        "resume",
        "liveness",
        "alarm",
        "sre",
        "tla",
        "wave-1"
      ],
      "links": [
        {
          "to": "spec-enterprise-evaluation",
          "rel": "implements"
        },
        {
          "to": "arch-evaluation-campaign",
          "rel": "implements"
        },
        {
          "to": "adr-0021-plan-level-resume-and-liveness",
          "rel": "depends-on"
        },
        {
          "to": "adr-0015-multi-turn-attempt-and-turn-snapshots",
          "rel": "depends-on"
        },
        {
          "to": "adr-0007-run-engine",
          "rel": "depends-on"
        },
        {
          "to": "design-eval-seam-contracts",
          "rel": "depends-on"
        },
        {
          "to": "design-eval-multi-turn",
          "rel": "depends-on"
        },
        {
          "to": "design-eval-atomic-publish",
          "rel": "depends-on"
        },
        {
          "to": "design-run-lifecycle-model",
          "rel": "refines"
        }
      ],
      "diagrams": [],
      "sourceSha256": "8517db2563c008917ffc02f8d969c073626b4716a9637145a5ceb70e6b760bb1"
    },
    {
      "id": "design-eval-seam-contracts",
      "path": "docs/design/eval-seam-contracts.md",
      "title": "W0 seam contracts: the interfaces every Evaluation Campaign slice designs and builds against",
      "type": "design",
      "status": "proposed",
      "owner": "@timianmalloo",
      "phase": "Enterprise evaluation: W0 (serial spine item 2), before Wave 1",
      "reviewBy": "2026-10-17",
      "reviewSuggested": [],
      "summary": "Revision 6.13 (Coordinator #39: HB-PLN-005 retired by X-A3c; the copy_retries null erratum; J1c's snapshot TABLE entry; X-K2b no longer waits on X-TE9; HB-ALM-003 to E5; the G1 cli.py and workspace.py pins stay; rev-6.13 change table at the end). Revision 6.12 (Coordinator #35: `cell.turn_ended` carries the int `turn_ms`, not a float `turn_seconds`, because the canonical form has no floats; X-J1b writes the one `lifecycle.TABLE` entry for it; the discrimination record's `hosts_ready` is an int count; rev-6.12 change table at the end). Revision 6.11 (C-W0, Coordinator #31: R-106's launch-recheck key set in section 6, the R-106 c7 reader key-set sweep, the shared-value rule (keys and value types), the X-K2a script-only split, the section 13 rows of the E2-E4 plan and HB-GRD-007 to X-C; rev-6.11 change table and re-read list at the end). Revision 6 (R-98: the discrimination record body drops `run_id` and `grading_id`, ADR-0016 Amendment 1; and the conditions of the five W0 rev 4/5 delta reviews; rev-6 change table and re-read list at the end). Revision 5 (the W1-E and W1-L seam answers SR-E1, SR-E2, SR-L1..SR-L4, the W1-L review rulings and R-97; rev-5 change table and re-read list at the end; DR-E1, then open, is ruled by R-98 and applied in rev 6). Revision 4 (the batch-b seam answers and the RV-PAT, RV-SIM, RV-SEC and RV-DS cross-slice findings on W1-B, W1-C, W1-D and W1-H; rev-4 change table and the delta re-read list at the end; rev 3's table kept). The one vocabulary the twelve Wave 1 design slices and the Wave 2 tracks share: the ten property-task ids and their BOM and task.yaml stubs, the task.yaml property and expected-value fields, the PropertyCheck input, result, framing and outcome precedence, create_once and the directory publish, bench-matrix/2 and bench-plan/2, the campaign ledger rows and the pre-registration freeze order, the identity manifest, the discrimination record, the catalog 0.7 metric ids under R-90, the power, verdict and gate shapes, every planned new module with its run/grade class, the HB codes reserved per track, the hub-file owner per phase, and the four frozen fields of every shared-surface guard. Ends with the disposition of every finding of the five W0 lens reviews.",
      "tags": [
        "benchmark",
        "campaign",
        "seam-contracts",
        "coordination",
        "w0",
        "evaluation-campaign"
      ],
      "links": [
        {
          "to": "arch-evaluation-campaign",
          "rel": "implements"
        },
        {
          "to": "spec-enterprise-evaluation",
          "rel": "implements"
        },
        {
          "to": "coordination-eval-campaign",
          "rel": "implements"
        },
        {
          "to": "adr-0014-arm-and-cell-grain",
          "rel": "depends-on"
        },
        {
          "to": "adr-0015-multi-turn-attempt-and-turn-snapshots",
          "rel": "depends-on"
        },
        {
          "to": "adr-0016-campaign-record",
          "rel": "depends-on"
        },
        {
          "to": "adr-0017-engine-identity-and-freeze",
          "rel": "depends-on"
        },
        {
          "to": "adr-0018-hidden-check-harness",
          "rel": "depends-on"
        },
        {
          "to": "adr-0019-catalog-0-7-property-metrics",
          "rel": "depends-on"
        },
        {
          "to": "adr-0020-power-and-verdicts-stdlib",
          "rel": "depends-on"
        },
        {
          "to": "adr-0021-plan-level-resume-and-liveness",
          "rel": "depends-on"
        },
        {
          "to": "note-20261003-spike-e1-ntfs-atomic-publish",
          "rel": "depends-on"
        },
        {
          "to": "note-20261003-spike-e1-job-alone",
          "rel": "depends-on"
        },
        {
          "to": "note-20261003-spike-e1-handle-list",
          "rel": "depends-on"
        },
        {
          "to": "rulings-register",
          "rel": "depends-on"
        },
        {
          "to": "review-eval-ta",
          "rel": "relates-to"
        },
        {
          "to": "review-eval-sec",
          "rel": "relates-to"
        },
        {
          "to": "review-eval-ds",
          "rel": "relates-to"
        },
        {
          "to": "review-eval-pat",
          "rel": "relates-to"
        },
        {
          "to": "review-eval-sim",
          "rel": "relates-to"
        }
      ],
      "diagrams": [],
      "sourceSha256": "26ce62573cc24d58a2df4c04f27adb14cf08e7a89d9d3712a55dae41946e7cfd"
    },
    {
      "id": "design-eval-security-tasks",
      "path": "docs/design/eval-security-tasks.md",
      "title": "Design W1-I: security tasks S1 and S2 (two codebases, a latent guard, in-process probes)",
      "type": "design",
      "status": "proposed",
      "owner": "@timianmalloo",
      "phase": "Enterprise evaluation E1/E4: Wave 1 design slice W1-I (S1 authored by X-I in E1; S2 in E4)",
      "reviewBy": "2026-10-17",
      "reviewSuggested": [],
      "summary": "S1 is specified to the point X-I can author it with no question: base microdot at a pinned commit (MIT, stdlib only), the prompt text, eight hidden functional tests (each shown red by a wrong-app fixture, not only by a missing module), eight in-process probes in a probe host (2 injection groups, 3 authorization bypass, 3 secret leak, both principals' tokens scanned, all BENCHCANARY- values), the reference and naive solutions, expected values with provenance (reference 1.0000, naive 0.3750, hand-derived), the interface case bound, and a defect-variant set that proves every probe branch live (flipped set, hidden tests green, deliverable ran, deciding clause). S1 is built on W0 rev 3 (ruling C-1: app.kind wsgi in E1, wsgi frame names, five probe-host items, start bound). S2 is cut to its base, pin, licence, tenancy unit and probe classes until an E4 spike. Rev 2 applies the four first-round reviews. Gate: rev 2 pending RV-TA, RV-PAT.",
      "tags": [
        "benchmark",
        "property-tasks",
        "security",
        "hidden-check",
        "canary",
        "evaluation-campaign",
        "wave-1"
      ],
      "links": [
        {
          "to": "spec-enterprise-evaluation",
          "rel": "implements"
        },
        {
          "to": "arch-evaluation-campaign",
          "rel": "implements"
        },
        {
          "to": "design-eval-seam-contracts",
          "rel": "depends-on"
        },
        {
          "to": "adr-0018-hidden-check-harness",
          "rel": "depends-on"
        },
        {
          "to": "adr-0019-catalog-0-7-property-metrics",
          "rel": "depends-on"
        },
        {
          "to": "adr-0012-proportionate-security",
          "rel": "depends-on"
        },
        {
          "to": "adr-0013-native-cells",
          "rel": "depends-on"
        },
        {
          "to": "rulings-register",
          "rel": "depends-on"
        },
        {
          "to": "coordination-eval-wave1-briefs",
          "rel": "relates-to"
        }
      ],
      "diagrams": [],
      "sourceSha256": "93b474584bcd4844385345f9f440d7b041c260738094034ca4ab0e5232025331"
    },
    {
      "id": "design-formal-grader",
      "path": "docs/design/formal-grader.md",
      "title": "Design: the formal grader (grade/formal.py) — checks, statement integrity, trace conformance, bug confirmation",
      "type": "design",
      "status": "draft",
      "owner": "@timianmalloo",
      "phase": "Phase 2: deterministic graders (S-08g); unblocks T-G1, T-G2",
      "reviewBy": "2027-03-29",
      "reviewSuggested": [
        {
          "by": "adr-0006-results-data-model",
          "on": "2026-10-03",
          "reason": "Proposed amendment 2026-10-03 (ADR-0014/0015, arch-evaluation-campaign): cell grain by arm, per-turn prompt_sent, archive_files snapshot key part, job terminated after the last turn; council gate pending"
        },
        {
          "by": "adr-0013-native-cells",
          "on": "2026-10-03",
          "reason": "Proposed amendment 2026-10-03 (ADR-0014/0015, arch-evaluation-campaign): cell grain by arm, per-turn prompt_sent, archive_files snapshot key part, job terminated after the last turn; council gate pending"
        }
      ],
      "summary": "Design for grade/formal.py: the four US-32 scores (checks, statement integrity, model conformance, model non-vacuity) plus US-33 bug confirmation (bugs_confirmed, bug_claim_precision) for G1 (TLA+) and G2 (Lean 4). Closes S-12's warm-before-clock gap for tla2tools.jar by design; names the toolchain invocation contract (correctness.run_step, the only sanctioned procs path); flags the TLA+ trace-replay mechanism as unspiked.",
      "tags": [
        "benchmark",
        "grading",
        "formal-methods",
        "tla+",
        "lean",
        "scenario-7"
      ],
      "links": [
        {
          "to": "spec-harness-bench",
          "rel": "implements"
        },
        {
          "to": "plan-spec-backlog",
          "rel": "refines"
        },
        {
          "to": "note-spike-s12-formal-toolchains",
          "rel": "depends-on"
        },
        {
          "to": "note-proposal-grounding-findings",
          "rel": "depends-on"
        },
        {
          "to": "design-phase3-graders",
          "rel": "refines"
        },
        {
          "to": "adr-0006-results-data-model",
          "rel": "depends-on"
        },
        {
          "to": "adr-0013-native-cells",
          "rel": "depends-on"
        }
      ],
      "diagrams": [],
      "sourceSha256": "35a9e21a114a060769440616d23bb3d0b920e247b9a003616b64bde3f0da2b9c"
    },
    {
      "id": "design-pack-improvement-section",
      "path": "docs/design/pack-improvement-section.md",
      "title": "Design: the report's closing section, \\\"Pack on vs pack off — where to improve the pack\\\"",
      "type": "design",
      "status": "draft",
      "owner": "@timianmalloo",
      "phase": "Phase 4 · report (follow-on to row 20)",
      "reviewBy": "2027-03-31",
      "reviewSuggested": [],
      "summary": "Specifies a report section that is always present and always last: from a run's own facts it computes paired pack-on/pack-off deltas, a value-vs-waste class per (task, combo), ceremony and drift indicators read from the native records, inconclusive detection, per-intention verdicts and a ranked, deterministic list of \"where to improve the pack\" findings (PK-01..PK-08). Every number names its source file and field; NA always carries a reason and small n is always shown. Report-only (no new ledger fact); red-first test plan with goldens from grid-1 and grid-1-cc; six slices. Written for an engineer who was not in the analysis session.",
      "tags": [
        "benchmark",
        "report",
        "pack-effect",
        "continuous-improvement",
        "statistics",
        "transcripts"
      ],
      "links": [
        {
          "to": "design-phase4-report",
          "rel": "depends-on"
        },
        {
          "to": "design-phase4-statistics",
          "rel": "depends-on"
        },
        {
          "to": "proposal-pack-onoff-analysis",
          "rel": "implements"
        },
        {
          "to": "proposal-enterprise-production-portfolio",
          "rel": "relates-to"
        }
      ],
      "diagrams": [],
      "sourceSha256": "0dc3681fd1745437a69f34261b6837f1d9a3da86aa38a638855b31426cd0ab8f"
    },
    {
      "id": "design-phase1-walking-skeleton",
      "path": "docs/design/phase1-walking-skeleton.md",
      "title": "Design: phase 1 walking skeleton (engine, cells, telemetry, grading, report)",
      "type": "design",
      "status": "draft",
      "owner": "@timianmalloo",
      "phase": "Phase 1 · walking skeleton (S-05, S-06, S-07, S-08a/b/f, S-10 skeleton)",
      "reviewBy": "2027-03-22",
      "reviewSuggested": [
        {
          "by": "adr-0006-results-data-model",
          "on": "2026-09-24",
          "reason": "Amendment 1: model_calls grain re-declared per native usage report with requests and model in the key; tool_calls.outcome_code (R-26, R-27)"
        },
        {
          "by": "adr-0007-run-engine",
          "on": "2026-10-03",
          "reason": "Proposed amendment 2026-10-03 (ADR-0014/0015, arch-evaluation-campaign): cell grain by arm, per-turn prompt_sent, archive_files snapshot key part, job terminated after the last turn; council gate pending"
        },
        {
          "by": "adr-0013-native-cells",
          "on": "2026-10-03",
          "reason": "Proposed amendment 2026-10-03 (ADR-0014/0015, arch-evaluation-campaign): cell grain by arm, per-turn prompt_sent, archive_files snapshot key part, job terminated after the last turn; council gate pending"
        }
      ],
      "summary": "The detailed design of the thinnest end-to-end path: prose → confirmed plan → run engine → native cells, each in its own git working copy and Job Object, driven over ACP (Claude, Codex) → verified archive → telemetry from native records → correctness and cost graded in grading working copies → pure projections → CLI table and a minimal HTML report. Version 4: cells run natively in their own working copies and Job Objects (ADR-0013); validity-first; the engine's launch, kill and record order matched to the checked lifecycle model.",
      "tags": [
        "benchmark",
        "runner",
        "engine",
        "native-cells",
        "acp",
        "telemetry",
        "grading",
        "report"
      ],
      "links": [
        {
          "to": "arch-harness-bench",
          "rel": "implements"
        },
        {
          "to": "spec-harness-bench",
          "rel": "implements"
        },
        {
          "to": "design-run-lifecycle-model",
          "rel": "depends-on"
        },
        {
          "to": "adr-0013-native-cells",
          "rel": "implements"
        },
        {
          "to": "adr-0002-cell-driver",
          "rel": "implements"
        },
        {
          "to": "adr-0003-harness-profile",
          "rel": "implements"
        },
        {
          "to": "adr-0006-results-data-model",
          "rel": "implements"
        },
        {
          "to": "adr-0007-run-engine",
          "rel": "implements"
        },
        {
          "to": "adr-0010-untrusted-cell-output",
          "rel": "implements"
        },
        {
          "to": "adr-0012-proportionate-security",
          "rel": "implements"
        }
      ],
      "diagrams": [],
      "sourceSha256": "68d21210315ba5735d300080ab513ee18935a94a25de40b28d64f82709a994a6"
    },
    {
      "id": "design-phase2-copilot-profile",
      "path": "docs/design/phase2-copilot-profile.md",
      "title": "Design: the Copilot harness profile (phase 2, to-do rows 1-5)",
      "type": "design",
      "status": "draft",
      "owner": "@timianmalloo",
      "phase": "Phase 2 · smoke on all harnesses (wave 1: the Copilot-vs-Codex capability)",
      "reviewBy": "2027-03-24",
      "reviewSuggested": [
        {
          "by": "adr-0006-results-data-model",
          "on": "2026-10-03",
          "reason": "Proposed amendment 2026-10-03 (ADR-0014/0015, arch-evaluation-campaign): cell grain by arm, per-turn prompt_sent, archive_files snapshot key part, job terminated after the last turn; council gate pending"
        }
      ],
      "summary": "How a Copilot cell runs: a data-only profile (bench/profiles/copilot.yaml) whose templated command launches the pinned native binary @github/copilot-win32-x64 1.0.89-1 by path with no ACP adapter; an ACP session/set_model before the prompt (driver.py changes); a reader over the per-cell events.jsonl that writes per-report model_calls rows under the ADR-0006 grain amendment (R-26) and records each tool call's outcome_code, so the pack-on hook denial measured on revision 92 (R-27) is visible. Also HB-PRE-002 for Copilot's instruction files, the US-9 scan, the US-9..US-14 promise-to-test table, and the Leader's capture and scrub procedure. Revision 3, after the design gate and rulings R-12..R-28.",
      "tags": [
        "benchmark",
        "harness",
        "copilot",
        "profile",
        "acp",
        "telemetry",
        "isolation"
      ],
      "links": [
        {
          "to": "design-phase1-walking-skeleton",
          "rel": "refines"
        },
        {
          "to": "arch-harness-bench",
          "rel": "implements"
        },
        {
          "to": "spec-harness-bench",
          "rel": "implements"
        },
        {
          "to": "adr-0003-harness-profile",
          "rel": "implements"
        },
        {
          "to": "adr-0006-results-data-model",
          "rel": "refines"
        },
        {
          "to": "adr-0008-telemetry",
          "rel": "implements"
        },
        {
          "to": "adr-0002-cell-driver",
          "rel": "depends-on"
        },
        {
          "to": "note-spike-isolation-permissions",
          "rel": "depends-on"
        },
        {
          "to": "note-spike-runner-path",
          "rel": "depends-on"
        },
        {
          "to": "note-20260923-token-source",
          "rel": "relates-to"
        },
        {
          "to": "rulings-register",
          "rel": "depends-on"
        },
        {
          "to": "coordination-finish-harness-bench",
          "rel": "relates-to"
        }
      ],
      "diagrams": [],
      "sourceSha256": "912760bbb9d49ad2b5b33db54a676aa0e8d0edc1b8e32fc7789965ec8f5e4e5b"
    },
    {
      "id": "design-phase2-scripted-user",
      "path": "docs/design/phase2-scripted-user.md",
      "title": "Design: the scripted user for scenario 1 (phase 2, row 8)",
      "type": "design",
      "status": "draft",
      "owner": "@timianmalloo",
      "phase": "Phase 2 · smoke on all harnesses (wave 2: row 8, the scripted user)",
      "reviewBy": "2027-03-25",
      "reviewSuggested": [],
      "summary": "The scenario-1 scripted user per R-37 and R-39: a bench-owned MCP server exposing one tool, ask_user(question) -> reply, passed in ACP session/new mcpServers, one prompt per cell; a deterministic matcher (exact, then five normalisation rules; a miss gets exactly \"Decide and state your assumption.\"); a per-call log with \"no question asked\" for zero calls; the \"scripted user\" allowlist class; the seams for W2-USER-W. Revision 2 after spike S-04: stdio works on Claude Code and Codex (Verified); Copilot 1.0.89-1 rejects client stdio servers (a decision request, with HTTP and launch-config variants written); the rule table scores precision 1.0 and recall 6/17 on the held-out set (0/11 on paraphrases); the S-04 threshold is set (regression floor met; confidence T = 0.80 on paraphrase recall not met). AI Systems Engineer: CLEAR WITH CONDITIONS, conditions applied.",
      "tags": [
        "benchmark",
        "scenario-1",
        "scripted-user",
        "mcp",
        "acp",
        "matcher",
        "clarification"
      ],
      "links": [
        {
          "to": "spec-harness-bench",
          "rel": "implements"
        },
        {
          "to": "arch-harness-bench",
          "rel": "implements"
        },
        {
          "to": "adr-0002-cell-driver",
          "rel": "refines"
        },
        {
          "to": "adr-0004-static-permissions",
          "rel": "depends-on"
        },
        {
          "to": "adr-0009-model-gateway",
          "rel": "depends-on"
        },
        {
          "to": "design-phase1-walking-skeleton",
          "rel": "refines"
        },
        {
          "to": "note-spike-s04-scripted-user",
          "rel": "depends-on"
        },
        {
          "to": "rulings-register",
          "rel": "depends-on"
        },
        {
          "to": "coordination-finish-harness-bench",
          "rel": "relates-to"
        }
      ],
      "diagrams": [],
      "sourceSha256": "e462b14bdb2f5c2c2d2113ac98c74dba0db79007045d9dec1ac4c73d0e2c312e"
    },
    {
      "id": "design-phase2-stop-decisions",
      "path": "docs/design/phase2-stop-decisions.md",
      "title": "Design: run-level stop, decision requests with a timeout, and the circuit breaker (phase 2, row 10)",
      "type": "design",
      "status": "draft",
      "owner": "@timianmalloo",
      "phase": "Phase 2 · smoke on all harnesses (wave 2: row 10, W2-STOP)",
      "reviewBy": "2027-03-25",
      "reviewSuggested": [
        {
          "by": "adr-0006-results-data-model",
          "on": "2026-10-03",
          "reason": "Proposed amendment 2026-10-03 (ADR-0014/0015, arch-evaluation-campaign): cell grain by arm, per-turn prompt_sent, archive_files snapshot key part, job terminated after the last turn; council gate pending"
        },
        {
          "by": "adr-0007-run-engine",
          "on": "2026-10-03",
          "reason": "Proposed amendment 2026-10-03 (ADR-0014/0015, arch-evaluation-campaign): cell grain by arm, per-turn prompt_sent, archive_files snapshot key part, job terminated after the last turn; council gate pending"
        }
      ],
      "summary": "How a run stops on purpose and how it asks for, and times out, a decision. `bench stop` and `bench answer` write apply-once control files that the engine applies on its own thread. A stop sends ACP session/cancel, closes stdin, waits a profile grace of at most 10 s, then terminates the Job Object, so every running cell is `stopped` within 30 s (R-21, UXA-10), and a `run.stopped` fact is recorded. Three decision kinds (blocked cell, qualification gap, spend cap) pause launching; each request is resolved exactly once; the plan's decision_timeout applies the default. The built breaker gets its acceptance criterion and falsifying reverts. The grace is a TLC-checked refinement of the terminate step (spike: 22 of 22 variants rejected; the US-44 bounds pass). Revision 2, after the three-lens gate.",
      "tags": [
        "benchmark",
        "run-engine",
        "stop",
        "decisions",
        "circuit-breaker",
        "tla",
        "acp",
        "lifecycle"
      ],
      "links": [
        {
          "to": "design-phase1-walking-skeleton",
          "rel": "refines"
        },
        {
          "to": "design-run-lifecycle-model",
          "rel": "refines"
        },
        {
          "to": "spec-harness-bench",
          "rel": "implements"
        },
        {
          "to": "arch-harness-bench",
          "rel": "implements"
        },
        {
          "to": "adr-0007-run-engine",
          "rel": "implements"
        },
        {
          "to": "adr-0006-results-data-model",
          "rel": "depends-on"
        },
        {
          "to": "adr-0002-cell-driver",
          "rel": "depends-on"
        },
        {
          "to": "adr-0004-static-permissions",
          "rel": "relates-to"
        },
        {
          "to": "rulings-register",
          "rel": "depends-on"
        },
        {
          "to": "coordination-finish-harness-bench",
          "rel": "relates-to"
        },
        {
          "to": "note-20260925-stop-decision-calls",
          "rel": "relates-to"
        }
      ],
      "diagrams": [],
      "sourceSha256": "773ef54b17f8554995fd374ee583c3cc7512ec362879c2954e5902850a3c1665"
    },
    {
      "id": "design-phase3-cost",
      "path": "docs/design/phase3-cost.md",
      "title": "Design: the cell-grain cost and efficiency metrics (phase 3, row 16, W3-COST phase 2)",
      "type": "design",
      "status": "draft",
      "owner": "@timianmalloo",
      "phase": "Phase 3 · grading and judges (wave 3: row 16, W3-COST)",
      "reviewBy": "2027-03-25",
      "reviewSuggested": [
        {
          "by": "adr-0006-results-data-model",
          "on": "2026-10-03",
          "reason": "Proposed amendment 2026-10-03 (ADR-0014/0015, arch-evaluation-campaign): cell grain by arm, per-turn prompt_sent, archive_files snapshot key part, job terminated after the last turn; council gate pending"
        }
      ],
      "summary": "Seam C-1: `grade/runner.py`'s inline `_cost` (cost_usd only) moves verbatim into `grade/cost.py`'s `grade_cell(inp)`, registered in `runner.GRADERS[\"cost\"]`. Six cell-grain metrics are decided: cost_usd (unchanged) plus five new ones -- tokens_per_minute, output_tokens_per_turn, cache_hit_ratio, cache_write_amplification, context_growth (peak) and compactions -- each defined only from `normalize.totals` and the existing view measures `views.busy_ms`, `views.calls_per_cell` and `views.model_call` (DM7: one definition per quantity). `compactions` has no recorded signal on any harness today, so it is unconditionally NA, never 0 (US-27).",
      "tags": [
        "benchmark",
        "grading",
        "metrics",
        "cost",
        "tokens",
        "cache",
        "determinism"
      ],
      "links": [
        {
          "to": "design-phase3-graders",
          "rel": "refines"
        },
        {
          "to": "spec-harness-bench",
          "rel": "implements"
        },
        {
          "to": "arch-harness-bench",
          "rel": "implements"
        },
        {
          "to": "adr-0006-results-data-model",
          "rel": "depends-on"
        },
        {
          "to": "adr-0008-telemetry",
          "rel": "depends-on"
        }
      ],
      "diagrams": [],
      "sourceSha256": "0716758a182336abcbbbcb7cc6e3f07676c4f8ecef1939641c02ab061d6e43c1"
    },
    {
      "id": "design-phase3-gateway-judges",
      "path": "docs/design/phase3-gateway-judges.md",
      "title": "Design: the model gateway and the two judges (phase 3, row 17)",
      "type": "design",
      "status": "draft",
      "owner": "@timianmalloo",
      "phase": "Phase 3 · wave 3 (row 17: the gateway, the judges, calibration; built by W3-GW-I)",
      "reviewBy": "2027-03-25",
      "reviewSuggested": [
        {
          "by": "adr-0006-results-data-model",
          "on": "2026-10-03",
          "reason": "Proposed amendment 2026-10-03 (ADR-0014/0015, arch-evaluation-campaign): cell grain by arm, per-turn prompt_sent, archive_files snapshot key part, job terminated after the last turn; council gate pending"
        },
        {
          "by": "adr-0013-native-cells",
          "on": "2026-10-03",
          "reason": "Proposed amendment 2026-10-03 (ADR-0014/0015, arch-evaluation-campaign): cell grain by arm, per-turn prompt_sent, archive_files snapshot key part, job terminated after the last turn; council gate pending"
        }
      ],
      "summary": "Row 17 per R-58 and R-59, driven by spike GW-H and revised through a five-persona gate. The gateway calls judges through the pinned headless CLIs, from call folders under the cells root, only under bench grade --allow-model-calls and never while any run is live. The Anthropic judge is claude-fable-5-1 (served on 2.1.282, text output, 0 tool events). The OpenAI judge gpt-6-sol is not qualified and is never spawned: Codex 0.156 keeps its code-mode exec tool (DR-GW-1). Requests are scrubbed, scanned, egress-checked and sent on stdin; answers are schema-validated; verdicts live in a request-keyed memo store whose hits are checked against the storing ledger. Calibration is one human label per (artifact, rubric item), set-checked before any verdict. The gate passed in two rounds, with every veto cleared by its holder. Five Owner decisions are open.",
      "tags": [
        "benchmark",
        "gateway",
        "judges",
        "calibration",
        "kappa",
        "blinding",
        "US-26",
        "US-35",
        "US-46",
        "US-47",
        "R-58",
        "R-59"
      ],
      "links": [
        {
          "to": "spec-harness-bench",
          "rel": "implements"
        },
        {
          "to": "arch-harness-bench",
          "rel": "implements"
        },
        {
          "to": "adr-0009-model-gateway",
          "rel": "refines"
        },
        {
          "to": "adr-0006-results-data-model",
          "rel": "depends-on"
        },
        {
          "to": "adr-0005-egress-control",
          "rel": "depends-on"
        },
        {
          "to": "adr-0013-native-cells",
          "rel": "depends-on"
        },
        {
          "to": "adr-0012-proportionate-security",
          "rel": "depends-on"
        },
        {
          "to": "adr-0003-harness-profile",
          "rel": "depends-on"
        },
        {
          "to": "design-phase1-walking-skeleton",
          "rel": "refines"
        },
        {
          "to": "note-spike-gw-headless",
          "rel": "depends-on"
        },
        {
          "to": "rulings-register",
          "rel": "depends-on"
        },
        {
          "to": "coordination-finish-harness-bench",
          "rel": "relates-to"
        }
      ],
      "diagrams": [],
      "sourceSha256": "971894a3f483971f8de28cdf8fb4839d6035caa77b8088c2dd92430ee885fc61"
    },
    {
      "id": "design-phase3-graders",
      "path": "docs/design/phase3-graders.md",
      "title": "Design: full graders — per-cell grader input, dispatch by task graders, catalog 0.4 versioning, and the byte-identity gate (phase 3, row 16)",
      "type": "design",
      "status": "draft",
      "owner": "@timianmalloo",
      "phase": "Phase 3 · grading and judges (wave 3: row 16, W3-GRADE-D)",
      "reviewBy": "2027-03-25",
      "reviewSuggested": [
        {
          "by": "adr-0006-results-data-model",
          "on": "2026-10-03",
          "reason": "Proposed amendment 2026-10-03 (ADR-0014/0015, arch-evaluation-campaign): cell grain by arm, per-turn prompt_sent, archive_files snapshot key part, job terminated after the last turn; council gate pending"
        },
        {
          "by": "adr-0013-native-cells",
          "on": "2026-10-03",
          "reason": "Proposed amendment 2026-10-03 (ADR-0014/0015, arch-evaluation-campaign): cell grain by arm, per-turn prompt_sent, archive_files snapshot key part, job terminated after the last turn; council gate pending"
        }
      ],
      "summary": "Row 16: every metric the ready tasks A1, C1, D1 and E6 name through their `graders:` lists gets a definition, an oracle rung (US-25), its NA reasons (US-27), an additivity class and a fixture with a stated expected value, cut from runs/row15-d1-1, runs/a1-capture-1 or the C1/E6 reference solutions. A frozen per-cell `CellInput` replaces `grade(run_dir, task_dir)`. A registry dispatch by the task's `graders`, with a completeness check before `grading.completed`, replaces the fixed `METRICS` tuple. Catalog `0.4.dev` is a probe version (R-59). `catalog_hash` and tool versions ride on `grading.started`. The US-4 control fails on a score change or a catalog-hash change without a version bump. The four gate tasks are frozen. The byte-identity gate compares `views.export` bytes of two asserted passes, never ledger bytes. Revision 2 clears the Test Architect's and the D&P Architect's vetoes.",
      "tags": [
        "benchmark",
        "grading",
        "metrics",
        "catalog",
        "versioning",
        "na",
        "determinism",
        "mutation",
        "drift",
        "clarification"
      ],
      "links": [
        {
          "to": "spec-harness-bench",
          "rel": "implements"
        },
        {
          "to": "arch-harness-bench",
          "rel": "implements"
        },
        {
          "to": "adr-0006-results-data-model",
          "rel": "depends-on"
        },
        {
          "to": "adr-0008-telemetry",
          "rel": "depends-on"
        },
        {
          "to": "adr-0009-model-gateway",
          "rel": "relates-to"
        },
        {
          "to": "adr-0010-untrusted-cell-output",
          "rel": "depends-on"
        },
        {
          "to": "adr-0013-native-cells",
          "rel": "depends-on"
        },
        {
          "to": "design-phase1-walking-skeleton",
          "rel": "refines"
        },
        {
          "to": "design-phase2-scripted-user",
          "rel": "depends-on"
        },
        {
          "to": "note-spike-s04-scripted-user",
          "rel": "relates-to"
        },
        {
          "to": "rulings-register",
          "rel": "depends-on"
        },
        {
          "to": "coordination-finish-harness-bench",
          "rel": "relates-to"
        },
        {
          "to": "proposal-cross-harness-benchmarking",
          "rel": "refines"
        }
      ],
      "diagrams": [],
      "sourceSha256": "7ab3f541781705af3004e9567e0cbaba868c4965b2464c579eeb3c470d58d914"
    },
    {
      "id": "design-phase4-report",
      "path": "docs/design/phase4-report.md",
      "title": "Design: the full HTML report and its two AI summaries (phase 4, wave 4 row 20)",
      "type": "design",
      "status": "draft",
      "owner": "@timianmalloo",
      "phase": "Phase 4 · statistics and full report (wave 4: row 20)",
      "reviewBy": "2027-03-28",
      "reviewSuggested": [],
      "summary": "Row 20: the eleven-section, self-contained, offline HTML report (US-40, US-41, US-43, US-51) and the two AI summaries (US-42). The report is a pure projection of the views and the statistics board, pre-rendered as HTML and inline SVG, with one hashed script for sort, filters and popovers under a CSP that blocks every other script. The only new stored fact is the summary record. The design fixes the archetype, tokens (colour-blind-safe categorical, PuOr diverging, viridis heatmap, all contrast-measured), every section's states, the summaries' claim-check contract, the EGRESS s2 sequencing, the test plan for UIA-1..15, and ten red-first slices (R0-R9). Nine decision requests (DR-R-1..9) carry recommended defaults. Mockup: docs/design/mockups/phase4-report.html.",
      "tags": [
        "benchmark",
        "report",
        "ui",
        "accessibility",
        "summaries",
        "egress",
        "csp",
        "offline",
        "uncertainty"
      ],
      "links": [
        {
          "to": "spec-harness-bench",
          "rel": "implements"
        },
        {
          "to": "arch-harness-bench",
          "rel": "implements"
        },
        {
          "to": "design-phase4-statistics",
          "rel": "depends-on"
        },
        {
          "to": "design-phase3-gateway-judges",
          "rel": "depends-on"
        },
        {
          "to": "adr-0005-egress-control",
          "rel": "depends-on"
        },
        {
          "to": "adr-0009-model-gateway",
          "rel": "depends-on"
        },
        {
          "to": "adr-0012-proportionate-security",
          "rel": "depends-on"
        },
        {
          "to": "coordination-finish-harness-bench",
          "rel": "relates-to"
        },
        {
          "to": "defect-classes",
          "rel": "relates-to"
        }
      ],
      "diagrams": [],
      "sourceSha256": "69f3c12182bb3b4693eab42523c8be331434af46d16d3aaab6177108ba41ac06"
    },
    {
      "id": "design-phase4-statistics",
      "path": "docs/design/phase4-statistics.md",
      "title": "Design: statistics — composites, bootstrap intervals, ranking with ties, pack effect and run comparison (phase 4, wave 4 row 19)",
      "type": "design",
      "status": "draft",
      "owner": "@timianmalloo",
      "phase": "Phase 4 · statistics and full report (wave 4: row 19)",
      "reviewBy": "2027-03-27",
      "reviewSuggested": [
        {
          "by": "adr-0006-results-data-model",
          "on": "2026-10-03",
          "reason": "Proposed amendment 2026-10-03 (ADR-0014/0015, arch-evaluation-campaign): cell grain by arm, per-turn prompt_sent, archive_files snapshot key part, job terminated after the last turn; council gate pending"
        }
      ],
      "summary": "Row 19 (S-08f composites + S-11 statistics): normalisation by catalog anchors and the correctness-gated composite at the cell grain; a two-stage (tasks, then repetitions) percentile bootstrap, 95%, at least 2,000 resamples, keyed per quantity from a recorded seed so the same results and seed give identical intervals; ranking where overlapping intervals share a tier and a pass@1 interval entirely below another can never rank above it (US-36, C1); the pack effect on minus off per area and combo with E1-E3 excluded and `no detectable effect` when the interval touches zero (US-37); the two-run comparison with its refusal rule (US-52). Everything is derived at read time; nothing new is stored. Six decision requests (DR-S-1..6) carry recommended defaults.",
      "tags": [
        "benchmark",
        "statistics",
        "bootstrap",
        "ranking",
        "pack-effect",
        "composites",
        "normalisation",
        "determinism"
      ],
      "links": [
        {
          "to": "spec-harness-bench",
          "rel": "implements"
        },
        {
          "to": "arch-harness-bench",
          "rel": "implements"
        },
        {
          "to": "adr-0006-results-data-model",
          "rel": "depends-on"
        },
        {
          "to": "design-phase3-graders",
          "rel": "depends-on"
        },
        {
          "to": "design-phase3-cost",
          "rel": "relates-to"
        },
        {
          "to": "design-phase3-gateway-judges",
          "rel": "relates-to"
        },
        {
          "to": "rulings-register",
          "rel": "depends-on"
        },
        {
          "to": "coordination-finish-harness-bench",
          "rel": "relates-to"
        },
        {
          "to": "proposal-cross-harness-benchmarking",
          "rel": "refines"
        }
      ],
      "diagrams": [],
      "sourceSha256": "2d36330dab267baa41719ca2e34620f388224060ee3ec833e6a9b923d8a21077"
    },
    {
      "id": "design-run-lifecycle-model",
      "path": "docs/design/run-lifecycle-model.md",
      "title": "Design: run lifecycle model (models/run_lifecycle.tla)",
      "type": "design",
      "status": "draft",
      "owner": "@timianmalloo",
      "phase": "Phase 1 · walking skeleton (S-13)",
      "reviewBy": "2027-03-22",
      "reviewSuggested": [
        {
          "by": "adr-0006-results-data-model",
          "on": "2026-09-24",
          "reason": "Amendment 1: model_calls grain re-declared per native usage report with requests and model in the key; tool_calls.outcome_code (R-26, R-27)"
        },
        {
          "by": "adr-0007-run-engine",
          "on": "2026-10-03",
          "reason": "Proposed amendment 2026-10-03 (ADR-0014/0015, arch-evaluation-campaign): cell grain by arm, per-turn prompt_sent, archive_files snapshot key part, job terminated after the last turn; council gate pending"
        },
        {
          "by": "adr-0013-native-cells",
          "on": "2026-10-03",
          "reason": "Proposed amendment 2026-10-03 (ADR-0014/0015, arch-evaluation-campaign): cell grain by arm, per-turn prompt_sent, archive_files snapshot key part, job terminated after the last turn; council gate pending"
        }
      ],
      "summary": "The TLA+ model of one run's lifecycle, the proof obligation the run engine is built against (US-44). TLC checks 16 safety invariants at the US-44 bounds (3 cells, parallelism 2, 1 engine crash) and at small bounds with `bench grade` contending, grading mutual exclusion at 2 passes, and 5 liveness properties at 1 cell; each of 22 seeded-bug variants is rejected by its own target checked alone, and two witnesses show that every cell can finish and the R-21 cancel grace is reachable. A mapping table binds every model action to the engine's ledger events, and a conformance test keeps the two in step.",
      "tags": [
        "benchmark",
        "tla",
        "model-checking",
        "runner",
        "lifecycle"
      ],
      "links": [
        {
          "to": "arch-harness-bench",
          "rel": "implements"
        },
        {
          "to": "adr-0007-run-engine",
          "rel": "implements"
        },
        {
          "to": "adr-0006-results-data-model",
          "rel": "depends-on"
        },
        {
          "to": "adr-0013-native-cells",
          "rel": "implements"
        },
        {
          "to": "spec-harness-bench",
          "rel": "implements"
        }
      ],
      "diagrams": [],
      "sourceSha256": "a4358621c550c308c63a8a6a6af58a6c34dd8b473851bee33bdcf425a2545b5d"
    },
    {
      "id": "audit-log",
      "path": "docs/audit/audit-log.md",
      "title": "Audit & Change Log",
      "type": "doc",
      "status": "accepted",
      "owner": "@timianmalloo",
      "phase": "",
      "reviewBy": "2027-09-23",
      "reviewSuggested": [],
      "summary": "The durable, committed history of what was prompted, done, and decided in this repository, so work compounds across sessions. The two JSONL files are the source of truth; audit-data.js and index.html are derived projections.",
      "tags": [
        "audit",
        "history",
        "change-log",
        "project-memory"
      ],
      "links": [
        {
          "to": "proposal-cross-harness-benchmarking",
          "rel": "relates-to"
        }
      ],
      "diagrams": [],
      "sourceSha256": "b278432234edb1a4ac1320f18bc276401296d16169fd21a648088a947e401364"
    },
    {
      "id": "coordination-eval-wave2-e1-overnight-2026-10-05",
      "path": "docs/coordination/eval-wave2-e1/overnight-2026-10-05.md",
      "title": "Overnight run 2026-10-04/05: Leader leader-e1e4 epoch 17 (E1 build joins, E2 starts)",
      "type": "doc",
      "status": "proposed",
      "owner": "@timianmalloo",
      "phase": "",
      "reviewBy": "2026-10-12",
      "reviewSuggested": [],
      "summary": "The overnight Leader run, epoch 17, 2026-10-04 16:56 to 2026-10-05 07:00 local. Phase 1 joined and pushed. Every E1 build track was built and joined, 18 tracks in 7 pushed batches (origin/main a6e37b76 -> `17e22e00` plus this report). X-INT, the E1 end-to-end turn, was built and joined, and its E1 E2E list is green (24 passed, 7 strict xfail). One operator action unblocks the external harnesses: the earlier session left an applied mutant in the primary's views.py, which froze main in the primary and the external runner, so the E1 critical path ran on Sonnet under R-105. Rulings R-104, R-105 and R-106. The gate ring was measured at 77 to 81 min. The operator queue below has a recommended default for each item.",
      "tags": [],
      "links": [
        {
          "to": "coordination-eval-wave2-e1-briefs",
          "rel": "relates-to"
        },
        {
          "to": "coordination-eval-campaign",
          "rel": "implements"
        },
        {
          "to": "rulings-register",
          "rel": "depends-on"
        }
      ],
      "diagrams": [],
      "sourceSha256": "64b32caa250a15cfef6c43ea02697773c0c0ce22357697b068345e6f0ea48cab"
    },
    {
      "id": "coordination-finish-harness-bench-run",
      "path": "docs/coordination/coordination-finish-harness-bench-run.md",
      "title": "Run record - coordination-finish-harness-bench",
      "type": "doc",
      "status": "draft",
      "owner": "@timianmalloo",
      "phase": "Phase 2 · smoke on all harnesses",
      "reviewBy": "2026-10-08",
      "reviewSuggested": [],
      "summary": "What happened when the finish-harness-bench plan was executed: qualifications, gate rounds, dispatches, slice joins, capture windows and planned against actual per track.",
      "tags": [
        "coordination",
        "run-record",
        "planned-vs-actual"
      ],
      "links": [
        {
          "to": "coordination-finish-harness-bench",
          "rel": "relates-to"
        }
      ],
      "diagrams": [],
      "sourceSha256": "33c51968ea560ff572c8b99674c1e4eb60dccd23df3cad5d52fda84f3819b454"
    },
    {
      "id": "coordination-phase1-finish-run",
      "path": "docs/coordination/coordination-phase1-finish-run.md",
      "title": "Run record - coordination-phase1-finish",
      "type": "doc",
      "status": "draft",
      "owner": "@timianmalloo",
      "phase": "Phase 1 · walking skeleton",
      "reviewBy": "2026-10-08",
      "reviewSuggested": [],
      "summary": "What happened when the phase-1 finish plan was executed: the measured qualification of grok and agy (both failed; ruling R-4 moved the tracks to Claude Code), the mutation-tool probes, the hardened checker's findings, and planned against actual time for each track.",
      "tags": [
        "coordination",
        "run-record",
        "planned-vs-actual"
      ],
      "links": [
        {
          "to": "coordination-phase1-finish",
          "rel": "relates-to"
        }
      ],
      "diagrams": [],
      "sourceSha256": "93fa6763587ff34106f283575074265c0bbb69839affc718ca1c4a79a8b530e3"
    },
    {
      "id": "coordinator-log",
      "path": "docs/coordination/coordinator-log.md",
      "title": "Coordinator hand-back log (index; one file per session)",
      "type": "doc",
      "status": "active",
      "owner": "@timianmalloo",
      "phase": "",
      "reviewBy": "2026-11-05",
      "reviewSuggested": [],
      "summary": "Where Coordinator hand-back entries live. From #29 each session writes its own file, docs/coordination/coordinator-log/c<NN>.md, so concurrent sessions never share an append point (the register merge class is JSONL-only, measured 2026-10-05; see .agents/artifacts.yml). Entries #1-#28 live in docs/coordination/eval-wave2-e1/README.md section 8.",
      "tags": [
        "coordination",
        "register"
      ],
      "links": [
        {
          "to": "coordination-eval-wave2-e1-briefs",
          "rel": "relates-to"
        },
        {
          "to": "coordination-eval-wave2-e234-briefs",
          "rel": "relates-to"
        }
      ],
      "diagrams": [],
      "sourceSha256": "acd8498fd932679d67586f51a0b1c47183b8e3d7a3cca26d3dfd3685e841e2a4"
    },
    {
      "id": "coordinator-log-c29",
      "path": "docs/coordination/coordinator-log/c29.md",
      "title": "Coordinator #29 hand-back (2026-10-05): the E2-E4 coordination plan",
      "type": "doc",
      "status": "accepted",
      "owner": "@timianmalloo",
      "phase": "",
      "reviewBy": "2026-11-05",
      "reviewSuggested": [],
      "summary": "Coordinator #29 wrote the E2-E4 coordination plan (Stages 2-9 of /prepare-for-coordination) on base 839d0f4a for Leader epoch 18, and registered six candidate defect classes and six instances. No request was open; no Owner decision is needed before the first dispatch.",
      "tags": [
        "coordination",
        "coordinator-log"
      ],
      "links": [
        {
          "to": "coordinator-log",
          "rel": "relates-to"
        },
        {
          "to": "coordination-e2e4",
          "rel": "relates-to"
        },
        {
          "to": "defect-classes",
          "rel": "relates-to"
        }
      ],
      "diagrams": [],
      "sourceSha256": "b8b0c87af6daacf7b5a810c17d3a44712a5db00de4b323f12c4ceddd3b709dd1"
    },
    {
      "id": "coordinator-log-c30",
      "path": "docs/coordination/coordinator-log/c30.md",
      "title": "Coordinator #30 hand-back (2026-10-05): the T0 compiles for E2-E4",
      "type": "doc",
      "status": "accepted",
      "owner": "@timianmalloo",
      "phase": "",
      "reviewBy": "2026-11-05",
      "reviewSuggested": [],
      "summary": "Coordinator #30 ran the plan's order-of-operations row 4 on integrate/e2e4-18 at 37ec0585: J1a recompiled (Codex, 3,300 s), A3a and LGa compiled (Agy), the X-I5, X-INTF and X-PACK briefs written and compiled, X-I-S2's authoring compiled. Every compilation is dispatchable, carries the R-104 worker gate with the eight-file guard list, and names W0 rev 6.10 and the integration head.",
      "tags": [
        "coordination",
        "coordinator-log",
        "compile"
      ],
      "links": [
        {
          "to": "coordinator-log",
          "rel": "relates-to"
        },
        {
          "to": "coordination-e2e4",
          "rel": "relates-to"
        },
        {
          "to": "brief-eval-x-i5",
          "rel": "relates-to"
        },
        {
          "to": "brief-eval-x-intf",
          "rel": "relates-to"
        },
        {
          "to": "brief-eval-x-pack",
          "rel": "relates-to"
        }
      ],
      "diagrams": [],
      "sourceSha256": "8dd901d27c65156286721259833e51e9a39b69901620326ce3ff07f8c81f0474"
    },
    {
      "id": "coordinator-log-c31",
      "path": "docs/coordination/coordinator-log/c31.md",
      "title": "Coordinator #31 hand-back (2026-10-05): C-W0, W0 rev 6.11",
      "type": "doc",
      "status": "accepted",
      "owner": "@timianmalloo",
      "phase": "",
      "reviewBy": "2026-11-05",
      "reviewSuggested": [],
      "summary": "Coordinator #31 did C-W0 of the E2-E4 plan on base 37ec0585: W0 rev 6.11 (R-106's stamp key set quoted in section 6, the R-106 c7 reader sweep with two findings, the shared-value rule, the X-K2a script-only split, the plan's section 13 rows, HB-GRD-007 to X-C), W1-D Amendment 1, W1-C SEC 6 confirmed, and GUARD-A's control as E1 README sections 2 and 3. No request was open; no Owner decision is needed.",
      "tags": [
        "coordination",
        "coordinator-log"
      ],
      "links": [
        {
          "to": "coordinator-log",
          "rel": "relates-to"
        },
        {
          "to": "coordination-e2e4",
          "rel": "relates-to"
        },
        {
          "to": "design-eval-seam-contracts",
          "rel": "relates-to"
        },
        {
          "to": "design-eval-identity",
          "rel": "relates-to"
        },
        {
          "to": "coordination-eval-wave2-e1-briefs",
          "rel": "relates-to"
        },
        {
          "to": "defect-classes",
          "rel": "relates-to"
        }
      ],
      "diagrams": [],
      "sourceSha256": "ca3b9e47c27de68058d5f7a03d2a61e8ac5d16b2cadf23255d808993bcaca84d"
    },
    {
      "id": "coordinator-log-c32",
      "path": "docs/coordination/coordinator-log/c32.md",
      "title": "Coordinator #32 hand-back (2026-10-05): four seam rulings, the wave-2 compiles, the register",
      "type": "doc",
      "status": "accepted",
      "owner": "@timianmalloo",
      "phase": "",
      "reviewBy": "2026-11-05",
      "reviewSuggested": [],
      "summary": "Coordinator #32, on base a27d79fe (integrate/e2e4-18 after the X-I5 join), resolved the four overdue seam requests by accepting each fallback (one with conditions, one with its owner corrected by the Leader), compiled X-LGb (Agy), X-K2a (Grok) and a recompiled X-INTF that folds in the R-106 c7 loop-back F-1/F-2, made the register edits #31 owed plus three new candidates (PIN-B, IDN-A, LOCK-A) and a REG-C pack-side sibling, and fixed the plan's readiness erratum.",
      "tags": [
        "coordination",
        "coordinator-log",
        "compile",
        "seam-requests"
      ],
      "links": [
        {
          "to": "coordinator-log",
          "rel": "relates-to"
        },
        {
          "to": "coordination-e2e4",
          "rel": "relates-to"
        },
        {
          "to": "brief-eval-x-intf",
          "rel": "relates-to"
        },
        {
          "to": "brief-eval-x-lg",
          "rel": "relates-to"
        },
        {
          "to": "brief-eval-x-k2",
          "rel": "relates-to"
        },
        {
          "to": "design-eval-seam-contracts",
          "rel": "relates-to"
        },
        {
          "to": "defect-classes",
          "rel": "relates-to"
        }
      ],
      "diagrams": [],
      "sourceSha256": "b31fe9eb302b96b0f7a38868f407c9a59f955f50e20a9434496bcdc1d796026a"
    },
    {
      "id": "coordinator-log-c33",
      "path": "docs/coordination/coordinator-log/c33.md",
      "title": "Coordinator #33 hand-back (2026-10-05): the X-G3 and X-J1b compiles, the register",
      "type": "doc",
      "status": "accepted",
      "owner": "@timianmalloo",
      "phase": "",
      "reviewBy": "2026-11-05",
      "reviewSuggested": [],
      "summary": "Coordinator #33, on base bcd35532 (integrate/e2e4-18 after the LGa and Coordinator #32 joins), compiled X-G3 (Grok, on X-A3a's landed names, with an XPORT-A fallback before the first prompt) and X-J1b (Codex, K4(2)-K4(4) on J1a's landed names, with #32's snapshot_cell conditions). Both compiles carry the same session string as their contracts (IDN-A). It completed X-G3's owned paths from W1-G, ruled the 0.7 release label the Leader's, and registered FPR-A plus instances of XPORT-A, LOCK-A and GATE-A.",
      "tags": [
        "coordination",
        "coordinator-log",
        "compile"
      ],
      "links": [
        {
          "to": "coordinator-log",
          "rel": "relates-to"
        },
        {
          "to": "coordination-e2e4",
          "rel": "relates-to"
        },
        {
          "to": "brief-eval-x-g3",
          "rel": "relates-to"
        },
        {
          "to": "brief-eval-x-j1",
          "rel": "relates-to"
        },
        {
          "to": "design-eval-catalog-0-7",
          "rel": "relates-to"
        },
        {
          "to": "design-eval-multi-turn",
          "rel": "relates-to"
        },
        {
          "to": "defect-classes",
          "rel": "relates-to"
        }
      ],
      "diagrams": [],
      "sourceSha256": "7b94008b6236d65dafbeeb8526f12bff06d57904bf9f0c467001367aa233e282"
    },
    {
      "id": "coordinator-log-c34",
      "path": "docs/coordination/coordinator-log/c34.md",
      "title": "Coordinator #34 hand-back (2026-10-05): the X-LGc, X-A3b and X-J2b compiles, pass_rule_problems, the register",
      "type": "doc",
      "status": "accepted",
      "owner": "@timianmalloo",
      "phase": "",
      "reviewBy": "2026-11-05",
      "reviewSuggested": [],
      "summary": "Coordinator #34, on base 0d4a291a (integrate/e2e4-18 after the A3a and Coordinator #33 joins), compiled three Agy turns: X-LGc (diffstats and the HB-RDY-009 frozen-value check in contract_failures), X-A3b (the pack-regression ring, three-arm plans, the EV-15 ring-hash refusal with one pre-granted errors.py row) and X-J2b (rework.grade, the variant reader, discriminate admitting a turns task; red-only on the engine leg by plan). It confirmed the plan's readiness.py assume by reading the file, named X-TE9 as the owner of readiness.pass_rule_problems in the next plan revision, and added SERVE-A's measured root cause (DRIFT) and an EOL-A instance to the register.",
      "tags": [
        "coordination",
        "coordinator-log",
        "compile"
      ],
      "links": [
        {
          "to": "coordinator-log",
          "rel": "relates-to"
        },
        {
          "to": "coordination-e2e4",
          "rel": "relates-to"
        },
        {
          "to": "brief-eval-x-lg",
          "rel": "relates-to"
        },
        {
          "to": "brief-eval-x-a3",
          "rel": "relates-to"
        },
        {
          "to": "brief-eval-x-j2",
          "rel": "relates-to"
        },
        {
          "to": "design-eval-property-tasks",
          "rel": "relates-to"
        },
        {
          "to": "design-eval-arms",
          "rel": "relates-to"
        },
        {
          "to": "design-eval-catalog-0-7",
          "rel": "relates-to"
        },
        {
          "to": "defect-classes",
          "rel": "relates-to"
        }
      ],
      "diagrams": [],
      "sourceSha256": "4bcde925ee46262847a34596ce0e720db1aede718866d2ccb4258b4f8fc98b0f"
    },
    {
      "id": "coordinator-log-c35",
      "path": "docs/coordination/coordinator-log/c35.md",
      "title": "Coordinator #35 hand-back (2026-10-05): X-J1b's two conflicts, W0 rev 6.12, the J1b continuation compile, CANON-A",
      "type": "doc",
      "status": "accepted",
      "owner": "@timianmalloo",
      "phase": "",
      "reviewBy": "2026-11-05",
      "reviewSuggested": [],
      "summary": "Coordinator #35, on base 3f887a0c, ruled X-J1b's blocking seam request. ADR-0006's canonical form (no floats) decides the duration: cell.turn_ended carries turn_ms, an int, by the outcome row's own expression. W1-J Amendment 1 and W0 rev 6.12 R6.12a hold it, and the ADR name sync went to the Owner as a non-blocking decision request. J1b gets the one lifecycle.TABLE entry for cell.turn_ended, because the engine checks the table at write time (R6.12b). It granted the three smaller requests as built, compiled the Sonnet same-tree continuation (merge integrate/e2e4-18 first, which holds bb177a2e), and registered CANON-A with its sweep.",
      "tags": [
        "coordination",
        "coordinator-log",
        "compile",
        "data-model"
      ],
      "links": [
        {
          "to": "coordinator-log",
          "rel": "relates-to"
        },
        {
          "to": "coordination-e2e4",
          "rel": "relates-to"
        },
        {
          "to": "brief-eval-x-j1",
          "rel": "relates-to"
        },
        {
          "to": "design-eval-multi-turn",
          "rel": "relates-to"
        },
        {
          "to": "design-eval-seam-contracts",
          "rel": "relates-to"
        },
        {
          "to": "adr-0006-results-data-model",
          "rel": "relates-to"
        },
        {
          "to": "defect-classes",
          "rel": "relates-to"
        }
      ],
      "diagrams": [],
      "sourceSha256": "90842417afc6f51c1ac118e39b8613365e650b98bb802414a4cef58ae4f71398"
    },
    {
      "id": "coordinator-log-c36",
      "path": "docs/coordination/coordinator-log/c36.md",
      "title": "Coordinator #36 hand-back (2026-10-05): the X-J1c compile, J1b's two scope notes, the snapshot TABLE entry, FLAKE-A and ROUTE-A",
      "type": "doc",
      "status": "accepted",
      "owner": "@timianmalloo",
      "phase": "",
      "reviewBy": "2026-11-05",
      "reviewSuggested": [],
      "summary": "Coordinator #36, on base 197092d3 (X-J1b's green, K4(4) at 60da1888), compiled X-J1c for Codex gpt-6.1-sol (session x-j1c-e1e4, branch build/eval-x-j1c, run w2-j1c-e1e4). J1c owns both of J1b's scope notes: wiring _snapshot_turn into the loop (in K4(5)), and turn_ended{1} for a single-turn cell (its own commit after K4(5)). Three boundary decisions are in the compile: J1c gets the one lifecycle.TABLE entry for cell.turn_snapshot_archived, because check_writer refuses an unmapped kind; copy_retries is null, because publish_dir does not return a count; and the snapshot_cell ALLOWED entry is deleted in K4(5). FLAKE-A and ROUTE-A are registered as candidates.",
      "tags": [
        "coordination",
        "coordinator-log",
        "compile"
      ],
      "links": [
        {
          "to": "coordinator-log",
          "rel": "relates-to"
        },
        {
          "to": "coordination-e2e4",
          "rel": "relates-to"
        },
        {
          "to": "brief-eval-x-j1",
          "rel": "relates-to"
        },
        {
          "to": "design-eval-multi-turn",
          "rel": "relates-to"
        },
        {
          "to": "design-eval-seam-contracts",
          "rel": "relates-to"
        },
        {
          "to": "defect-classes",
          "rel": "relates-to"
        }
      ],
      "diagrams": [],
      "sourceSha256": "f564497b96fca083c70aac7a7a1ae105c19c000444284f6215d94c1b8284a732"
    },
    {
      "id": "coordinator-log-c37",
      "path": "docs/coordination/coordinator-log/c37.md",
      "title": "Coordinator #37 hand-back (2026-10-05): J1c's three seam rulings, the test_driver regression, the J1c continuation and X-J1d compiles, the context split rule, CEIL-A",
      "type": "doc",
      "status": "accepted",
      "owner": "@timianmalloo",
      "phase": "",
      "reviewBy": "2026-11-05",
      "reviewSuggested": [],
      "summary": "Coordinator #37, on base 9a9dee14 (X-J1c's Codex partial), ruled J1c's three seam requests: both test seams stand, each paired with a strict-xfail J1d re-tighten case (RT-1, RT-2), and the docs-index derive is granted. The snapshot fill is tried three times with no wait after the last failure. The two test_driver failures are J1c's regression (7c7c2eb5 moved every cell onto open_session; the spy still watches run_turn). Compiled the J1c Sonnet continuation and X-J1d (Codex), with a measured context split rule. CEIL-A registered; RUN-B, LOCK-A and SEED-A instances added.",
      "tags": [
        "coordination",
        "coordinator-log",
        "compile"
      ],
      "links": [
        {
          "to": "coordinator-log",
          "rel": "relates-to"
        },
        {
          "to": "coordination-e2e4",
          "rel": "relates-to"
        },
        {
          "to": "brief-eval-x-j1",
          "rel": "relates-to"
        },
        {
          "to": "design-eval-multi-turn",
          "rel": "relates-to"
        },
        {
          "to": "defect-classes",
          "rel": "relates-to"
        },
        {
          "to": "plan-eval-x-j1c",
          "rel": "relates-to"
        }
      ],
      "diagrams": [],
      "sourceSha256": "7d0a7f4157960ead085b0c612f4beb45feda264147cc65df7d643658ff1dde66"
    },
    {
      "id": "coordinator-log-c38",
      "path": "docs/coordination/coordinator-log/c38.md",
      "title": "Coordinator #38 hand-back (2026-10-06): J1d's K2 fixture seam, the X-J1e, X-J2c and X-A3c compiles, cells[].calibration to the plan revision, QUOTE-A, CACHE-B and PATH-B",
      "type": "doc",
      "status": "accepted",
      "owner": "@timianmalloo",
      "phase": "",
      "reviewBy": "2026-11-06",
      "reviewSuggested": [],
      "summary": "Coordinator #38, on base 97fee009 (J1d's K1-K3 on integrate/e2e4-18 070f16b4), granted J1d's K2 fixture seam as built (six constructor lines, no assertion changed). Compiled the three P3 turns J1d unblocks: X-J1e (Codex, runner contract), X-J2c and X-A3c (Claude Code Sonnet Agent-tool sub-agents, own trees off the integration head after J1d joins). Put cells[].calibration (EV-9) in the next plan revision, not in A3c. Registered QUOTE-A, CACHE-B and PATH-B, a MUT-E instance (the STRATEGIES union) and a fourth FLAKE-A instance, which fires its upgrade trigger.",
      "tags": [
        "coordination",
        "coordinator-log",
        "compile"
      ],
      "links": [
        {
          "to": "coordinator-log",
          "rel": "relates-to"
        },
        {
          "to": "coordination-e2e4",
          "rel": "relates-to"
        },
        {
          "to": "brief-eval-x-j1",
          "rel": "relates-to"
        },
        {
          "to": "brief-eval-x-j2",
          "rel": "relates-to"
        },
        {
          "to": "brief-eval-x-a3",
          "rel": "relates-to"
        },
        {
          "to": "design-eval-multi-turn",
          "rel": "relates-to"
        },
        {
          "to": "defect-classes",
          "rel": "relates-to"
        }
      ],
      "diagrams": [],
      "sourceSha256": "995e8a858132ed1edf48a9f70bedd286242c6323efc4787af71aee95f2cc511f"
    },
    {
      "id": "coordinator-log-c39",
      "path": "docs/coordination/coordinator-log/c39.md",
      "title": "Coordinator #39 hand-back (2026-10-06): the P4 compiles (X-K1a, X-K2b, X-RDY), A3c's G1 seam, W0 rev 6.13 and W1-J errata, REL-A, PROBE-A and OPER-A",
      "type": "doc",
      "status": "accepted",
      "owner": "@timianmalloo",
      "phase": "",
      "reviewBy": "2026-11-06",
      "reviewSuggested": [],
      "summary": "Coordinator #39, on base 1a837a5d (X-J1e's join; X-A3c's join running on 186ad7da), compiled batch P4's three turns: X-K1a (Codex; W1-K K1 and K2, with Coordinator #39's four-turn split), X-K2b (Agy; the alarm, with HB-ALM-003 and the report header left in E5 as W1-K says) and X-RDY (Claude Code Sonnet; seven ready flips, S1's order). Ruled that A3c's G1 pins in cli.py and workspace.py stay. Wrote W0 rev 6.13 (HB-PLN-005 retired, the copy_retries erratum, J1c's TABLE row, no X-TE9 wait for K2b, HB-ALM-003 to E5) and the W1-J errata, and registered REL-A, PROBE-A, OPER-A and a LOCK-A cost instance.",
      "tags": [
        "coordination",
        "coordinator-log",
        "compile"
      ],
      "links": [
        {
          "to": "coordinator-log",
          "rel": "relates-to"
        },
        {
          "to": "coordination-e2e4",
          "rel": "relates-to"
        },
        {
          "to": "brief-eval-x-k1",
          "rel": "relates-to"
        },
        {
          "to": "brief-eval-x-k2",
          "rel": "relates-to"
        },
        {
          "to": "design-eval-seam-contracts",
          "rel": "relates-to"
        },
        {
          "to": "design-eval-multi-turn",
          "rel": "relates-to"
        },
        {
          "to": "defect-classes",
          "rel": "relates-to"
        }
      ],
      "diagrams": [],
      "sourceSha256": "8066984a571d77d886eb162931410cc596d3bc8693782d94727fad8fb506f337"
    },
    {
      "id": "coordinator-log-c42",
      "path": "docs/coordination/coordinator-log/c42.md",
      "title": "Coordinator #42 hand-back (2026-10-06): X-K1b compiled, the rework evidence-pointer fix folded into X-FIXD turn 2, FALLBACK-A and EVID-A registered",
      "type": "doc",
      "status": "accepted",
      "owner": "@timianmalloo",
      "phase": "",
      "reviewBy": "2026-11-06",
      "reviewSuggested": [],
      "summary": "Coordinator #42, on build/eval-x-k1a (fd8b5e61), compiled X-K1b (Codex gpt-6.1-sol; W1-K K3 and K4, on K1a's landed names) and updated x-k1.contract.json with a Leader-only fallback. It folded the rework evidence-pointer fix into X-FIXD turn 2, which supersedes Coordinator #41's turn-2 compile. It recorded K1a's real history from its audit entries, registered FALLBACK-A (two carriers; X-K2b's open compile carries the same clause) and EVID-A (rework.py drops the write_section pointer at both calls), and added Lane F item 10.",
      "tags": [
        "coordination",
        "coordinator-log",
        "compile"
      ],
      "links": [
        {
          "to": "coordinator-log",
          "rel": "relates-to"
        },
        {
          "to": "coordinator-log-c39",
          "rel": "relates-to"
        },
        {
          "to": "coordination-e2e4",
          "rel": "relates-to"
        },
        {
          "to": "brief-eval-x-k1",
          "rel": "relates-to"
        },
        {
          "to": "design-eval-resume",
          "rel": "relates-to"
        },
        {
          "to": "design-eval-discriminate",
          "rel": "relates-to"
        },
        {
          "to": "defect-classes",
          "rel": "relates-to"
        }
      ],
      "diagrams": [],
      "sourceSha256": "d2ceff73598a33a2eb7398133ac1074d9661d3a53d6fea28f35ef7301b4e9693"
    },
    {
      "id": "defect-classes",
      "path": "docs/lessons/defect-classes.md",
      "title": "Defect-class register",
      "type": "doc",
      "status": "accepted",
      "owner": "@timianmalloo",
      "phase": "",
      "reviewBy": "2026-12-22",
      "reviewSuggested": [],
      "summary": "The project's register of defect classes: the recurring shapes of things that go wrong here, what each one survives, and the control that now fails when the shape recurs. Read at grounding; appended to on every defect, correction or falsified assumption.",
      "tags": [
        "lessons",
        "defect-classes",
        "continuous-improvement"
      ],
      "links": [
        {
          "to": "arch-harness-bench",
          "rel": "relates-to"
        },
        {
          "to": "design-run-lifecycle-model",
          "rel": "relates-to"
        }
      ],
      "diagrams": [],
      "sourceSha256": "60f1d562bccdc85aa227555697babcb71d274870643876f8c0dbb57310874578"
    },
    {
      "id": "note-proposal-grounding-findings",
      "path": "docs/notes/proposal-grounding-findings.md",
      "title": "Proposal grounding findings (scaffold pass)",
      "type": "doc",
      "status": "draft",
      "owner": "@timianmalloo",
      "phase": "",
      "reviewBy": "2026-10-23",
      "reviewSuggested": [],
      "summary": "What the scaffold pass found when it checked the proposal against the mockup and the pack's real coord-runner.py: a worker-isolation seam between \"fresh clone per run\" and coord-runner's worktrees, runner limits the design must fit, gaps with no owner, and the evidence behind the formal-methods revision (scenario 7, oracle ladder, protocol conformance).",
      "tags": [
        "benchmark",
        "findings",
        "open-questions"
      ],
      "links": [
        {
          "to": "proposal-cross-harness-benchmarking",
          "rel": "refines"
        }
      ],
      "diagrams": [],
      "sourceSha256": "6e60fa814c6eae61a7b55760e8315c186138ee62e0783571b412994046748e4e"
    },
    {
      "id": "note-spike-fm1-tla-trace-validation",
      "path": "docs/notes/spike-fm1-tla-trace-validation.md",
      "title": "Spike DR-FM1: TLC's external-trace-validation mechanism, measured on this host",
      "type": "doc",
      "status": "draft",
      "owner": "@timianmalloo",
      "phase": "Phase 2: deterministic graders (S-08g); unblocks T-G1's model_conformance/model_non_vacuity",
      "reviewBy": "2026-10-29",
      "reviewSuggested": [],
      "summary": "DR-FM1's granted spike (docs/notes/rulings.md R-84), run on this host. TWO documented TLC trace-validation mechanisms were opened and read: the current one (tlaplus/Examples' EWD998ChanTrace.tla, using the Json/IOUtils CommunityModules and a POSTCONDITION) and the original one (Pressler/Kuppe, \"Verifying Software Traces Against a Formal Specification with TLA+ and TLC\", Dec 2018). The pinned tla2tools v1.7.4 (TLC 2.19) does not support the POSTCONDITION/ALIAS config keywords the current pattern uses (verified from the jar's own keyword table), and every CommunityModules release checked (Feb 2023 - Sep 2026) fails to load under TLC 2.19 at all (a class it references, tlc2.value.impl.KSubsetValue, does not exist in that TLC build, and TLC's override loader aborts for Json/IOUtils too even though neither needs it). The classic technique needs neither: the trace is a literal TLA+ value, the model's own post-step state is compared to a recorded snapshot via an INVARIANT, and TLC's own violation report names the first divergent line. Run end to end on this host: a small reference model of coord-core.py's lease fold accepts one recorded five-step trace (exit 0, \"No error has been found\", depth 6) and rejects one bug-seeded trace at exactly its known divergence (exit 12, \"Invariant TraceInv is violated\", the printed line naming trace step 3 verbatim). The trace interface (state variables and the recorded-line shape) is written down for G1's prompt.",
      "tags": [
        "benchmark",
        "spike",
        "formal-methods",
        "tla+",
        "toolchain",
        "DR-FM1",
        "G1"
      ],
      "links": [
        {
          "to": "rulings-register",
          "rel": "depends-on"
        },
        {
          "to": "design-formal-grader",
          "rel": "refines"
        },
        {
          "to": "note-spike-s12-formal-toolchains",
          "rel": "depends-on"
        }
      ],
      "diagrams": [],
      "sourceSha256": "c3fb2b2bc474aad67f114db773a428d3d4da6766a4c87636d14baade372bed46"
    },
    {
      "id": "note-spike-gw-headless",
      "path": "docs/notes/spike-gw-headless.md",
      "title": "Spike GW-H: the headless judge CLIs with every tool denied: Claude qualifies in text mode; Codex keeps its code-mode exec tool",
      "type": "doc",
      "status": "draft",
      "owner": "@timianmalloo",
      "phase": "",
      "reviewBy": "2026-12-25",
      "reviewSuggested": [
        {
          "by": "design-phase3-gateway-judges",
          "on": "2026-09-25",
          "reason": "row-17 gateway design gated (rev 3): Fable judge, Codex not qualified (DR-GW-1), CLI-added context (DR-GW-5)"
        }
      ],
      "summary": "Five Leader-run probe turns (2026-09-25). Claude Code 2.1.282 serves claude-fable-5-1 (and the fallback claude-opus-5-5) with 0 tool events in text mode; --json-schema adds a StructuredOutput tool call, so text mode is used. Codex 0.156.0 serves gpt-6-sol but still advertises its code-mode exec tool: the model called it once per turn and it failed closed (\"code-mode host is disabled\"), so Codex does not meet R-58 c4 as launched (a decision request). The CLIs add context the gateway cannot scan: the Claude account e-mail on some calls, the operator's ~/.agents/skills root (user name, home path) in Codex, and each CLI's self-identification. The OpenAI account is at 99% of its weekly limit until 2026-09-29T20:03Z.",
      "tags": [
        "benchmark",
        "spike",
        "phase-3",
        "gateway",
        "judges",
        "US-46",
        "R-58"
      ],
      "links": [
        {
          "to": "design-phase3-gateway-judges",
          "rel": "relates-to"
        },
        {
          "to": "adr-0009-model-gateway",
          "rel": "relates-to"
        },
        {
          "to": "spec-harness-bench",
          "rel": "relates-to"
        },
        {
          "to": "rulings-register",
          "rel": "depends-on"
        }
      ],
      "diagrams": [],
      "sourceSha256": "b9280f03e3a9cd5c94eebc415a8e5bedfdadc016c6fde390023f3f457c8b89ee"
    },
    {
      "id": "note-spike-isolation-permissions",
      "path": "docs/notes/spike-isolation-permissions.md",
      "title": "Spikes R1, R2, R11, N1, N2: config isolation, static permissions, host isolation, native cells",
      "type": "doc",
      "status": "draft",
      "owner": "@timianmalloo",
      "phase": "",
      "reviewBy": "2026-10-23",
      "reviewSuggested": [],
      "summary": "Per-cell config homes keep sign-in and drop user-level skills for all three harnesses, but a workspace under the user profile still loads ~/.claude/CLAUDE.md, and Claude's account context (email, account-synced skills) survives any isolation. A static profile runs shell and edits with zero prompts on every harness. Linux containers give every harness the same containment, but Copilot needs a token passed in there. N1/N2 (after ADR-0012): natively, with Codex in agent-full-access, all three run symmetric and unsandboxed with zero prompts, log every command, and Copilot needs no token; a Windows Job Object kills and confirms a cell's whole process tree.",
      "tags": [
        "benchmark",
        "spike",
        "isolation",
        "permissions",
        "containers",
        "security"
      ],
      "links": [
        {
          "to": "spec-harness-bench",
          "rel": "refines"
        },
        {
          "to": "note-spike-runner-path",
          "rel": "refines"
        }
      ],
      "diagrams": [],
      "sourceSha256": "8d2699649e9e22be2315839714c9683713119b0cb163420a455eed0bb9101a9d"
    },
    {
      "id": "note-spike-n5-codex-skill-roots",
      "path": "docs/notes/spike-n5-codex-skill-roots.md",
      "title": "Spike N5: no observed Codex 0.156 mechanism removes ~/.agents/skills from a cell",
      "type": "doc",
      "status": "draft",
      "owner": "@timianmalloo",
      "phase": "",
      "reviewBy": "2026-10-23",
      "reviewSuggested": [],
      "summary": "T5's 1.5h research timebox found one candidate (features.skip_host_skill_discovery in config.toml) and ran it for real against the US-13 canary: the operator's ~/.agents/skills skill still reached the Codex cell. A third party independently reports the same flag, plus --ignore-user-config, --ignore-rules and project_doc_max_bytes=0, all fail the same way on 0.154.0. Negative result: no Codex 0.156 mechanism observed (source or run) removes a user skill root from a cell. The change is reverted; N5 stays open, xfail(strict) with an updated reason.",
      "tags": [
        "benchmark",
        "spike",
        "phase-1",
        "codex",
        "skills",
        "N5"
      ],
      "links": [
        {
          "to": "design-phase1-walking-skeleton",
          "rel": "refines"
        },
        {
          "to": "coordination-phase1-finish",
          "rel": "relates-to"
        }
      ],
      "diagrams": [],
      "sourceSha256": "2327898c1d68749562fe1335e2bba74eb712a2399989eb601e21a868601e813f"
    },
    {
      "id": "note-spike-phase1-probes",
      "path": "docs/notes/spike-phase1-probes.md",
      "title": "Phase-1 probes W1, W3, N4: pack install, provider-error rows, job containment",
      "type": "doc",
      "status": "draft",
      "owner": "@timianmalloo",
      "phase": "",
      "reviewBy": "2026-10-23",
      "reviewSuggested": [
        {
          "by": "adr-0013-native-cells",
          "on": "2026-10-03",
          "reason": "Proposed amendment 2026-10-03 (ADR-0014/0015, arch-evaluation-campaign): cell grain by arm, per-turn prompt_sent, archive_files snapshot key part, job terminated after the last turn; council gate pending"
        }
      ],
      "summary": "W1: pack-apply.py apply --install installs pack revision 92 non-interactively in under a second and lists every path it wrote as JSON (437 files). W3: a failed Claude call is an assistant row with isApiErrorMessage, apiErrorStatus and error, model \"<synthetic>\" and zero usage; Codex reports a bad model as ACP complete with task_complete.error. N4: no harness process leaves its cell's Job Object, the job handle is not inheritable, and nothing survives TerminateJobObject.",
      "tags": [
        "benchmark",
        "spike",
        "phase-1",
        "pack",
        "telemetry",
        "job-object"
      ],
      "links": [
        {
          "to": "design-phase1-walking-skeleton",
          "rel": "refines"
        },
        {
          "to": "adr-0013-native-cells",
          "rel": "refines"
        }
      ],
      "diagrams": [],
      "sourceSha256": "9dade027eb726ba4b620935498b0708b0e2f6df789ef821ec483c526af229b0d"
    },
    {
      "id": "note-spike-runner-path",
      "path": "docs/notes/spike-runner-path.md",
      "title": "Spike: harness launch over ACP, telemetry, and worker isolation",
      "type": "doc",
      "status": "draft",
      "owner": "@timianmalloo",
      "phase": "",
      "reviewBy": "2026-10-23",
      "reviewSuggested": [],
      "summary": "Spikes 1 and 2 run on the workstation on 2026-09-23. All three harnesses complete a turn over ACP through the pack's transport, and every token count lives in each harness's own session store (Copilot also records a native cost basis). A generated per-cell repo as the invoking checkout isolates workers with no runner change. Four runner gaps block unattended benchmark cells: prompt delivery, per-worker model pins, permission symmetry, and user-level config leakage.",
      "tags": [
        "benchmark",
        "spike",
        "runner",
        "telemetry",
        "isolation"
      ],
      "links": [
        {
          "to": "note-proposal-grounding-findings",
          "rel": "refines"
        },
        {
          "to": "proposal-cross-harness-benchmarking",
          "rel": "refines"
        }
      ],
      "diagrams": [],
      "sourceSha256": "6be48da395ad06a2e18cf0e664f395e84f62f915bd6629db4ca86712b119edda"
    },
    {
      "id": "note-spike-s04-scripted-user",
      "path": "docs/notes/spike-s04-scripted-user.md",
      "title": "Spike S-04: the scripted user's ask_user tool reaches Claude Code and Codex over stdio; Copilot rejects stdio from the client",
      "type": "doc",
      "status": "draft",
      "owner": "@timianmalloo",
      "phase": "",
      "reviewBy": "2026-12-25",
      "reviewSuggested": [],
      "summary": "Eleven probe turns on the pinned builds (Leader-run, 2026-09-25). Claude Code 2.1.282 and Codex 0.156.0 start a stdio MCP server given in ACP session/new mcpServers, list ask_user, and call it on request; the reply reaches the model. Copilot 1.0.89-1 accepts session/new but rejects the stdio entry (\"Rejecting non-http/sse MCP server\"), with or without --disable-builtin-mcps, so the tool never reaches it: a decision request (R-37 c1), with an HTTP and a launch-config variant written for the Leader. On A1, Claude asked once (the key ambiguity, paraphrased; no match), Codex asked nothing. The rule table's held-out measurement: precision 1.0, 0/21 default-labelled matches, paraphrase recall 0/11 (overall 6/17); S-04 threshold set (regression floor met; T = 0.80 on paraphrase recall not met, so A1 clarification metrics carry \"low-confidence matcher\" in wave 2). S-04b: session HTTP is listed and called on all three harnesses, and Copilot's launch config works too, both under --disable-builtin-mcps; Copilot lists tools lazily, at the first prompt.",
      "tags": [
        "benchmark",
        "spike",
        "phase-2",
        "scenario-1",
        "scripted-user",
        "mcp",
        "acp",
        "matcher",
        "S-04"
      ],
      "links": [
        {
          "to": "design-phase2-scripted-user",
          "rel": "relates-to"
        },
        {
          "to": "spec-harness-bench",
          "rel": "relates-to"
        },
        {
          "to": "adr-0004-static-permissions",
          "rel": "relates-to"
        },
        {
          "to": "rulings-register",
          "rel": "depends-on"
        }
      ],
      "diagrams": [],
      "sourceSha256": "eb2da9c50caab0eb1856d7407bba4811a01934d4a41f077b672ab3a85a2045be"
    },
    {
      "id": "note-spike-s12-formal-toolchains",
      "path": "docs/notes/spike-s12-formal-toolchains.md",
      "title": "Spike S-12: TLA+ and Lean 4 toolchains run natively on the Windows operator host",
      "type": "doc",
      "status": "draft",
      "owner": "@timianmalloo",
      "phase": "",
      "reviewBy": "2026-10-29",
      "reviewSuggested": [
        {
          "by": "adr-0013-native-cells",
          "on": "2026-10-03",
          "reason": "Proposed amendment 2026-10-03 (ADR-0014/0015, arch-evaluation-campaign): cell grain by arm, per-turn prompt_sent, archive_files snapshot key part, job terminated after the last turn; council gate pending"
        }
      ],
      "summary": "Both toolchains proved out natively on this Windows 11 host. TLA+: Temurin JDK 21 already on PATH, tla2tools.jar v1.7.4 re-downloaded and its sha256 matched tools/check_models.py's pin exactly, TLC checked run_lifecycle.tla (liveness config) clean in 10.4s inside a fresh git worktree. Lean 4: elan 4.2.4 installed natively to the operator's per-user ~/.elan, a minimal no-Mathlib lake project pinned to leanprover/lean4:v4.34.1 built clean (`#print axioms` shows only propext/Quot.sound, no sorry) in a fresh git worktree; first build (toolchain download+install+build) took 54.3s, a rebuild with the toolchain already warm took 1.1s. The elan toolchain cache is 3.1 GB and lives outside any cell's working copy; a cell's own `.lake/build` is 70 KB. macOS is unverified for both toolchains (marked, not guessed): no macOS CI job exists today. Nothing in either toolchain failed; a first draft Lean proof was wrong (my error, not a toolchain fault) and was fixed.",
      "tags": [
        "benchmark",
        "spike",
        "formal-methods",
        "tla+",
        "lean",
        "toolchain",
        "S-12",
        "G1",
        "G2"
      ],
      "links": [
        {
          "to": "plan-spec-backlog",
          "rel": "refines"
        },
        {
          "to": "note-proposal-grounding-findings",
          "rel": "refines"
        },
        {
          "to": "adr-0013-native-cells",
          "rel": "depends-on"
        },
        {
          "to": "spec-harness-bench",
          "rel": "relates-to"
        }
      ],
      "diagrams": [],
      "sourceSha256": "d35a8989cbc5eb2f8456f152825f7a70d3f79266c6567e2e24727038af97beb7"
    },
    {
      "id": "plan-eval-x-j1a",
      "path": "docs/plans/eval-x-j1a.md",
      "title": "X-J1a: skeleton, assertion-red table and cell budget clock",
      "type": "doc",
      "status": "proposed",
      "owner": "@timianmalloo",
      "phase": "",
      "reviewBy": "2026-10-19",
      "reviewSuggested": [],
      "summary": "J1a execution graph and measured skeleton, red and green evidence.",
      "tags": [
        "evaluation",
        "coordination",
        "execution-graph"
      ],
      "links": [
        {
          "to": "brief-eval-x-j1",
          "rel": "implements"
        },
        {
          "to": "design-eval-multi-turn",
          "rel": "depends-on"
        }
      ],
      "diagrams": [
        {
          "kind": "flowchart",
          "title": "Diagram 1",
          "mermaid": "flowchart LR\n G --> S --> R --> C --> V --> H"
        }
      ],
      "sourceSha256": "21e6681caa476d0431a368581b3fd833f4f8ad39dc21839e9eaf027095b7237d"
    },
    {
      "id": "plan-eval-x-j1b",
      "path": "docs/plans/eval-x-j1b.md",
      "title": "X-J1b: returned-turn usage, decisions and session lifetime",
      "type": "doc",
      "status": "proposed",
      "owner": "@timianmalloo",
      "phase": "",
      "reviewBy": "2026-10-17",
      "reviewSuggested": [],
      "summary": "Create-only execution plan and red proof for dispatch x-j1b-e1e4. Builds three fixes on J1a's landed interfaces; runtime evidence and final cost ledger are recorded in the closing coordination-worker audit entry. The Leader performs independent join review.",
      "tags": [
        "implementation",
        "evaluation",
        "multi-turn",
        "proof"
      ],
      "links": [
        {
          "to": "brief-eval-x-j1",
          "rel": "implements"
        },
        {
          "to": "design-eval-multi-turn",
          "rel": "depends-on"
        },
        {
          "to": "design-eval-seam-contracts",
          "rel": "depends-on"
        }
      ],
      "diagrams": [
        {
          "kind": "flowchart",
          "title": "Execution graph",
          "mermaid": "flowchart LR\n B --> R --> P --> S --> U --> D --> C --> G --> H"
        }
      ],
      "sourceSha256": "33a78832e033e09bd28b598f304a50e097bac5d6eef1ff98d9b20110037ad4d3"
    },
    {
      "id": "plan-eval-x-j1c",
      "path": "docs/plans/eval-x-j1c.md",
      "title": "X-J1c: durable snapshots, recovery and single-turn end facts",
      "type": "doc",
      "status": "proposed",
      "owner": "@timianmalloo",
      "phase": "",
      "reviewBy": "2026-10-17",
      "reviewSuggested": [],
      "summary": "Create-only dispatch plan and base red proof. Closing audit records actual delivery, measurements and gates; the Leader independently reviews and joins.",
      "tags": [
        "evaluation",
        "implementation",
        "multi-turn",
        "proof"
      ],
      "links": [
        {
          "to": "brief-eval-x-j1",
          "rel": "implements"
        },
        {
          "to": "design-eval-multi-turn",
          "rel": "depends-on"
        },
        {
          "to": "design-eval-seam-contracts",
          "rel": "depends-on"
        }
      ],
      "diagrams": [
        {
          "kind": "flowchart",
          "title": "Execution graph",
          "mermaid": "flowchart LR\n B --> R --> P --> K --> T --> G --> H\n K --> M --> G"
        }
      ],
      "sourceSha256": "6b80966a85b0a4a931d0151980cf387be0b978c66c2ba4770b70209731d6a592"
    },
    {
      "id": "plan-eval-x-j1d",
      "path": "docs/plans/eval-x-j1d.md",
      "title": "X-J1d readers and conformance dispatch",
      "type": "doc",
      "status": "active",
      "owner": "x-j1d-e1e4",
      "phase": "",
      "reviewBy": "2026-11-05",
      "reviewSuggested": [],
      "summary": "J1d readers and conformance execution graph with red-first proof and native context checkpoints.",
      "tags": [
        "evaluation",
        "coordination"
      ],
      "links": [
        {
          "to": "design-eval-multi-turn",
          "rel": "relates-to"
        },
        {
          "to": "design-eval-seam-contracts",
          "rel": "depends-on"
        }
      ],
      "diagrams": [
        {
          "kind": "flowchart",
          "title": "X-J1d execution graph",
          "mermaid": "flowchart LR\n B --> K1 --> G\n B --> K2 --> G\n B --> K3 --> S --> K4 --> G --> H\n S --> H"
        }
      ],
      "sourceSha256": "00e5cc89fc4c70ca4d4730cb89722da04ebcc8d5eadf9b907c389f535174a2a7"
    },
    {
      "id": "plan-eval-x-j1e",
      "path": "docs/plans/eval-x-j1e.md",
      "title": "X-J1e: W1-J mutation proof and planned context split",
      "type": "doc",
      "status": "proposed",
      "owner": "@timianmalloo",
      "phase": "",
      "reviewBy": "2026-10-17",
      "reviewSuggested": [],
      "summary": "43 engine rows and two driver rows landed; engine 105 killed/3 survived/1 timeout, driver 6 killed/1 survived. Planned hand-back after K2 at 128178 context tokens. S-J4 and final worker gates remain open.",
      "tags": [
        "evaluation",
        "multi-turn",
        "mutations",
        "coordination"
      ],
      "links": [
        {
          "to": "brief-eval-x-j1",
          "rel": "implements"
        },
        {
          "to": "design-eval-multi-turn",
          "rel": "depends-on"
        }
      ],
      "diagrams": [
        {
          "kind": "flowchart",
          "title": "Execution graph",
          "mermaid": "flowchart LR\n B --> G0 --> K1 --> M1 --> K2\n K2 -->|at most 110k| S --> G --> H\n K2 -->|above 110k: planned split| H"
        }
      ],
      "sourceSha256": "34dcfbe0b20675ff2f8e6873ffa81ee3ab9c307992617d957f9fa989d0a2e604"
    },
    {
      "id": "plan-eval-x-k1a",
      "path": "docs/plans/eval-x-k1a.md",
      "title": "X-K1a: resume skeleton and assertion-red test handoff",
      "type": "doc",
      "status": "proposed",
      "owner": "@timianmalloo",
      "phase": "",
      "reviewBy": "2026-10-17",
      "reviewSuggested": [],
      "summary": "Bounded X-K1a execution: refusal skeleton, confirmed code registry, assertion-red tests, R-104 gates and split-rule handoff.",
      "tags": [
        "evaluation",
        "resume",
        "execution-plan"
      ],
      "links": [
        {
          "to": "brief-eval-x-k1",
          "rel": "implements"
        },
        {
          "to": "design-eval-resume",
          "rel": "depends-on"
        },
        {
          "to": "design-eval-seam-contracts",
          "rel": "depends-on"
        }
      ],
      "diagrams": [
        {
          "kind": "flowchart",
          "title": "Graph and floors",
          "mermaid": "flowchart LR\n  G0 --> G1 --> K1a --> K1b --> K2 --> G2 --> H\n  K1a --> K1c --> K2"
        }
      ],
      "sourceSha256": "592a38b4c2653264c54e06f840e331d21627d2624dff11d7a45dc78928d2a7bf"
    },
    {
      "id": "proof-phase2",
      "path": "docs/proof/phase2.md",
      "title": "Proof Pack - phase 2 (wave-by-wave joins)",
      "type": "doc",
      "status": "draft",
      "owner": "@timianmalloo",
      "phase": "Phase 2 · smoke on all harnesses",
      "reviewBy": "2026-10-08",
      "reviewSuggested": [],
      "summary": "The evidence for each phase-2 join: what was claimed, the red observed by a non-author, the mutation result, the reviewer's verdict, and the residuals. One Claim table per join.",
      "tags": [
        "proof",
        "phase2",
        "red-first",
        "joins"
      ],
      "links": [
        {
          "to": "coordination-finish-harness-bench",
          "rel": "relates-to"
        },
        {
          "to": "proof-phase1",
          "rel": "relates-to"
        }
      ],
      "diagrams": [],
      "sourceSha256": "22f534f0e61cb15908757ffc2902841f4db2567d376f8d0c5ddeef32c7f0dac2"
    },
    {
      "id": "proposal-benchmark-state-and-target",
      "path": "docs/proposals/benchmark-state-and-target.md",
      "title": "Benchmark: state and target",
      "type": "doc",
      "status": "proposed",
      "owner": "@timianmalloo",
      "phase": "",
      "reviewBy": "2026-12-31",
      "reviewSuggested": [],
      "summary": "After grids 1-4 the tool works (276-cell grids, verify ok, CI green) and its pack-improvement loop found and verified real fixes (pack-attributed failures 4 -> 0, ceremony waste -79%), but it cannot answer the question it was built for: the tasks are mostly saturated, the judge metrics never record, and no task tests security, resilience, rework or the Spike Protocol. On these tasks the pack costs 2.9-10.8x tokens with no pass gain and worse drift. Approach: an Enterprise/Production task family with mechanical checks, metrics that record, a power analysis, a pilot ring and an engine freeze, and one well-powered grid comparing pack-off, the current pack and a slimmed pack. The page is benchmark-state-and-target.html.",
      "tags": [
        "benchmark",
        "proposal",
        "pack-effect",
        "enterprise",
        "assessment"
      ],
      "links": [
        {
          "to": "proposal-pack-onoff-analysis",
          "rel": "relates-to"
        },
        {
          "to": "proposal-enterprise-production-portfolio",
          "rel": "relates-to"
        },
        {
          "to": "proposal-cross-harness-benchmarking",
          "rel": "relates-to"
        }
      ],
      "diagrams": [],
      "sourceSha256": "6e3c3b3fdd84cbe7cfd839cc575780f6c9bd39fe6432428b44d7632cf4d1c422"
    },
    {
      "id": "proposal-cross-harness-benchmarking",
      "path": "docs/proposals/cross-harness-benchmarking-proposal.md",
      "title": "Cross-Harness Benchmarking Proposal (ai-forward)",
      "type": "doc",
      "status": "accepted",
      "owner": "@timianmalloo",
      "phase": "",
      "reviewBy": "2027-03-22",
      "reviewSuggested": [],
      "summary": "The source design for this repo: a harness × model × pack factorial benchmark over a 24-task, seven-scenario BOM, driven by one coordinator through the ai-forward coordination layer, graded by the strongest mechanical oracle available (proof, model check, trace conformance, tests) before two blind judges, reported as a CLI table and an HTML page.",
      "tags": [
        "benchmark",
        "proposal"
      ],
      "links": [],
      "diagrams": [
        {
          "kind": "flowchart",
          "title": "Architecture",
          "mermaid": "flowchart TD\n  C[Coordinator session<br/>Claude Code or Codex] --> IL[(Intent log + KG<br/>ai-forward)]\n  C --> M[matrix.yaml × bom.yaml<br/>run plan]\n  M --> W1[Worker: Codex CLI<br/>gpt-6-sol]\n  M --> W2[Worker: Copilot CLI<br/>gpt-6-sol]\n  M --> W3[Worker: Claude Code<br/>opus-5.5]\n  W1 --> R1[Isolated repo + container<br/>pack on/off bootstrap]\n  W2 --> R2[Isolated repo + container]\n  W3 --> R3[Isolated repo + container]\n  R1 --> T[Telemetry sink<br/>OTel collector + session logs]\n  R2 --> T\n  R3 --> T\n  T --> G[grade/*.py<br/>deterministic + judge]\n  G --> S[(results.duckdb)]\n  S --> RP[report: CLI table<br/>HTML + kiviats + AI summaries]"
        }
      ],
      "sourceSha256": "599e881c212a84daecdb3fe4fcce0f251a6f89faee2040584fd621926e706112"
    },
    {
      "id": "proposal-enterprise-production-portfolio",
      "path": "docs/proposals/enterprise-production-portfolio.md",
      "title": "An Enterprise/Production portfolio for harness-bench",
      "type": "doc",
      "status": "proposed",
      "owner": "@timianmalloo",
      "phase": "",
      "reviewBy": "2026-12-31",
      "reviewSuggested": [],
      "summary": "BOM 0.5 measures SWE capability on small, saturated tasks; no task carries a latent enterprise requirement with a mechanical oracle. Proposes eight task families (H security, I privacy, J compliance, K resilience, L operability, M long-horizon rework, N unfamiliar API / spike, O simplicity controls, P drift), their mechanical metrics, sample sizes (about 39 cells per arm for a 0.30 pass-rate delta), the map to each pack intention, and a phased rollout that fixes measurement first. The page is enterprise-production-portfolio.html.",
      "tags": [
        "benchmark",
        "proposal",
        "bom",
        "security",
        "privacy",
        "resilience",
        "rework",
        "simplicity"
      ],
      "links": [
        {
          "to": "proposal-cross-harness-benchmarking",
          "rel": "relates-to"
        },
        {
          "to": "proposal-pack-onoff-analysis",
          "rel": "depends-on"
        }
      ],
      "diagrams": [],
      "sourceSha256": "d697717132ff5593483f35e8ecb04948ceadc97f9c1b83c1f4136140105f5b9d"
    },
    {
      "id": "proposal-pack-onoff-analysis",
      "path": "docs/proposals/pack-onoff-analysis.md",
      "title": "Pack on vs pack off: grid-1 analysis and ranked pack changes",
      "type": "doc",
      "status": "proposed",
      "owner": "@timianmalloo",
      "phase": "",
      "reviewBy": "2026-12-31",
      "reviewSuggested": [],
      "summary": "grid-1 + grid-1-cc (108 cells, pack r97, BOM 0.3 smoke): the pack cost 3.5x tokens and 1.9x wall clock and passed 40/54 vs 48/54 (p=0.08); 10 of 14 pack-on failures trace to worktree diversion (WT1) and ceremony that ended the turn, not to wrong code. Process changed as intended (goal state 51/54, test-first on D1 8/9 vs 0/9) but no smoke task can show the payoff; security, privacy, resilience and the Spike Protocol are not measurable in this BOM. Seven ranked pack changes. The page is pack-onoff-analysis.html.",
      "tags": [
        "benchmark",
        "proposal",
        "pack-effect",
        "continuous-improvement"
      ],
      "links": [
        {
          "to": "proposal-cross-harness-benchmarking",
          "rel": "relates-to"
        },
        {
          "to": "design-phase4-report",
          "rel": "relates-to"
        }
      ],
      "diagrams": [],
      "sourceSha256": "32f235bdd9ef5a50f339b185b9f5b27a48dbb164b03913b0a07c5bf58f1e5fd8"
    },
    {
      "id": "review-eval-ds",
      "path": "docs/design/reviews/eval-review-ds.md",
      "title": "Evaluation Campaign design reviews: Distributed Systems lens (Adversary Mode)",
      "type": "doc",
      "status": "draft",
      "owner": "@timianmalloo",
      "phase": "",
      "reviewBy": "2026-10-17",
      "reviewSuggested": [],
      "summary": "Adversary-mode review of the Wave 1 design slices by the Distributed Systems lens (rv-ds-e1e4): crash, ordering, idempotency and concurrency findings per slice, each with evidence, a smallest fix and a confidence label, and one gate line per slice. Appended per batch. First section: W0 seam contracts with Owner ruling R-90.",
      "tags": [],
      "links": [
        {
          "to": "design-eval-seam-contracts",
          "rel": "relates-to"
        }
      ],
      "diagrams": [],
      "sourceSha256": "2e738331996f46eb30416c1ee5a11d6aed1fed5b7cf677b60a300e7a8d3ea9c2"
    },
    {
      "id": "review-eval-ds-w1b",
      "path": "docs/design/reviews/eval-review-ds-w1b.md",
      "title": "W1-B crash-atomic publish: Distributed Systems lens review",
      "type": "doc",
      "status": "draft",
      "owner": "@timianmalloo",
      "phase": "",
      "reviewBy": "2026-10-17",
      "reviewSuggested": [],
      "summary": "Adversary-mode review of docs/design/eval-atomic-publish.md (branch design/eval-atomic-publish, 67e7dc83) by the Distributed Systems lens: the four W0 dispositions taken on trust (DS-5, DS-6, DS-7, DS-9), the bounded rename retry, and five minor findings.",
      "tags": [],
      "links": [
        {
          "to": "design-eval-seam-contracts",
          "rel": "relates-to"
        }
      ],
      "diagrams": [],
      "sourceSha256": "5251732e1cd4289428039c0593ca2bcf0102f5de6d2e399b5f41af19a333478d"
    },
    {
      "id": "review-eval-ds-w1c",
      "path": "docs/design/reviews/eval-review-ds-w1c.md",
      "title": "W1-C campaign record and bench campaign: Distributed Systems lens review",
      "type": "doc",
      "status": "draft",
      "owner": "@timianmalloo",
      "phase": "",
      "reviewBy": "2026-10-17",
      "reviewSuggested": [],
      "summary": "Adversary-mode review of docs/design/eval-campaign-record.md (design/eval-campaign-record, ae21488b, 61338062) by the Distributed Systems lens. DS-1, F2 and F8 hold. Two majors: the torn-tail repair breaks the ledger-prefix rule after a commit, and the run side of conclude has no lock-then-probe partner. PASS WITH CONDITIONS.",
      "tags": [],
      "links": [
        {
          "to": "design-eval-seam-contracts",
          "rel": "relates-to"
        }
      ],
      "diagrams": [],
      "sourceSha256": "1bce63791bbba85e0eb55e47af0b8f06bf90131a3dc75d712f6af432ccf8defe"
    },
    {
      "id": "review-eval-ds-w1j",
      "path": "docs/design/reviews/eval-review-ds-w1j.md",
      "title": "W1-J multi-turn attempt, turn snapshots and TLA+ model: Distributed Systems lens review",
      "type": "doc",
      "status": "draft",
      "owner": "@timianmalloo",
      "phase": "",
      "reviewBy": "2026-10-17",
      "reviewSuggested": [],
      "summary": "Adversary-mode review of docs/design/eval-multi-turn.md (design/eval-multi-turn, 08fabe34, 6b838ff2) and models/run_lifecycle.tla by the Distributed Systems lens. The turn loop, the ack barrier and the snapshot order hold, and the model fits the engine's sequential worker. Three majors: snapshot recovery has no E2 code path, the sweep seam is stale, and two of the five invariants have no code mirror. PASS WITH CONDITIONS.",
      "tags": [],
      "links": [
        {
          "to": "design-eval-seam-contracts",
          "rel": "relates-to"
        }
      ],
      "diagrams": [],
      "sourceSha256": "d70e401df96961909a7dbcf6a8fc12b4d21da47122ae7ce9aa25bb7e0292125e"
    },
    {
      "id": "review-eval-ds-w1k",
      "path": "docs/design/reviews/eval-review-ds-w1k.md",
      "title": "W1-K resume, liveness and the alarm channel: Distributed Systems lens review",
      "type": "doc",
      "status": "draft",
      "owner": "@timianmalloo",
      "phase": "",
      "reviewBy": "2026-10-17",
      "reviewSuggested": [],
      "summary": "Adversary-mode review of docs/design/eval-resume.md rev 1.1 (design/eval-resume, 315cf1d4) and models/run_lifecycle.tla against W0 rev 6.8, R-100, R-101 and ADR-0021 Amendment 1. The stop windows, finish-the-stop, NoLaunchAfterStop and the classifier hold. R-101 settles F-1 and removes the seal and alarm hazards it would have caused, but leaves the design text stale. Seven majors: stale R-101 text and the step 4 pending definition, run-level state not rebuilt on resume, no lock heartbeat during resume, pid reuse ignores the recorded creation time, segment ordinal and ordering, the HB-LED-005 wedge, and the pid-alive exit. PASS WITH CONDITIONS.",
      "tags": [],
      "links": [
        {
          "to": "design-eval-seam-contracts",
          "rel": "relates-to"
        }
      ],
      "diagrams": [],
      "sourceSha256": "5ebaf54b8e1ccacef5192f971ece7beeef77ffaf40fcc22d02dfa226130585ca"
    },
    {
      "id": "review-eval-pat",
      "path": "docs/design/reviews/eval-review-pat.md",
      "title": "Patterns Expert review of the Evaluation Campaign design slices (Adversary Mode)",
      "type": "doc",
      "status": "draft",
      "owner": "@timianmalloo",
      "phase": "",
      "reviewBy": "2026-10-17",
      "reviewSuggested": [],
      "summary": "One Patterns Expert (RV-PAT) lens file for the Evaluation Campaign: one section per reviewed slice, appended per batch. Findings carry location, severity, evidence, fix and confidence. Advisory lens; a pattern survives only if the Simplifier also clears it.",
      "tags": [
        "review",
        "patterns-expert",
        "evaluation-campaign",
        "wave-1"
      ],
      "links": [
        {
          "to": "design-eval-seam-contracts",
          "rel": "relates-to"
        }
      ],
      "diagrams": [],
      "sourceSha256": "18c21e232bd2506fa8cc02c361491fffccd6db12006110fa278c0653d98c904b"
    },
    {
      "id": "review-eval-pat-w1a",
      "path": "docs/design/reviews/eval-review-pat-w1a.md",
      "title": "Patterns Expert review of W1-A, arms v2 (Adversary Mode)",
      "type": "doc",
      "status": "draft",
      "owner": "@timianmalloo",
      "phase": "",
      "reviewBy": "2026-10-17",
      "reviewSuggested": [],
      "summary": "RV-PAT review of design/eval-arms (ab13f0eb) against W0 rev 2 and R-87..R-93. The hash-keyed blocked order with a bounded redraw and the AST form of G1 survive; the dropped top-level pack makes four readers degrade silently (one of them not covered by SP-A3), G1's token set is narrower than its claim, and the drop is in no seam request.",
      "tags": [
        "review",
        "patterns-expert",
        "evaluation-campaign",
        "wave-1",
        "w1-a"
      ],
      "links": [
        {
          "to": "design-eval-seam-contracts",
          "rel": "relates-to"
        }
      ],
      "diagrams": [],
      "sourceSha256": "a1bef601e5f3cb91dd3f9ebbf9a55408d249813f1a74d0849ebadd9b94ce5e3d"
    },
    {
      "id": "review-eval-pat-w1b",
      "path": "docs/design/reviews/eval-review-pat-w1b.md",
      "title": "Patterns Expert review of W1-B, crash-atomic publish (Adversary Mode)",
      "type": "doc",
      "status": "draft",
      "owner": "@timianmalloo",
      "phase": "",
      "reviewBy": "2026-10-17",
      "reviewSuggested": [],
      "summary": "RV-PAT review of design/eval-atomic-publish (67e7dc83) against W0 rev 2 and R-87..R-93. W0 finding 5 (a verify step before the rename) landed in full. One duplicated constant and retry loop against workspace.py, and minor idiom points.",
      "tags": [
        "review",
        "patterns-expert",
        "evaluation-campaign",
        "wave-1",
        "w1-b"
      ],
      "links": [
        {
          "to": "design-eval-seam-contracts",
          "rel": "relates-to"
        }
      ],
      "diagrams": [],
      "sourceSha256": "679de9c8f28e2b6684cd7282e3dc83c533ed0715fadc8d1b9ae839715a0cde46"
    },
    {
      "id": "review-eval-pat-w1c",
      "path": "docs/design/reviews/eval-review-pat-w1c.md",
      "title": "Patterns Expert review of W1-C: campaign record and bench campaign (Adversary Mode)",
      "type": "doc",
      "status": "draft",
      "owner": "@timianmalloo",
      "phase": "",
      "reviewBy": "2026-10-17",
      "reviewSuggested": [],
      "summary": "RV-PAT review of docs/design/eval-campaign-record.md (design/eval-campaign-record, ae21488b, 61338062) against W0 rev 3 and R-87..R-96. One blocking finding: the state table leaves no legal way to re-pilot after a fix in the registered state. The acquire_then_probe protocol is sound but its signature fits one probe, not a set. Gate BLOCK.",
      "tags": [
        "review",
        "patterns-expert",
        "evaluation-campaign",
        "wave-1"
      ],
      "links": [
        {
          "to": "design-eval-seam-contracts",
          "rel": "relates-to"
        }
      ],
      "diagrams": [],
      "sourceSha256": "3fdf783e77176a6fc5fefd9c0461a9aa9269cc65eb1b32369b646e6d4abda6ff"
    },
    {
      "id": "review-eval-pat-w1d",
      "path": "docs/design/reviews/eval-review-pat-w1d.md",
      "title": "Patterns Expert review of W1-D, engine identity (Adversary Mode)",
      "type": "doc",
      "status": "draft",
      "owner": "@timianmalloo",
      "phase": "",
      "reviewBy": "2026-10-17",
      "reviewSuggested": [],
      "summary": "RV-PAT review of design/eval-identity (71a15a0b) against W0 rev 2 and R-87..R-93. The injected check, the single CLASSES table, import_graph.py and the refusal of a tooling class survive; the refusal's cost model prices only grade-side edits and omits the run-side shared kernel, the launch check's reference identity is unfiled, and the SUBPROCESS_CALLERS mapping inherits a matcher that misses aliased imports. telemetry/* is provisional.",
      "tags": [
        "review",
        "patterns-expert",
        "evaluation-campaign",
        "wave-1",
        "w1-d"
      ],
      "links": [
        {
          "to": "design-eval-seam-contracts",
          "rel": "relates-to"
        }
      ],
      "diagrams": [],
      "sourceSha256": "7da33ff71d59e17bf028b3732ab744578caad0d450be6c98b5c7488d6433bbde"
    },
    {
      "id": "review-eval-pat-w1e",
      "path": "docs/design/reviews/eval-review-pat-w1e.md",
      "title": "Patterns Expert review of W1-E, discriminate and readiness (Adversary Mode)",
      "type": "doc",
      "status": "draft",
      "owner": "@timianmalloo",
      "phase": "",
      "reviewBy": "2026-10-17",
      "reviewSuggested": [],
      "summary": "RV-PAT review of design/eval-discriminate (549f7bc4) against W0 rev 5 and R-98. The SyntheticLauncher Strategy and the overlay rule conform. Twelve findings: the baseline compare still defines \"a manifest seen from one task\" a second time, the variant compare has no readiness row or code, three copies of the overlay path rule, a re-implemented env filter, the clauses.json hand-off by path arithmetic, and R-98 residue. BLOCK until applied.",
      "tags": [
        "review",
        "patterns-expert",
        "evaluation-campaign",
        "wave-1",
        "w1-e"
      ],
      "links": [
        {
          "to": "design-eval-seam-contracts",
          "rel": "relates-to"
        }
      ],
      "diagrams": [],
      "sourceSha256": "241c30e969a19d20da3dd758b06738e495f9fb2dea3a51e11fdd8acb5e703cd8"
    },
    {
      "id": "review-eval-pat-w1f",
      "path": "docs/design/reviews/eval-review-pat-w1f.md",
      "title": "Patterns Expert review of W1-F, the property grader (Adversary Mode)",
      "type": "doc",
      "status": "draft",
      "owner": "@timianmalloo",
      "phase": "",
      "reviewBy": "2026-10-17",
      "reviewSuggested": [],
      "summary": "RV-PAT review of design/eval-property-grader (441da4ba, e41289a2) against W0 rev 2 (3c1c9827). Patterns named correctly, four divergences from W0 rev 2 flagged as seams, no blocker.",
      "tags": [
        "review",
        "patterns-expert",
        "evaluation-campaign",
        "wave-1",
        "w1-f"
      ],
      "links": [
        {
          "to": "design-eval-seam-contracts",
          "rel": "relates-to"
        }
      ],
      "diagrams": [],
      "sourceSha256": "01c7cc579b70df928bcc210eb0ba15aa7a36ba039c6751ca67f72510eb413c61"
    },
    {
      "id": "review-eval-pat-w1g",
      "path": "docs/design/reviews/eval-review-pat-w1g.md",
      "title": "Patterns Expert review of W1-G, catalog 0.7 (Adversary Mode)",
      "type": "doc",
      "status": "draft",
      "owner": "@timianmalloo",
      "phase": "",
      "reviewBy": "2026-10-17",
      "reviewSuggested": [],
      "summary": "RV-PAT review of design/eval-catalog-0-7 (b0987941) against W0 rev 2 and R-87..R-93. The owner rule and also_graded_by survive the Simplifier check; one real gap (a non-owner formal grader emitting pass_at_1 trips HB-GRD-004), an incomplete reader sweep for the new key, and minor idiom points. RV-TA findings are not repeated.",
      "tags": [
        "review",
        "patterns-expert",
        "evaluation-campaign",
        "wave-1",
        "w1-g"
      ],
      "links": [
        {
          "to": "design-eval-seam-contracts",
          "rel": "relates-to"
        }
      ],
      "diagrams": [],
      "sourceSha256": "c33ac9d8f236927e6121743dd55d504e18253c268c91cef111867c973d182657"
    },
    {
      "id": "review-eval-pat-w1h",
      "path": "docs/design/reviews/eval-review-pat-w1h.md",
      "title": "Patterns Expert review of W1-H: power, verdicts, gates, report section 3 (Adversary Mode)",
      "type": "doc",
      "status": "draft",
      "owner": "@timianmalloo",
      "phase": "",
      "reviewBy": "2026-10-17",
      "reviewSuggested": [],
      "summary": "RV-PAT review of docs/design/eval-power-verdicts.md (design/eval-power-verdicts, 2a9faa3c, b5509d66) against W0 rev 3 and R-87..R-96. The design predates R-96; the holm level_rule disclosure and its second test row are missing. Six findings, no blocking, gate PASS WITH CONDITIONS.",
      "tags": [
        "review",
        "patterns-expert",
        "evaluation-campaign",
        "wave-1"
      ],
      "links": [
        {
          "to": "design-eval-seam-contracts",
          "rel": "relates-to"
        }
      ],
      "diagrams": [],
      "sourceSha256": "bd2a44d2bc529215f326d6c51aa8dac31d3dd05bce58e60627170d2f80cded7d"
    },
    {
      "id": "review-eval-pat-w1i",
      "path": "docs/design/reviews/eval-review-pat-w1i.md",
      "title": "Patterns Expert review of W1-I, security tasks S1 and S2 (Adversary Mode)",
      "type": "doc",
      "status": "draft",
      "owner": "@timianmalloo",
      "phase": "",
      "reviewBy": "2026-10-17",
      "reviewSuggested": [],
      "summary": "RV-PAT review of design/eval-security-tasks (2fc8906b) against W0 rev 2, R-87..R-94 and the W1-F rev 2 property grader. One blocking seam disagreement: S1 needs app.kind wsgi with a factory, which W1-F rev 2 does not build in E1 and tells W1-I not to use. Patterns, folder shape, expected values and naming otherwise fit.",
      "tags": [
        "review",
        "patterns-expert",
        "evaluation-campaign",
        "wave-1",
        "w1-i"
      ],
      "links": [
        {
          "to": "design-eval-seam-contracts",
          "rel": "relates-to"
        }
      ],
      "diagrams": [],
      "sourceSha256": "325ed61a2612279876fc84935fa81ca59c7aa6f26bb89407ba4a3311242c7ea3"
    },
    {
      "id": "review-eval-pat-w1j",
      "path": "docs/design/reviews/eval-review-pat-w1j.md",
      "title": "W1-J multi-turn: Patterns Expert lens review",
      "type": "doc",
      "status": "draft",
      "owner": "@timianmalloo",
      "phase": "",
      "reviewBy": "2026-10-17",
      "reviewSuggested": [],
      "summary": "Adversary-mode review of docs/design/eval-multi-turn.md (branch design/eval-multi-turn, 6b838ff2) by the Patterns Expert lens: session protocol, the _attempt turn loop, the snapshot as a Memento, the turn-<n> archive layout, KEYS and the final-rows filter, the shared append_missing_rows helper (a seam disagreement with W1-B), and the check_models.py extension. RV-TA's findings are not repeated.",
      "tags": [],
      "links": [
        {
          "to": "design-eval-seam-contracts",
          "rel": "relates-to"
        }
      ],
      "diagrams": [],
      "sourceSha256": "0820df82326c77df02683b9cd20f7d2cc707197ea7c89272ef29de5157afc16e"
    },
    {
      "id": "review-eval-pat-w1k",
      "path": "docs/design/reviews/eval-review-pat-w1k.md",
      "title": "Patterns Expert review of W1-K, resume, liveness and the alarm (Adversary Mode)",
      "type": "doc",
      "status": "draft",
      "owner": "@timianmalloo",
      "phase": "",
      "reviewBy": "2026-10-17",
      "reviewSuggested": [],
      "summary": "RV-PAT review of design/eval-resume rev 1.1 (315cf1d4) against W0 rev 6.8, R-100 and ADR-0021 with Amendment 1. The reconcile-from-log and the one-input classifier are sound; one seam defect (X-K1 cannot reach its own tests), one contradiction (a finished stop still alarms), and five smaller pattern gaps. No pattern is named in the doc.",
      "tags": [
        "review",
        "patterns-expert",
        "evaluation-campaign",
        "wave-1",
        "w1-k"
      ],
      "links": [
        {
          "to": "design-eval-seam-contracts",
          "rel": "relates-to"
        }
      ],
      "diagrams": [],
      "sourceSha256": "56c52b805ffbf97db1f169cf3209fab2cc45e45ebfeddf3b536703b3a377d624"
    },
    {
      "id": "review-eval-pat-w1l",
      "path": "docs/design/reviews/eval-review-pat-w1l.md",
      "title": "Patterns Expert review of W1-L, the eight property tasks (Adversary Mode)",
      "type": "doc",
      "status": "draft",
      "owner": "@timianmalloo",
      "phase": "",
      "reviewBy": "2026-10-17",
      "reviewSuggested": [],
      "summary": "RV-PAT review of design/eval-property-tasks (5da93d91) against W0 rev 3, R-87..R-96, the merged W1-F strategy and registration pattern, W1-G catalog 0.7 and W1-I's task pattern. The pin, NOTICE, wrong-app and variant pattern conforms. Seven findings: an E2/E4 phasing contradiction for the shared product-line counter, an agent-editable vendored library, an under-specified fault-case predicate, and strategy and catalog fit gaps. PASS WITH CONDITIONS.",
      "tags": [
        "review",
        "patterns-expert",
        "evaluation-campaign",
        "wave-1",
        "w1-l"
      ],
      "links": [
        {
          "to": "design-eval-seam-contracts",
          "rel": "relates-to"
        }
      ],
      "diagrams": [],
      "sourceSha256": "10fe24ae90af7b74cfa61d438f46a9f2c93c3d13f4f7b932fcb9e83dac2e94af"
    },
    {
      "id": "review-eval-sec",
      "path": "docs/design/reviews/eval-review-sec.md",
      "title": "Security & Identity lens review: Evaluation Campaign design slices (Adversary Mode)",
      "type": "doc",
      "status": "draft",
      "owner": "@timianmalloo",
      "phase": "",
      "reviewBy": "2026-10-17",
      "reviewSuggested": [],
      "summary": "The Security & Identity lens's findings on the Evaluation Campaign designs, one section per slice, appended per batch. Each section ends with one gate line. Findings only: no design is edited here.",
      "tags": [
        "review",
        "security",
        "evaluation-campaign",
        "wave-1"
      ],
      "links": [
        {
          "to": "design-eval-seam-contracts",
          "rel": "relates-to"
        }
      ],
      "diagrams": [],
      "sourceSha256": "14ae047db1757d5186e8d30ae44e1a1ba5d1b8a5a6e69fe7edfe55d91721ccf4"
    },
    {
      "id": "review-eval-sec-s2spike",
      "path": "docs/design/reviews/eval-review-sec-s2spike.md",
      "title": "Security & Identity review of the redesigned S2 spike (R-99) (Adversary Mode)",
      "type": "doc",
      "status": "draft",
      "owner": "@timianmalloo",
      "phase": "",
      "reviewBy": "2026-10-17",
      "reviewSuggested": [],
      "summary": "Security & Identity gate on the S2 spike under R-99 (build/eval-x-i-s2b, 12f828df). The letter of R-99 holds; the tamper-refusal probe never reaches bottle's signature check, the leak probe does not scan logs, and the pin lacks a content hash. PASS WITH CONDITIONS, 6 findings.",
      "tags": [
        "review",
        "security",
        "evaluation-campaign",
        "s2",
        "r99"
      ],
      "links": [
        {
          "to": "design-eval-seam-contracts",
          "rel": "relates-to"
        },
        {
          "to": "review-eval-sec",
          "rel": "refines"
        }
      ],
      "diagrams": [],
      "sourceSha256": "c2ca5e46f22359e86aead167e27848a1404090895537ea54efdf14f565626f35"
    },
    {
      "id": "review-eval-sec-w1b",
      "path": "docs/design/reviews/eval-review-sec-w1b.md",
      "title": "Security & Identity review of W1-B: crash-atomic publish (Adversary Mode)",
      "type": "doc",
      "status": "draft",
      "owner": "@timianmalloo",
      "phase": "",
      "reviewBy": "2026-10-17",
      "reviewSuggested": [],
      "summary": "Security & Identity gate on W1-B (design/eval-atomic-publish, 67e7dc83) against W0 rev 2. W0 F10 landed (nonce temp name, exclusive create, lstat-first non-recursing sweep, tests named). Open: ignore patterns hide planted content from the tamper check, the temp-to-final link has no identity check, and the symlink branch is unmeasured with a test that can skip everywhere. PASS WITH CONDITIONS, 8 findings.",
      "tags": [
        "review",
        "security",
        "evaluation-campaign",
        "wave-1",
        "w1-b"
      ],
      "links": [
        {
          "to": "design-eval-seam-contracts",
          "rel": "relates-to"
        },
        {
          "to": "review-eval-sec",
          "rel": "refines"
        }
      ],
      "diagrams": [],
      "sourceSha256": "72070286c2458a4a228c43e457b4258dfcd4c72b5150d27482371f62e1d0d075"
    },
    {
      "id": "review-eval-sec-w1c",
      "path": "docs/design/reviews/eval-review-sec-w1c.md",
      "title": "Security & Identity review of W1-C: campaign record and bench campaign (Adversary Mode)",
      "type": "doc",
      "status": "draft",
      "owner": "@timianmalloo",
      "phase": "",
      "reviewBy": "2026-10-17",
      "reviewSuggested": [],
      "summary": "Security & Identity gate on W1-C (design/eval-campaign-record, ae21488b + 61338062) against W0 rev 3 and R-87..R-96. Tamper tests, lock-as-regular-file and the three ignore lines are mostly sound. Open: unvalidated campaign id writes outside the folder, symlinked ledger or folders, a status-code-keyed git witness blind to ignored paths, and attach freezing on a chain-derived stamp while binding no plan content.",
      "tags": [
        "review",
        "security",
        "evaluation-campaign",
        "wave-1",
        "w1-c"
      ],
      "links": [
        {
          "to": "design-eval-seam-contracts",
          "rel": "relates-to"
        },
        {
          "to": "review-eval-sec",
          "rel": "refines"
        }
      ],
      "diagrams": [],
      "sourceSha256": "a3757d6ce6731cd6180552d45504592b69bc251c9557de511549053c7c98b43a"
    },
    {
      "id": "review-eval-sec-w1e",
      "path": "docs/design/reviews/eval-review-sec-w1e.md",
      "title": "Security & Identity review of W1-E: discriminate, the synthetic profile and readiness (Adversary Mode)",
      "type": "doc",
      "status": "draft",
      "owner": "@timianmalloo",
      "phase": "",
      "reviewBy": "2026-10-17",
      "reviewSuggested": [],
      "summary": "Security & Identity gate on W1-E (design/eval-discriminate, 549f7bc4) judged against W0 rev 5 and R-98. Variants are data-only and the overlay is mostly safe, but the overlay misses destination links and Windows name forms, the variant edits have no path containment, the synthetic environment is a denylist that contradicts itself, and the attach path does not refuse a discrimination run. PASS WITH CONDITIONS, 10 findings.",
      "tags": [
        "review",
        "security",
        "evaluation-campaign",
        "wave-1",
        "w1-e"
      ],
      "links": [
        {
          "to": "design-eval-seam-contracts",
          "rel": "relates-to"
        },
        {
          "to": "review-eval-sec",
          "rel": "refines"
        }
      ],
      "diagrams": [],
      "sourceSha256": "89e40f91a92bd46f8371806d74554bd9ff040ff776bf00655485a55eff57447d"
    },
    {
      "id": "review-eval-sec-w1f",
      "path": "docs/design/reviews/eval-review-sec-w1f.md",
      "title": "Security & Identity review of W1-F: hidden-check runner and property grader (Adversary Mode)",
      "type": "doc",
      "status": "draft",
      "owner": "@timianmalloo",
      "phase": "",
      "reviewBy": "2026-10-17",
      "reviewSuggested": [],
      "summary": "Security & Identity gate on W1-F (design/eval-property-grader, 441da4ba and e41289a2) against W0 rev 2. Both carried-over conditions are met in the design text; the forged-document fixture is named as a red test but the spike scripts are not committed and no positive control is named. PASS WITH CONDITIONS, 8 findings.",
      "tags": [
        "review",
        "security",
        "evaluation-campaign",
        "wave-1",
        "w1-f"
      ],
      "links": [
        {
          "to": "design-eval-seam-contracts",
          "rel": "relates-to"
        },
        {
          "to": "review-eval-sec",
          "rel": "refines"
        }
      ],
      "diagrams": [],
      "sourceSha256": "18dce2da2879aae256e87796b1574fc932971d049d81dc98e9560bf7a4785290"
    },
    {
      "id": "review-eval-sec-w1i",
      "path": "docs/design/reviews/eval-review-sec-w1i.md",
      "title": "Security & Identity review of W1-I: security tasks S1 and S2 (Adversary Mode)",
      "type": "doc",
      "status": "draft",
      "owner": "@timianmalloo",
      "phase": "",
      "reviewBy": "2026-10-17",
      "reviewSuggested": [],
      "summary": "Security & Identity gate on W1-I (design/eval-security-tasks, 2fc8906b) against W0 rev 2 and R-87..R-94. The latent requirement is latent, the probes run in the probe-host child, both tasks declare no build and use MIT bases pinned by full commit. The secret-leak probes scan one of two tokens, S2's signed cookies are pickle-based, and the new `app` keys are not in W0. PASS WITH CONDITIONS, 8 findings.",
      "tags": [
        "review",
        "security",
        "evaluation-campaign",
        "wave-1",
        "w1-i"
      ],
      "links": [
        {
          "to": "design-eval-seam-contracts",
          "rel": "relates-to"
        },
        {
          "to": "review-eval-sec",
          "rel": "refines"
        }
      ],
      "diagrams": [],
      "sourceSha256": "d286b2c9ef11f1e8da31814acf3050e406632059c11df71aab9860afb37325f7"
    },
    {
      "id": "review-eval-sim",
      "path": "docs/design/reviews/eval-review-sim.md",
      "title": "Simplifier lens review of the Evaluation Campaign designs (RV-SIM)",
      "type": "doc",
      "status": "draft",
      "owner": "@timianmalloo",
      "phase": "",
      "reviewBy": "2026-10-17",
      "reviewSuggested": [],
      "summary": "The Simplifier's Adversary Mode findings on the Evaluation Campaign design slices, one section per slice, appended per batch. Soft veto on unjustified complexity. First section: W0 seam contracts at main 5092455c.",
      "tags": [],
      "links": [
        {
          "to": "design-eval-seam-contracts",
          "rel": "relates-to"
        }
      ],
      "diagrams": [],
      "sourceSha256": "c6be0e7d4145dd1fcd2e234a164a452b53865a3a38867fa0280aaae2e881dc76"
    },
    {
      "id": "review-eval-sim-w1a",
      "path": "docs/design/reviews/eval-review-sim-w1a.md",
      "title": "Simplifier lens review of W1-A, arms v2",
      "type": "doc",
      "status": "draft",
      "owner": "@timianmalloo",
      "phase": "",
      "reviewBy": "2026-10-17",
      "reviewSuggested": [],
      "summary": "RV-SIM (Simplifier, soft veto) findings on docs/design/eval-arms.md (design/eval-arms, ab13f0eb) against W0 rev 2 and R-87..R-93 on main. The hash-keyed blocked order with a bounded redraw earns its place; HB-PLN-004 and G1 earn theirs. Three tests and one comparison table are weight that can go.",
      "tags": [],
      "links": [
        {
          "to": "design-eval-seam-contracts",
          "rel": "relates-to"
        }
      ],
      "diagrams": [],
      "sourceSha256": "5ce2b0abc3ef7877004b253d386bfafab795fbe68e9173d793ee018590ad446f"
    },
    {
      "id": "review-eval-sim-w1b",
      "path": "docs/design/reviews/eval-review-sim-w1b.md",
      "title": "Simplifier lens review of W1-B, crash-atomic publish",
      "type": "doc",
      "status": "draft",
      "owner": "@timianmalloo",
      "phase": "",
      "reviewBy": "2026-10-17",
      "reviewSuggested": [],
      "summary": "RV-SIM (Simplifier, soft veto) findings on docs/design/eval-atomic-publish.md (design/eval-atomic-publish, 67e7dc83) against W0 rev 2 section 4 and R-87..R-93 on main. The two helpers, the strict verify and the temp reader fix earn their place; recover_archive is built two phases early and the test and telemetry surface has removable pieces.",
      "tags": [],
      "links": [
        {
          "to": "design-eval-seam-contracts",
          "rel": "relates-to"
        }
      ],
      "diagrams": [],
      "sourceSha256": "be00c56fc382061170f39bd21fcc7eeafc8c064fbb4100188b64e39c0dead710"
    },
    {
      "id": "review-eval-sim-w1c",
      "path": "docs/design/reviews/eval-review-sim-w1c.md",
      "title": "Simplifier lens review of W1-C, campaign record and bench campaign",
      "type": "doc",
      "status": "draft",
      "owner": "@timianmalloo",
      "phase": "",
      "reviewBy": "2026-10-17",
      "reviewSuggested": [],
      "summary": "RV-SIM (Simplifier, soft veto) findings on docs/design/eval-campaign-record.md (design/eval-campaign-record, ae21488b, 61338062) against W0 rev 3 and R-87..R-96. OI-4 answered: ring_run.attached.tag is constant and can go in the SR-C2 request. status and verify are specified both as read-only and as full lock-probe-sweep sessions.",
      "tags": [],
      "links": [
        {
          "to": "design-eval-seam-contracts",
          "rel": "relates-to"
        }
      ],
      "diagrams": [],
      "sourceSha256": "9b10d9156950d3ad3726972d605bcb28670275889eb8ad1478f6f98f3c080448"
    },
    {
      "id": "review-eval-sim-w1d",
      "path": "docs/design/reviews/eval-review-sim-w1d.md",
      "title": "Simplifier lens review of W1-D, engine identity",
      "type": "doc",
      "status": "draft",
      "owner": "@timianmalloo",
      "phase": "",
      "reviewBy": "2026-10-17",
      "reviewSuggested": [],
      "summary": "RV-SIM (Simplifier, soft veto) findings on docs/design/eval-identity.md (design/eval-identity, 71a15a0b) against W0 rev 2 and R-87..R-93 on main. The refusal of a third class is accepted; tests/import_graph.py earns its place; the second-read torn-read guard and the doubled grade-side hash need a reason or a trim. telemetry/* is provisional.",
      "tags": [],
      "links": [
        {
          "to": "design-eval-seam-contracts",
          "rel": "relates-to"
        }
      ],
      "diagrams": [],
      "sourceSha256": "c862b5fa4bdd0dc807da71facdea81ca7c5c0fa4cc7b2c8839eaddf8d481ac64"
    },
    {
      "id": "review-eval-sim-w1e",
      "path": "docs/design/reviews/eval-review-sim-w1e.md",
      "title": "Simplifier review of W1-E (discriminate, synthetic profile, readiness)",
      "type": "doc",
      "status": "draft",
      "owner": "@timianmalloo",
      "phase": "",
      "reviewBy": "2026-10-17",
      "reviewSuggested": [],
      "summary": "RV-SIM (Adversary Mode, soft veto) on design/eval-discriminate 549f7bc4 against W0 rev 5 and R-98. PASS WITH CONDITIONS: the SyntheticLauncher, variants-as-cells and the HB-RDY set are the smallest correct mechanism for E1; defer the empty FROZEN registry (HB-RDY-009) to E4, fold about ten test nodes, key the run link by record name, and drop the build re-hash.",
      "tags": [],
      "links": [
        {
          "to": "design-eval-seam-contracts",
          "rel": "relates-to"
        }
      ],
      "diagrams": [],
      "sourceSha256": "b1640f5c6c09d40b7f2776d7cde366b5e07f445130d69098148ffcd01416430e"
    },
    {
      "id": "review-eval-sim-w1f",
      "path": "docs/design/reviews/eval-review-sim-w1f.md",
      "title": "Simplifier lens review of W1-F, the property grader",
      "type": "doc",
      "status": "draft",
      "owner": "@timianmalloo",
      "phase": "",
      "reviewBy": "2026-10-17",
      "reviewSuggested": [],
      "summary": "RV-SIM (Simplifier, soft veto) findings on docs/design/eval-property-grader.md (design/eval-property-grader, 441da4ba and e41289a2) checked against W0 rev 2 on main 3c1c9827.",
      "tags": [],
      "links": [
        {
          "to": "design-eval-seam-contracts",
          "rel": "relates-to"
        }
      ],
      "diagrams": [],
      "sourceSha256": "e02b9c406c50e4ac255322f67b483331ebc51b943a7b5c0e97b4f27fee167473"
    },
    {
      "id": "review-eval-sim-w1g",
      "path": "docs/design/reviews/eval-review-sim-w1g.md",
      "title": "Simplifier lens review of W1-G, catalog 0.7",
      "type": "doc",
      "status": "draft",
      "owner": "@timianmalloo",
      "phase": "",
      "reviewBy": "2026-10-17",
      "reviewSuggested": [],
      "summary": "RV-SIM (Simplifier, soft veto) findings on docs/design/eval-catalog-0-7.md (design/eval-catalog-0-7, b0987941) against W0 rev 2 and R-87..R-93 on main. also_graded_by is the smallest correct mechanism; the (e) exception and corrected_from record are built for a case the design itself shows cannot occur.",
      "tags": [],
      "links": [
        {
          "to": "design-eval-seam-contracts",
          "rel": "relates-to"
        }
      ],
      "diagrams": [],
      "sourceSha256": "884d2fa0b86d7e0e0bb2a50e1f1d05093778cf7750b02c3d12b49360f297f621"
    },
    {
      "id": "review-eval-sim-w1h",
      "path": "docs/design/reviews/eval-review-sim-w1h.md",
      "title": "Simplifier lens review of W1-H, power, verdicts, gates and report section 3",
      "type": "doc",
      "status": "draft",
      "owner": "@timianmalloo",
      "phase": "",
      "reviewBy": "2026-10-17",
      "reviewSuggested": [],
      "summary": "RV-SIM (Simplifier, soft veto) findings on docs/design/eval-power-verdicts.md (design/eval-power-verdicts, 2a9faa3c, b5509d66) against W0 rev 3 and R-87..R-96. The core is the smallest correct shape. About a third of the label, statement and sweep rows duplicate another row's mutant; one seam with W1-C (pilot arity, admission) is open.",
      "tags": [],
      "links": [
        {
          "to": "design-eval-seam-contracts",
          "rel": "relates-to"
        }
      ],
      "diagrams": [],
      "sourceSha256": "f51e5bd95ac3a1c9151effb97dd8438a9be7ccecf0caaa66582e358155680613"
    },
    {
      "id": "review-eval-sim-w1i",
      "path": "docs/design/reviews/eval-review-sim-w1i.md",
      "title": "Simplifier lens review of W1-I, security tasks S1 and S2",
      "type": "doc",
      "status": "draft",
      "owner": "@timianmalloo",
      "phase": "",
      "reviewBy": "2026-10-17",
      "reviewSuggested": [],
      "summary": "RV-SIM (Simplifier, soft veto) findings on docs/design/eval-security-tasks.md (design/eval-security-tasks, 2fc8906b) against W0 rev 2 and R-87..R-94 on main. All five probe-host asks are needed by S1 and none is S2-only. The S2 probe list is premature for E1. Ten probes reduce to nine or eight, eleven hidden tests to nine, and about six of 21 tests repeat a check that W1-F, X-E or another test already owns.",
      "tags": [],
      "links": [
        {
          "to": "design-eval-seam-contracts",
          "rel": "relates-to"
        }
      ],
      "diagrams": [],
      "sourceSha256": "a97c88934f6ac7af7f54eff8fc95d769ce89b0702cfc78f842975db0fbe5afe6"
    },
    {
      "id": "review-eval-sim-w1j",
      "path": "docs/design/reviews/eval-review-sim-w1j.md",
      "title": "Simplifier lens review of W1-J, multi-turn attempt and the TLA+ model",
      "type": "doc",
      "status": "draft",
      "owner": "@timianmalloo",
      "phase": "",
      "reviewBy": "2026-10-17",
      "reviewSuggested": [],
      "summary": "RV-SIM (Simplifier, soft veto) findings on docs/design/eval-multi-turn.md (design/eval-multi-turn, 08fabe34, 6b838ff2) against W0 rev 6 and the rulings on main. The mechanism earns its place for E2. The check_models.py change can shrink to data rows by reusing the existing WIDER substitution, the US-44 run should be one-time evidence, one of the two in-place variants is the same guard, and the resume-owned parts wait for W1-K.",
      "tags": [],
      "links": [
        {
          "to": "design-eval-seam-contracts",
          "rel": "relates-to"
        }
      ],
      "diagrams": [],
      "sourceSha256": "be3d70f4fd74e78422394d9d06b72a133c2360746f4099ee7f464be2e074a271"
    },
    {
      "id": "review-eval-sim-w1k",
      "path": "docs/design/reviews/eval-review-sim-w1k.md",
      "title": "Simplifier review of W1-K, resume, liveness and the alarm (Adversary Mode)",
      "type": "doc",
      "status": "draft",
      "owner": "@timianmalloo",
      "phase": "",
      "reviewBy": "2026-10-17",
      "reviewSuggested": [],
      "summary": "RV-SIM review of design/eval-resume rev 1.1 (315cf1d4). The reconcile design is the smallest correct core; the proof is larger than it needs to be (the prefix sweep already kills the classifier mutants), and the alarm channel ships two deliveries where one reaches the sleeping operator. Soft veto: conditions, no block.",
      "tags": [
        "review",
        "simplifier",
        "evaluation-campaign",
        "wave-1",
        "w1-k"
      ],
      "links": [
        {
          "to": "design-eval-seam-contracts",
          "rel": "relates-to"
        }
      ],
      "diagrams": [],
      "sourceSha256": "429696d3b1db788fab0e26112c4bc9cdf94fd666c7235a320517c911a883c940"
    },
    {
      "id": "review-eval-sim-w1l",
      "path": "docs/design/reviews/eval-review-sim-w1l.md",
      "title": "Simplifier review of W1-L (property tasks and four graders)",
      "type": "doc",
      "status": "draft",
      "owner": "@timianmalloo",
      "phase": "",
      "reviewBy": "2026-10-17",
      "reviewSuggested": [],
      "summary": "RV-SIM (Adversary Mode, soft veto) on design/eval-property-tasks 5da93d91. PASS WITH CONDITIONS: cut verified_before_use until SR-L1, defer the noguess resolver, fix the E2/E4 phase inversion of product_lines and in_radius, remove dead resilience cases and duplicate variants, and fold the per-task test rows into readiness.",
      "tags": [],
      "links": [
        {
          "to": "design-eval-seam-contracts",
          "rel": "relates-to"
        }
      ],
      "diagrams": [],
      "sourceSha256": "9fa4e7bda99adf13192cab2b73f7eabd0cdc3ac79153b75728af9182626633fd"
    },
    {
      "id": "review-eval-sre-w1d",
      "path": "docs/design/reviews/eval-review-sre-w1d.md",
      "title": "W1-D engine identity design review: SRE lens",
      "type": "doc",
      "status": "draft",
      "owner": "@timianmalloo",
      "phase": "Enterprise evaluation: Wave 1 gate reviews",
      "reviewBy": "2026-10-17",
      "reviewSuggested": [],
      "summary": "SRE (Adversary Mode) review of W1-D at 71a15a0b. The per-launch recheck is measured on the right row and fails closed, but it runs synchronously on the supervisory loop with unbounded retries, the stop is not actionable from bench status, and torn-read recoveries and the grading interpreter are not recorded. PASS WITH CONDITIONS.",
      "tags": [
        "review",
        "sre",
        "evaluation-campaign",
        "wave-1",
        "w1-d"
      ],
      "links": [
        {
          "to": "design-eval-seam-contracts",
          "rel": "relates-to"
        }
      ],
      "diagrams": [],
      "sourceSha256": "5e3029dbb2a5d8e339f0be0e3f87abfd191a10bd9becba6945130197d89e7d8a"
    },
    {
      "id": "review-eval-sre-w1j",
      "path": "docs/design/reviews/eval-review-sre-w1j.md",
      "title": "W1-J multi-turn design review: SRE lens",
      "type": "doc",
      "status": "draft",
      "owner": "@timianmalloo",
      "phase": "Enterprise evaluation: Wave 1 gate reviews",
      "reviewBy": "2026-10-17",
      "reviewSuggested": [],
      "summary": "SRE (Adversary Mode) review of W1-J at 6b838ff2 against W0 rev 6. Per-turn timing, snapshot cost and spend summing are measurable by default, and the budget fix and end_turn-only rule are right. But the turn loop writes no turn_ended for the very turns that stop the attempt, bench status restarts its clock at turn 2, and the copy-cost spike did not measure the fsync-and-verify path. PASS WITH CONDITIONS.",
      "tags": [
        "review",
        "sre",
        "evaluation-campaign",
        "wave-1",
        "w1-j"
      ],
      "links": [
        {
          "to": "design-eval-seam-contracts",
          "rel": "relates-to"
        }
      ],
      "diagrams": [],
      "sourceSha256": "13c7180017ca42ed74ed764d8435d9a46f5aa7a7e14f60dd4480d2f61a008ba6"
    },
    {
      "id": "review-eval-sre-w1k",
      "path": "docs/design/reviews/eval-review-sre-w1k.md",
      "title": "W1-K resume, liveness and the alarm channel: SRE lens review",
      "type": "doc",
      "status": "draft",
      "owner": "@timianmalloo",
      "phase": "",
      "reviewBy": "2026-10-17",
      "reviewSuggested": [],
      "summary": "Adversary-mode review of docs/design/eval-resume.md (branch design/eval-resume, 315cf1d4, rev 1.1) by the SRE lens: the alarm and the resume disagree on what \"pending\" means, the last_progress_at segment pick is wrong after a grading pass, the default alarm channel does not reach a sleeping operator, and the wrapper can leak the ntfy topic. Twelve findings, condition-setting.",
      "tags": [],
      "links": [
        {
          "to": "design-eval-seam-contracts",
          "rel": "relates-to"
        }
      ],
      "diagrams": [],
      "sourceSha256": "6dbb1b345f2d9c0aca3332938e0ee35c2611ccb9906582d0a48c128a65539c86"
    },
    {
      "id": "review-eval-ta",
      "path": "docs/design/reviews/eval-review-ta.md",
      "title": "Evaluation Campaign design reviews: Test Architect lens",
      "type": "doc",
      "status": "draft",
      "owner": "@timianmalloo",
      "phase": "Enterprise evaluation: Wave 1 gate reviews",
      "reviewBy": "2026-10-17",
      "reviewSuggested": [],
      "summary": "Test Architect (Adversary Mode) findings and gate lines, one section per reviewed slice. W0 first: the contracts are mostly testable, but the guard allowlists are red on arrival, the check outcome precedence is open, and W0 still reads DR-4 as open after R-90.",
      "tags": [
        "review",
        "test-architect",
        "evaluation-campaign",
        "wave-1"
      ],
      "links": [
        {
          "to": "design-eval-seam-contracts",
          "rel": "relates-to"
        }
      ],
      "diagrams": [],
      "sourceSha256": "58aa306fe773223a7bc01e3fdab56fb115aab774568cff79990bd9f9a10cfe52"
    },
    {
      "id": "review-eval-ta-s2spike",
      "path": "docs/design/reviews/eval-review-ta-s2spike.md",
      "title": "Test Architect review of the redesigned S2 spike (R-99) (Adversary Mode)",
      "type": "doc",
      "status": "draft",
      "owner": "@timianmalloo",
      "phase": "",
      "reviewBy": "2026-10-17",
      "reviewSuggested": [],
      "summary": "Test Architect gate on the S2 spike (build/eval-x-i-s2b, 12f828df). The diagonal reproduces and is real for four probes; the tamper probe is live for one input shape only, and two probes pass vacuously on a wrong app. PASS WITH CONDITIONS, 6 findings.",
      "tags": [
        "review",
        "test-architect",
        "evaluation-campaign",
        "s2",
        "r99"
      ],
      "links": [
        {
          "to": "design-eval-seam-contracts",
          "rel": "relates-to"
        },
        {
          "to": "review-eval-ta",
          "rel": "refines"
        }
      ],
      "diagrams": [],
      "sourceSha256": "7d8b3799bb7a2efa2903d5d5117810710a73173cf91579ae146312901756bcec"
    },
    {
      "id": "review-eval-ta-w1a",
      "path": "docs/design/reviews/eval-review-ta-w1a.md",
      "title": "W1-A arms v2 design review: Test Architect lens",
      "type": "doc",
      "status": "draft",
      "owner": "@timianmalloo",
      "phase": "Enterprise evaluation: Wave 1 gate reviews",
      "reviewBy": "2026-10-17",
      "reviewSuggested": [],
      "summary": "Test Architect (Adversary Mode) review of W1-A against W0 rev 2 and R-87..R-93. The EV-17 map is complete and the grid-4 fixture is independent of the new code (derived from the live plan). PASS WITH CONDITIONS: no control that checks the on/off literal sweep outside Python, a real-wiring gap behind a faked install_pack, an architecture test with no red case, and a boundary case for the balance bound.",
      "tags": [
        "review",
        "test-architect",
        "evaluation-campaign",
        "wave-1",
        "w1-a"
      ],
      "links": [
        {
          "to": "design-eval-seam-contracts",
          "rel": "relates-to"
        }
      ],
      "diagrams": [],
      "sourceSha256": "8c74630765c213725014dd41cd1564a01166cdf414a2e480734a367e7d272451"
    },
    {
      "id": "review-eval-ta-w1b",
      "path": "docs/design/reviews/eval-review-ta-w1b.md",
      "title": "W1-B crash-atomic publish design review: Test Architect lens",
      "type": "doc",
      "status": "draft",
      "owner": "@timianmalloo",
      "phase": "Enterprise evaluation: Wave 1 gate reviews",
      "reviewBy": "2026-10-17",
      "reviewSuggested": [],
      "summary": "Test Architect (Adversary Mode) review of W1-B against W0 rev 2 section 4 and R-87..R-93. The kill tests, the 26 mutant map and the recovery table are strong. BLOCK on two controls that cannot fail as specified: the call-site classification test (its allowlist contradicts the tree and it has no red fixture) and the Windows no-fsync branch test (it overwrites the constant a mutant changes).",
      "tags": [
        "review",
        "test-architect",
        "evaluation-campaign",
        "wave-1",
        "w1-b"
      ],
      "links": [
        {
          "to": "design-eval-seam-contracts",
          "rel": "relates-to"
        }
      ],
      "diagrams": [],
      "sourceSha256": "cb42e6a4b9535b9965b731003dd1623120eb42dcab774d1d13f1398b7b968d5e"
    },
    {
      "id": "review-eval-ta-w1c",
      "path": "docs/design/reviews/eval-review-ta-w1c.md",
      "title": "W1-C campaign record and bench campaign design review: Test Architect lens",
      "type": "doc",
      "status": "draft",
      "owner": "@timianmalloo",
      "phase": "Enterprise evaluation: Wave 1 gate reviews",
      "reviewBy": "2026-10-17",
      "reviewSuggested": [],
      "summary": "Test Architect (Adversary Mode) review of W1-C against W0 rev 3, the section 2a testability floor and R-87..R-95. The transition table, the per-command guard / idempotency / refusal / test columns, the git-prefix verify rule and the real-wiring tests (P-3, P-4) are strong. PASS WITH CONDITIONS: skeleton landing order for X-B and X-D is unstated so about 15 tests are red by a missing module, 17 mutants are bare ids, the register-side race has no mutant, and the \"measured over 90 races\" claim has no positive control.",
      "tags": [
        "review",
        "test-architect",
        "evaluation-campaign",
        "wave-1",
        "w1-c"
      ],
      "links": [
        {
          "to": "design-eval-seam-contracts",
          "rel": "relates-to"
        }
      ],
      "diagrams": [],
      "sourceSha256": "550632ad0091f31cf2acb8bc82b6da5f3c812df7b28de7e4b1cdd652bc5ac6fd"
    },
    {
      "id": "review-eval-ta-w1d",
      "path": "docs/design/reviews/eval-review-ta-w1d.md",
      "title": "W1-D engine identity design review: Test Architect lens",
      "type": "doc",
      "status": "draft",
      "owner": "@timianmalloo",
      "phase": "Enterprise evaluation: Wave 1 gate reviews",
      "reviewBy": "2026-10-17",
      "reviewSuggested": [],
      "summary": "Test Architect (Adversary Mode) review of W1-D against W0 rev 2 sections 6, 9, 10, 12 and R-87..R-93. The direction test has five red fixtures and the engine tests are well chosen. BLOCK on the launch recheck wiring (no test fails when cli.py stops passing the check) and on the G2 coverage half (no red fixtures, and the check is not specified to take a root). The telemetry reclassification section is provisional (Owner request pending).",
      "tags": [
        "review",
        "test-architect",
        "evaluation-campaign",
        "wave-1",
        "w1-d"
      ],
      "links": [
        {
          "to": "design-eval-seam-contracts",
          "rel": "relates-to"
        }
      ],
      "diagrams": [],
      "sourceSha256": "56d9113537b7ed9b5fe31112d6906f43b44c370c8a502c4cc40657c84a430193"
    },
    {
      "id": "review-eval-ta-w1e",
      "path": "docs/design/reviews/eval-review-ta-w1e.md",
      "title": "W1-E discriminate design review: Test Architect lens",
      "type": "doc",
      "status": "draft",
      "owner": "@timianmalloo",
      "phase": "Enterprise evaluation: Wave 1 gate reviews",
      "reviewBy": "2026-10-17",
      "reviewSuggested": [],
      "summary": "Test Architect (Adversary Mode) review of W1-E (design/eval-discriminate, 549f7bc4) against W0 rev 5 and R-98. BLOCK: R-HOST and the variant compare assume a check that three of five properties do not have; the campaign identity compare is stale against rev 5 for_task; untrustworthy records trap a legitimate retry. The SCAN-A fixture, T-E1a/T-E1b and the skeleton-first commit are sound in shape.",
      "tags": [
        "review",
        "test-architect",
        "evaluation-campaign",
        "wave-1",
        "w1-e"
      ],
      "links": [
        {
          "to": "design-eval-seam-contracts",
          "rel": "relates-to"
        }
      ],
      "diagrams": [],
      "sourceSha256": "3ee65cc973e552602ae14800354c658ad777f2208ddd748f769867e40c52eee6"
    },
    {
      "id": "review-eval-ta-w1f",
      "path": "docs/design/reviews/eval-review-ta-w1f.md",
      "title": "W1-F property grader design review: Test Architect lens",
      "type": "doc",
      "status": "draft",
      "owner": "@timianmalloo",
      "phase": "Enterprise evaluation: Wave 1 gate reviews",
      "reviewBy": "2026-10-17",
      "reviewSuggested": [],
      "summary": "Test Architect (Adversary Mode) review of W1-F against W0 rev 2. The ADR-0018 red tests are named and can fail. Two blocking gaps: the hidden-tests phase has no suspend control (W0 s3 requires one per phase), and the clean-exit tamper test (my W0 rev 2 condition) is not specified. The design also still disagrees with W0 rev 2 at four points.",
      "tags": [
        "review",
        "test-architect",
        "evaluation-campaign",
        "wave-1",
        "w1-f"
      ],
      "links": [
        {
          "to": "design-eval-seam-contracts",
          "rel": "relates-to"
        }
      ],
      "diagrams": [],
      "sourceSha256": "33124234b26a7c0ad855539c8e39f6b86c2cb274c77313f47cefa734009c60eb"
    },
    {
      "id": "review-eval-ta-w1g",
      "path": "docs/design/reviews/eval-review-ta-w1g.md",
      "title": "W1-G catalog 0.7 design review: Test Architect lens",
      "type": "doc",
      "status": "draft",
      "owner": "@timianmalloo",
      "phase": "Enterprise evaluation: Wave 1 gate reviews",
      "reviewBy": "2026-10-17",
      "reviewSuggested": [],
      "summary": "Test Architect (Adversary Mode) review of W1-G against W0 rev 2 and R-87..R-93. The three-valued _pass fix and the pass rule are well tested. BLOCK on three controls that cannot fail as specified: the cross-version regrade (no red case, and the 0.6 golden's digest is checked by nothing once 0.7 is current), and the (e) exception (clause v and others untested, commit check is a regex).",
      "tags": [
        "review",
        "test-architect",
        "evaluation-campaign",
        "wave-1",
        "w1-g"
      ],
      "links": [
        {
          "to": "design-eval-seam-contracts",
          "rel": "relates-to"
        }
      ],
      "diagrams": [],
      "sourceSha256": "684469f7893d3d5bdf763648f189faf86d5cb8840c9e22c8b73a8151c461ec38"
    },
    {
      "id": "review-eval-ta-w1h",
      "path": "docs/design/reviews/eval-review-ta-w1h.md",
      "title": "W1-H power, verdicts, gates and report section 3 design review: Test Architect lens",
      "type": "doc",
      "status": "draft",
      "owner": "@timianmalloo",
      "phase": "Enterprise evaluation: Wave 1 gate reviews",
      "reviewBy": "2026-10-17",
      "reviewSuggested": [],
      "summary": "Test Architect (Adversary Mode) review of W1-H against W0 rev 3, the section 2a testability floor and R-87..R-96. Exact pins for 93/53/115, the label and statement tables, the conservation test and the R-93 DOM test are strong. PASS WITH CONDITIONS: three named mutants are not killed by the row that names them, one precedence pair has an equivalent mutant, rows that pass on the skeleton can be made red by a better skeleton, the coverage test has a one-sigma margin, and R-96 adds conditions the plan does not yet test.",
      "tags": [
        "review",
        "test-architect",
        "evaluation-campaign",
        "wave-1",
        "w1-h"
      ],
      "links": [
        {
          "to": "design-eval-seam-contracts",
          "rel": "relates-to"
        }
      ],
      "diagrams": [],
      "sourceSha256": "ce30415edd1a56756cec1db3385f29a724821b47f51e6614ce30caedf2f3f7e9"
    },
    {
      "id": "review-eval-ta-w1i",
      "path": "docs/design/reviews/eval-review-ta-w1i.md",
      "title": "W1-I security tasks S1 and S2 design review: Test Architect lens",
      "type": "doc",
      "status": "draft",
      "owner": "@timianmalloo",
      "phase": "Enterprise evaluation: Wave 1 gate reviews",
      "reviewBy": "2026-10-17",
      "reviewSuggested": [],
      "summary": "Test Architect (Adversary Mode) review of W1-I against W0 rev 2 and R-87..R-94. The probe table, the corrected inj-1 and the nine-variant idea are strong. BLOCK on two controls that can be satisfied for the wrong reason: the 11 hidden tests are red only by a missing module, and the variant test judges outcomes while a fail-closed host turns any crash into \"exploited\".",
      "tags": [
        "review",
        "test-architect",
        "evaluation-campaign",
        "wave-1",
        "w1-i"
      ],
      "links": [
        {
          "to": "design-eval-seam-contracts",
          "rel": "relates-to"
        }
      ],
      "diagrams": [],
      "sourceSha256": "60320ec9b40537661e3c2b375e345ef2a436d47b0b472498db323d9b882b8c7d"
    },
    {
      "id": "review-eval-ta-w1j",
      "path": "docs/design/reviews/eval-review-ta-w1j.md",
      "title": "W1-J multi-turn design review: Test Architect lens",
      "type": "doc",
      "status": "draft",
      "owner": "@timianmalloo",
      "phase": "Enterprise evaluation: Wave 1 gate reviews",
      "reviewBy": "2026-10-17",
      "reviewSuggested": [],
      "summary": "Test Architect (Adversary Mode) review of W1-J (multi-turn attempt, turn snapshots, TLA+ model v5) against W0 rev 6 and the rulings on main. PASS WITH CONDITIONS: the model evidence is real and each ADR-0015 section 7 invariant has its own variant, but the check_models.py change exceeds its grant and is not on the branch, the two engine-bug tests are red for the wrong reason, and the final-row omission is pinned on the reader side only.",
      "tags": [
        "review",
        "test-architect",
        "evaluation-campaign",
        "wave-1",
        "w1-j"
      ],
      "links": [
        {
          "to": "design-eval-seam-contracts",
          "rel": "relates-to"
        }
      ],
      "diagrams": [],
      "sourceSha256": "bbb97953c678b2652d7e7fd02a39c8f7fe52601b98e81c277a2bddf303394ae5"
    },
    {
      "id": "review-eval-ta-w1k",
      "path": "docs/design/reviews/eval-review-ta-w1k.md",
      "title": "W1-K resume, liveness and the alarm channel: Test Architect lens review",
      "type": "doc",
      "status": "draft",
      "owner": "@timianmalloo",
      "phase": "",
      "reviewBy": "2026-10-17",
      "reviewSuggested": [],
      "summary": "Adversary-mode review of docs/design/eval-resume.md (design/eval-resume, 315cf1d4, rev 1.1) and models/run_lifecycle.tla by the Test Architect lens. The window map, the prefix sweep and the TLC evidence are strong. Conditions: the stop path has no C7 or C4 cell in its tests, finish-the-stop idempotence (W12e) contradicts the unsealed new segments, X-K1's gate entry tests need X-K2's cmd_run hunk, two reds are mutant-shaped, and F-1 leaves one liveness property vacuous for the code. PASS WITH CONDITIONS.",
      "tags": [],
      "links": [
        {
          "to": "design-eval-seam-contracts",
          "rel": "relates-to"
        }
      ],
      "diagrams": [],
      "sourceSha256": "1101de66319e5f7b558a39ebea06eac08203cb2d82627a4204fbf18f3636c815"
    },
    {
      "id": "review-eval-ta-w1l",
      "path": "docs/design/reviews/eval-review-ta-w1l.md",
      "title": "W1-L property tasks (eight) design review: Test Architect lens",
      "type": "doc",
      "status": "draft",
      "owner": "@timianmalloo",
      "phase": "Enterprise evaluation: Wave 1 gate reviews",
      "reviewBy": "2026-10-17",
      "reviewSuggested": [],
      "summary": "Test Architect (Adversary Mode) review of W1-L (RS1/RS2, RW1/RW2, NG1/NG2, SM1/SM2 and four graders) against W0 rev 3, R-87..R-96 and the W1-I pattern. BLOCK on four items: simplicity primary is launderable through a file outside the radius, verified_before_use returns a plausible 0 for shell reads, the grader-helper tests are red by ImportError, and the wrong-app fixtures leave about a third of the hidden tests unguarded.",
      "tags": [
        "review",
        "test-architect",
        "evaluation-campaign",
        "wave-1",
        "w1-l"
      ],
      "links": [
        {
          "to": "design-eval-seam-contracts",
          "rel": "relates-to"
        }
      ],
      "diagrams": [],
      "sourceSha256": "6870ca4c300824c59bed200083ce50b9dde2b55b55a5d4ef12ca8afed49eef89"
    },
    {
      "id": "runbook-resume-and-alarm",
      "path": "docs/runbooks/resume-and-alarm.md",
      "title": "Runbook: resume a crashed run and wire the alarm channel",
      "type": "doc",
      "status": "draft",
      "owner": "@timianmalloo",
      "phase": "",
      "reviewBy": "2026-12-31",
      "reviewSuggested": [],
      "summary": "How an operator wires the unattended alarm for a multi-night run: the ntfy topic and user variable, the Task Scheduler task that runs tools/alarm-task.ps1 every 15 minutes, the delivery log and edge state file, and the honest limits (a toast wakes no one; a sleeping host cannot push).",
      "tags": [
        "runbook",
        "alarm",
        "ntfy",
        "resume",
        "task-scheduler",
        "evaluation-campaign"
      ],
      "links": [
        {
          "to": "adr-0021-plan-level-resume-and-liveness",
          "rel": "implements"
        },
        {
          "to": "design-eval-resume",
          "rel": "implements"
        },
        {
          "to": "design-eval-seam-contracts",
          "rel": "depends-on"
        }
      ],
      "diagrams": [],
      "sourceSha256": "2b35fece6b5117acf6c8651d17c4ba3e1b9e21b5859ebbdc0c913c266c09df8d"
    },
    {
      "id": "brief-eval-env-a",
      "path": "docs/coordination/eval-wave2-e1/env-a.md",
      "title": "Brief ENV-A: hermetic tests never read the operator's credential (the ambient-credential fix)",
      "type": "plan",
      "status": "proposed",
      "owner": "@timianmalloo",
      "phase": "",
      "reviewBy": "2026-10-17",
      "reviewSuggested": [],
      "summary": "An autouse fixture that clears every credential variable for tests not marked credentials, with a test that proves the three Q0-join failures pass with the token set; Grok grok-4.7 high, one turn.",
      "tags": [],
      "links": [
        {
          "to": "coordination-eval-wave2-e1-briefs",
          "rel": "implements"
        }
      ],
      "diagrams": [],
      "sourceSha256": "88131b43a7d9a50dde6bbe90a328864d76924af4623c1e4d7937b9e130bbf59b"
    },
    {
      "id": "brief-eval-hyg-verify",
      "path": "docs/coordination/eval-wave2-e1/hyg-verify.md",
      "title": "Brief HYG-VERIFY: the four run-verify-gates failures on main (machine paths, portable text I/O, skill contracts, subprocess UTF-8)",
      "type": "plan",
      "status": "proposed",
      "owner": "@timianmalloo",
      "phase": "",
      "reviewBy": "2026-10-17",
      "reviewSuggested": [],
      "summary": "Four of the nine pack verify gates fail on main before and after the E1 joins (measured at fec54563: 24 machine paths, 25 text-I/O findings, 1 skill-contract refusal, 5 subprocess calls). Every finding is in a repo-owned file. HYG-VERIFY fixes each red-first against the gate's own output, opts out true fixtures with the gate's own marker, and records the gate defects it finds as findings for the pack. Claude Sonnet, one session, 90 min.",
      "tags": [],
      "links": [
        {
          "to": "coordination-eval-wave2-e1-briefs",
          "rel": "implements"
        },
        {
          "to": "defect-classes",
          "rel": "relates-to"
        }
      ],
      "diagrams": [],
      "sourceSha256": "cca38f2189a9641d361ac480d91754f32c9c2cdc29b24d346f7557ac3657b301"
    },
    {
      "id": "brief-eval-kill-guard",
      "path": "docs/coordination/eval-wave2-e1/kill-guard.md",
      "title": "Brief KILL-GUARD: the PreToolUse guard refuses process kills by name or pattern (class PROC-A)",
      "type": "plan",
      "status": "proposed",
      "owner": "@timianmalloo",
      "phase": "",
      "reviewBy": "2026-10-17",
      "reviewSuggested": [],
      "summary": "tools/heredoc_guard.py gains a fourth verdict: a kill by process name, pattern or command line (Stop-Process -Name, a pipeline into Stop-Process, taskkill /IM or /FI, pkill, killall) is refused; a kill by PID passes. The hook is also wired for the PowerShell tool. Claude Sonnet, one short session.",
      "tags": [],
      "links": [
        {
          "to": "coordination-eval-wave2-e1-briefs",
          "rel": "implements"
        },
        {
          "to": "defect-classes",
          "rel": "relates-to"
        }
      ],
      "diagrams": [],
      "sourceSha256": "a5a7fb08d91d74783f66c39f22eb228244f1232c81a1f7484eeac5e80591ee30"
    },
    {
      "id": "brief-eval-time-b",
      "path": "docs/coordination/eval-wave2-e1/time-b.md",
      "title": "Brief TIME-B: two load-sensitive timing tests made deterministic, and the scan that keeps the class out",
      "type": "plan",
      "status": "proposed",
      "owner": "@timianmalloo",
      "phase": "",
      "reviewBy": "2026-10-17",
      "reviewSuggested": [],
      "summary": "Reproduce, then fix, the two tests that fail under full-suite -n auto load (an injected clock or an event-driven wait), and add a scan test for real-sleep and wall-clock assertions under tests/ with a named allowlist; Claude Sonnet, one session.",
      "tags": [],
      "links": [
        {
          "to": "coordination-eval-wave2-e1-briefs",
          "rel": "implements"
        }
      ],
      "diagrams": [],
      "sourceSha256": "e2c40321e24a778160e596893c6e0907cf8dcefcdcc20f667ddb2bd11ad04f6d"
    },
    {
      "id": "brief-eval-time-b2",
      "path": "docs/coordination/eval-wave2-e1/time-b2.md",
      "title": "Brief TIME-B2: the thirteen unaudited real-time tests, reproduced by forced delay and put under test-side time control",
      "type": "plan",
      "status": "proposed",
      "owner": "@timianmalloo",
      "phase": "",
      "reviewBy": "2026-10-17",
      "reviewSuggested": [],
      "summary": "TIME-B's scan allowlists 13 tests as UNAUDITED (12 in test_engine.py, 1 in test_oslock.py). For each: a forced-delay reproduction that fails on an assertion, then test-side time control (event-driven wait, injected clock or test-scaled bound), or a measured reason it cannot flip. Shipped bounds unchanged. Claude Sonnet, one session.",
      "tags": [],
      "links": [
        {
          "to": "coordination-eval-wave2-e1-briefs",
          "rel": "implements"
        },
        {
          "to": "brief-eval-time-b",
          "rel": "depends-on"
        }
      ],
      "diagrams": [],
      "sourceSha256": "040176f1f6cc345b8fd7ac360d8ef250e4d632647e2e41e128c85e111b3eaba1"
    },
    {
      "id": "brief-eval-tool-gsm",
      "path": "docs/coordination/eval-wave2-e1/tool-gsm.md",
      "title": "Brief TOOL-GSM: the Grok served-model reader (R-92 condition 1)",
      "type": "plan",
      "status": "proposed",
      "owner": "@timianmalloo",
      "phase": "",
      "reviewBy": "2026-10-17",
      "reviewSuggested": [],
      "summary": "A stdlib script that reads one Grok dispatch's session directory and fails unless every response was served by grok-4.7; it must join before the second Grok dispatch (R-92).",
      "tags": [],
      "links": [
        {
          "to": "coordination-eval-wave2-e1-briefs",
          "rel": "implements"
        },
        {
          "to": "rulings-register",
          "rel": "depends-on"
        }
      ],
      "diagrams": [],
      "sourceSha256": "57c3960e70475246ed81a4d1ff337fade7d0c94bd1e6461b0df37d0cff99f401"
    },
    {
      "id": "brief-eval-tool-gsm-b",
      "path": "docs/coordination/eval-wave2-e1/tool-gsm-b.md",
      "title": "Brief TOOL-GSM-B: the Grok served-model reader on a deadline-killed session",
      "type": "plan",
      "status": "proposed",
      "owner": "@timianmalloo",
      "phase": "",
      "reviewBy": "2026-10-17",
      "reviewSuggested": [],
      "summary": "tools/grok_served_model.py falls back to the assistant rows of chat_history.jsonl when usage.json is absent, says which file it read, and still exits non-zero when nothing is recorded or the ids disagree with the pin.",
      "tags": [],
      "links": [
        {
          "to": "coordination-eval-wave2-e1-briefs",
          "rel": "implements"
        },
        {
          "to": "brief-eval-tool-gsm",
          "rel": "depends-on"
        },
        {
          "to": "rulings-register",
          "rel": "depends-on"
        }
      ],
      "diagrams": [],
      "sourceSha256": "dccd13b36f97db865ed77191495949124dfc56a9df3f419b14e3e2e1cf0e2773"
    },
    {
      "id": "brief-eval-tool-gsm-first",
      "path": "docs/coordination/eval-wave2-e1/tool-gsm-first.md",
      "title": "Brief TOOL-GSM-FIRST: a --first mode for the Grok served-model reader (R-103 condition 3)",
      "type": "plan",
      "status": "proposed",
      "owner": "@timianmalloo",
      "phase": "",
      "reviewBy": "2026-10-17",
      "reviewSuggested": [],
      "summary": "tools/grok_served_model.py gains --first: read the first assistant row's model_id from chat_history.jsonl and exit at once, non-zero on a non-grok-4.7 id, so the Leader can kill a drifted Grok turn inside 120 s (R-103 c3). Lands before X-H1a's dispatch. Claude Sonnet, one short session.",
      "tags": [],
      "links": [
        {
          "to": "coordination-eval-wave2-e1-briefs",
          "rel": "implements"
        },
        {
          "to": "brief-eval-tool-gsm-b",
          "rel": "depends-on"
        },
        {
          "to": "rulings-register",
          "rel": "depends-on"
        }
      ],
      "diagrams": [],
      "sourceSha256": "91eb0bf54538fb9b4a6ee85e7b58e37fa400281549b08de2910bc407e34bea8e"
    },
    {
      "id": "brief-eval-w1-k",
      "path": "docs/coordination/eval-wave2-e234/w1-k.md",
      "title": "Design brief W1-K: resume, liveness and the alarm (dispatch after W1-J merges)",
      "type": "plan",
      "status": "proposed",
      "owner": "@timianmalloo",
      "phase": "",
      "reviewBy": "2026-10-17",
      "reviewSuggested": [],
      "summary": "The design slice for ADR-0021's plan-level resume, liveness and alarm, run with /design-slice on Claude Sonnet after W1-J merges. It extends W1-J's TLA+ model with NoResumeAfterStop, maps every ADR-0021 section 4 row to a kill-then-resume test, and chooses the alarm channel. X-K1 and X-K2 build from it.",
      "tags": [],
      "links": [
        {
          "to": "coordination-eval-wave2-e234-briefs",
          "rel": "implements"
        },
        {
          "to": "coordination-eval-campaign",
          "rel": "implements"
        },
        {
          "to": "design-eval-seam-contracts",
          "rel": "depends-on"
        }
      ],
      "diagrams": [],
      "sourceSha256": "162a11f1ab46627f23ef9d657676b86b64aa2ce2fc6bccfed5fb7e9bc5b182f9"
    },
    {
      "id": "brief-eval-x-a1",
      "path": "docs/coordination/eval-wave2-e1/x-a1.md",
      "title": "Brief X-A1: arms in the plan, ring plumbing, the pack-reader guard (E1 build)",
      "type": "plan",
      "status": "proposed",
      "owner": "@timianmalloo",
      "phase": "",
      "reviewBy": "2026-10-17",
      "reviewSuggested": [],
      "summary": "X-A1 builds bench-matrix/2 and bench-plan/2, the accessors, launch order, ready rule, role binding, the G1 guard and the reader migrations of W1-A rev 2 on Codex gpt-6.1-sol, in two dispatches, each red and green in one turn.",
      "tags": [],
      "links": [
        {
          "to": "coordination-eval-wave2-e1-briefs",
          "rel": "implements"
        },
        {
          "to": "design-eval-arms",
          "rel": "depends-on"
        },
        {
          "to": "design-eval-seam-contracts",
          "rel": "depends-on"
        }
      ],
      "diagrams": [],
      "sourceSha256": "6252a059c23b39058f30bda99d149f90ce4ed4360f61d4d8350c543c452304b0"
    },
    {
      "id": "brief-eval-x-a3",
      "path": "docs/coordination/eval-wave2-e234/x-a3.md",
      "title": "Brief X-A3: three arms, rings, comparison readers and the _passed fix (E3 build)",
      "type": "plan",
      "status": "proposed",
      "owner": "@timianmalloo",
      "phase": "",
      "reviewBy": "2026-10-17",
      "reviewSuggested": [],
      "summary": "X-A3 lands ADR-0019 item 4's _passed fix first (X-G3 waits on it), then three-arm plans, rings and the comparison-pair readers of W1-A's E3 half, on Agy gemini-3.8-flash-high in three turns.",
      "tags": [],
      "links": [
        {
          "to": "coordination-eval-wave2-e234-briefs",
          "rel": "implements"
        },
        {
          "to": "design-eval-arms",
          "rel": "depends-on"
        },
        {
          "to": "design-eval-catalog-0-7",
          "rel": "depends-on"
        },
        {
          "to": "design-eval-seam-contracts",
          "rel": "depends-on"
        }
      ],
      "diagrams": [],
      "sourceSha256": "2bed236c300b65b03e8ca4e220d640244333557a8b950d604e0be150b80124fb"
    },
    {
      "id": "brief-eval-x-b1",
      "path": "docs/coordination/eval-wave2-e1/x-b1.md",
      "title": "Brief X-B1: create_once, publish_dir, the temp sweep and the lock helper (E1 build)",
      "type": "plan",
      "status": "proposed",
      "owner": "@timianmalloo",
      "phase": "",
      "reviewBy": "2026-10-17",
      "reviewSuggested": [],
      "summary": "X-B1 builds atomic.py (W1-B rev 2), the workspace._land hunk and oslock.acquire_then_probe on Grok grok-4.7 high, in three dispatches, each red and green in one turn and joined before the next.",
      "tags": [],
      "links": [
        {
          "to": "coordination-eval-wave2-e1-briefs",
          "rel": "implements"
        },
        {
          "to": "design-eval-atomic-publish",
          "rel": "depends-on"
        },
        {
          "to": "design-eval-seam-contracts",
          "rel": "depends-on"
        }
      ],
      "diagrams": [],
      "sourceSha256": "172372d640a9c1fc24da756e9e8155666f4057f41683a94050bfe5365205fb7d"
    },
    {
      "id": "brief-eval-x-b2",
      "path": "docs/coordination/eval-wave2-e1/x-b2.md",
      "title": "Brief X-B2: crash-atomic final archive (E1 build)",
      "type": "plan",
      "status": "proposed",
      "owner": "@timianmalloo",
      "phase": "",
      "reviewBy": "2026-10-17",
      "reviewSuggested": [],
      "summary": "X-B2 reworks archive.archive_cell onto atomic.publish_dir with a strict verify and archive.attempt_dirs as the one attempt-folder reader (W1-B rev 2 section 6) on Agy gemini-3.8-flash-high, one turn red and green.",
      "tags": [],
      "links": [
        {
          "to": "coordination-eval-wave2-e1-briefs",
          "rel": "implements"
        },
        {
          "to": "design-eval-atomic-publish",
          "rel": "depends-on"
        },
        {
          "to": "design-eval-seam-contracts",
          "rel": "depends-on"
        }
      ],
      "diagrams": [],
      "sourceSha256": "a16f73aeebe362c4dd5e74b5d5c60566d0bd106fe6baff2168c70d890e10c348"
    },
    {
      "id": "brief-eval-x-c",
      "path": "docs/coordination/eval-wave2-e1/x-c.md",
      "title": "Brief X-C: campaign record, `bench campaign` and the run-side check (E1 build)",
      "type": "plan",
      "status": "proposed",
      "owner": "@timianmalloo",
      "phase": "",
      "reviewBy": "2026-10-17",
      "reviewSuggested": [],
      "summary": "X-C builds campaign.py, the bench campaign commands, the lock protocol, verify with its git witness, the run-side check inside the engine, the campaign status document and the after-grading hook of W1-C rev 2, under W0 rev 6, in serial dispatches C1 -> C2 (C2a ran) -> C3a -> C3b (Coordinator #26: C2b returns to C3a; Coordinator #27: C3b re-cut on 1c615832 under R-106), each red and green in one turn; planned Agy gemini-3.8-flash-high, run as Claude Sonnet from the integration head under R-105 while the primary is blocked (Coordinator #22: C1 re-read against integrate/b3-stage2 f7e1e357).",
      "tags": [],
      "links": [
        {
          "to": "coordination-eval-wave2-e1-briefs",
          "rel": "implements"
        },
        {
          "to": "design-eval-campaign-record",
          "rel": "depends-on"
        },
        {
          "to": "design-eval-seam-contracts",
          "rel": "depends-on"
        }
      ],
      "diagrams": [],
      "sourceSha256": "2f1e37044b13059c16aabc6d917fda2245b532f0d7d9316bb231d27940aa5c8f"
    },
    {
      "id": "brief-eval-x-cv",
      "path": "docs/coordination/eval-wave2-e234/x-cv.md",
      "title": "Brief X-CV: the convergence check, the final ten discrimination records, the proof note",
      "type": "plan",
      "status": "proposed",
      "owner": "@timianmalloo",
      "phase": "",
      "reviewBy": "2026-10-17",
      "reviewSuggested": [],
      "summary": "X-CV runs after every E2-E4 item has joined and the 0.7 freeze is committed: the whole ADR-0021 section 4 table, TLC with every invariant, then the ten discrimination records at the final engine identity (the Leader), on Claude Sonnet.",
      "tags": [],
      "links": [
        {
          "to": "coordination-eval-wave2-e234-briefs",
          "rel": "implements"
        },
        {
          "to": "coordination-eval-campaign",
          "rel": "implements"
        }
      ],
      "diagrams": [],
      "sourceSha256": "5abec8c5bb5d8e175361745f4f0bcda768537a44ea1a9909accf49b57ba574a0"
    },
    {
      "id": "brief-eval-x-d",
      "path": "docs/coordination/eval-wave2-e1/x-d.md",
      "title": "Brief X-D: engine identity, launch recheck, E1 registry rows (E1 build)",
      "type": "plan",
      "status": "proposed",
      "owner": "@timianmalloo",
      "phase": "",
      "reviewBy": "2026-10-17",
      "reviewSuggested": [],
      "summary": "X-D builds identity.py, the E1 errors.py rows, the guard entries and the engine launch recheck of W1-D rev 2 on Codex gpt-6.1-sol, in two dispatches, each red and green in one turn.",
      "tags": [],
      "links": [
        {
          "to": "coordination-eval-wave2-e1-briefs",
          "rel": "implements"
        },
        {
          "to": "design-eval-identity",
          "rel": "depends-on"
        },
        {
          "to": "design-eval-seam-contracts",
          "rel": "depends-on"
        }
      ],
      "diagrams": [],
      "sourceSha256": "2fa2b201653db884e9294ae9adeb4d871deb185e1cc701719579edcaaa6d68ba"
    },
    {
      "id": "brief-eval-x-d1-followon",
      "path": "docs/coordination/eval-wave2-e1/x-d1-followon.md",
      "title": "X-D1 follow-on: turn the partial D1 green under the rev 6.4 rulings (Sonnet, same tree)",
      "type": "plan",
      "status": "proposed",
      "owner": "@timianmalloo",
      "phase": "",
      "reviewBy": "2026-10-17",
      "reviewSuggested": [],
      "summary": "X-D1 on Codex ended partial at 3cea81d9 with ten assertion-red tests. This Sonnet follow-on, in the same tree, implements the two direction scans in tests/import_graph.py and the two-place catalog_hash hunk in grade/runner.py (W0 rev 6.4, R6.4a and R6.4b), then runs the join gate.",
      "tags": [],
      "links": [
        {
          "to": "brief-eval-x-d",
          "rel": "implements"
        },
        {
          "to": "coordination-eval-wave2-e1-briefs",
          "rel": "implements"
        },
        {
          "to": "design-eval-identity",
          "rel": "depends-on"
        },
        {
          "to": "design-eval-seam-contracts",
          "rel": "depends-on"
        }
      ],
      "diagrams": [],
      "sourceSha256": "98abf6cf67f881acf4878e5e3c0da7034e59d1e4d286473b574eecb54a1bfbe9"
    },
    {
      "id": "brief-eval-x-e",
      "path": "docs/coordination/eval-wave2-e1/x-e.md",
      "title": "Brief X-E: discriminate, synthetic agent and readiness (E1 build)",
      "type": "plan",
      "status": "proposed",
      "owner": "@timianmalloo",
      "phase": "",
      "reviewBy": "2026-10-17",
      "reviewSuggested": [],
      "summary": "X-E builds discriminate.py, readiness.py and synthetic_agent.py of W1-E rev 2 under W0 rev 6 and R-98, red first, on Sonnet, from integrate/e1e4-17 (Coordinator #16): the skeleton, the engine-only tests, the host tests, and the X-I2 F4 keep-or-drop line per S1 payload.",
      "tags": [],
      "links": [
        {
          "to": "coordination-eval-wave2-e1-briefs",
          "rel": "implements"
        },
        {
          "to": "design-eval-discriminate",
          "rel": "depends-on"
        },
        {
          "to": "design-eval-seam-contracts",
          "rel": "depends-on"
        }
      ],
      "diagrams": [],
      "sourceSha256": "bdc9f235929384d350bea1be1b588b2e341ccc068ebdb6bc9aad6713ad74957a"
    },
    {
      "id": "brief-eval-x-f",
      "path": "docs/coordination/eval-wave2-e1/x-f.md",
      "title": "Brief X-F: property grader and hidden-check runner (E1 build)",
      "type": "plan",
      "status": "proposed",
      "owner": "@timianmalloo",
      "phase": "",
      "reviewBy": "2026-10-17",
      "reviewSuggested": [],
      "summary": "X-F builds grade/property.py, bench_check.py, _env.py and the runner, correctness, mutation, procs and egress edits of W1-F rev 3, red first, on Sonnet; F0 (the skeleton) joins first so X-G1 can start.",
      "tags": [],
      "links": [
        {
          "to": "coordination-eval-wave2-e1-briefs",
          "rel": "implements"
        },
        {
          "to": "design-eval-property-grader",
          "rel": "depends-on"
        },
        {
          "to": "design-eval-seam-contracts",
          "rel": "depends-on"
        }
      ],
      "diagrams": [],
      "sourceSha256": "a8de3e141c1d32c14490a6a35ec66e7fae243b9855f6a7e040159a77c4af22a3"
    },
    {
      "id": "brief-eval-x-g1",
      "path": "docs/coordination/eval-wave2-e1/x-g1.md",
      "title": "Brief X-G1: catalog 0.7.dev, the eleven property metrics (E1 build)",
      "type": "plan",
      "status": "proposed",
      "owner": "@timianmalloo",
      "phase": "",
      "reviewBy": "2026-10-17",
      "reviewSuggested": [],
      "summary": "X-G1 adds the eleven 0.7.dev metrics with property tags and pass_at_1's also_graded_by to bench/metrics.yaml (W1-G rev 2, R-90, R-95) on Grok grok-4.7 high, one turn red and green.",
      "tags": [],
      "links": [
        {
          "to": "coordination-eval-wave2-e1-briefs",
          "rel": "implements"
        },
        {
          "to": "design-eval-catalog-0-7",
          "rel": "depends-on"
        },
        {
          "to": "design-eval-seam-contracts",
          "rel": "depends-on"
        }
      ],
      "diagrams": [],
      "sourceSha256": "ddcdd5487396d265418362d5708a8f123beab54ff110f2bd208c900296a79648"
    },
    {
      "id": "brief-eval-x-g3",
      "path": "docs/coordination/eval-wave2-e234/x-g3.md",
      "title": "Brief X-G3: scenario-7 pass_at_1 under the declared rule and the 0.7 freeze prep (E3 build)",
      "type": "plan",
      "status": "proposed",
      "owner": "@timianmalloo",
      "phase": "",
      "reviewBy": "2026-10-17",
      "reviewSuggested": [],
      "summary": "X-G3 records scenario-7 pass_at_1 under G2's declared pass rule and prepares the 0.7 fixtures for the US-4 control, on Grok grok-4.7, after X-A3a's _passed fix joins; the Leader then runs freeze_catalog.py (R-86).",
      "tags": [],
      "links": [
        {
          "to": "coordination-eval-wave2-e234-briefs",
          "rel": "implements"
        },
        {
          "to": "design-eval-catalog-0-7",
          "rel": "depends-on"
        },
        {
          "to": "design-eval-seam-contracts",
          "rel": "depends-on"
        }
      ],
      "diagrams": [],
      "sourceSha256": "00afb4033367e5e80644c6873773205f7490d23f1bf3e1a5706b30bd2ccc44a3"
    },
    {
      "id": "brief-eval-x-h1",
      "path": "docs/coordination/eval-wave2-e1/x-h1.md",
      "title": "Brief X-H1: power, verdicts, dominance, ring gates (E1 build)",
      "type": "plan",
      "status": "proposed",
      "owner": "@timianmalloo",
      "phase": "",
      "reviewBy": "2026-10-17",
      "reviewSuggested": [],
      "summary": "X-H1 builds power.py, verdicts.py and gates.py of W1-H rev 2 (stdlib only, pure functions) under W0 rev 6, in three serial turns a -> b -> c (gates calls verdicts.seed_for), each red and green in one turn; a ran on Grok grok-4.7 high, b ran as Claude Sonnet from integrate/e1e4-17 under R-105 (Coordinator #18); c runs as Claude Sonnet from integrate/b3-stage2 (b6c08e30, carries b) under R-105 (b) (Coordinator #21).",
      "tags": [],
      "links": [
        {
          "to": "coordination-eval-wave2-e1-briefs",
          "rel": "implements"
        },
        {
          "to": "design-eval-power-verdicts",
          "rel": "depends-on"
        },
        {
          "to": "design-eval-seam-contracts",
          "rel": "depends-on"
        },
        {
          "to": "adr-0020-power-and-verdicts-stdlib",
          "rel": "depends-on"
        }
      ],
      "diagrams": [],
      "sourceSha256": "54acf3fb7f083001bbe98a1bca1d5e692d8f564a5449eec418f9fbfb61c0b5ad"
    },
    {
      "id": "brief-eval-x-h2",
      "path": "docs/coordination/eval-wave2-e1/x-h2.md",
      "title": "Brief X-H2: report section 3, the R-93 line, the plan_packs header (E1 build)",
      "type": "plan",
      "status": "proposed",
      "owner": "@timianmalloo",
      "phase": "",
      "reviewBy": "2026-10-17",
      "reviewSuggested": [],
      "summary": "X-H2 builds report/campaign_section.py (verdict rows, legend, exclusions block, NA counts, the three-state R-93 line) and the report/html.py hook with the EV-20 campaign block and the plan_packs header lines; planned Agy gemini-3.8-flash-high, run as Claude Sonnet from the integration head under R-105 beside X-C2 (Coordinator #25: re-read against integrate/e1e4-17 e6a7160a; real C1 read API, fixtures only for the C2/C3 store reads and bindings).",
      "tags": [],
      "links": [
        {
          "to": "coordination-eval-wave2-e1-briefs",
          "rel": "implements"
        },
        {
          "to": "design-eval-power-verdicts",
          "rel": "depends-on"
        },
        {
          "to": "design-eval-seam-contracts",
          "rel": "depends-on"
        }
      ],
      "diagrams": [],
      "sourceSha256": "1869dd5d96eb41ab1e2637a797c97de165597763c015ff8e280a07ba6e531265"
    },
    {
      "id": "brief-eval-x-i",
      "path": "docs/coordination/eval-wave2-e1/x-i.md",
      "title": "Brief X-I: security task S1 (E1 build)",
      "type": "plan",
      "status": "proposed",
      "owner": "@timianmalloo",
      "phase": "",
      "reviewBy": "2026-10-17",
      "reviewSuggested": [],
      "summary": "X-I authors tasks/S1 per W1-I rev 2 on Sonnet, then, in a follow-on after X-F joins, proves the reference and naive solutions through the real grader.",
      "tags": [],
      "links": [
        {
          "to": "coordination-eval-wave2-e1-briefs",
          "rel": "implements"
        },
        {
          "to": "design-eval-security-tasks",
          "rel": "depends-on"
        },
        {
          "to": "design-eval-seam-contracts",
          "rel": "depends-on"
        }
      ],
      "diagrams": [],
      "sourceSha256": "af9344cf02511f14b2e60b25eff0f9b842f3314d2ae02709c8903414959feebe"
    },
    {
      "id": "brief-eval-x-i-s2",
      "path": "docs/coordination/eval-wave2-e234/x-i-s2.md",
      "title": "Brief X-I-S2: the second security task S2 on bottle (E4) - spike and authoring now, ready after X-F and the 0.7 freeze",
      "type": "plan",
      "status": "proposed",
      "owner": "@timianmalloo",
      "phase": "",
      "reviewBy": "2026-10-17",
      "reviewSuggested": [],
      "summary": "X-I-S2 runs the S2 spike W1-I section 12 requires (prompt, latent requirement, probes each proven live, the session rules as amended by R-99: login route only, no bottle or pickle import, inert bytes only, tamper-refusal in place of forged-session), records it for RV-SEC and RV-TA, then authors tasks/S2 to draft on Claude Sonnet; ready after X-F joins and catalog 0.7 is frozen.",
      "tags": [],
      "links": [
        {
          "to": "coordination-eval-wave2-e234-briefs",
          "rel": "implements"
        },
        {
          "to": "design-eval-seam-contracts",
          "rel": "depends-on"
        }
      ],
      "diagrams": [],
      "sourceSha256": "1318ac08a9df14ba214162df316cf1c94c017ca095ff3061d384be7b5d368ed9"
    },
    {
      "id": "brief-eval-x-i5",
      "path": "docs/coordination/eval-wave2-e234/x-i5.md",
      "title": "Brief X-I5: S1 fix - the F4 payload drop and the two NA declarations (E1 follow-on, Sonnet)",
      "type": "plan",
      "status": "proposed",
      "owner": "@timianmalloo",
      "phase": "",
      "reviewBy": "2026-10-19",
      "reviewSuggested": [],
      "summary": "X-I5 applies the operator's decision (2) of 2026-10-05 to S1: the check keeps payloads A0, B2, B3 and C0 and drops the other nine, expected.reference declares NA for behavioural_equivalence and regression_count, and S1 gets a new task version; the strict-xfail marker at tests/test_e1_e2e.py:327 is removed when its leg passes. Sonnet, from the integration head; the Leader then runs bench discriminate S1 and commits S1 ready with its record (Coordinator #30).",
      "tags": [],
      "links": [
        {
          "to": "coordination-eval-wave2-e234-briefs",
          "rel": "implements"
        },
        {
          "to": "coordination-e2e4",
          "rel": "implements"
        },
        {
          "to": "brief-eval-x-i",
          "rel": "depends-on"
        },
        {
          "to": "design-eval-seam-contracts",
          "rel": "depends-on"
        }
      ],
      "diagrams": [],
      "sourceSha256": "d442d01daca738cfbeb502d6ffdf3d1353873a909b680efd7f01a6454ec997c0"
    },
    {
      "id": "brief-eval-x-int",
      "path": "docs/coordination/eval-wave2-e1/x-int.md",
      "title": "Brief X-INT: the E1 end-to-end walking skeleton (E1 build)",
      "type": "plan",
      "status": "proposed",
      "owner": "@timianmalloo",
      "phase": "",
      "reviewBy": "2026-10-17",
      "reviewSuggested": [],
      "summary": "X-INT proves the joined E1 tracks end to end through the real CLI, test-only: the campaign walk with real gates, power and readiness, the S1 discrimination run and the T-E19 reader refusals, a two-arm report, the lock and hook partners of C2a and C3b, on Sonnet from the integration head (R-105 re-cut, Coordinator #28).",
      "tags": [],
      "links": [
        {
          "to": "coordination-eval-wave2-e1-briefs",
          "rel": "implements"
        },
        {
          "to": "coordination-eval-campaign",
          "rel": "depends-on"
        },
        {
          "to": "design-eval-seam-contracts",
          "rel": "depends-on"
        }
      ],
      "diagrams": [],
      "sourceSha256": "cb95c2dcc33c12c6524a9f2e794d7d8d738bb2255f9e46c6222655032d8659e7"
    },
    {
      "id": "brief-eval-x-intf",
      "path": "docs/coordination/eval-wave2-e234/x-intf.md",
      "title": "Brief X-INTF: X-INT's three follow-ons - run_side_check on a plan without a campaign block, the EV-18 cell id in status.text, campaign commands honour --runs (Sonnet)",
      "type": "plan",
      "status": "proposed",
      "owner": "@timianmalloo",
      "phase": "",
      "reviewBy": "2026-10-19",
      "reviewSuggested": [],
      "summary": "X-INTF fixes the three src/ findings X-INT recorded as strict-xfail legs: campaign.run_side_check refuses a non-measurement plan with no campaign block (HB-CMP-010, SR-E3), status.text names a blocked cell with its id and cause (EV-18), and the campaign commands read the --runs folder instead of <root>/runs. One Sonnet session, dispatched only after X-J1a joins (the status.py order); markers :471 and :591 in tests/test_e1_e2e.py are removed when their legs pass (Coordinator #30). Coordinator #32 adds finding 4, the R-106 c7 loop-back (W0 rev 6.11 section 6 F-1 and F-2 in campaign._tree_run_diff, with a cross-owner attach-vs-launch_check test), because X-INTF already owns campaign.py this phase.",
      "tags": [],
      "links": [
        {
          "to": "coordination-eval-wave2-e234-briefs",
          "rel": "implements"
        },
        {
          "to": "coordination-e2e4",
          "rel": "implements"
        },
        {
          "to": "brief-eval-x-int",
          "rel": "depends-on"
        },
        {
          "to": "design-eval-seam-contracts",
          "rel": "depends-on"
        },
        {
          "to": "design-eval-discriminate",
          "rel": "depends-on"
        },
        {
          "to": "design-eval-power-verdicts",
          "rel": "depends-on"
        }
      ],
      "diagrams": [],
      "sourceSha256": "9da872a46585886bd90c4eca65c4e92ea32a5462af14bb9ea22024a485618ccc"
    },
    {
      "id": "brief-eval-x-j1",
      "path": "docs/coordination/eval-wave2-e234/x-j1.md",
      "title": "Brief X-J1: the multi-turn engine (E2 build) - unblocked by W1-J rev 2; starts after X-D joins",
      "type": "plan",
      "status": "proposed",
      "owner": "@timianmalloo",
      "phase": "",
      "reviewBy": "2026-10-17",
      "reviewSuggested": [],
      "summary": "X-J1 builds W1-J rev 2's multi-turn engine (open_session/send_turn/Session.close, the turn loop with turn_ended.next, per-turn snapshots through publish_dir, append_missing_rows, the lifecycle turn rules) on Codex gpt-6.1-sol in five turns cut to W1-J section 11's commit order. W1-J's gate passed (merged f23d35ed). X-J1a starts after X-D (X-D1 and its D2 engine recheck) has joined, because X-D owns engine.py in E1 and engine.py edits are serialised.",
      "tags": [],
      "links": [
        {
          "to": "coordination-eval-wave2-e234-briefs",
          "rel": "implements"
        },
        {
          "to": "design-eval-seam-contracts",
          "rel": "depends-on"
        },
        {
          "to": "design-eval-multi-turn",
          "rel": "depends-on"
        }
      ],
      "diagrams": [],
      "sourceSha256": "acb813ae982cacb561090889971108c3faa9d3ac260349305876f19ec649cdf3"
    },
    {
      "id": "brief-eval-x-j2",
      "path": "docs/coordination/eval-wave2-e234/x-j2.md",
      "title": "Brief X-J2: _changes, the rework grader, per-turn synthetic cells and multi-turn discrimination (E2) - unblocked by W1-J rev 2",
      "type": "plan",
      "status": "proposed",
      "owner": "@timianmalloo",
      "phase": "",
      "reviewBy": "2026-10-17",
      "reviewSuggested": [],
      "summary": "X-J2 lands grade/_changes.py's four counting functions (J2a, waits on the X-F and X-A1a joins), then rework.py, per-turn synthetic cells, the multi-turn discrimination path and the variant reader's two new edit forms (J2b, unblocked by W1-J rev 2's gate; waits on X-J2a, X-E, X-LB0 and X-J1's turn record), on Agy gemini-3.8-flash-high.",
      "tags": [],
      "links": [
        {
          "to": "coordination-eval-wave2-e234-briefs",
          "rel": "implements"
        },
        {
          "to": "design-eval-property-tasks",
          "rel": "depends-on"
        },
        {
          "to": "design-eval-seam-contracts",
          "rel": "depends-on"
        },
        {
          "to": "design-eval-multi-turn",
          "rel": "depends-on"
        }
      ],
      "diagrams": [],
      "sourceSha256": "965ca92b2fe92b3457922d64ed365f619274cb7130e52e40ac01937a78ac9b3d"
    },
    {
      "id": "brief-eval-x-k1",
      "path": "docs/coordination/eval-wave2-e234/x-k1.md",
      "title": "Brief X-K1: resume in the engine (E3 build) - BLOCKED on W1-K and X-J1",
      "type": "plan",
      "status": "proposed",
      "owner": "@timianmalloo",
      "phase": "",
      "reviewBy": "2026-10-17",
      "reviewSuggested": [],
      "summary": "X-K1 builds plan-level resume (ADR-0021) on Codex gpt-6.1-sol in four turns. Blocked until W1-K passes its gate and X-J1 has joined (serial spine 6). The Coordinator writes the turn split from W1-K's test map.",
      "tags": [],
      "links": [
        {
          "to": "coordination-eval-wave2-e234-briefs",
          "rel": "implements"
        },
        {
          "to": "design-eval-seam-contracts",
          "rel": "depends-on"
        }
      ],
      "diagrams": [],
      "sourceSha256": "0d274cbd1335fc6b5b34621816bf5901898ebcd53a6b8a7178cc692a2cb58ccf"
    },
    {
      "id": "brief-eval-x-k2",
      "path": "docs/coordination/eval-wave2-e234/x-k2.md",
      "title": "Brief X-K2: liveness and the alarm (E3 build) - BLOCKED on W1-K",
      "type": "plan",
      "status": "proposed",
      "owner": "@timianmalloo",
      "phase": "",
      "reviewBy": "2026-10-17",
      "reviewSuggested": [],
      "summary": "X-K2 builds bench status --alarm-after, last_progress_at and the ntfy alarm channel (R-102), importing resume.has_work, on Agy gemini-3.8-flash-high in two turns. Blocked until W1-K passes its gate.",
      "tags": [],
      "links": [
        {
          "to": "coordination-eval-wave2-e234-briefs",
          "rel": "implements"
        },
        {
          "to": "design-eval-seam-contracts",
          "rel": "depends-on"
        }
      ],
      "diagrams": [],
      "sourceSha256": "dfd3cbaaf27064a49afd7ee8e124117598b5ffb390f1639b87ba42dcc5f9aad8"
    },
    {
      "id": "brief-eval-x-lb",
      "path": "docs/coordination/eval-wave2-e234/x-lb.md",
      "title": "Brief X-LB: SR-L5 property additions (LB0) and the loopback fake harness (LB1, BLOCKED on SP-LB) (E4 build)",
      "type": "plan",
      "status": "proposed",
      "owner": "@timianmalloo",
      "phase": "",
      "reviewBy": "2026-10-17",
      "reviewSuggested": [],
      "summary": "X-LB is the E4 owner of grade/property.py and bench_check.py. LB0 lands SR-L5's four small additions (needed by X-J2b and X-LG) after X-F joins; LB1 builds the loopback fake behind the PropertyCheck contract once the operator's SP-LB run passes. Claude Sonnet, security-adjacent.",
      "tags": [],
      "links": [
        {
          "to": "coordination-eval-wave2-e234-briefs",
          "rel": "implements"
        },
        {
          "to": "design-eval-property-tasks",
          "rel": "depends-on"
        },
        {
          "to": "design-eval-seam-contracts",
          "rel": "depends-on"
        }
      ],
      "diagrams": [],
      "sourceSha256": "56104e1087deaf137c0e6814ea86090b32aea94763e429f602ba721953f10144"
    },
    {
      "id": "brief-eval-x-lg",
      "path": "docs/coordination/eval-wave2-e234/x-lg.md",
      "title": "Brief X-LG: the no-guessing and simplicity graders (E4 build)",
      "type": "plan",
      "status": "proposed",
      "owner": "@timianmalloo",
      "phase": "",
      "reviewBy": "2026-10-17",
      "reviewSuggested": [],
      "summary": "X-LG builds grade/noguess.py (hallucinated_symbol_errors, R-97; verified_before_use NA not built) and grade/diffstats.py (size_vs_reference, new_abstractions, new_dependencies, the outside-radius scope clause) on Agy gemini-3.8-flash-high in three turns, after E1's hub files, X-J2a and X-LB0 join.",
      "tags": [],
      "links": [
        {
          "to": "coordination-eval-wave2-e234-briefs",
          "rel": "implements"
        },
        {
          "to": "design-eval-property-tasks",
          "rel": "depends-on"
        },
        {
          "to": "design-eval-seam-contracts",
          "rel": "depends-on"
        }
      ],
      "diagrams": [],
      "sourceSha256": "1c9cf03613301cdc7c8701711e2e9207f2721ccbad9be49b151c537f0fad1c90"
    },
    {
      "id": "brief-eval-x-ng",
      "path": "docs/coordination/eval-wave2-e234/x-ng.md",
      "title": "Brief X-NG: no-guessing tasks NG1, NG2 (E4) - authoring now, ready after X-LG",
      "type": "plan",
      "status": "proposed",
      "owner": "@timianmalloo",
      "phase": "",
      "reviewBy": "2026-10-17",
      "reviewSuggested": [],
      "summary": "X-NG authors tasks/NG1 and tasks/NG2 to W1-L section 7 with Erratum 1 and W0 rev 6.6, on Claude Sonnet, to draft; the ready flip follows X-LG's noguess strategy.",
      "tags": [],
      "links": [
        {
          "to": "coordination-eval-wave2-e234-briefs",
          "rel": "implements"
        },
        {
          "to": "design-eval-property-tasks",
          "rel": "depends-on"
        },
        {
          "to": "design-eval-seam-contracts",
          "rel": "depends-on"
        }
      ],
      "diagrams": [],
      "sourceSha256": "23ecf30121f0cc53f3350608f7c001a2f2bc8f0dfa56ebc84fce5a9fa701ab08"
    },
    {
      "id": "brief-eval-x-pack",
      "path": "docs/coordination/eval-wave2-e234/x-pack.md",
      "title": "Brief X-PACK: Lane F - the ai-forward upstream of nine pack fixes, then /updatepack here (Claude Code Opus)",
      "type": "plan",
      "status": "proposed",
      "owner": "@timianmalloo",
      "phase": "",
      "reviewBy": "2026-10-19",
      "reviewSuggested": [],
      "summary": "X-PACK (Lane F) upstreams nine coordination and verify-gate fixes into ai-forward's pack sources, red first in ai-forward's own tests and proven by tools/verify-bundle.ps1, in its own worktree of C:\\\\Projects\\\\ai-forward (phase 1); after the Leader pushes ai-forward, it runs /updatepack in this repo in a second worktree and retires the Grok transport deviation (phase 2, joins P5). Claude Code Opus, session lanef-e1e4 (Coordinator #30).",
      "tags": [],
      "links": [
        {
          "to": "coordination-e2e4",
          "rel": "implements"
        },
        {
          "to": "coordination-eval-wave2-e234-briefs",
          "rel": "implements"
        },
        {
          "to": "defect-classes",
          "rel": "depends-on"
        }
      ],
      "diagrams": [],
      "sourceSha256": "f15eecb750e068fbfabc14e5ccab41ba5cdbe05265f47f01c7655402e0da7c05"
    },
    {
      "id": "brief-eval-x-rs",
      "path": "docs/coordination/eval-wave2-e234/x-rs.md",
      "title": "Brief X-RS: resilience tasks RS1, RS2 (E4) - waits on SP-LB's result; ready after X-LB",
      "type": "plan",
      "status": "proposed",
      "owner": "@timianmalloo",
      "phase": "",
      "reviewBy": "2026-10-17",
      "reviewSuggested": [],
      "summary": "X-RS authors tasks/RS1 and tasks/RS2 to W1-L section 9 (provisional on SP-LB and X-LB) with Erratum 1, on Claude Sonnet. Starts when SP-LB's operator run has passed and merged; ready after X-LB.",
      "tags": [],
      "links": [
        {
          "to": "coordination-eval-wave2-e234-briefs",
          "rel": "implements"
        },
        {
          "to": "design-eval-property-tasks",
          "rel": "depends-on"
        },
        {
          "to": "design-eval-seam-contracts",
          "rel": "depends-on"
        }
      ],
      "diagrams": [],
      "sourceSha256": "fb004e69750494fa69426a68992fb92b0888845182c2c49bbec9a884cab26300"
    },
    {
      "id": "brief-eval-x-rw",
      "path": "docs/coordination/eval-wave2-e234/x-rw.md",
      "title": "Brief X-RW: rework tasks RW1 (E2) and RW2 (E4) - authoring now, ready after X-J1 and X-J2b",
      "type": "plan",
      "status": "proposed",
      "owner": "@timianmalloo",
      "phase": "",
      "reviewBy": "2026-10-17",
      "reviewSuggested": [],
      "summary": "X-RW authors tasks/RW1 and tasks/RW2 to W1-L sections 6.2-6.3 with Erratum 1 and W0 rev 6.6, on Claude Sonnet. Authoring stops at draft; the ready flip is a follow-on after X-J1 and X-J2b join.",
      "tags": [],
      "links": [
        {
          "to": "coordination-eval-wave2-e234-briefs",
          "rel": "implements"
        },
        {
          "to": "design-eval-property-tasks",
          "rel": "depends-on"
        },
        {
          "to": "design-eval-seam-contracts",
          "rel": "depends-on"
        }
      ],
      "diagrams": [],
      "sourceSha256": "726274580db23083f2baae0cba4d523ec53192ab4c79b84cef2010f724463826"
    },
    {
      "id": "brief-eval-x-sm",
      "path": "docs/coordination/eval-wave2-e234/x-sm.md",
      "title": "Brief X-SM: simplicity tasks SM1, SM2 (E4) - authoring now, ready after X-LG and X-J2b",
      "type": "plan",
      "status": "proposed",
      "owner": "@timianmalloo",
      "phase": "",
      "reviewBy": "2026-10-17",
      "reviewSuggested": [],
      "summary": "X-SM authors tasks/SM1 and tasks/SM2 to W1-L section 8 with Erratum 1 and W0 rev 6.6 (launderlines, launderclass, laundertest), on Claude Sonnet, to draft; ready follows X-LG and X-J2b.",
      "tags": [],
      "links": [
        {
          "to": "coordination-eval-wave2-e234-briefs",
          "rel": "implements"
        },
        {
          "to": "design-eval-property-tasks",
          "rel": "depends-on"
        },
        {
          "to": "design-eval-seam-contracts",
          "rel": "depends-on"
        }
      ],
      "diagrams": [],
      "sourceSha256": "94ec74e5552cb4703ec2b068af7f1f29e1187e99ba6fbd01be4a7dd62976eb4f"
    },
    {
      "id": "coordination-e2e4",
      "path": "docs/coordination/coordination-e2e4.md",
      "title": "Coordination plan - Evaluation Campaign E2-E4, convergence, overnight follow-ons and the pack upstream",
      "type": "plan",
      "status": "proposed",
      "owner": "@timianmalloo",
      "phase": "Enterprise evaluation: E2 (multi-turn), E3 (arms, freeze, resume, alarm), E4 (property graders and tasks), convergence; Leader epoch 18",
      "reviewBy": "2026-10-19",
      "reviewSuggested": [],
      "summary": "Coordinator #29's plan for the rest of the Evaluation Campaign build at 839d0f4a: 14 dispatchable tracks plus 2 operator-gated ones (X-LB1, X-RS) across Codex, Agy, Grok and Claude Code, one owner per authored file per phase with the joint-satisfiability check for every shared surface, a serial spine of the engine lane (X-J1 then X-K1 then X-K2b then X-CV), five push batches with at most two gate rings, nine struck or merged tracks, and Lane F (the ai-forward upstream) in its own worktree of C:\\projects\\ai-forward. Critical path Inferred at 15-20 h wall.",
      "tags": [
        "coordination",
        "worktrees",
        "parallelism",
        "evaluation-campaign",
        "e2",
        "e3",
        "e4"
      ],
      "links": [
        {
          "to": "coordination-eval-campaign",
          "rel": "implements"
        },
        {
          "to": "coordination-eval-wave2-e234-briefs",
          "rel": "depends-on"
        },
        {
          "to": "coordination-eval-wave2-e1-overnight-2026-10-05",
          "rel": "depends-on"
        },
        {
          "to": "design-eval-seam-contracts",
          "rel": "depends-on"
        },
        {
          "to": "rulings-register",
          "rel": "depends-on"
        },
        {
          "to": "defect-classes",
          "rel": "relates-to"
        },
        {
          "to": "coordinator-log",
          "rel": "relates-to"
        }
      ],
      "diagrams": [],
      "sourceSha256": "c269897eef443cd48fcd19a621b29878c9978dbc0ef04d36b6c8c2707da65ad1"
    },
    {
      "id": "coordination-eval-brief-rv-ds",
      "path": "docs/coordination/eval-wave1/rv-ds.md",
      "title": "RV-DS brief: Distributed Systems lens reviewer (Adversary Mode)",
      "type": "plan",
      "status": "proposed",
      "owner": "@timianmalloo",
      "phase": "Enterprise evaluation: Wave 1 dispatch",
      "reviewBy": "2026-10-17",
      "reviewSuggested": [],
      "summary": "Self-contained Wave 1 dispatch brief (rv-ds): session, branch, pinned model, owned paths, inputs, W0 sections, gate lenses, budget, exit evidence, fallback and not-in-scope. The launcher passes only this file's path.",
      "tags": [
        "coordination",
        "brief",
        "wave-1",
        "evaluation-campaign"
      ],
      "links": [
        {
          "to": "coordination-eval-wave1-briefs",
          "rel": "implements"
        },
        {
          "to": "design-eval-seam-contracts",
          "rel": "depends-on"
        }
      ],
      "diagrams": [],
      "sourceSha256": "c814ad5fcdb1ca745c689e3c45557d78ff3b3ebcccc0bc9637e56316ceba74ef"
    },
    {
      "id": "coordination-eval-brief-rv-pat",
      "path": "docs/coordination/eval-wave1/rv-pat.md",
      "title": "RV-PAT brief: Patterns Expert lens reviewer (Adversary Mode)",
      "type": "plan",
      "status": "proposed",
      "owner": "@timianmalloo",
      "phase": "Enterprise evaluation: Wave 1 dispatch",
      "reviewBy": "2026-10-17",
      "reviewSuggested": [],
      "summary": "Self-contained Wave 1 dispatch brief (rv-pat): session, branch, pinned model, owned paths, inputs, W0 sections, gate lenses, budget, exit evidence, fallback and not-in-scope. The launcher passes only this file's path.",
      "tags": [
        "coordination",
        "brief",
        "wave-1",
        "evaluation-campaign"
      ],
      "links": [
        {
          "to": "coordination-eval-wave1-briefs",
          "rel": "implements"
        },
        {
          "to": "design-eval-seam-contracts",
          "rel": "depends-on"
        }
      ],
      "diagrams": [],
      "sourceSha256": "9325c72019a7b2b4c0860d0144deec14541bf478def131f35751b0fabac8e1ad"
    },
    {
      "id": "coordination-eval-brief-rv-sec",
      "path": "docs/coordination/eval-wave1/rv-sec.md",
      "title": "RV-SEC brief: Security & Identity lens reviewer (Adversary Mode)",
      "type": "plan",
      "status": "proposed",
      "owner": "@timianmalloo",
      "phase": "Enterprise evaluation: Wave 1 dispatch",
      "reviewBy": "2026-10-17",
      "reviewSuggested": [],
      "summary": "Self-contained Wave 1 dispatch brief (rv-sec): session, branch, pinned model, owned paths, inputs, W0 sections, gate lenses, budget, exit evidence, fallback and not-in-scope. The launcher passes only this file's path.",
      "tags": [
        "coordination",
        "brief",
        "wave-1",
        "evaluation-campaign"
      ],
      "links": [
        {
          "to": "coordination-eval-wave1-briefs",
          "rel": "implements"
        },
        {
          "to": "design-eval-seam-contracts",
          "rel": "depends-on"
        }
      ],
      "diagrams": [],
      "sourceSha256": "079f38c5bd3e24703a0d27f226e19988456f98f4e631bd0815f8b5f8f5fec9e0"
    },
    {
      "id": "coordination-eval-brief-rv-sim",
      "path": "docs/coordination/eval-wave1/rv-sim.md",
      "title": "RV-SIM brief: Simplifier lens reviewer (Adversary Mode)",
      "type": "plan",
      "status": "proposed",
      "owner": "@timianmalloo",
      "phase": "Enterprise evaluation: Wave 1 dispatch",
      "reviewBy": "2026-10-17",
      "reviewSuggested": [],
      "summary": "Self-contained Wave 1 dispatch brief (rv-sim): session, branch, pinned model, owned paths, inputs, W0 sections, gate lenses, budget, exit evidence, fallback and not-in-scope. The launcher passes only this file's path.",
      "tags": [
        "coordination",
        "brief",
        "wave-1",
        "evaluation-campaign"
      ],
      "links": [
        {
          "to": "coordination-eval-wave1-briefs",
          "rel": "implements"
        },
        {
          "to": "design-eval-seam-contracts",
          "rel": "depends-on"
        }
      ],
      "diagrams": [],
      "sourceSha256": "5163b00fcbfdbc0b4a569396338ff4e96f17ea04ed7c5c74b6ed96b265fef2f2"
    },
    {
      "id": "coordination-eval-brief-rv-sre",
      "path": "docs/coordination/eval-wave1/rv-sre.md",
      "title": "RV-SRE brief: SRE lens reviewer (Adversary Mode)",
      "type": "plan",
      "status": "proposed",
      "owner": "@timianmalloo",
      "phase": "Enterprise evaluation: Wave 1 dispatch",
      "reviewBy": "2026-10-17",
      "reviewSuggested": [],
      "summary": "Self-contained Wave 1 dispatch brief (rv-sre): session, branch, pinned model, owned paths, inputs, W0 sections, gate lenses, budget, exit evidence, fallback and not-in-scope. The launcher passes only this file's path.",
      "tags": [
        "coordination",
        "brief",
        "wave-1",
        "evaluation-campaign"
      ],
      "links": [
        {
          "to": "coordination-eval-wave1-briefs",
          "rel": "implements"
        },
        {
          "to": "design-eval-seam-contracts",
          "rel": "depends-on"
        }
      ],
      "diagrams": [],
      "sourceSha256": "bd2c0504b529a879104fe8e7cb4a9821edc9ba0b36223c4bbaf0589e16952c36"
    },
    {
      "id": "coordination-eval-brief-rv-ta",
      "path": "docs/coordination/eval-wave1/rv-ta.md",
      "title": "RV-TA brief: Test Architect lens reviewer (Adversary Mode)",
      "type": "plan",
      "status": "proposed",
      "owner": "@timianmalloo",
      "phase": "Enterprise evaluation: Wave 1 dispatch",
      "reviewBy": "2026-10-17",
      "reviewSuggested": [],
      "summary": "Self-contained Wave 1 dispatch brief (rv-ta): session, branch, pinned model, owned paths, inputs, W0 sections, gate lenses, budget, exit evidence, fallback and not-in-scope. The launcher passes only this file's path.",
      "tags": [
        "coordination",
        "brief",
        "wave-1",
        "evaluation-campaign"
      ],
      "links": [
        {
          "to": "coordination-eval-wave1-briefs",
          "rel": "implements"
        },
        {
          "to": "design-eval-seam-contracts",
          "rel": "depends-on"
        }
      ],
      "diagrams": [],
      "sourceSha256": "20a050af94ccb1a7f7bbdcad7bf0267a4db4c5e7840cf0857f7b078fe28b9e89"
    },
    {
      "id": "coordination-eval-brief-sp-lb-loopback",
      "path": "docs/coordination/eval-wave1/sp-lb-loopback.md",
      "title": "SP-LB brief: loopback firewall spike (Windows; the operator runs it)",
      "type": "plan",
      "status": "proposed",
      "owner": "@timianmalloo",
      "phase": "Enterprise evaluation: Wave 1 dispatch",
      "reviewBy": "2026-10-17",
      "reviewSuggested": [],
      "summary": "Self-contained Wave 1 dispatch brief (sp-lb-loopback): session, branch, pinned model, owned paths, inputs, W0 sections, gate lenses, budget, exit evidence, fallback and not-in-scope. The launcher passes only this file's path.",
      "tags": [
        "coordination",
        "brief",
        "wave-1",
        "evaluation-campaign"
      ],
      "links": [
        {
          "to": "coordination-eval-wave1-briefs",
          "rel": "implements"
        },
        {
          "to": "design-eval-seam-contracts",
          "rel": "depends-on"
        }
      ],
      "diagrams": [],
      "sourceSha256": "5c1cc3ee649e1f4e0f181bdb9c1fc6f9ce7ca888a075abad4b3ffdf6dfe21ac2"
    },
    {
      "id": "coordination-eval-brief-w1-a-arms",
      "path": "docs/coordination/eval-wave1/w1-a-arms.md",
      "title": "W1-A brief: arms v2 (ADR-0014)",
      "type": "plan",
      "status": "proposed",
      "owner": "@timianmalloo",
      "phase": "Enterprise evaluation: Wave 1 dispatch",
      "reviewBy": "2026-10-17",
      "reviewSuggested": [],
      "summary": "Self-contained Wave 1 dispatch brief (w1-a-arms): session, branch, pinned model, owned paths, inputs, W0 sections, gate lenses, budget, exit evidence, fallback and not-in-scope. The launcher passes only this file's path.",
      "tags": [
        "coordination",
        "brief",
        "wave-1",
        "evaluation-campaign"
      ],
      "links": [
        {
          "to": "coordination-eval-wave1-briefs",
          "rel": "implements"
        },
        {
          "to": "design-eval-seam-contracts",
          "rel": "depends-on"
        }
      ],
      "diagrams": [],
      "sourceSha256": "9adc3887229833a8325ffb7cfb5799a17a38a406b5414d998a6f46bd55b2b80c"
    },
    {
      "id": "coordination-eval-brief-w1-b-atomic-publish",
      "path": "docs/coordination/eval-wave1/w1-b-atomic-publish.md",
      "title": "W1-B brief: crash-atomic publish (archive rename + create_once)",
      "type": "plan",
      "status": "proposed",
      "owner": "@timianmalloo",
      "phase": "Enterprise evaluation: Wave 1 dispatch",
      "reviewBy": "2026-10-17",
      "reviewSuggested": [],
      "summary": "Self-contained Wave 1 dispatch brief (w1-b-atomic-publish): session, branch, pinned model, owned paths, inputs, W0 sections, gate lenses, budget, exit evidence, fallback and not-in-scope. The launcher passes only this file's path.",
      "tags": [
        "coordination",
        "brief",
        "wave-1",
        "evaluation-campaign"
      ],
      "links": [
        {
          "to": "coordination-eval-wave1-briefs",
          "rel": "implements"
        },
        {
          "to": "design-eval-seam-contracts",
          "rel": "depends-on"
        }
      ],
      "diagrams": [],
      "sourceSha256": "05dfdae47c5eec5a5f0f60f1ed7009d9c99fb92310c27c755e5679272776aa77"
    },
    {
      "id": "coordination-eval-brief-w1-c-campaign-record",
      "path": "docs/coordination/eval-wave1/w1-c-campaign-record.md",
      "title": "W1-C brief: campaign record and `bench campaign`",
      "type": "plan",
      "status": "proposed",
      "owner": "@timianmalloo",
      "phase": "Enterprise evaluation: Wave 1 dispatch",
      "reviewBy": "2026-10-17",
      "reviewSuggested": [],
      "summary": "Self-contained Wave 1 dispatch brief (w1-c-campaign-record): session, branch, pinned model, owned paths, inputs, W0 sections, gate lenses, budget, exit evidence, fallback and not-in-scope. The launcher passes only this file's path.",
      "tags": [
        "coordination",
        "brief",
        "wave-1",
        "evaluation-campaign"
      ],
      "links": [
        {
          "to": "coordination-eval-wave1-briefs",
          "rel": "implements"
        },
        {
          "to": "design-eval-seam-contracts",
          "rel": "depends-on"
        }
      ],
      "diagrams": [],
      "sourceSha256": "6056f0e1d9dbf7168ec1c1926dafa8701c6724567d26331b6e41089b68394e94"
    },
    {
      "id": "coordination-eval-brief-w1-d-identity",
      "path": "docs/coordination/eval-wave1/w1-d-identity.md",
      "title": "W1-D brief: engine identity, freeze and per-launch recheck",
      "type": "plan",
      "status": "proposed",
      "owner": "@timianmalloo",
      "phase": "Enterprise evaluation: Wave 1 dispatch",
      "reviewBy": "2026-10-17",
      "reviewSuggested": [],
      "summary": "Self-contained Wave 1 dispatch brief (w1-d-identity): session, branch, pinned model, owned paths, inputs, W0 sections, gate lenses, budget, exit evidence, fallback and not-in-scope. The launcher passes only this file's path.",
      "tags": [
        "coordination",
        "brief",
        "wave-1",
        "evaluation-campaign"
      ],
      "links": [
        {
          "to": "coordination-eval-wave1-briefs",
          "rel": "implements"
        },
        {
          "to": "design-eval-seam-contracts",
          "rel": "depends-on"
        }
      ],
      "diagrams": [],
      "sourceSha256": "24b608d592a74c6e0ccfabfadbc6c50939a829549b9cb6b894f860b3db17bf8e"
    },
    {
      "id": "coordination-eval-brief-w1-e-discriminate",
      "path": "docs/coordination/eval-wave1/w1-e-discriminate.md",
      "title": "W1-E brief: discriminate, synthetic profile and readiness (EV-7)",
      "type": "plan",
      "status": "proposed",
      "owner": "@timianmalloo",
      "phase": "Enterprise evaluation: Wave 1 dispatch",
      "reviewBy": "2026-10-17",
      "reviewSuggested": [],
      "summary": "Self-contained Wave 1 dispatch brief (w1-e-discriminate): session, branch, pinned model, owned paths, inputs, W0 sections, gate lenses, budget, exit evidence, fallback and not-in-scope. The launcher passes only this file's path.",
      "tags": [
        "coordination",
        "brief",
        "wave-1",
        "evaluation-campaign"
      ],
      "links": [
        {
          "to": "coordination-eval-wave1-briefs",
          "rel": "implements"
        },
        {
          "to": "design-eval-seam-contracts",
          "rel": "depends-on"
        }
      ],
      "diagrams": [],
      "sourceSha256": "e2848b7bd80aa557498bd299eebb1734167cab12aea6efaa860bec06f01e88c2"
    },
    {
      "id": "coordination-eval-brief-w1-f-property-grader",
      "path": "docs/coordination/eval-wave1/w1-f-property-grader.md",
      "title": "W1-F brief: hidden-check runner and property grader (security-sensitive)",
      "type": "plan",
      "status": "proposed",
      "owner": "@timianmalloo",
      "phase": "Enterprise evaluation: Wave 1 dispatch",
      "reviewBy": "2026-10-17",
      "reviewSuggested": [],
      "summary": "Self-contained Wave 1 dispatch brief (w1-f-property-grader): session, branch, pinned model, owned paths, inputs, W0 sections, gate lenses, budget, exit evidence, fallback and not-in-scope. The launcher passes only this file's path.",
      "tags": [
        "coordination",
        "brief",
        "wave-1",
        "evaluation-campaign"
      ],
      "links": [
        {
          "to": "coordination-eval-wave1-briefs",
          "rel": "implements"
        },
        {
          "to": "design-eval-seam-contracts",
          "rel": "depends-on"
        }
      ],
      "diagrams": [],
      "sourceSha256": "2fee4beb0fb70c623d50754b705144a5c77775f532793c57e841986bda5e6001"
    },
    {
      "id": "coordination-eval-brief-w1-g-catalog",
      "path": "docs/coordination/eval-wave1/w1-g-catalog.md",
      "title": "W1-G brief: catalog 0.7 (ADR-0019), scenario-7 pass@1 and the missing-pass@1 fix",
      "type": "plan",
      "status": "proposed",
      "owner": "@timianmalloo",
      "phase": "Enterprise evaluation: Wave 1 dispatch",
      "reviewBy": "2026-10-17",
      "reviewSuggested": [],
      "summary": "Self-contained Wave 1 dispatch brief (w1-g-catalog): session, branch, pinned model, owned paths, inputs, W0 sections, gate lenses, budget, exit evidence, fallback and not-in-scope. The launcher passes only this file's path.",
      "tags": [
        "coordination",
        "brief",
        "wave-1",
        "evaluation-campaign"
      ],
      "links": [
        {
          "to": "coordination-eval-wave1-briefs",
          "rel": "implements"
        },
        {
          "to": "design-eval-seam-contracts",
          "rel": "depends-on"
        }
      ],
      "diagrams": [],
      "sourceSha256": "53ce7e020ce8c0841cd52ee11413c2b4e80e7d061067163918a1fb3b3386fc4d"
    },
    {
      "id": "coordination-eval-brief-w1-h-power-verdicts",
      "path": "docs/coordination/eval-wave1/w1-h-power-verdicts.md",
      "title": "W1-H brief: power, verdicts, dominance, ring gates and report section 3",
      "type": "plan",
      "status": "proposed",
      "owner": "@timianmalloo",
      "phase": "Enterprise evaluation: Wave 1 dispatch",
      "reviewBy": "2026-10-17",
      "reviewSuggested": [],
      "summary": "Self-contained Wave 1 dispatch brief (w1-h-power-verdicts): session, branch, pinned model, owned paths, inputs, W0 sections, gate lenses, budget, exit evidence, fallback and not-in-scope. The launcher passes only this file's path.",
      "tags": [
        "coordination",
        "brief",
        "wave-1",
        "evaluation-campaign"
      ],
      "links": [
        {
          "to": "coordination-eval-wave1-briefs",
          "rel": "implements"
        },
        {
          "to": "design-eval-seam-contracts",
          "rel": "depends-on"
        }
      ],
      "diagrams": [],
      "sourceSha256": "009490d0e90c3ada016008869590eff5a0dc57de8da4547f0a65245514935700"
    },
    {
      "id": "coordination-eval-brief-w1-i-security-tasks",
      "path": "docs/coordination/eval-wave1/w1-i-security-tasks.md",
      "title": "W1-I brief: security tasks S1 and S2 (task design)",
      "type": "plan",
      "status": "proposed",
      "owner": "@timianmalloo",
      "phase": "Enterprise evaluation: Wave 1 dispatch",
      "reviewBy": "2026-10-17",
      "reviewSuggested": [],
      "summary": "Self-contained Wave 1 dispatch brief (w1-i-security-tasks): session, branch, pinned model, owned paths, inputs, W0 sections, gate lenses, budget, exit evidence, fallback and not-in-scope. The launcher passes only this file's path.",
      "tags": [
        "coordination",
        "brief",
        "wave-1",
        "evaluation-campaign"
      ],
      "links": [
        {
          "to": "coordination-eval-wave1-briefs",
          "rel": "implements"
        },
        {
          "to": "design-eval-seam-contracts",
          "rel": "depends-on"
        }
      ],
      "diagrams": [],
      "sourceSha256": "6b9e69ac42dc59d18043bf7572cf4b2e544c25abb0bad0d138e0c7cdb093d2af"
    },
    {
      "id": "coordination-eval-brief-w1-j-multi-turn",
      "path": "docs/coordination/eval-wave1/w1-j-multi-turn.md",
      "title": "W1-J brief: multi-turn attempt, turn snapshots and the TLA+ model (ADR-0015)",
      "type": "plan",
      "status": "proposed",
      "owner": "@timianmalloo",
      "phase": "Enterprise evaluation: Wave 1 dispatch",
      "reviewBy": "2026-10-17",
      "reviewSuggested": [],
      "summary": "Self-contained Wave 1 dispatch brief (w1-j-multi-turn): session, branch, pinned model, owned paths, inputs, W0 sections, gate lenses, budget, exit evidence, fallback and not-in-scope. The launcher passes only this file's path.",
      "tags": [
        "coordination",
        "brief",
        "wave-1",
        "evaluation-campaign"
      ],
      "links": [
        {
          "to": "coordination-eval-wave1-briefs",
          "rel": "implements"
        },
        {
          "to": "design-eval-seam-contracts",
          "rel": "depends-on"
        }
      ],
      "diagrams": [],
      "sourceSha256": "db4c35d639e5e206f3f1e02530a324b6a9d926c748c536eae70c2fc10862485a"
    },
    {
      "id": "coordination-eval-brief-w1-k-resume",
      "path": "docs/coordination/eval-wave1/w1-k-resume.md",
      "title": "W1-K brief: plan-level resume, liveness and the alarm channel (ADR-0021)",
      "type": "plan",
      "status": "proposed",
      "owner": "@timianmalloo",
      "phase": "Enterprise evaluation: Wave 1 dispatch",
      "reviewBy": "2026-10-17",
      "reviewSuggested": [],
      "summary": "Self-contained Wave 1 dispatch brief (w1-k-resume): session, branch, pinned model, owned paths, inputs, W0 sections, gate lenses, budget, exit evidence, fallback and not-in-scope. The launcher passes only this file's path.",
      "tags": [
        "coordination",
        "brief",
        "wave-1",
        "evaluation-campaign"
      ],
      "links": [
        {
          "to": "coordination-eval-wave1-briefs",
          "rel": "implements"
        },
        {
          "to": "design-eval-seam-contracts",
          "rel": "depends-on"
        }
      ],
      "diagrams": [],
      "sourceSha256": "72ca58384d73ab49d772963f95bf9eb4f61fdc146fc30b7a5875716703ed6fe4"
    },
    {
      "id": "coordination-eval-brief-w1-l-property-tasks",
      "path": "docs/coordination/eval-wave1/w1-l-property-tasks.md",
      "title": "W1-L brief: the remaining property tasks: resilience, rework, no-guessing, simplicity (×2 each)",
      "type": "plan",
      "status": "proposed",
      "owner": "@timianmalloo",
      "phase": "Enterprise evaluation: Wave 1 dispatch",
      "reviewBy": "2026-10-17",
      "reviewSuggested": [],
      "summary": "Self-contained Wave 1 dispatch brief (w1-l-property-tasks): session, branch, pinned model, owned paths, inputs, W0 sections, gate lenses, budget, exit evidence, fallback and not-in-scope. The launcher passes only this file's path.",
      "tags": [
        "coordination",
        "brief",
        "wave-1",
        "evaluation-campaign"
      ],
      "links": [
        {
          "to": "coordination-eval-wave1-briefs",
          "rel": "implements"
        },
        {
          "to": "design-eval-seam-contracts",
          "rel": "depends-on"
        }
      ],
      "diagrams": [],
      "sourceSha256": "f83531f019581701c8d02bc5050a9c78ea5586074ce8c61bd8e5c19cc9e23be4"
    },
    {
      "id": "coordination-eval-campaign",
      "path": "docs/coordination/coordination-eval-campaign.md",
      "title": "Coordination plan - Evaluation Campaign build (phases E1-E4)",
      "type": "plan",
      "status": "proposed",
      "owner": "@timianmalloo",
      "phase": "Enterprise evaluation: E1 walking skeleton, then E2 / E3 / E4 in parallel",
      "reviewBy": "2026-10-17",
      "reviewSuggested": [],
      "summary": "Builds phases E1-E4 of the Evaluation Campaign across Claude Code (Sonnet), Codex, Agy and Grok workers under a Claude Code Leader, a Fable Owner and an Opus 5.5 Coordinator. Serial spine first: harness qualification (Codex is blocked on the operator), then one seam-contracts doc that also fixes one owner per hub file per phase. Then twelve design slices reviewed by six lens reviewers, then federated red-first implementation along the real dependency graph: E1 to its demo, then E2, E3 and E4 in parallel, with engine.py edits serialised J before K, converging on the ADR-0021 section 4 table, TLC and ten discrimination records produced at the final engine identity.",
      "tags": [
        "coordination",
        "worktrees",
        "parallelism",
        "federation",
        "evaluation-campaign"
      ],
      "links": [
        {
          "to": "arch-evaluation-campaign",
          "rel": "implements"
        },
        {
          "to": "spec-enterprise-evaluation",
          "rel": "relates-to"
        },
        {
          "to": "coordination-phase1-finish",
          "rel": "relates-to"
        }
      ],
      "diagrams": [],
      "sourceSha256": "6483e206fb3db8920ad65f550ae0d9aaf29906581c093d1585fb072a4c4d49a8"
    },
    {
      "id": "coordination-eval-q0",
      "path": "docs/coordination/eval-q0/README.md",
      "title": "Q0: harness qualification for the Evaluation Campaign build (Codex 0.160.0, Agy 1.2.13, Grok 1.0.41)",
      "type": "plan",
      "status": "proposed",
      "owner": "@timianmalloo",
      "phase": "Enterprise evaluation: serial spine item 1 (Q0)",
      "reviewBy": "2026-10-17",
      "reviewSuggested": [],
      "summary": "The Q0 runner contract (q0-contract.json) and the Leader's command sequence through the operator-approved wrapper: one smoke turn each for Codex 0.160.0 / gpt-6.1-sol, Agy 1.2.13 / gemini-3.8-flash-high and Grok 1.0.41 / grok-4.7 (high), in one run with parallelism 3, then the served model read back per worker.",
      "tags": [
        "coordination",
        "qualification",
        "coord-runner",
        "evaluation-campaign"
      ],
      "links": [
        {
          "to": "coordination-eval-campaign",
          "rel": "implements"
        },
        {
          "to": "rulings-register",
          "rel": "depends-on"
        }
      ],
      "diagrams": [],
      "sourceSha256": "d79453c04137a69d749be6383d05625fda0eae9b586c3c8f89790701364e4ac0"
    },
    {
      "id": "coordination-eval-wave1-briefs",
      "path": "docs/coordination/eval-wave1/README.md",
      "title": "Wave 1 dispatch pack: design-slice and lens-reviewer briefs (Evaluation Campaign)",
      "type": "plan",
      "status": "proposed",
      "owner": "@timianmalloo",
      "phase": "Enterprise evaluation: Wave 1 (design slices W1-A..W1-L, spike SP-LB, lens reviewers RV-*)",
      "reviewBy": "2026-10-17",
      "reviewSuggested": [],
      "summary": "The rules every Wave 1 worker follows, plus one self-contained brief per design track (W1-A..W1-L), the loopback spike (SP-LB) and the six lens reviewers. A launcher passes only the brief's path; the brief tells the worker to read this file first.",
      "tags": [
        "coordination",
        "briefs",
        "wave-1",
        "evaluation-campaign"
      ],
      "links": [
        {
          "to": "coordination-eval-campaign",
          "rel": "implements"
        },
        {
          "to": "design-eval-seam-contracts",
          "rel": "depends-on"
        },
        {
          "to": "rulings-register",
          "rel": "depends-on"
        }
      ],
      "diagrams": [],
      "sourceSha256": "e9d90123909840664872204d201be56ce41df2e05a31975af309a88b7d084c3d"
    },
    {
      "id": "coordination-eval-wave2-e1-briefs",
      "path": "docs/coordination/eval-wave2-e1/README.md",
      "title": "Wave 2 E1 dispatch pack: build briefs, routing, DAG and launch order (Evaluation Campaign)",
      "type": "plan",
      "status": "proposed",
      "owner": "@timianmalloo",
      "phase": "Enterprise evaluation: Wave 2, phase E1 (walking skeleton build)",
      "reviewBy": "2026-10-17",
      "reviewSuggested": [],
      "summary": "The rules every E1 build worker follows, the routing of the fourteen E1 items to harness and pinned model (R-87, R-88 confirmed to Codex, R-91, R-92), the real dependency DAG, the launch order by critical path, the dispatch shape per track (one external turn red and green, or a Sonnet follow-on), and one brief per item. Nine briefs are written; five wait on designs that have not passed their gate. Part 2 (W0 rev 6, Coordinator session #6): the X-C, X-H1, X-H2, X-E and X-INT briefs, TOOL-GSM-B, the rev-6 alignment of part 1, the external compilations, the Grok transport finding, and the DAG and launch order as of 2026-10-03 evening. Coordinator #31 (C-W0, 2026-10-05): section 3 is now the worker gate every E1-E4 brief inherits (the eight-file guard list on the skeleton and final commits, own mutation file only, never --touched; the whole suite is the Leader's, R-104), and section 2 carries RED-C and \"green on arrival\" (GUARD-A's control).",
      "tags": [
        "coordination",
        "briefs",
        "wave-2",
        "e1",
        "evaluation-campaign"
      ],
      "links": [
        {
          "to": "coordination-eval-campaign",
          "rel": "implements"
        },
        {
          "to": "design-eval-seam-contracts",
          "rel": "depends-on"
        },
        {
          "to": "coordination-eval-wave1-briefs",
          "rel": "relates-to"
        },
        {
          "to": "rulings-register",
          "rel": "depends-on"
        }
      ],
      "diagrams": [],
      "sourceSha256": "59a9fafe6a4c4f9273bd3f93eeb69ee6468f237f0063063acb7af93376a1d27b"
    },
    {
      "id": "coordination-eval-wave2-e234-briefs",
      "path": "docs/coordination/eval-wave2-e234/README.md",
      "title": "Wave 2 E2-E4 dispatch pack: briefs, routing, DAG and launch order (Evaluation Campaign, pack part 3)",
      "type": "plan",
      "status": "proposed",
      "owner": "@timianmalloo",
      "phase": "Enterprise evaluation: Wave 2, phases E2 (multi-turn), E3 (arms, catalog freeze, resume), E4 (remaining property tasks), convergence",
      "reviewBy": "2026-10-17",
      "reviewSuggested": [],
      "summary": "Pack part 3 (Coordinator session #7): the routing of the sixteen E2-E4 items and X-CV to harness and pinned model, the real DAG, the launch order by critical path, the gate state of each design, and one brief per item, plus the W1-K design brief. Four Sonnet items can start now (X-NG, X-SM, X-RW authoring; the X-I-S2 spike). Every external brief is written but waits on a design gate or an E1 join, so nothing external is compiled yet (CO-S0 runs at dispatch). W0 rev 6.6 carries the rulings these briefs build on: RV-TA W1-L rev 2 R2-1..R2-4, and the laundering-variant names. Coordinator #9: W1-J rev 2 passed its gate and merged (f23d35ed), so X-J1 and X-J2 are unblocked by design; x-j1.md is re-cut on W1-J rev 2's final names and commit order; X-J1a and X-J2a are compiled (CO-S0); X-J1a starts only after X-D has joined, because X-D owns engine.py in E1. The X-I-S2 brief carries R-99's session rules.",
      "tags": [
        "coordination",
        "briefs",
        "wave-2",
        "e2",
        "e3",
        "e4",
        "evaluation-campaign"
      ],
      "links": [
        {
          "to": "coordination-eval-campaign",
          "rel": "implements"
        },
        {
          "to": "coordination-eval-wave2-e1-briefs",
          "rel": "depends-on"
        },
        {
          "to": "design-eval-seam-contracts",
          "rel": "depends-on"
        },
        {
          "to": "design-eval-property-tasks",
          "rel": "depends-on"
        },
        {
          "to": "rulings-register",
          "rel": "depends-on"
        }
      ],
      "diagrams": [],
      "sourceSha256": "e3ae06a8347b43e7945efd362e4e3cea7e35d6ed1d65593c0c8a00b08d1b0701"
    },
    {
      "id": "coordination-finish-harness-bench",
      "path": "docs/coordination/coordination-finish-harness-bench.md",
      "title": "Coordination plan - finish harness-bench (phases 2-5, the 31 outstanding to-dos)",
      "type": "plan",
      "status": "accepted",
      "owner": "@timianmalloo",
      "phase": "Phase 2 · smoke on all harnesses",
      "reviewBy": "2026-10-08",
      "reviewSuggested": [],
      "summary": "A rolling-wave plan for the 31 outstanding to-dos. Waves 0-1 are planned to the track (the Copilot-vs-Codex capability, the real ACP transcript, hardening and the upstream pack fixes); waves 2-5 are planned to the row, with the gate's exit conditions carried. Each later wave is re-derived at the previous join. Owner Fable, Leader Opus 5.5, workers on Codex gpt-6-sol, Grok, Agy and Claude subagents.",
      "tags": [
        "coordination",
        "worktrees",
        "parallelism",
        "phase-2"
      ],
      "links": [
        {
          "to": "design-phase1-walking-skeleton",
          "rel": "relates-to"
        },
        {
          "to": "rulings-register",
          "rel": "relates-to"
        },
        {
          "to": "coordination-phase1-finish-run",
          "rel": "relates-to"
        }
      ],
      "diagrams": [],
      "sourceSha256": "a65f5281ebb860ff8e60ef204880b97f5869747d3ff91460400da058b05982a1"
    },
    {
      "id": "coordination-phase1-finish",
      "path": "docs/coordination/coordination-phase1-finish.md",
      "title": "Coordination plan - finish harness-bench phase 1 (pre-merge findings, N5, mutation bar, E2E)",
      "type": "plan",
      "status": "proposed",
      "owner": "@timianmalloo",
      "phase": "Phase 1 · walking skeleton",
      "reviewBy": "2026-10-08",
      "reviewSuggested": [],
      "summary": "Finish phase 1 with the pre-merge gate cleared. Five parallel fix tracks own disjoint files: engine, ledger and verify, process edges, surfaces, and the Codex N5 spike. Each runs its own red-first commits and mutation testing. The sub-agents run on Grok (subscription) and Agy, under an Opus 5.5 Coordinator and a Fable Owner (ruling R-1). Joins happen in completion order, then comes a serial close: the real E2E (\"usable\"), then the Proof Pack and re-review (\"merge-ready\").",
      "tags": [
        "coordination",
        "worktrees",
        "parallelism",
        "phase-1"
      ],
      "links": [
        {
          "to": "design-phase1-walking-skeleton",
          "rel": "implements"
        },
        {
          "to": "design-run-lifecycle-model",
          "rel": "relates-to"
        }
      ],
      "diagrams": [],
      "sourceSha256": "b0dfc4a36341adc1f4b1772a4d4f8933e89f36ada5fd9a50332f73d7fa0939f6"
    },
    {
      "id": "plan-spec-backlog",
      "path": "docs/specs/README.md",
      "title": "Spec backlog: from proposal to a running benchmark",
      "type": "plan",
      "status": "draft",
      "owner": "@timianmalloo",
      "phase": "",
      "reviewBy": "2026-10-23",
      "reviewSuggested": [],
      "summary": "The ordered list of specs, architecture decisions and task-authoring units that turn the proposal into a working benchmark. Each unit names the pack skill that produces it, the proposal phase it serves, its dependencies, and the scaffold code it will replace.",
      "tags": [
        "benchmark",
        "backlog",
        "specs"
      ],
      "links": [
        {
          "to": "proposal-cross-harness-benchmarking",
          "rel": "implements"
        },
        {
          "to": "note-proposal-grounding-findings",
          "rel": "depends-on"
        }
      ],
      "diagrams": [],
      "sourceSha256": "b65007497b4bc047e0bd76b590acbf1fb40ac4fd7ed46805de21d675cfe2c40d"
    },
    {
      "id": "privacy-review",
      "path": "docs/security/privacy-review.md",
      "title": "Privacy Review",
      "type": "privacy-review",
      "status": "draft",
      "owner": "@timianmalloo",
      "phase": "Phase 1 · walking skeleton",
      "reviewBy": "2027-03-22",
      "reviewSuggested": [
        {
          "by": "design-phase3-gateway-judges",
          "on": "2026-09-25",
          "reason": "row-17 gateway design gated (rev 3): Fable judge, Codex not qualified (DR-GW-1), CLI-added context (DR-GW-5)"
        }
      ],
      "summary": "The only personal data is the operator's own: the account email that appears in harness transcripts, and the username in home paths. Both stay in local, gitignored run archives; the report embeds no transcript text and shows archive-relative paths. No third party receives personal data beyond the model providers the operator's own subscriptions already use.",
      "tags": [
        "privacy",
        "data-governance"
      ],
      "links": [
        {
          "to": "arch-harness-bench",
          "rel": "documents"
        },
        {
          "to": "design-phase1-walking-skeleton",
          "rel": "documents"
        },
        {
          "to": "design-run-lifecycle-model",
          "rel": "documents"
        },
        {
          "to": "design-phase2-copilot-profile",
          "rel": "documents"
        },
        {
          "to": "design-phase3-gateway-judges",
          "rel": "documents"
        },
        {
          "to": "design-formal-grader",
          "rel": "documents"
        }
      ],
      "diagrams": [],
      "sourceSha256": "3cd0f2f69f16d1e0ae4804ded9648d9738bbb726885ee49639910c937a7cfbf3"
    },
    {
      "id": "findings-t1-engine-hardening",
      "path": "docs/proof/findings-T1.md",
      "title": "Findings to tests: T1 engine hardening",
      "type": "proof-pack",
      "status": "accepted",
      "owner": "@timianmalloo",
      "phase": "Phase 1 · walking skeleton",
      "reviewBy": "2026-12-22",
      "reviewSuggested": [],
      "summary": "The T1 checklist, finding by finding: the test node, the red commit that added the test alone, the failing line at that commit, and the fix commit. Items 14 and 15 were missing controls, not defects, so their red is shown under a named mutant. The Coordinator transcribed this file (the harness refused the sub-agent's write) and re-ran two red SHAs.",
      "tags": [
        "proof",
        "red-first",
        "engine",
        "lifecycle",
        "errors",
        "T1"
      ],
      "links": [
        {
          "to": "coordination-phase1-finish",
          "rel": "relates-to"
        },
        {
          "to": "mutation-record-t1",
          "rel": "relates-to"
        }
      ],
      "diagrams": [],
      "sourceSha256": "0a3c0381356c52433eb75d4eb66a69da834f768906a63e8e5b06a78d6839762f"
    },
    {
      "id": "findings-t10-engine-mutation",
      "path": "docs/proof/findings-T10.md",
      "title": "Findings → tests: track T10 engine-mutation",
      "type": "proof-pack",
      "status": "accepted",
      "owner": "@timianmalloo",
      "phase": "Phase 1 · walking skeleton",
      "reviewBy": "2026-12-22",
      "reviewSuggested": [],
      "summary": "The Test Architect's required item: the 466 engine.py mutants T1 never ran. All 466 ran under cosmic-ray: 343 killed, 62 killed after new tests, 61 argued equivalent, 0 open. One design drift was found and fixed red-first: the kill-retry backoff capped at 60 s against the design's 30 s (red 70531dc, fix e10b1e9). T10 also found that tools/mutate_check.py can leave a stale mutant .pyc.",
      "tags": [
        "proof",
        "findings",
        "mutation",
        "cosmic-ray",
        "T10",
        "engine"
      ],
      "links": [
        {
          "to": "coordination-phase1-finish",
          "rel": "relates-to"
        },
        {
          "to": "mutation-record-t1",
          "rel": "relates-to"
        }
      ],
      "diagrams": [],
      "sourceSha256": "e4181c96ac7770e101f6c37c5609c451a81a83eedb0d3bc0d531be0d797508b7"
    },
    {
      "id": "findings-t11-verify-later-pass",
      "path": "docs/proof/findings-T11.md",
      "title": "Findings → tests: track T11 verify-later-pass",
      "type": "proof-pack",
      "status": "accepted",
      "owner": "@timianmalloo",
      "phase": "Phase 1 · walking skeleton",
      "reviewBy": "2026-12-22",
      "reviewSuggested": [],
      "summary": "Test Architect N1: a later grading pass whose events segment was cut back before grading.completed and re-sealed verified with warnings and exit 0, silently rolling the current scores back. The honest runner seals events only after grading.completed, so bench verify now reports such a segment as HB-LED-002 (exit 5). Red 8edd94f, fixed in bdcd2ef, survivors killed in 98414f5; views.json 34/34; scoped cosmic-ray on verify 98 mutants, 0 open. Whole-tail deletion (shape A) is disclosed, not fixed.",
      "tags": [
        "proof",
        "findings",
        "red-first",
        "T11",
        "views",
        "verify",
        "ledger"
      ],
      "links": [
        {
          "to": "coordination-phase1-finish",
          "rel": "relates-to"
        },
        {
          "to": "mutation-record-t2",
          "rel": "relates-to"
        }
      ],
      "diagrams": [],
      "sourceSha256": "78e212cce869f500958b32917b024ffab97230043a22fc5615f6facbc9cfe5ee"
    },
    {
      "id": "findings-t12-mutation-rerun",
      "path": "docs/proof/findings-T12.md",
      "title": "Findings → tests: track T12 mutation-rerun",
      "type": "proof-pack",
      "status": "accepted",
      "owner": "@timianmalloo",
      "phase": "Phase 1 · walking skeleton",
      "reviewBy": "2026-12-22",
      "reviewSuggested": [],
      "summary": "Every cosmic-ray mutant (2699) re-run with bytecode off. 0 open. The records overstated 29 kills in ledger, views and grade (now killed by new tests in a0c4f52) and argued one engine mutant equivalent on a false argument. Stale bytecode was not the cause, because cosmic-ray already disables it. The likely causes are cosmic-ray counting any non-zero exit or timeout as a kill, and hand-transcribed counts.",
      "tags": [
        "proof",
        "findings",
        "mutation",
        "cosmic-ray",
        "T12",
        "records"
      ],
      "links": [
        {
          "to": "coordination-phase1-finish",
          "rel": "relates-to"
        },
        {
          "to": "mutation-record-t1",
          "rel": "relates-to"
        },
        {
          "to": "mutation-record-t2",
          "rel": "relates-to"
        }
      ],
      "diagrams": [],
      "sourceSha256": "b709fb2ac5b32bd1237f3c30b3b91e4ae849e0c415d3282a713d8af37c432e5e"
    },
    {
      "id": "findings-t2-ledger-verify",
      "path": "docs/proof/findings-T2.md",
      "title": "Findings → tests: track T2 ledger-verify",
      "type": "proof-pack",
      "status": "accepted",
      "owner": "@timianmalloo",
      "phase": "Phase 1 · walking skeleton",
      "reviewBy": "2026-12-22",
      "reviewSuggested": [],
      "summary": "Track T2's findings→tests map: twelve findings on the ledger, verify and grading, each with its red commit, test nodes and failing line. The harness refused the sub-agent's writes of this file, so the Coordinator transcribed it from the track's report and re-ran two red SHAs itself.",
      "tags": [
        "proof",
        "findings",
        "red-first",
        "T2"
      ],
      "links": [
        {
          "to": "coordination-phase1-finish",
          "rel": "relates-to"
        }
      ],
      "diagrams": [],
      "sourceSha256": "8841a8960ad9e868cfa3a92aa173b67a2551f582a5a4d12b832cac89cddbde65"
    },
    {
      "id": "findings-t3-process-edges",
      "path": "docs/proof/findings-T3.md",
      "title": "Findings → tests: track T3 process-edges",
      "type": "proof-pack",
      "status": "accepted",
      "owner": "@timianmalloo",
      "phase": "Phase 1 · walking skeleton",
      "reviewBy": "2026-12-22",
      "reviewSuggested": [],
      "summary": "Track T3's findings→tests map: nine findings, each with a test-only red commit and a separate fix. The harness refused the sub-agent's write of this file, so the Coordinator transcribed it from the track's report and re-ran two red SHAs itself.",
      "tags": [
        "proof",
        "findings",
        "red-first",
        "T3"
      ],
      "links": [
        {
          "to": "coordination-phase1-finish",
          "rel": "relates-to"
        }
      ],
      "diagrams": [],
      "sourceSha256": "114ec6faaf780d5362cf308c4152f05daa2373ca85d3acf68fc5ff0859836655"
    },
    {
      "id": "findings-t4",
      "path": "docs/proof/findings-T4.md",
      "title": "T4 surfaces -- findings, red SHAs, and mutation results",
      "type": "proof-pack",
      "status": "accepted",
      "owner": "@timianmalloo",
      "phase": "Phase 1 - walking skeleton",
      "reviewBy": "2026-10-08",
      "reviewSuggested": [],
      "summary": "T4 surfaces' findings-to-tests map for the coordination plan's exit list, each with its red SHA and failing line, plus the mutation-check result for tests/mutations/{status,report,cli}.json.",
      "tags": [
        "proof",
        "coordination",
        "t4",
        "mutation"
      ],
      "links": [
        {
          "to": "coordination-phase1-finish",
          "rel": "relates-to"
        }
      ],
      "diagrams": [],
      "sourceSha256": "5f6f1d6d3af88c81fba61ee0cb18a6cc49c6a9356fabcba9ef7a6fa9cd189f66"
    },
    {
      "id": "findings-t6-workspace-race",
      "path": "docs/proof/findings-T6.md",
      "title": "Findings → tests: track T6 workspace race",
      "type": "proof-pack",
      "status": "accepted",
      "owner": "@timianmalloo",
      "phase": "Phase 1 · walking skeleton",
      "reviewBy": "2026-12-22",
      "reviewSuggested": [],
      "summary": "The first real E2E failed one cell with HB-CELL-113: two workers building the same task source or pack checkout at once collided on a Windows rename. Red 0082875 (the Coordinator re-ran it), fixed in a76e7c3, with both workspace.json mutations killed.",
      "tags": [
        "proof",
        "findings",
        "red-first",
        "T6",
        "workspace"
      ],
      "links": [
        {
          "to": "coordination-phase1-finish",
          "rel": "relates-to"
        }
      ],
      "diagrams": [],
      "sourceSha256": "d6fd2b79eed4773f5d2220b5c439eca0f717c3f49801a1fdad26666c3dc81d2b"
    },
    {
      "id": "findings-t8-reader-and-paths",
      "path": "docs/proof/findings-T8.md",
      "title": "Findings → tests: track T8 reader-and-paths",
      "type": "proof-pack",
      "status": "accepted",
      "owner": "@timianmalloo",
      "phase": "Phase 1 · walking skeleton",
      "reviewBy": "2026-12-22",
      "reviewSuggested": [],
      "summary": "Two loop-back defects found by the real E2E. T8-1: the Codex reader took the pack-on cell's injected AGENTS.md instructions block as the prompt (US-10). T8-2: a relative --tools-dir left the pack root relative, so pack-apply.py was looked up under the cell working copy and never found (HB-CELL-113). Red 05f52fa / 62c38ba, fixed in 9ddbe38, with both t8.json mutations killed.",
      "tags": [
        "proof",
        "findings",
        "red-first",
        "T8",
        "telemetry",
        "cli"
      ],
      "links": [
        {
          "to": "coordination-phase1-finish",
          "rel": "relates-to"
        }
      ],
      "diagrams": [],
      "sourceSha256": "711d2ead2e4fbe97630a41519ae01465d0b3cc9fe0ca8cb041b4fadd58495a45"
    },
    {
      "id": "findings-t9-cleanup-and-log",
      "path": "docs/proof/findings-T9.md",
      "title": "Findings → tests: track T9 cleanup-and-log",
      "type": "proof-pack",
      "status": "accepted",
      "owner": "@timianmalloo",
      "phase": "Phase 1 · walking skeleton",
      "reviewBy": "2026-12-22",
      "reviewSuggested": [],
      "summary": "Two loop-back defects found by the third real E2E. T9-1: the loser of a build race left its temp folder on disk, because git writes read-only object files on Windows and rmtree(ignore_errors=True) failed silently. T9-2: engine.configure_logging added a FileHandler per call, so runs in one process wrote into each other's engine.log and a finished run's log stayed open. Red e225ff5, fixed in 7f962fb, all three t9.json mutations killed.",
      "tags": [
        "proof",
        "findings",
        "red-first",
        "T9",
        "workspace",
        "engine",
        "logging"
      ],
      "links": [
        {
          "to": "coordination-phase1-finish",
          "rel": "relates-to"
        }
      ],
      "diagrams": [],
      "sourceSha256": "2102aa6dd5fdb3137bf1340f0de21ef73c568387caff286c7eb2946330da92a6"
    },
    {
      "id": "proof-findings-t5",
      "path": "docs/proof/findings-T5.md",
      "title": "T5 findings: N5 spike (Codex host skill discovery)",
      "type": "proof-pack",
      "status": "draft",
      "owner": "@timianmalloo",
      "phase": "Phase 1 · walking skeleton",
      "reviewBy": "2026-10-08",
      "reviewSuggested": [],
      "summary": "T5's findings->tests map and the T5 fallback decision request. One mechanism was tried for real (features.skip_host_skill_discovery); the canary still leaked, so the change is reverted and N5 stays open. Recommends fallback option (a): keep xfail(strict), record the exposure, flag Codex cells in the report header.",
      "tags": [
        "proof",
        "phase-1",
        "codex",
        "N5",
        "T5"
      ],
      "links": [
        {
          "to": "coordination-phase1-finish",
          "rel": "relates-to"
        },
        {
          "to": "note-spike-n5-codex-skill-roots",
          "rel": "relates-to"
        }
      ],
      "diagrams": [],
      "sourceSha256": "ff77e25774f861cfac57df5ed5d9a09b31b33820b87031899c92a6b3fe88e337"
    },
    {
      "id": "proof-phase1",
      "path": "docs/proof/phase1.md",
      "title": "Proof Pack: phase 1 walking skeleton",
      "type": "proof-pack",
      "status": "accepted",
      "owner": "@timianmalloo",
      "phase": "Phase 1 · walking skeleton",
      "reviewBy": "2026-12-22",
      "reviewSuggested": [],
      "summary": "Phase 1 is usable. The real 4-cell E2E (Claude Code and Codex, pack on and off) passes on the integrated branch with real model calls: all cells valid, the ledger verifies, re-grading is byte-identical, and the report renders offline. Every pre-merge finding was closed red-first across tracks T1–T9, and every mutation file is killed. N5 (user skill roots reaching Codex cells) is disclosed and flagged, not fixed.",
      "tags": [
        "proof",
        "phase1",
        "e2e",
        "mutation",
        "red-first"
      ],
      "links": [
        {
          "to": "design-phase1-walking-skeleton",
          "rel": "implements"
        },
        {
          "to": "coordination-phase1-finish",
          "rel": "relates-to"
        },
        {
          "to": "mutation-record-phase1",
          "rel": "relates-to"
        }
      ],
      "diagrams": [],
      "sourceSha256": "3c461a2234e192bdfeead82323923503ea6eb68d8dbeea1974d27227d2e43428"
    },
    {
      "id": "proof-phase2-stop",
      "path": "docs/proof/phase2-stop.md",
      "title": "Proof Pack: STOP-I (row 10 - stop, decisions, spend cap, circuit breaker)",
      "type": "proof-pack",
      "status": "draft",
      "owner": "@timianmalloo",
      "phase": "Phase 2 · W2-STOP-I slice 6 (the proof pass)",
      "reviewBy": "2026-10-09",
      "reviewSuggested": [],
      "summary": "W2-STOP-I's join evidence (design section 21's Test Architect conditions): every tests/mutations/{engine,driver, status,cli,plan,stop}.json mutant observed red on its named test (172/172 killed, two stale-find and one wrong-target survivor found and fixed in this slice), R10-1 red on the hard-floor mutant with a clean measured stop time (10.03 s), the full check_models.py output (22/22 seeded variants rejected, 2/2 witnesses violated, the US-44 bounds safety run passed), the plan `:145` Stop/Race/US-15 clauses mapped to their tests, and the test_correctness_dotnet.py timeout test's flake diagnosed (Inferred; not reproduced under measured load). The default suite passes and ruff is clean.",
      "tags": [
        "proof",
        "phase2",
        "stop-i",
        "red-first",
        "mutation",
        "tla",
        "join-ready"
      ],
      "links": [
        {
          "to": "proof-phase2",
          "rel": "relates-to"
        },
        {
          "to": "design-phase2-stop-decisions",
          "rel": "implements"
        }
      ],
      "diagrams": [],
      "sourceSha256": "5bf27c31afd69bf9fe3681e0d905e57900c4a908b1ac789cb9d76ac8049cf383"
    },
    {
      "id": "spec-enterprise-evaluation",
      "path": "docs/specs/enterprise-evaluation.md",
      "title": "Spec: Enterprise/Production evaluation, a campaign that gives each pack property a verdict per harness",
      "type": "spec",
      "status": "in-review",
      "owner": "@timianmalloo",
      "phase": "Benchmark target (proposal benchmark-state-and-target, approach A-D; sequence steps 1-6)",
      "reviewBy": "2027-04-01",
      "reviewSuggested": [],
      "summary": "The what and why of an evaluation campaign that can answer, with a stated confidence, whether a pack revision gives better Enterprise/Production outcomes per unit of cost than pack-off and another pack revision, on each harness. It adds ten property tasks (two each for security, resilience, rework, no-guessing and simplicity), each with a hidden mechanical check proven through the engine. It also adds metrics that must record, a reference-checked power analysis and pre-registration, a pilot ring, a pack-regression ring, an engine freeze after authoring, a three-arm comparison grid in one run, and a per-property verdict in the report. The operator's decisions of 2026-10-03 and the specify gate's findings are recorded. It refines the harness-bench spec and surfaces twelve conflicts with it.",
      "tags": [
        "benchmark",
        "spec",
        "enterprise",
        "pack-effect",
        "power-analysis",
        "pre-registration",
        "ring",
        "verdict"
      ],
      "links": [
        {
          "to": "spec-harness-bench",
          "rel": "refines"
        },
        {
          "to": "proposal-benchmark-state-and-target",
          "rel": "implements"
        },
        {
          "to": "proposal-enterprise-production-portfolio",
          "rel": "relates-to"
        },
        {
          "to": "proposal-pack-onoff-analysis",
          "rel": "relates-to"
        },
        {
          "to": "proposal-cross-harness-benchmarking",
          "rel": "relates-to"
        },
        {
          "to": "design-pack-improvement-section",
          "rel": "relates-to"
        }
      ],
      "diagrams": [
        {
          "kind": "flowchart",
          "title": "Conceptual domain model (DM1 / DM4 / DM14)",
          "mermaid": "flowchart LR\n  subgraph Camp[\"Evaluation Campaign (new)\"]\n    C[Campaign] --> PR[Pre-registration]\n    C --> EB[Engine baseline]\n    C --> DF[Recorded defect fix]\n    C --> PA[Power analysis, by input hash]\n  end\n  subgraph Cat[\"Benchmark Catalog (extended)\"]\n    TV[Task version + hidden check] --> DR[Discrimination record]\n    RV[Ring: tagged matrix, hashed]\n    MC[Metric catalog version]\n  end\n  subgraph Exec[\"Run Execution (amended)\"]\n    Run --> Plan[Plan: one pack revision per pack-on arm]\n    Run --> Cell[Cell: task version, combo, arm, rep]\n  end\n  subgraph Ev[\"Evidence (amended)\"]\n    Arch[Cell archive + turn snapshots]\n  end\n  Cell -. produces .-> Arch\n  subgraph Gr[\"Grading\"]\n    SS[Score set]\n  end\n  subgraph Rep[\"Reporting (extended)\"]\n    PV[Property verdict, derived]\n  end\n  C -. references by id .-> RV\n  C -. references by id .-> Run\n  PR -. names .-> TV\n  PR -. names primary metric in .-> MC\n  DR -. valid for .-> EB\n  Cell --> SS\n  SS --> PV\n  PR -. decides rules of .-> PV\n  PA -. reads variance of .-> SS"
        },
        {
          "kind": "flowchart",
          "title": "User flows",
          "mermaid": "flowchart TD\n  A([P1 starts a campaign: draft]) --> AU[Author 10 property tasks; catalog 0.7; changes free]\n  AU --> RD{Every task ready: discrimination record with expected values?}\n  RD -->|no| RE[Names each task and the failing item] --> FIX1[P2 fixes the task, freely] --> RD\n  RD -->|yes| SP{Post-turn spike passed on all 3 harnesses?}\n  SP -->|no| SPF[Names the harness and the evidence] --> FIX2[Engine change, freely, before baseline] --> SP\n  SP -->|yes| B[Record engine baseline]\n  B -->|precondition missing| BR[Baseline refused, naming it] --> AU\n  B --> RR{Records reproduce at the baseline?}\n  RR -->|no| RRF[Names task and metric] --> DF0[Recorded defect fix, or abandon and re-author] --> RR\n  RR -->|yes| PP[Prior power analysis: MDE, pairs, cells, hours, tokens; assumed inputs marked]\n  PP --> PIL[Pilot ring: plan shown, P1 confirms]\n  PIL --> G{Pilot gate}\n  G -->|fails| GF[Named items: metric, task, cause] --> DF[Fix recorded as a defect fix with its class] --> PIL\n  G -->|passes| ADM{Admission: pack-off saturated or floor?}\n  ADM -->|some tasks| DROP[Named tasks not admitted] --> FP\n  ADM -->|none| FP[Final power analysis from pilot rates]\n  FP -->|capacity below requirement| CAP[Reachable MDE shown] -->|P1 accepts MDE or changes plan| FP\n  CAP -->|P1 abandons| AB([Campaign abandoned; pilot results kept])\n  FP --> PR[Pre-registration shown with hash]\n  PR -->|P1 declines| FP\n  PR -->|P1 confirms| GRID[Comparison grid: three arms, interleaved]\n  GRID -->|stop or crash| UF1([As harness-bench UF-1: stopped or incomplete; resume])\n  GRID -->|defect found| DF2[Fix recorded] --> RG[Every campaign run re-graded] --> VER\n  GRID -->|single cell lost or blocked, run continues| CL[Cell named with cause; decision request if US-15 applies] --> XN[Counted in its verdict's excluded n, with id and reason; listed in completion summary and validity banner] --> GRID\n  GRID -->|all cells terminal| VER{Eligible?}\n  VER -->|engine drift or pre-registration mismatch| INEL([No verdicts; reason and differing items])\n  VER -->|eligible| OUT([Verdict table in summary and report])"
        },
        {
          "kind": "flowchart",
          "title": "User flows",
          "mermaid": "flowchart TD\n  A([P4 has a candidate pack revision]) --> P[Ring plan: incumbent, candidate, pack-off; bound shown]\n  P -->|bound over 8 h| OB[Shown as over budget] -->|P4 proceeds or cancels| P\n  P -->|confirm| R[Ring runs and is graded]\n  R -->|candidate fails to install| INST([Cells blocked with cause; no result; fix upstream])\n  R --> GT{Ring gate}\n  GT -->|fails| GF([Named items; result withheld; rerun after fix])\n  GT -->|passes| RES{Per property}\n  RES -->|interval wholly worse| SIG([regression signal: effect, interval, evidence])\n  RES -->|otherwise| NR([no regression detected at the ring MDE])\n  A -->|ring template edited| NV[New ring hash; comparison with earlier hashes refused] --> P"
        },
        {
          "kind": "flowchart",
          "title": "User flows",
          "mermaid": "flowchart TD\n  O([Open report]) --> H[Header + campaign block: question, arms, pre-registration hash, baseline, fixes, MDE]\n  O -->|run in no campaign| NC([No verdict section; harness-bench report as before])\n  H -->|run ineligible| IN([Verdict section states reason and differing items; no verdicts])\n  H --> T[Verdict table: property x harness, per comparison]\n  T -->|better or worse| E1[Effect, interval, MDE mark, token ratio]\n  T -->|no difference >= MDE| E2([Interval inside the MDE band; reader can rule out effects of MDE size])\n  T -->|inconclusive| E3([Reason: underpowered or not recorded, with counts; reader sees what more data would need])\n  E1 -->|dominance rule met| D([A dominates B: keep A for this harness])\n  E1 -->|better but costlier| C([better at xN tokens: reader weighs value against cost])\n  T -->|activate a verdict| RUNS[Runs filtered to its pairs] --> UF3([Harness-bench UF-3: cell card])\n  T -->|activate excluded n| XL[Excluded cells: id, arm, cause] --> UF3\n  O -->|pack section read directly| PK([Pack section: header and every intention verdict labelled exploratory; link to section 3])\n  UF3 -->|archive absent| NA([Archive not in this copy + path])\n  H -->|analysis not pre-registered| EX([Labelled exploratory wherever shown; not a verdict])"
        }
      ],
      "sourceSha256": "dc44b25711edc3125b255de5df1e911a90cda089f18f7b433b26037d467392d1"
    },
    {
      "id": "spec-harness-bench",
      "path": "docs/specs/harness-bench.md",
      "title": "Spec: harness-bench, a cross-harness, cross-model benchmark with the pack as a factor",
      "type": "spec",
      "status": "accepted",
      "owner": "@timianmalloo",
      "phase": "BOM v0: smoke milestone (proposal phases 0-5), then full grid (phase 6)",
      "reviewBy": "2027-03-22",
      "reviewSuggested": [],
      "summary": "The what and why of harness-bench in three layers: a functional spec (domain model, 52 stories with Gherkin criteria tagged by milestone, ISO 25010 NFRs, threat model), a UX spec for the run conversation, the bench CLI, task authoring and the report (IA, five flows with stop, resume and unanswered-decision paths), and a UI spec for the report and CLI table (archetype B3 with recorded deviations, uncertainty on every estimate, complete states, WCAG 2.2 AA). The runner spikes and a six-lens adversarial gate turned the proposal's assumptions into explicit requirements.",
      "tags": [
        "benchmark",
        "spec",
        "harness",
        "model",
        "pack",
        "grading",
        "report"
      ],
      "links": [
        {
          "to": "proposal-cross-harness-benchmarking",
          "rel": "implements"
        },
        {
          "to": "note-proposal-grounding-findings",
          "rel": "depends-on"
        },
        {
          "to": "note-spike-runner-path",
          "rel": "depends-on"
        },
        {
          "to": "plan-spec-backlog",
          "rel": "refines"
        }
      ],
      "diagrams": [
        {
          "kind": "flowchart",
          "title": "Conceptual domain model (DM1 / DM4)",
          "mermaid": "flowchart LR\n  subgraph Catalog[\"Benchmark Catalog\"]\n    BOM[BOM version] --> TV[Task version]\n    MC[Metric catalog version]\n    PL[Price list version]\n  end\n  subgraph Exec[\"Run Execution\"]\n    Run --> Plan[Frozen plan]\n    Run --> Sched[Run scheduler policy]\n    Cell --> Attempt\n  end\n  subgraph Ev[\"Evidence\"]\n    Arch[Cell archive]\n    TD[Teardown policy]\n  end\n  subgraph Gr[\"Grading\"]\n    SS[Score set]\n    JV[Judge verdict]\n    CM[Clarification match]\n  end\n  subgraph Rep[\"Reporting\"]\n    Report\n    Summary[AI summary]\n  end\n  TV -. by identity .-> Cell\n  Run -. by identity .-> Cell\n  Cell -. produces .-> Arch\n  Arch -. graded into .-> SS\n  MC -. version .-> SS\n  PL -. version .-> SS\n  JV --> SS\n  CM --> SS\n  SS --> Report\n  Report --> Summary\n  Gr -. ACL: coordination-ledger reader .- Pack[(ai-forward coordination, external)]"
        },
        {
          "kind": "flowchart",
          "title": "User flows",
          "mermaid": "flowchart TD\n  A([P1 types /start-benchmark + prose]) --> B[Compile prose to matrix]\n  B -->|unresolved clause| DR1[Decision request per clause, with default]\n  DR1 -->|answered| B\n  DR1 -->|P1 abandons| X1([No matrix written. Nothing spent])\n  B -->|resolved| V{validate + plan}\n  V -->|task not ready / invalid matrix| E1[Each problem with its fix]\n  E1 --> X2([Stop. Nothing spent])\n  V -->|ok| P[Plan: combos, models, builds, pack revision, cells, time bound, cap, decision timeout]\n  P -->|decline| X3([Stop. Nothing spent])\n  P -->|confirm| R[Cells run unattended]\n  R -->|blocked cell / qualification gap / cap| DR2[Decision request: cause, options, default, time to default]\n  DR2 -->|answered| R\n  DR2 -->|timeout| DEF[Default applied and recorded] --> R\n  R -->|P1 says stop, or bench stop| ST[Stop starts; running cells stopped within 30 s and archived; open decision superseded]\n  ST --> STP([Run stopped. Terminal cells graded and reported. Resume launches cells with no outcome])\n  R -->|coordinator crash| CR[Running cells end failed - coordinator crash, archived]\n  CR --> INC([Run incomplete. bench status says coordinator not running])\n  INC -->|full milestone: resume| RS{Resume checks}\n  STP -->|resume| RS\n  RS -->|finished run| N1([Nothing to resume])\n  RS -->|running, coordinator alive| N4([Refuses; points to bench status])\n  RS -->|unknown id| N2([Lists known run ids])\n  RS -->|build or task hash drifted| N3([Refuses, names drift, suggests a new run])\n  RS -->|ok| R\n  INC -->|smoke milestone| NEW([Re-run as a new run id; archived cells kept])\n  R -->|all cells terminal| G[Grade]\n  G -->|judge API down| G2[Judged metrics NA; re-grade fills them] --> RP\n  G --> RP[Report: CLI table + HTML]\n  RP --> Z([Completion summary: counts, report path, headlines, overhead])"
        },
        {
          "kind": "flowchart",
          "title": "User flows",
          "mermaid": "flowchart TD\n  O([Open report file]) --> H[Header: jump links to Leaderboard and Pack effect]\n  H -->|needs context| AB[About this run: pack, revision, terms] --> H\n  H -->|banner shows exclusions| L1[Exclusion list] --> H\n  H --> LB[Leaderboard: gated rank, ties, intervals]\n  LB -->|sort / isolate combo / switch pack| LB\n  LB -->|activate a score| EV[Evidence: raw value, unit, version, pointer]\n  EV -->|archive present| ART([Artifact opens])\n  EV -->|archive absent| NA1[Archive not in this copy + path] --> LB\n  LB --> PE[Pack effect with intervals]\n  PE -->|interval crosses zero| NDE[no detectable effect]\n  PE --> K[Frontier, areas, scenarios, context growth]\n  K -->|value not recorded| NR[not recorded + reason, never 0] --> K\n  K --> S[Summaries with run-id links]\n  S -->|claim check failed| SNP[Not published: n claims did not resolve + how to regenerate]\n  S -->|activate a run id| RUN[Runs filtered to that cell] --> ART\n  O -->|no completed cells| EMPTY[Header + banner + No cell completed in this run. Run bench status to see why] --> Z2([P1 inspects the run])\n  O -->|report of two runs| CMP[Comparison: B − A per area and combo, with intervals]\n  CMP -->|runs differ in combos, BOM or catalog| REF([Comparison refused; each difference named])\n  CMP -->|interval crosses zero| NDE"
        },
        {
          "kind": "flowchart",
          "title": "User flows",
          "mermaid": "flowchart TD\n  A([Activate a cell from any score or run id]) --> B[Cell card: task version, combo, pack, rep, execution outcome, validity, served model, build]\n  B -->|invalid| I[Cause: model mismatch / containment, with evidence]\n  B -->|blocked, e.g. blocked - auth| BL[Cause and when it happened; no score recorded]\n  B -->|timed_out or stopped| T[Budget, elapsed; graded on the tree left]\n  B --> S[Scores by area with evidence pointers]\n  S -->|G-task| F[Four formal scores side by side + first counterexample or failing trace step]\n  S -->|judged metric| J[Both verdicts; not recorded when > 1 step apart]\n  S -->|withheld| W[withheld: sensitive content, no payload shown]\n  S --> D[Diff, transcript excerpt, test output]\n  D -->|archive absent| NA[Archive not in this copy + path]"
        },
        {
          "kind": "flowchart",
          "title": "User flows",
          "mermaid": "flowchart TD\n  A([P1 changes a grader, metric, anchor or rubric]) --> B{CI grades frozen fixtures}\n  B -->|scores unchanged| OK([Merge])\n  B -->|changed, version not bumped| FAIL[CI fails naming metrics and fixtures] --> V[Bump catalog version]\n  V --> B\n  B -->|changed, version bumped| RG[bench grade archived runs under the new version]\n  RG -->|cache miss| M[Reported; new judge calls only when P1 allows them]\n  RG --> R([Both versions kept; reports name their version])"
        },
        {
          "kind": "flowchart",
          "title": "User flows",
          "mermaid": "flowchart TD\n  A([P2 runs /new-bench-task ID]) --> S[stub: task.yaml from template]\n  S --> D[draft: prompt.md, workspace base]\n  D --> O[oracle: hidden tests / rubric / clarifications / seeded bug]\n  O --> V{bench validate}\n  V -->|contract broken| E[Folder, rule, fix] --> O\n  V -->|scenario 1, no clarifications| E\n  V -->|scenario 7, no seeded bug or no toolchain pin| E\n  V -->|ok| DIS{Discrimination check: reference passes, naive or seeded fails}\n  DIS -->|does not discriminate| E2[Oracle too weak or too strict: shown with both results] --> O\n  DIS -->|discriminates| R([status: ready])"
        }
      ],
      "sourceSha256": "9d009f9d990506096fc9b3358ad05b5c2b70c8f8804b52fdb96958ba2d35e321"
    },
    {
      "id": "threat-model",
      "path": "docs/security/threat-model.md",
      "title": "Threat Model",
      "type": "threat-model",
      "status": "draft",
      "owner": "@timianmalloo",
      "phase": "Phase 1 · walking skeleton",
      "reviewBy": "2027-03-22",
      "reviewSuggested": [
        {
          "by": "design-phase3-gateway-judges",
          "on": "2026-09-25",
          "reason": "row-17 gateway design gated (rev 3): Fable judge, Codex not qualified (DR-GW-1), CLI-added context (DR-GW-5)"
        },
        {
          "by": "adr-0013-native-cells",
          "on": "2026-10-03",
          "reason": "Proposed amendment 2026-10-03 (ADR-0014/0015, arch-evaluation-campaign): cell grain by arm, per-turn prompt_sent, archive_files snapshot key part, job terminated after the last turn; council gate pending"
        }
      ],
      "summary": "harness-bench is a local benchmark run by one trusted operator (ADR-0012). Each cell works natively in its own git working copy, and nothing more (ADR-0013). The controls that remain protect result validity (hidden tests never in the agent's tree) and what the operator shares (no credential in a published report). The agent's reach outside its working copy is accepted by the owner.",
      "tags": [
        "security",
        "threat-model"
      ],
      "links": [
        {
          "to": "arch-harness-bench",
          "rel": "documents"
        },
        {
          "to": "design-phase1-walking-skeleton",
          "rel": "documents"
        },
        {
          "to": "design-run-lifecycle-model",
          "rel": "documents"
        },
        {
          "to": "design-phase2-copilot-profile",
          "rel": "documents"
        },
        {
          "to": "design-phase3-gateway-judges",
          "rel": "documents"
        },
        {
          "to": "design-formal-grader",
          "rel": "documents"
        },
        {
          "to": "adr-0012-proportionate-security",
          "rel": "depends-on"
        },
        {
          "to": "adr-0013-native-cells",
          "rel": "depends-on"
        }
      ],
      "diagrams": [
        {
          "kind": "flowchart",
          "title": "1. System trust-boundary map",
          "mermaid": "flowchart LR\n  subgraph Host[\"Host (trusted: the operator)\"]\n    Engine[\"bench engine\\n(single writer)\"]\n    Runs[\"runs/&lt;id&gt;\\nledger + archives\"]\n    Creds[\"subscription logins\\n(harness homes)\"]\n    Report[\"report HTML\"]\n  end\n  subgraph Cell[\"Cell (the agent, with the operator's rights)\"]\n    Agent[\"harness + model\"]\n    WS[\"own git working copy\"]\n  end\n  Oracle[\"hidden tests / oracle\"]\n  Engine -- \"B1 spawn into Job Object, kill\" --> Cell\n  Creds -- \"B1 per-cell copy\" --> Cell\n  Cell -- \"B4 archive\" --> Runs\n  Oracle -. \"B2 never in the task clone\" .- Cell\n  Runs --> Report\n  Report -- \"B5 publish\" --> Shared[\"shared report\"]"
        }
      ],
      "sourceSha256": "8be69c5be0babb7b09d1b7b023721d7cd6a1bed19987f6da0f5bdc3bb1fa4d8b"
    }
  ],
  "surfaces": [
    {
      "id": "surface-audit-index",
      "path": "docs/audit/index.html",
      "title": "x-harness-x-model-bench — Audit & Change Log",
      "kind": "audit",
      "description": "Browse the committed audit and change timeline.",
      "artifactId": "audit-log"
    },
    {
      "id": "surface-design-eval-arms",
      "path": "docs/design/eval-arms.html",
      "title": "Eval Arms",
      "kind": "design-preview",
      "description": "Inspect a rendered design or design-language preview.",
      "artifactId": "design-eval-arms"
    },
    {
      "id": "surface-design-eval-campaign-record",
      "path": "docs/design/eval-campaign-record.html",
      "title": "Eval Campaign Record",
      "kind": "design-preview",
      "description": "Inspect a rendered design or design-language preview.",
      "artifactId": "design-eval-campaign-record"
    },
    {
      "id": "surface-design-eval-catalog-0-7",
      "path": "docs/design/eval-catalog-0-7.html",
      "title": "Eval Catalog 0 7",
      "kind": "design-preview",
      "description": "Inspect a rendered design or design-language preview.",
      "artifactId": "design-eval-catalog-0-7"
    },
    {
      "id": "surface-design-eval-discriminate",
      "path": "docs/design/eval-discriminate.html",
      "title": "Eval Discriminate",
      "kind": "design-preview",
      "description": "Inspect a rendered design or design-language preview.",
      "artifactId": "design-eval-discriminate"
    },
    {
      "id": "surface-design-eval-multi-turn",
      "path": "docs/design/eval-multi-turn.html",
      "title": "Eval Multi Turn",
      "kind": "design-preview",
      "description": "Inspect a rendered design or design-language preview.",
      "artifactId": "design-eval-multi-turn"
    },
    {
      "id": "surface-design-eval-property-grader",
      "path": "docs/design/eval-property-grader.html",
      "title": "Eval Property Grader",
      "kind": "design-preview",
      "description": "Inspect a rendered design or design-language preview.",
      "artifactId": "design-eval-property-grader"
    },
    {
      "id": "surface-design-eval-resume",
      "path": "docs/design/eval-resume.html",
      "title": "Eval Resume",
      "kind": "design-preview",
      "description": "Inspect a rendered design or design-language preview.",
      "artifactId": "design-eval-resume"
    },
    {
      "id": "surface-design-eval-seam-contracts",
      "path": "docs/design/eval-seam-contracts.html",
      "title": "Eval Seam Contracts",
      "kind": "design-preview",
      "description": "Inspect a rendered design or design-language preview.",
      "artifactId": "design-eval-seam-contracts"
    },
    {
      "id": "surface-design-eval-security-tasks",
      "path": "docs/design/eval-security-tasks.html",
      "title": "Eval Security Tasks",
      "kind": "design-preview",
      "description": "Inspect a rendered design or design-language preview.",
      "artifactId": "design-eval-security-tasks"
    },
    {
      "id": "surface-design-mockups-phase4-report",
      "path": "docs/design/mockups/phase4-report.html",
      "title": "harness-bench report mockup (row 20)",
      "kind": "design-preview",
      "description": "Inspect a rendered design or design-language preview."
    },
    {
      "id": "surface-design-run-lifecycle-model",
      "path": "docs/design/run-lifecycle-model.html",
      "title": "Run Lifecycle Model",
      "kind": "design-preview",
      "description": "Inspect a rendered design or design-language preview.",
      "artifactId": "design-run-lifecycle-model"
    },
    {
      "id": "surface-proposals-benchmark-state-and-target",
      "path": "docs/proposals/benchmark-state-and-target.html",
      "title": "Benchmark: state and target",
      "kind": "knowledge-tool",
      "description": "Open an interactive knowledge artifact.",
      "artifactId": "proposal-benchmark-state-and-target"
    },
    {
      "id": "surface-coordination-coordination-e2e4",
      "path": "docs/coordination/coordination-e2e4.html",
      "title": "Coordination E2E4",
      "kind": "knowledge-tool",
      "description": "Open an interactive knowledge artifact.",
      "artifactId": "coordination-e2e4"
    },
    {
      "id": "surface-coordination-coordination-eval-campaign",
      "path": "docs/coordination/coordination-eval-campaign.html",
      "title": "Coordination Eval Campaign",
      "kind": "knowledge-tool",
      "description": "Open an interactive knowledge artifact.",
      "artifactId": "coordination-eval-campaign"
    },
    {
      "id": "surface-coordination-coordination-phase1-finish",
      "path": "docs/coordination/coordination-phase1-finish.html",
      "title": "Coordination plan - finish harness-bench phase 1 (pre-merge findings, N5, mutation bar, E2E)",
      "kind": "knowledge-tool",
      "description": "Open an interactive knowledge artifact.",
      "artifactId": "coordination-phase1-finish"
    },
    {
      "id": "surface-proposals-enterprise-production-portfolio",
      "path": "docs/proposals/enterprise-production-portfolio.html",
      "title": "Enterprise production portfolio",
      "kind": "knowledge-tool",
      "description": "Open an interactive knowledge artifact.",
      "artifactId": "proposal-enterprise-production-portfolio"
    },
    {
      "id": "surface-plans-eval-x-j1a",
      "path": "docs/plans/eval-x-j1a.html",
      "title": "Eval X J1A",
      "kind": "knowledge-tool",
      "description": "Open an interactive knowledge artifact.",
      "artifactId": "plan-eval-x-j1a"
    },
    {
      "id": "surface-plans-eval-x-j1b",
      "path": "docs/plans/eval-x-j1b.html",
      "title": "Eval X J1B",
      "kind": "knowledge-tool",
      "description": "Open an interactive knowledge artifact.",
      "artifactId": "plan-eval-x-j1b"
    },
    {
      "id": "surface-plans-eval-x-j1c",
      "path": "docs/plans/eval-x-j1c.html",
      "title": "Eval X J1C",
      "kind": "knowledge-tool",
      "description": "Open an interactive knowledge artifact.",
      "artifactId": "plan-eval-x-j1c"
    },
    {
      "id": "surface-plans-eval-x-j1d",
      "path": "docs/plans/eval-x-j1d.html",
      "title": "Eval X J1D",
      "kind": "knowledge-tool",
      "description": "Open an interactive knowledge artifact.",
      "artifactId": "plan-eval-x-j1d"
    },
    {
      "id": "surface-plans-eval-x-j1e",
      "path": "docs/plans/eval-x-j1e.html",
      "title": "Eval X J1E",
      "kind": "knowledge-tool",
      "description": "Open an interactive knowledge artifact.",
      "artifactId": "plan-eval-x-j1e"
    },
    {
      "id": "surface-plans-eval-x-k1a",
      "path": "docs/plans/eval-x-k1a.html",
      "title": "Eval X K1A",
      "kind": "knowledge-tool",
      "description": "Open an interactive knowledge artifact.",
      "artifactId": "plan-eval-x-k1a"
    },
    {
      "id": "surface-case-study",
      "path": "docs/case-study.html",
      "title": "From Specification to Implementation: An AI-Forward Case Study",
      "kind": "knowledge-tool",
      "description": "Open an interactive knowledge artifact."
    },
    {
      "id": "surface-proposals-harness-bench-report-mockup",
      "path": "docs/proposals/harness-bench-report-mockup.html",
      "title": "harness-bench · run 2026-09-23 (mockup)",
      "kind": "knowledge-tool",
      "description": "Open an interactive knowledge artifact."
    },
    {
      "id": "surface-coordination-coordination-finish-harness-bench",
      "path": "docs/coordination/coordination-finish-harness-bench.html",
      "title": "harness-bench — Documentation",
      "kind": "knowledge-tool",
      "description": "Open an interactive knowledge artifact.",
      "artifactId": "coordination-finish-harness-bench"
    },
    {
      "id": "surface-specs-harness-bench",
      "path": "docs/specs/harness-bench.html",
      "title": "harness-bench — Documentation",
      "kind": "knowledge-tool",
      "description": "Open an interactive knowledge artifact.",
      "artifactId": "spec-harness-bench"
    },
    {
      "id": "surface-coordination-eval-wave2-e1-overnight-2026-10-05",
      "path": "docs/coordination/eval-wave2-e1/overnight-2026-10-05.html",
      "title": "Overnight 2026 10 05",
      "kind": "knowledge-tool",
      "description": "Open an interactive knowledge artifact.",
      "artifactId": "coordination-eval-wave2-e1-overnight-2026-10-05"
    },
    {
      "id": "surface-proposals-pack-onoff-analysis",
      "path": "docs/proposals/pack-onoff-analysis.html",
      "title": "Pack on vs pack off: grid-1 analysis",
      "kind": "knowledge-tool",
      "description": "Open an interactive knowledge artifact.",
      "artifactId": "proposal-pack-onoff-analysis"
    }
  ],
  "graphSha256": "4a95cafa364caa7ac04de6276c38b9129621af8b33ee1417c69e7c927d27a6b1"
};
