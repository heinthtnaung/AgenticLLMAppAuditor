"""Guards on the local models in the JSON record: each digest and the version, or why not."""

from dataclasses import replace

from report.json_local_models import local_models_of
from report.model_identity import (
    ESCALATION_ROLE,
    MEMBER_ROLE,
    ModelDigest,
    OllamaVersion,
    UnknownDigest,
    UnknownOllamaVersion,
)
from report.provenance import LocalModels

DIGEST = "845dbda0ea48ed749caafd9e6037047aa19acfcfd82e704d7ca97d631a0b697e"
NOT_LISTED = "the server lists no model named gemma4:latest"
ASKED = LocalModels(
    server="http://127.0.0.1:11434", context_tokens=8192, timeout_seconds=180.0,
    temperature=0, seed=11, think=False, order_check=True, escalation_model="gemma4:latest",
    ollama_version=OllamaVersion("0.34.3"),
    models=(
        ModelDigest("qwen2.5:7b-instruct", MEMBER_ROLE, DIGEST),
        UnknownDigest("gemma4:latest", ESCALATION_ROLE, NOT_LISTED),
    ),
)


def test_every_setting_is_kept_and_the_server_s_version_and_each_digest_follow():
    rendered = local_models_of(ASKED)
    assert list(rendered)[:8] == [
        "server", "context_tokens", "timeout_seconds", "temperature", "seed", "think",
        "order_check", "escalation_model",
    ]
    assert rendered["ollama_version"] == {"version": "0.34.3", "known": True}
    assert rendered["models"] == [
        {"model": "qwen2.5:7b-instruct", "role": "member", "digest": DIGEST, "known": True},
        {"model": "gemma4:latest", "role": "escalation", "known": False, "reason": NOT_LISTED},
    ]


def test_a_version_the_server_did_not_give_says_why_and_names_no_version():
    unknown = replace(ASKED, ollama_version=UnknownOllamaVersion("the server could not be reached"))
    assert local_models_of(unknown)["ollama_version"] == {
        "known": False, "reason": "the server could not be reached",
    }


def test_a_run_with_no_council_has_no_local_models():
    assert local_models_of(None) is None
