"""Each baseline's achievable ceiling, computed in the plan before either was written.

Baseline A can reach five of the vulnerable fixture's six graded entries, and
Baseline B can reach none of them. Both ceilings were written down in
`PHASE_4_PLAN.md` before the code existed, so these tests are the check on the
prediction rather than a record of the outcome -- and the *reasons* are asserted
too, because a ceiling reported as a bare number reads as a system that tried
and failed.
"""

import json

from baseline_fixtures import stub_syft
from baselines.rules import RULES
from baselines.sbom_only import scan_repo as sbom_scan
from conftest import app_path, ground_truth, require_corpus
from dependency_fixtures import CORPUS_GENERATOR_OUTPUT, SUPPORT_AGENT
from evaluation.grading import LINE_TOLERANCE, line_window, matches_key
from evaluation.scorer import score_app
from run_baseline import STATIC_RULES, build_documents

# Baseline A's ceiling: the five entries whose surface a regex can name.
REACHABLE_KEY_IDS = ["VULN1-01", "VULN1-02", "VULN1-03", "VULN1-04", "VULN1-05"]

# The one it cannot reach, and how the scorer attributes the miss.
OUT_OF_REACH_KEY_ID = "VULN1-06"
OUT_OF_REACH_REASON = "no_check_for_risk_class"
SUPPLY_CHAIN = "LLM03"

# Where the key anchors that entry, and where a crude undeclared-import rule
# would have fired instead: the import statement at the top of the same file.
USE_SITE_FILE = "utils.py"
USE_SITE_LINE = 75
IMPORT_LINE = 3
IMPORT_STATEMENT = "import yaml"


def score_static_rules() -> dict:
    """Score Baseline A over the vulnerable fixture, through the unmodified harness."""
    require_corpus(SUPPORT_AGENT)
    findings, surfaces = build_documents(STATIC_RULES, str(app_path(SUPPORT_AGENT)))
    return score_app(SUPPORT_AGENT, ground_truth(SUPPORT_AGENT),
                     json.loads(findings), json.loads(surfaces))


def key_entry(key_id: str) -> dict:
    """Return one entry of the vulnerable fixture's grading key."""
    return next(e for e in ground_truth(SUPPORT_AGENT)["findings"] if e["id"] == key_id)


def test_baseline_a_reaches_exactly_the_five_entries_predicted_for_it() -> None:
    """Named ids, not a count: reaching five *different* entries is not the prediction."""
    assert score_static_rules()["matched_key_ids"] == REACHABLE_KEY_IDS


def test_baseline_a_misses_the_supply_chain_entry_it_was_predicted_to_miss() -> None:
    """Five of six. The sixth is the one the plan said no regex could anchor."""
    scored = score_static_rules()
    assert (scored["true_positives"], scored["key_finding_count"]) == (5, 6)
    assert [miss["key_id"] for miss in scored["misses"]] == [OUT_OF_REACH_KEY_ID]


def test_the_miss_is_attributed_to_having_no_rule_for_that_class() -> None:
    """Its rule list covers four classes and LLM03 is not one, so the reason is derived."""
    require_corpus(SUPPORT_AGENT)
    miss = score_static_rules()["misses"][0]
    assert miss["reason"] == OUT_OF_REACH_REASON
    assert SUPPLY_CHAIN not in {rule.owasp_id for rule in RULES}


def test_the_key_anchors_that_entry_at_the_use_site_not_the_import() -> None:
    """`utils.py:75` is `yaml.load(...)`, which is what makes the entry line-anchored."""
    require_corpus(SUPPORT_AGENT)
    entry = key_entry(OUT_OF_REACH_KEY_ID)
    lines = (app_path(SUPPORT_AGENT) / USE_SITE_FILE).read_text(encoding="utf-8").splitlines()
    assert (entry["file"], entry["line"]) == (USE_SITE_FILE, USE_SITE_LINE)
    assert "yaml.load" in lines[USE_SITE_LINE - 1]


def test_an_undeclared_import_rule_would_fire_outside_the_window_the_key_allows() -> None:
    """The reason the ceiling is five: `import yaml` sits at line 3, and the window is [75, 78].

    A crude "imported but never declared" rule names the risk correctly and
    still scores zero, because naming a risk is not anchoring it where the key
    does. Only the mapping join gets from the import to the use site.
    """
    require_corpus(SUPPORT_AGENT)
    lines = (app_path(SUPPORT_AGENT) / USE_SITE_FILE).read_text(encoding="utf-8").splitlines()
    assert lines[IMPORT_LINE - 1].strip() == IMPORT_STATEMENT
    first, last = line_window(key_entry(OUT_OF_REACH_KEY_ID))
    assert (first, last) == (USE_SITE_LINE, USE_SITE_LINE + LINE_TOLERANCE)
    assert not first <= IMPORT_LINE <= last


def component_findings(monkeypatch) -> list[dict]:
    """Baseline B's findings for the vulnerable fixture, as the scorer would read them."""
    stub_syft(monkeypatch, CORPUS_GENERATOR_OUTPUT)
    return [{"file": f.file, "line": f.line, "owasp_id": f.owasp_id,
             "surface_kind": f.surface_kind, "surface_name": f.surface_name}
            for f in sbom_scan(str(app_path(SUPPORT_AGENT)))]


def test_baseline_b_matches_no_key_entry_at_all(monkeypatch) -> None:
    """Its ceiling is zero, and it is zero against every entry, not only the LLM03 one."""
    require_corpus(SUPPORT_AGENT)
    key = ground_truth(SUPPORT_AGENT)["findings"]
    produced = component_findings(monkeypatch)
    assert produced
    assert [(f, e) for f in produced for e in key if matches_key(f, e)] == []


def test_it_misses_the_one_supply_chain_entry_for_want_of_a_line(monkeypatch) -> None:
    """The join needs a file and a line; a component-level finding has neither to give."""
    require_corpus(SUPPORT_AGENT)
    entry = key_entry(OUT_OF_REACH_KEY_ID)
    produced = component_findings(monkeypatch)
    supply_chain = [f for f in produced if f["owasp_id"] == entry["owasp_id"]]
    assert supply_chain
    assert [f for f in supply_chain if matches_key(f, entry)] == []


def test_the_same_finding_would_match_once_it_carried_the_anchor(monkeypatch) -> None:
    """Mutation check: the class is right, so the missing file and line are the whole cause."""
    require_corpus(SUPPORT_AGENT)
    entry = key_entry(OUT_OF_REACH_KEY_ID)
    anchored = {**component_findings(monkeypatch)[0],
                "file": entry["file"], "line": entry["line"],
                "surface_kind": entry["llm_surface"], "surface_name": entry["surface_name"]}
    assert matches_key(anchored, entry)
