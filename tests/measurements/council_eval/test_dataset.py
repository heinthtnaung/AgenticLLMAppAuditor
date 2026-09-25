"""Guards on the frozen dataset: what goes in comes back as the finding the audit would build."""

import pytest

import eval_samples as samples
from council_eval import dataset
from council_eval.dataset import Item, published_dates, read_dataset, write_dataset

BUILT_FROM = {"repository": "fetched/example"}


def test_a_frozen_item_reads_back_as_the_same_finding(tmp_path):
    path = tmp_path / "dataset.json"
    write_dataset((samples.item(),), BUILT_FROM, path)
    (read,) = read_dataset(path)
    assert read == samples.item()


def test_the_rebuilt_finding_carries_the_scores_the_join_computes(tmp_path):
    path = tmp_path / "dataset.json"
    write_dataset((samples.item(),), BUILT_FROM, path)
    (read,) = read_dataset(path)
    assert {score.source: score.base_score for score in read.finding.scores} == {
        "ghsa": 7.5, "nvd": 5.3, "redhat": 7.5,
    }


def test_a_frozen_dataset_is_never_rewritten(tmp_path):
    path = tmp_path / "dataset.json"
    write_dataset((samples.item(),), BUILT_FROM, path)
    with pytest.raises(FileExistsError, match="is not rewritten"):
        write_dataset((samples.item(),), BUILT_FROM, path)


def test_a_dataset_naming_one_advisory_twice_is_refused(tmp_path):
    path = tmp_path / "dataset.json"
    write_dataset((samples.item(), samples.item()), BUILT_FROM, path)
    with pytest.raises(ValueError, match="more than once"):
        read_dataset(path)


def test_the_publication_date_is_read_from_the_scan_the_product_does_not_keep():
    record = {"VulnerabilityID": "CVE-1", "PublishedDate": "2026"}
    raw = {"Results": [{"Vulnerabilities": [record]}]}
    assert published_dates(raw) == {"CVE-1": "2026"}


def test_a_finding_the_scan_did_not_date_is_refused():
    with pytest.raises(ValueError, match="carries no PublishedDate"):
        dataset.published_of({}, samples.finding())


def test_the_items_are_the_audit_s_findings_in_the_order_it_asks_them(monkeypatch, tmp_path):
    first, second = samples.finding("CVE-2026-0002"), samples.finding("CVE-2026-0001")
    raw = {"Results": [{"Vulnerabilities": [
        {"VulnerabilityID": "CVE-2026-0001", "PublishedDate": "2026-01"},
        {"VulnerabilityID": "CVE-2026-0002", "PublishedDate": "2026-02"},
    ]}]}
    monkeypatch.setattr(dataset, "run_json_scanner", lambda command: raw)
    monkeypatch.setattr(dataset.syft_runner, "scan_directory", lambda directory: FakeCatalogue())
    monkeypatch.setattr(dataset, "read_advisories", lambda document: {})
    monkeypatch.setattr(dataset, "build_findings", lambda components, advisories: (first, second))
    items = dataset.vulnscout_items(tmp_path, tmp_path)
    assert [(one.key, one.published) for one in items] == [
        ("CVE-2026-0002", "2026-02"), ("CVE-2026-0001", "2026-01"),
    ]


def test_an_item_is_named_by_its_advisory():
    assert Item("V", samples.PUBLISHED, samples.finding("CVE-2026-0009")).key == "CVE-2026-0009"


class FakeCatalogue:
    """What Syft gives back, reduced to the one field the dataset reads."""

    components = ()
