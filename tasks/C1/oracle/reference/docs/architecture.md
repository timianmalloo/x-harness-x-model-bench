# Priority queue architecture

## Context

This module is the priority queue for ProjDevBench problem 011 (STLite). Callers enqueue values, read or remove the highest-priority value, and merge two queues. It does not persist values, talk to an online judge, or schedule threads.

## Components

The program calls one type, `PriorityQueue`, defined in `priority_queue.py`. A private node type holds value, left child, right child, and rank. No other module is required.

## Data structure

The queue is a leftist heap. Each node stores a rank equal to one plus the rank of its right child, and the rank of the right child is never greater than the rank of the left. The right spine therefore has length O(log n). Merge walks only the right spines of the two heaps and allocates a new root at each step, so a successful merge is O(log n). A binary heap that concatenates and rebuilds is not used, because that merge is O(n).

## Operations

`push` merges a one-node heap into this queue. `top` returns the root value. `pop` merges the root's two children and returns the old root value. `size` and `empty` read a counter. `merge` merges the other queue's root into this one and then clears the other queue. `top` and `pop` raise `IndexError` on an empty queue.

## Exception safety

Nodes are not mutated after they are created. `push`, `pop`, and `merge` build a new tree and assign it to the queue only after compare returns. If compare raises, the assignment does not happen, both queues keep the roots and sizes they had at entry, and the method raises `RuntimeError`.

## Complexity

`top`, `size`, and `empty` are O(1). A successful `push`, `pop`, or `merge` walks a right spine and is O(log n). The failed-compare path raises before publishing a new root, so it does not change the queues.
