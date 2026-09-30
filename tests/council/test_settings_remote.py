"""Guards on a server elsewhere: refused unless `AUDITOR_REMOTE_SERVER=yes`, and only then."""

from pathlib import Path

import pytest

from council.settings import SettingsError, load_settings, on_this_machine, remote_host

ABSENT = Path("/absent.env")
# A documentation address (RFC 5737): nothing here ever sends to it.
ELSEWHERE = "http://192.0.2.15:11434"
REFUSED_WITHOUT_KEY = (
    f"AUDITOR_SERVER_URL is '{ELSEWHERE}' (the environment), which is not this machine: "
    "a local member may only talk to 127.0.0.1, localhost; set AUDITOR_REMOTE_SERVER=yes "
    "to send the advisory text to that machine"
)


def remote(url: str = ELSEWHERE, opt_in: str = "yes") -> dict[str, str]:
    """Give an environment naming a server and the opt-in, as an operator would export them."""
    return {"AUDITOR_SERVER_URL": url, "AUDITOR_REMOTE_SERVER": opt_in}


def test_a_server_elsewhere_is_refused_without_the_key_naming_the_key():
    with pytest.raises(SettingsError) as refused:
        load_settings({"AUDITOR_SERVER_URL": ELSEWHERE}, ABSENT)
    assert str(refused.value) == REFUSED_WITHOUT_KEY


def test_with_the_key_a_server_elsewhere_is_the_server():
    chosen = load_settings(remote(), ABSENT)
    assert (chosen.server, chosen.remote_opted_in) == (ELSEWHERE, True)


def test_the_key_is_read_from_the_file_as_every_setting_is(tmp_path):
    written = tmp_path / ".env"
    written.write_text(f"AUDITOR_SERVER_URL={ELSEWHERE}\nAUDITOR_REMOTE_SERVER=yes\n", "utf-8")
    assert load_settings({}, written).server == ELSEWHERE


@pytest.mark.parametrize("value", ["true", "1", "Yes", "YES", "no", "y"])
def test_any_value_but_yes_is_refused_saying_only_yes_enables_it(value):
    with pytest.raises(SettingsError, match=r"only `yes` enables it") as refused:
        load_settings(remote(opt_in=value), ABSENT)
    assert f"AUDITOR_REMOTE_SERVER is {value!r} (the environment)" in str(refused.value)


def test_an_empty_key_is_the_key_unset_and_a_server_elsewhere_is_still_refused():
    with pytest.raises(SettingsError, match="set AUDITOR_REMOTE_SERVER=yes"):
        load_settings(remote(opt_in=""), ABSENT)
    assert load_settings({"AUDITOR_REMOTE_SERVER": ""}, ABSENT).remote_opted_in is False


def test_the_key_beside_this_machine_is_allowed_and_the_server_stays_local():
    chosen = load_settings(remote(url="http://localhost:11434"), ABSENT)
    assert chosen.remote_opted_in is True
    assert on_this_machine(chosen.server)
    assert remote_host(chosen.server) == ""


@pytest.mark.parametrize(
    "url", ["ftp://192.0.2.15:11434", "http://:11434", "192.0.2.15:11434", f"{ELSEWHERE}/v1"]
)
def test_the_key_does_not_let_an_address_that_is_not_one_through(url):
    with pytest.raises(SettingsError, match="give the server's address alone"):
        load_settings(remote(url=url), ABSENT)


@pytest.mark.parametrize(
    ("server", "host"),
    [
        ("http://127.0.0.1:11434", ""),
        ("http://localhost:11434", ""),
        ("http://[::1]:11434", ""),
        (ELSEWHERE, "192.0.2.15"),
        ("https://ollama.lan", "ollama.lan"),
    ],
)
def test_the_host_named_is_the_server_s_where_it_is_another_machine(server, host):
    assert remote_host(server) == host
    assert on_this_machine(server) is (host == "")


def test_an_address_naming_no_host_cannot_be_said_to_be_anywhere():
    with pytest.raises(SettingsError, match="names no host"):
        remote_host("http://:11434")
