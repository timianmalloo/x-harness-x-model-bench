# Workspace

The run workspace is `source.repo` at `source.commit` in `task.yaml` — a full, unmodified
working copy of the Django repository (BSD-3-Clause), checked out at
`e8fcdaad5c428878d0a5d6ba820d957013f75595`:

```
git clone https://github.com/django/django.git ws
cd ws
git checkout e8fcdaad5c428878d0a5d6ba820d957013f75595
git remote remove origin
```

This is the whole given codebase (`django/`, `tests/`, `docs/`, `setup.py`, ...) as SWE-bench
Verified gives it: the entire pinned repository, not an excerpt. It is not vendored into this
folder — at ~49 MB and ~6,400 files (measured with `git clean -xdf` then `du -sh .` /
`find . -type f | wc -l` on this Windows host, `.git` excluded) it is materialized by cloning the
pin above, the same way ADR-0013 Amendment 1 has every public task get "a native working copy" and
"the engine keeps one bench-owned local clone per task version, at the base commit, with no
remote" (ADR-0013 Decision 1). No file here overlays the clone: nothing in this task needs a stub,
a public test or a doc beyond what the repository itself already contains at that commit.

Two of Django's own directories are named `bin` (`django/bin/`, `django/contrib/admin/bin/`, two
small standalone scripts unrelated to this issue) and would trip this repo's own
`GENERATED_DIR_NAMES` vendoring check (`bin`, built for .NET's `bin/`/`obj/`) if ever vendored
here; since nothing is vendored, that collision does not arise.

Nothing under `tasks/E4/tests/` or `tasks/E4/oracle/` is reachable from this clone or its history.
