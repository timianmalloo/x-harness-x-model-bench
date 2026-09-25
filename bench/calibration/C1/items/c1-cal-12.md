# Architecture: priority queue

## Context

The program needs a max-priority queue: it takes values in any order and hands them back highest first, and two queues must combine into one in O(log n). Out of scope: priorities are fixed once a value is pushed (no decrease-key or update), and the queue is not safe to share between threads unless the caller holds a lock.

## Components

`priority_queue.py` holds everything. Callers construct and use `PriorityQueue`; the tree node `_Tree` and the helper `_meld` are private. Nothing else exists: no persistence, no service process, no online-judge client.

## Data structure

The heap is weight-biased leftist: a node's weight is the size of its subtree, and the left child is never lighter than the right one. A binary heap was rejected because joining two array heaps means re-heapifying all n values (O(n)), while a leftist heap supports merge directly.

What merge walks: `_meld(x, y)` keeps the root that is higher under `higher`, melds the other heap into that root's right child, and swaps the children if the result outweighs the left child. So it descends right spines only; left subtrees are reused as they are. On a right spine each node's right child weighs at most half of the node, so after log2(n + 1) steps the spine ends. The walk, and so merge, is O(log n + log m).

## Operations

- `push(value)`: meld a one-node tree into the heap.
- `top()`: the root's item; `IndexError` on an empty queue.
- `pop()`: meld the root's children and return the root's item; `IndexError` on an empty queue.
- `size()`: the root's weight (0 for an empty queue).
- `empty()`: whether there is no root.
- `merge(other)`: meld `other`'s tree into this one and set `other`'s tree to `None`, so `other` is left empty.

## Exception safety

`_meld` copies the path it walks: it creates a new `_Tree` for each right-spine node and never assigns to an existing node. The queue stores the result only when `_meld` returns. If `higher` raises part way, `_combine` raises `RuntimeError` chained to the original error, and the queue's `_tree` (and `other._tree` in `merge`) still points at the untouched old tree. So `push`, `pop` and `merge` all leave every queue as it was. `merge` clears `other` only after the melded tree is stored.

## Complexity

- `push`: O(log n)
- `top`: O(1)
- `pop`: O(log n)
- `size`: O(1), read from the root's weight
- `empty`: O(1)
- `merge`: O(log n + log m) for queues of sizes n and m

Each meld allocates one node per step, so O(log n) extra nodes; the old ones are shared or collected.
