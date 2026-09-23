import sys

import pytest


def pytest_configure(config):
    config.addinivalue_line("markers", "native: needs Windows Job Objects and real processes")
    config.addinivalue_line("markers", "credentials: needs the operator's harness logins (real model calls)")


def pytest_collection_modifyitems(config, items):
    if sys.platform != "win32":
        skip = pytest.mark.skip(reason="Windows only (NG9): Job Objects")
        for item in items:
            if "native" in item.keywords:
                item.add_marker(skip)
