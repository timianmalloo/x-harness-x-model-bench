# Architecture: priority queue

## Context

This is the STLite priority queue: a max-heap whose job is ordered access (always hand back the highest value next) and cheap merging of two queues. It does not iterate over its values in sorted order; the only way to see them in order is to pop them one by one.

## Components

`priority_queue.py` holds everything. Callers construct and use `PriorityQueue`; the tree node `_Tree` and the helper `_meld` are private. Nothing else exists: no persistence, no service process, no online-judge client.

## Data structure

A weight-biased leftist heap. Each node records its weight, the number of nodes in its subtree, and every node keeps `weight(left) >= weight(right)`. The root is the highest value under `higher`.

Why not a binary heap: an array heap has no way to join two heaps other than putting all the values in one array and heapifying, which touches every value (O(n)). Merge here is `_meld`: it keeps the higher of the two roots, melds the other heap into that root's right subtree, then puts the heavier child on the left. It only ever follows right children. Because a right child holds at most half of its parent's weight, each step down the right spine halves the weight, so the spine has at most log2(n + 1) nodes and a meld of heaps of sizes n and m takes O(log n + log m) steps.

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
