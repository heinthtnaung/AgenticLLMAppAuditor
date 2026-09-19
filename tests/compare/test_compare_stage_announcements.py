"""A comparison announces eight stages, not sixteen: the listener reaches one arm.

`--compare-models` audits the tree twice. Both audits go through
`audit_run.audit`, which announces every stage it passes, so handing the
listener to both would send the page **two** `surfaces`, two `checks` and so on.

**That is not a cosmetic doubling, it is the overlay walking off the end.**
`StageProgress` reads the stored list positionally -- `index === announced.length`
is what marks the stage now in flight -- so a ninth announcement against eight
boundaries indexes past the last one and the panel stops marking anything. The
naive fix for "a compare run announces nothing" is to thread `on_stage` into
both arms, and it is the fix that breaks the page.

So the listener reaches the **local arm only**, and this file holds that as a
property of the announcements rather than as a line in a docstring: each stage
name is announced at most once, and the count never exceeds the vocabulary
`src/reporting/progress.py` owns.

**Why the local arm and not the hosted one.** The local arm is the one a default
audit runs, so its stage names are the ones the page's list was built from; and
it runs first, so a panel following it is not idle while the first audit works.

Staged by `compare_arms_fixtures`, which replaces both model clients and the
publish step. Nothing here reaches a network or a model.
"""

from collections import Counter

import compare_run
import main
from reporting.progress import STAGES

from compare_arms_fixtures import CLOUD_MODEL, stage


def announcements(monkeypatch, tmp_path) -> list[str]:
    """Every stage name one whole comparison announces, in order."""
    said: list[str] = []
    repo = stage(monkeypatch, tmp_path)
    compare_run.run(str(repo), main.DEFAULT_ARTIFACTS_DIR, CLOUD_MODEL,
                    on_stage=lambda name, _detail: said.append(name))
    return said


def test_no_stage_is_announced_twice(monkeypatch, tmp_path) -> None:
    """The doubling itself: two arms announcing would repeat every name."""
    repeated = [name for name, times in Counter(announcements(monkeypatch, tmp_path)).items()
                if times > 1]
    assert repeated == []


def test_the_run_announces_no_more_stages_than_there_are(monkeypatch, tmp_path) -> None:
    """The overlay indexes positionally, so a ninth announcement walks off the list."""
    assert len(announcements(monkeypatch, tmp_path)) <= len(STAGES)


def test_every_name_announced_is_one_the_page_knows(monkeypatch, tmp_path) -> None:
    """`GET /api/stages` serves this vocabulary; a name outside it renders nowhere."""
    assert set(announcements(monkeypatch, tmp_path)) <= set(STAGES)


def test_the_comparison_announces_something_at_all(monkeypatch, tmp_path) -> None:
    """Non-vacuity: an empty list satisfies all three checks above.

    This is the defect the threading fixed -- `stages: []` stored on a run that
    had done the work twice, rendered as eight boundaries struck through.
    """
    assert announcements(monkeypatch, tmp_path)
