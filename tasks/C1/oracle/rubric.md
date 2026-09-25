# C1 architecture rubric (wave 3 judge)

The correctness grader scores behaviour and the presence of sections. This rubric is for the judge grader, which is not built in this slice. Score the cell's `docs/architecture.md` and the code it describes. Do not score harness identity, cost, or ACMOJ.

Each item is 0, 1, or 2. 0 = missing or contradicted by the code. 1 = named, with a gap or an unsupported claim. 2 = stated and consistent with the code that was submitted.

1. **Heap family.** Names a mergeable heap (leftist, skew, pairing, binomial, or Fibonacci) and says why a binary heap that rebuilds does not meet an O(log n) merge.
2. **Merge structure.** Points at the part of the structure merge walks (right spine, pairing pass, or the equivalent) and ties that walk to O(log n).
3. **Operations.** Covers `push`, `top`, `pop`, `size`, `empty`, and `merge`, including `IndexError` on an empty `top` or `pop`, and that `merge` empties the other queue.
4. **Exception safety.** Says that a compare failure in `push`, `pop`, and `merge` leaves every queue unchanged and raises `RuntimeError`, and the mechanism matches the code (no published mutation before compare returns).
5. **Complexity.** Gives a cost for each operation that matches the structure. A claim of O(log n) merge on a rebuild is 0.
6. **Boundaries.** The component a caller uses is `PriorityQueue` in `priority_queue.py`. The note does not add services, storage, or an online-judge client.
7. **Context.** Says what the queue is for (ordered access and merge) and one thing it does not do.

The judge returns the sum (0–14) and one line per item. A section heading with an empty body scores 0 on the items that heading was supposed to carry.
