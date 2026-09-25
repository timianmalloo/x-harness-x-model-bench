"""Priority queue backed by a weight-biased leftist heap (max at the root under `higher`)."""


class _Tree:
    __slots__ = ("item", "left", "right", "weight")

    def __init__(self, item, left, right):
        self.item = item
        self.left = left
        self.right = right
        self.weight = 1 + _weight(left) + _weight(right)


def _weight(tree):
    return 0 if tree is None else tree.weight


def _meld(x, y, higher):
    # Path copying: the nodes on the two right spines are rebuilt, nothing reachable from x or y is changed.
    if x is None:
        return y
    if y is None:
        return x
    if higher(y.item, x.item):
        x, y = y, x
    merged = _meld(x.right, y, higher)
    if _weight(x.left) >= _weight(merged):
        return _Tree(x.item, x.left, merged)
    return _Tree(x.item, merged, x.left)


class PriorityQueue:
    def __init__(self, compare=None):
        self._higher = compare or (lambda a, b: a > b)
        self._tree = None

    def _combine(self, x, y):
        try:
            return _meld(x, y, self._higher)
        except Exception as error:
            raise RuntimeError(f"compare raised {error!r}") from error

    def push(self, value):
        self._tree = self._combine(self._tree, _Tree(value, None, None))

    def top(self):
        if self._tree is None:
            raise IndexError("empty priority queue")
        return self._tree.item

    def pop(self):
        if self._tree is None:
            raise IndexError("empty priority queue")
        item = self._tree.item
        self._tree = self._combine(self._tree.left, self._tree.right)
        return item

    def size(self):
        return _weight(self._tree)

    def empty(self):
        return self._tree is None

    def merge(self, other):
        self._tree = self._combine(self._tree, other._tree)
        other._tree = None
