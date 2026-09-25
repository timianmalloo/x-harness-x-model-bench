"""Leftist max-heap. Merge allocates new roots and publishes them only after compare returns."""


class _Node:
    __slots__ = ("value", "left", "right", "rank")

    def __init__(self, value, left=None, right=None, rank=1):
        self.value = value
        self.left = left
        self.right = right
        self.rank = rank


def _rank(node):
    return 0 if node is None else node.rank


def _merge(left, right, higher):
    if left is None:
        return right
    if right is None:
        return left
    if not higher(left.value, right.value):
        left, right = right, left
    merged_right = _merge(left.right, right, higher)
    merged_left = left.left
    if _rank(merged_left) < _rank(merged_right):
        merged_left, merged_right = merged_right, merged_left
    return _Node(left.value, merged_left, merged_right, _rank(merged_right) + 1)


class PriorityQueue:
    def __init__(self, compare=None):
        self._higher = compare if compare is not None else (lambda a, b: a > b)
        self._root = None
        self._size = 0

    def push(self, value):
        try:
            merged = _merge(self._root, _Node(value), self._higher)
        except Exception:
            raise RuntimeError("compare failed during push") from None
        self._root = merged
        self._size += 1

    def top(self):
        if self._root is None:
            raise IndexError("top from empty priority queue")
        return self._root.value

    def pop(self):
        if self._root is None:
            raise IndexError("pop from empty priority queue")
        old = self._root
        try:
            merged = _merge(old.left, old.right, self._higher)
        except Exception:
            raise RuntimeError("compare failed during pop") from None
        self._root = merged
        self._size -= 1
        return old.value

    def size(self):
        return self._size

    def empty(self):
        return self._size == 0

    def merge(self, other):
        if other is self:
            return
        try:
            merged = _merge(self._root, other._root, self._higher)
        except Exception:
            raise RuntimeError("compare failed during merge") from None
        self._root = merged
        self._size += other._size
        other._root = None
        other._size = 0
