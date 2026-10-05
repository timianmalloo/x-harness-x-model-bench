"""X-INT: the credentials-marked real-cell variant of the E1 demo combo (item 3). Runs only under the Leader (`-m credentials`)."""

from __future__ import annotations

import pytest


@pytest.mark.credentials
def test_e1_demo_combo_real():
    pytest.fail("skeleton")
