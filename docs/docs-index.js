// Derived from artifact frontmatter by scripts/docs-graph.py — DO NOT hand-edit (frontmatter wins; see knowledge-visualization.md V2/V18).
window.DOCS_INDEX = {
  "schemaVersion": "docs-index/v2",
  "project": "x-harness-x-model-bench",
  "generator": "docs-graph.py derive",
  "rootId": "audit-log",
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
          "mermaid": "flowchart LR\n  subgraph Catalog[\"Benchmark Catalog\"]\n    BOM[BOM version] --> TV[Task version]\n    MC[Metric catalog version]\n    PL[Price list version]\n  end\n  subgraph Exec[\"Run Execution\"]\n    Run --> Plan[Frozen plan]\n    Run --> Sched[Run scheduler policy]\n    Cell --> Attempt\n  end\n  subgraph Ev[\"Evidence\"]\n    Arch[Cell archive]\n    TD[Teardown policy]\n  end\n  subgraph Gr[\"Grading\"]\n    SS[Score set]\n    JV[Judge verdict]\n    CM[Clarification match]\n  end\n  subgraph Rep[\"Reporting\"]\n    Report\n    Summary[AI summary]\n  end\n  TV -. by identity .-> Cell\n  Run -. by identity .-> Cell\n  Cell -. produces .-> Arch\n  Arch -. graded into .-> SS\n  MC -. version .-> SS\n  PL -. version .-> SS\n  JV --> SS\n  CM --> SS\n  SS --> Report\n  Report --> Summary\n  Exec -. ACL .- Pack[(ai-forward coordination, external)]"
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
      "sourceSha256": "b2753f8a479df28baf97ff95f9c93a2339b18181e30c47ab84626ff6f282c85c"
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
  "graphSha256": "0c65c1bcf50a84717fe88e1309aa321ebdc23385b0d832a2efbd041c27ee0570"
};
