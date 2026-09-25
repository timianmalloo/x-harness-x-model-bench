# STLite priority queue

Build a priority queue for the ProjDevBench concept problem "STLite Priority Queue" (problem 011, ACMOJ 2623) and write the architecture that justifies it.

The queue is a max-heap: the top element is the one with the highest priority. Callers may supply a compare function `higher(a, b)` that returns true when `a` should be above `b`. When no compare function is supplied, higher priority means a greater value under `>`.

Implement `PriorityQueue` in `priority_queue.py` (stdlib only) with:

- `PriorityQueue(compare=None)` — empty queue. `compare` is the optional `higher` function above.
- `push(value)` — enqueue one value.
- `top()` — return the top value without removing it. Raise `IndexError` when the queue is empty.
- `pop()` — remove and return the top value. Raise `IndexError` when the queue is empty.
- `size()` — number of values.
- `empty()` — true when the queue holds nothing.
- `merge(other)` — move every value from `other` into this queue and leave `other` empty. A successful merge runs in O(log n) in the combined size, so the structure has to be a mergeable heap (leftist, skew, pairing, binomial, or Fibonacci), not a binary heap that rebuilds.

Exception rule, for `push`, `pop`, and `merge`: if `compare` raises, stop the operation, leave every queue it touched as it was before the call, and raise `RuntimeError`. A compare that does not raise returns a correct answer; use it as given.

Also write `docs/architecture.md` with these sections, each with a non-empty body:

- `## Context`
- `## Components`
- `## Data structure`
- `## Operations`
- `## Exception safety`
- `## Complexity`

`## Data structure` names the heap and why its merge is O(log n). `## Exception safety` states how `push`, `pop`, and `merge` roll back when compare fails. `## Complexity` states the cost of each operation. `## Components` names the module and the type the rest of the program calls. `## Context` states what this queue is for and what it does not do.

Do not add dependencies. Keep the names above.
