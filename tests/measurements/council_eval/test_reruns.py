"""Guards on comparing two passes: byte for byte, and every mid-item reload named."""

import pytest

import eval_samples as samples
from council_eval.recording import CallRecord
from council_eval.replies import Replies
from council_eval.reruns import compare_passes

LOADED = {"response": "{}", "load_duration": 4_000_000_000}
WARM = {"response": "{}", "load_duration": 2_000_000}


def one_pass(envelopes: dict, model: str = samples.MODEL) -> Replies:
    """Build a pass of one model over one item, with an envelope per metric given."""
    calls = {
        (samples.KEY, model, metric): CallRecord(metric, f"sent-{metric}", envelope, 0.5)
        for metric, envelope in envelopes.items()
    }
    return Replies(headers=({"model": model},), calls=calls)


def test_two_passes_with_the_same_replies_are_identical_throughout():
    same = {"AV": LOADED, "AC": WARM}
    found = compare_passes(one_pass(same), one_pass(same))
    assert (found.calls, found.same_request, found.identical, found.differing) == (2, 2, 2, ())


def test_a_reply_that_moved_is_named():
    moved = {"AV": LOADED, "AC": {"response": '{"value": "H"}', "load_duration": 0}}
    found = compare_passes(one_pass({"AV": LOADED, "AC": WARM}), one_pass(moved))
    assert found.differing == ((samples.KEY, samples.MODEL, "AC"),)
    assert found.identical == 1


def test_a_call_after_an_item_s_first_that_spent_time_loading_is_named():
    reloaded = {"AV": LOADED, "AC": LOADED}
    found = compare_passes(one_pass(reloaded), one_pass({"AV": LOADED, "AC": WARM}))
    assert found.reloaded_first == ((samples.KEY, samples.MODEL, "AC"),)
    assert found.reloaded_second == ()


def test_a_call_that_got_nothing_back_is_unanswered_and_not_a_difference():
    found = compare_passes(one_pass({"AV": LOADED}), one_pass({"AV": None}))
    assert (found.unanswered, found.identical, found.differing) == (1, 0, ())


def test_passes_of_two_models_are_refused():
    with pytest.raises(ValueError, match="two passes of one model"):
        compare_passes(one_pass({"AV": LOADED}), one_pass({"AV": LOADED}, samples.OTHER_MODEL))


def test_passes_that_recorded_different_calls_are_refused():
    with pytest.raises(ValueError, match="did not record the same calls"):
        compare_passes(one_pass({"AV": LOADED}), one_pass({"AV": LOADED, "AC": WARM}))
