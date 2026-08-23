"""Each detector reports only its own surface kind and ignores the other three."""

import pytest
from detector_helpers import (
    FILE,
    AGENT_SOURCE,
    BOTH_ROUTES_SOURCE,
    DATA_SOURCE_SOURCE,
    NON_TEXT_PROMPT_SOURCE,
    PROMPT_CALL_SOURCE,
    PROMPT_CONCAT_SOURCE,
    PROMPT_FORMAT_SOURCE,
    PROMPT_STRING_SOURCE,
    ROUTE_SOURCE,
    TOOL_CONSTRUCTOR_SOURCE,
    TOOL_DECORATOR_SOURCE,
    TOOL_SUBCLASS_SOURCE,
    other_detectors,
    parse,
)
from detectors import (
    find_agent_defs,
    find_data_sources,
    find_prompt_templates,
    find_tool_calls,
)

@pytest.mark.parametrize(
    "detector, source",
    [
        (find_prompt_templates, PROMPT_CALL_SOURCE),
        (find_prompt_templates, PROMPT_STRING_SOURCE),
        (find_agent_defs, AGENT_SOURCE),
        (find_tool_calls, TOOL_DECORATOR_SOURCE),
        (find_tool_calls, TOOL_CONSTRUCTOR_SOURCE),
        (find_tool_calls, TOOL_SUBCLASS_SOURCE),
        (find_data_sources, DATA_SOURCE_SOURCE),
        (find_data_sources, ROUTE_SOURCE),
    ],
)
def test_other_detectors_ignore_this_construct(detector, source: str) -> None:
    """Only the owning detector reports a construct; the other three return nothing."""
    tree = parse(source)
    found = {other.__name__: other(tree, FILE) for other in other_detectors(detector)}
    assert not [name for name, surfaces in found.items() if surfaces], found


