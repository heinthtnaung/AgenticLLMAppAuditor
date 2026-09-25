"""Which fences on the page print this tool's output, read off the page and the tool's command line.

A fence with no language is printed output, and the command it follows is the
nearest `bash` fence above it. When a line of that command starts the tool,
under the name `cli.arguments` gives it, the fence counts as this tool's output
and the command is read by the tool's own argument parser, so a test can ask
what kind of run it was without quoting a flag.
"""

import re
import shlex

from cli.arguments import PROGRAM, Options, parse_arguments

from readme_markers import FENCE, found_blocks, line_of

SHELL_LANGUAGE = "bash"
LINE_CONTINUATION = "\\\n"


def unmarked_tool_output(page: str) -> list[tuple[Options, ...]]:
    """Give the runs above each fence of this tool's output that carries no marker."""
    marked = {line for _, _, line in found_blocks(page)}
    return [
        runs_of(command)
        for command, output in outputs_with_commands(page)
        if runs_of(command) and line_of(page, output.start()) - 1 not in marked
    ]


def outputs_with_commands(page: str) -> list[tuple[str, re.Match]]:
    """Pair each fence of printed output with the body of the nearest shell fence above it."""
    pairs: list[tuple[str, re.Match]] = []
    command = ""
    for fence in FENCE.finditer(page):
        language = fence.group("language").strip()
        if language == SHELL_LANGUAGE:
            command = fence.group("body")
            continue
        if not language:
            pairs.append((command, fence))
    return pairs


def runs_of(command: str) -> tuple[Options, ...]:
    """Read each line of a shell fence that starts this tool into the options it runs with."""
    lines = command.replace(LINE_CONTINUATION, " ").splitlines()
    return tuple(
        parse_arguments(shlex.split(line)[1:]) for line in lines if line.split()[:1] == [PROGRAM]
    )
