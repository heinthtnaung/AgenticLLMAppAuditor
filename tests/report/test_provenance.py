"""Guards on what produced a run: a database there or named missing, and every field asked."""

import pytest

from report.provenance import AdvisoryDatabase, RunProvenance, UnknownAdvisoryDatabase
from report_samples import DATABASE


@pytest.mark.parametrize("built", ["", "   "], ids=["empty", "blank"])
def test_a_database_naming_no_build_date_is_refused(built):
    with pytest.raises(ValueError, match="must give the date it was built"):
        AdvisoryDatabase(built)


def test_a_missing_database_date_must_say_why():
    with pytest.raises(ValueError, match="must say why it is missing"):
        UnknownAdvisoryDatabase("")


def test_an_unreadable_database_is_not_the_same_as_a_fresh_one():
    unknown = UnknownAdvisoryDatabase("no metadata.json on this machine")
    assert not isinstance(unknown, AdvisoryDatabase)
    assert not hasattr(unknown, "built_at")


@pytest.mark.parametrize("field", ["repository", "syft_version", "trivy_version"])
def test_provenance_a_reader_could_not_reproduce_the_run_from_is_refused(field):
    fields = {"repository": "r", "syft_version": "s", "trivy_version": "t", "database": DATABASE}
    with pytest.raises(ValueError, match=f"needs {field}"):
        RunProvenance(**{**fields, field: ""})


@pytest.mark.parametrize("given", [None, "2026-09-22", 0], ids=["none", "str", "int"])
def test_provenance_without_a_real_database_is_refused(given):
    with pytest.raises(TypeError, match="needs a database"):
        RunProvenance("r", "s", "t", given)
