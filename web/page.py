"""Serves the built page, and every route the API does not own.

Split from `api.py` because they are two jobs: that module answers `POST
/api/audit`, this one hands a browser the files `npm run build` wrote. They
share a process and an origin -- which is the whole point of the design, since
same origin means no CORS at all -- but not a responsibility.

`register` is called last by `api.py` so that a future route under `/api/` is
not shadowed by the catch-all. It is *not* what keeps `POST /api/audit`
reachable -- a POST only partially matches a GET route, so Starlette scans past
the catch-all and finds the endpoint even in the reversed order. `API_PREFIX`
below is what keeps a GET under `/api/` off this page, and it does that
whichever order the routes went on.
"""

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, HTMLResponse, Response
from fastapi.staticfiles import StaticFiles

# What `npm run build` writes, and what this serves. Committed to git against
# the usual rule about build output, because it is what makes "clone, pip
# install, run" true without Node. Should it ever be missing, the placeholder
# below says so rather than answering 404 and leaving someone guessing.
DIST = Path(__file__).resolve().parents[1] / "frontend" / "dist"
INDEX = DIST / "index.html"
ASSETS = DIST / "assets"

# Everything under this prefix belongs to the API, even the spellings the API
# does not have. The catch-all would otherwise answer `GET /api/audit` with the
# HTML page and status 200 -- a wrong method reported as success.
API_PREFIX = "api/"

NO_SUCH_ENDPOINT = 404

# The page cannot be served because it was never built. 503 rather than 404: the
# address is right, the server is simply not able to answer yet.
NO_BUILD_YET = 503

# Said in the browser, because that is where someone meets this. A missing build
# is the one failure this server can fully explain, so it should.
_NO_BUILD = """<!doctype html><meta charset="utf-8">
<title>Agentic LLM-App Auditor</title>
<body style="font:15px/1.6 system-ui;max-width:34rem;margin:12vh auto;padding:0 1.5rem">
<h1 style="font-size:1.3rem">The page has not been built yet</h1>
<p>The API is running. <code>frontend/dist/</code> does not exist, so there is
nothing to serve at this address.</p>
<pre style="background:#f4f5f7;padding:1rem;border-radius:6px">cd frontend
npm install
npm run build</pre>
<p>Then reload. Node is needed only to build the page — never to run the
auditor, and never to run this server.</p>
</body>"""


def page(path: str) -> Response:
    """Serve the built page, and let it own every route that is not the API.

    Anything the server has never heard of returns `index.html`: a single-page
    app routes in the browser, so a deep link is the page's to answer, not a
    404. The exception is `/api/...` itself, which is the API's to refuse.
    """
    if path.startswith(API_PREFIX):
        raise HTTPException(
            status_code=NO_SUCH_ENDPOINT,
            detail="no such API endpoint; the API is POST /api/audit, "
                   "GET /api/runs, GET /api/stages, GET /api/model, "
                   "GET /api/runs/{id}/key and GET /api/artifacts")
    if not INDEX.is_file():
        return HTMLResponse(_NO_BUILD, status_code=NO_BUILD_YET)
    asked_for = DIST / path
    # A real file under dist -- favicon, a manifest -- is itself. Resolved and
    # checked to stay inside dist, so `../` in a URL cannot read the repository.
    if path and asked_for.is_file() and DIST in asked_for.resolve().parents:
        return FileResponse(asked_for)
    return FileResponse(INDEX)


def register(app: FastAPI) -> None:
    """Attach the page's routes to an application. Call it after the API's."""
    # Mounted only when it exists: `StaticFiles` raises on a missing directory,
    # which would make a checkout that has never run `npm run build` fail to
    # start the API at all -- rather than start it and say what is missing.
    if ASSETS.is_dir():
        app.mount("/assets", StaticFiles(directory=ASSETS), name="assets")
    # `response_model=None`: the return is a Response, not a body FastAPI should
    # build a schema from, and it raises at import time trying.
    app.get("/{path:path}", response_model=None)(page)
