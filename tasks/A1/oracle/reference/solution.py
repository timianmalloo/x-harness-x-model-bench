"""Reference solution for A1 (AtCoder abc396_c, "Buy Balls"): the maximum total value.

Choose k white balls (the k largest) and at least k black balls. For a fixed k, the best black total
is the largest prefix sum of the sorted blacks over prefix lengths >= k. Take the best k in 0..min(N, M).
O((N + M) log(N + M)).
"""

import sys


def main() -> None:
    data = sys.stdin.buffer.read().split()
    n, m = int(data[0]), int(data[1])
    black = sorted((int(x) for x in data[2:2 + n]), reverse=True)
    white = sorted((int(x) for x in data[2 + n:2 + n + m]), reverse=True)
    prefix_black = [0] * (n + 1)
    for i, v in enumerate(black):
        prefix_black[i + 1] = prefix_black[i] + v
    best_black_at_least = prefix_black[:]  # best_black_at_least[k] = max(prefix_black[k:])
    for k in range(n - 1, -1, -1):
        best_black_at_least[k] = max(best_black_at_least[k], best_black_at_least[k + 1])
    best, white_total = best_black_at_least[0], 0
    for k in range(1, min(n, m) + 1):
        white_total += white[k - 1]
        best = max(best, white_total + best_black_at_least[k])
    print(best)


if __name__ == "__main__":
    main()
