"""The fetcher launches git, with a scrubbed environment, and never the URL.

Split from test_no_write_commands.py, which owns the general rule that only two
modules may start a process at all. This file owns the fetcher's half of it,
because a URL is untrusted input and what reaches `subprocess.run` is the whole
of the trust boundary: the program name, and the environment it runs in.

Both are asserted over the source rather than by running anything -- a code
path not taken looks identical to one that does not exist.
"""

import ast
import os

import fetch_repo
from ast_scan import dotted_name, parse
from conftest import SRC_DIR
from fetch_repo import PROGRAM_NAME as FETCHER_PROGRAM
from test_no_write_commands import FETCHER_MODULE, PROCESS_LAUNCHERS


def launch_calls(module: str) -> list[ast.Call]:
    """Return every process-launching call one module makes."""
    tree = parse(SRC_DIR / module)
    return [node for node in ast.walk(tree)
            if isinstance(node, ast.Call) and dotted_name(node.func) in PROCESS_LAUNCHERS]


def test_the_fetcher_launches_git_and_never_the_url_it_was_given() -> None:
    """Its one launch names the program by constant, so a URL can never be argv[0].

    A URL is untrusted input. If it could reach the front of the argument list
    it would name the program to run, which is the whole of the `ext::` attack.
    """
    launches = launch_calls(FETCHER_MODULE)
    assert len(launches) == 1
    argv = launches[0].args[0]
    assert isinstance(argv, ast.List)
    assert dotted_name(argv.elts[0]) == "PROGRAM_NAME"
    assert FETCHER_PROGRAM == "git"


def test_the_fetcher_passes_a_scrubbed_environment() -> None:
    """It hands subprocess an explicit env, so no git config is inherited.

    Without this, an `insteadOf` line in ~/.gitconfig rewrites a URL that has
    already passed validation -- the URL check alone does not hold.
    """
    keywords = {word.arg: word.value for word in launch_calls(FETCHER_MODULE)[0].keywords}
    assert "env" in keywords, "the fetcher must pass an explicit environment"
    assert dotted_name(keywords["env"].func) == "_environment"
    # And what that function returns, because the structural half above passes
    # just as happily if it is rewritten to hand back os.environ.
    assert fetch_repo._environment() == {
        "PATH": os.environ.get("PATH", fetch_repo.DEFAULT_PATH),
        "GIT_CONFIG_GLOBAL": os.devnull,
        "GIT_CONFIG_SYSTEM": os.devnull,
        "GIT_TERMINAL_PROMPT": "0",
    }


