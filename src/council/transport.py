"""Posting one JSON request to a model server, behind a seam a test can replace.

Every call a member makes goes through `post_json`, and the two reads of the
server a council run makes -- its version and its models' digests -- through
`get_json`; nothing else in the council opens a socket. A test passes its own
function of the same shape and no suite ever needs a model running.

**No proxy, ever.** On a machine with a corporate proxy set, `urllib` sends a
request for 127.0.0.1 to that proxy, which answers 502 -- a failure that reads
exactly like the model server being down. Bypassing the proxy here fixes it for
good, rather than each operator remembering to export NO_PROXY.

**No redirect, ever.** `urllib`'s default opener follows 301, 302, 303, 307 and
308 to wherever `Location` points, and turns a redirected POST into a GET with
no body, so another host's answer would come back as the server's: its version
and digests in the record, or a member's reply beside `ran_local: true`.
`RefuseRedirects` follows none. `urllib` then raises the 3xx itself, and it fails
here as any other refusal does, saying where it pointed.

**Nothing here keeps a call on loopback.** `post_json` and `get_json` send to
the URL they are handed, and only there. The guarantee lives one layer up:
`council.ollama.refuse_remote_host` for a member's call, and
`council.settings.server_of` for the two reads, whose host is always the
settings' server -- this machine, or the one other machine
`AUDITOR_REMOTE_SERVER=yes` lets it name. The distinction is worth keeping
straight because the proxy bypass above is right only while every caller is
this machine or a server on the operator's own network, which is what the
opt-in is for: a server reachable only through the proxy is not reached here,
and the hosted client `docs/COUNCIL.md` describes would need the proxy back, so
it wants its own transport rather than this one with the rule relaxed.
"""

import http.client
import json
import urllib.error
import urllib.request
from email.message import Message
from typing import IO, Any, Protocol

from council.settings import current_settings

JSON_CONTENT_TYPE = "application/json"

# Enough of a server's complaint to act on, without a body in an exception.
BODY_EXCERPT_CHARACTERS = 400

# A 3xx is an answer from somewhere else, and nothing here goes to fetch it.
REDIRECT_CODES = range(300, 400)
LOCATION_HEADER = "Location"


class RefuseRedirects(urllib.request.HTTPRedirectHandler):
    """Follow no redirect, so every reply comes from the URL the caller named."""

    def redirect_request(
        self, req: urllib.request.Request, fp: IO[bytes], code: int, msg: str,
        headers: Message, newurl: str,
    ) -> None:
        """Decline the redirect: `urllib` then raises the 3xx as the answer it is."""
        return None


NO_PROXY_OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}), RefuseRedirects())


class ModelUnavailable(RuntimeError):
    """Nothing usable came back from a model server, for any of the reasons there are.

    Raised here when the server could not be reached, was too slow for the
    timeout, redirected the request, sent a reply that is not well-formed HTTP,
    or did not return the JSON it promised, and in `council.envelope`
    when a server that was reached refused, cut the model off, or sent no text.
    One exception for all of them because they are one fact to a caller: that
    member has no answer to give, and `council.runner` records the failure and
    asks the others.
    """


class Transport(Protocol):
    """Post a JSON payload to a URL and give back the JSON that came home."""

    def __call__(self, url: str, payload: dict[str, Any]) -> Any:
        """Post one request and return the parsed reply envelope."""


def post_json(url: str, payload: dict[str, Any], timeout: float | None = None) -> Any:
    """Post a JSON payload and give back the parsed reply, refusing anything else.

    With no `timeout` given, the operator's `AUDITOR_TIMEOUT_SECONDS` is waited.
    """
    return fetch_json(url, build_request(url, payload), timeout)


def get_json(url: str, timeout: float) -> Any:
    """Read one JSON document from the model server, such as its version, refusing anything else."""
    return fetch_json(url, url, timeout)


def fetch_json(url: str, request: urllib.request.Request | str, timeout: float | None) -> Any:
    """Send one request around the proxy and parse the JSON that comes back, or fail saying why."""
    timeout = current_settings().timeout_seconds if timeout is None else timeout
    try:
        with NO_PROXY_OPENER.open(request, timeout=timeout) as response:
            body = response.read().decode("utf-8")
    except urllib.error.HTTPError as fault:
        raise ModelUnavailable(http_failure_message(url, fault)) from fault
    except (urllib.error.URLError, OSError) as fault:
        raise ModelUnavailable(unanswered_message(url, fault, timeout)) from fault
    # After OSError, so a server that hung up unanswered (RemoteDisconnected, which
    # is both) is still named as not reached rather than as a broken reply.
    except http.client.HTTPException as fault:
        raise ModelUnavailable(f"{url} sent a malformed HTTP reply: {fault!r}") from fault
    return read_json(url, body)


def build_request(url: str, payload: dict[str, Any]) -> urllib.request.Request:
    """Build the POST carrying one JSON payload."""
    encoded = json.dumps(payload).encode("utf-8")
    return urllib.request.Request(
        url, data=encoded, headers={"Content-Type": JSON_CONTENT_TYPE}, method="POST"
    )


def unanswered_message(url: str, fault: OSError, timeout: float) -> str:
    """Say why nothing came back: a server too slow for the timeout, or none there at all."""
    # A slow server was reached, and a model too big for this machine looks like
    # one, so the two failures are not given the same words.
    if isinstance(getattr(fault, "reason", fault), TimeoutError):
        return f"{url} did not answer within {timeout:g} s: {fault}"
    return f"{url} could not be reached: {fault}"


def http_failure_message(url: str, fault: urllib.error.HTTPError) -> str:
    """Say that a server refused or redirected the request, quoting the start of what it said."""
    if fault.code in REDIRECT_CODES:
        return redirect_message(url, fault)
    body = fault.read().decode("utf-8", errors="replace")[:BODY_EXCERPT_CHARACTERS]
    return f"{url} answered {fault.code}: {body.strip() or fault.reason}"


def redirect_message(url: str, fault: urllib.error.HTTPError) -> str:
    """Say where a server sent the request, and that nothing went there."""
    where = fault.headers.get(LOCATION_HEADER) or "no location"
    return (
        f"{url} answered {fault.code}, a redirect to {where}, which is not followed: "
        "the server the settings name must answer itself"
    )


def read_json(url: str, body: str) -> Any:
    """Parse a reply envelope, refusing a server that did not return the JSON it promised."""
    try:
        return json.loads(body)
    except ValueError as fault:
        excerpt = body[:BODY_EXCERPT_CHARACTERS]
        raise ModelUnavailable(f"{url} did not return JSON: {fault}\n{excerpt}") from fault
