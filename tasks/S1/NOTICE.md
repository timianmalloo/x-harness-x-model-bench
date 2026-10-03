# Notice

Task S1 builds its base from microdot (https://github.com/miguelgrinberg/microdot) at commit
`7742db9ff9f49635de3387145fafe56bf2377a97`, licensed MIT, `Copyright (c) 2019 Miguel Grinberg`. The engine fetches the
tree at plan time (`source.workspace_from: source`); nothing from microdot is vendored in this repository. The upstream
licence text is in `LICENSE` beside this file.

The planted values `BENCHCANARY-S1-*` in `oracle/` are synthetic canaries, not credentials.
