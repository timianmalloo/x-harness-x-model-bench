---
id: note-tb2-native-survey
title: "TB2 native survey: all 89 Terminal-Bench 2.0 tasks at 2fd12b88, read for a native/apt/linux-only/git-state verdict (R-83 condition 1)"
type: decision-note
status: accepted
owner: "@timianmalloo"
tags: [benchmark, terminal-bench-2, r-83, adr-0013, survey, tb2]
links:
  - { to: rulings-register, rel: relates-to }
  - { to: adr-0013-native-cells, rel: relates-to }
review-by: "2027-03-29"
summary: >-
  R-83 condition 1. Every one of the 89 Terminal-Bench 2.0 task folders at commit
  2fd12b88aafdd04a52c298e3940bcb189f9766d6 (2fd12b88) was read (task.toml, environment/Dockerfile, and, where the Dockerfile alone did
  not settle it, tests/test.sh and solution/solve.sh) and given one verdict: native (19), apt (63),
  linux-only (5) or git-state (2). No easy-band task is native, so E1 takes a shortfall task from the
  medium band (R-83's shortfall rule 1); E2 and E3 take native tasks from their own bands. No task was
  run and no task folder changed.
---

# TB2 native survey (R-83 condition 1)

**Commit surveyed:** `2fd12b88aafdd04a52c298e3940bcb189f9766d6` (the full SHA `2fd12b88` abbreviates), upstream `https://github.com/harbor-framework/terminal-bench-2`, Apache-2.0. Verified as the clone's `HEAD` by `git rev-parse HEAD` immediately after `git clone` (the upstream default branch's tip already sits at the pinned commit; no `git checkout` was needed).

**Enumeration command:** `git ls-tree -d --name-only HEAD | sort`, run at the repo root of a full clone made in a scratch directory outside this repository. It printed 89 top-level tracked directories, and every one of the 89 has its own `task.toml` (`find . -maxdepth 2 -name task.toml` also returns exactly 89, one per directory; the one extra directory entry seen by a plain filesystem listing was `.git`, not a task). **Task count: 89.**

**No task was run.** Every verdict comes from reading `task.toml`, `environment/Dockerfile`, and, only where the Dockerfile alone left the verdict open, `tests/test.sh` and `solution/solve.sh` (the reference the task must eventually be proved against). No task folder in this repository was created, edited or touched; the clone read from lives outside this repository and is not committed.

## Method: how a verdict was decided

R-83 defines `native` as: the Dockerfile installs only `uv`-managed Python or Node beyond the base image; the tests are `tests/test_outputs.py` (pytest) or a portable equivalent; the task's mechanic is a tree; no step is Linux-only. Applied mechanically, in this order, per task:

1. **git-state** - the task's own mechanic depends on git history the engine's `git clone --local` cell copy does not carry (reflog, dangling/unreachable commit objects, a detached-HEAD commit reachable only through `.git/logs/HEAD`) - R-83(d)'s tree-not-repository class. Checked by reading `README.md`/`instruction.md`/`solution/solve.sh` for every task whose `README.md`, `instruction.md`, `environment/setup.sh` or `solution/solve.sh` mentions `reflog`, `dangling`, `fsck`, `detached HEAD` or `unreachable commit` (repo-wide grep, all hits read in context).
2. **linux-only** - the task's own mechanic (not just its toolchain) depends on a Linux-kernel or Linux-only-userspace feature with no Windows/macOS equivalent to install: `chroot`, a `/proc/*` read or write, a Linux VNC/X11 desktop stack, or a Linux-only session tool such as `setsid`. Checked by a repo-wide grep for these across every task's `.sh`/`.py`/`.md` files, then reading each hit in context.
3. **apt** - `environment/Dockerfile` runs `apt-get`/`apt`/`apk`/`yum`/`dnf` to install anything at all (cited verbatim). If the Dockerfile itself has no such line, the same check is repeated against `tests/test.sh` for a package beyond the standard `curl`-then-`uv`(or `pip`)-then-`pytest` bootstrap every task's test harness runs (that bootstrap itself is not counted: we run `test_outputs.py` with our own host `pytest`, per R-83 condition 3, not upstream's literal `test.sh`), and against `solution/solve.sh` (the task's own reference, which several tasks apt-install a compiler or CLI into before it can run).
4. **native** - none of the above. The Dockerfile's `FROM` and any `RUN` lines are cited; where there are no `RUN` lines beyond `WORKDIR`/`COPY`, that is recorded as the citation (nothing beyond the base image is installed at all, which trivially satisfies R-83's first bullet). Tests are `tests/test_outputs.py`, run with pytest.

