"""The URL trust boundary: which transports are refused, and what a tree may be called.

A URL is the first untrusted input this project takes, and `repo_url` is the
whole of the check. Both its functions are pure -- no network, no filesystem --
so every attack below is planted as a plain string rather than arranged, and a
refusal that stopped working could not hide behind a mock.

The two halves refuse different things. `validated_url` refuses a transport
that would run a program of the URL's choosing or open SSH's surface;
`destination_name` refuses a last path segment that would escape the download
root or hide inside it.
"""

import pytest

from repo_url import destination_name, validated_url

# One planted attempt per transport, and what makes each one an attack.
FILE_URL = "file:///etc/passwd"
EXT_URL = "ext::sh -c whoami"
SCP_URL = "git@github.com:owner/repo.git"
SSH_URL = "ssh://git@github.com/owner/repo.git"
PLAIN_HTTP_URL = "http://github.com/owner/repo"

HTTPS_URL = "https://github.com/owner/repo"


# --- What may be fetched at all --------------------------------------------

def test_an_https_url_is_returned_unchanged() -> None:
    """The one accepted transport passes through, so the refusals below mean something."""
    assert validated_url(HTTPS_URL) == HTTPS_URL


def test_surrounding_whitespace_is_stripped_before_the_check() -> None:
    """A URL pasted from a terminal keeps its spaces; the scheme check must not see them."""
    assert validated_url(f"  {HTTPS_URL}\n") == HTTPS_URL


def test_a_file_url_is_refused() -> None:
    """`file://` makes git read the local disk, which is not fetching a repository."""
    with pytest.raises(ValueError, match="only https:// URLs are fetched"):
        validated_url(FILE_URL)


def test_the_refusal_names_the_transport_it_refused() -> None:
    """A reader has to be told which scheme was rejected, not just that one was."""
    with pytest.raises(ValueError, match="'file'"):
        validated_url(FILE_URL)


def test_an_ext_url_is_refused() -> None:
    """`ext::` hands git a shell command to run, so it is the whole attack in one string."""
    with pytest.raises(ValueError, match="only https:// URLs are fetched"):
        validated_url(EXT_URL)


def test_an_scp_style_git_address_is_refused() -> None:
    """`git@host:path` has no scheme at all, so it must fail closed rather than pass."""
    with pytest.raises(ValueError, match="only https:// URLs are fetched"):
        validated_url(SCP_URL)


def test_an_ssh_url_is_refused() -> None:
    """SSH buys an agent and a known_hosts file for repositories that are public."""
    with pytest.raises(ValueError, match="only https:// URLs are fetched"):
        validated_url(SSH_URL)


def test_a_plain_http_url_is_refused() -> None:
    """http is not https: the fetch would be readable and rewritable in transit."""
    with pytest.raises(ValueError, match="only https:// URLs are fetched"):
        validated_url(PLAIN_HTTP_URL)


def test_an_empty_url_is_refused() -> None:
    """No URL is a mistake to report, never an empty fetch that quietly does nothing."""
    with pytest.raises(ValueError, match="no repository URL given"):
        validated_url("")


def test_a_whitespace_only_url_is_refused() -> None:
    """It strips to nothing, so it must reach the same refusal as the empty string."""
    with pytest.raises(ValueError, match="no repository URL given"):
        validated_url("   \t\n")


def test_an_https_url_with_no_host_is_refused() -> None:
    """The scheme alone is not a repository: with no host there is nothing to fetch."""
    with pytest.raises(ValueError, match="names no host"):
        validated_url("https:///owner/repo")


# --- What the fetched tree may be called ------------------------------------

def test_the_name_is_the_last_path_segment() -> None:
    """A plain URL names the directory the tree lands in."""
    assert destination_name("https://host/owner/repo") == "repo"


def test_a_dot_git_suffix_is_dropped_from_the_name() -> None:
    """`repo.git` and `repo` are the same repository, so they get the same directory."""
    assert destination_name("https://host/owner/repo.git") == "repo"


def test_a_trailing_slash_is_dropped_from_the_name() -> None:
    """A copied browser URL often ends in a slash; it must not yield an empty name."""
    assert destination_name("https://host/owner/repo/") == "repo"


def test_a_parent_directory_name_is_refused() -> None:
    """`..` as the derived name is the traversal this function exists to stop."""
    with pytest.raises(ValueError, match="not a single plain path segment"):
        destination_name("https://host/owner/..")


def test_a_name_holding_a_path_separator_is_refused() -> None:
    """A separator would make the name a path, so the tree could land anywhere."""
    with pytest.raises(ValueError, match="not a single plain path segment"):
        destination_name("https://host/owner/repo\\..\\corpus")


def test_a_hidden_name_is_refused() -> None:
    """A leading dot hides the tree from a listing, and `.git` would look like history."""
    with pytest.raises(ValueError, match="not a single plain path segment"):
        destination_name("https://host/owner/.hidden")


def test_a_url_with_no_path_is_refused() -> None:
    """A bare host names no repository, so there is no name to derive from it."""
    with pytest.raises(ValueError, match="not a single plain path segment"):
        destination_name("https://host")


def test_the_refusal_quotes_the_name_it_would_not_use() -> None:
    """The reader needs to see what was derived, or the message says nothing useful."""
    with pytest.raises(ValueError, match="'\\.\\.'"):
        destination_name("https://host/owner/..")
