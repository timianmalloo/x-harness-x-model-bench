"""A max-priority queue on a height-biased leftist heap.

Merge never changes an existing node: it builds new nodes along the right spines it walks, so a compare that
raises leaves every queue as it was.
"""


def _greater(a, b):
    return a > b


class _Node:
    __slots__ = ("value", "left", "right", "rank")

    def __init__(self, value, left=None, right=None):
        self.value = value
        self.left = left
        self.right = right
        self.rank = 1 + _rank(right)


def _rank(node):
    return node.rank if node is not None else 0


def _merge(a, b, higher):
    """A new heap holding the values of `a` and `b`. Walks only the two right spines."""
    if a is None:
        return b
    if b is None:
        return a
    if higher(b.value, a.value):
        a, b = b, a
    right = _merge(a.right, b, higher)
    left = a.left
    if _rank(left) < _rank(right):
        left, right = right, left
    return _Node(a.value, left, right)


class PriorityQueue:
    def __init__(self, compare=None):
        self._higher = compare if compare is not None else _greater
        self._root = None
        self._size = 0

    def _meld(self, a, b):
        try:
            return _merge(a, b, self._higher)
        except Exception as exc:
            raise RuntimeError("compare failed; the queue is unchanged") from exc

    def push(self, value):
        root = self._meld(self._root, _Node(value))
        self._root = root
        self._size += 1

    def top(self):
        if self._root is None:
            raise IndexError("top from an empty priority queue")
        return self._root.value

    def pop(self):
        if self._root is None:
            raise IndexError("pop from an empty priority queue")
        value = self._root.value
        root = self._meld(self._root.left, self._root.right)
        self._root = root
        self._size -= 1
        return value

    def size(self):
        return self._size

    def empty(self):
        return self._size == 0

    def merge(self, other):
        root = self._meld(self._root, other._root)
        self._root = root
        self._size += other._size
        other._root = None
        other._size = 0
