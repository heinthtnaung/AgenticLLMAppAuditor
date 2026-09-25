"""Guards on reading the server's journal: requests and loads kept, host dropped, turns found."""

import pytest

import eval_samples  # noqa: F401  (puts the evaluation package on the path)
from council_eval.server_log import (
    Load,
    Request,
    excerpt_lines,
    irregular_turns,
    read_excerpt,
    turn_count,
)

PREFIX = "2026-09-24T18:56:32+08:00 SOME-HOST ollama[2107]:"
GIN = f"{PREFIX} [GIN] 2026/09/24 - 18:56:32 | 200 |"
GENERATE = f'{GIN}  4.534269843s |       127.0.0.1 | POST     "/api/generate"'
UNLOAD = f'{GIN}     829.381µs |       127.0.0.1 | POST     "/api/generate"'
LOAD = f"{PREFIX} print_info: general.name          = Qwen2.5 7B Instruct"
LOADER = f"{PREFIX} llama_model_loader: - kv   2:   general.name str   = Qwen2.5 7B Instruct"
KEPT_GENERATE = "\t".join([
    "2026-09-24T18:56:32+08:00", "request", "200", "4.534269843",
    "127.0.0.1", "POST", "/api/generate",
])


def test_a_request_is_kept_with_its_duration_in_seconds_and_without_the_host():
    assert excerpt_lines(GENERATE) == [KEPT_GENERATE]


def test_a_duration_in_microseconds_is_read_in_seconds():
    (request,), _ = read_excerpt("\n".join(excerpt_lines(UNLOAD)))
    assert request.seconds == pytest.approx(0.000829381)


def test_a_load_is_kept_once_by_the_name_its_weights_carry():
    kept = excerpt_lines("\n".join([LOADER, LOAD]))
    assert kept == ["2026-09-24T18:56:32+08:00\tload\tQwen2.5 7B Instruct"]


def test_other_journal_lines_are_left_out():
    other = f"{PREFIX} load_tensors: offloaded 29/29 layers to GPU\nnot a journal line"
    assert excerpt_lines(other) == []


def test_an_excerpt_reads_back_into_its_requests_and_loads():
    requests, loads = read_excerpt("\n".join(excerpt_lines("\n".join([LOAD, GENERATE]))))
    assert loads == (Load("2026-09-24T18:56:32+08:00", "Qwen2.5 7B Instruct"),)
    assert requests[0].path == "/api/generate"


def test_an_excerpt_line_of_neither_kind_is_refused():
    with pytest.raises(ValueError, match="neither a request nor a load"):
        read_excerpt("2026\tsomething\telse")


def asked(*seconds: float) -> tuple[Request, ...]:
    """Build generate requests taking the given times, in order."""
    return tuple(generate_request(f"t{index}", one) for index, one in enumerate(seconds))


def generate_request(time: str, seconds: float) -> Request:
    """Build one generate request from loopback."""
    return Request(time, "200", seconds, "127.0.0.1", "POST", "/api/generate")


def test_turns_are_counted_by_their_unloads():
    assert turn_count(asked(0.001, 0.5, 0.5, 0.001, 0.5, 0.5)) == 2


def test_a_turn_holding_more_calls_than_were_asked_is_named_by_its_unload():
    requests = asked(0.001, 0.5, 0.5, 0.001, 0.5, 0.5, 0.5)
    assert irregular_turns(requests, calls_per_turn=2) == [("t3", 3)]


def test_requests_to_other_paths_are_not_calls():
    requests = (*asked(0.001, 0.5), Request("t9", "200", 0.001, "127.0.0.1", "GET", "/api/ps"))
    assert irregular_turns(requests, calls_per_turn=1) == []
