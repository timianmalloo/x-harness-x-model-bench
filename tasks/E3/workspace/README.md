# Workspace

Empty by design. `source.workspace_from` is left at its default (`workspace`), so the engine's
`task_source()` builds the base tree as `tasks/E3/workspace/` alone, committed once (R-83): this
folder plus its one file.

Upstream `extract-moves-from-video` gives the agent nothing to start from either — its
`environment/Dockerfile` is `FROM ubuntu:24.04` / `WORKDIR /app` with no further `RUN` lines, and
`instruction.md` (`prompt.md` here) asks the agent to download a video, transcribe it, and create
`solution.txt` from scratch. There is no starter file to vendor, and nothing under
`tasks/E3/tests/` or `tasks/E3/oracle/` is reachable from this clone or its history (US-8).
