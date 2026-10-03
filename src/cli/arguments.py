"""What the audit command takes.

**The repository is an argument and nothing clones it.** Fetching needs the
corporate proxy on and scanning needs it off -- `docs/SETUP.md` says the two go in
opposite directions -- so a command doing both would flip that state mid-run.
`docs/diagrams.md` already puts the advisory database's download out of band for
the same reason, and the repository belongs on the same side of that line: the
operator fetches once, and the scan over what is on disk can then be repeated
identically, offline, as many times as anyone wants.

**The council is off unless a flag asks for one.** `--council-member` names
each member on the command line; `--council` runs the ones `AUDITOR_COUNCIL_MEMBERS`
names, so switching models is one line of `.env`. The setting alone starts
nothing, and both flags at once are refused rather than one silently winning.
Naming none, which is the default, is a run with no council: the published
scores stand side by side, and a council, when one runs, adds its own reading
beside them without choosing among them.

**And when it is on it is scoped.** The council reconciles sources, so by default
it is asked only about the findings whose sources do not settle them;
`--council-all-findings` turns that off. The flag exists because scoping costs
something real -- a council that never reads an agreed finding cannot discover
that both its sources are wrong -- and that is a call for the operator.
"""

import argparse
from dataclasses import dataclass
from pathlib import Path

from council.env_file import COUNCIL_MEMBERS, SERVER

PROGRAM = "audit"
# The scan is offline; a council, when one runs, reaches a model server, so the
# description cannot call the whole run offline. SERVER names it, here or remote.
DESCRIPTION = (
    "Audit a repository against the pinned advisory database, offline; a council, "
    f"when one runs, asks the Ollama server {SERVER} names."
)

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
# Not "local": with AUDITOR_REMOTE_SERVER=yes the server is another machine.
MEMBER_HELP = (
    f"add one model on the Ollama server {SERVER} names to the assessor council, "
    "by its Ollama name; repeat for more members, and give none to run no council"
)
COUNCIL_HELP = (
    f"run the assessor council with the models {COUNCIL_MEMBERS} names, in the environment "
    f"or .env, comma-separated, on the Ollama server {SERVER} names"
)
ALL_FINDINGS_HELP = (
    "put every finding to the council, not only those whose published sources "
    "disagree, include one that could not be read, or scored nothing; slower, "
    "and the only way to catch two sources that agree and are both wrong"
)
# Accepted, the flag would change nothing, and the run would read as one that
# asked about every finding when it asked about none.
ALL_FINDINGS_WITHOUT_MEMBERS = (
    "--council-all-findings needs --council or a --council-member: with nobody named "
    "there is no council to put the findings to"
)
# Taking one over the other would be a precedence the operator never chose.
BOTH_COUNCILS = (
    f"--council runs the members {COUNCIL_MEMBERS} names and --council-member names "
    "them here; give one or the other, not both"
)


@dataclass(frozen=True)
class Options:
    """One invocation: what to audit, how to report it, and who to ask about it."""

    repository: Path
    report_format: str
    council_models: tuple[str, ...]
    council_all_findings: bool = False
    # `--council`: the members are the setting's, read by `cli.audit` when it runs.
    council_from_settings: bool = False
    # None is "no file was given", which is the only thing absence can mean for
    # a command-line path, and `organisation_run` reads it as exactly that.
    answers: Path | None = None


def parse_arguments(argv: list[str] | None = None) -> Options:
    """Read one command line into the options an audit runs with."""
    parser = build_parser()
    parsed = parser.parse_args(argv)
    if parsed.council and parsed.council_member:
        parser.error(BOTH_COUNCILS)
    if parsed.council_all_findings and not (parsed.council or parsed.council_member):
        parser.error(ALL_FINDINGS_WITHOUT_MEMBERS)
    return Options(
        repository=Path(parsed.repository),
        report_format=parsed.format,
        council_models=tuple(parsed.council_member),
        council_all_findings=parsed.council_all_findings,
        council_from_settings=parsed.council,
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
    parser.add_argument("--council", action="store_true", help=COUNCIL_HELP)
    parser.add_argument(
        "--council-all-findings", action="store_true", help=ALL_FINDINGS_HELP
    )
    parser.add_argument("--answers", metavar="FILE", default=None, help=ANSWERS_HELP)
    return parser
