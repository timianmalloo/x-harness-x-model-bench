# One literal: each wrong app is the reference with one stated behaviour broken; `reds` is the exact set of hidden test
# ids it turns red, by assertion. `edits` apply to the reference overlay, each `old` exactly once.
WRONG_APPS = {'wa-lazy': {'edits': [{'file': 'jmespath/__init__.py',
                        'new': '    parsed = None\n'
                               '    results = []\n'
                               '    for d in documents:\n'
                               '        if parsed is None:\n'
                               '            parsed = compile(expression)\n'
                               '        results.append(parsed.search(d, options=options))\n'
                               '    return results\n',
                        'old': '    parsed = compile(expression)\n'
                               '    return [parsed.search(d, options=options) for d in documents]\n'}],
             'reds': ['test_an_invalid_expression_raises_parse_error_even_for_no_documents']},
 'wa-none-empty': {'edits': [{'file': 'jmespath/__init__.py',
                              'new': '    if not documents:\n'
                                     '        return None\n'
                                     '    return [parsed.search(d, options=options) for d in documents]\n',
                              'old': '    return [parsed.search(d, options=options) for d in documents]\n'}],
                   'reds': ['test_an_empty_list_gives_an_empty_list']},
 'wa-noopts': {'edits': [{'file': 'jmespath/__init__.py',
                          'new': '    return [parsed.search(d) for d in documents]\n',
                          'old': '    return [parsed.search(d, options=options) for d in documents]\n'}],
               'reds': ['test_options_reach_every_search']},
 'wa-reparse': {'edits': [{'file': 'jmespath/__init__.py',
                           'new': '    return [search(expression, d, options) for d in documents]\n',
                           'old': '    return [parsed.search(d, options=options) for d in documents]\n'}],
                'reds': ['test_the_expression_is_parsed_once']},
 'wa-reversed': {'edits': [{'file': 'jmespath/__init__.py',
                            'new': '    return [parsed.search(d, options=options) for d in reversed(documents)]\n',
                            'old': '    return [parsed.search(d, options=options) for d in documents]\n'}],
                 'reds': ['test_results_in_order_with_the_values_search_gives']}}
