"""Guards on saying a council run is alive: counted, on the error stream, and only when slow."""

import io
import pathlib
import re

from cli.progress import NO_PROGRESS, CouncilProgress

CLOCK = re.compile(r"\b(datetime\.now|time\.time|utcnow|date\.today|perf_counter|monotonic)\b")


def reporting(findings: int = 3, members: int = 2):
    """Build a progress reporter writing somewhere a test can read."""
    written = io.StringIO()
    return CouncilProgress(findings=findings, members=members, out=written), written


def test_the_total_is_every_call_the_run_will_make():
    # Eighteen findings and two members is 288 calls, which is the number a
    # reader needs to know how far through a seventy-seven minute run they are.
    assert CouncilProgress(findings=18, members=2, out=io.StringIO()).calls == 288


def test_one_line_is_said_for_every_member_asked():
    watching, written = reporting(findings=2, members=2)
    for advisory in ("CVE-1", "CVE-2"):
        watching.starting(advisory)
        for metric in ("AV", "AC"):
            for member in ("qwen", "gemma"):
                watching.asking(metric, member)
    assert len(written.getvalue().strip().split("\n")) == 8


def test_a_line_locates_the_run_by_finding_metric_and_member():
    watching, written = reporting()
    watching.starting("CVE-2021-23337")
    watching.asking("AV", "gemma4:latest")
    said = written.getvalue()
    assert "CVE-2021-23337" in said
    assert "AV" in said
    assert "gemma4:latest" in said


def test_the_call_count_climbs_towards_the_total():
    watching, written = reporting(findings=1, members=1)
    watching.starting("CVE-1")
    watching.asking("AV", "qwen")
    watching.asking("AC", "qwen")
    assert "1/8" in written.getvalue()
    assert "2/8" in written.getvalue()


def test_the_finding_count_climbs_as_the_run_moves_on():
    watching, written = reporting(findings=3, members=1)
    watching.starting("CVE-1")
    watching.asking("AV", "qwen")
    watching.starting("CVE-2")
    watching.asking("AV", "qwen")
    assert "1/3" in written.getvalue()
    assert "2/3" in written.getvalue()


class RecordingStream(io.StringIO):
    """A stream that remembers being flushed, which StringIO cannot show on its own."""

    flushes = 0

    def flush(self) -> None:
        """Count the flush and do what a StringIO does."""
        self.flushes += 1


def test_every_line_ends_so_a_reader_sees_it_as_it_happens():
    # A partial line buffered until the run ends is no better than silence.
    watching, written = reporting()
    watching.starting("CVE-1")
    watching.asking("AV", "qwen")
    assert written.getvalue().endswith("\n")


def test_every_line_is_pushed_out_rather_than_buffered_until_the_run_ends():
    # The whole point on a seventy-seven minute run: a line held in a buffer
    # until the process exits is silence with extra steps.
    written = RecordingStream()
    watching = CouncilProgress(findings=1, members=1, out=written)
    watching.starting("CVE-1")
    watching.asking("AV", "qwen")
    watching.asking("AC", "qwen")
    assert written.flushes == 2


def test_a_run_nobody_is_watching_says_nothing():
    # A scan with no council takes about a second and needs none of this.
    NO_PROGRESS.starting("CVE-1")
    NO_PROGRESS.asking("AV", "qwen")


def test_nothing_anywhere_in_src_reads_a_clock():
    # Guarded here because progress is the change that would have introduced the
    # first one: elapsed timings on a seventy-seven minute run are the obvious
    # thing to want. A line printed before its call is liveness, and a reader
    # watching a terminal supplies the elapsed time themselves, so counts are
    # enough -- and `README.md`, `docs/diagrams.md` and `docs/SCORING_MODEL.md`
    # all still say there is no clock anywhere in `src/`.
    source = pathlib.Path(__file__).resolve().parents[2] / "src"
    reading = [
        f"{path}:{number}"
        for path in sorted(source.rglob("*.py"))
        for number, line in enumerate(path.read_text(encoding="utf-8").split("\n"), 1)
        if CLOCK.search(line)
    ]
    assert reading == []
