"""Guard: a symlinked repository root is scanned as its real directory, not a false clean.

Syft follows a symlinked root and catalogues it; `trivy fs` does not descend one and
finds nothing. A run that handed the link to both would catalogue components and match
no advisory -- a "could not run" that reads exactly like "found nothing". So the root
is resolved once before the walk and either scanner, and all three read the same real
directory. The fakes here answer as the real tools did on the corpus, and each records
the path it was handed so the resolve is checked, not only its effect on Trivy.
"""

from pathlib import Path

from cli import audit as audit_module
from cli.arguments import TEXT_FORMAT, Options
from cli.audit import run_audit
from deps.syft_report import Catalogue
from deps.trivy_runner import TrivyScan
from cli_samples import ADVISORY, DATED, LODASH, scanners_answering


def options_for(path: Path) -> Options:
    """Build the options one run is about."""
    return Options(repository=path, report_format=TEXT_FORMAT, council_models=())


def recording_scanners(monkeypatch) -> dict:
    """Answer as the real tools do, recording the path the walk and each scanner receive."""
    scanners_answering(monkeypatch)
    seen: dict[str, Path] = {}
    found = Catalogue(components=(LODASH,), unidentified=())
    matched = TrivyScan(advisories={ADVISORY.purl: (ADVISORY,)}, secrets=())
    empty = TrivyScan(advisories={}, secrets=())

    def walk(path):
        """The manifest walk, recording the root it was handed."""
        seen["walk"] = Path(path)
        return ()

    def syft_scan(path):
        """Syft follows a symlinked root, so it catalogues whatever the link points to."""
        seen["syft"] = Path(path)
        return found

    def trivy_scan(path, cache):
        """`trivy fs` does not descend a symlinked root, so a linked one comes back empty."""
        seen["trivy"] = Path(path)
        return empty if Path(path).is_symlink() else matched

    monkeypatch.setattr(audit_module.manifests, "unread_manifests", walk)
    monkeypatch.setattr(audit_module.syft_runner, "scan_directory", syft_scan)
    monkeypatch.setattr(audit_module.trivy_runner, "scan_directory", trivy_scan)
    return seen


def linked_repository(tmp_path: Path) -> Path:
    """Give a symlink pointing at a real directory, as an operator's linked root would be."""
    real = tmp_path / "repo"
    real.mkdir()
    link = tmp_path / "link"
    link.symlink_to(real, target_is_directory=True)
    return link


def test_a_symlinked_root_is_scanned_as_its_real_directory_not_a_false_clean(tmp_path, monkeypatch):
    recording_scanners(monkeypatch)
    report = run_audit(options_for(linked_repository(tmp_path)), DATED)
    # On the bug Trivy saw the link, matched nothing, and this was 0: a false clean.
    assert len(report.findings) == 1
    assert report.findings[0].advisory.advisory_id == ADVISORY.advisory_id


def test_the_walk_and_both_scanners_read_the_same_resolved_root(tmp_path, monkeypatch):
    seen = recording_scanners(monkeypatch)
    link = linked_repository(tmp_path)
    run_audit(options_for(link), DATED)
    # The link is resolved once, so nothing downstream can be handed the link instead.
    assert seen["walk"] == seen["syft"] == seen["trivy"] == link.resolve()
    assert seen["trivy"] != link
    assert not seen["trivy"].is_symlink()


def test_the_report_still_names_the_symlinked_root_as_the_operator_gave_it(tmp_path, monkeypatch):
    recording_scanners(monkeypatch)
    link = linked_repository(tmp_path)
    # Resolved for the scan, named as given: the record must not silently rewrite the path.
    assert run_audit(options_for(link), DATED).provenance.repository == str(link)


def test_a_real_directory_root_is_scanned_the_same_way(tmp_path, monkeypatch):
    seen = recording_scanners(monkeypatch)
    real = tmp_path / "repo"
    real.mkdir()
    report = run_audit(options_for(real), DATED)
    assert len(report.findings) == 1
    assert seen["walk"] == seen["syft"] == seen["trivy"] == real.resolve()
    assert report.provenance.repository == str(real)
