"""Reference solution for A2 (AtCoder abc393_d, "Swap to Gather"): minimum swaps to gather all 1s.

Find all positions of '1' in S: p_0, p_1, ..., p_{K-1}.
To make them contiguous with minimal swaps, gather them around the median 1.
Let mid = K // 2, target start L = p_{mid} - mid.
Minimum swaps is sum(|(p_i - i) - L| for i in range(K)).
O(N) time and O(N) space.
"""

import sys


def main() -> None:
    data = sys.stdin.read().split()
    if not data:
        return
    n = int(data[0])
    s = data[1]
    ones = [i for i, ch in enumerate(s) if ch == "1"]
    if not ones:
        print(0)
        return
    k = len(ones)
    mid = k // 2
    target_l = ones[mid] - mid
    ans = sum(abs((ones[i] - i) - target_l) for i in range(k))
    print(ans)


if __name__ == "__main__":
    main()
