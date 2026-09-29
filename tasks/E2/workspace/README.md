# Workspace

Empty by upstream design. `count-dataset-tokens`'s own `environment/Dockerfile` at
`2fd12b88aafdd04a52c298e3940bcb189f9766d6` is `FROM python:3.13-slim-bookworm` with a bare
`WORKDIR /app` and no `COPY` — the upstream task ships no starter file. The agent starts from an
empty working directory (US-8: nothing here overlays a stub, a public test or a doc; there is none
to give) and must write its own script and its own `answer.txt` (native path; upstream writes
`/app/answer.txt`, see `tasks/E2/README.md`).

This file exists only so `workspace/` is a tracked, non-empty directory (`bench validate`'s `status
ready requires workspace/` check reads `.is_dir()`); it is not part of the upstream task, and is
not one of `source.vendored_paths` in `task.yaml`.
