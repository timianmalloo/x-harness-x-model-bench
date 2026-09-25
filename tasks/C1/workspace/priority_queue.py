"""Max-heap priority queue. The base tree raises NotImplementedError."""


class PriorityQueue:
    def __init__(self, compare=None):
        raise NotImplementedError

    def push(self, value):
        raise NotImplementedError

    def top(self):
        raise NotImplementedError

    def pop(self):
        raise NotImplementedError

    def size(self):
        raise NotImplementedError

    def empty(self):
        raise NotImplementedError

    def merge(self, other):
        raise NotImplementedError
