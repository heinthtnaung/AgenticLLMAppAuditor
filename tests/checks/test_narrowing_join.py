"""`findings.json` and `planner.json` describing one narrowed run, and agreeing about it.

**Two builders, two files, one fact.** `artifacts/planner_document.py` publishes
which surfaces the model asked each check to examine; `artifacts/coverage.py`
publishes how many each check then examined. Nothing in the tool reads one to
produce the other, and nothing reads `planner.json` at all
(`docs/SCHEMAS.md`) -- so there is no downstream failure to catch a drift
between them. Only a test compares the two, and this is it.

The join asserted: for every entry in `checks_narrowed`,

    examined_surface_count == len(planner.json surface_selection[check])

A sibling of `test_narrowed_run.py`, which owns what the narrowing costs. Both
audit the app in `narrowing_fixtures`.
"""

from narrowing_fixtures import narrowed_audit


def test_each_narrowing_examined_as_many_surfaces_as_the_planner_selected(tmp_path) -> None:
    """The join itself, over every entry rather than the one this app happens to produce."""
    document, planner_document = narrowed_audit(tmp_path)
    selection = planner_document["surface_selection"]
    assert document["checks_narrowed"], "a run that narrowed nothing proves nothing here"
    for entry in document["checks_narrowed"]:
        assert entry["examined_surface_count"] == len(selection[entry["check"]])


def test_every_narrowed_check_appears_in_the_planners_selection(tmp_path) -> None:
    """A narrowing in one file and not the other is a record of a run that did not happen."""
    document, planner_document = narrowed_audit(tmp_path)
    narrowed = {entry["check"] for entry in document["checks_narrowed"]}
    assert narrowed <= set(planner_document["surface_selection"])


def test_the_denominator_is_the_surfaces_the_run_itself_considered(tmp_path) -> None:
    """`eligible_surface_count` is the run's own surface count, not a number of its own."""
    document, _planner = narrowed_audit(tmp_path)
    considered = document["coverage"]["surfaces_considered"]
    assert [entry["eligible_surface_count"] for entry in document["checks_narrowed"]] == [
        considered]


def test_the_two_files_agree_which_findings_schema_the_run_produced(tmp_path) -> None:
    """What invalidates `planner.json`, in place of a timestamp, taken from the file beside it."""
    document, planner_document = narrowed_audit(tmp_path)
    assert planner_document["findings_schema_version"] == document["schema_version"]
