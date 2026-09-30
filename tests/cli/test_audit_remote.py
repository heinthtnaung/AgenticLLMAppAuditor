"""Guards on an audit whose server is elsewhere: every call goes there, and the record says so.

Nothing is sent: `council.transport.fetch_json`, which every generation and both
reads of the server go through, is answered here, and `tests/conftest.py`
refuses a request to any machine but this one besides.
"""

import json
from itertools import chain

from cli import audit as audit_module
from cli.arguments import TEXT_FORMAT, Options
from cli.audit import run_audit
from cli_samples import DATED, QUOTATION, scanners_answering
from council import transport
from council.ollama import GENERATE_PATH
from report.html_report import as_html
from report.json_report import as_json
from report.text_report import as_text

MEMBERS = ("small:1b", "other:3b")
BIG = "big:27b"
DIGESTS = {
    "small:1b": "845dbda0ea48ed74", "other:3b": "a80c4f17acd55265", "big:27b": "c6eb396dbd59",
}
DECLINED = json.dumps({"value": "NO_EVIDENCE", "evidence": ""})
EXPLAINED = json.dumps(
    {"items": [{"metric": "C", "why": "It names no data.", "quotation": QUOTATION}]}
)
MODELS_LINE = (
    "models: small:1b 845dbda0ea48, other:3b a80c4f17acd5, big:27b (escalation) c6eb396dbd59; "
    "Ollama 0.34.3"
)


def serving(sent: list):
    """Stand in for the one model server, noting the URL and model of every request."""

    def fetch(url, request, timeout):
        """Answer a read or a generation: members decline, so the escalation model is asked."""
        payload = json.loads(request.data) if hasattr(request, "data") else {}
        sent.append((url, payload.get("model", "")))
        if url.endswith("/api/version"):
            return {"version": "0.34.3"}
        if url.endswith("/api/tags"):
            return {"models": [{"name": name, "digest": held} for name, held in DIGESTS.items()]}
        said = EXPLAINED if "explain why" in payload["system"] else DECLINED
        return {"model": payload["model"], "response": said, "done_reason": "stop"}

    return fetch


def audited(tmp_path, monkeypatch) -> tuple[list, object]:
    """Audit with two members and an escalation model, every call answered by the fake server."""
    sent = []
    scanners_answering(monkeypatch)
    monkeypatch.setattr(audit_module, "get_json", transport.get_json)
    monkeypatch.setattr(audit_module, "escalation_model", lambda: BIG)
    monkeypatch.setattr(transport, "fetch_json", serving(sent))
    options = Options(repository=tmp_path, report_format=TEXT_FORMAT, council_models=MEMBERS)
    return sent, run_audit(options, DATED)


def values_of(document, key: str) -> list:
    """Give every value a key holds anywhere in a JSON document, however deep."""
    if isinstance(document, list):
        return list(chain.from_iterable(values_of(one, key) for one in document))
    if not isinstance(document, dict):
        return []
    here = [document[key]] if key in document else []
    return here + values_of(list(document.values()), key)


def test_every_call_goes_to_the_one_server_elsewhere(tmp_path, monkeypatch, remote_server):
    sent, _ = audited(tmp_path, monkeypatch)
    assert {url for url, _ in sent} == {
        f"{remote_server}/api/tags",
        f"{remote_server}/api/version",
        f"{remote_server}{GENERATE_PATH}",
    }
    # The members, then the escalation model on every metric both ways, then the explainer.
    asked = [model for url, model in sent if url.endswith(GENERATE_PATH)]
    assert (asked.count("small:1b"), asked.count("other:3b"), asked.count(BIG)) == (16, 16, 17)


def test_the_record_names_the_host_and_no_member_ran_local(tmp_path, monkeypatch, remote_server):
    _, report = audited(tmp_path, monkeypatch)
    written = json.loads(as_json(report))
    local = written["run"]["local_models"]
    assert (local["server"], local["remote_host"]) == (remote_server, "192.0.2.15")
    assert list(local)[:2] == ["server", "remote_host"]
    ran_local = values_of(written, "ran_local")
    assert len(ran_local) == 2 * 8 + 8 and not any(ran_local)
    explained = written["findings"][0]["llm_explanation"]
    assert (explained["assessed"], explained["model"]) == (True, BIG)


def test_the_models_line_says_the_server_is_not_this_machine(tmp_path, monkeypatch, remote_server):
    _, report = audited(tmp_path, monkeypatch)
    said = f"{MODELS_LINE} on 192.0.2.15, not this machine"
    assert f"  {said}\n" in as_text(report)
    assert f'<p class="meta">{said}</p>' in as_html(report)


def test_on_this_machine_the_record_names_no_host_and_the_line_is_as_it_was(tmp_path, monkeypatch):
    sent, report = audited(tmp_path, monkeypatch)
    assert all(url.startswith("http://127.0.0.1:11434/") for url, _ in sent)
    written = json.loads(as_json(report))
    assert "remote_host" not in written["run"]["local_models"]
    assert all(values_of(written, "ran_local"))
    assert f"  {MODELS_LINE}\n" in as_text(report)
    assert f'<p class="meta">{MODELS_LINE}</p>' in as_html(report)


def test_a_run_elsewhere_is_still_recorded_under_local_models(tmp_path, monkeypatch, remote_server):
    # A misnomer kept on purpose: renaming the key would break every reader of the record.
    _, report = audited(tmp_path, monkeypatch)
    assert "local_models" in json.loads(as_json(report))["run"]
