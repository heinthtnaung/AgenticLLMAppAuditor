"""Guards on reading which weights and which server a council run uses: named, or why not."""

import pytest

from cli.model_identity import READ_TIMEOUT_SECONDS, local_identities, tagged
from council.settings import current_settings
from council.transport import ModelUnavailable
from report.model_identity import (
    ESCALATION_ROLE,
    MEMBER_ROLE,
    ModelDigest,
    OllamaVersion,
    UnknownDigest,
    UnknownOllamaVersion,
)

HOST = "http://127.0.0.1:11434"
QWEN = "845dbda0ea48ed749caafd9e6037047aa19acfcfd82e704d7ca97d631a0b697e"
GEMMA = "c6eb396dbd5992bbe3f5cdb947e8bbc0ee413d7c17e2beaae69f5d569cf982eb"
LLAMA = "a80c4f17acd55265feec403c7aef86be0c25983ab279d83f3bcd3abbcb5b8b72"
TAGS = {"models": [
    {"name": "qwen2.5:7b-instruct", "digest": QWEN},
    {"name": "gemma4:latest", "digest": GEMMA},
    {"name": "llama3.2:latest", "digest": LLAMA},
    {"name": "broken:latest"},
    {"name": "blank:latest", "digest": ""},
    {"digest": QWEN},
    "junk",
]}


def serving(tags=TAGS, version=None, asked=None):
    """Build a fake server answering the two reads, noting each URL and timeout asked."""
    asked = [] if asked is None else asked

    def get(url, timeout):
        """Answer one read as the fake server holds it."""
        asked.append((url, timeout))
        if url.endswith("/api/version"):
            return {"version": "0.34.3"} if version is None else version
        return tags

    return get


def failing(fault: Exception):
    """Build a fake server whose every read fails with this one fault."""

    def get(url, timeout):
        """Fail as the server fails."""
        raise fault

    return get


def test_each_model_the_run_asks_is_named_by_its_digest_and_the_server_by_its_version():
    version, models = local_identities(("qwen2.5:7b-instruct",), "gemma4:latest", HOST, serving())
    assert version == OllamaVersion("0.34.3")
    assert models == (
        ModelDigest("qwen2.5:7b-instruct", MEMBER_ROLE, QWEN),
        ModelDigest("gemma4:latest", ESCALATION_ROLE, GEMMA),
    )


@pytest.mark.parametrize("given", [" 0.34.3 ", "0.34.3\n"], ids=["spaced", "newline"])
def test_a_version_is_recorded_without_the_space_around_it(given):
    version, _ = local_identities((), None, HOST, serving(version={"version": given}))
    assert version == OllamaVersion("0.34.3")


def test_the_two_reads_go_to_the_host_handed_in_and_no_more():
    asked, host = [], "http://localhost:11500"
    local_identities(("qwen2.5:7b-instruct", "gemma4:latest"), None, host, serving(asked=asked))
    assert [url for url, _ in asked] == [f"{host}/api/tags", f"{host}/api/version"]


def test_both_reads_wait_their_own_short_timeout_not_the_generation_timeout():
    asked = []
    local_identities(("qwen2.5:7b-instruct",), None, HOST, serving(asked=asked))
    assert [timeout for _, timeout in asked] == [READ_TIMEOUT_SECONDS, READ_TIMEOUT_SECONDS]
    assert READ_TIMEOUT_SECONDS < current_settings().timeout_seconds


def test_a_name_without_a_tag_is_found_under_the_tag_ollama_assumes():
    _, (model,) = local_identities(("llama3.2",), None, HOST, serving())
    assert model == ModelDigest("llama3.2", MEMBER_ROLE, LLAMA)


@pytest.mark.parametrize(
    ("name", "listed_as"),
    [
        ("llama3.2", "llama3.2:latest"),
        ("qwen2.5:7b-instruct", "qwen2.5:7b-instruct"),
        ("myregistry:5000/model", "myregistry:5000/model:latest"),
        ("myregistry:5000/model:1b", "myregistry:5000/model:1b"),
        ("library/model", "library/model:latest"),
        ("myregistry:5000/library/model", "myregistry:5000/library/model:latest"),
    ],
    ids=[
        "plain", "tagged", "registry-with-port", "registry-with-port-and-tag", "namespaced",
        "registry-with-port-and-namespace",
    ],
)
def test_a_tag_is_read_only_from_the_part_of_the_name_after_the_last_slash(name, listed_as):
    assert tagged(name) == listed_as


