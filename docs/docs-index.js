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
      "sourceSha256": "c63113c0d48dddf26d34faef2c28d0974c731ff6dcd69b0b7368ba630675e176"
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
      "sourceSha256": "b24044b331bb70a584dcecb9bfede068050b01f41b39164f61e7e15e055e36f7"
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
      "sourceSha256": "b239bddc9ac605c41d45c20ca09ff481e25b5f1c1a85f5f35096e8512b39b8e0"
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
      "sourceSha256": "b4affef7efd9943abb53a493634f064ce4e4c0df83a29793e38ce9ad6f885509"
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
      "sourceSha256": "a7ca9f0a61f7bc7f6b1657a189020d642372f91d20e760a91ebc9f26d4215247"
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
      "sourceSha256": "b85c178624f60e2805ec13c6e781b43368d7e18008b510c7b07039d7abcc7dda"
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
      "sourceSha256": "38c63445d9c42604256bae18f3df915c277b7a4312e680bd1bc379dbb8732c60"
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
      "sourceSha256": "fea4b3c8bc2799cfda23a80c7f7c4a422f94b09d92454be36159e6164711c1f6"
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
      "summary": "A restarted `bench run` for an existing run id resumes it: it verifies the ledger, proves each cell terminal from its recorded outcome event, reconciles every non-terminal cell by ADR-0007's rules extended per turn (ADR-0015), relaunches only never-prompted cells in the frozen plan order, and grades once every cell is terminal. It refuses a resume after a stop or under a drifted run-side identity. `bench status` exposes last_progress_at, and `bench status --alarm-after` gives a scheduled check a non-zero exit when progress stalls. A per-launch disk check and a stated worst-case cell and grading time complete the multi-night story.",
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
      "sourceSha256": "a21a64ebc37fb049fb8019ca181c3e0e5d9702befd3ea04ae668ea18d930b598"
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
      "sourceSha256": "f4a94ef16a9889ff1923491693ecb0533e12741e2a9345905ebd65b4e864415d"
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
      "summary": "Revision 2. The one vocabulary the twelve Wave 1 design slices and the Wave 2 tracks share: the ten property-task ids and their BOM and task.yaml stubs, the task.yaml property and expected-value fields, the PropertyCheck input, result, framing and outcome precedence, create_once and the directory publish, bench-matrix/2 and bench-plan/2, the campaign ledger rows and the pre-registration freeze order, the identity manifest, the discrimination record, the catalog 0.7 metric ids under R-90, the power, verdict and gate shapes, every planned new module with its run/grade class, the HB codes reserved per track, the hub-file owner per phase, and the four frozen fields of every shared-surface guard. Ends with the disposition of every finding of the five W0 lens reviews.",
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
      "sourceSha256": "dd54e1963b397b840c92373598cf1c8f166384d556f42353341fa76117933a5c"
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
      "sourceSha256": "52d7d305c96d90c65de701503a8ccf26a2a0e0ad3c180e917fbc0c1413676b77"
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
      "sourceSha256": "187d4f09758f6a375601b9ddb7a0fc2c12f0043c64dd5117e0e97a7f70879f43"
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
      "sourceSha256": "e69173cadc79609b475999dedd6a7a537c2f9b50669f08202809d75aa2581ae4"
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
      "sourceSha256": "cac2581e19b119c1e877e7ca86db14203662fd2f012ae25732366558a495c930"
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
      "sourceSha256": "b2451ce2c599676479ac43eaa5d8dbe031a7e3f79a94f04ea495008870943362"
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
      "sourceSha256": "5665e66315039cf611d9c8fa7f7b9c0b1285fdfc6d3c5e57dc20640175987e95"
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
      "sourceSha256": "5c563cb767a9c366a129acb0c121b925220c29b4b55ab7619236c0679bf89b85"
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
      "sourceSha256": "6498292143c8251d7eacdd9887b620b175937d91c7c69224f58467d473a63c2f"
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
      "sourceSha256": "0b00511fbc81f9dfcea0fbc2fdc36dbbc7e4c8b273f2c38248dcaa6d328fbcde"
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
      "sourceSha256": "419eae4b6c538261f2df8886c398978b0fb458cc0ff45ed486e089ecb4f65f2d"
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
      "sourceSha256": "218e6fe8bdf9182f9e5f9a52aa75b17228f0f92ed2e7a0fb04b8e870831f87fa"
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
      "sourceSha256": "87ef42f05959e3fc15a32c08c3961ded84c6c97f6551d661d51d538592619e09"
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
      "sourceSha256": "6abf11a4043297b0f4e7fc2e3f3465e3575d54b2a68242649ee0a4e20298d7c4"
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
      "sourceSha256": "a65992eab45e0bcfbeca7493342745a82f72c6bf1233e821dac5f0dfdcaa33ac"
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
      "sourceSha256": "a6b2110475049b1bceb5252b93fed89dc6b5c653ae3fec30aec2975c0f1d91b2"
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
      "id": "surface-design-eval-seam-contracts",
      "path": "docs/design/eval-seam-contracts.html",
      "title": "Eval Seam Contracts",
      "kind": "design-preview",
      "description": "Inspect a rendered design or design-language preview.",
      "artifactId": "design-eval-seam-contracts"
    },
    {
      "id": "surface-design-mockups-phase4-report",
      "path": "docs/design/mockups/phase4-report.html",
      "title": "harness-bench report mockup (row 20)",
      "kind": "design-preview",
      "description": "Inspect a rendered design or design-language preview."
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
      "id": "surface-proposals-pack-onoff-analysis",
      "path": "docs/proposals/pack-onoff-analysis.html",
      "title": "Pack on vs pack off: grid-1 analysis",
      "kind": "knowledge-tool",
      "description": "Open an interactive knowledge artifact.",
      "artifactId": "proposal-pack-onoff-analysis"
    }
  ],
  "graphSha256": "56bd8da86f6d064b5c9847718cc31c80a243cc60e737d3357082465f35aa6e43"
};
