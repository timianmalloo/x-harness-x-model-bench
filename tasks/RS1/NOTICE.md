# Notice

Task RS1 builds its base from the Prometheus Python client (https://github.com/prometheus/client_python) at commit
`9cd073cb4dc6ee617eadf02dcdec94e0225eff0a`, licensed Apache-2.0, `Copyright 2015 The Prometheus Authors`. The engine
fetches the tree at plan time (`source.workspace_from: source`); nothing from the client is vendored in this repository
except `workspace/docs/ledger-service.md` (authored here) and the solution overlays under `oracle/solutions/` (each a new
`prometheus_client/ledger.py`, authored here). The upstream licence text is in `LICENSE` beside this file.
