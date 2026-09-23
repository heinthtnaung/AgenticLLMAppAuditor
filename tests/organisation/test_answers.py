"""Guards on the answer file: only approved questions, and Unknown never read as No."""

import json
from pathlib import Path

import pytest

from organisation.answers import OrganisationAnswers, approval_block, read_answers
from organisation_samples import BLANK_ANSWERS, written
from scoring.library import question, refuse_incomplete
from scoring.question import Answer


def test_an_answer_file_is_read_into_answers_by_question_id(tmp_path):
    given = read_answers(written(tmp_path, answers={"EXP-1": "Yes", "BUS-1": "No"}))
    assert given.everywhere["EXP-1"] is Answer.YES
    assert given.everywhere["BUS-1"] is Answer.NO
    assert set(given.everywhere) == set(BLANK_ANSWERS)


@pytest.mark.parametrize(
    ("written_word", "expected"),
    [
        ("Yes", Answer.YES),
        ("no", Answer.NO),
        ("Unknown", Answer.UNKNOWN),
        ("N/A", Answer.NOT_APPLICABLE),
    ],
)
def test_every_answer_the_design_allows_is_read(tmp_path, written_word, expected):
    path = written(tmp_path, answers={"EXP-1": written_word})
    assert read_answers(path).everywhere["EXP-1"] is expected


def test_unknown_is_carried_through_rather_than_read_as_no(tmp_path):
    # It must produce a flagged provisional score, which it cannot do if the
    # file reader quietly turns it into a No on the way in.
    path = written(tmp_path, answers={"EXP-1": "Unknown"})
    assert read_answers(path).everywhere["EXP-1"] is Answer.UNKNOWN


def test_a_question_nobody_approved_is_refused(tmp_path):
    # The file may carry an id and never a weight, so this is where a made-up
    # question is stopped rather than silently scored.
    path = written(tmp_path, complete=False, answers={"EXP-99": "Yes"})
    with pytest.raises(ValueError, match="not a question in the approved library"):
        read_answers(path)


@pytest.mark.parametrize("given", ["maybe", "", "true", 1])
def test_a_word_that_is_no_answer_is_refused(tmp_path, given):
    path = written(tmp_path, answers={"EXP-1": given})
    with pytest.raises(ValueError, match="an answer is Yes, No, Unknown, N/A"):
        read_answers(path)


def test_one_advisory_can_override_what_holds_everywhere(tmp_path):
    # Exposure describes an asset and rarely differs per CVE; whether *this*
    # vulnerability is exploited in the wild is a fact about the vulnerability.
    path = written(
        tmp_path,
        answers={"THR-1": "No", "EXP-1": "Yes"},
        by_advisory={"CVE-2021-23337": {"THR-1": "Yes"}},
    )
    given = read_answers(path)
    assert given.applying_to("CVE-2021-23337")["THR-1"] is Answer.YES
    assert given.applying_to("CVE-OTHER")["THR-1"] is Answer.NO
    assert given.applying_to("CVE-OTHER")["EXP-1"] is Answer.YES


def test_an_override_names_a_question_the_library_approved_too(tmp_path):
    path = written(tmp_path, by_advisory={"CVE-1": {"NOPE-1": "Yes"}})
    with pytest.raises(ValueError, match="not a question in the approved library"):
        read_answers(path)


@pytest.mark.parametrize("document", [{}, {"answers": {}}], ids=["no block", "empty block"])
def test_a_file_answering_nothing_at_all_is_refused_rather_than_read_as_twelve_noes(
    tmp_path, document
):
    # The whole-file case of the same fault: an empty answers block is not an
    # environment described as harmless, it is a file nobody filled in.
    path = written(tmp_path, complete=False, **document)
    with pytest.raises(ValueError, match="unanswered; the approved library asks all 12"):
        read_answers(path)


def test_an_environment_nobody_described_answers_nothing():
    assert OrganisationAnswers().applying_to("CVE-1") == {}


