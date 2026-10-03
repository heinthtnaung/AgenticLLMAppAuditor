"""Guards on a dataset's chat prompts: what a chat is shown, and what it is never shown."""

import re
from collections import Counter
from itertools import chain, product
from pathlib import Path

import pytest

import chat_samples
import eval_samples as samples
from council.evidence import CVE_IDENTIFIER
from council.prompt import build_prompt
from council.redaction import BARE_VECTOR, GHSA_IDENTIFIER, PUBLISHED_VECTOR
from council_eval.chat_prompt_set import chat_prompts
from council_eval.dataset import read_dataset
from scoring.library import APPROVED_QUESTIONS

PILOT_DATASET = (
    Path(__file__).resolve().parents[3]
    / "measurements" / "council_eval_runs" / "pilot-vulnscout" / "vulnscout.dataset.json"
)
IDENTIFIED = (
    "CVE-2021-44228 lets a remote attacker in; see GHSA-jfh8-c2jp-5v3q. "
    "Scored CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:C/C:H/I:H/A:H, or AV:N/AC:L by another."
)
LEAKS = (CVE_IDENTIFIER, GHSA_IDENTIFIER, PUBLISHED_VECTOR, BARE_VECTOR)
ORDER_WORDS = ("forward", "reversed", "order")
WITHHELD_URL = re.compile(r"https?://\S*\[identifier withheld\]")


def corpus_prompts() -> tuple:
    """Build every prompt of the pilot's 18 findings, the corpus a person will paste."""
    return chat_prompts(read_dataset(PILOT_DATASET))


def organisation_words() -> tuple[str, ...]:
    """Give every approved question's id and text, which is what an organisation answers."""
    return tuple(chain.from_iterable((one.question_id, one.text) for one in APPROVED_QUESTIONS))


def carries_any(text: str, found) -> bool:
    """Say whether a text holds any of some words."""
    return any(word in text for word in found)


def words(text: str) -> Counter:
    """Count a text's words, whatever order they stand in."""
    return Counter(re.findall(r"\w+", text))


def test_each_item_gets_a_forward_and_a_reversed_prompt_named_by_its_prompt_id():
    prompts = chat_prompts(chat_samples.TWO_ITEMS)
    assert [one.file for one in prompts] == [f"chat-prompt-{one.prompt_id}.txt" for one in prompts]
    assert [(one.key, one.order) for one in prompts] == [
        ("CVE-2026-0001", "forward"), ("CVE-2026-0001", "reversed"),
        ("CVE-2026-0002", "forward"), ("CVE-2026-0002", "reversed"),
    ]


@pytest.mark.parametrize("index", range(4))
def test_no_prompt_names_its_order_or_its_advisory_in_its_file_name_or_its_words(index):
    prompt = chat_prompts(chat_samples.TWO_ITEMS)[index]
    pasted = (prompt.file + prompt.text).lower()
    assert [word for word in ORDER_WORDS if word in pasted] == []
    assert not CVE_IDENTIFIER.search(prompt.file + prompt.text)


def test_two_advisories_that_read_alike_are_refused_as_one_prompt():
    alike = (samples.item("CVE-2026-0001"), samples.item("CVE-2026-0002"))
    with pytest.raises(ValueError, match="CVE-2026-0001 and CVE-2026-0002 read alike"):
        chat_prompts(alike)


def test_a_chat_is_shown_the_advisory_a_council_member_is_shown():
    shown = chat_samples.prompts((samples.item(),))[0].advisory_shown
    assert shown == build_prompt("AV", samples.ADVISORY_TEXT).advisory_shown


def test_an_id_or_a_published_vector_in_an_advisory_never_reaches_the_prompt():
    (forward, reversed_) = chat_prompts((chat_samples.item_reading(samples.KEY, IDENTIFIED),))
    assert not any(pattern.search(forward.text + reversed_.text) for pattern in LEAKS)


@pytest.mark.parametrize("pattern", LEAKS, ids=lambda one: one.pattern[:24])
def test_no_prompt_of_the_real_corpus_carries_an_id_or_a_published_vector(pattern):
    assert not [one.file for one in corpus_prompts() if pattern.search(one.text + one.file)]


def test_no_prompt_of_the_real_corpus_carries_its_own_published_vectors():
    items = read_dataset(PILOT_DATASET)
    vectors = {one.key: one.finding.advisory.vectors.values() for one in items}
    assert not [one.file for one in corpus_prompts() if carries_any(one.text, vectors[one.key])]


def test_no_prompt_of_the_real_corpus_carries_an_organisation_question_or_answer():
    words = organisation_words()
    assert not [one.file for one in corpus_prompts() if carries_any(one.text, words)]


def test_no_prompt_of_the_real_corpus_names_its_order_in_its_own_words_or_its_name():
    # The advisory's own prose may say `forward` -- two of these say "forward
    # slash" -- and says it alike in both orders; everything else is the prompt's.
    own = {one.file: one.text.replace(one.advisory_shown, "").lower() for one in corpus_prompts()}
    pairs = product(own.items(), ORDER_WORDS)
    assert [(file, word) for (file, text), word in pairs if word in text] == []
    assert not [one.file for one in corpus_prompts() if carries_any(one.file.lower(), ORDER_WORDS)]


def test_an_advisory_s_two_prompts_differ_in_word_order_alone_and_the_record_says_which():
    forward, reversed_ = corpus_prompts()[:2]
    assert (forward.order, reversed_.order) == ("forward", "reversed")
    assert forward.body != reversed_.body
    assert words(forward.body) == words(reversed_.body)


def test_a_prompt_still_carries_the_address_of_an_advisory_whose_id_was_withheld():
    # A known gap, asserted so that closing it turns this red. The redaction is
    # the council's: it takes the id out of a URL and leaves the rest standing,
    # so two advisories still name the project and the page the id would open.
    withheld = [one for one in corpus_prompts() if WITHHELD_URL.search(one.advisory_shown)]
    assert len(withheld) == 4
    found = set(chain.from_iterable(WITHHELD_URL.findall(one.text) for one in withheld))
    assert "https://github.com/lodash/lodash/security/advisories/[identifier withheld]" in found


def test_a_prompt_still_names_the_package_and_version_a_model_may_remember():
    # A known gap, asserted so that closing it turns this red. The redaction is
    # the council's: ids and vectors out, the advisory's prose in. A frontier
    # model may know an advisory by its package and version, and rule 2 asking
    # it not to use that is a request, not a guarantee.
    first = corpus_prompts()[0]
    assert re.search(r"brace-expansion through 5\.0\.6", first.text)
