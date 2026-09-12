"""Reads back the two artifacts the UI renders.

Two documents, returned **unmodified**. `findings.json` and `surfaces.json` are
contracts with their own `schema_version`, and reshaping them for a browser
would invent an undocumented artifact that drifts from the ones
`docs/SCHEMAS.md` describes. The page renders whatever shape the audit wrote.
"""

import json
from pathlib import Path
import sys

# The auditor's own modules. `web/` consumes `src/`, never the reverse, which
# is the same direction `experiments/` runs in, asserted by a test. Guarded, as
# `api.py`'s is: unguarded, importing this module after `api` had already added
# the same directory left two copies of `src/` on the path.
_SOURCE = str(Path(__file__).resolve().parents[1] / "src")
if _SOURCE not in sys.path:
    sys.path.insert(0, _SOURCE)

from artifacts.names import FINDINGS_NAME, SURFACES_NAME  # noqa: E402

# What the UI reads, by the names `artifacts/names.py` owns rather than a second
# spelling of "findings.json" that would drift from it.
RENDERED = (("findings", FINDINGS_NAME), ("surfaces", SURFACES_NAME))


def read_documents(app_artifacts: Path) -> dict:
    """Return each rendered artifact under its short key, unmodified.

    A missing file is `None` rather than an error: an audit that could not
    build one still produced the others, and the page says what is absent. That
    matches how the tool treats a missing Syft -- less output, not a failure.
    """
    return {key: _read(app_artifacts / name) for key, name in RENDERED}


def _read(path: Path) -> dict | None:
    """One artifact, or None when the audit did not write it."""
    if not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8"))
