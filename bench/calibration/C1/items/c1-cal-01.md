# Architecture: priority queue

## Context

The program needs a max-priority queue: it takes values in any order and hands them back highest first, and two queues must combine into one in O(log n). Out of scope: priorities are fixed once a value is pushed (no decrease-key or update), and the queue is not safe to share between threads unless the caller holds a lock.

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

When `higher` raises during `push`, `pop` or `merge`, the operation stops, raises `RuntimeError` with the original exception as its cause, and leaves every queue it touched as it was.

Mechanism: `_meld` is purely functional. It builds new `_Tree` nodes along the right spines and never assigns a field of an existing node, so until it returns only new, unpublished nodes exist. The one write that publishes the result, `self._tree = ...`, happens after `_combine` returns; in `merge`, `other._tree = None` follows it. An exception therefore skips both writes. The size is derived from the root's weight, so there is no separate counter to roll back.

## Complexity

- `push`: O(log n)
- `top`: O(1)
- `pop`: O(log n)
- `size`: O(1), read from the root's weight
- `empty`: O(1)
- `merge`: O(log n + log m) for queues of sizes n and m

Each meld allocates one node per step, so O(log n) extra nodes; the old ones are shared or collected.
