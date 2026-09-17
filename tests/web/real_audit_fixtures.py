"""Staging for one *real* audit driven through the endpoint, with nothing left outside.

Two files need it and a second copy is how the two would start auditing
different things: `test_api_audit.py`, which asserts what the reply says about a
run that really happened, and `test_auditor_not_in_artifacts.py`, which sweeps
the files that run wrote. Both need the same tree, the same replaced stages and
the same working directory.

**Only the stages that would leave this process are replaced.** The fetch (which
would clone), the publish stage (which would want a PDF renderer), the model,
Syft and Trivy -- and `forbid_subprocesses` turns any remaining attempt to start
one into a test failure. Everything between those seams is the real audit: the
extractor, the checks, the documents and `outputs.write_all` all run, which is
what makes a sweep of the written files mean anything.

What the synthetic tree costs is worth saying, because it is weaker than a real
repository: nothing in `mixed_app_fixtures` is oversized, non-UTF-8, malformed
or shaped in a way nobody foresaw, so a defect that only appears on an
unforeseen repository is not caught through this.

It imports fastapi indirectly through nothing at all -- there is no server
package here -- but its callers drive an endpoint, so they skip on the web extra
before importing this.
"""

from pathlib import Path

import pytest

from cli_helpers import (
    EMPTY_SCAN, forbid_subprocesses, stub_knowledge, stub_model, stub_syft)
from mixed_app_fixtures import APP_NAME, write_mixed_app
from pipeline_helpers import point_download_root, record_fetch, record_publish

# The link the page posts. The last segment is the directory name the fetch
# stage would land on, so it matches the app the stubbed fetch hands back.
URL = f"https://example.invalid/owner/{APP_NAME}"


def stub_every_outside_stage(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    """Write the app to audit, replace every stage that would leave this process.

    Returns the repository written, so a caller can read the source the audit
    was given. The `chdir` is not tidiness: the request carries no artifacts
    directory -- the page cannot name one -- so the run uses
    `main.DEFAULT_ARTIFACTS_DIR`, which is relative, and without it the audit
    would write into the checkout's own `artifacts/`.
    """
    repo = write_mixed_app(tmp_path)
    stub_model(monkeypatch)
    stub_knowledge(monkeypatch)
    stub_syft(monkeypatch, EMPTY_SCAN)
    point_download_root(monkeypatch, tmp_path)
    record_fetch(monkeypatch, result=repo)
    record_publish(monkeypatch)
    forbid_subprocesses(monkeypatch)
    monkeypatch.chdir(tmp_path)
    return repo
