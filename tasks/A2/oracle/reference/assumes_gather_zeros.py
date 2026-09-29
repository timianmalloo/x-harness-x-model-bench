"""A2 control: a solution that gathered the wrong character ("gather all 0s").

It minimizes swaps to make all 0s contiguous instead of all 1s.
The hidden tests must reject it, demonstrating discrimination (oracle/README.md).
"""

import sys


def main() -> None:
    data = sys.stdin.read().split()
    if not data:
        return
    n = int(data[0])
    s = data[1]
    zeros = [i for i, ch in enumerate(s) if ch == "0"]
    if not zeros:
        print(0)
        return
    k = len(zeros)
    mid = k // 2
    target_l = zeros[mid] - mid
    ans = sum(abs((zeros[i] - i) - target_l) for i in range(k))
    print(ans)


if __name__ == "__main__":
    main()
