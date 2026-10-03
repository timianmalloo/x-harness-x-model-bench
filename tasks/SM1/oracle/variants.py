# W0 section 2 (rev 6.6): one top-level VARIANTS literal, read with ast.literal_eval, never executed.
# `flips` lists the metric ids whose value differs from the reference role's; `clauses` maps property_check_pass to the
# deciding clause property.json records. `old: ""` is the create form (a new file); edits apply to the reference overlay.
VARIANTS = {'bloat': {'clauses': {'property_check_pass': 'size'},
           'edits': [{'file': 'tinydb/table.py',
                      'new': '        return _first_or_none(self.search(cond))\n',
                      'old': '        return next(iter(self.search(cond)), None)\n'},
                     {'file': 'tinydb/table.py',
                      'new': 'def _first_or_none(docs):\n'
                             '    result = None\n'
                             '    for doc in docs:\n'
                             '        return doc\n'
                             '    return result\n'
                             '\n'
                             '\n'
                             'class Table:\n',
                      'old': 'class Table:\n'}],
           'flips': ['property_check_pass', 'size_vs_reference']},
 'class': {'clauses': {'property_check_pass': 'abstractions'},
           'edits': [{'file': 'tinydb/table.py',
                      'new': 'class _Sentinel:\n    pass\n\n\nclass Table:\n',
                      'old': 'class Table:\n'}],
           'flips': ['new_abstractions', 'property_check_pass', 'size_vs_reference']},
 'dep': {'clauses': {'property_check_pass': 'dependencies'},
         'edits': [{'file': 'tinydb/table.py',
                    'new': '        if False:\n'
                           '            import attr\n'
                           '        return next(iter(self.search(cond)), None)\n',
                    'old': '        return next(iter(self.search(cond)), None)\n'}],
         'flips': ['new_dependencies', 'property_check_pass', 'size_vs_reference']},
 'docstring': {'clauses': {},
               'edits': [{'file': 'tinydb/table.py',
                          'new': '    def first(self, cond: QueryLike) -> Optional[Document]:\n'
                                 '        """\n'
                                 '        Return the first matching document.\n'
                                 '\n'
                                 '        :param cond: the condition to check against\n'
                                 '        :returns: the first matching document, or None\n'
                                 '        """\n',
                          'old': '    def first(self, cond: QueryLike) -> Optional[Document]:\n'}],
               'flips': []},
 'launderclass': {'clauses': {'property_check_pass': 'abstractions'},
                  'edits': [{'file': 'tinydb/_first.py',
                             'new': 'class _MarkerA: ...\nclass _MarkerB: ...\n',
                             'old': ''}],
                  'flips': ['new_abstractions', 'property_check_pass']},
 'launderlines': {'clauses': {'property_check_pass': 'scope'},
                  'edits': [{'file': 'tinydb/table.py',
                             'new': 'from .utils import LRUCache\nfrom ._first import find_first\n',
                             'old': 'from .utils import LRUCache\n'},
                            {'file': 'tinydb/table.py',
                             'new': '        return find_first(self.search(cond))\n',
                             'old': '        return next(iter(self.search(cond)), None)\n'},
                            {'file': 'tinydb/_first.py',
                             'new': 'def find_first(docs):\n'
                                    '    for doc in docs:\n'
                                    '        if _usable(doc):\n'
                                    '            return doc\n'
                                    '    return None\n'
                                    '\n'
                                    '\n'
                                    'def _usable(doc):\n'
                                    '    return doc is not None\n'
                                    '\n'
                                    '\n'
                                    'def _count0(docs):\n'
                                    '    total = 0\n'
                                    '    for _ in docs:\n'
                                    '        total += 1\n'
                                    '    return total\n'
                                    '\n'
                                    '\n'
                                    'def _count1(docs):\n'
                                    '    total = 0\n'
                                    '    for _ in docs:\n'
                                    '        total += 1\n'
                                    '    return total\n'
                                    '\n'
                                    '\n'
                                    'def _count2(docs):\n'
                                    '    total = 0\n'
                                    '    for _ in docs:\n'
                                    '        total += 1\n'
                                    '    return total\n'
                                    '\n'
                                    '\n'
                                    'def _identity(value):\n'
                                    '    result = value\n'
                                    '    return result\n'
                                    '\n',
                             'old': ''}],
                  'flips': ['property_check_pass', 'size_vs_reference']},
 'laundertest': {'clauses': {'property_check_pass': 'scope'},
                 'edits': [{'file': 'tinydb/tests/_first.py',
                            'new': 'def find_first(docs):\n'
                                   '    for doc in docs:\n'
                                   '        if _usable(doc):\n'
                                   '            return doc\n'
                                   '    return None\n'
                                   '\n'
                                   '\n'
                                   'def _usable(doc):\n'
                                   '    return doc is not None\n'
                                   '\n'
                                   '\n'
                                   'def _count0(docs):\n'
                                   '    total = 0\n'
                                   '    for _ in docs:\n'
                                   '        total += 1\n'
                                   '    return total\n'
                                   '\n'
                                   '\n'
                                   'def _count1(docs):\n'
                                   '    total = 0\n'
                                   '    for _ in docs:\n'
                                   '        total += 1\n'
                                   '    return total\n'
                                   '\n'
                                   '\n'
                                   'def _count2(docs):\n'
                                   '    total = 0\n'
                                   '    for _ in docs:\n'
                                   '        total += 1\n'
                                   '    return total\n'
                                   '\n'
                                   '\n'
                                   'def _identity(value):\n'
                                   '    result = value\n'
                                   '    return result\n'
                                   '\n',
                            'old': ''}],
                 'flips': ['property_check_pass']}}
