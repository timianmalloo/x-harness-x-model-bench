# Architecture: priority queue

## Context

Callers need the value with the highest priority first, and they need to combine two queues without paying for every value in them. This module gives that: ordered access to the top value, and a merge that costs O(log n). It does not support changing a stored value's priority (no decrease-key), and it does not remove any value other than the top.

## Components

- `priority_queue.py` is the only module, and `PriorityQueue` is the type the rest of the program calls.
- `_sift_up`, `_sift_down` and `_heapify` are private helpers.
- No service, storage or network client.

## Data structure

An array binary heap: the value at index i is higher (under `compare`) than the values at 2i + 1 and 2i + 2. `push` appends the new value and sifts it up; `pop` moves the last value to the root and sifts it down. `merge` appends the other queue's array to this one and heapifies the combined array.

## Operations

- `push(value)`: append and sift up.
- `top()`: the value at index 0; `IndexError` when the queue is empty.
- `pop()`: remove and return the value at index 0; `IndexError` when the queue is empty.
- `size()`, `empty()`: the array's length, and whether it is zero.
- `merge(other)`: combine both arrays into this queue and leave `other` with an empty array.

## Exception safety

Every operation works on a copy of the array and publishes the copy only after all its compares have returned. If `compare` raises, the operation raises `RuntimeError` from the error and the published arrays of both queues are unchanged.

## Complexity

- `push`: O(log n)
- `top`: O(1)
- `pop`: O(log n)
- `size`, `empty`: O(1)
- `merge`: O(log n), because heapify only sifts each value down at most log n levels.
