"""What the model server logged while a pass ran: every request, and every model it loaded.

Ollama's journal is the one witness to other clients. A pass records its own
calls, and nothing it writes can show a request it did not make. An excerpt
keeps the two kinds of line that decide that -- each HTTP request and each
model load -- with the machine's name and the process id dropped, so it can be
kept beside the pass it vouches for.

**A pass's turns are found by their unloads.** Each item starts with an unload
request, which the server answers in milliseconds, and no model call in these
passes took under a quarter of a second. So the generate requests between one
unload and the next are one turn, and a turn of any other size than the metrics
asked holds a request this pass did not make.

The excerpt is read from `journalctl -u ollama -o short-iso`, whose lines open
with an ISO time, the host and the process.
"""

import re
from dataclasses import dataclass

JOURNAL_LINE = re.compile(r"^(\S+) \S+ \S+: (.*)$")
REQUEST_MESSAGE = re.compile(
    r'^\[GIN\] .+? \| (\d{3}) \|\s+([\d.]+)(µs|ms|s) \|\s+(\S+) \| (\w+)\s+"([^"]+)"$'
)
LOAD_MESSAGE = re.compile(r"^print_info: general\.name\s+= (.+)$")
SECONDS_PER_UNIT = {"µs": 1e-6, "ms": 1e-3, "s": 1.0}
REQUEST_KIND = "request"
LOAD_KIND = "load"
FIELD_SEPARATOR = "\t"
NOT_KEPT = ""
GENERATE_PATH = "/api/generate"
UNLOAD_BELOW_SECONDS = 0.01


@dataclass(frozen=True)
class Request:
    """One HTTP request the server answered: when, how, how long it took, and to what."""

    time: str
    status: str
    seconds: float
    client: str
    method: str
    path: str


@dataclass(frozen=True)
class Load:
    """One model the server loaded, and when, by the name its weights carry."""

    time: str
    model: str


def excerpt_lines(journal: str) -> list[str]:
    """Keep a journal's request and load lines as tab-separated fields, host and process dropped."""
    kept = [excerpt_line(line) for line in journal.splitlines()]
    return [line for line in kept if line != NOT_KEPT]


def excerpt_line(line: str) -> str:
    """Give one journal line as an excerpt line, or `NOT_KEPT` if it records neither kind."""
    prefixed = JOURNAL_LINE.match(line)
    if not prefixed:
        return NOT_KEPT
    time, message = prefixed.groups()
    request = REQUEST_MESSAGE.match(message)
    if request:
        status, value, unit, client, method, path = request.groups()
        seconds = f"{float(value) * SECONDS_PER_UNIT[unit]:.9f}"
        return FIELD_SEPARATOR.join([time, REQUEST_KIND, status, seconds, client, method, path])
    load = LOAD_MESSAGE.match(message)
    return FIELD_SEPARATOR.join([time, LOAD_KIND, load.group(1).strip()]) if load else NOT_KEPT


def read_excerpt(text: str) -> tuple[tuple[Request, ...], tuple[Load, ...]]:
    """Read an excerpt back into its requests and its loads, refusing a line of neither kind."""
    fields = [line.split(FIELD_SEPARATOR) for line in text.splitlines() if line]
    unknown = [one for one in fields if one[1] not in (REQUEST_KIND, LOAD_KIND)]
    if unknown:
        raise ValueError(f"{len(unknown)} excerpt lines are neither a request nor a load")
    requests = [one for one in fields if one[1] == REQUEST_KIND]
    loads = [one for one in fields if one[1] == LOAD_KIND]
    return tuple(request_of(one) for one in requests), tuple(Load(one[0], one[2]) for one in loads)


def request_of(fields: list[str]) -> Request:
    """Rebuild one request from its excerpt fields."""
    time, _, status, seconds, client, method, path = fields
    return Request(time, status, float(seconds), client, method, path)


def irregular_turns(requests: tuple[Request, ...], calls_per_turn: int) -> list[tuple[str, int]]:
    """Name each turn, by the time of its unload, that holds a number of calls other than asked."""
    generated = [one for one in requests if one.path == GENERATE_PATH]
    unloads = [index for index, one in enumerate(generated) if one.seconds < UNLOAD_BELOW_SECONDS]
    bounds = zip(unloads, [*unloads[1:], len(generated)])
    sizes = [(generated[start].time, end - start - 1) for start, end in bounds]
    return [(time, calls) for time, calls in sizes if calls != calls_per_turn]


def turn_count(requests: tuple[Request, ...]) -> int:
    """Count the turns, which is the unload requests among the generate requests."""
    return sum(one.path == GENERATE_PATH and one.seconds < UNLOAD_BELOW_SECONDS for one in requests)
