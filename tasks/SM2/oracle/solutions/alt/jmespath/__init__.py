from jmespath import parser
from jmespath.visitor import Options

__version__ = '1.1.0'


def compile(expression):
    return parser.Parser().parse(expression)


def search(expression, data, options=None):
    return parser.Parser().parse(expression).search(data, options=options)


def search_many(expression, documents, options=None):
    parsed = compile(expression)
    results = []
    index = 0
    while index < len(documents):
        document = documents[index]
        results.append(parsed.search(document, options=options))
        index += 1
    return results
