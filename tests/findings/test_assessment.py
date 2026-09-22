"""Guards on reading one source's published vector: scored, or refused with a reason."""

import pytest

from findings.assessment import SourceScore, UnreadableSource, read_source, read_sources
from finding_samples import (
    GHSA_SCORE,
    GHSA_VECTOR,
    HARMLESS_SCORE,
    HARMLESS_VECTOR,
    REDHAT_SCORE,
    REDHAT_VECTOR,
    VERSION_2_VECTOR,
    VERSION_4_VECTOR,
    advisory,
)


def test_a_readable_vector_is_scored_and_attributed():
    read = read_source("ghsa", GHSA_VECTOR)
    assert isinstance(read, SourceScore)
    assert read.source == "ghsa"
    assert read.base_score == GHSA_SCORE
    assert read.parsed_vector.version == "3.0"


def test_the_published_text_is_quoted_as_published():
    # The record has to re-derive the published score, so the source's own
    # spelling is kept even where the parsed vector canonicalises it.
    shuffled = "CVSS:3.1/A:N/C:N/I:N/S:U/UI:R/PR:H/AC:H/AV:L"
    read = read_source("nvd", shuffled)
    assert read.vector == shuffled
    assert str(read.parsed_vector) == HARMLESS_VECTOR


@pytest.mark.parametrize(
    ("vector_text", "expected"),
    [(VERSION_2_VECTOR, "CVSS v2"), (VERSION_4_VECTOR, "CVSS v4.0")],
    ids=["version 2", "version 4.0"],
)
def test_a_refused_vector_is_recorded_unscored_with_the_reason(vector_text, expected):
    read = read_source("nvd", vector_text)
    assert isinstance(read, UnreadableSource)
    assert read.source == "nvd"
    assert read.vector == vector_text
    assert expected in read.refusal


@pytest.mark.parametrize(
    "vector_text",
    ["", "CVSS:3.1/AV:N", "CVSS:3.1/AV:Z/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H", "nonsense"],
    ids=["empty", "incomplete", "illegal value", "not a vector"],
)
def test_an_unreadable_vector_never_raises_out_of_the_reader(vector_text):
    # An audit that fell over on one malformed published vector would report
    # nothing at all, which is worse than reporting that one source unread.
    assert isinstance(read_source("nvd", vector_text), UnreadableSource)


def test_a_vector_worth_zero_is_scored_not_refused():
    read = read_source("nvd", HARMLESS_VECTOR)
    assert isinstance(read, SourceScore)
    assert read.base_score == HARMLESS_SCORE


def test_every_source_is_read_in_source_name_order():
    read = read_sources(advisory(vectors={"redhat": REDHAT_VECTOR, "ghsa": GHSA_VECTOR}))
    assert [item.source for item in read] == ["ghsa", "redhat"]
    assert [item.base_score for item in read] == [GHSA_SCORE, REDHAT_SCORE]


def test_an_advisory_nobody_published_a_vector_for_reads_as_nothing():
    assert read_sources(advisory(vectors={})) == []


def test_no_source_is_preferred_when_they_disagree():
    # Red Hat and GHSA are read the same way and kept side by side; nothing here
    # decides between them.
    read = read_sources(advisory(vectors={"ghsa": GHSA_VECTOR, "redhat": REDHAT_VECTOR}))
    assert len(read) == 2
    assert {item.source for item in read} == {"ghsa", "redhat"}
