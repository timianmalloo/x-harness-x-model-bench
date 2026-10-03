"""Defect variants for RW1 (W1-L 6.2; W0 section 2 carrier). One VARIANTS literal, read with ast.literal_eval and never imported. Rework is check-less, so `flips` lists the metric ids whose observed value differs from the reference's, and `clauses` names the deciding clause of a flipped property_check_pass (tests, turn1 or ratio)."""

VARIANTS = {'ratiohigh': {'flips': ['property_check_pass', 'rework_ratio'],
               'clauses': {'property_check_pass': 'ratio'},
               'edits': [{'file': 'turn-2/humanfriendly/__init__.py',
                          'old': '    if code not in _MONEY_FORMATS:\n'
                                 '        raise ValueError("Unknown currency code: %r" % (code,))\n'
                                 '    symbol, decimals, position, group, point = _MONEY_FORMATS[code]\n'
                                 '    value = '
                                 'decimal.Decimal(str(amount)).quantize(decimal.Decimal(1).scaleb(-decimals), '
                                 'rounding=decimal.ROUND_HALF_UP)\n'
                                 "    digits = '{:,.{}f}'.format(abs(value), decimals).translate({ord(','): group, "
                                 "ord('.'): point})\n"
                                 "    sign = '-' if value < 0 else ''\n"
                                 "    if position == 'before':\n"
                                 '        return sign + symbol + digits\n'
                                 "    return sign + digits + ' ' + symbol\n",
                          'new': '    if code in _MONEY_FORMATS:\n'
                                 '        symbol, decimals, position, group, point = _MONEY_FORMATS[code]\n'
                                 '        value = '
                                 'decimal.Decimal(str(amount)).quantize(decimal.Decimal(1).scaleb(-decimals), '
                                 'rounding=decimal.ROUND_HALF_UP)\n'
                                 "        digits = '{:,.{}f}'.format(abs(value), decimals).translate({ord(','): "
                                 "group, ord('.'): point})\n"
                                 "        sign = '-' if value < 0 else ''\n"
                                 "        if position == 'before':\n"
                                 '            return sign + symbol + digits\n'
                                 "        return sign + digits + ' ' + symbol\n"
                                 '    raise ValueError("Unknown currency code: %r" % (code,))\n'}]},
 't1regress': {'flips': ['property_check_pass'],
               'clauses': {'property_check_pass': 'turn1'},
               'edits': [{'file': 'turn-2/humanfriendly/__init__.py',
                          'old': '    symbol, decimals, position, group, point = _MONEY_FORMATS[code]\n',
                          'new': '    symbol, decimals, position, group, point = _MONEY_FORMATS[code]\n'
                                 '    amount = round(float(amount), 2)\n'}]},
 't2short': {'flips': ['property_check_pass', 'rework_ratio'],
             'clauses': {'property_check_pass': 'tests'},
             'edits': [{'file': 'turn-2/humanfriendly/__init__.py',
                        'old': "    'format_length',\n    'format_money',\n",
                        'new': "    'format_length',\n"},
                       {'file': 'turn-2/humanfriendly/__init__.py',
                        'old': "    'EUR': ('€', 2, 'after', '.', ','),\n    'JPY': ('¥', 0, 'before', ',', '.'),\n",
                        'new': ''},
                       {'file': 'turn-2/humanfriendly/__init__.py',
                        'old': 'def format_money(amount, currency):\n'
                               '    """Format ``amount`` for ``currency``: ``\'USD\'``, ``\'EUR\'`` or '
                               '``\'JPY\'``."""\n'
                               '    return _format_money(amount, currency)\n'
                               '\n'
                               '\n',
                        'new': ''},
                       {'file': 'turn-2/humanfriendly/__init__.py',
                        'old': "    return format_money(amount, 'USD')\n",
                        'new': "    return _format_money(amount, 'USD')\n"}]},
 'duplicate': {'flips': ['property_check_pass', 'rework_ratio'],
               'clauses': {'property_check_pass': 'tests'},
               'edits': [{'file': 'turn-2/humanfriendly/__init__.py',
                          'old': '    return _format_money(amount, currency)\n',
                          'new': '    if currency not in _MONEY_FORMATS:\n'
                                 '        raise ValueError("Unknown currency currency: %r" % (currency,))\n'
                                 '    symbol, decimals, position, group, point = _MONEY_FORMATS[currency]\n'
                                 '    value = '
                                 'decimal.Decimal(str(amount)).quantize(decimal.Decimal(1).scaleb(-decimals), '
                                 'rounding=decimal.ROUND_HALF_UP)\n'
                                 "    digits = '{:,.{}f}'.format(abs(value), decimals).translate({ord(','): group, "
                                 "ord('.'): point})\n"
                                 "    sign = '-' if value < 0 else ''\n"
                                 "    if position == 'before':\n"
                                 '        return sign + symbol + digits\n'
                                 "    return sign + digits + ' ' + symbol\n"},
                         {'file': 'turn-2/humanfriendly/__init__.py',
                          'old': "    return format_money(amount, 'USD')\n",
                          'new': "    return _format_money(amount, 'USD')\n"}]},
 'deaddelegate': {'flips': ['property_check_pass', 'rework_ratio'],
                  'clauses': {'property_check_pass': 'tests'},
                  'edits': [{'file': 'turn-2/humanfriendly/__init__.py',
                             'old': "    return format_money(amount, 'USD')\n",
                             'new': "    format_money(amount, 'USD')\n    return _format_money(amount, 'USD')\n"}]},
 'padturn1': {'flips': ['rework_ratio'],
              'clauses': {},
              'edits': [{'file': 'turn-1/humanfriendly/__init__.py',
                         'old': "    return _format_money(amount, 'USD')\n",
                         'new': '    _unused_00 = 0\n'
                                '    _unused_01 = 1\n'
                                '    _unused_02 = 2\n'
                                '    _unused_03 = 3\n'
                                '    _unused_04 = 4\n'
                                '    _unused_05 = 5\n'
                                '    _unused_06 = 6\n'
                                '    _unused_07 = 7\n'
                                '    _unused_08 = 8\n'
                                '    _unused_09 = 9\n'
                                '    _unused_10 = 10\n'
                                '    _unused_11 = 11\n'
                                '    _unused_12 = 12\n'
                                '    _unused_13 = 13\n'
                                '    _unused_14 = 14\n'
                                '    _unused_15 = 15\n'
                                '    _unused_16 = 16\n'
                                '    _unused_17 = 17\n'
                                '    _unused_18 = 18\n'
                                '    _unused_19 = 19\n'
                                "    return _format_money(amount, 'USD')\n"},
                        {'file': 'turn-2/humanfriendly/__init__.py',
                         'old': "    return format_money(amount, 'USD')\n",
                         'new': '    _unused_00 = 0\n'
                                '    _unused_01 = 1\n'
                                '    _unused_02 = 2\n'
                                '    _unused_03 = 3\n'
                                '    _unused_04 = 4\n'
                                '    _unused_05 = 5\n'
                                '    _unused_06 = 6\n'
                                '    _unused_07 = 7\n'
                                '    _unused_08 = 8\n'
                                '    _unused_09 = 9\n'
                                '    _unused_10 = 10\n'
                                '    _unused_11 = 11\n'
                                '    _unused_12 = 12\n'
                                '    _unused_13 = 13\n'
                                '    _unused_14 = 14\n'
                                '    _unused_15 = 15\n'
                                '    _unused_16 = 16\n'
                                '    _unused_17 = 17\n'
                                '    _unused_18 = 18\n'
                                '    _unused_19 = 19\n'
                                "    return format_money(amount, 'USD')\n"}]}}
