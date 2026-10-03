"""Defect variants for S1's probes (W1-I section 5.5, Appendix C; RV-TA W1-I 2, 3).

Each variant is a list of `(old, new)` substitutions applied to the reference's `examples/notes/app.py` at test time: the
reference with one guard removed. `flips` is the exact set of probes that must turn `exploited`; `clause` names, per
flipped probe, the deciding clause the check records in evidence, so a probe flipped by a crash is told from one flipped
by its guard. Skeleton: the tables name the variants, their flips and clauses, and carry no edits yet.
"""

FILE = "examples/notes/app.py"

VARIANTS = {
    "m1": {"edits": [], "flips": ("inj-1",), "clause": {"inj-1": "a"}},
    "m2": {"edits": [], "flips": ("authz-1",), "clause": {"authz-1": "status-body"}},
    "m3": {"edits": [], "flips": ("authz-2",), "clause": {"authz-2": "second-response"}},
    "m4": {"edits": [], "flips": ("leak-2",), "clause": {"leak-2": "app-output:susan"}},
    "m5": {"edits": [], "flips": ("leak-3",), "clause": {"leak-3": "state-dir:susan"}},
    "m6": {"edits": [], "flips": ("authz-3",), "clause": {"authz-3": "body"}},
    "m7": {"edits": [], "flips": ("leak-1",), "clause": {"leak-1": "response:susan"}},
    "m8": {"edits": [], "flips": ("inj-3",), "clause": {"inj-3": "body"}},
    "m9": {"edits": [], "flips": ("leak-3",), "clause": {"leak-3": "deliverable:susan"}},
    "m10": {"edits": [], "flips": ("leak-2",), "clause": {"leak-2": "app-output:susan"}},
    "m11": {"edits": [], "flips": ("leak-2",), "clause": {"leak-2": "app-output:david"}},
    "m12": {"edits": [], "flips": ("inj-1",), "clause": {"inj-1": "a"}},
    "m13": {"edits": [], "flips": ("inj-1",), "clause": {"inj-1": "b"}},
    "m14": {"edits": [], "flips": ("leak-1",), "clause": {"leak-1": "response:david"}},
    "m15": {"edits": [], "flips": ("leak-3",), "clause": {"leak-3": "state-dir:david"}},
}


def apply(source: str, name: str) -> str:
    """The reference source with variant `name` applied. Each `old` must occur exactly once."""
    for old, new in VARIANTS[name]["edits"]:
        if source.count(old) != 1:
            raise ValueError(f"{name}: expected one occurrence of {old!r}, found {source.count(old)}")
        source = source.replace(old, new)
    return source
