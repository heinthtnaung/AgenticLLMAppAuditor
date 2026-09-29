"""Guards on a council run's weights and server in the record: each named, or why not."""

import pytest

from report.model_identity import (
    MEMBER_ROLE,
    ModelDigest,
    OllamaVersion,
    UnknownDigest,
    UnknownOllamaVersion,
)

MODEL = "qwen2.5:7b-instruct"
DIGEST = "845dbda0ea48ed749caafd9e6037047aa19acfcfd82e704d7ca97d631a0b697e"


@pytest.mark.parametrize("model, digest", [("", DIGEST), (MODEL, "")], ids=["model", "digest"])
def test_a_digest_naming_no_model_or_no_weights_is_refused(model, digest):
    with pytest.raises(ValueError, match="must name the model and its digest"):
        ModelDigest(model, MEMBER_ROLE, digest)


@pytest.mark.parametrize("model, reason", [("", "unlisted"), (MODEL, "")], ids=["model", "reason"])
def test_an_unknown_digest_naming_no_model_or_no_reason_is_refused(model, reason):
    with pytest.raises(ValueError, match="must name the model and say why it is unknown"):
        UnknownDigest(model, MEMBER_ROLE, reason)


@pytest.mark.parametrize("version", ["", "   "], ids=["empty", "blank"])
def test_a_version_naming_nothing_is_refused(version):
    with pytest.raises(ValueError, match="must say what it is"):
        OllamaVersion(version)


def test_an_unknown_version_must_say_why():
    with pytest.raises(ValueError, match="must say why it is unknown"):
        UnknownOllamaVersion("")
