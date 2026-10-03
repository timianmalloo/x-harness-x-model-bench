"""Child process for the NG task tests: which dotted names does a vendored library really define?

Usage: python -S reflect.py <library directory> <name>...
A name is `lib.Member`, `lib.Cls.member` or `lib.Cls.__init__:keyword`. Prints one JSON object, name to true or false.
It imports only the vendored library it is pointed at, never agent code.
"""

import importlib
import inspect
import json
import sys


def present(name):
    head, _, keyword = name.partition(":")
    parts = head.split(".")
    try:
        obj = importlib.import_module(parts[0])
    except Exception:  # noqa: BLE001 - a library that does not import defines nothing
        return False
    for part in parts[1:]:
        if not hasattr(obj, part):
            return False
        obj = getattr(obj, part)
    if not keyword:
        return True
    parameters = inspect.signature(obj).parameters
    return keyword in parameters or any(p.kind is p.VAR_KEYWORD for p in parameters.values())


if __name__ == "__main__":
    sys.path.insert(0, sys.argv[1])
    print(json.dumps({name: present(name) for name in sys.argv[2:]}))
