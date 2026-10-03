---
id: "note-spike-s12-formal-toolchains"
title: "Spike S-12: TLA+ and Lean 4 toolchains run natively on the Windows operator host"
type: doc
status: draft
owner: "@timianmalloo"
tags: [benchmark, spike, formal-methods, tla+, lean, toolchain, S-12, G1, G2]
links:
  - { to: plan-spec-backlog, rel: refines }
  - { to: note-proposal-grounding-findings, rel: refines }
  - { to: adr-0013-native-cells, rel: depends-on }
  - { to: spec-harness-bench, rel: relates-to }
review-by: "2026-10-29"
summary: >-
  Both toolchains proved out natively on this Windows 11 host. TLA+: Temurin JDK 21 already on
  PATH, tla2tools.jar v1.7.4 re-downloaded and its sha256 matched tools/check_models.py's pin
  exactly, TLC checked run_lifecycle.tla (liveness config) clean in 10.4s inside a fresh git
  worktree. Lean 4: elan 4.2.4 installed natively to the operator's per-user ~/.elan, a minimal
  no-Mathlib lake project pinned to leanprover/lean4:v4.34.1 built clean (`#print axioms` shows
  only propext/Quot.sound, no sorry) in a fresh git worktree; first build (toolchain
  download+install+build) took 54.3s, a rebuild with the toolchain already warm took 1.1s. The
  elan toolchain cache is 3.1 GB and lives outside any cell's working copy; a cell's own
  `.lake/build` is 70 KB. macOS is unverified for both toolchains (marked, not guessed): no
  macOS CI job exists today. Nothing in either toolchain failed; a first draft Lean proof was
  wrong (my error, not a toolchain fault) and was fixed.
review-suggested:
  - { by: adr-0013-native-cells, on: 2026-10-03, reason: "Proposed amendment 2026-10-03 (ADR-0014/0015, arch-evaluation-campaign): cell grain by arm, per-turn prompt_sent, archive_files snapshot key part, job terminated after the last turn; council gate pending" }
---

# Spike S-12: TLA+ and Lean 4 toolchains run natively on the Windows operator host

Date: 2026-09-29. Machine: this Windows 11 workstation (the same host `docs/notes/spike-isolation-permissions.md` and ADR-0013 describe). Worker: `worker-sonnet-s12` in worktree `C:/Projects/x-harness-x-model-bench-w5-s12` (branch `w5-s12`). Resolves F9's toolchain flag and is the declared dependency of S-08g, T-G1 and T-G2 (`docs/specs/README.md`).

Labels: **Verified** = run here, this session; **Assume** = a marked belief, with what would confirm it and what breaks if false; **Flagged** = open, needs a decision.

**Terminology note (Assume).** This spike's Done-when text calls for the checks to run "inside a fresh git worktree," so that is the mechanism used below (`git worktree add`, twice, into the scratch directory). ADR-0013 Decision 1 says the actual G1/G2 cell will be a **`git clone --local`**, explicitly *not* a `git worktree` (worktrees of one clone share refs, stashes and config across cells; that was rejected at the gate). **Assume:** for a single formal-methods invocation (TLC or `lake build`), which only reads files and runs a standalone JVM/Lean process against a working directory, a worktree and a local clone present the same surface to the tool — neither TLC nor `lake` reads refs, stashes or shared config. **What would confirm it:** re-running these same two checks inside a `git clone --local` working copy once S-08g's cell scaffolding exists. **What breaks if false:** a toolchain quirk (path resolution, `.git` file vs. directory, case sensitivity) that only shows up under a real clone; low risk, cheap to catch at first cell run. A same-repo `git clone --local` attempted here for cross-check hit unrelated checkout errors (see "What failed," below) and was abandoned rather than debugged, since it is not what Done-when asked for.

## 1. TLA+

| Item | Value |
| --- | --- |
| JDK on PATH | Temurin 21.0.11+10 LTS (`openjdk version "21.0.11" 2026-04-21`), Eclipse Adoptium build, at `C:\Program Files\Eclipse Adoptium\jdk-21.0.11.10-hotspot\bin\java.exe` |
| tla2tools.jar pin | `v1.7.4`, matching `tools/check_models.py` (`TLA_VERSION`/`JAR_URL`/`JAR_SHA256`) |
| sha256, re-verified | `936a262061c914694dfd669a543be24573c45d5aa0ff20a8b96b23d01e050e88` — **matches the pin exactly** |
| Model checked | `models/run_lifecycle.tla` + `models/run_lifecycle.liveness.cfg` (1 cell; the smallest of the three configs) |
| TLC result | `Model checking completed. No error has been found.` — 188,425 states generated, 58,016 distinct, exit code 0 |
| Wall time | 10.4s (parse + implied-temporal check + full state-space check) |
| Worktree | fresh `git worktree add <scratch>/wt-tla HEAD -b spike-s12-tla-check`, removed after the run |

