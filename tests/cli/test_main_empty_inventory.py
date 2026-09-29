"""Guards on a run over a directory Syft catalogues nothing in: named everywhere, and exit 3."""

import html
import json
from pathlib import Path

from cli.main import FOUND_NOTHING_BUT_UNCHECKED
from cli.report_files import SUFFIXES
from cli_samples import REPORTS_FOLDER, REPOSITORY_NAME, run_command_line
from report.absences import COMPONENT_INVENTORY, NOTHING_CATALOGUED

# What the two scanners give over an empty directory, as Syft's own report of one
# in `tests/deps/fixtures/syft_report_no_artifacts.json` reads.
NOTHING_THERE = {"components": (), "advisories": {}}


def written(tmp_path: Path, report_format: str) -> str:
    """Read back one of the three reports the run wrote."""
    named = f"{REPOSITORY_NAME}{SUFFIXES[report_format]}"
    return (tmp_path / REPORTS_FOLDER / named).read_text(encoding="utf-8")


def audited_empty(monkeypatch, tmp_path: Path) -> int:
    """Audit the empty directory `run_command_line` makes, checking first that it is empty."""
    code, _, _ = run_command_line([], monkeypatch, tmp_path, **NOTHING_THERE)
    assert list((tmp_path / REPOSITORY_NAME).iterdir()) == []
    return code


def test_an_empty_directory_exits_three_rather_than_passing_as_clean(monkeypatch, tmp_path):
    # Once it exited 0 on "0 findings across 0 components", and a pipeline
    # passing only on 0 went green on a scan of nothing.
    assert audited_empty(monkeypatch, tmp_path) == FOUND_NOTHING_BUT_UNCHECKED


def test_the_audit_record_names_the_empty_inventory_first_under_not_assessed(
    monkeypatch, tmp_path
):
    audited_empty(monkeypatch, tmp_path)
    first = json.loads(written(tmp_path, "json"))["not_assessed"][0]
    assert first == {"what": COMPONENT_INVENTORY, "because": NOTHING_CATALOGUED}


def test_the_terminal_names_the_empty_inventory_under_not_assessed(monkeypatch, tmp_path):
    audited_empty(monkeypatch, tmp_path)
    not_assessed = written(tmp_path, "text").split("NOT ASSESSED\n")[1]
    assert not_assessed.startswith(f"  {COMPONENT_INVENTORY}\n    {NOTHING_CATALOGUED}\n")


def test_the_page_names_the_empty_inventory_under_not_assessed(monkeypatch, tmp_path):
    audited_empty(monkeypatch, tmp_path)
    named = (
        f'<span class="absence-what">{html.escape(COMPONENT_INVENTORY)}</span> '
        f'<span class="absence-why">{html.escape(NOTHING_CATALOGUED)}</span>'
    )
    assert named in written(tmp_path, "html").split('<p class="eyebrow">Not assessed</p>')[1]
