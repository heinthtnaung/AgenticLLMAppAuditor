"""The advisory runner launches Trivy, offline by flags, and nothing else.

Split the way test_fetch_launch.py is: test_no_write_commands.py owns the rule
that only three modules start a process; this file owns Trivy's half of it.
The flags are the offline guarantee -- a blocked socket in this process proves
nothing about a subprocess -- so they are asserted by value, the same way
Syft's SYFT_CHECK_FOR_APP_UPDATE is.
"""

import ast

from ast_scan import dotted_name, parse
from conftest import SRC_DIR
from deps.trivy_runner import GENERATOR_NAME, SCAN_ARGUMENTS
from test_no_write_commands import ADVISORY_MODULE, PROCESS_LAUNCHERS

# Every switch that keeps a scan off the network, each one load-bearing.
OFFLINE_FLAGS = (
    "--skip-db-update", "--skip-java-db-update", "--skip-check-update",
    "--offline-scan", "--disable-telemetry", "--skip-version-check",
)


def launch_calls() -> list[ast.Call]:
    """Return every process-launching call the advisory runner makes."""
    tree = parse(SRC_DIR / ADVISORY_MODULE)
    return [node for node in ast.walk(tree)
            if isinstance(node, ast.Call) and dotted_name(node.func) in PROCESS_LAUNCHERS]


def test_the_advisory_runner_launches_trivy_and_nothing_else() -> None:
    """Its one launch names the program by constant, never by anything computed."""
    launches = launch_calls()
    assert len(launches) == 1
    argv = launches[0].args[0]
    assert isinstance(argv, ast.List)
    assert dotted_name(argv.elts[0]) == "GENERATOR_NAME"
    assert GENERATOR_NAME == "trivy"


def test_every_scan_carries_every_offline_flag() -> None:
    """The database update, rego update, version check and telemetry: all off, by name."""
    for flag in OFFLINE_FLAGS:
        assert flag in SCAN_ARGUMENTS, f"a Trivy scan without {flag} may reach the network"


def test_the_runner_passes_a_minimal_environment() -> None:
    """PATH and nothing else, so no inherited setting can switch a network path on.

    By value, not just by shape: an `env=os.environ` would satisfy a
    keyword-exists check while inheriting every proxy and cache setting.
    """
    launch = launch_calls()[0]
    keywords = {word.arg: word.value for word in launch.keywords}
    assert "env" in keywords
    env = keywords["env"]
    assert isinstance(env, ast.Dict)
    keys = [key.value for key in env.keys if isinstance(key, ast.Constant)]
    assert keys == ["PATH"], f"the runner's env must hold PATH alone, got {keys}"
