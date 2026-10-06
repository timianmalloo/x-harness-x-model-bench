# Notice

Task RS2 builds its base from structlog (https://github.com/hynek/structlog) at commit
`91f44ae9031c80ad9c6045172f182803543ba6ba`, licensed `MIT OR Apache-2.0`, `Copyright (c) 2013 Hynek Schlawack and the structlog
contributors`. The engine fetches the tree at plan time (`source.workspace_from: source`); nothing from structlog is vendored in
this repository except `workspace/docs/collector.md` (authored here) and the solution overlays under `oracle/solutions/` (each a
new `src/structlog/shipper.py`, authored here). The upstream licence texts are in `LICENSE` (MIT) and `LICENSE-APACHE` beside
this file.
