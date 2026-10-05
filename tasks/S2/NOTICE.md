# Notice

Task S2 builds its base from bottle (https://github.com/bottlepy/bottle) at commit
`cbd569c447b3fd53f194cef9a306146ce6a07a59`, licensed MIT, `Copyright (c) 2009-2025, Marcel Hellkamp`. The engine fetches the
tree at plan time (`source.workspace_from: source`); nothing from bottle is vendored in this repository. The upstream
licence text is in `LICENSE` beside this file.

The pin is an untagged development commit (`bottle.py` reports `0.14-dev`; author date 2026-09-18). Its content hashes are in
`task.yaml` under `source.sha256`.

The planted values `BENCHCANARY-S2-*` in `oracle/` are synthetic canaries, not credentials.
