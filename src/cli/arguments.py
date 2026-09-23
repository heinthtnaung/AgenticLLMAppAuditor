"""What the audit command takes.

**The repository is an argument and nothing clones it.** Fetching needs the
corporate proxy on and scanning needs it off -- `CLAUDE.md` says the two go in
opposite directions -- so a command doing both would flip that state mid-run.
`docs/diagrams.md` already puts the advisory database's download out of band for
the same reason, and the repository belongs on the same side of that line: the
operator fetches once, and the scan over what is on disk can then be repeated
identically, offline, as many times as anyone wants.

**The council is off because the roster is empty.** No file format has been
committed to, so members are named on the command line rather than read from a
schema nobody has agreed. Naming none, which is the default, is a run with no
council -- and that is the honest state, because the per-source scores then
stand side by side with no winner.
"""

import argparse
from dataclasses import dataclass
from pathlib import Path

PROGRAM = "audit"
DESCRIPTION = "Audit a repository against the pinned advisory database, offline."

TEXT_FORMAT = "text"
JSON_FORMAT = "json"
HTML_FORMAT = "html"
REPORT_FORMATS = (TEXT_FORMAT, JSON_FORMAT, HTML_FORMAT)

REPOSITORY_HELP = "the repository to audit, already on disk"
FORMAT_HELP = (
    "text for a terminal, json for the audit record, "
    "html for one self-contained page that fetches nothing"
)
ANSWERS_HELP = (
    "a JSON file of this organisation's answers to the approved questions; "
    "without one no Organisation Risk Score is computed and the report says so"
)
MEMBER_HELP = (
    "add one local model to the assessor council, by its Ollama name; "
    "repeat for more members, and give none to run no council"
)


@dataclass(frozen=True)
class Options:
    """One invocation: what to audit, how to report it, and who to ask about it."""

    repository: Path
    report_format: str
    council_models: tuple[str, ...]
    # None is "no file was given", which is the only thing absence can mean for
    # a command-line path, and `organisation_run` reads it as exactly that.
    answers: Path | None = None


def parse_arguments(argv: list[str] | None = None) -> Options:
    """Read one command line into the options an audit runs with."""
    parsed = build_parser().parse_args(argv)
    return Options(
        repository=Path(parsed.repository),
        report_format=parsed.format,
        council_models=tuple(parsed.council_member),
        answers=Path(parsed.answers) if parsed.answers else None,
    )


def build_parser() -> argparse.ArgumentParser:
    """Describe the command line, so `--help` is the documentation."""
    parser = argparse.ArgumentParser(prog=PROGRAM, description=DESCRIPTION)
    parser.add_argument("repository", help=REPOSITORY_HELP)
    parser.add_argument(
        "--format", choices=REPORT_FORMATS, default=TEXT_FORMAT, help=FORMAT_HELP
    )
    parser.add_argument(
        "--council-member", action="append", default=[], metavar="MODEL", help=MEMBER_HELP
    )
    parser.add_argument("--answers", metavar="FILE", default=None, help=ANSWERS_HELP)
    return parser
