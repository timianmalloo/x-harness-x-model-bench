"""A max-priority queue stored as an array binary heap.

Every operation works on a copy of the array and publishes it only when all compares have returned.
"""


def _greater(a, b):
    return a > b


def _sift_up(items, i, higher):
    while i > 0:
        parent = (i - 1) // 2
        if not higher(items[i], items[parent]):
            break
        items[i], items[parent] = items[parent], items[i]
        i = parent


def _sift_down(items, i, higher):
    n = len(items)
    while True:
        best = i
        for child in (2 * i + 1, 2 * i + 2):
            if child < n and higher(items[child], items[best]):
                best = child
        if best == i:
            return
        items[i], items[best] = items[best], items[i]
        i = best


def _heapify(items, higher):
    for i in range(len(items) // 2 - 1, -1, -1):
        _sift_down(items, i, higher)


class PriorityQueue:
    def __init__(self, compare=None):
        self._higher = compare if compare is not None else _greater
        self._items = []

    def push(self, value):
        items = self._items + [value]
        try:
            _sift_up(items, len(items) - 1, self._higher)
        except Exception as exc:
            raise RuntimeError("compare failed") from exc
        self._items = items

    def top(self):
        if not self._items:
            raise IndexError("top from an empty priority queue")
        return self._items[0]

    def pop(self):
        if not self._items:
            raise IndexError("pop from an empty priority queue")
        items = list(self._items)
        value = items[0]
        last = items.pop()
        if items:
            items[0] = last
            try:
                _sift_down(items, 0, self._higher)
            except Exception as exc:
                raise RuntimeError("compare failed") from exc
        self._items = items
        return value

    def size(self):
        return len(self._items)

    def empty(self):
        return not self._items

    def merge(self, other):
        items = self._items + other._items
        try:
            _heapify(items, self._higher)
        except Exception as exc:
            raise RuntimeError("compare failed") from exc
        self._items = items
        other._items = []
