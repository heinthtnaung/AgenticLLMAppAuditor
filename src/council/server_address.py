"""What a model server's address may be: http or https, a host and an optional port from 1 to 65535.

After them comes nothing but trailing slashes, or the generate endpoint an
earlier version of this project had operators write, which is read without it;
whitespace around the address is dropped. `council.settings` reads
`AUDITOR_SERVER_URL` and decides whether its host may be another machine; this
is the shape every address must have first, whatever `AUDITOR_REMOTE_SERVER` says.

**No username, password, query or fragment.** A username or password makes
`http.client` look up a name that is no host, and a query or a fragment rides
along to the same server with the path mangled; none reaches another host, but
an address that says more than where the server is reads as though it meant
something, so each is refused naming the part. One with an `@` is not quoted
back, in case it holds a password.

**A port is a whole number from 1 to 65535, or none.** `urlsplit` finds `:abc`,
`:11434;p` or `:99999` wrong only when the port is asked for, so it is asked for
here: otherwise the address would pass and fail at the first call, as a server
that could not be reached. Port 0 is a number, but it is reserved, and no server
can be reached at it.
"""

from urllib.parse import SplitResult, urlsplit

from council.env_file import SERVER, SettingsError

# This machine's Ollama: the setting's default, and the example every refusal gives.
DEFAULT_ADDRESS = "http://127.0.0.1:11434"
SERVER_SCHEMES = ("http", "https")
# What an earlier version of this project had operators write, endpoint and all.
OLD_ENDPOINT = "/api/generate"
# What an address may not carry, by its opening mark; "#" goes first, owning any "?" after it.
USERINFO_MARK = "@"
EXTRA_PARTS = (("#", "a fragment"), ("?", "a query"))
# A port `urlsplit` reads, but one that names no server.
UNREACHABLE_PORT = 0


def address_of(value: str, source: str) -> str:
    """Give the server's address, the old form with its endpoint accepted, refusing any other."""
    refuse_extra_parts(value, source)
    address = value.strip().rstrip("/").removesuffix(OLD_ENDPOINT)
    parts = urlsplit(address)
    if parts.scheme not in SERVER_SCHEMES or not parts.hostname or parts.path:
        raise SettingsError(
            f"{SERVER} is {value!r} ({source}); give the server's address alone, "
            f"as {DEFAULT_ADDRESS}"
        )
    refuse_unusable_port(value, source, parts)
    return address


def refuse_extra_parts(value: str, source: str) -> None:
    """Refuse an address carrying a username or password, a fragment or a query, naming which."""
    # Not quoted: what sits before an "@" may be a password.
    if USERINFO_MARK in value:
        raise SettingsError(
            f"{SERVER} ({source}) has an '{USERINFO_MARK}' in it, so it may carry a username or "
            f"password; give the server's address alone, as {DEFAULT_ADDRESS}. It is not "
            "quoted here in case it holds a secret"
        )
    carried = [part for mark, part in EXTRA_PARTS if mark in value]
    if carried:
        raise SettingsError(
            f"{SERVER} is {value!r} ({source}), which carries {carried[0]}; give the server's "
            f"address alone, as {DEFAULT_ADDRESS}"
        )


def refuse_unusable_port(value: str, source: str, parts: SplitResult) -> None:
    """Refuse a port no server can be reached at: anything but a whole number from 1 to 65535."""
    try:
        reachable = parts.port != UNREACHABLE_PORT
    except ValueError:
        reachable = False
    if reachable:
        return
    raise SettingsError(
        f"{SERVER} is {value!r} ({source}), whose port is not a whole number from 1 to 65535; "
        f"give the address with a port in that range, or none, as {DEFAULT_ADDRESS}"
    )
