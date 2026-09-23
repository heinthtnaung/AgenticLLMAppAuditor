"""What the organisation answered, read from a file the operator fills in.

**JSON, because the project has added no dependency and will not start here.**
It is already the format every scanner on the audit path speaks, so there is one
parser to trust rather than two.

A key this reader does not know is ignored, which is how `answers.example.json`
carries each question's text beside its id under `_questions`: JSON has no
comments and an operator answering `EXP-3` should not have to look up what
`EXP-3` asks.

**Answers apply to every finding unless a finding overrides them.** Exposure and
business impact describe an asset and rarely differ per CVE; threat does --
whether *this* vulnerability is exploited in the wild is a fact about the
vulnerability. Demanding every question for all eighteen findings would make the
file unusable, and pretending threat is uniform would make it wrong, so there is
a default block and an optional override per advisory.

An answer is Yes, No, Unknown or N/A. **Unknown is never read as No**: it is
carried through, and the score it produces comes out flagged.

**And an omission is not an answer.** A file that leaves a question out is
refused, naming every question it left out. A mistyped id was already refused
loudly while an omitted one scored silently as a No -- and the loud case is the
harmless one, because a typo scores nothing while an omission puts a confident,
lower, wrong number in front of a reader. The operator already has the way to
say they do not know.
"""

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping

from scoring.library import question, refuse_incomplete
from scoring.question import Answer

ANSWERS_FIELD = "answers"
BY_ADVISORY_FIELD = "by_advisory"
APPROVAL_FIELD = "approval"

ANSWERS_BY_WORD = {given.value.lower(): given for given in Answer}


@dataclass(frozen=True)
class OrganisationAnswers:
    """One environment's answers: what holds everywhere, and what one advisory changes."""

    everywhere: Mapping[str, Answer] = field(default_factory=dict)
    by_advisory: Mapping[str, Mapping[str, Answer]] = field(default_factory=dict)

    def applying_to(self, advisory_id: str) -> dict[str, Answer]:
        """Give the answers that apply to one advisory, its own overriding the default."""
        return {**self.everywhere, **self.by_advisory.get(advisory_id, {})}


def read_answers(path: str | Path) -> OrganisationAnswers:
    """Read an answer file, refusing anything the approved library does not recognise."""
    document = read_document(Path(path))
    everywhere = read_block(document.get(ANSWERS_FIELD) or {}, ANSWERS_FIELD)
    refuse_incomplete(everywhere)
    return OrganisationAnswers(
        everywhere=everywhere,
        by_advisory={
            advisory_id: read_block(block, f"{BY_ADVISORY_FIELD}.{advisory_id}")
            for advisory_id, block in (document.get(BY_ADVISORY_FIELD) or {}).items()
        },
    )


def read_document(path: Path) -> Mapping[str, Any]:
    """Read the file, refusing one that is absent or is not the JSON object it must be."""
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except OSError as fault:
        raise ValueError(f"No answer file at {str(path)!r}: {fault}") from fault
    except ValueError as fault:
        raise ValueError(f"{str(path)!r} is not readable JSON: {fault}") from fault
    if not isinstance(document, Mapping):
        raise ValueError(f"{str(path)!r} must hold a JSON object of answers")
    return document


def read_block(block: Any, named: str) -> dict[str, Answer]:
    """Read one block of answers, resolving every id against the approved library."""
    if not isinstance(block, Mapping):
        raise ValueError(f"{named} must be an object of question id to answer")
    return {identifier: read_one(identifier, given, named) for identifier, given in block.items()}


def read_one(identifier: str, given: Any, named: str) -> Answer:
    """Read one answer, refusing a question nobody approved and a word nobody offered."""
    # Resolving through the library is what stops a file inventing a question or
    # a weight: an id is all a file may carry, and the weight stays in the library.
    question(identifier)
    answer = ANSWERS_BY_WORD.get(str(given).strip().lower())
    if answer is None:
        allowed = ", ".join(one.value for one in Answer)
        raise ValueError(f"{named}.{identifier} is {given!r}; an answer is {allowed}")
    return answer


def approval_block(path: str | Path) -> Mapping[str, Any]:
    """Give the approval an answer file carries, which is empty when it carries none."""
    block = read_document(Path(path)).get(APPROVAL_FIELD) or {}
    if not isinstance(block, Mapping):
        raise ValueError(f"{APPROVAL_FIELD} must be an object naming who approved and when")
    return block
