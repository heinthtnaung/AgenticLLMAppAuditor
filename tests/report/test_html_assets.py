"""Guards on the packaged stylesheet and script: joined whole, inlined, and fetching nothing.

They are package data read at render time (`report.html_assets`), so an installed
copy carries the same self-contained page a source checkout does. The package-data
list that ships them is held to the files on disk by `tests/test_pyproject.py`.
"""

from report.html_assets import SCRIPT_FILE, STYLESHEET_FILES, read_asset, script, stylesheet


def test_the_stylesheet_joins_its_files_and_names_both_themes():
    sheet = stylesheet()
    assert ":root {" in sheet
    assert "prefers-color-scheme: dark" in sheet
    # The join is the concatenation of the files in their fixed order.
    assert sheet == "\n".join(read_asset(name) for name in STYLESHEET_FILES)


def test_the_stylesheet_fetches_nothing():
    sheet = stylesheet()
    assert "url(" not in sheet and "@import" not in sheet


def test_the_script_turns_panels_into_tabs_only_when_it_runs():
    # The `js` class is what the stylesheet keys the tab behaviour on, so the
    # script must add it; without the script the class is never set.
    assert 'classList.add("js")' in script()


def test_each_asset_is_read_by_name_from_the_package():
    for name in STYLESHEET_FILES:
        assert read_asset(name).strip(), f"{name} shipped empty"
    assert read_asset(SCRIPT_FILE) == script()
