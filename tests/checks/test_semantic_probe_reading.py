"""`read_verdict` and `template_text`: the two pure functions the probe rests on.

Split from `test_semantic_probe.py`, which is about what `run_over_repo` returns
for a whole app. These two are called directly, with no repository and no model
between the input and the answer, so a wrong verdict or a mis-read template shows
up here as itself rather than as a probe with a surprising outcome.

Both halves have one bias to defend against, and it is the same one: answering
`SAFE` for something nobody read. A reply carrying neither word is `None` rather
than "not vulnerable", and a template whose text was assembled out of sight is
`""` rather than a short harmless-looking string -- because "the model cleared
this template" is a claim, and a claim needs something behind it.

`template_text` still needs a file, because it reads a real `ast` tree -- the
tree of a file the test wrote into `tmp_path`, never of a repository this project
does not own.
"""

from checks import semantic_probe
from checks.semantic_probe import SAFE, VULNERABLE, read_verdict, template_text
from parsing.extractor_python import parse_file
from semantic_probe_fixtures import PROMPT_APP, PROMPT_LINE, TEMPLATE_TEXT, write_app

# The two well-formed answers, spelled here too: this file must stay readable
# without the sibling open beside it.
VULNERABLE_REPLY = "VULNERABLE\nThe {question} value is dropped straight into the instructions."
VULNERABLE_RATIONALE = "The {question} value is dropped straight into the instructions."
SAFE_REPLY = "SAFE\nThe template names no variable, so nothing external reaches it."
SAFE_RATIONALE = "The template names no variable, so nothing external reaches it."

# --- read_verdict ------------------------------------------------------------

def test_read_verdict_takes_the_word_from_the_first_line_and_the_reason_from_the_rest() -> None:
    """The two halves of the answer the prompt asks for, split where it asks for them."""
    assert read_verdict(VULNERABLE_REPLY) == (VULNERABLE, VULNERABLE_RATIONALE)


def test_read_verdict_reads_a_safe_answer_as_its_own_verdict_and_keeps_its_reasoning() -> None:
    """Guard: without this the split above would pass on a reader that always says VULNERABLE."""
    assert read_verdict(SAFE_REPLY) == (SAFE, SAFE_RATIONALE)


def test_read_verdict_ignores_the_case_the_model_answered_in() -> None:
    """Local models lowercase their own instructions often enough that this must not decide it."""
    assert read_verdict("vulnerable\nthe user's text becomes instructions") == (
        VULNERABLE, "the user's text becomes instructions")


def test_read_verdict_falls_back_to_the_first_line_when_there_is_no_second() -> None:
    """A one-word answer still carries something a reader can see beside the verdict."""
    assert read_verdict("VULNERABLE") == (VULNERABLE, "VULNERABLE")


def test_read_verdict_reads_a_verdict_the_model_fenced_its_answer_in() -> None:
    """qwen wraps answers in ``` constantly, which used to make the verdict line the second one."""
    assert read_verdict("```\nVULNERABLE\nthe question lands in the rules\n```") == (
        VULNERABLE, "the question lands in the rules")


def test_read_verdict_reads_a_verdict_the_model_put_a_preamble_in_front_of() -> None:
    """"Answer: SAFE" is an answer, and a first-word test threw it away as no answer at all."""
    assert read_verdict("Answer: SAFE") == (SAFE, "Answer: SAFE")
    assert read_verdict("The template is VULNERABLE") == (
        VULNERABLE, "The template is VULNERABLE")


def test_read_verdict_reads_not_vulnerable_as_the_opposite_of_vulnerable() -> None:
    """The word contains its own negation, so looking anywhere in the line has to survive this."""
    assert read_verdict("NOT VULNERABLE\nthe question is quoted") == (
        SAFE, "the question is quoted")


def test_read_verdict_returns_no_verdict_and_no_reason_for_an_empty_answer() -> None:
    """Nothing said, nothing recorded: `None` is a third answer, and never a clean bill."""
    assert read_verdict("   ") == (None, "")
    assert read_verdict("") == (None, "")


def test_read_verdict_returns_no_verdict_for_prose_that_answers_neither_word() -> None:
    """The prose is kept as evidence, but the closed question went unanswered."""
    prose = "I had a look at the template and it seems fine to me."
    assert read_verdict(prose) == (None, prose)


def test_read_verdict_refuses_to_parse_something_that_is_not_text() -> None:
    """A non-string arrives from a broken client, and must not raise on `.strip()`."""
    assert read_verdict(None) == (None, "")
    assert read_verdict(42) == (None, "")


def test_read_verdict_truncates_a_rambling_rationale_to_the_declared_limit() -> None:
    """The evidence line stays readable, and the cap is the module's constant, not a guess."""
    _verdict, rationale = read_verdict("VULNERABLE\n" + "x" * 1000)
    assert len(rationale) == semantic_probe.MAX_RATIONALE


# --- template_text -----------------------------------------------------------

