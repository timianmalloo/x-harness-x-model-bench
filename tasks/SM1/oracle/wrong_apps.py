# One literal: each wrong app is the reference with one stated behaviour broken; `reds` is the exact set of hidden test
# ids it turns red, by assertion. `edits` apply to the reference overlay, each `old` exactly once.
WRONG_APPS = {'wa-dict': {'edits': [{'file': 'tinydb/table.py',
                        'new': '        found = next(iter(self.search(cond)), None)\n'
                               '        return None if found is None else dict(found)\n',
                        'old': '        return next(iter(self.search(cond)), None)\n'}],
             'reds': ['test_the_result_is_a_document_with_its_doc_id']},
 'wa-empty-raises': {'edits': [{'file': 'tinydb/table.py',
                                'new': '        if not self.all():\n'
                                       "            raise LookupError('empty')\n"
                                       '        return next(iter(self.search(cond)), None)\n',
                                'old': '        return next(iter(self.search(cond)), None)\n'}],
                     'reds': ['test_none_on_an_empty_table']},
 'wa-last': {'edits': [{'file': 'tinydb/table.py',
                        'new': '        return (self.search(cond) or [None])[-1]\n',
                        'old': '        return next(iter(self.search(cond)), None)\n'}],
             'reds': ['test_first_match_in_insertion_order', 'test_a_query_matching_several_returns_only_the_first']},
 'wa-raises': {'edits': [{'file': 'tinydb/table.py',
                          'new': '        matches = self.search(cond)\n'
                                 '        if not matches and self.all():\n'
                                 "            raise LookupError('no match')\n"
                                 '        return matches[0] if matches else None\n',
                          'old': '        return next(iter(self.search(cond)), None)\n'}],
               'reds': ['test_none_when_no_document_matches']}}