**How the JDK is installed natively on Windows [Verified, pre-existing on this host]:** the Eclipse Adoptium (Temurin) MSI installer, machine-wide under `C:\Program Files\Eclipse Adoptium\`. This install pre-dated the spike (this session did not install it) and matches CI's own `actions/setup-java@v4` with `distribution: temurin`, `java-version: "21"` (`.github/workflows/ci.yml` `models` job) — the same distribution and major version, Windows here vs. `ubuntu-latest` in CI. TLC's own startup banner corroborates the runtime it actually used: `Eclipse Adoptium 21.0.11 x86_64`.

**On macOS [Assume]:** Eclipse Adoptium publishes an official Temurin 21 `.pkg`/`.tar.gz` for macOS (x64 and aarch64) at the same per-machine/per-user convention. **What would confirm it:** a `macos-latest` job added to `.github/workflows/ci.yml` running `actions/setup-java@v4` the same way the `models` job does, then `python tools/check_models.py`. **What breaks if false:** none of this spike's Windows evidence carries over; ADR-0013 Amendment 1 requires native execution on macOS too, so this is a real gap, not a formality — **no such CI job exists today** (the workflow file has exactly two jobs, `test` on `windows-latest` and `models` on `ubuntu-latest`; confirmed by grep, no macOS job anywhere in `.github/workflows/`).

**Commands run, exactly:**
```
curl -O --location https://... (jar download via urllib, see below)
java -XX:+UseParallelGC -XX:MaxRAMPercentage=75 -cp .tools/tla2tools.jar tlc2.TLC -workers auto -metadir <tmp> -config run_lifecycle.liveness.cfg run_lifecycle.tla
```
(cwd = `models/`, matching `tools/check_models.py`'s own `cwd=MODELS`; TLC could not resolve the module when invoked with `models/run_lifecycle.tla` as a path argument from the worktree root — the module search path is relative to the process's cwd, not the argument's directory. This is a real gotcha for whatever invokes TLC directly: run it with cwd set to the directory holding the `.tla`/`.cfg` files, or pass `-lib <models dir>`, not a bare relative path from elsewhere.)

## 2. Lean 4

| Item | Value |
| --- | --- |
| elan version | `4.2.4 (227caca13 2026-08-25)` — the current `leanprover/elan` GitHub release |
| elan install command | `curl -O --location https://elan.lean-lang.org/elan-init.ps1` then `& .\elan-init.ps1 -NoPrompt $true` (the official Windows path per lean-lang.org's install docs) |
| elan install location | `C:\Users\malla\.elan` — the installer's own standard per-user default (not chosen by me; this is the operator's real home directory, named here per the Not-in-scope instruction) |
| Pinned toolchain | `leanprover/lean4:v4.34.1` (current stable `leanprover/lean4` release, `lean-toolchain` file) |
| Lake project | `lakefile.toml` (no `[[require]]` entries — no Mathlib), one library `SpikeLeanProj` with `SpikeLeanProj/Basic.lean` |
| Theorem | `theorem add_comm_nat (a b : Nat) : a + b = b + a := by omega` (`omega` is Lean 4 core/std, not Mathlib) |
| `#print axioms add_comm_nat` | `'add_comm_nat' depends on axioms: [propext, Quot.sound]` — core axioms only, no `sorryAx` |
| `lake build`, cold (toolchain not yet installed) | exit 1 on the *first* attempt — my draft proof was wrong (`simp` didn't close the inductive step), not a toolchain fault; fixed to `by omega`. Wall time for the cold run (includes downloading + installing the 3.1 GB toolchain) was 54.3s. |
| `lake build`, warm (toolchain cached, corrected proof) | exit 0, `Build completed successfully (4 jobs)`, wall time 1.13s |
| elan toolchain disk size | `C:\Users\malla\.elan` total **3.1 GB** (`leanprover--lean4---v4.34.1` toolchain itself: 3.1 GB; `elan\bin` proxies: 5.7 MB) |
| Project build-output disk size | `.lake/build` inside the project: **70 KB** |
| Worktree | fresh `git worktree add <scratch>/wt-lean HEAD -b spike-s12-lean-check`, with the scratch lake project as an untracked subdirectory; both removed after the run |

**On macOS [Assume]:** elan ships official `elan-x86_64-apple-darwin.tar.gz` and `elan-aarch64-apple-darwin.tar.gz` release assets (checked directly: `gh api repos/leanprover/elan/releases/latest`), and Lean 4 publishes macOS toolchain archives at `releases.lean-lang.org`, so the same install path (elan → `lean-toolchain` pin → `lake build`) should work unchanged. **What would confirm it:** the same `macos-latest` CI job named above, run once with `curl ... | elan-init` (the Unix install form) instead of the PowerShell script. **What breaks if false:** ADR-0013 Amendment 1's native-macOS requirement is unmet for G2 — again, **no CI job currently exists to catch this**.

## 3. What a cell needs warmed before its clock starts

| Cache | Path | Outside the cell's working copy? |
| --- | --- | --- |
| JDK | `C:\Program Files\Eclipse Adoptium\jdk-21.0.11.10-hotspot` | Yes — machine-wide install, already on PATH; nothing to warm per cell |
| `tla2tools.jar` | `<working copy>/.tools/tla2tools.jar` (`tools/check_models.py`'s own `ROOT / ".tools"`, `ROOT` = the script's own repo root) | **No** — `check_models.py` downloads it into *this* clone/worktree if absent. Every fresh cell would re-download it (2.3 MB, ~0.6s here) unless the grading step is changed to point at a machine-level shared path. Cheap today, but it is a **network dependency inside the timed budget**, which conflicts with the design rule quoted in the Measured section ("pinned toolchains warmed before the clock"). **Flagged for S-08g:** either pre-seed `.tools/tla2tools.jar` into every fresh cell clone before the clock starts, or add an env-var override to `check_models.py`'s `JAR` path pointing at a shared, pre-warmed location. Not fixed here — changing engine code is out of scope for this spike. |
| elan toolchains | `%USERPROFILE%\.elan\toolchains\` (here: `leanprover--lean4---v4.34.1`, 3.1 GB) | **Yes** — `~/.elan` is per-user, outside every git working copy. Warmed once per host (`elan toolchain install leanprover/lean4:v4.34.1`, or trigger it via one `lake build` in any project pinned to that version) and then free for every later cell on that host, as the 54.3s → 1.13s difference shows. |
| A Lean project's own build output | `<cell working copy>/.lake/build` | No, and it doesn't need to be — 70 KB, no network, builds in ~1s once the toolchain is warm. Fine to build inside the graded run. |

**Bottom line:** the JDK and the elan/Lean toolchain are the expensive, host-level things to warm once before any cell's clock starts. The TLA+ jar is small enough that its current per-clone download is a nuisance, not a real cost, but it is a network call inside the budget today and should be named as a gap for S-08g.

## 4. How a grading step should invoke each tool

Both must be invoked directly (a real process create), never through `cmd.exe /c`, and with forward-slash paths — this repo already does that for TLC (`tools/check_models.py` builds a `subprocess.run([...])` argv list, no shell). Lean has no equivalent script here yet; the pattern verified in this spike:

- **TLC:** `java -XX:+UseParallelGC -XX:MaxRAMPercentage=75 -cp <root>/.tools/tla2tools.jar tlc2.TLC -workers auto -metadir <tmp>/meta -config <model>.<name>.cfg <model>.tla`, run with `cwd` set to the directory holding the `.tla`/`.cfg` files (see the gotcha in §1) — every path argument forward-slashed, e.g. `C:/Projects/.../models`.
- **Lean/lake:** `<ELAN_HOME>/bin/lake.exe build` (or `<ELAN_HOME>/bin/lake` once on PATH), run with `cwd` set to the lake project root (where `lakefile.toml` and `lean-toolchain` live); `<ELAN_HOME>/bin/lake.exe env lean <file>.lean` for a one-off `#print axioms` check. `ELAN_HOME` is `%USERPROFILE%/.elan` by elan's own default; a grading step should resolve it once at host-warm time and pass the absolute forward-slash path, not rely on an inherited PATH.

## 5. What failed, plainly

- **Nothing in either toolchain failed.** Both JDK+TLC and elan+lake+Lean ran clean and produced the expected results once given correct inputs.
- **My own error, not a toolchain fault:** the first draft Lean theorem's `simp`-based induction proof didn't close (`unsolved goals` on the successor case). Rewritten to `by omega` (Lean 4 core, decides linear Nat arithmetic, no Mathlib) and it built clean. This says nothing about G2's real proof difficulty — it is scaffold-only, one throwaway lemma.
- **A same-repo `git clone --local` cross-check (attempted to close the worktree-vs-clone gap above) hit unrelated checkout errors** ("Changes to be committed: deleted: ...") for files unconnected to TLA+ or Lean; abandoned rather than debugged since it wasn't what Done-when asked for, and left as the Assume in the terminology note above.
- **macOS is entirely unverified** for both toolchains — no macOS CI job exists to have caught anything, and this session's host is Windows. This is the one real gap for G1/G2 against ADR-0013 Amendment 1's native-macOS requirement: it needs a `macos-latest` CI job before either task can claim cross-platform reproducibility, not just a Windows result.
