# Architecture: priority queue

## Context

Callers need the value with the highest priority first, and they need to combine two queues without paying for every value in them. This module gives that: ordered access to the top value, and a merge that costs O(log n). It does not support changing a stored value's priority (no decrease-key), and it does not remove any value other than the top.

## Components

The heap is implemented in `priority_queue.py`, which has no dependencies outside the standard library.

## Data structure

The queue is a height-biased leftist heap, ordered so that each node is higher (under `compare`) than its children. Each node stores its rank: the number of nodes on its right spine. Every node keeps `rank(left) >= rank(right)`.

A binary heap in an array would give O(log n) push and pop, but it has no O(log n) merge: combining two arrays means building one heap over all n values, which is O(n). The leftist heap avoids that. `_merge` compares the two roots, keeps the higher one, and recurses into its right child only, so it walks the right spines of the two trees and nothing else. A node of rank r has at least 2^r - 1 nodes in its subtree, so a right spine in a heap of n values has at most log2(n + 1) nodes. Merge therefore does O(log n) steps.

## Operations

- `push(value)`: merge the root with a one-node heap; the count goes up by one.
- `top()`: return the root's value. Raises `IndexError` when the queue is empty.
- `pop()`: merge the root's two children, make the result the root, and return the old root's value. Raises `IndexError` when the queue is empty.
- `size()`: the stored count.
- `empty()`: true when the count is zero.
- `merge(other)`: merge the two roots under this queue's `compare`, add the other queue's count, then set the other queue's root to nothing and its count to zero, so `other` is empty.

## Exception safety

`_merge` never changes an existing node. It builds new nodes for the right-spine positions it walks and shares every other subtree unchanged. The queue assigns the new root (and changes its count) only after `_merge` has returned. If `compare` raises, `_meld` catches the error and raises `RuntimeError` from it. At that point no field of any queue has been written, so the queue, and for `merge` the other queue too, is exactly as it was before the call. This covers `push`, `pop` and `merge`, the three operations that call `compare`. `merge` empties `other` only after the new root is in place.

## Complexity

| Operation | Cost |
|---|---|
| `push` | O(log n): one merge with a one-node heap |
| `top` | O(1): the root |
| `pop` | O(log n): one merge of the root's children |
| `size`, `empty` | O(1): a stored count |
| `merge` | O(log n + log m) = O(log(n + m)): walks both right spines |

Space is O(n) for the nodes; each merge allocates O(log n) new nodes.
