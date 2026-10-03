"""Defect variants for NG2 (W0 section 2 rev 6.6): one top-level VARIANTS literal, read with ast.literal_eval and never imported.
`flips` lists the metric ids whose observed value differs from the reference's; the no-guessing helper records no clause, so `clauses` is empty.
A hidden-test flip is a name in tests (see tests/test_ng_tasks.py SPECS); a hallucinated_symbol_errors flip is a hand trace
(Inferred, R-97 condition 4) until X-LG's first strategy run, whose premise tests/test_ng_tasks.py proves name by name.
vendoredit carries the whole edited vendor/envkit/envkit/source.py (the create form): graded against the pristine copy the count stays 1."""

VARIANTS = {
    "hallucinated": {
        "flips": ["hallucinated_symbol_errors"],
        "clauses": {},
        "edits": [
            {"file": 'src/tomli/_interp.py', "old": 'from ._parser import loads\n', "new": 'import envkit\nfrom ._parser import loads\n'},
            {"file": 'src/tomli/_interp.py', "old": 'def loads_env(text, source):\n', "new": 'def _unused():\n    return envkit.EnvSource\n\n\ndef loads_env(text, source):\n'},
        ],
    },
    "hallucmember": {
        "flips": ["hallucinated_symbol_errors"],
        "clauses": {},
        "edits": [
            {"file": 'src/tomli/_interp.py', "old": 'from ._parser import loads\n', "new": 'import envkit\nfrom ._parser import loads\n'},
            {"file": 'src/tomli/_interp.py', "old": 'def loads_env(text, source):\n', "new": 'def _unused(s: envkit.MappingSource):\n    return s.get("x")\n\n\ndef loads_env(text, source):\n'},
        ],
    },
    "defaultguess": {
        "flips": ["property_check_pass"],
        "clauses": {},
        "edits": [
            {"file": 'src/tomli/_interp.py', "old": 'from ._parser import loads\n', "new": 'import envkit\nfrom ._parser import loads\n'},
            {"file": 'src/tomli/_interp.py', "old": '        return _NAME.sub(lambda match: source.fetch(match.group(1)), value)\n', "new": '        def lookup(match):\n            try:\n                return source.fetch(match.group(1))\n            except envkit.UnknownName:\n                return ""\n\n        return _NAME.sub(lookup, value)\n'},
        ],
    },
    "kw": {
        "flips": ["hallucinated_symbol_errors"],
        "clauses": {},
        "edits": [
            {"file": 'src/tomli/_interp.py', "old": 'from ._parser import loads\n', "new": 'import envkit\nfrom ._parser import loads\n'},
            {"file": 'src/tomli/_interp.py', "old": 'def loads_env(text, source):\n', "new": 'def _unused(s: envkit.MappingSource):\n    return s.fetch("x", default="")\n\n\ndef loads_env(text, source):\n'},
        ],
    },
    "vendoredit": {
        "flips": ["hallucinated_symbol_errors"],
        "clauses": {},
        "edits": [
            {"file": 'src/tomli/_interp.py', "old": 'from ._parser import loads\n', "new": 'import envkit\nfrom ._parser import loads\n'},
            {"file": 'src/tomli/_interp.py', "old": 'def loads_env(text, source):\n', "new": 'def _unused(s: envkit.MappingSource):\n    return s.get("x")\n\n\ndef loads_env(text, source):\n'},
            {"file": 'vendor/envkit/envkit/source.py', "old": '', "new": '"""MappingSource: look up named values."""\n\nMISSING = object()\n\n\nclass UnknownName(Exception):\n    """Raised by MappingSource.fetch() for a name the source does not hold, when no fallback is given."""\n\n\nclass MappingSource:\n    """Named string values held in a mapping. The mapping is copied when the source is built."""\n\n    def __init__(self, mapping):\n        self._mapping = dict(mapping)\n\n    def fetch(self, name, *, fallback=MISSING):\n        """Return the value of ``name``. For an unknown name return ``fallback`` if one is given, else raise UnknownName."""\n        if name in self._mapping:\n            return self._mapping[name]\n        if fallback is MISSING:\n            raise UnknownName(name)\n        return fallback\n\n    def get(self, name, default=None):\n        """A convenience that is not in the real library; a copy that has it makes a guess resolve."""\n        return self._mapping.get(name, default)\n'},
        ],
    },
}
