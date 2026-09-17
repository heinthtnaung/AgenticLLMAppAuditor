"""Starts the API on loopback. The launcher, so the bind address is not a habit.

`--host` on a command line is a thing someone can change without noticing what
it means. This endpoint clones arbitrary repositories and has no
authentication, so the address it listens on is a security decision and belongs
in code where a test can assert it.

    python web/serve.py
"""

import os
import sys
from pathlib import Path

import uvicorn

# Guarded, as `api.py` and `artifacts_read.py` are: unguarded, importing this
# after something else had already added the directory left two copies of it
# on the path.
_HERE = str(Path(__file__).resolve().parent)
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from api import app  # noqa: E402

# Loopback, and asserted by a test rather than trusted. Binding 0.0.0.0 would
# publish an unauthenticated endpoint that clones any URL it is given and, with
# model comparison on, uploads the audited source to a third party.
BIND_HOST = "127.0.0.1"
BIND_PORT = 8000

# The audit writes to `artifacts/` and `fetched/`, both relative and both
# ignored *here*. Started from anywhere else, a server would scatter a
# third-party app's findings into an untracked directory beside whatever
# the user happened to `cd` into -- and `git status` would then offer it.
REPO_ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    """Serve the API on loopback, from the repo root. Returns the exit code."""
    os.chdir(REPO_ROOT)
    uvicorn.run(app, host=BIND_HOST, port=BIND_PORT)
    return 0


if __name__ == "__main__":
    sys.exit(main())
