"""The recorded explainer calls hold what the README says, and the summary re-derives from them.

What the replies say, and the outcome each call recorded when it was made, never change: the
file is the record. What the explainer's current reading makes of the replies is
`summary.txt`, re-derived here byte for byte with no model called. So a change to how a reply
is read turns only the last test red, and the summary is regenerated with that change.
"""

import sys
from itertools import chain, product
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "measurements"))

from council.explanation import NOT_A_DISPUTED_METRIC, REPEAT, UNVERIFIED_QUOTATION  # noqa: E402
from explainer_vulnscout.summary import metrics_as_written, recorded_calls, summary  # noqa: E402

RECORDS = ROOT / "measurements" / "explainer_vulnscout"
REPLIES = RECORDS / "replies.jsonl"
GEMMA = "gemma4:latest"
GLM = "glm-4.7-flash"
NANOSECONDS = 1e9
# No call but a model's first spent more than this loading it.
WARM_SECONDS = 0.01
HEADER, CALLS = recorded_calls(REPLIES)


def own(model: str, one_metric: bool) -> list[dict]:
    """Give one model's calls on the one-metric findings, or on the others."""
    return [one for one in CALLS if one["model"] == model and one["one_metric"] == one_metric]


def drops_of(call: dict) -> list[dict]:
    """Give the items one call recorded as not kept, each with its finding."""
    return [drop | {"advisory_id": call["advisory_id"]} for drop in call["outcome"]["dropped"]]


def dropped(calls: list[dict]) -> list[dict]:
    """Give every item the calls recorded as not kept, in the order the calls were made."""
    return list(chain.from_iterable(map(drops_of, calls)))


def test_the_header_names_the_weights_the_server_and_the_pinning():
    assert HEADER["ollama_version"] == "0.34.3"
    assert HEADER["digests"] == {
        GEMMA: "c6eb396dbd5992bbe3f5cdb947e8bbc0ee413d7c17e2beaae69f5d569cf982eb",
        GLM: "4475827791a269b02c8ec49b1c3bc1abb5846bacf3fae015b75d33986322d8f6",
    }
    pinned = (HEADER["prompt_version"], HEADER["temperature"], HEADER["think"])
    assert pinned == ("sources-differ-1", 0, False)
    assert (HEADER["context_tokens"], HEADER["seeds"], HEADER["timeout_seconds"]) == (
        8192, [11, 12], 180.0
    )


def test_the_draft_s_header_lacks_what_the_readme_states_in_its_place():
    stated = ("server", "remote_host", "dataset_sha256", "commit", "changes", "started")
    assert [name for name in stated if name in HEADER] == []


def test_each_model_was_asked_under_each_seed_about_each_finding_and_answered_whole():
    asked = [(one["model"], one["seed"], one["advisory_id"]) for one in CALLS]
    assert asked == list(product((GEMMA, GLM), (11, 12), HEADER["findings"]))
    assert {one["envelope"]["done_reason"] for one in CALLS} == {"stop"}


def test_gemma_named_the_one_disputed_metric_in_words_and_its_code_otherwise():
    named = set(chain.from_iterable(map(metrics_as_written, own(GEMMA, one_metric=True))))
    assert named == {"'Availability'", "'Availability (A)'", "'AC (Attack Complexity)'"}
    coded = [metrics_as_written(one) for one in own(GEMMA, one_metric=False)]
    assert coded == [["'C'", "'I'", "'A'"], ["'PR'", "'I'", "'A'"]] * 2


def test_glm_wrote_every_metric_as_its_code():
    calls = [one for one in CALLS if one["model"] == GLM]
    written = set(chain.from_iterable(map(metrics_as_written, calls)))
    assert written == {"'A'", "'AC'", "'C'", "'I'", "'PR'"}


def test_as_recorded_gemma_kept_nothing_on_a_one_metric_finding_though_every_quotation_verified():
    calls = own(GEMMA, one_metric=True)
    assert [one["outcome"]["explained"] for one in calls] == [False] * 6
    drops = [(one["reason"], one["quotation_found"]) for one in dropped(calls)]
    assert drops == [(NOT_A_DISPUTED_METRIC, True)] * 6


def test_as_recorded_glm_explained_every_finding_dropping_only_a_repeated_ac_item():
    calls = [one for one in CALLS if one["model"] == GLM]
    assert all(one["outcome"]["explained"] for one in calls)
    drops = [(one["advisory_id"], one["reason"], one["quotation_found"]) for one in dropped(calls)]
    assert drops == [("CVE-2026-4800", REPEAT, True)] * 2


def test_as_recorded_no_item_was_dropped_for_its_quotation():
    assert UNVERIFIED_QUOTATION not in {one["reason"] for one in dropped(CALLS)}


def test_no_call_came_near_the_timeout():
    assert round(max(one["seconds"] for one in CALLS), 1) == 37.3 < HEADER["timeout_seconds"]


def test_only_each_model_s_first_call_loaded_it():
    loads = [one["envelope"]["load_duration"] / NANOSECONDS for one in CALLS]
    first = [index in (0, 10) for index in range(20)]
    assert [seconds > WARM_SECONDS for seconds in loads] == first
    assert (round(loads[0], 1), round(loads[10], 1)) == (12.7, 23.4)


def test_the_seed_changed_the_reply_on_nine_of_the_ten_pairs():
    by_call = {(one["model"], one["advisory_id"], one["seed"]): one["envelope"]["response"]
               for one in CALLS}
    same = [key[:2] for key in by_call if key[2] == 11 and by_call[key] == by_call[key[:2] + (12,)]]
    assert same == [(GLM, "CVE-2026-13149")]


def test_the_saved_summary_re_derives_byte_for_byte_from_the_replies():
    saved = (RECORDS / "summary.txt").read_text(encoding="utf-8")
    assert summary(REPLIES) == saved, (
        "the explainer now reads these replies otherwise: regenerate summary.txt with the "
        "command in its README, and update the README's scored block with it"
    )
