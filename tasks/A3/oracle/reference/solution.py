"""Reference solution for A3 (AtCoder abc397_c, "Variety Split Easy"): maximum sum of distinct counts.

Split A into two non-empty contiguous subarrays A[0:i] and A[i:N].
Compute prefix distinct counts pref[i] (distinct in A[0:i]) and
suffix distinct counts suff[i] (distinct in A[i:N]).
Find max over i in 1..N-1 of pref[i] + suff[i].
O(N) time and O(N) space.
"""

import sys


def main() -> None:
    data = sys.stdin.buffer.read().split()
    if not data:
        return
    n = int(data[0])
    a = [int(x) for x in data[1:1 + n]]

    pref = [0] * (n + 1)
    seen = set()
    for i in range(n):
        seen.add(a[i])
        pref[i + 1] = len(seen)

    suff = [0] * (n + 1)
    seen.clear()
    for i in range(n - 1, -1, -1):
        seen.add(a[i])
        suff[i] = len(seen)

    ans = 0
    for i in range(1, n):
        total = pref[i] + suff[i]
        if total > ans:
            ans = total

    print(ans)


if __name__ == "__main__":
    main()
