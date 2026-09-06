"""A whole audit through `main.run` reaches the local model server and nothing else.

`tests/parsing/test_offline.py` blocks the socket around extraction, the
mapping and the audit graph. None of those is the command a person types, and
the guarantee got narrower on 2026-09-06: `cloud_client.py` joined
`model_client.py` in `test_offline_containment.py`'s `NETWORK_MODULES`, so
"only one module in `src/` can open a connection" is no longer the sentence.
What is left is "an ordinary audit reaches Ollama and no other host", and this
file is what holds that -- through `build_parser` and `run`, the real entry
point, with and without `--semantic-probe`.

Every recorded attempt is asserted to carry the port `AUDITOR_SERVER_URL`
names, so a connection to a hosted API on 443 fails this whether or not anyone
thought to name that host. The counts are literals, because a run that reached
no server at all would satisfy "every attempt was Ollama's" trivially.

Nothing is stubbed except the knowledge base: an index this machine happens to
have built would add embed calls to the counts below and make them depend on
who is running the suite. The model client is deliberately left real -- these
tests are about which socket it opens, so replacing it would remove the
subject.
"""

import sys
from pathlib import Path
from urllib.parse import urlsplit

import main
import model_client
from checks.auditability import CHECK_NAME as AUDITABILITY_CHECK
from checks.output_handling import CHECK_NAME as QUERY_CHECK
from checks.permissions import CHECK_NAME as PERMISSION_CHECK
from checks.semantic_probe import CHECK_NAME as PROBE_CHECK, NO_MODEL
from checks.taint import CHECK_NAME as TAINT_CHECK
from cli_helpers import read_artifact, stub_knowledge
from mixed_app_fixtures import APP_NAME, write_mixed_app
from offline_fixtures import no_network  # noqa: F401  (used as a fixture)
from outputs import FINDINGS_NAME

# The only endpoint an audit may reach, read from the setting that names it
# rather than respelled -- a machine with AUDITOR_SERVER_URL on another port is
# still offline, and this must not fail on it.
OLLAMA_PORT = urlsplit(model_client.SERVER_URL).port

# The mixed app carries no dependency manifest, so no bill of materials is
# built, the supply-chain check has no mapping to examine, and four of the five
# checks report. Named here rather than imported: `MIXED_APP_FINDINGS` counts
# the five a mapped run produces, which is a different run from this one.
OFFLINE_RULE_IDS = sorted(
    [PERMISSION_CHECK, TAINT_CHECK, QUERY_CHECK, AUDITABILITY_CHECK])

# One call: `outputs.build_remediation` asks for the model's digest before it
# advises, and the refusal that comes back degrades every advice entry.
DEFAULT_RUN_ATTEMPTS = 1

# `--semantic-probe` adds the digest `main.local_model` asks for, the planner's
# check order, one verdict on the app's one prompt template, and one advice
# call per finding -- the advice arrives through the advisor seam, which asks
# the model directly instead of taking the digest first.
PROBE_RUN_ATTEMPTS = 1 + 1 + 1 + len(OFFLINE_RULE_IDS)

# The two modules `--compare-models` pulls in. An ordinary audit must load
# neither, which is why `main.run` imports `compare_run` inside the branch.
COMPARISON_MODULES = ("compare_run", "cloud_client")


def audit(monkeypatch, tmp_path: Path, flags: tuple[str, ...] = ()) -> Path:
    """Run the real entry point over a freshly written app; return its artifact directory."""
    stub_knowledge(monkeypatch)
    repo = write_mixed_app(tmp_path)
    artifacts = tmp_path / "artifacts"
    args = main.build_parser().parse_args(
        [str(repo), "--artifacts-dir", str(artifacts), *flags])
    assert main.run(args) == 0
    return artifacts


def attempted_ports(blocked) -> set[int]:
    """The port of every outbound connection the run tried to open."""
    return {address[1] for address in blocked.attempts}


def forget_the_comparison_modules(monkeypatch) -> None:
    """Unload the two `--compare-models` modules, so a later import is this run's."""
    for name in COMPARISON_MODULES:
        monkeypatch.delitem(sys.modules, name, raising=False)


def test_the_port_asserted_against_is_the_one_the_client_is_configured_with() -> None:
    """Guard: a URL with no port would make every assertion below compare against None."""
    assert isinstance(OLLAMA_PORT, int)


def test_a_default_audit_reaches_only_the_local_model_server(
        monkeypatch, tmp_path, no_network) -> None:
    """The command a person types, with every socket refused: one call, to Ollama's port."""
    audit(monkeypatch, tmp_path)
    assert attempted_ports(no_network) == {OLLAMA_PORT}
    assert len(no_network.attempts) == DEFAULT_RUN_ATTEMPTS


def test_that_default_audit_really_audited_something(monkeypatch, tmp_path, no_network) -> None:
    """Guard: a run that found nothing would pass the count above having done nothing."""
    document = read_artifact(audit(monkeypatch, tmp_path), APP_NAME, FINDINGS_NAME)
    assert sorted(f["rule_id"] for f in document["findings"]) == OFFLINE_RULE_IDS


def test_a_probed_audit_reaches_only_the_local_model_server(
        monkeypatch, tmp_path, no_network) -> None:
    """The flag that turns the model on adds calls, and every one of them is local."""
    audit(monkeypatch, tmp_path, ("--semantic-probe",))
    assert attempted_ports(no_network) == {OLLAMA_PORT}
    assert len(no_network.attempts) == PROBE_RUN_ATTEMPTS


def test_that_probed_audit_really_put_a_template_to_the_model(
        monkeypatch, tmp_path, no_network) -> None:
    """Guard: the count above is only meaningful if the probe was reached and refused."""
    document = read_artifact(audit(monkeypatch, tmp_path, ("--semantic-probe",)),
                             APP_NAME, FINDINGS_NAME)
    refused = [probe for probe in document["probes"]
               if probe["probe_name"] == PROBE_CHECK]
    assert [probe["reason"] for probe in refused] == [NO_MODEL]


def test_a_default_audit_never_loads_the_cloud_client(
        monkeypatch, tmp_path, no_network) -> None:
    """The runtime half: nothing on the audit path imports the client while running.

    Both modules are dropped from `sys.modules` first, because another test in
    the same process imports them. That makes this a check on *deferred*
    imports -- a module-scope one would already have happened and is
    `tests/compare/test_cloud_client_containment.py`'s job.
    """
    forget_the_comparison_modules(monkeypatch)
    audit(monkeypatch, tmp_path)
    assert [name for name in COMPARISON_MODULES if name in sys.modules] == []


def test_a_probed_audit_never_loads_the_cloud_client(
        monkeypatch, tmp_path, no_network) -> None:
    """The audit that does call a model still calls the local one, and defers no import."""
    forget_the_comparison_modules(monkeypatch)
    audit(monkeypatch, tmp_path, ("--semantic-probe",))
    assert [name for name in COMPARISON_MODULES if name in sys.modules] == []
