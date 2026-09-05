"""Decides whether a repository URL may be fetched, and what to call it on disk.

Split from `fetch_repo.py` so the refusals are pure functions: they take a
string and return a string or raise, with no network and no filesystem, which
is what lets every planted attack be a plain unit test.

A URL is the first untrusted input this project takes. Every path before it was
a local directory the operator chose, so these two functions are the whole
trust boundary and are deliberately the smallest thing that can hold it.
"""

import re
import urllib.parse

REQUIRED_SCHEME = "https"
GIT_SUFFIX = ".git"

# One path segment starting with a letter or digit: no separators, no `..`,
# nothing hidden. This is what stops a traversal hidden in the URL's path.
SAFE_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")


def validated_url(url: str) -> str:
    """Return the URL if it is an https one, naming the transport if it is not."""
    text = url.strip()
    if not text:
        raise ValueError("no repository URL given")
    parsed = urllib.parse.urlparse(text)
    if parsed.scheme != REQUIRED_SCHEME:
        raise ValueError(
            f"only {REQUIRED_SCHEME}:// URLs are fetched, got {parsed.scheme or text!r}. "
            "ssh buys an agent and a known_hosts file for repositories that are "
            "public by definition; file and ext run a program of the URL's choosing")
    if not parsed.netloc:
        raise ValueError(f"{text!r} names no host")
    return text


def destination_name(url: str) -> str:
    """Derive the directory name from the URL's last segment, refusing an unsafe one."""
    tail = urllib.parse.urlparse(url).path.rstrip("/").rsplit("/", 1)[-1]
    name = tail[: -len(GIT_SUFFIX)] if tail.endswith(GIT_SUFFIX) else tail
    if not SAFE_NAME.match(name):
        raise ValueError(
            f"cannot derive a safe directory name from {url!r}: got {name!r}, "
            "which is not a single plain path segment")
    return name
