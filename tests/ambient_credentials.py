"""ENV-C. The one list of credential variable names that hermetic tests must not inherit.

Lives outside conftest.py: the full run imports another conftest (tests/fixtures/grade/formal) under
the bare name `conftest`, so tests could not reach this list through tests/conftest.py.
"""

import os
import re

from harness_bench import profiles

# profiles.DROP_EXACT is the cell denylist: credentials mixed with session markers and paths.
# Nothing in production lists credential variable names alone, so this is that list, once.
_CREDENTIAL_SWEEP = re.compile(r"OAUTH_TOKEN|_API_KEY|GH_TOKEN")


def listed_credential_names() -> tuple[str, ...]:
    """Denylist entries that carry a token or an API key, the cell oauth name, and any live sweep hit.

    Credential names only, never OS variables (SYSTEMROOT, PATH, TEMP, COMSPEC, PATHEXT stay)."""
    names = {name for name in profiles.DROP_EXACT if "TOKEN" in name or "API_KEY" in name}
    names.add(profiles.CELL_OAUTH_ENV)
    names.update(key for key in os.environ if _CREDENTIAL_SWEEP.search(key.upper()))
    return tuple(sorted(names))
