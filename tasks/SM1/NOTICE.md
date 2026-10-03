# Notice

Task SM1 builds its base from TinyDB (https://github.com/msiemens/tinydb) at commit
`18d73a15066a04c77f19ae9a8c03d582bd344c0d`, licensed MIT, `Copyright (C) 2013 Markus Siemens`. The engine fetches the
tree at plan time (`source.workspace_from: source`); nothing from TinyDB is vendored in this repository except the
solution overlays under `oracle/solutions/` (each a modified copy of `tinydb/table.py`), which carry the same licence. The
upstream licence text is in `LICENSE` beside this file.
