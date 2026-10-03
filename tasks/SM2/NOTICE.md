# Notice

Task SM2 builds its base from jmespath.py (https://github.com/jmespath/jmespath.py) at commit
`2812594e69d43098ef60f81f4efc404c071b0418`, licensed MIT, `Copyright (c) 2013 Amazon.com, Inc. or its affiliates`. The
engine fetches the tree at plan time (`source.workspace_from: source`); nothing from jmespath.py is vendored in this
repository except the solution overlays under `oracle/solutions/` (each a modified copy of `jmespath/__init__.py`), which
carry the same licence. The upstream licence text is in `LICENSE` beside this file.
