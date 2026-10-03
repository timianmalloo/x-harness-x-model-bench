# Notice

Task RW1 builds its base from humanfriendly (https://github.com/xolox/python-humanfriendly) at commit
`6758ac61f906cd8528682003070a57febe4ad3cf`, licensed MIT, `Copyright (c) 2021 Peter Odding`. The engine fetches the
tree at plan time (`source.workspace_from: source`); nothing from humanfriendly is vendored in this repository except
the reference, naive and alternative solution overlays under `oracle/solutions/`, which are derived works of the files
they replace and carry the same licence. The upstream licence text is in `LICENSE` beside this file.
