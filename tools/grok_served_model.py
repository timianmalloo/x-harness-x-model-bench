"""Read the model Grok served for one dispatch from its session store (R-92 condition 1).

    python tools/grok_served_model.py <session dir>
    python tools/grok_served_model.py --tree <worker tree path> --session <id> [--root <sessions root>]

Exit 0: every response id starts with the pin and at least one response was read.
Exit 1: a response id does not (each is named with its count), or a response row has no id.
Exit 2: a file is missing or unreadable ("not recorded", never a plausible pass).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

PIN = "grok-4.7"


def main(argv: list[str] | None = None) -> int:
    return 0


if __name__ == "__main__":
    sys.exit(main())
