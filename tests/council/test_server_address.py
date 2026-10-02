"""Guards on what a server's address may carry: a scheme, a host and a port, and nothing else."""

from pathlib import Path

import pytest

from council.settings import SettingsError, load_settings

ABSENT = Path("/absent.env")
HERE = "http://127.0.0.1:11434"
# A documentation address (RFC 5737): nothing here ever sends to it.
ELSEWHERE = "http://192.0.2.15:11434"
SECRET = "hunter2"
USERINFO = "may carry a username or password"
CARRIED = [
    ("http://192.0.2.15@127.0.0.1:11434", USERINFO),
    (f"http://:{SECRET}@127.0.0.1:11434", USERINFO),
    (f"{HERE}?x=1", "carries a query"),
    (f"{HERE}#frag", "carries a fragment"),
]
FOUR = ["username", "password", "query", "fragment"]


def env_file(tmp_path: Path, value: str) -> Path:
    """Write a settings file naming this server, as an operator would."""
    path = tmp_path / ".env"
    path.write_text(f"AUDITOR_SERVER_URL={value}\n", encoding="utf-8")
    return path


@pytest.mark.parametrize(("value", "said"), CARRIED, ids=FOUR)
def test_each_part_is_refused_from_the_environment_naming_the_setting(value, said):
    with pytest.raises(SettingsError, match=said) as refused:
        load_settings({"AUDITOR_SERVER_URL": value}, ABSENT)
    assert str(refused.value).startswith("AUDITOR_SERVER_URL ")
    assert "(the environment)" in str(refused.value)


@pytest.mark.parametrize(("value", "said"), CARRIED, ids=FOUR)
def test_each_part_is_refused_from_the_file_naming_its_line(tmp_path, value, said):
    written = env_file(tmp_path, value)
    with pytest.raises(SettingsError, match=said) as refused:
        load_settings({}, written)
    assert f"{written} line 1" in str(refused.value)


@pytest.mark.parametrize(
    "value",
    ["http://ollama@192.0.2.15:11434", f"http://:{SECRET}@192.0.2.15:11434",
     f"{ELSEWHERE}?x=1", f"{ELSEWHERE}#frag"],
    ids=FOUR,
)
def test_the_opt_in_lets_no_part_through_either(value):
    environment = {"AUDITOR_SERVER_URL": value, "AUDITOR_REMOTE_SERVER": "yes"}
    with pytest.raises(SettingsError, match="give the server's address alone"):
        load_settings(environment, ABSENT)


def test_an_address_that_may_hold_a_password_is_never_quoted():
    with pytest.raises(SettingsError) as refused:
        load_settings({"AUDITOR_SERVER_URL": f"http://ollama:{SECRET}@127.0.0.1:11434"}, ABSENT)
    assert str(refused.value) == (
        "AUDITOR_SERVER_URL (the environment) has an '@' in it, so it may carry a username or "
        "password; give the server's address alone, as http://127.0.0.1:11434. It is not "
        "quoted here in case it holds a secret"
    )


def test_a_query_is_refused_quoting_the_address_and_naming_the_part():
    with pytest.raises(SettingsError) as refused:
        load_settings({"AUDITOR_SERVER_URL": f"{HERE}?x=1"}, ABSENT)
    assert str(refused.value) == (
        "AUDITOR_SERVER_URL is 'http://127.0.0.1:11434?x=1' (the environment), which carries "
        "a query; give the server's address alone, as http://127.0.0.1:11434"
    )


@pytest.mark.parametrize(
    ("value", "said"),
    [
        ("http://@127.0.0.1:11434", USERINFO),
        (f"{HERE}?", "carries a query"),
        (f"{HERE}#", "carries a fragment"),
        (f"{HERE}#frag?x=1", "carries a fragment"),
        (f"{HERE}/api/generate?x=1", "carries a query"),
    ],
    ids=["empty-userinfo", "empty-query", "empty-fragment", "query-inside-fragment", "old-form"],
)
def test_a_mark_with_nothing_after_it_or_after_the_old_endpoint_is_refused_all_the_same(
    value, said
):
    with pytest.raises(SettingsError, match=said):
        load_settings({"AUDITOR_SERVER_URL": value}, ABSENT)


@pytest.mark.parametrize(
    "value",
    ["ftp://127.0.0.1:11434", "127.0.0.1:11434", "http://:11434", f"{HERE}/v1"],
    ids=["another-scheme", "no-scheme", "no-host", "a-path"],
)
def test_an_address_without_its_scheme_and_host_alone_is_refused_quoting_it(value):
    with pytest.raises(SettingsError) as refused:
        load_settings({"AUDITOR_SERVER_URL": value}, ABSENT)
    assert str(refused.value) == (
        f"AUDITOR_SERVER_URL is {value!r} (the environment); give the server's address alone, "
        "as http://127.0.0.1:11434"
    )


@pytest.mark.parametrize(
    ("given", "read"),
    [
        (HERE, HERE),
        (f"{HERE}/", HERE),
        (f"{HERE}/api/generate", HERE),
        ("https://[::1]:443", "https://[::1]:443"),
    ],
    ids=["plain", "trailing-slash", "old-endpoint-form", "https-ipv6"],
)
def test_an_address_carrying_nothing_more_is_still_read(given, read):
    assert load_settings({"AUDITOR_SERVER_URL": given}, ABSENT).server == read


def test_with_the_opt_in_a_plain_address_elsewhere_is_still_read():
    environment = {"AUDITOR_SERVER_URL": ELSEWHERE, "AUDITOR_REMOTE_SERVER": "yes"}
    assert load_settings(environment, ABSENT).server == ELSEWHERE
