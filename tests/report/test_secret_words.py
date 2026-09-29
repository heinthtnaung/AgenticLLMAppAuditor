"""Guards on the words both pages give a secret: its place, and what matched it."""

from report.secret_words import described, location_of
from report_samples import secret


def test_a_secret_on_one_line_is_placed_by_its_file_and_that_line():
    assert location_of(secret()) == "config/settings.py:2"


def test_a_secret_over_several_lines_is_placed_by_its_first_and_last():
    assert location_of(secret("keys/deploy.pem", 1, end_line=27)) == "keys/deploy.pem:1-27"


def test_what_matched_a_secret_is_its_severity_title_category_and_rule():
    assert described(secret()) == [
        "CRITICAL", "GitHub Personal Access Token", "GitHub", "rule github-pat",
    ]
