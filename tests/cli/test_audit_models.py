"""Guards on reading the weights and the server in an audit: a council run only, never a stop."""

from cli import audit as audit_module
from cli.arguments import TEXT_FORMAT, Options
from cli.audit import run_audit
from cli.model_identity import READ_TIMEOUT_SECONDS
from council.settings import current_settings
from council.transport import ModelUnavailable
from report.model_identity import (
    ESCALATION_ROLE,
    MEMBER_ROLE,
    ModelDigest,
    OllamaVersion,
    UnknownOllamaVersion,
)
from cli_samples import DATED, explaining_nothing, scanners_answering

SMALL = "845dbda0ea48ed749caafd9e6037047aa19acfcfd82e704d7ca97d631a0b697e"
OTHER = "a80c4f17acd55265feec403c7aef86be0c25983ab279d83f3bcd3abbcb5b8b72"
BIG = "c6eb396dbd5992bbe3f5cdb947e8bbc0ee413d7c17e2beaae69f5d569cf982eb"
HELD = {"small:1b": SMALL, "other:3b": OTHER, "big:27b": BIG}


def options_for(path, models=()) -> Options:
    """Build the options of a run naming these council members, or none."""
    return Options(repository=path, report_format=TEXT_FORMAT, council_models=tuple(models))


def serving(asked: list):
    """Build a fake server holding three models, noting every read made of it and its timeout."""

    def get(url, timeout):
        """Answer one read, noting it."""
        asked.append((url, timeout))
        if url.endswith("/api/version"):
            return {"version": "0.34.3"}
        return {"models": [{"name": name, "digest": digest} for name, digest in HELD.items()]}

    return get


def asking_nobody(findings, roster, **_) -> tuple:
    """Stand in for the council, which these tests do not need to hear from."""
    return ()


def test_a_council_run_records_the_server_s_version_and_each_model_s_digest(tmp_path, monkeypatch):
    asked, server = [], current_settings().server
    scanners_answering(monkeypatch)
    explaining_nothing(monkeypatch)
    monkeypatch.setattr(audit_module, "get_json", serving(asked))
    monkeypatch.setattr(audit_module, "escalation_model", lambda: "big:27b")
    monkeypatch.setattr(audit_module, "assessments", asking_nobody)
    report = run_audit(options_for(tmp_path, ("small:1b", "other:3b")), DATED)
    local = report.provenance.local_models
    assert local.ollama_version == OllamaVersion("0.34.3")
    assert local.models == (
        ModelDigest("small:1b", MEMBER_ROLE, SMALL),
        ModelDigest("other:3b", MEMBER_ROLE, OTHER),
        ModelDigest("big:27b", ESCALATION_ROLE, BIG),
    )
    assert asked == [
        (f"{server}/api/tags", READ_TIMEOUT_SECONDS),
        (f"{server}/api/version", READ_TIMEOUT_SECONDS),
    ]


def test_a_run_naming_no_member_reads_nothing_of_the_server(tmp_path, monkeypatch):
    asked = []
    scanners_answering(monkeypatch)
    monkeypatch.setattr(audit_module, "get_json", serving(asked))
    assert run_audit(options_for(tmp_path), DATED).provenance.local_models is None
    assert asked == []


def test_a_server_that_cannot_be_read_is_recorded_as_unread_and_the_audit_goes_on(
    tmp_path, monkeypatch
):
    def unreachable(url, timeout):
        """Fail as a server that is not there fails."""
        raise ModelUnavailable(f"{url} could not be reached: Connection refused")

    scanners_answering(monkeypatch)
    explaining_nothing(monkeypatch)
    monkeypatch.setattr(audit_module, "get_json", unreachable)
    monkeypatch.setattr(audit_module, "assessments", asking_nobody)
    report = run_audit(options_for(tmp_path, ("small:1b",)), DATED)
    assert isinstance(report.provenance.local_models.ollama_version, UnknownOllamaVersion)
    assert len(report.findings) == 1
