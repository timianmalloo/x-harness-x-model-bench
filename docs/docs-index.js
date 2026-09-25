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
      "sourceSha256": "3834bc9469bcb9d9f630554ad916e986a68a2b4db501167cc472b21e4d1b5c43"
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
      "sourceSha256": "9527f6472003f7649c6c2d6e1d67a0f90fc18034855d401df43d15804875cdba"
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
      "sourceSha256": "734bdbbc4651013d8130c1527ee3a0081b9cdeee241ea85c3a7e6e9bfbbb04ed"
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
      "sourceSha256": "ffb65ee78047574b4ae1a7adaef18a42e654ffe3fcacde850070f9e7e612cc31"
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
      "sourceSha256": "1435fdb058057ecb9167b2697b0a614d555e1333b0ce25cdca9bcae20b08b955"
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
      "sourceSha256": "78ab25577cbd309b85a4b28378ba4ee6886a2a248a3a6b16b696366e5d62d097"
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
      "reviewSuggested": [],
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
      "sourceSha256": "b15244d34330ebd4917bbc7599bd30944f2de10767b6a719ec18a0e19c25ee7f"
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
      "reviewSuggested": [],
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
      "sourceSha256": "3dbc40e3d87e76548cf8bda92266fefc77892f87086a180ae5a9572d91b287b7"
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
      "reviewSuggested": [],
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
      "sourceSha256": "e3758a322c4c304094423a3dcbb878e9e27b6da53cfc143d58e6c917801e3674"
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
      "reviewSuggested": [],
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
      "sourceSha256": "61cfd44cdac602696254e7d583e506632d4d03ba4085917387d46cf9fab1e519"
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
      "reviewSuggested": [],
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
      "sourceSha256": "ea4db9cd170dcaf00bf7f28ce0119db61a05b879c263d8547648c275a31fe0f4"
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
      "sourceSha256": "2d300301d99c0b9a0205e5f40faf745f7ae3613525ec326d34253e580ee46752"
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
      "sourceSha256": "6149319ea64c332b00011cf5ef4f793e5a096a199027a81fd19a8874b3f23b45"
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
      "sourceSha256": "df3e70a068c2a429646a718575759dc3e3536e6ea317237b2e8323a5bf0e7b86"
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
      "sourceSha256": "58005e78a98383b528e807dfc0c9d8cee6b17b92736c7b62b9068ff67a6c3630"
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
      "sourceSha256": "e24377dd1b0e2469f6d3b32e20c9351ff25c467277cebf4b8e02376926b8be82"
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
        }
      ],
      "diagrams": [],
      "sourceSha256": "8a234feb6e1c15bb06d9eaac3ec6142a14c4eeddb494fce360c8d231317842b3"
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
      "sourceSha256": "7a141630228ed2c625049197c50ba3e0c98e51fa22a2a3d80a9736f6e5b603d2"
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
      "sourceSha256": "7f3a8675fbafdd9599e5a90bfd6d3674e8ca85ca79ce301108aab80517198094"
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
      "sourceSha256": "cf96632215fe35af4ab9d8c3c91929e5925db17785e8b6bdeef34158a400c17b"
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
    }
  ],
  "graphSha256": "afc718647e56f5914482f74d88c1f05ee66f911070f62e318f6b500cd51643c4"
};