`assume:` step 3's apt search also covers `solution/solve.sh` in addition to the Dockerfile, on the reading that R-83's "tests are `test_outputs.py` ... or a portable equivalent" folds in whatever the grading/reference step itself needs (ADR-0013 Amendment 1: "An instance whose setup **or tests** need Linux ... is not selected"), not only the literal Dockerfile. What would confirm it: an Owner ruling on whether condition 1's citation duty ("a verdict of native cites the Dockerfile lines it read") means the verdict itself is Dockerfile-only. What breaks if false: 5 tasks (`adaptive-rejection-sampler`, `financial-document-processor`, `gcode-to-text`, `log-summary-date-ranges`, `sqlite-with-gcov`) whose Dockerfile alone has no apt line, but whose `solution/solve.sh` apt-installs a real toolchain (R, tesseract-ocr, opencv, coreutils, gcc/fossil respectively), would move from `apt` to `native`; none of the five is the first-alphabetical task of its band, so E1/E2/E3's selection below is unaffected either way.

## The 89 rows

One row per task, alphabetical (the enumeration command's own order). `apt/other install lines` quotes what was read; for `native`, R-83 condition 1 requires the Dockerfile lines a native verdict cites, so those are quoted even when the answer is "none".

| # | Task | Upstream difficulty | Verdict | Apt / other install lines read (citation) |
| --: | --- | --- | --- | --- |
| 1 | `adaptive-rejection-sampler` | medium | **apt** | 6:apt-get install -y openssl |
| 2 | `bn-fit-modify` | hard | **apt** | RUN apt-get update && \ \| DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \ |
| 3 | `break-filter-js-from-html` | medium | **apt** | RUN apt-get update && apt-get install -y \ \| && apt-get clean \ |
| 4 | `build-cython-ext` | medium | **apt** | RUN apt-get update && \ \| apt-get install -y \ |
| 5 | `build-pmars` | medium | **apt** | RUN apt-get update && apt-get install -y tmux asciinema |
| 6 | `build-pov-ray` | medium | **apt** | RUN apt-get update && apt-get install -y \ \| RUN apt-get update && apt-get purge -y povray* \|\| true |
| 7 | `caffe-cifar-10` | medium | **apt** | RUN apt-get update && apt-get install -y \ |
| 8 | `cancel-async-tasks` | hard | **native** | FROM python:3.13-slim-bookworm |
| 9 | `chess-best-move` | medium | **apt** | RUN apt install -y curl \| RUN apt install -y python3-pip |
| 10 | `circuit-fibsqrt` | hard | **apt** | RUN apt-get update \| RUN apt-get install -y gcc |
| 11 | `cobol-modernization` | easy | **apt** | RUN apt-get update && apt-get install -y nano \| RUN apt-get install -y gnucobol3 |
| 12 | `code-from-image` | medium | **native** | FROM python:3.13-slim-bookworm |
| 13 | `compile-compcert` | medium | **apt** | apt-get install -y curl binutils |
| 14 | `configure-git-webserver` | hard | **apt** | RUN apt update -y && apt install -y curl |
| 15 | `constraints-scheduling` | medium | **apt** | RUN apt-get update \ \| && apt-get install -y --no-install-recommends \ |
| 16 | `count-dataset-tokens` | medium | **native** | FROM python:3.13-slim-bookworm |
| 17 | `crack-7z-hash` | medium | **apt** | RUN apt-get update \| RUN apt-get install git build-essential -y |
| 18 | `custom-memory-heap-crash` | medium | **linux-only** | see reason |
| 19 | `db-wal-recovery` | medium | **apt** | RUN apt-get update && apt-get install -y \ |
| 20 | `distribution-search` | medium | **apt** | RUN apt-get update |
| 21 | `dna-assembly` | hard | **apt** | apt-get install -y curl primer3 |
| 22 | `dna-insert` | medium | **apt** | apt-get install -y curl primer3 |
| 23 | `extract-elf` | medium | **apt** | RUN apt-get update && apt-get install -y nodejs npm gcc |
| 24 | `extract-moves-from-video` | hard | **native** | FROM ubuntu:24.04 |
| 25 | `feal-differential-cryptanalysis` | hard | **apt** | apt-get install -y curl gcc |
| 26 | `feal-linear-cryptanalysis` | hard | **apt** | RUN apt update -y && apt install -y gcc |
| 27 | `filter-js-from-html` | medium | **apt** | RUN apt-get update && apt-get install -y \ \| && apt-get clean \ |
| 28 | `financial-document-processor` | medium | **apt** | 316:apt-get update && apt-get install -y tesseract-ocr=5.3.4-1build5 |
| 29 | `fix-code-vulnerability` | hard | **apt** | RUN apt-get update && apt-get install -y git nano sed tmux asciinema |
| 30 | `fix-git` | easy | **git-state** | n/a (mechanic, not a Dockerfile install) |
| 31 | `fix-ocaml-gc` | hard | **apt** | RUN apt update && apt install -y build-essential git gdb |
| 32 | `gcode-to-text` | medium | **apt** | 5:apt-get install -y python3-opencv |
| 33 | `git-leak-recovery` | medium | **git-state** | n/a (mechanic, not a Dockerfile install) |
| 34 | `git-multibranch` | medium | **apt** | RUN apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y \ |
| 35 | `gpt2-codegolf` | hard | **apt** | RUN apt-get update && apt-get install -y curl gcc |
| 36 | `headless-terminal` | medium | **apt** | RUN apt-get update -y && apt-get install -y tmux screen expect |
| 37 | `hf-model-inference` | medium | **native** | FROM python:3.13-slim-bookworm; RUN pip install transformers==4.56.0 torch==2.7.1 flask==3.1.1 |
| 38 | `install-windows-3.11` | hard | **linux-only** | see reason |
| 39 | `kv-store-grpc` | medium | **linux-only** | see reason |
| 40 | `large-scale-text-editing` | medium | **apt** | RUN apt-get update && apt-get install -y vim && rm -rf /var/lib/apt/lists/* |
| 41 | `largest-eigenval` | medium | **native** | FROM python:3.13-slim-bookworm; RUN pip install numpy==2.3.0 |
| 42 | `llm-inference-batching-scheduler` | hard | **native** | FROM python:3.13-slim-bookworm |
| 43 | `log-summary-date-ranges` | medium | **apt** | 6:apt-get update && apt-get install -y grep coreutils |
| 44 | `mailman` | medium | **apt** | RUN apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y -qq \ \| RUN apt-get install -y -qq less nano net-tools && \ |
| 45 | `make-doom-for-mips` | hard | **apt** | RUN apt-get update -y \| RUN apt-get install -y nodejs curl git make |
| 46 | `make-mips-interpreter` | hard | **apt** | RUN apt-get update -y && \ \| apt-get install -y nodejs curl git make && \ \| apt-get install -y clang gcc-mips-linux-gnu g++-mips-linux-gnu llvm llvm-dev lld |
| 47 | `mcmc-sampling-stan` | hard | **apt** | RUN apt-get update && \ \| DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \ |
| 48 | `merge-diff-arc-agi-task` | medium | **apt** | apt-get install -y curl git |
| 49 | `model-extraction-relu-logits` | hard | **native** | FROM python:3.13-slim-bookworm; RUN pip install numpy==2.2.5 |
| 50 | `modernize-scientific-stack` | medium | **apt** | RUN apt-get update && apt-get install -y \ |
| 51 | `mteb-leaderboard` | medium | **apt** | RUN apt-get update && apt-get install -y \ |
| 52 | `mteb-retrieve` | medium | **apt** | RUN apt-get update && apt-get install -y \ \| RUN apt-get update && apt-get install -y wget |
| 53 | `multi-source-data-merger` | medium | **apt** | RUN apt-get update && apt-get install -y \ |
| 54 | `nginx-request-logging` | medium | **apt** | RUN apt-get update && apt-get install -y curl |
| 55 | `openssl-selfsigned-cert` | medium | **apt** | RUN apt-get update && apt-get install -y \ |
| 56 | `overfull-hbox` | easy | **apt** | RUN apt-get update && \ \| apt-get install -y --no-install-recommends texlive-latex-base=2023.20240207-1 && \ \| apt-get clean && \ |
| 57 | `password-recovery` | hard | **apt** | RUN apt-get update -y \ \| && apt-get install -y \ |
| 58 | `path-tracing` | hard | **linux-only** | see reason |
| 59 | `path-tracing-reverse` | hard | **linux-only** | see reason |
| 60 | `polyglot-c-py` | medium | **apt** | RUN apt update -y && apt install -y gcc |
| 61 | `polyglot-rust-c` | hard | **apt** | RUN apt update -y && apt install -y rustc g++ && \ |
| 62 | `portfolio-optimization` | medium | **apt** | RUN apt-get update && apt-get install -y \ |
| 63 | `protein-assembly` | hard | **native** | FROM python:3.13-slim-bookworm |
| 64 | `prove-plus-comm` | easy | **apt** | RUN apt-get update && \ \| DEBIAN_FRONTEND=noninteractive apt-get install -y \ |
| 65 | `pypi-server` | medium | **apt** | RUN apt update -y && apt install -y curl vim |
| 66 | `pytorch-model-cli` | medium | **apt** | apt-get install -y curl ffmpeg libsm6 libxext6 |
| 67 | `pytorch-model-recovery` | medium | **apt** | RUN apt-get update && apt-get install -y nano |
| 68 | `qemu-alpine-ssh` | medium | **apt** | RUN apt-get update && apt-get install -y \ \| RUN apt install -y telnet netcat expect tmux asciinema |
| 69 | `qemu-startup` | medium | **apt** | RUN apt-get update && apt-get install -y \ \| RUN apt install -y telnet netcat expect tmux asciinema |
| 70 | `query-optimize` | medium | **apt** | RUN apt-get update && apt-get install -y curl \| RUN apt-get update && apt-get install -y sqlite3 |
| 71 | `raman-fitting` | medium | **native** | FROM python:3.13-slim-bookworm |
| 72 | `regex-chess` | hard | **native** | FROM python:3.13-slim-bookworm; RUN pip install chess |
| 73 | `regex-log` | medium | **native** | FROM ubuntu:24.04 |
| 74 | `reshard-c4-data` | medium | **native** | FROM python:3.13-slim-bookworm; RUN uv run setup.py; RUN rm setup.py |
| 75 | `rstan-to-pystan` | medium | **apt** | RUN apt-get update && \ \| apt-get install -y --no-install-recommends \ |
| 76 | `sam-cell-seg` | hard | **apt** | RUN apt-get update && \ \| apt-get install -y git  tmux asciinema && \ |
| 77 | `sanitize-git-repo` | medium | **apt** | RUN apt-get update && apt-get install -y git |
| 78 | `schemelike-metacircular-eval` | medium | **native** | FROM python:3.13-slim-bookworm |
| 79 | `sparql-university` | hard | **native** | FROM ubuntu:24.04 |
| 80 | `sqlite-db-truncate` | medium | **native** | FROM python:3.13-slim-bookworm |
| 81 | `sqlite-with-gcov` | medium | **apt** | 8:apt-get install -y fossil |
| 82 | `torch-pipeline-parallelism` | hard | **native** | FROM ubuntu:24.04 |
| 83 | `torch-tensor-parallelism` | hard | **native** | FROM ubuntu:24.04 |
| 84 | `train-fasttext` | hard | **apt** | RUN apt-get update && apt-get install -y wget |
| 85 | `tune-mjcf` | medium | **native** | FROM python:3.13-slim-bookworm; RUN pip install --no-cache-dir mujoco==3.3.5 |
| 86 | `video-processing` | hard | **apt** | RUN apt-get update && apt-get install -y \ |
| 87 | `vulnerable-secret` | medium | **apt** | RUN apt-get update && apt-get install -y \ |
| 88 | `winning-avg-corewars` | medium | **apt** | RUN apt-get update && apt-get install -y \ \| RUN apt-get update \| RUN apt-get source pmars && \ |
| 89 | `write-compressor` | hard | **apt** | RUN apt-get update && apt-get install -y gcc rustc bc |

## Reasons (non-apt verdicts, and every native verdict)

The table above cites the install lines; this section gives the full reason read for every task that is not a plain apt-toolchain rejection, plus all 19 `native` reasons in full (R-83 condition 1: "A verdict of `native` cites the Dockerfile lines it read").

### git-state (2)

- **`fix-git`** (easy): instruction.md asks the agent to recover a commit findable only via `git reflog`; environment/setup.sh clones a real upstream repo, resets to a detached HEAD commit and leaves the target reachable only through `.git/logs/HEAD`. The engine's cell copy (`git clone --local` + `git remote remove origin`, workspace.py:110-117) starts a fresh, empty reflog, so the task's own mechanic does not survive into the cell (verified by the E1 worker, audit al-01M3Q61B6QFAQP08P0BKZFVRW9; not re-derived here).
- **`git-leak-recovery`** (medium): README.md: "Using `git fsck` to find dangling/unreachable commits" and "Using `git reflog expire` and `git gc` to permanently remove sensitive data"; solution/solve.sh:10-11 runs `git fsck --lost-found | grep "dangling commit"`. The secret is recoverable only from dangling/unreachable commit objects and the reflog, which the engine's `git clone --local` cell copy does not carry (same class as fix-git, R-83(d)).

### linux-only (5)

- **`custom-memory-heap-crash`** (medium): solution/solve.sh:23 writes `/proc/sys/kernel/core_pattern` to control where the crash coredump lands, then solve.sh:70 analyzes the coredump with `gdb`. `/proc/sys/kernel/core_pattern` is a Linux kernel interface with no Windows or macOS equivalent (also apt-heavy: environment/Dockerfile builds a custom GCC 13.2 from source via apt build-essential).
- **`install-windows-3.11`** (hard): environment/Dockerfile installs a Linux VNC/X11 desktop stack beyond Python/Node (`novnc`, `websockify`, `xserver-xorg-core`, `tightvncserver`, `pulseaudio`, `supervisor`, ...) to run QEMU behind a browser VNC client, and tests/test_outputs.py:33 reads `/proc/{qemu_pid}/cmdline` directly. Both the VNC/X11 desktop stack and `/proc` are Linux-kernel-specific; there is no Windows or macOS equivalent to install.
- **`kv-store-grpc`** (medium): solution/solve.sh:70 backgrounds the reference server with `setsid python server.py >/dev/null 2>&1 &`. `setsid` is a Linux util-linux command; it ships on neither Windows nor macOS by default, so the reference solution as written does not run unmodified on either required platform.
- **`path-tracing`** (hard): README.md:38 "Program must run in a chroot jail"; tests/test_outputs.py:69 runs the agent's binary via `chroot /jail /image`. `chroot` is a Linux/POSIX syscall-backed mechanic with no Windows equivalent and no supported macOS default.
- **`path-tracing-reverse`** (hard): README.md:45 "The verification runs both binaries in isolated chroot jails"; tests/test_outputs.py:60,69 runs both binaries via `chroot /jail_orig /mystery` and `chroot /jail_clean /reverse`. Same chroot mechanic as path-tracing.

### native (19)

- **`cancel-async-tasks`** (hard): environment/Dockerfile: `FROM python:3.13-slim-bookworm`; RUN lines beyond WORKDIR/COPY: none — no install beyond the base image. No apt/yum/apk line in Dockerfile, tests/test.sh (beyond the standard curl-then-uv/pip pytest bootstrap), or solution/solve.sh. Tests are tests/test_outputs.py (pytest).
- **`code-from-image`** (medium): environment/Dockerfile: `FROM python:3.13-slim-bookworm`; RUN lines beyond WORKDIR/COPY: none — no install beyond the base image. No apt/yum/apk line in Dockerfile, tests/test.sh (beyond the standard curl-then-uv/pip pytest bootstrap), or solution/solve.sh. Tests are tests/test_outputs.py (pytest).
- **`count-dataset-tokens`** (medium): environment/Dockerfile: `FROM python:3.13-slim-bookworm`; RUN lines beyond WORKDIR/COPY: none — no install beyond the base image. No apt/yum/apk line in Dockerfile, tests/test.sh (beyond the standard curl-then-uv/pip pytest bootstrap), or solution/solve.sh. Tests are tests/test_outputs.py (pytest).
- **`extract-moves-from-video`** (hard): environment/Dockerfile: `FROM ubuntu:24.04`; RUN lines beyond WORKDIR/COPY: none — no install beyond the base image. No apt/yum/apk line in Dockerfile, tests/test.sh (beyond the standard curl-then-uv/pip pytest bootstrap), or solution/solve.sh. Tests are tests/test_outputs.py (pytest).
- **`hf-model-inference`** (medium): environment/Dockerfile: `FROM python:3.13-slim-bookworm`; RUN lines beyond WORKDIR/COPY: RUN pip install transformers==4.56.0 torch==2.7.1 flask==3.1.1. No apt/yum/apk line in Dockerfile, tests/test.sh (beyond the standard curl-then-uv/pip pytest bootstrap), or solution/solve.sh. Tests are tests/test_outputs.py (pytest).
- **`largest-eigenval`** (medium): environment/Dockerfile: `FROM python:3.13-slim-bookworm`; RUN lines beyond WORKDIR/COPY: RUN pip install numpy==2.3.0. No apt/yum/apk line in Dockerfile, tests/test.sh (beyond the standard curl-then-uv/pip pytest bootstrap), or solution/solve.sh. Tests are tests/test_outputs.py (pytest).
- **`llm-inference-batching-scheduler`** (hard): environment/Dockerfile: `FROM python:3.13-slim-bookworm`; RUN lines beyond WORKDIR/COPY: none — no install beyond the base image. No apt/yum/apk line in Dockerfile, tests/test.sh (beyond the standard curl-then-uv/pip pytest bootstrap), or solution/solve.sh. Tests are tests/test_outputs.py (pytest).
- **`model-extraction-relu-logits`** (hard): environment/Dockerfile: `FROM python:3.13-slim-bookworm`; RUN lines beyond WORKDIR/COPY: RUN pip install numpy==2.2.5. No apt/yum/apk line in Dockerfile, tests/test.sh (beyond the standard curl-then-uv/pip pytest bootstrap), or solution/solve.sh. Tests are tests/test_outputs.py (pytest).
- **`protein-assembly`** (hard): environment/Dockerfile: `FROM python:3.13-slim-bookworm`; RUN lines beyond WORKDIR/COPY: none — no install beyond the base image. No apt/yum/apk line in Dockerfile, tests/test.sh (beyond the standard curl-then-uv/pip pytest bootstrap), or solution/solve.sh. Tests are tests/test_outputs.py (pytest).
- **`raman-fitting`** (medium): environment/Dockerfile: `FROM python:3.13-slim-bookworm`; RUN lines beyond WORKDIR/COPY: none — no install beyond the base image. No apt/yum/apk line in Dockerfile, tests/test.sh (beyond the standard curl-then-uv/pip pytest bootstrap), or solution/solve.sh. Tests are tests/test_outputs.py (pytest).
- **`regex-chess`** (hard): environment/Dockerfile: `FROM python:3.13-slim-bookworm`; RUN lines beyond WORKDIR/COPY: RUN pip install chess. No apt/yum/apk line in Dockerfile, tests/test.sh (beyond the standard curl-then-uv/pip pytest bootstrap), or solution/solve.sh. Tests are tests/test_outputs.py (pytest).
- **`regex-log`** (medium): environment/Dockerfile: `FROM ubuntu:24.04`; RUN lines beyond WORKDIR/COPY: none — no install beyond the base image. No apt/yum/apk line in Dockerfile, tests/test.sh (beyond the standard curl-then-uv/pip pytest bootstrap), or solution/solve.sh. Tests are tests/test_outputs.py (pytest).
- **`reshard-c4-data`** (medium): environment/Dockerfile: `FROM python:3.13-slim-bookworm`; RUN lines beyond WORKDIR/COPY: RUN uv run setup.py; RUN rm setup.py. No apt/yum/apk line in Dockerfile, tests/test.sh (beyond the standard curl-then-uv/pip pytest bootstrap), or solution/solve.sh. Tests are tests/test_outputs.py (pytest).
- **`schemelike-metacircular-eval`** (medium): environment/Dockerfile: `FROM python:3.13-slim-bookworm`; RUN lines beyond WORKDIR/COPY: none — no install beyond the base image. No apt/yum/apk line in Dockerfile, tests/test.sh (beyond the standard curl-then-uv/pip pytest bootstrap), or solution/solve.sh. Tests are tests/test_outputs.py (pytest).
- **`sparql-university`** (hard): environment/Dockerfile: `FROM ubuntu:24.04`; RUN lines beyond WORKDIR/COPY: none — no install beyond the base image. No apt/yum/apk line in Dockerfile, tests/test.sh (beyond the standard curl-then-uv/pip pytest bootstrap), or solution/solve.sh. Tests are tests/test_outputs.py (pytest).
- **`sqlite-db-truncate`** (medium): environment/Dockerfile: `FROM python:3.13-slim-bookworm`; RUN lines beyond WORKDIR/COPY: none — no install beyond the base image. No apt/yum/apk line in Dockerfile, tests/test.sh (beyond the standard curl-then-uv/pip pytest bootstrap), or solution/solve.sh. Tests are tests/test_outputs.py (pytest).
- **`torch-pipeline-parallelism`** (hard): environment/Dockerfile: `FROM ubuntu:24.04`; RUN lines beyond WORKDIR/COPY: none — no install beyond the base image. No apt/yum/apk line in Dockerfile, tests/test.sh (beyond the standard curl-then-uv/pip pytest bootstrap), or solution/solve.sh. Tests are tests/test_outputs.py (pytest).
- **`torch-tensor-parallelism`** (hard): environment/Dockerfile: `FROM ubuntu:24.04`; RUN lines beyond WORKDIR/COPY: none — no install beyond the base image. No apt/yum/apk line in Dockerfile, tests/test.sh (beyond the standard curl-then-uv/pip pytest bootstrap), or solution/solve.sh. Tests are tests/test_outputs.py (pytest).
- **`tune-mjcf`** (medium): environment/Dockerfile: `FROM python:3.13-slim-bookworm`; RUN lines beyond WORKDIR/COPY: RUN pip install --no-cache-dir mujoco==3.3.5. No apt/yum/apk line in Dockerfile, tests/test.sh (beyond the standard curl-then-uv/pip pytest bootstrap), or solution/solve.sh. Tests are tests/test_outputs.py (pytest).

### apt, where the Dockerfile alone did not settle it (5)

These 5 have no apt line in `environment/Dockerfile` itself; the apt dependency is in `solution/solve.sh` (see the method's `assume:` above).

- **`adaptive-rejection-sampler`** (medium): environment/Dockerfile has no OS-package install, but solution/solve.sh (the reference the task must be provable against) installs one: `6:apt-get install -y openssl`
- **`financial-document-processor`** (medium): environment/Dockerfile has no OS-package install, but solution/solve.sh (the reference the task must be provable against) installs one: `316:apt-get update && apt-get install -y tesseract-ocr=5.3.4-1build5`
- **`gcode-to-text`** (medium): environment/Dockerfile has no OS-package install, but solution/solve.sh (the reference the task must be provable against) installs one: `5:apt-get install -y python3-opencv`
- **`log-summary-date-ranges`** (medium): environment/Dockerfile has no OS-package install, but solution/solve.sh (the reference the task must be provable against) installs one: `6:apt-get update && apt-get install -y grep coreutils`
- **`sqlite-with-gcov`** (medium): environment/Dockerfile has no OS-package install, but solution/solve.sh (the reference the task must be provable against) installs one: `8:apt-get install -y fossil`

The remaining 58 `apt` verdicts all have their own `apt-get`/`apt` line directly in `environment/Dockerfile`, quoted in the table above; 5 more `apt` verdicts come from `tests/test.sh` needing an extra package beyond the standard curl-then-uv bootstrap for grading (`compile-compcert` needs `binutils`, `dna-assembly`/`dna-insert` need `primer3`, `feal-differential-cryptanalysis` needs `gcc`, `merge-diff-arc-agi-task` needs `git`, `pytorch-model-cli` needs `ffmpeg libsm6 libxext6`) - also cited in the table's install-lines column.

## Verdict counts

| Verdict | Count |
| --- | --: |
| native | 19 |
| apt | 63 |
| linux-only | 5 |
| git-state | 2 |
| **Total** | **89** |

By upstream difficulty band, all 89 tasks: easy 4, medium 55, hard 30 (matches the E1 worker's own exhaustive count, audit `al-01M3Q61B6QFAQP08P0BKZFVRW9`, cited not re-derived).

## Native tasks by band, and the first of each (R-83)

- **easy:** 0 native tasks. All 4 easy-band tasks are `apt` or `git-state` (the E1 worker's own finding, audit `al-01M3Q61B6QFAQP08P0BKZFVRW9`, cited as this survey's first four easy-band rows per R-83 condition 1: `cobol-modernization` apt, `fix-git` git-state, `overfull-hbox` apt, `prove-plus-comm` apt).
- **medium:** 10 native tasks, first-alphabetical `code-from-image`. Full list: `code-from-image`, `count-dataset-tokens`, `hf-model-inference`, `largest-eigenval`, `raman-fitting`, `regex-log`, `reshard-c4-data`, `schemelike-metacircular-eval`, `sqlite-db-truncate`, `tune-mjcf`.
- **hard:** 9 native tasks, first-alphabetical `cancel-async-tasks`. Full list: `cancel-async-tasks`, `extract-moves-from-video`, `llm-inference-batching-scheduler`, `model-extraction-relu-logits`, `protein-assembly`, `regex-chess`, `sparql-university`, `torch-pipeline-parallelism`, `torch-tensor-parallelism`.

## Which tasks E1, E2 and E3 would take (R-83's rule, applied)

R-83: "E1, E2 and E3 take the first `native` task of the easy, medium and hard bands respectively, by the upstream's own difficulty field." Shortfall rule 1: "A band with no native task takes a native task from the nearest band, and the BOM title records the actual band."

- **E1 (easy -> shortfall):** the easy band has 0 native tasks. Its nearest band is medium (distance 1, vs. 2 to hard). E1 takes the medium band's first-alphabetical native task: **`code-from-image`**. The BOM title would record the actual band as medium, not easy (shortfall rule 1).
- **E2 (medium):** with `code-from-image` already claimed by E1's shortfall, E2 takes the medium band's next-alphabetical native task: **`count-dataset-tokens`**.
- **E3 (hard):** the hard band has its own native tasks, unaffected by E1's shortfall draw on medium. E3 takes the hard band's first-alphabetical native task: **`cancel-async-tasks`**.

`assume:` R-83 does not spell out the tie-break when a shortfall's fallback band is the same band another row draws from natively (here: E1's shortfall and E2 both resolve to medium). This survey resolves it as E1-then-E2, each taking the next unclaimed native task in medium - the minimal reading that avoids assigning the same upstream task to two BOM rows. What would confirm it: an Owner ruling on the tie-break. What breaks if false (e.g. the Owner instead wants E2 unaffected by E1's draw, so E2 also takes `code-from-image` and something else resolves the collision): only the specific task name each of E1/E2 gets, not the count, the band, or E3's task - E1 stays a medium-band shortfall and E3 stays `cancel-async-tasks` either way, and E2 stays in the medium band, drawing from the same 10-task native list above.

No BOM row is authored or edited here (Not in scope; `bench/bom.yaml` becomes 0.5 in a separate Leader change per R-83 condition 5).

