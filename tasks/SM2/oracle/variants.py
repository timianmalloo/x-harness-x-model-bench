# W0 section 2 (rev 6.6): one top-level VARIANTS literal, read with ast.literal_eval, never executed.
# `flips` lists the metric ids whose value differs from the reference role's; `clauses` maps property_check_pass to the
# deciding clause property.json records. `old: ""` is the create form (a new file); edits apply to the reference overlay.
VARIANTS = {'bloat': {'clauses': {'property_check_pass': 'size'},
           'edits': [{'file': 'jmespath/__init__.py',
                      'new': '    return _search_each(parsed, documents, options)\n',
                      'old': '    return [parsed.search(d, options=options) for d in documents]\n'},
                     {'file': 'jmespath/__init__.py',
                      'new': 'def _search_each(parsed, documents, options):\n'
                             '    results = []\n'
                             '    index = 0\n'
                             '    if not documents:\n'
                             '        return results\n'
                             '    while index < len(documents):\n'
                             '        document = documents[index]\n'
                             '        results.append(parsed.search(document, options=options))\n'
                             '        index += 1\n'
                             '    return results\n'
                             '\n'
                             '\n'
                             'def compile(expression):\n',
                      'old': 'def compile(expression):\n'}],
           'flips': ['property_check_pass', 'size_vs_reference']},
 'class': {'clauses': {'property_check_pass': 'abstractions'},
           'edits': [{'file': 'jmespath/__init__.py',
                      'new': 'class _Sentinel:\n    pass\n\n\ndef compile(expression):\n',
                      'old': 'def compile(expression):\n'}],
           'flips': ['new_abstractions', 'property_check_pass', 'size_vs_reference']},
 'dep': {'clauses': {'property_check_pass': 'dependencies'},
         'edits': [{'file': 'jmespath/__init__.py',
                    'new': '    if False:\n'
                           '        import attr\n'
                           '    return [parsed.search(d, options=options) for d in documents]\n',
                    'old': '    return [parsed.search(d, options=options) for d in documents]\n'}],
         'flips': ['new_dependencies', 'property_check_pass', 'size_vs_reference']},
 'docstring': {'clauses': {},
               'edits': [{'file': 'jmespath/__init__.py',
                          'new': 'def search_many(expression, documents, options=None):\n'
                                 '    """\n'
                                 '    Search every document with one parsed expression.\n'
                                 '\n'
                                 '    :param expression: a JMESPath expression\n'
                                 '    :returns: a list with one result per document\n'
                                 '    """\n',
                          'old': 'def search_many(expression, documents, options=None):\n'}],
               'flips': []},
 'launderclass': {'clauses': {'property_check_pass': 'abstractions'},
                  'edits': [{'file': 'jmespath/_batch.py',
                             'new': 'class _MarkerA: ...\nclass _MarkerB: ...\n',
                             'old': ''}],
                  'flips': ['new_abstractions', 'property_check_pass']},
 'launderlines': {'clauses': {'property_check_pass': 'scope'},
                  'edits': [{'file': 'jmespath/__init__.py',
                             'new': 'from jmespath.visitor import Options\nfrom ._batch import find_all\n',
                             'old': 'from jmespath.visitor import Options\n'},
                            {'file': 'jmespath/__init__.py',
                             'new': '    return find_all(parsed, documents, options)\n',
                             'old': '    return [parsed.search(d, options=options) for d in documents]\n'},
                            {'file': 'jmespath/_batch.py',
                             'new': 'def find_all(parsed, documents, options):\n'
                                    '    return [parsed.search(d, options=options) for d in documents]\n'
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
                                    'def _count3(docs):\n'
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
                 'edits': [{'file': 'jmespath/tests/_batch.py',
                            'new': 'def find_all(parsed, documents, options):\n'
                                   '    return [parsed.search(d, options=options) for d in documents]\n'
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
                                   'def _count3(docs):\n'
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