def template_at(tmp_path, source: str, line: int) -> str:
    """Write the source and read the template off the tree at one line."""
    repo = write_app(tmp_path, source)
    return template_text(parse_file(repo / "agent.py"), line)


def test_template_text_returns_the_literal_written_at_that_line(tmp_path) -> None:
    """The text the model is shown is the text a reader sees in the file."""
    assert template_at(tmp_path, PROMPT_APP, PROMPT_LINE) == TEMPLATE_TEXT


def test_template_text_reads_a_template_split_across_adjacent_literals(tmp_path) -> None:
    """Python joins adjacent literals into one constant, so the whole instruction arrives."""
    source = (
        'prompt = build(\n'
        '    "You are a support agent. "\n'
        '    "Answer the question: {question}"\n'
        ')\n'
    )
    assert template_at(tmp_path, source, 1) == (
        "You are a support agent. Answer the question: {question}")


def test_template_text_joins_a_concatenation_with_nothing_between_the_halves(tmp_path) -> None:
    """Any separator this inserted would be a delimiter the template does not have.

    The question the model is asked is whether the two sides are separated. A
    newline between them answers it, in the template's favour, before it is put.
    """
    source = 'prompt = build("You are a support agent. " + "Answer: {question}")\n'
    assert template_at(tmp_path, source, 1) == "You are a support agent. Answer: {question}"


def test_template_text_keeps_an_f_strings_interpolation_point_as_a_placeholder(tmp_path) -> None:
    """The interpolated name is the subject of the question, so it survives into the text."""
    source = 'prompt = build(f"System: {role}. Reply to the user.")\n'
    assert template_at(tmp_path, source, 1) == "System: {role}. Reply to the user."


def test_template_text_keeps_a_concatenated_variable_as_a_placeholder(tmp_path) -> None:
    """The other way a value is dropped into instructions, and it reads the same way."""
    source = 'prompt = build("You are an agent. " + user_role + " Answer:")\n'
    assert template_at(tmp_path, source, 1) == "You are an agent. {user_role} Answer:"


def test_template_text_names_a_whole_interpolated_expression_not_just_a_variable(
        tmp_path) -> None:
    """LangGraph templates interpolate state, so the placeholder has to carry more than a name."""
    source = 'prompt = build(f"Context: {state[\'question\']}. Answer it.")\n'
    assert template_at(tmp_path, source, 1) == "Context: {state['question']}. Answer it."


def test_template_text_is_empty_when_the_expression_cannot_be_rebuilt(tmp_path) -> None:
    """A call, not a string: the text was assembled somewhere this cannot see."""
    source = 'prompt = build(open("prompt.txt").read())\n'
    assert template_at(tmp_path, source, 1) == ""


def test_template_text_is_empty_when_the_line_only_names_a_template_built_elsewhere(
        tmp_path) -> None:
    """A bare name is the whole template and none of its text, which concludes nothing.

    **Left failing on purpose.** `_render` answers `{TEMPLATE}` here, and
    `template_text` passes that on as readable text, so the model is shown a
    template consisting of one placeholder and asked whether a value sits in
    instruction text without a delimiter -- about instructions it was never
    shown. A `SAFE` verdict on that is exactly the unsupported clean bill the
    rest of this module was rewritten to stop writing.

    `{name}` is right *inside* an expression, where the literal text around it
    is what makes the question answerable. The fix is in `template_text`, not
    here: render as now, then answer "" when the rendered text is nothing but
    placeholders.
    """
    source = 'TEMPLATE = "hidden"\n\nprompt = build(TEMPLATE)\n'
    assert template_at(tmp_path, source, 3) == ""


def test_template_text_is_empty_when_nothing_at_all_sits_on_that_line(tmp_path) -> None:
    """A surface line the tree has no call or assignment for concludes nothing either."""
    source = 'prompt = build("You are a support agent. {question}")\n'
    assert template_at(tmp_path, source, 9) == ""


def test_template_text_ignores_a_whitespace_only_literal(tmp_path) -> None:
    """Blank text is not instructions, and would ask the model to judge nothing."""
    source = 'prompt = build("   ")\n'
    assert template_at(tmp_path, source, 1) == ""


def test_template_text_reads_the_call_on_the_line_rather_than_the_assignment_around_it(
        tmp_path) -> None:
    """The assignment's value is the call, and rendering that as a whole answers "".

    So the preference is what makes an assigned template readable at all, and a
    surface anchored on this line is exactly what the check is handed.
    """
    source = 'prompt = build(f"System: {role}.")\n'
    assert template_at(tmp_path, source, 1) == "System: {role}."


def test_template_text_reads_a_template_passed_by_keyword(tmp_path) -> None:
    """`from_template(template=...)` is the same template, written the other way round."""
    source = 'prompt = ChatPromptTemplate.from_template(template=f"System: {role}.")\n'
    assert template_at(tmp_path, source, 1) == "System: {role}."
