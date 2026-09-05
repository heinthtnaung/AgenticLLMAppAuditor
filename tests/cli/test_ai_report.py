"""The AI-formatted report: styled by a model, but never allowed to fabricate.

The model may omit advisories (it summarises), which the banner discloses, but
a page naming a CVE the audit never found is refused whole. Every model call is
stubbed, so no test needs Ollama or reaches the network.
"""

import pytest

import ai_report
import model_client

REPORT = """# Audit report: demo

## Known vulnerabilities in dependencies

- `pkg:npm/lodash@4.17.19` — CVE-2021-23337 (HIGH), CVE-2020-28500
"""


def stub_model(monkeypatch, answer: str, digest: str | None = "abcdef012345") -> None:
    """Replace the model call and the digest lookup, so nothing reaches a server."""
    monkeypatch.setattr(model_client, "ask", lambda prompt, model=None: answer)
    monkeypatch.setattr(model_client, "model_digest", lambda model=None: digest)


def app_with_report(tmp_path):
    """An artifact directory holding a report.md for the formatter to read."""
    app = tmp_path / "demo"
    app.mkdir()
    (app / "report.md").write_text(REPORT, encoding="utf-8")
    return app


def test_a_page_that_invents_an_advisory_is_refused_whole(monkeypatch, tmp_path) -> None:
    """Fabrication is the worst failure a security report has, so it is fatal."""
    stub_model(monkeypatch, "<p>CVE-2021-23337 CVE-2020-28500 and CVE-2099-9999</p>")
    with pytest.raises(ValueError, match="CVE-2099-9999"):
        ai_report.format_report(app_with_report(tmp_path))


def test_a_fabricated_non_cve_advisory_id_is_also_refused(monkeypatch, tmp_path) -> None:
    """Invention is fatal in every scheme Trivy emits, not only CVE/GHSA, and case-insensitively."""
    stub_model(monkeypatch, "<p>CVE-2021-23337 CVE-2020-28500 PYSEC-2099-1 and gO-2099-9</p>")
    with pytest.raises(ValueError, match="PYSEC-2099-1"):
        ai_report.format_report(app_with_report(tmp_path))


def test_a_non_directory_is_a_clear_error(tmp_path) -> None:
    """The formatter needs an artifact directory, and says so when given a file."""
    a_file = tmp_path / "not-a-dir"
    a_file.write_text("x", encoding="utf-8")
    with pytest.raises(NotADirectoryError, match="not a directory"):
        ai_report.format_report(a_file)


def test_a_complete_page_names_every_advisory_and_says_so(monkeypatch, tmp_path) -> None:
    """When the model reproduces every id, the banner says the view is complete."""
    stub_model(monkeypatch, "<p>CVE-2021-23337 CVE-2020-28500</p>")
    page = ai_report.format_report(app_with_report(tmp_path)).read_text(encoding="utf-8")
    assert "name every advisory" in page
    assert "INCOMPLETE" not in page
    assert "gemma4" in page and "Formatted by" in page  # provenance: the model that wrote it


def test_an_incomplete_page_is_written_but_flagged_and_points_at_the_real_report(
        monkeypatch, tmp_path) -> None:
    """The model summarised: the page is kept, but the banner discloses the omission."""
    stub_model(monkeypatch, "<p>CVE-2021-23337 only</p>")
    page = ai_report.format_report(app_with_report(tmp_path)).read_text(encoding="utf-8")
    assert "INCOMPLETE" in page
    assert "report.html" in page
    assert "omits 1 advisory id" in page


def test_a_model_that_cannot_be_reached_raises_for_the_caller_to_degrade(
        monkeypatch, tmp_path) -> None:
    """The audit already wrote report.html; an absent model is a note, not a failure."""
    def unreachable(prompt, model=None):
        raise RuntimeError("cannot reach the local model server")
    monkeypatch.setattr(model_client, "ask", unreachable)
    with pytest.raises(RuntimeError, match="cannot reach"):
        ai_report.format_report(app_with_report(tmp_path))


def test_no_report_to_format_is_a_clear_error(tmp_path) -> None:
    """The formatter reads report.md, so its absence names the fix."""
    (tmp_path / "empty").mkdir()
    with pytest.raises(FileNotFoundError, match="run the audit first"):
        ai_report.format_report(tmp_path / "empty")


def test_a_fenced_answer_is_unwrapped(monkeypatch, tmp_path) -> None:
    """A model that wraps its HTML in a ```html fence still yields a clean page."""
    stub_model(monkeypatch, "```html\n<p>CVE-2021-23337 CVE-2020-28500</p>\n```")
    page = ai_report.format_report(app_with_report(tmp_path)).read_text(encoding="utf-8")
    assert "```" not in page.split("</head>")[-1]
