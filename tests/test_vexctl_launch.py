"""The emitter launches vexctl, deterministically, and can never claim not_affected.

Split the way test_advisory_launch.py is: test_no_write_commands.py owns the
rule that only four modules start a process; this file owns vexctl's half.

Two properties live here and both are asserted over the source, because a code
path not taken looks identical to one that does not exist:

**Determinism.** The child environment is exactly PATH, TZ and
SOURCE_DATE_EPOCH. TZ is load-bearing rather than tidy -- one OpenVEX field
renders in the local offset without it, so two machines would produce
different bytes from identical findings.

**The measured bound.** This project may say a component is `affected` (an LLM
surface reaches it) or `under_investigation` (it carries an advisory but no
surface reaches it, so exploitability is not assessed) -- but it must never say
`not_affected`: `mapping.json` holds one entry per LLM surface, so "no surface
reaches it" is not "the vulnerable code is unreachable", and `not_affected`
would suppress a real vulnerability. `not_affected` and its two companion
fields are therefore unrepresentable, and that is asserted rather than left to
the emitter's good intentions.
"""

import ast
import shutil

import emit_vex
from ast_scan import dotted_name, modules_using_value, parse
from conftest import SRC_DIR
from emit_vex import PROGRAM_NAME, _environment
from test_no_write_commands import EMITTER_MODULE, PROCESS_LAUNCHERS

# The environment vexctl is given, and the whole of it.
EXPECTED_ENVIRONMENT = ("PATH", "SOURCE_DATE_EPOCH", "TZ")

# What a not_affected claim needs. None may appear anywhere under src/: the
# status itself, and the two fields OpenVEX allows only alongside it.
FORBIDDEN_CLAIMS = ("not_affected", "--justification", "--impact-statement")

PLANTED_CLAIM = 'ARGUMENTS = ["--status", "not_affected"]\n'


def launch_calls() -> list[ast.Call]:
    """Return every process-launching call the emitter makes."""
    tree = parse(SRC_DIR / EMITTER_MODULE)
    return [node for node in ast.walk(tree)
            if isinstance(node, ast.Call) and dotted_name(node.func) in PROCESS_LAUNCHERS]


def test_the_emitter_launches_vexctl_and_nothing_else() -> None:
    """Its one launch names the program by constant, never by anything computed."""
    launches = launch_calls()
    assert len(launches) == 1
    argv = launches[0].args[0]
    assert isinstance(argv, ast.List)
    assert dotted_name(argv.elts[0]) == "PROGRAM_NAME"
    assert PROGRAM_NAME == "vexctl"


def test_the_child_environment_is_exactly_what_determinism_needs() -> None:
    """By value: an inherited environment would pass a keyword-exists check."""
    keywords = {word.arg for word in launch_calls()[0].keywords}
    assert "env" in keywords
    assert tuple(sorted(_environment("0"))) == EXPECTED_ENVIRONMENT
    assert _environment("0")["TZ"] == "UTC", "without UTC one field renders a local offset"
    assert _environment("1700000000")["SOURCE_DATE_EPOCH"] == "1700000000"


def test_no_module_can_state_that_something_is_not_affected() -> None:
    """The measured bound, enforced: surface reachability never proves unreachability."""
    for claim in FORBIDDEN_CLAIMS:
        assert modules_using_value(claim) == set(), \
            f"a module passes {claim!r} as a value, asserting what the mapping cannot support"


def test_that_ban_would_notice_a_module_that_broke_it(tmp_path) -> None:
    """The check above is only worth having if it fires, so plant a claim and see."""
    planted = tmp_path / "claimer.py"
    planted.write_text(PLANTED_CLAIM, encoding="utf-8")
    assert modules_using_value("not_affected", tmp_path) == {"claimer.py"}


def test_a_docstring_explaining_the_refusal_is_not_a_violation(tmp_path) -> None:
    """Guard on the guard: prose about the ban must not read as breaking it."""
    prose = tmp_path / "explainer.py"
    prose.write_text('"""This project never claims not_affected."""\n', encoding="utf-8")
    assert modules_using_value("not_affected", tmp_path) == set()


def test_is_available_says_yes_when_vexctl_is_on_the_path(monkeypatch) -> None:
    """`which` finding the program is the whole answer, so no process ever starts."""
    monkeypatch.setattr(shutil, "which", lambda program: f"/usr/bin/{program}")
    assert emit_vex.is_available()


def test_is_available_says_no_when_vexctl_is_absent(monkeypatch) -> None:
    """A missing tool is a plain False, which is what lets a caller skip, not crash."""
    monkeypatch.setattr(shutil, "which", lambda program: None)
    assert not emit_vex.is_available()