def test_a_file_that_is_not_there_is_refused(tmp_path):
    with pytest.raises(ValueError, match="No answer file at"):
        read_answers(tmp_path / "absent.json")


def test_a_file_that_is_not_json_is_refused(tmp_path):
    path = tmp_path / "answers.json"
    path.write_text("not json at all", encoding="utf-8")
    with pytest.raises(ValueError, match="is not readable JSON"):
        read_answers(path)


@pytest.mark.parametrize("document", ["[]", '"answers"', "7"], ids=["list", "string", "number"])
def test_a_document_that_is_not_an_object_of_answers_is_refused(tmp_path, document):
    path = tmp_path / "answers.json"
    path.write_text(document, encoding="utf-8")
    with pytest.raises(ValueError, match="must hold a JSON object of answers"):
        read_answers(path)


def test_a_block_that_is_not_an_object_is_refused(tmp_path):
    path = written(tmp_path, complete=False, answers=["EXP-1"])
    with pytest.raises(ValueError, match="must be an object of question id to answer"):
        read_answers(path)


def test_a_file_leaving_one_question_out_is_refused_rather_than_scoring_it_as_no(tmp_path):
    # One deleted line moved a finding ten points and changed its band, with
    # nothing flagged. A mistyped id was already refused loudly; an omitted one
    # was not, and the loud case is the harmless one, because a typo scores
    # nothing while an omission puts a confident lower number in front of a reader.
    short = {identifier: "No" for identifier in BLANK_ANSWERS if identifier != "EXP-1"}
    path = written(tmp_path, complete=False, answers=short)
    with pytest.raises(ValueError, match="^EXP-1 unanswered"):
        read_answers(path)


def test_every_unanswered_question_is_named_at_once(tmp_path):
    # One round of correcting the file, not one question at a time.
    short = {identifier: "No" for identifier in BLANK_ANSWERS if not identifier.startswith("THR")}
    path = written(tmp_path, complete=False, answers=short)
    with pytest.raises(ValueError, match="THR-1, THR-2, THR-3 unanswered"):
        read_answers(path)


def test_the_refusal_says_what_to_write_instead():
    # The operator already has the way to say they do not know, and the message
    # is the only place they will be told which it is.
    with pytest.raises(ValueError, match="answer Unknown to record that nobody knows"):
        refuse_incomplete({})


def test_the_approval_a_file_carries_is_given_back_as_written(tmp_path):
    path = written(tmp_path, approval={"approver": "someone", "decision": "approved"})
    assert approval_block(path)["approver"] == "someone"


def test_a_file_carrying_no_approval_carries_none(tmp_path):
    assert approval_block(written(tmp_path, answers={"EXP-1": "Yes"})) == {}


EXAMPLE = Path(__file__).resolve().parents[2] / "answers.example.json"


def example_document() -> dict:
    """Read the answer file the repository ships as a starting point."""
    return json.loads(EXAMPLE.read_text(encoding="utf-8"))


def test_the_example_file_answers_every_approved_question():
    # An example file is the one artefact that falls out of step silently when a
    # thirteenth question is added, and an out-of-date template is worse than none.
    assert set(example_document()["answers"]) == set(BLANK_ANSWERS)


def test_the_example_file_answers_nothing_the_library_does_not_ask():
    assert not set(example_document()["answers"]) - set(BLANK_ANSWERS)


def test_the_example_file_spells_out_every_question_it_asks():
    assert set(example_document()["_questions"]) == set(BLANK_ANSWERS)


def test_the_question_text_in_the_example_is_the_librarys_own():
    written_out = example_document()["_questions"]
    assert all(question(identifier).text == text for identifier, text in written_out.items())


def test_the_example_file_runs_as_it_ships():
    # The strongest version of the check: it is not merely complete, it is
    # accepted by the reader that refuses an incomplete one.
    given = read_answers(EXAMPLE)
    assert set(given.everywhere) == set(BLANK_ANSWERS)
    assert all(answer is Answer.NO for answer in given.everywhere.values())
