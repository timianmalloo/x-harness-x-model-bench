---
id: backlog
title: "Deferred Work and Spikes"
type: doc
status: accepted
owner: "@timianmalloo"
tags: [backlog, spikes, todo, deferred, ai, evals]
links:
  - { to: kb-cfd-hydrofoil-simulation, rel: depends-on }
  - { to: decision-0001-geometry-kernel, rel: depends-on }
  - { to: kb-ai-in-the-product, rel: depends-on }
review-by: 2026-12-06
summary: >-
  Work that has been consciously deferred rather than forgotten — spikes with a stated question and
  a definition of done, decisions waiting on evidence, and the standing engineering commitments this
  project has made to itself.
---

# Backlog — deferred work and spikes

Every item states **the question**, **what would settle it**, and **what breaks if it is wrong**.
An item without those three is not ready to be here.

## Spikes — deferred, not dropped

### SPIKE-01 · HelixToolkit control-point manipulation
**Status:** deferred by decision, 2026-09-06 · **Size:** ~half a day

**Question.** Can HelixToolkit's manipulator/gizmo support be used to drag a single spline control
point in a 3D viewport, constrained to a plane, with acceptable hit-testing and feedback?

**Why it is uncertain.** The published demos (`ManipulatorDemo`) show *object transforms* — moving a
whole model. `ManipulationBinding` maps manipulation gestures and its binding target was relaxed to
`Element` rather than `GeometryModel3D`. Dragging one control point of many, snapped to a
construction plane, is a different interaction and is not demonstrated.

**Done when.** A throwaway WPF app shows a degree-5 spline in `Viewport3DX` with draggable control
points, plane-constrained, with keyboard nudge at a defined step.

**If it is wrong.** Control-point editing happens in dedicated 2D curve views only (which the design
already favours — the five distribution curves are 2D problems), and the 3D viewport becomes
display-and-select rather than edit. **Recoverable, and the fallback is arguably the better UX
anyway** — which is why this is safe to defer.

### SPIKE-02 · STEP writer round-trip
**Status:** open, blocked on nothing · **Size:** ~1–2 days

**Question.** Can we emit a `B_SPLINE_SURFACE_WITH_KNOTS` AP203 Part 21 file that a real CAM system
opens with a smooth surface?

**Done when.** Fusion 360 (or Mastercam) opens our exported wing, and the surface shows no
faceting, no gaps, and a clean zebra/curvature check.

**If it is wrong.** Fall back to STEPcode (BSD). If that also fails, the fabrication story reduces
to high-density STL, which `kb-fabrication-interop` establishes is materially worse for a
curvature-critical surface.

**Note.** "It writes a file" is not the acceptance test. Opening it elsewhere is.

### SPIKE-03 · snappyHexMesh auto-generation
**Status:** open · **Size:** ~2 days

**Question.** Can meshing settings be generated reliably from the parametric model across the
geometry range, or does each wing need hand-tuning?

**Done when.** Three wings spanning the design range (AR 5 / 8 / 12) mesh unattended and pass
`checkMesh`.

**If it is wrong.** The "you never see a dictionary file" promise fails at the CFD tier, and the
architecture needs a mesh-diagnostics UI rather than a hidden step. **This is the load-bearing
assumption of `kb-cfd-orchestration`.**

### SPIKE-04 · The numeral check
**Status:** open · **Size:** ~half a day

**Question.** Can a mechanical check reliably reject model-generated text containing numbers that
were not supplied to the call, without false-positives on legitimate rounding and unit conversion?

**Why it matters.** It is the deterministic guard on the one non-deterministic component that could
do real damage — an explanation that invents "L/D is around 19" instead of reading 19.8 is
fabricated engineering data with no visible tell.

**Done when.** The check runs over a corpus of good and deliberately-poisoned explanations, catching
every fabricated numeral and passing legitimate rounding of supplied values.

**If it is wrong.** The explain feature ships with model output rendered as clearly-marked prose
that never restates a figure — the numbers stay in the UI chrome beside it, not in the sentence.

## Standing commitments — decisions already made, to be honoured

### COMMIT-01 · Verification at a higher tier
**Confirmed by the user, 2026-09-06.**

No optimiser result is presented as an answer on estimator evidence alone. Every candidate offered
to the user is re-evaluated at the VLM tier first; anything destined for fabrication is verified at
the CFD tier. The rationale is that **optimisation amplifies model error** — a search over tens of
thousands of candidates will find precisely the corner of the design space where the cheap model is
most wrong and present it as the winner.

Three mechanisms, all required:
1. Every optimum re-checked at a higher tier before display.
2. The tool shows where a candidate sits relative to the estimator's validity envelope (attached
   flow, small α, high Re) and flags any near the edge.
3. Candidates carry a **confidence** alongside the score, and are never ranked by score alone.

### COMMIT-02 · No LGPL-family dependencies
**Decided 2026-09-06** — see `decision-0001-geometry-kernel`. Permissive licences only (MIT, BSD,
Apache). OCCT is deferred indefinitely; rhino3dm (MIT) and STEPcode (BSD) are the sanctioned
fallbacks.

### COMMIT-03 · Import means our own format
**Decided 2026-09-06.** The "open an existing wing" path reads **files this tool wrote**, not
arbitrary third-party geometry. Reconstructing stations from an arbitrary B-Rep is a *fitting*
problem and is out of scope. This removes the last requirement that would have needed a geometry
kernel.

### COMMIT-04 · Language in, numbers out
**Decided 2026-09-06** — see `kb-ai-in-the-product`.

The model reads and writes **language**; the solver reads and writes **numbers**. Numbers flow into
the model as context and never out of it as results. No LLM computes or estimates a physical
quantity, chooses a design, generates geometry, or judges structural safety. Every AI capability
ships with an eval or does not ship. The tool is fully usable with no API key and no network.

## Deferred decisions

| Item | Deferred because | Revisit when |
|---|---|---|
| **Mold-block generation** | `kb-fabrication-interop` concluded "export STEP and stop"; molds are made in CAM | Someone actually wants to machine a mold from this tool |
| **G-code generation** | Owning tool libraries, post-processors and collision checking is a second product, and mistakes break machines | Never, on current scope |
| **CAD MCP integration** | Our own model is exact; round-tripping through an MCP server is a lossy translation of geometry we already have | If downstream CAD work (fixtures, assembly context) becomes routine |
| **Inverse design (latent/generative)** | Needs a training corpus that does not exist for hydrofoils | After the CFD tier has generated one |
| **Grasshopper-style visual programming** | The generative layer already covers the parametric need | If users start asking for custom relationships |
| **LIC flow rendering** | Streamlines are cheaper and familiar; LIC is a shader to write and tune | After the 3D viewport is real |
