"""MappingSource: look up named values."""

MISSING = object()


class UnknownName(Exception):
    """Raised by MappingSource.fetch() for a name the source does not hold, when no fallback is given."""


class MappingSource:
    """Named string values held in a mapping. The mapping is copied when the source is built."""

    def __init__(self, mapping):
        self._mapping = dict(mapping)

    def fetch(self, name, *, fallback=MISSING):
        """Return the value of ``name``. For an unknown name return ``fallback`` if one is given, else raise UnknownName."""
        if name in self._mapping:
            return self._mapping[name]
        if fallback is MISSING:
            raise UnknownName(name)
        return fallback
