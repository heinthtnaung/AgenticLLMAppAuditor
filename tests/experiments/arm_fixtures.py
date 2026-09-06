"""Arms shaped the way `compare_models._arm` returns them, built without a model.

Every test in this folder needs the same thing: one arm of a comparison, as the
dict `_arm` hands back -- a model name, a verdict per subject, the reason and
the detail behind each verdict, and the exposure ledger's summary. Building that
by hand in five files is how the five copies start disagreeing, so it is built
here once.

The six probe states below are the *only* ones the semantic probe can reach, and
the reasons are spelled from that module's own constants; the detail
sentences are copies, and only `STATIC_REFUTATION` is joined on: a reason
string edited in `checks/semantic_probe.py` must move these with it. What this
file cannot give is a real run -- no model answers here, and no repository is
read. `test_prompt_labelling_seam.py` is the test that pays that price.
"""

from agreement import partition
from artifacts.finding import CONFIRMED, INCONCLUSIVE, NOT_RUN, REFUTED
from checks.semantic_probe import NO_MODEL, NO_TEXT, SAFE, STATIC_REFUTATION, VULNERABLE
from compare_models import SCHEMA_VERSION

# The two arms every test names, spelled the way the study spells them: the
# local model by its Ollama tag and the hosted one by its provider path.
LOCAL = "qwen2.5-coder:7b-instruct"
HOSTED = "z-ai/glm-5.2"

# Four subject ids, spelled like the surface ids the probe reports. Here rather
# than in each test file, which is how three copies of them started drifting.
FIRST = "agent.py:5:PROMPT_TEMPLATE:ChatPromptTemplate.from_template"
SECOND = "agent.py:9:PROMPT_TEMPLATE:PromptTemplate.from_template"
THIRD = "tools.py:3:PROMPT_TEMPLATE:ChatPromptTemplate.from_template"
FOURTH = "tools.py:8:PROMPT_TEMPLATE:PromptTemplate.from_template"

# One probe's outcome, the reason it carries (None when a model concluded it),
# and the detail text. `agreement.reason_without_a_model` reads all three.
State = tuple[str, str | None, str]

# The four states reached without asking a model, in the probe's own words.
TEXT_NOT_LITERAL_STATE: State = (
    INCONCLUSIVE, NO_TEXT, "the template's text is not written literally at this line")
INTERPOLATES_NOTHING_STATE: State = (REFUTED, None, STATIC_REFUTATION)
MODEL_UNREACHABLE_STATE: State = (
    NOT_RUN, NO_MODEL, "the model could not be reached: connection refused")
ANSWERED_UNUSABLY_STATE: State = (
    INCONCLUSIVE, NO_MODEL, f"the model answered neither {VULNERABLE} nor {SAFE}: (nothing)")

# The two states a model actually answered. The cleared detail is deliberately
# not `STATIC_REFUTATION`: that sentence is what marks a refutation reached
# without a model, so reusing it here would make a real answer read as an
# exclusion and quietly empty the buckets under test.
FLAGGED_STATE: State = (
    CONFIRMED, None, "the question is dropped straight into the instruction text")
CLEARED_STATE: State = (REFUTED, None, "the model read the template as structurally safe")

# Defaults for an arm whose exposure is not what the test is about.
DEFAULT_SECONDS = 1.5
DEFAULT_REQUESTS = 1
DEFAULT_BYTES = 100
DEFAULT_FIELD_KINDS = ("prompt template source text",)

# Stated, never measured, and carried verbatim into the rendered page.
UNMEASURABLE_STAND_IN = ("provider retention period",)


def arm(model: str, states: dict[str, State], seconds: float = DEFAULT_SECONDS,
        requests: int = DEFAULT_REQUESTS, bytes_sent: int = DEFAULT_BYTES,
        field_kinds: tuple[str, ...] = DEFAULT_FIELD_KINDS) -> dict:
    """One arm of a comparison, from a map of subject to probe state."""
    return {
        "model": model,
        "seconds": seconds,
        "verdicts": {subject: state[0] for subject, state in states.items()},
        "reasons": {subject: state[1] for subject, state in states.items()},
        "details": {subject: state[2] for subject, state in states.items()},
        "findings": [],
        "exposure": {"requests": requests, "bytes_sent": bytes_sent,
                     "prompt_kinds": [], "field_kinds_transmitted": list(field_kinds)},
    }


def study_result(arms: list[dict], repository: str = "/tmp/study-app") -> dict:
    """The document `compare()` assembles, with the real partition and no model calls.

    `partition` is the real one on purpose: a report test that sorted the
    subjects itself would be checking the report against a second implementation
    of the rule instead of against the one that ships.
    """
    return {"schema_version": SCHEMA_VERSION, "repository": repository, "arms": arms,
            **partition(arms), "unmeasurable_exposure": list(UNMEASURABLE_STAND_IN)}
