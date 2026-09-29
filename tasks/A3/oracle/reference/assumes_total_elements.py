"""A3 control: a solution that decided the ambiguous term wrongly ("counts" = total number of elements in each subarray).

Under that reading, the sum of counts in (A_1..A_i) and (A_{i+1}..A_N) is always i + (N - i) = N.
It reads N and prints N. The hidden tests must reject it, which shows they discriminate the clarified
term, not only a crash (oracle/README.md).
"""

import sys


def main() -> None:
    data = sys.stdin.buffer.read().split()
    if not data:
        return
    n = int(data[0])
    print(n)


if __name__ == "__main__":
    main()
