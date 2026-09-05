"""A whole audit the planner narrowed: what `findings.json` loses, and what it must not.

Three things a narrowed run must not change, each with its own reason:

* `coverage.checks_run` -- a narrowed check still looked, and an absence there
  is read as `no_check_for_risk_class` by the scorer.
* `coverage.advisory_unreached_component_count` -- the two component-anchored
  checks are not narrowable, so no component may slip off both sides of the
  ledger at once.
* the shape of the document -- `checks_narrowed` is `[]` on a run that narrowed
  nothing, never absent and never null.

Against that sits the one thing a narrowing is *meant* to change, and this file
states it plainly rather than burying it: a finding goes unfound because the
model did not look. That is the honest cost of task 7.4.

The app comes from `narrowing_fixtures`, which writes it into `tmp_path`.
`tests/checks/test_narrowing_join.py` audits the same app and asks whether
`findings.json` and `planner.json` still agree about it.
"""

from narrowing_fixtures import (
    DATA, EVERY_SURFACE, FULL_FINDINGS, NARROWED_FINDINGS, SHELL,
    UNPLANNED_CHECK, UNREACHED_COMPONENTS, audit, narrowed_audit, narrowing_reply)
from checks.known_advisory import CHECK_NAME as ADVISORY_CHECK
from checks.permissions import CHECK_NAME as PERMISSION_CHECK
from checks.plan_selection import NARROWABLE_CHECKS


# --- the app itself ----------------------------------------------------------

def test_the_unnarrowed_audit_reports_every_finding_this_app_has(tmp_path) -> None:
    """The baseline every claim below is measured against, asserted rather than assumed."""
    document, _planner = audit(tmp_path)
    assert document["finding_count"] == FULL_FINDINGS


def test_a_run_that_narrowed_nothing_says_so_with_an_empty_list(tmp_path) -> None:
    """`[]` and not null: whether a narrowing happened is always knowable."""
    document, _planner = audit(tmp_path)
    assert document["checks_narrowed"] == []


def test_the_narrowable_check_under_test_really_is_narrowable() -> None:
    """Guard: narrowing a check the guard refuses would test the refusal, not the narrowing."""
    assert PERMISSION_CHECK in NARROWABLE_CHECKS


# --- what a narrowing costs, stated in counts -------------------------------

def test_a_narrowed_check_reports_one_finding_fewer(tmp_path) -> None:
    """The honest cost of task 7.4: a finding goes unfound because the model did not look."""
    document, _planner = narrowed_audit(tmp_path)
    assert document["finding_count"] == NARROWED_FINDINGS


def test_the_narrowing_is_published_with_its_denominator(tmp_path) -> None:
    """Counts, never a rate: one of three, and the reader does the division."""
    document, _planner = narrowed_audit(tmp_path)
    assert document["checks_narrowed"] == [
        {"check": PERMISSION_CHECK, "examined_surface_count": 1,
         "eligible_surface_count": EVERY_SURFACE}]


def test_the_finding_that_survived_is_the_surface_the_model_chose(tmp_path) -> None:
    """Which one went is as much the claim as how many: the unchosen tool is the one lost."""
    document, _planner = narrowed_audit(tmp_path)
    names = [finding["surface_name"] for finding in document["findings"]
             if finding["rule_id"] == PERMISSION_CHECK]
    assert names == ["ShellTool"]


# --- what a narrowing must not change ---------------------------------------

def test_a_narrowed_check_is_still_named_in_checks_run(tmp_path) -> None:
    """It looked. Absent, `docs/SCHEMAS.md` reads it as having been unable to look at all."""
    narrowed, _planner = narrowed_audit(tmp_path / "narrowed")
    full, _planner = audit(tmp_path / "full")
    assert narrowed["coverage"]["checks_run"] == full["coverage"]["checks_run"]
    assert PERMISSION_CHECK in narrowed["coverage"]["checks_run"]


def test_a_narrowed_run_covers_the_same_risk_classes(tmp_path) -> None:
    """A narrowed class was still examined, so the scorer must not read it as unexamined."""
    narrowed, _planner = narrowed_audit(tmp_path / "narrowed")
    full, _planner = audit(tmp_path / "full")
    assert narrowed["coverage"]["risk_classes_checked"] == full["coverage"]["risk_classes_checked"]


def test_a_narrowed_run_counts_the_same_unreached_components(tmp_path) -> None:
    """Rule 4's whole reason: no component may leave both sides of the ledger at once.

    Were the advisory check narrowable, its finding would disappear while this
    count stayed at one -- the component would be neither reported nor counted
    as unreached, which is the one outcome the coverage block exists to
    prevent.
    """
    narrowed, _planner = narrowed_audit(tmp_path / "narrowed")
    full, _planner = audit(tmp_path / "full")
    assert narrowed["coverage"]["advisory_unreached_component_count"] == UNREACHED_COMPONENTS
    assert full["coverage"]["advisory_unreached_component_count"] == UNREACHED_COMPONENTS


def test_asking_to_narrow_the_advisory_check_changes_nothing_it_reports(tmp_path) -> None:
    """The refusal end to end: the model asks, the guard says no, the ledger is untouched."""
    document, planner_document = audit(
        tmp_path / "asked", narrowing_reply(ADVISORY_CHECK, [DATA.id]))
    full, _planner = audit(tmp_path / "full")
    assert document["checks_narrowed"] == []
    assert document["finding_count"] == full["finding_count"]
    assert [entry["check"] for entry in planner_document["refused_narrowing"]] == [ADVISORY_CHECK]


def test_narrowing_a_check_this_app_never_planned_does_not_end_the_audit(tmp_path) -> None:
    """A model naming a check with no subject here must be contained, not fatal.

    This app builds no agent, so `agent_defined_without_callback_handler` is
    absent from `checks_run` -- and it is narrowable, so the guard honours the
    narrowing and `check_narrowings` then refuses a record for a check that
    never ran. The audit raises. Rule 1 says every failure mode falls back to
    full coverage, and a `ValueError` out of `build_findings` is the one
    fallback a reply must never be able to cause.
    """
    document, _planner = audit(
        tmp_path, narrowing_reply(UNPLANNED_CHECK, [SHELL.id]))
    assert UNPLANNED_CHECK not in document["coverage"]["checks_run"]
    assert document["checks_narrowed"] == []


def test_no_narrowed_check_is_ever_absent_from_checks_run(tmp_path) -> None:
    """The invariant stated on its own, since it is what the crash above is protecting."""
    document, _planner = narrowed_audit(tmp_path)
    for entry in document["checks_narrowed"]:
        assert entry["check"] in document["coverage"]["checks_run"]
