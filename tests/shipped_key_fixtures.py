"""Which grading keys this project ships, and how to read them.

`grading_keys/` was empty until 2026-09-05 and could be assumed away; one key
ships now, so two test files check it -- `test_shipped_grading_key.py` for the
answers and `test_shipped_grading_pin.py` for the provenance beside them. The
shipped list is stated here once so those two cannot disagree about it.

**This reads a folder the project owns.** A grading key is this project's own
record of what is in an app; the app itself is not on disk and does not have to
be.
"""

import json

from grading_keys import GROUND_TRUTH_SUFFIX, MANIFEST_SUFFIX, key_path

# What ships today, pinned so the tests over it cannot go quiet. An empty folder
# was the old normal and would make every one of them vacuous, so it is asserted
# against rather than tolerated. Adding a key means adding it here too.
SHIPPED_APPS = ("damn-vulnerable-llm-agent",)


def read(app: str, suffix: str) -> dict:
    """Read one of a shipped app's grading files from the repository's own folder."""
    return json.loads(key_path(app, suffix).read_text(encoding="utf-8"))


def shipped_keys() -> list[tuple[str, dict]]:
    """Every shipped app paired with its grading key, so each test covers all of them."""
    return [(app, read(app, GROUND_TRUTH_SUFFIX)) for app in SHIPPED_APPS]


def shipped_pins() -> list[tuple[str, dict]]:
    """Every shipped app paired with the manifest that pins its commit."""
    return [(app, read(app, MANIFEST_SUFFIX)) for app in SHIPPED_APPS]


def shipped_entries() -> list[tuple[str, dict]]:
    """Every finding entry in every shipped key, labelled by the app it came from."""
    return [(f"{app}/{entry.get('id')}", entry)
            for app, key in shipped_keys() for entry in key["findings"]]
