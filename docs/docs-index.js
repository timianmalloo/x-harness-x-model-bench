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
      "sourceSha256": "f2f8c54f5fbb39a221b38e3ef81a244d9eaae0d6a96c724febb5e07889a93080"
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
      "sourceSha256": "5bda5fb79f8a242a34b6be8a23e55af0d8137aad880bcc4698dbb8bb2b9299e9"
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
      "summary": "The durable record is a set of append-only, hash-chained JSON Lines facts per run with declared grains (lifecycle events, model calls, tool calls, archive files, grading passes, scores, verdict uses, egress events), immutable content-addressed dimensions, and one shared content-addressed verdict cache. Current states, costs, composites and statistics are derived projections computed in memory; no results database is persisted.",
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
      "sourceSha256": "3bc0d51e529542e271b8ad4d63d45d3c1a58d890cebb56ed9d56829f9e4af309"
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
      "sourceSha256": "d151926d17b6bd3c08e2ce73be95789161da21482aad684668c4fada72cf1495"
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
      "sourceSha256": "da7f2e0eb827dd43af9cf37c552d3326914ea0db5b91a4ce9a5636736cde4aa4"
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
      "sourceSha256": "27da114b153d8f864a697bb171c1c7134c08688e28a136b88768cbd94520af68"
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
      "summary": "Owner ruling: isolation beyond a working copy is not required. Each authored-task cell is a native process on the operator's Windows workstation, working in its own git working copy, with its own harness home and a symmetric unsandboxed permission profile. A Windows Job Object is how the engine stops a cell and knows it has stopped, not a sandbox. Containers, the egress proxy and every other isolation control are dropped for authored tasks; Harbor tasks keep their containers.",
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
      "sourceSha256": "3331dc8a4708de79d045b541cc97882274bf9120b68adc07f018bbeb2fdd0834"
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
          "mermaid": "flowchart TB\n  subgraph Session[\"Coordinator session (Claude Code, /start-benchmark)\"]\n    SK[start-benchmark skill: compile, confirm, relay, audit-log entries]\n  end\n  subgraph Host[\"bench (Python, T0) on the Windows host\"]\n    CLI[bench CLI: validate, plan, run, status, stop, grade, report, verify, teardown]\n    ENG[Run engine: single writer, lifecycle = run_lifecycle.tla]\n    WSB[Workspace builder]\n    TLS[Tools folder: pinned harness builds]\n    PRF[(Harness profiles: build, mode, pin, home seeding, reader)]\n    DRV[ACP cell driver]\n    ARC[Archiver: no link following, exact-value credential scan]\n    TEL[Telemetry: readers + normaliser]\n    GRD[Grade orchestrator]\n    GW[Model gateway: tool-less]\n    EG[Egress gate]\n    VIEWS[Pure-Python projections]\n    REP[Report: CLI + HTML + summaries]\n  end\n  subgraph Store[\"runs/<run_id>/ + cache/\"]\n    LED[(hash-chained facts: events, model_calls, tool_calls, archive_files, scores, verdict_uses, egress_events)]\n    ARCH[(cell archives)]\n    CTL[(control/: stop, decision answers)]\n    VC[(shared verdict cache)]\n  end\n  subgraph Cells[\"bench-cells/<run>/<cell> (native, one Job Object each)\"]\n    CELL[Cell: own working copy + own harness home]\n    GC[Grading working copy: archive + hidden tests]\n  end\n  SK -->|bench plan / run / status --json| CLI\n  SK -->|decision answers| CTL\n  CLI --> ENG\n  ENG --> WSB & DRV & ARC\n  PRF --> TLS & DRV & TEL\n  DRV -->|spawn into Job Object, ACP stdio| CELL\n  CTL --> ENG\n  ENG --> LED\n  ARC --> ARCH\n  ARCH --> TEL --> LED\n  ARCH --> GRD --> GC\n  GRD --> LED\n  GRD --> GW\n  GW --> VC\n  GW --> EG\n  LED --> VIEWS --> REP\n  REP --> GW\n  REP --> EG"
        }
      ],
      "sourceSha256": "3818fd2d2aab1026085f985ce30b198952054a67b41518fd26edf40ce4c12272"
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
      "sourceSha256": "308efde4ed027bd66a2041d7794ff268fa4bbcc643e7292e80edb676c86cebf5"
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
      "reviewSuggested": [],
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
      "sourceSha256": "41027ae770a5fe7fa2980604d3d89240ff3f55594bdda9be39dbbcf2716aeafc"
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
      "sourceSha256": "246f0a3686348504280a109df10b0f4f82f65129cbce930623d995d7643acada"
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
      "sourceSha256": "b586635d0cf4bf610dca3be2b929c2c8af128770b63ebc4759e13e0ea033054c"
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
      "reviewSuggested": [],
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
      "sourceSha256": "39b32dc8ffae7afa860c3cfa61994c0581ea0251285cc93a553d5ac7d719d3e4"
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
      "reviewSuggested": [],
      "summary": "The TLA+ model of one run's lifecycle, the proof obligation the run engine is built against (US-44). TLC checks 16 safety invariants at the US-44 bounds (3 cells, parallelism 2, 1 engine crash) and at small bounds with `bench grade` contending, grading mutual exclusion at 2 passes, and 5 liveness properties at 1 cell; each of 21 seeded-bug variants is rejected by its own target checked alone, and a witness shows every cell can finish. A mapping table binds every model action to the engine's ledger events, and a conformance test keeps the two in step.",
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
      "sourceSha256": "ab7d72ebcd01e682384553aa51f8163a62a377f079112421a77397dcef4e3e88"
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
      "sourceSha256": "b892b9816cc6d8d7c8512e3b68cf7b388961f4fdbfe6c41e404656cd78f83dc8"
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
      "id": "note-spike-phase1-probes",
      "path": "docs/notes/spike-phase1-probes.md",
      "title": "Phase-1 probes W1, W3, N4: pack install, provider-error rows, job containment",
      "type": "doc",
      "status": "draft",
      "owner": "@timianmalloo",
      "phase": "",
      "reviewBy": "2026-10-23",
      "reviewSuggested": [],
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
      "sourceSha256": "c7120b4935287c2ec0faa4fc3a5313fdab8345eb9b68248f023d26f531cc480d"
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
      "sourceSha256": "0d970fba92ab07db3c068eb4a1bc87122b8fd0c821b3f4df299807aa36efa410"
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
      "reviewSuggested": [],
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
        }
      ],
      "diagrams": [],
      "sourceSha256": "d54e510a81dfb32ebc3f256b4fd6be310d719fba944dcdef11213e6d9ab50dad"
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
      "sourceSha256": "50c64de481f7887d22ec6f6203d646db43fad10042539854e1b6ef2cc9fb24b5"
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
      "reviewSuggested": [],
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
      "sourceSha256": "b7ad3fbf99ce707c6676c51ad16878540dc191bcc63ae47b6b905c9fe54a7798"
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
      "id": "surface-coordination-coordination-phase1-finish",
      "path": "docs/coordination/coordination-phase1-finish.html",
      "title": "Coordination plan - finish harness-bench phase 1 (pre-merge findings, N5, mutation bar, E2E)",
      "kind": "knowledge-tool",
      "description": "Open an interactive knowledge artifact.",
      "artifactId": "coordination-phase1-finish"
    },
    {
      "id": "surface-proposals-harness-bench-report-mockup",
      "path": "docs/proposals/harness-bench-report-mockup.html",
      "title": "harness-bench · run 2026-09-23 (mockup)",
      "kind": "knowledge-tool",
      "description": "Open an interactive knowledge artifact."
    },
    {
      "id": "surface-specs-harness-bench",
      "path": "docs/specs/harness-bench.html",
      "title": "harness-bench — Documentation",
      "kind": "knowledge-tool",
      "description": "Open an interactive knowledge artifact.",
      "artifactId": "spec-harness-bench"
    }
  ],
  "graphSha256": "703acbc6a6e4df90fe925337ac10e57068e97f94b6824189cc2ee6fb7bc72083"
};
