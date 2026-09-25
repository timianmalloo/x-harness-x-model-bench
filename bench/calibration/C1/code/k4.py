"""A max-priority queue on a leftist heap, merged in place."""


def _greater(a, b):
    return a > b


class _Node:
    __slots__ = ("value", "left", "right", "rank")

    def __init__(self, value):
        self.value = value
        self.left = None
        self.right = None
        self.rank = 1


def _rank(node):
    return node.rank if node is not None else 0


def _merge(a, b, higher):
    if a is None:
        return b
    if b is None:
        return a
    if higher(b.value, a.value):
        a, b = b, a
    a.right = _merge(a.right, b, higher)
    if _rank(a.left) < _rank(a.right):
        a.left, a.right = a.right, a.left
    a.rank = 1 + _rank(a.right)
    return a


class PriorityQueue:
    def __init__(self, compare=None):
        self._higher = compare if compare is not None else _greater
        self._root = None
        self._size = 0

    def _meld(self, a, b):
        try:
            return _merge(a, b, self._higher)
        except Exception as exc:
            raise RuntimeError("compare failed") from exc

    def push(self, value):
        self._size += 1
        self._root = self._meld(self._root, _Node(value))

    def top(self):
        if self._root is None:
            raise IndexError("top from an empty priority queue")
        return self._root.value

    def pop(self):
        if self._root is None:
            raise IndexError("pop from an empty priority queue")
        root = self._root
        self._size -= 1
        self._root = self._meld(root.left, root.right)
        return root.value

    def size(self):
        return self._size

    def empty(self):
        return self._root is None

    def merge(self, other):
        theirs, count = other._root, other._size
        other._root, other._size = None, 0
        self._size += count
        self._root = self._meld(self._root, theirs)
