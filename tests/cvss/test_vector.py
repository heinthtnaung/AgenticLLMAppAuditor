"""Guards on parsing, refusing, canonicalising and deriving a CVSS Base vector."""

import pytest

from cvss.vector import CvssVector, differing_metrics, parse

CANONICAL = "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H"

# CVE-2025-37164, scored by two sources that differ in one metric: Scope.
CNA_VECTOR = "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:C/C:H/I:H/A:H"
TENABLE_VECTOR = "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H"


def test_a_canonical_vector_parses_to_its_eight_metrics():
    vector = parse(CANONICAL)
    assert vector.version == "3.1"
    assert vector.value("AV") == "N"
    assert vector.value("S") == "U"
    assert vector.value("A") == "H"


def test_a_version_3_0_vector_is_accepted_and_keeps_its_version():
    vector = parse("CVSS:3.0/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H")
    assert vector.version == "3.0"
    assert str(vector).startswith("CVSS:3.0/")


def test_the_declared_version_separates_two_otherwise_identical_vectors():
    # The Base equations are identical, but a published v3.0 score may differ in
    # the last decimal, so the two records must not collapse into one.
    assert parse("CVSS:3.0/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H") != parse(CANONICAL)


def test_a_version_4_0_vector_is_refused_by_name():
    with pytest.raises(ValueError, match="CVSS v4.0 is not supported"):
        parse("CVSS:4.0/AV:N/AC:L/AT:N/PR:N/UI:N/VC:H/VI:H/VA:H/SC:N/SI:N/SA:N")


def test_a_version_2_vector_is_refused_by_name():
    with pytest.raises(ValueError, match="CVSS v2 vector"):
        parse("AV:N/AC:L/Au:N/C:P/I:P/A:P")


def test_a_vector_without_a_version_prefix_is_refused():
    with pytest.raises(ValueError, match="must start with"):
        parse("AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H")


def test_an_unknown_version_is_refused():
    with pytest.raises(ValueError, match="Unknown CVSS version '3.2'"):
        parse("CVSS:3.2/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H")


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("CVSS:3.1/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H", "Attack Vector (AV)"),
        ("CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H", "Availability (A)"),
        ("CVSS:3.1/AV:N/AC:L/PR:N/UI:N/C:H/I:H/A:H", "Scope (S)"),
    ],
)
def test_a_missing_metric_is_refused_and_named_in_words(text, expected):
    # Never defaulted: a defaulted metric invents an assessment nobody made.
    with pytest.raises(ValueError, match="needs all eight metrics") as refusal:
        parse(text)
    assert expected in str(refusal.value)


def test_several_missing_metrics_are_all_named_in_specification_order():
    with pytest.raises(ValueError) as refusal:
        parse("CVSS:3.1/AC:L/PR:N/UI:N/S:U/C:H")
    message = str(refusal.value)
    assert "Attack Vector (AV), Integrity (I), Availability (A)" in message


def test_an_unknown_metric_is_refused():
    with pytest.raises(ValueError, match="Unknown metric 'XX'"):
        parse("CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H/XX:N")


def test_an_illegal_value_is_refused_and_the_metric_named_in_words():
    with pytest.raises(ValueError, match="not a value of Attack Vector") as refusal:
        parse("CVSS:3.1/AV:Z/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H")
    assert "allowed values are N, A, L, P" in str(refusal.value)


def test_a_value_legal_for_another_metric_is_still_refused():
    with pytest.raises(ValueError, match="not a value of Attack Complexity"):
        parse("CVSS:3.1/AV:N/AC:N/PR:N/UI:N/S:U/C:H/I:H/A:H")


def test_a_metric_given_twice_is_refused_and_named_in_words():
    with pytest.raises(ValueError, match=r"Attack Vector \(AV\) is given twice"):
        parse("CVSS:3.1/AV:N/AV:L/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H")


@pytest.mark.parametrize(
    "text",
    [
        "CVSS:3.1/AVN/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H",
        "CVSS:3.1/AV:N:X/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H",
        "CVSS:3.1/AV:/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H",
        "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H/",
    ],
    ids=["no colon", "two colons", "empty value", "trailing separator"],
)
def test_a_malformed_pair_is_refused(text):
    with pytest.raises(ValueError, match="Malformed metric"):
        parse(text)


@pytest.mark.parametrize("text", ["", "   ", None], ids=["empty", "blank", "none"])
def test_an_empty_vector_is_refused(text):
    with pytest.raises(ValueError, match="non-empty string"):
        parse(text)


def test_a_shuffled_vector_rebuilds_in_specification_order():
    shuffled = "CVSS:3.1/A:H/C:H/S:U/I:H/UI:N/PR:N/AC:L/AV:N"
    assert str(parse(shuffled)) == CANONICAL


def test_two_spellings_of_one_assessment_compare_equal():
    shuffled = "CVSS:3.1/S:U/AV:N/AC:L/PR:N/UI:N/C:H/I:H/A:H"
    assert parse(shuffled) == parse(CANONICAL)


def test_the_canonical_form_round_trips():
    assert str(parse(str(parse(CANONICAL)))) == CANONICAL


def test_deriving_a_vector_leaves_the_original_untouched():
    original = parse(TENABLE_VECTOR)
    derived = original.with_metric("S", "C")
    assert derived.value("S") == "C"
    assert original.value("S") == "U"
    assert str(original) == TENABLE_VECTOR
    assert derived is not original


def test_a_derived_vector_keeps_the_declared_version():
    derived = parse("CVSS:3.0/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H").with_metric("S", "C")
    assert derived.version == "3.0"


def test_deriving_with_an_illegal_value_is_refused():
    with pytest.raises(ValueError, match="not a value of Scope"):
        parse(CANONICAL).with_metric("S", "X")


def test_deriving_an_unknown_metric_is_refused():
    with pytest.raises(ValueError, match="Unknown metric 'E'"):
        parse(CANONICAL).with_metric("E", "P")


def test_the_metric_values_cannot_be_edited_in_place():
    # The council hands one vector to several members; a shared mutable vector
    # would make their disagreement meaningless.
    with pytest.raises(TypeError):
        parse(CANONICAL).metrics["AV"] = "L"


def test_asking_for_a_metric_the_vector_has_no_such_thing_as_is_refused():
    with pytest.raises(ValueError, match="not a CVSS Base metric"):
        parse(CANONICAL).value("E")


def test_the_two_published_scorings_of_cve_2025_37164_differ_in_scope_alone():
    assert differing_metrics(parse(CNA_VECTOR), parse(TENABLE_VECTOR)) == ("S",)


def test_identical_vectors_differ_in_nothing():
    assert differing_metrics(parse(CANONICAL), parse(CANONICAL)) == ()


def test_differences_are_reported_in_specification_order():
    other = "CVSS:3.1/AV:P/AC:L/PR:N/UI:R/S:U/C:H/I:H/A:N"
    assert differing_metrics(parse(CANONICAL), parse(other)) == ("AV", "UI", "A")


def test_a_vector_built_directly_is_locked_like_a_parsed_one():
    vector = CvssVector(version="3.1", metrics=dict(parse(CANONICAL).metrics))
    assert str(vector) == CANONICAL
    with pytest.raises(TypeError):
        vector.metrics["AV"] = "L"