def test_a_registry_name_with_a_port_is_found_under_the_tag_ollama_assumes():
    tags = {"models": [{"name": "myregistry:5000/model:latest", "digest": QWEN}]}
    _, (model,) = local_identities(("myregistry:5000/model",), None, HOST, serving(tags=tags))
    assert model == ModelDigest("myregistry:5000/model", MEMBER_ROLE, QWEN)


def test_a_model_the_server_does_not_list_is_recorded_as_unknown_and_why():
    _, (model,) = local_identities(("absent:1b",), None, HOST, serving())
    assert model == UnknownDigest(
        "absent:1b", MEMBER_ROLE, "the server lists no model named absent:1b"
    )


@pytest.mark.parametrize("name", ["broken", "blank"], ids=["no-digest", "empty-digest"])
def test_a_model_the_server_lists_without_a_digest_is_recorded_as_just_that(name):
    _, (model,) = local_identities((name,), None, HOST, serving())
    assert model == UnknownDigest(name, MEMBER_ROLE, f"the server lists {name} without a digest")


def breaking_on(path: str):
    """Build a fake server answering every read but the one at `path`, which fails as a bug does."""
    answered = serving()

    def get(url, timeout):
        """Answer one read, or fail on the one path."""
        if url.endswith(path):
            raise RuntimeError("a bug, not the server")
        return answered(url, timeout)

    return get


@pytest.mark.parametrize("path", ["/api/tags", "/api/version"], ids=["tags", "version"])
def test_a_fault_that_is_not_the_server_s_stops_the_run_rather_than_reading_as_unknown(path):
    with pytest.raises(RuntimeError, match="a bug, not the server"):
        local_identities(("qwen2.5:7b-instruct",), None, HOST, breaking_on(path))


def unreachable(url, timeout):
    """Fail as a server that is not there fails, naming the URL as `council.transport` does."""
    raise ModelUnavailable(f"{url} could not be reached: Connection refused")


def test_a_server_that_cannot_be_reached_is_named_once_per_reason_and_stops_nothing():
    version, (model,) = local_identities(("qwen2.5:7b-instruct",), None, HOST, unreachable)
    assert version == UnknownOllamaVersion(
        f"no version could be read: {HOST}/api/version could not be reached: Connection refused"
    )
    assert model == UnknownDigest("qwen2.5:7b-instruct", MEMBER_ROLE, (
        f"no list of models could be read: {HOST}/api/tags could not be reached: Connection refused"
    ))


def test_a_reply_that_cannot_be_decoded_is_recorded_as_unread_and_stops_nothing():
    # A body that is not UTF-8 reaches the caller as a ValueError, not ModelUnavailable.
    fault = UnicodeDecodeError("utf-8", b"\xff", 0, 1, "invalid start byte")
    version, (model,) = local_identities(("qwen2.5:7b-instruct",), None, HOST, failing(fault))
    assert version == UnknownOllamaVersion(f"no version could be read: {fault}")
    assert model.reason == f"no list of models could be read: {fault}"


@pytest.mark.parametrize(
    "reply",
    [{"release": "0.34.3"}, {"version": "   "}, {"version": 34}, ["0.34.3"]],
    ids=["no-version", "blank", "not-text", "not-an-object"],
)
def test_a_version_reply_of_the_wrong_shape_is_unknown_rather_than_guessed_at(reply):
    version, _ = local_identities((), None, HOST, serving(version=reply))
    assert version == UnknownOllamaVersion(f"{HOST}/api/version answered without a version")


@pytest.mark.parametrize(
    "reply", [{"models": "all of them"}, {"model": []}, ["qwen2.5:7b-instruct"]],
    ids=["not-a-list", "no-models", "not-an-object"],
)
def test_a_list_reply_of_the_wrong_shape_is_unknown_rather_than_guessed_at(reply):
    _, (model,) = local_identities(("qwen2.5:7b-instruct",), None, HOST, serving(tags=reply))
    assert model.reason == f"{HOST}/api/tags answered without a list of models"
