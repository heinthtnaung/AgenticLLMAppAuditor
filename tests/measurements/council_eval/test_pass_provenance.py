"""Guards on a pass's header: the pinning is the product's own, and the weights are the server's."""

import pytest

import council.ollama
import eval_samples as samples
from council.settings import Settings
from council_eval import pass_provenance
from council_eval.pass_provenance import file_digest, model_digest, pass_header
from council_eval.variants import BASELINE, LIBRARY_REVERSED, Variant

TAGS = {"models": [{"name": samples.MODEL, "digest": "sha256-abc"}]}


def serving(url: str):
    """Answer the two reads a header makes of the model server."""
    return TAGS if url.endswith("/api/tags") else {"version": "0.34.3"}


def header(tmp_path, variant: Variant = BASELINE):
    """Build the header of a pass over a one-line dataset, asked in one variant's words."""
    dataset = tmp_path / "dataset.json"
    dataset.write_text("{}\n")
    return pass_header(
        samples.MODEL, dataset, variant, get=serving, run=lambda command: "abc123\n"
    )


def test_the_pinning_recorded_is_what_the_product_sends(tmp_path):
    written = header(tmp_path)
    # Literals, as in the product's own tests: a header copying the constants
    # would agree with them whatever they held.
    assert (written["temperature"], written["seed"], written["num_ctx"]) == (0, 11, 8192)
    assert written["think"] is False
    assert written["prompt_version"] == "member-base-metric-3"


def test_the_window_and_timeout_recorded_are_the_operator_s_settings(tmp_path, monkeypatch):
    chosen = Settings("small:1b", "http://localhost:11434", 600.0, 16_384)
    monkeypatch.setattr(council.ollama, "current_settings", lambda: chosen)
    monkeypatch.setattr(pass_provenance, "current_settings", lambda: chosen)
    written = header(tmp_path)
    assert (written["num_ctx"], written["timeout_seconds"]) == (16_384, 600.0)


def test_the_weights_are_named_by_the_digest_the_server_holds(tmp_path):
    assert header(tmp_path)["digest"] == "sha256-abc"
    assert header(tmp_path)["ollama"] == "0.34.3"


def test_a_model_the_server_does_not_hold_is_refused():
    with pytest.raises(ValueError, match="the server holds no"):
        model_digest("missing:1b", TAGS)


def test_the_dataset_is_named_by_its_fingerprint(tmp_path):
    written = header(tmp_path)
    assert written["dataset_sha256"] == file_digest(tmp_path / "dataset.json")


def test_a_pass_asked_in_a_variant_s_words_records_the_variant_s_version(tmp_path):
    written = header(tmp_path, LIBRARY_REVERSED)
    assert written["prompt_version"] == "member-base-metric-3+library-1+reversed-1"
