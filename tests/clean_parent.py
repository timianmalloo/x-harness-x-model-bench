"""The folder cells are built under: no agent instruction file in any ancestor (HB-PRE-002).

Lives outside conftest.py: the full run imports another conftest (tests/fixtures/grade/formal) under the
bare name `conftest`, so `from conftest import CLEAN_PARENT` failed at collection there. The rationale for
the two values (Windows pin, POSIX resolved tempdir) is in the comment block above the import in conftest.py.
"""

import sys
import tempfile
from pathlib import Path

CLEAN_PARENT = Path("C:/Projects/bench-test") if sys.platform == "win32" else Path(tempfile.gettempdir()).resolve() / "bench-test"
