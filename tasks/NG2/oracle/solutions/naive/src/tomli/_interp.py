"""Replace ``${NAME}`` in the string values of a parsed TOML document."""

import re

from envkit import EnvSource

from ._parser import loads

_NAME = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}")


def _expand(value, source: EnvSource):
    if isinstance(value, str):
        return _NAME.sub(lambda match: source.get(match.group(1), ""), value)
    if isinstance(value, list):
        return [_expand(item, source) for item in value]
    if isinstance(value, dict):
        return {key: _expand(item, source) for key, item in value.items()}
    return value


def loads_env(text, source: EnvSource):
    """Parse ``text`` as TOML and replace ``${NAME}`` in every string value with ``source.get("NAME", "")``."""
    return _expand(loads(text), source)
