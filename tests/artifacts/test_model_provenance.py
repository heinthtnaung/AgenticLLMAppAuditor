"""Schema version 3's provenance block: the digest, and the settings a used run must record.

`model_provenance` is shared by `findings.json` and `remediation.json`, so two
files cannot grow two shapes for one fact. Version 3 added `model_digest` and
tightened one invariant: a `used` run must record the settings it sent, because
a run nobody can repeat is not evidence of anything.
"""

import pytest

from artifacts.finding import SCHEMA_VERSION
from artifacts.findings_document import (
    MODEL_DISABLED,
    MODEL_UNAVAILABLE,
    MODEL_USED,
    model_provenance,
    model_run,
)

MODEL = "qwen2.5-coder:7b-instruct"
DECODE_SETTINGS = {"temperature": 0, "seed": 0}
# Bare hex: `model_digest` passes through what /api/tags reports, unprefixed.
DIGEST = "1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef"


def test_the_findings_schema_is_at_version_seven() -> None:
    """Version 7 added the top-level `checks_narrowed`.

    The literal is the tripwire, deliberately: every artifact already on disk
    is unreadable to `report.py` and `vex.py` at a new version, so a bump has
    to be a decision someone made rather than one that happened.
    """
    assert SCHEMA_VERSION == 7


def test_a_used_run_records_the_digest_it_was_given() -> None:
    """A tag is mutable, so the build is recorded beside the name."""
    assert model_provenance(MODEL_USED, MODEL, DECODE_SETTINGS, DIGEST)["model_digest"] == DIGEST


def test_a_used_run_with_no_digest_recorded_is_accepted() -> None:
    """Null is an honest "not recorded"; refusing it would force a wrong value."""
    run = model_provenance(MODEL_USED, MODEL, DECODE_SETTINGS)
    assert run["model_digest"] is None
    assert run["status"] == MODEL_USED


@pytest.mark.parametrize("status", [MODEL_DISABLED, MODEL_UNAVAILABLE, MODEL_USED])
def test_every_provenance_block_carries_the_digest_field(status: str) -> None:
    """A reader reads one shape, so a missing key never has to be told from a null."""
    named = (MODEL, DECODE_SETTINGS) if status == MODEL_USED else (None, None)
    assert "model_digest" in model_provenance(status, *named)


def test_a_used_run_with_no_settings_is_refused() -> None:
    """Repeatable prose is the whole case for exempting it from byte-identity."""
    with pytest.raises(ValueError, match="must record the decode settings"):
        model_provenance(MODEL_USED, MODEL)


def test_a_used_run_with_empty_settings_is_refused() -> None:
    """An empty dict records nothing, so it is refused exactly as omitting it is."""
    with pytest.raises(ValueError, match="must record the decode settings"):
        model_provenance(MODEL_USED, MODEL, {})


def test_a_run_that_wrote_nothing_needs_no_settings() -> None:
    """There is nothing to repeat, so the block records an empty dict rather than refusing."""
    assert model_provenance(MODEL_DISABLED)["model_settings"] == {}


def test_the_settings_are_copied_rather_than_referenced() -> None:
    """A caller mutating its dict afterwards must not rewrite the artifact."""
    settings = dict(DECODE_SETTINGS)
    run = model_provenance(MODEL_USED, MODEL, settings)
    settings["seed"] = 99
    assert run["model_settings"]["seed"] == 0


def test_the_findings_documents_run_block_is_the_provenance_block_plus_a_ranking() -> None:
    """One shape for the shared fact, and one field only findings.json has."""
    shared = model_provenance(MODEL_USED, MODEL, DECODE_SETTINGS, DIGEST)
    document = model_run(MODEL_USED, MODEL, DECODE_SETTINGS, None, DIGEST)
    assert set(document) == set(shared) | {"ranking"}
    assert {key: document[key] for key in shared} == shared


def test_the_findings_documents_run_block_enforces_the_same_settings_rule() -> None:
    """The tightened invariant reaches findings.json, not only the shared helper."""
    with pytest.raises(ValueError, match="must record the decode settings"):
        model_run(MODEL_USED, MODEL)
