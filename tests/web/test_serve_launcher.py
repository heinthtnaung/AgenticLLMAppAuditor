"""What the launcher actually does when it is run: where it listens, and from where.

`test_server_settings.py` reads `serve.BIND_HOST` as a constant. This file calls
`main()` with `uvicorn.run` replaced by a recorder and asserts what the launcher
did with it, which is the half a constant cannot show: a bind address named and
not passed is a comment.

The working directory is the second decision, and it is not tidiness. An audit
writes `artifacts/<app>/` and `fetched/<app>/` relative to the process's own
directory, and both are ignored *in this repository*. Started from anywhere
else, the server would scatter a third-party application's findings -- and a
clone of its source -- into an untracked directory beside whatever the user
happened to `cd` into, and the next `git status` there would offer them for
commit.

**The run history is the third decision, and it is measured in a subprocess.**
`web/api.py` opens `runs/history.sqlite3` at *import*, against a relative
directory, and `serve.main()` chdirs only when it is called -- so where that
file lands is decided before the launcher runs, and cannot be observed in this
process at all: this suite has already imported `api`, and
`tests/web/__init__.py` deliberately points that import at a throwaway
directory. The last test starts a fresh interpreter from somewhere else and asks
the wrapper where its store is, which is the only way to see what a user
launching from their home directory would get.

Nothing here binds a port. `uvicorn.run` is the one call that would open a
listening socket and it never runs; the recorder standing in for it notes the
directory it was called from, which is the fact under test. The launch
directory is changed with `monkeypatch.chdir`, which restores it however the
test ends -- including when it fails.

The file skips without the server packages: `serve.py` imports uvicorn at
module scope, so with no web extra there is no launcher to call.
"""

import json
import subprocess
import sys
from pathlib import Path

import pytest

pytest.importorskip("fastapi", reason="the web extra is not installed, so there is no server")
pytest.importorskip("uvicorn", reason="the web extra is not installed, so there is no server")

import api      # noqa: E402
import serve    # noqa: E402
from conftest import REPO_ROOT  # noqa: E402

# The only address this endpoint may listen on, spelled here rather than read
# off `serve` so the assertion is not the constant agreeing with itself.
LOOPBACK_HOST = "127.0.0.1"

# What a launcher that got as far as serving returns.
SUCCESS = 0

# A directory a user might plausibly have started the server from.
ELSEWHERE = "some-other-checkout"

# Asks the wrapper, in a fresh interpreter, where the run history it opened is.
# Imports `serve` rather than `api`, because `serve` is what the documented
# launch command runs and it pulls `api` in itself.
STORE_PROBE = (
    "import json, sys\n"
    "sys.path.insert(0, sys.argv[1])\n"
    "import serve, api\n"
    "print(json.dumps({'store': str(api.STORE.path)}))\n"
)


def launch_from(monkeypatch: pytest.MonkeyPatch, directory: Path) -> dict:
    """Run the launcher from a directory, with the socket call recorded instead of made."""
    served: dict = {}

    def fake_uvicorn_run(application, host: str, port: int) -> None:
        """Record what would have been served, from where, instead of binding a port."""
        served.update(application=application, host=host, port=port, cwd=Path.cwd())

    monkeypatch.setattr(serve.uvicorn, "run", fake_uvicorn_run)
    directory.mkdir(exist_ok=True)
    monkeypatch.chdir(directory)
    served["returned"] = serve.main()
    return served


def test_the_launcher_serves_the_api_application(monkeypatch, tmp_path) -> None:
    """The launcher hands uvicorn the wrapper's own app, not one of its own making."""
    assert launch_from(monkeypatch, tmp_path / ELSEWHERE)["application"] is api.app


def test_the_launcher_binds_loopback_and_the_port_it_names(monkeypatch, tmp_path) -> None:
    """The address is passed, not merely declared: an unpublished port is the whole control."""
    served = launch_from(monkeypatch, tmp_path / ELSEWHERE)
    assert served["host"] == LOOPBACK_HOST
    assert served["port"] == serve.BIND_PORT


def test_the_server_runs_from_the_repository_root(monkeypatch, tmp_path) -> None:
    """An audit's `artifacts/` and `fetched/` land here, wherever the server was started.

    The directory is read inside the recorder, so this says the move happened
    *before* the server was handed the application -- not merely that it
    happened at some point during the call.
    """
    started_from = tmp_path / ELSEWHERE
    served = launch_from(monkeypatch, started_from)
    assert served["cwd"] == serve.REPO_ROOT
    assert served["cwd"] != started_from


def test_the_launcher_leaves_the_process_in_the_repository_root(monkeypatch,
                                                                tmp_path) -> None:
    """`uvicorn.run` blocks, and every audit it serves runs in this same process."""
    launch_from(monkeypatch, tmp_path / ELSEWHERE)
    assert Path.cwd() == serve.REPO_ROOT


def test_the_root_the_launcher_moves_to_is_this_repository() -> None:
    """Non-vacuity: `parents[1]` of `web/serve.py` is the checkout, not some parent of it."""
    assert serve.REPO_ROOT == REPO_ROOT
    assert (serve.REPO_ROOT / "src").is_dir()


def test_the_launcher_reports_success(monkeypatch, tmp_path) -> None:
    """`main` is the process exit code, so a served run must be a zero."""
    assert launch_from(monkeypatch, tmp_path / ELSEWHERE)["returned"] == SUCCESS


def store_path_when_launched_from(started_in: Path) -> Path:
    """Where a fresh interpreter's wrapper put its run history, started from there."""
    finished = subprocess.run(
        [sys.executable, "-c", STORE_PROBE, str(REPO_ROOT / "web")],
        cwd=started_in, capture_output=True, text=True, check=False)
    assert finished.returncode == 0, f"the probe could not import the wrapper:\n{finished.stderr}"
    return Path(json.loads(finished.stdout)["store"])


def test_the_run_history_lands_in_the_repository_wherever_the_server_started(tmp_path) -> None:
    """The reason `main` chdirs at all, applied to the one durable file this project owns.

    `serve.py` moves to the repository root so that a third-party application's
    findings and a clone of its source do not land in whatever directory the
    user happened to be in. The run history holds every repository URL anyone
    audited and the findings of every finished run -- the same class of content,
    in a file that outlives `artifacts/` -- so it belongs under the same rule.
    """
    started_from = tmp_path / ELSEWHERE
    started_from.mkdir()
    assert store_path_when_launched_from(started_from).parent.parent == serve.REPO_ROOT
