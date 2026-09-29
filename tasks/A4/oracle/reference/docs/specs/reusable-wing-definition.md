# Spec: Reusable Wing Definition

- **Status:** Draft
- **Tier (cost-of-error):** T1
- **Related:** cfd-bench P0 "Conventions & spine" (`CfdBench.Core`).

## Part A — Functional specification

This specification defines the persistence mechanism that makes the P0 wing definition reusable across separate runs and analysis invocations on a local machine.

### Problem

In P0, a wing aggregate is instantiated programmatically in memory. Once the execution completes or the process exits, the wing geometry is lost. Engineers running parameter sweeps, structural checks, or iterative design runs require the ability to save a verified wing definition to disk and reload it in subsequent runs without data loss, precision drift, or re-specifying station geometries.

### Conceptual domain model

Bounded context: Wing Persistence within the CfdBench design lifecycle.

Ubiquitous language:

- **Wing Document** — A persistent serialized representation of a `Wing` aggregate stored in a local project file.
- **Format Identifier** — A required header field (`schema: "cfd-wing/1"`) identifying the document type and version.
- **Station Record** — The serialized representation of a `Station` value object (span position, leading-edge x, chord, twist angle).
- **Fail-Closed Validation** — The principle that any corrupt, unversioned, unsupported, or invariant-violating document is refused immediately without constructing or returning a partial `Wing`.
- **Derived Omission** — The principle that planform quantities (span, projected area, aspect ratio, mean chord) are purely derived functions of the defining stations and are never persisted in the document.

Domain Invariants:
1. Every stored station coordinate and length represents metres; twist angle represents radians (or degrees with explicit conversion).
2. The document must carry a recognized format version string (`cfd-wing/1`).
3. Loading validates and enforces all `Wing` aggregate invariants (at least two stations, root at centreline $y=0$, strictly increasing span positions, strictly positive chords).
4. No derived quantities, mesh caches, CFD polars, or simulation output data are stored in the wing document.

### Core scenario

An engineer configures a wing geometry using `CfdBench.Core.Domain.Wing` with multiple stations. The engineer invokes the persistence component to save the definition to a file `wing.json`. The file is written as UTF-8 formatted JSON with format identifier `cfd-wing/1`. In a subsequent run or separate process, the engineer loads `wing.json`. The loader parses the document, validates the schema version and all domain invariants, and reconstructs the immutable `Wing` aggregate. Derivations computed on the reloaded wing match the original values to machine precision.

### In scope / Out of scope (explicit non-goals)

- **In scope:**
  - Local filesystem persistence: saving and loading wing definitions to and from local files.
  - Serialization format: standard human-readable JSON encoding.
  - Schema versioning: explicit format identifier (`cfd-wing/1`) enabling future format migration and fail-closed rejection of incompatible versions.
  - Validation: strict validation of document syntax, schema structure, and wing invariants upon load.
  - Round-trip fidelity: identical station coordinates and planform derived quantities upon re-loading.
- **Out of scope (explicit non-goals):**
  - Networked, multi-tenant, or cloud service sharing (no remote database, API server, or HTTP endpoint).
  - Persisting derived quantities, CFD simulation meshes, surface polars, or solver convergence history (these are derived on the fly or stored in later-phase analysis contexts).
  - Direct CAD/STEP export (export remains an abstraction port as defined in P0).
  - Graphical user interface or file chooser dialogs (this phase provides a headless library and CLI contract).

### User stories & acceptance criteria (testable)

**US-1 — Save and reload wing definition**
- **Given** a valid `Wing` aggregate with root and tip stations,
- **When** the wing is saved to a local JSON file and reloaded,
- **Then** the reloaded `Wing` contains the exact same sequence of stations and produces identical derived quantities (span, area, aspect ratio, mean chord).

**US-2 — Rejection of unsupported schema versions**
- **Given** a wing document file whose schema version is missing, empty, or unrecognized (e.g., `cfd-wing/2` when only `cfd-wing/1` is supported),
- **When** the file is loaded,
- **Then** loading fails closed with a `SchemaVersionException`, and no `Wing` instance is returned.

**US-3 — Rejection of invalid geometry and invariant violations**
- **Given** a wing document where span positions do not strictly increase, root span is non-zero, or chord is negative/zero,
- **When** the file is loaded,
- **Then** loading fails closed with an `InvariantValidationException` naming the violated rule, and no partial `Wing` is constructed.

**US-4 — Omission of derived quantities in stored documents**
- **Given** a serialized wing document generated by the persistence serializer,
- **When** the JSON text is inspected,
- **Then** it contains only the schema version, metadata, and defining stations; it contains no keys for `Span`, `ProjectedArea`, `AspectRatio`, or `MeanChord`.

**US-5 — Malformed file handling**
- **Given** a file containing truncated or malformed JSON,
- **When** loading is attempted,
- **Then** loading fails closed with a descriptive parsing error and leaves process state clean.

### Non-functional requirements (ISO/IEC 25010 checklist)

| Characteristic | Requirement |
|---|---|
| **Performance Efficiency** | Serialization and deserialization of a wing with up to 64 stations takes under 20 ms on standard hardware. |
| **Reliability** | Fail-closed operation: any syntax or invariant error aborts loading without returning an unvalidated or incomplete object. |
| **Security** | Safe JSON deserialization with no polymorphic type instantiation or arbitrary code execution vulnerabilities. |
| **Usability** | Clear, actionable error messages indicating the exact file position and invariant failure on rejection. |
| **Compatibility** | Standard UTF-8 JSON encoding compatible with cross-platform tools. Explicit format versioning for schema evolution. |
| **Maintainability** | Clean separation of persistence schema DTOs from core domain entities (`Wing`, `Station`). |
| **Portability** | Platform-neutral: standard POSIX/Windows forward-slash path handling, newline agnostic (CRLF/LF), runs identically on Windows and macOS. |

### Document schema definition

The serialized JSON document schema `cfd-wing/1`:

```json
{
  "schema": "cfd-wing/1",
  "name": "example-foil",
  "stations": [
    {
      "span_position_m": 0.0,
      "leading_edge_x_m": 0.0,
      "chord_m": 0.25,
      "twist_deg": 2.0
    },
    {
      "span_position_m": 0.75,
      "leading_edge_x_m": 0.05,
      "chord_m": 0.15,
      "twist_deg": 0.0
    }
  ]
}
```

## Part B — UX specification

This component provides file-based programmatic APIs for C#/.NET and CLI tool interactions:

1. **Programmatic API:**
   - `WingDocument.Save(Wing wing, string path)` / `WingDocument.Save(Wing wing, Stream stream)`
   - `Wing WingDocument.Load(string path)` / `Wing WingDocument.Load(Stream stream)`
2. **CLI Interface (headless):**
   - File paths can be passed as standard command arguments.
   - Standard exit codes: 0 for success, non-zero with error output on stderr on failure.

No interactive desktop or graphical user experience is in scope for this foundational persistence layer.

## Part C — UI specification

N/A — This phase delivers headless domain persistence. There is no graphical user interface. All interactions occur via the code API or command-line execution.
