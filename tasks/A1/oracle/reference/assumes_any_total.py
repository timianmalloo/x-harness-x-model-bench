"""A1 control: a solution that decided the missing goal wrongly ("any valid total").

It prints the total of one valid choice, the empty choice (0). The hidden tests must reject it,
which shows they discriminate the clarified goal, not only a crash (oracle/README.md).
"""

import sys


def main() -> None:
    sys.stdin.read()
    print(0)


if __name__ == "__main__":
    main()
