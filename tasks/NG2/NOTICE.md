# Notice

Task NG2 builds its base from tomli (https://github.com/hukkin/tomli) at commit
`5a77b12a7a9f052ce5a20c335d2825658f6aea52`, licensed MIT, `Copyright (c) 2021 Taneli Hukkinen`. The engine fetches the
tree at plan time (`source.workspace_from: source`); nothing from tomli is vendored in this repository. The upstream
licence text is in `LICENSE` beside this file.

`workspace/vendor/envkit/` is an authored, unpublished library written for this task and licensed MIT (its own `LICENSE`).
It is not part of tomli.
