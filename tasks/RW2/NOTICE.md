# Notice

Task RW2 builds its base from schedule (https://github.com/dbader/schedule) at commit
`82a43db1b938d8fdf60103bd41f329e06c8d3651`, licensed MIT, `Copyright (c) 2013 Daniel Bader`. The engine fetches the
tree at plan time (`source.workspace_from: source`); nothing from schedule is vendored in this repository except the
reference, naive and alternative solution overlays under `oracle/solutions/`, which are derived works of the files they
replace and carry the same licence. The upstream licence text is in `LICENSE` beside this file.
