"""Guards on the tab bar and panels: each tab controls a panel, and every panel shows by default.

The contract the script reads is `[role="tab"]` with `aria-controls`, so these
hold the markup that contract needs, and that a panel is a plain section shown
without any script.
"""

from report.html_tabs import Panel, panel_section, panels_main, tabbar

PANELS = (
    Panel("overview", "Overview", "<p>o</p>"),
    Panel("disagree", "Disagreements", "<p>d</p>", 5, alarm=True),
    Panel("agree", "Agreements", "<p>a</p>", 14),
)


def test_a_tab_controls_its_panel_by_aria_controls():
    bar = tabbar(PANELS)
    assert 'role="tab" href="#disagree" data-tab="disagree" aria-controls="panel-disagree"' in bar


def test_the_bar_is_a_tablist_of_one_tab_per_panel():
    bar = tabbar(PANELS)
    assert 'role="tablist"' in bar
    assert bar.count('role="tab"') == len(PANELS)


def test_a_count_rides_on_the_tab_and_an_alarm_count_is_marked():
    bar = tabbar(PANELS)
    assert '<span class="n alarm">5</span>' in bar
    assert '<span class="n">14</span>' in bar


def test_a_tab_with_no_count_carries_no_badge():
    assert '<span class="n' not in tabbar((Panel("overview", "Overview", "<p>o</p>"),))


def test_an_alarm_count_of_zero_is_not_alarmed():
    # Nothing to read first is not an alarm, so a zero disagreement count is plain.
    bar = tabbar((Panel("disagree", "Disagreements", "", 0, alarm=True),))
    assert '<span class="n">0</span>' in bar
    assert "n alarm" not in bar


def test_a_panel_is_a_labelled_tab_panel_shown_by_default():
    section = panel_section(Panel("risk", "Org risk", "<p>body</p>"))
    assert section.startswith('<section id="panel-risk" class="panel" role="tabpanel"')
    assert 'aria-labelledby="tab-risk"' in section
    assert "hidden" not in section


def test_every_panel_lands_in_main():
    main = panels_main(PANELS)
    assert main.startswith('<main class="wrap">')
    assert main.count('class="panel"') == len(PANELS)
