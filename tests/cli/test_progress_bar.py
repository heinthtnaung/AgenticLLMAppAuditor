"""Guards on the terminal bar: it fills to the run's fraction, carries no clock, and never wraps."""

import io

from cli.progress_bar import (
    BAR_WIDTH,
    EMPTY,
    FILLED,
    LINE_WIDTH,
    RETURN,
    BarDisplay,
    bar,
    bar_for,
    filled_cells,
    percent,
)
from cli_samples import FakeTerminal


def frames(written: str) -> list[str]:
    """Give each redrawn frame's visible text, stripped of the padding that clears the last."""
    return [piece.rstrip() for piece in written.split(RETURN) if piece.strip()]


def test_a_bar_at_the_start_is_empty():
    assert filled_cells(0, 786) == 0
    assert percent(0, 786) == 0
    assert bar(0, 786) == f"[{EMPTY * BAR_WIDTH}]"


def test_a_bar_partway_is_filled_to_its_fraction():
    # Half of eighteen cells is nine, and half of a run is fifty percent.
    assert filled_cells(5, 10) == 9
    assert percent(5, 10) == 50
    assert bar(5, 10) == f"[{FILLED * 9}{EMPTY * 9}]"


def test_a_finished_bar_is_full():
    assert filled_cells(10, 10) == BAR_WIDTH
    assert percent(10, 10) == 100
    assert bar(10, 10) == f"[{FILLED * BAR_WIDTH}]"


def test_neither_the_bar_nor_the_count_runs_past_full():
    # A member counted twice by a miscount must not draw a nineteenth cell or 101 percent.
    assert filled_cells(11, 10) == BAR_WIDTH
    assert percent(11, 10) == 100


def test_a_run_with_nothing_to_do_draws_an_empty_bar_rather_than_dividing_by_zero():
    assert filled_cells(0, 0) == 0
    assert percent(0, 0) == 0


def test_the_council_bar_carries_a_bar_the_counts_the_percentage_and_the_finding():
    out = FakeTerminal()
    BarDisplay(out).council("council", 5, 10, 2, 3)
    drawn = frames(out.getvalue())[-1]
    assert drawn == f"council [{FILLED * 9}{EMPTY * 9}] 5/10  50%  finding 2/3"


def test_the_council_bar_is_redrawn_in_place_and_not_newline_terminated():
    out = FakeTerminal()
    watching = BarDisplay(out)
    watching.council("council", 1, 10, 1, 3)
    watching.council("council", 2, 10, 1, 3)
    written = out.getvalue()
    assert written.startswith(RETURN)
    assert written.count(RETURN) == 2
    assert "\n" not in written


def test_the_escalation_line_is_a_running_count_with_no_bar_and_no_percentage():
    # Escalation's total is not known until the council has left something open.
    out = FakeTerminal()
    BarDisplay(out).escalation("escalation", 4, 2, 3, "CVE-1")
    drawn = frames(out.getvalue())[-1]
    assert drawn == "escalation 4  finding 2/3 CVE-1"
    assert "[" not in drawn
    assert "%" not in drawn


def test_the_explanation_phase_has_its_own_bar_one_call_to_a_finding():
    out = FakeTerminal()
    BarDisplay(out).explanation("explanation", 1, 2, "CVE-1")
    drawn = frames(out.getvalue())[-1]
    assert drawn == f"explanation [{FILLED * 9}{EMPTY * 9}] 1/2  50%  finding CVE-1"


def test_a_new_phase_begins_on_its_own_line_so_the_bar_before_it_stays_put():
    out = FakeTerminal()
    watching = BarDisplay(out)
    watching.council("council", 10, 10, 3, 3)
    watching.escalation("escalation", 1, 1, 3, "CVE-1")
    council_frame, escalation_frame = frames(out.getvalue())
    assert council_frame.startswith("council ")
    assert escalation_frame.startswith("escalation ")
    # One newline, closing the council line before the escalation line is drawn.
    assert out.getvalue().count("\n") == 1


def test_finishing_ends_the_open_line_so_later_output_starts_below_the_bar():
    out = FakeTerminal()
    watching = BarDisplay(out)
    watching.council("council", 10, 10, 3, 3)
    watching.finish()
    assert out.getvalue().endswith("\n")


def test_finishing_twice_closes_the_line_once():
    # finish() runs in a finally, so a phase that both completed and unwound must
    # not end two lines; it resets the phase, so the second finish writes nothing.
    out = FakeTerminal()
    watching = BarDisplay(out)
    watching.council("council", 10, 10, 3, 3)
    watching.finish()
    watching.finish()
    assert out.getvalue().count("\n") == 1


def test_finishing_a_bar_that_drew_nothing_writes_nothing():
    # A run that asked about no finding drew no frame, so it has no line to close.
    out = FakeTerminal()
    BarDisplay(out).finish()
    assert out.getvalue() == ""


def test_a_frame_never_wraps_an_eighty_column_terminal():
    # A long advisory id is clipped, not allowed to spill onto a second row.
    out = FakeTerminal()
    BarDisplay(out).escalation("escalation", 9, 2, 3, "CVE-" + "9" * 200)
    for piece in out.getvalue().split(RETURN):
        assert len(piece) <= LINE_WIDTH < 80


def test_a_shorter_frame_clears_the_longer_one_before_it():
    # Padding to a fixed width is what wipes the tail of a line that was longer.
    out = FakeTerminal()
    watching = BarDisplay(out)
    watching.escalation("escalation", 1, 1, 3, "CVE-LONG-IDENTIFIER")
    watching.escalation("escalation", 2, 1, 3, "CVE-1")
    second = out.getvalue().split(RETURN)[-1]
    assert len(second) == LINE_WIDTH


def test_a_terminal_without_debug_gets_a_bar():
    assert isinstance(bar_for(FakeTerminal(), debug=False), BarDisplay)


def test_debug_takes_the_full_log_even_at_a_terminal():
    assert bar_for(FakeTerminal(), debug=True) is None


def test_a_redirected_stream_takes_the_full_log():
    assert bar_for(io.StringIO(), debug=False) is None


def test_the_bar_writes_to_its_own_stream_and_never_to_stdout(capsys):
    out = FakeTerminal()
    watching = BarDisplay(out)
    watching.council("council", 1, 10, 1, 3)
    watching.finish()
    assert capsys.readouterr().out == ""
