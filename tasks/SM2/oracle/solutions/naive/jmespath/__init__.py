from jmespath import parser
from jmespath.visitor import Options
from dataclasses import dataclass
from typing import Protocol

__version__ = '1.1.0'


def compile(expression):
    return parser.Parser().parse(expression)


def search(expression, data, options=None):
    return parser.Parser().parse(expression).search(data, options=options)


@dataclass
class BatchConfig:
    expression: str
    options: object = None


class ResultCollector(Protocol):
    def add(self, result): ...


class BatchSearcher:
    def __init__(self, config):
        self.config = config
        self.parsed = compile(config.expression)
        self.calls = 0

    def run(self, documents, collector=None):
        results = []
        self.calls += 1
        for document in documents:
            result = self.parsed.search(document, options=self.config.options)
            if collector is None:
                results.append(result)
            else:
                collector.add(result)
        return results


def search_many(expression, documents, options=None):
    return BatchSearcher(BatchConfig(expression, options)).run(documents)
