"""Finds tools holding more privilege than their purpose needs.

The rule, written before the code so it is visible rather than fitted to one
fixture: a tool surface is over-privileged when its class grants a capability
-- a shell, an interpreter, outbound HTTP -- that an agent tool does not need
in order to answer a question. Those classes are named in
`HIGH_PRIVILEGE_TOOLS`, and naming them is the whole judgement; there is no
inference here.
"""

from artifacts.finding import STATIC, Finding
from artifacts.surface import TOOL_CALL
from detectors.detector_names import HIGH_PRIVILEGE_TOOLS

CHECK_NAME = "high_privilege_tool"

# LLM06 in the 2025 OWASP list: excessive agency and unsafe tool use.
OWASP_ID = "LLM06"

TITLE = "Agent tool grants shell, interpreter or network access"


def find_over_privileged_tools(surfaces: list) -> list[Finding]:
    """Report every tool surface whose class carries a high-privilege capability.

    Note what this does not find. An ordinary tool that accepts an identifier
    without checking who asked for it is also excessive agency, and the corpus
    grades one -- but that is a missing authorisation check, not a privileged
    class, and seeing it needs the dataflow the taint probe builds.
    """
    return [
        Finding(
            OWASP_ID, CHECK_NAME, TITLE, STATIC,
            surface_id=surface.id, surface_kind=surface.kind,
            surface_name=surface.name, file=surface.file, line=surface.line,
        )
        for surface in surfaces
        if surface.kind == TOOL_CALL and surface.name in HIGH_PRIVILEGE_TOOLS
    ]
