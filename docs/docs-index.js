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
      "status": "draft",
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
      "sourceSha256": "7f9897c54b9e14046d46c06fed15a518004abbdf723876558ecdabf831999f47"
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
      "summary": "Measured cells are launched by a small bench-owned driver that speaks ACP to the containerised harness with a container-side cwd, a verbatim prompt, a per-cell model pin, deny-all permissions and a deadline on every step. The pack's coord-runner cannot meet US-9, US-10 or US-11 as installed; Harbor's one-shot, permissive agent runs cannot meet US-10 (scenario 1), US-14 or at-most-once. Both are recorded, with a trigger to re-evaluate.",
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
      "sourceSha256": "f3fa01c81f357cbbc1877f35c596c4ef9db06b23e1047f534cd3f3715f9a3cc3"
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
      "sourceSha256": "d8300c592cd7661ff8f690ce763e5aca908606df5ac75dece05416ecbd7fb473"
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
      "sourceSha256": "5ab6773b168dcb0e7c2c37ff5e8c417aa80065eabc7a6d6e921ec410fb88d881"
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
      "sourceSha256": "48b86c050a02aa0e3372a3726a72b6b34f3749fefc8f2f4816de1ad28e33971d"
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
      "summary": "The durable record is a set of append-only, hash-chained JSON Lines facts per run with declared grains (lifecycle events, model calls, tool calls, archive files, grading passes, scores, verdict uses, egress events), immutable content-addressed dimensions, and one shared content-addressed verdict cache. Current states, costs, composites and statistics are derived views in in-memory DuckDB; no results database is persisted.",
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
      "sourceSha256": "902ad09be38897d6758d6208ed986812da1dbf65303b294e4fcc74a520c90ed2"
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
      "sourceSha256": "69a487a6e12cc52c37031aa04a364d04f3312ef487925e17fe905b79634d74ee"
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
      "sourceSha256": "f02eb68a95d6fc3d5707d71371188bb54f569ab59abfe4fb484a9bfadf37823b"
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
      "summary": "Judges, the AI summaries and the model rung of the scripted-user matcher call models through one gateway: no tools, schema-constrained output, agent text as delimited data, results read through the shared content-addressed cache, every payload through the egress gate. One backend is built, chosen by the owner before phase 3; if it is unavailable, the result is NOT_RECORDED.",
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
      "sourceSha256": "70c8ac2b2526afa68aff7add13626469e0e3d753feef6e971b26a446a2646662"
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
      "sourceSha256": "8614159b91624a504dc796601e295aea4751b7d273c9335fbbcfee150633a520"
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
      "id": "arch-harness-bench",
      "path": "docs/architecture.md",
      "title": "Architecture: harness-bench",
      "type": "architecture",
      "status": "draft",
      "owner": "@timianmalloo",
      "phase": "S-02 architecture of record (smoke milestone first)",
      "reviewBy": "2027-03-22",
      "reviewSuggested": [],
      "summary": "A deterministic pipeline (plan, run, grade, report) whose single-writer run engine launches every measured cell in its own hardened Linux container through a bench-owned ACP driver, with a pinned per-cell harness profile, a static permission profile, no reach to host credentials, and grading in no-network containers. Hash-chained append-only ledgers per run are the record; every result is a derived view. Models appear only as the systems under test and, tool-less, as judges, summarizer and matcher.",
      "tags": [
        "benchmark",
        "architecture",
        "containers",
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
          "mermaid": "flowchart TB\n  subgraph Session[\"Coordinator session (Claude Code, /start-benchmark)\"]\n    SK[start-benchmark skill: compile, confirm, relay, audit-log entries]\n  end\n  subgraph Host[\"bench (Python, T0) on the Windows host\"]\n    CLI[bench CLI: validate, plan, run, status, stop, grade, report, verify, teardown]\n    ENG[Run engine: single writer, lifecycle = run_lifecycle.tla]\n    WSB[Workspace builder]\n    IMG[Image builder: env image + pinned harness layer, SBOM, CVE scan]\n    PRF[(Harness profiles: build, mode, pin, home seeding, reader)]\n    DRV[ACP cell driver]\n    ARC[Archiver: no link following, exact-value credential scan]\n    TEL[Telemetry: readers + normaliser]\n    GRD[Grade orchestrator]\n    GW[Model gateway: tool-less]\n    EG[Egress gate]\n    VIEWS[In-memory DuckDB views]\n    REP[Report: CLI + HTML + summaries]\n  end\n  subgraph Store[\"runs/<run_id>/ + cache/\"]\n    LED[(hash-chained facts: events, model_calls, tool_calls, archive_files, scores, verdict_uses, egress_events)]\n    ARCH[(cell archives)]\n    CTL[(control/: stop, decision answers)]\n    VC[(shared verdict cache)]\n  end\n  subgraph Docker[\"Docker Desktop (WSL2)\"]\n    PROXY[Egress proxy, off-the-shelf]\n    CELL[Cell containers: one network each]\n    GC[Grading containers: --network none, read-only mounts]\n  end\n  SK -->|bench plan / run / status --json| CLI\n  SK -->|decision answers| CTL\n  CLI --> ENG\n  ENG --> WSB & IMG & DRV & ARC\n  PRF --> IMG & DRV & TEL\n  DRV -->|docker run -i hb-run-cell, ACP stdio| CELL\n  CELL --> PROXY\n  CTL --> ENG\n  ENG --> LED\n  ARC --> ARCH\n  ARCH --> TEL --> LED\n  ARCH --> GRD --> GC\n  GRD --> LED\n  GRD --> GW\n  GW --> VC\n  GW --> EG\n  LED --> VIEWS --> REP\n  REP --> GW\n  REP --> EG"
        }
      ],
      "sourceSha256": "26c5611fa941899840d3f952a8de13b051722670a1da8957f8e0803c0e23739b"
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
      "title": "Spikes R1, R2, R11: config isolation, static permissions, host isolation",
      "type": "doc",
      "status": "draft",
      "owner": "@timianmalloo",
      "phase": "",
      "reviewBy": "2026-10-23",
      "reviewSuggested": [],
      "summary": "Per-cell config homes keep sign-in and drop user-level skills for all three harnesses, but a workspace under the user profile still loads ~/.claude/CLAUDE.md, and Claude's account context (email, account-synced skills) survives any isolation. A static profile runs shell and edits with zero prompts on every harness, but only Codex sandboxes commands on native Windows. Linux containers give every harness the same containment; Claude and Codex ran in one, Copilot needs a token passed in.",
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
      "sourceSha256": "da09fde2b6acb845cf2ef7fbf540d2f522c69fe258b220867596d76209aaa798"
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
      "sourceSha256": "638b7bc5ce30570528fdd9cd0e2c215c3b55158c2676b69e3b7444562856d82e"
    },
    {
      "id": "spec-harness-bench",
      "path": "docs/specs/harness-bench.md",
      "title": "Spec: harness-bench, a cross-harness, cross-model benchmark with the pack as a factor",
      "type": "spec",
      "status": "draft",
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
      "sourceSha256": "bb9f19ef8b7841cfb7e8fadb210fd062a6c588ab3857b27b4bdf5fe44a2413fc"
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
  "graphSha256": "df90d4818aacf31809b870d94492c8e9232a945ee4279215cb8e3514a198e096"
};
