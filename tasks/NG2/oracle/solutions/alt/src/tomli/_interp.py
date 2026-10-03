"""Replace ``${NAME}`` in the string values of a parsed TOML document."""

import re

import envkit

from ._parser import loads

_PATTERN = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}")


def _convert(node, replace):
    match node:
        case str():
            return replace(node)
        case list():
            return [_convert(item, replace) for item in node]
        case dict():
            return {key: _convert(item, replace) for key, item in node.items()}
        case _:
            return node


def loads_env(text, source: envkit.MappingSource):
    """Parse ``text`` as TOML; a string value has each ``${NAME}`` replaced by ``source.fetch("NAME")``."""

    def replace(string):
        return _PATTERN.sub(lambda found: source.fetch(found.group(1), fallback=envkit.MISSING), string)

    return _convert(loads(text), replace)
