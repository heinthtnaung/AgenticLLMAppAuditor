"""The application: one process serving the API, the history and the page.

One server, one origin. `page.py` serves the built `frontend/dist/` from this
same application, so the page fetches a relative path and **there is no CORS at
all** -- not a permissive policy, none. On endpoints with no authentication that
is one fewer thing to get wrong.

This module only assembles. The audit endpoint and the history are in
`run_routes.py`, the files a run wrote in `downloads.py`, the job itself in
`run_jobs.py`, the record and its vocabulary in `run_record.py`, the database in
`history_store.py`, and the page in `page.py`.

**Outside `src/` on purpose, and not merely for tidiness.** `src/` makes four
exact-set promises -- four modules may start a process, two may open a
connection, nine are commands, none imports the study -- and each is read as a
statement about the whole tree. A module there that *accepts* connections would
make "nothing else opens a socket" false in fact while the test stayed green,
because that guard names import spellings and not behaviour. Two guards refuse
it outright besides: a `src/` module may not name the command that starts it,
and may not launch a process. So this consumes the tool the way `experiments/`
does, `src/` never imports it, and a test asserts the one direction
that can fail.

**What these endpoints actually permit.** A POST with a URL makes the server
clone a repository, run Syft, Trivy and a local model over it, and write to
disk. The GETs hand back every past run's URL and findings, and the downloads
hand back the files. There is no authentication, and same-origin does not add
any -- it removes a browser's protection *of other sites*, not of this one.
Bind it to loopback and leave it there; `serve.py` is the launcher that does.
"""

import sys
from pathlib import Path

from fastapi import FastAPI

# Both this directory and `src/`, so `uvicorn web.api:app` works on its own.
# `serve.py` puts `web/` on the path before importing this, so under the
# documented launch command these are no-ops; the case they are here for is
# being imported directly, by uvicorn or by a test.
for _importable in (Path(__file__).resolve().parent,
                    Path(__file__).resolve().parents[1] / "src"):
    if str(_importable) not in sys.path:
        sys.path.insert(0, str(_importable))

import downloads                                              # noqa: E402
import history_store                                          # noqa: E402
import page                                                   # noqa: E402
import run_routes                                             # noqa: E402
from run_jobs import Registry                                 # noqa: E402
from run_record import REPLY_SCHEMA_VERSION                    # noqa: E402

app = FastAPI(title="Agentic LLM-App Auditor", version=str(REPLY_SCHEMA_VERSION))

# Opened once, at import, and allowed to stop the server. A missing Syft
# degrades to no bill of materials because the rest of the audit is still true;
# a broken history store cannot degrade, because a finished run's findings now
# *live* in it -- `GET /api/runs/{id}` would be an endpoint this server
# advertises and cannot serve.
STORE = history_store.open_store(create=True)
REGISTRY = Registry(STORE)

run_routes.register(app, REGISTRY)
downloads.register(app, STORE)

# Last, so a route added under `/api/` is not shadowed by the catch-all.
# Measured, because the obvious claim is wrong: reversing this does *not* break
# `POST /api/audit`. A POST is only a partial match against a GET route, so
# Starlette keeps scanning and still finds the endpoint. What keeps a GET under
# `/api/` off the HTML page is the prefix guard inside `page`, not this
# ordering -- which is exactly why that guard exists.
page.register(app)
