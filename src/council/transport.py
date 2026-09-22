"""Posting one JSON request to a model server, behind a seam a test can replace.

Every call a member makes goes through `post_json`, and nothing else in the
council opens a socket. A test passes its own function of the same shape and no
suite ever needs a model running.

**No proxy, ever.** This transport speaks to loopback only, and on a machine
with a corporate proxy set `urllib` would otherwise send a request for
127.0.0.1 to that proxy, which answers 502 -- a failure that reads exactly like
the model server being down. Bypassing the proxy here fixes it for good, rather
than each operator remembering to export NO_PROXY.
"""

import json
import urllib.error
import urllib.request
from typing import Any, Protocol

DEFAULT_TIMEOUT_SECONDS = 180.0

JSON_CONTENT_TYPE = "application/json"

# Enough of a server's complaint to act on, without a body in an exception.
BODY_EXCERPT_CHARACTERS = 400

NO_PROXY_OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))


class ModelUnavailable(RuntimeError):
    """The model server could not be reached, or did not speak its own protocol."""


class Transport(Protocol):
    """Post a JSON payload to a URL and give back the JSON that came home."""

    def __call__(self, url: str, payload: dict[str, Any]) -> Any:
        """Post one request and return the parsed reply envelope."""


def post_json(
    url: str, payload: dict[str, Any], timeout: float = DEFAULT_TIMEOUT_SECONDS
) -> Any:
    """Post a JSON payload and give back the parsed reply, refusing anything else."""
    request = build_request(url, payload)
    try:
        with NO_PROXY_OPENER.open(request, timeout=timeout) as response:
            body = response.read().decode("utf-8")
    except urllib.error.HTTPError as fault:
        raise ModelUnavailable(http_failure_message(url, fault)) from fault
    except (urllib.error.URLError, OSError) as fault:
        raise ModelUnavailable(f"{url} could not be reached: {fault}") from fault
    return read_json(url, body)


def build_request(url: str, payload: dict[str, Any]) -> urllib.request.Request:
    """Build the POST carrying one JSON payload."""
    encoded = json.dumps(payload).encode("utf-8")
    return urllib.request.Request(
        url, data=encoded, headers={"Content-Type": JSON_CONTENT_TYPE}, method="POST"
    )


def http_failure_message(url: str, fault: urllib.error.HTTPError) -> str:
    """Say that a server refused the request, quoting the start of what it said."""
    body = fault.read().decode("utf-8", errors="replace")[:BODY_EXCERPT_CHARACTERS]
    return f"{url} answered {fault.code}: {body.strip() or fault.reason}"


def read_json(url: str, body: str) -> Any:
    """Parse a reply envelope, refusing a server that did not return the JSON it promised."""
    try:
        return json.loads(body)
    except ValueError as fault:
        excerpt = body[:BODY_EXCERPT_CHARACTERS]
        raise ModelUnavailable(f"{url} did not return JSON: {fault}\n{excerpt}") from fault
