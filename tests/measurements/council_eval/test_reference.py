"""Guards on R1: Red Hat's value, where NVD or GHSA reads the metric the same, and nothing else."""

import eval_samples  # noqa: F401  (puts the evaluation package on the path)
from council_eval.reference import NO_FULL_REFERENCE, full_reference, r1_reference

HIGH = "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:N/I:N/A:H"
LOW = "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:N/I:N/A:L"
LOCAL_LOW = "CVSS:3.1/AV:L/AC:L/PR:N/UI:N/S:U/C:N/I:N/A:L"


def test_a_metric_red_hat_and_nvd_read_the_same_is_referenced():
    assert r1_reference({"redhat": HIGH, "nvd": HIGH})["A"] == "H"


def test_a_metric_red_hat_reads_alone_has_no_reference():
    reference = r1_reference({"redhat": HIGH, "nvd": LOW, "ghsa": LOW})
    assert "A" not in reference
    assert reference["AV"] == "N"


def test_either_corroborating_source_is_enough():
    assert r1_reference({"redhat": HIGH, "nvd": LOW, "ghsa": HIGH})["A"] == "H"


def test_nvd_and_ghsa_agreeing_without_red_hat_are_no_reference():
    # Measured: GHSA gives NVD's full vector on 251 of 333 advisories, often
    # plausibly as NVD republishing the GitHub CNA's score.
    assert r1_reference({"nvd": HIGH, "ghsa": HIGH}) == {}


def test_julia_and_bitnami_do_not_corroborate_red_hat():
    # Measured: julia gives NVD's full vector on 112 of 112, bitnami on 134 of 140.
    assert r1_reference({"redhat": HIGH, "julia": HIGH, "bitnami": HIGH}) == {}


def test_a_vector_the_calculator_refuses_corroborates_nothing():
    version_two = "AV:N/AC:L/Au:N/C:P/I:P/A:P"
    assert r1_reference({"redhat": HIGH, "nvd": version_two}) == {}


def test_the_full_reference_needs_every_metric_referenced():
    assert full_reference({"redhat": HIGH, "ghsa": HIGH}) == HIGH
    assert full_reference({"redhat": HIGH, "ghsa": LOCAL_LOW}) == NO_FULL_REFERENCE
