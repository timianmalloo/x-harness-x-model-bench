# Notice

Task NG1 builds its base from cachetools (https://github.com/tkem/cachetools) at commit
`3c082c654c2804b9354e4b62dbd2994f1aac464d`, licensed MIT, `Copyright (c) 2014-2026 Thomas Kemmer`. The engine fetches the
tree at plan time (`source.workspace_from: source`); nothing from cachetools is vendored in this repository. The upstream
licence text is in `LICENSE` beside this file.

`workspace/vendor/quotakit/` is an authored, unpublished library written for this task and licensed MIT (its own `LICENSE`).
It is not part of cachetools.
