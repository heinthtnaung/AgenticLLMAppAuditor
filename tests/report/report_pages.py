"""Records the whole-page tests render, and a parser that gathers what the guards check.

Named `report_pages` and not `samples`: pytest puts each test directory on the
path and imports by basename. The `Page` parser reads the page once so the offline
guard is checked against the parsed tree, not a grep -- `fetched/vulnscout` in a
repository name is not a false alarm.
"""

import re
from html.parser import HTMLParser

from council_runs import INVENTED, OTHER_QUOTE, answering, council_ran
from organisation.approval import Approval, Decision
from organisation.risk import assess, per_source
from report.model_identity import MEMBER_ROLE, ModelDigest, OllamaVersion
from report.provenance import LocalModels, RunProvenance
from report.record import Report, build_report
from report_samples import (
    CONFIDENTIALITY_ONLY, LOW_CONFIDENTIALITY, PROVENANCE, TOTAL_LOSS, VERSION_2_VECTOR,
    advisory, catalogue, component, finding, secret, unidentified,
)
from scoring.library import APPROVED_QUESTIONS
from scoring.question import Answer

DJANGO = component()
PYYAML = component("pyyaml", "5.1")
FLASK = component("flask", "1.0")

DISSENTING = {"gemma4:latest": {"AC": answering("H", OTHER_QUOTE), "AV": answering("A", INVENTED)}}
APPROVAL = Approval("hein", Decision.APPROVED, "2026-09-22T09:00:00Z", "shipped")

# The seven tabs the redesign lays the record out on, in the order the bar shows them.
TABS = ("overview", "disagree", "agree", "risk", "council", "secrets", "inventory")

# An external address in an attribute: a full URL, or a protocol-relative one.
EXTERNAL = re.compile(r"(https?:)?//", re.IGNORECASE)


def all_answers(overrides=None) -> dict:
    """Answer every approved question No, except the ones a test names."""
    return {**{asked.question_id: Answer.NO for asked in APPROVED_QUESTIONS}, **(overrides or {})}


ANSWERS = all_answers({"EXP-1": Answer.YES, "BUS-1": Answer.YES, "THR-1": Answer.UNKNOWN})


def full_report() -> Report:
    """One record carrying every kind of thing the page has a shape for."""
    disagreeing = finding(DJANGO, vectors={"ghsa": LOW_CONFIDENTIALITY, "redhat": TOTAL_LOSS})
    agreeing = finding(PYYAML, advisory_id="CVE-2020-14343",
                       vectors={"ghsa": CONFIDENTIALITY_ONLY, "nvd": CONFIDENTIALITY_ONLY})
    refused = finding(FLASK, advisory_id="CVE-2023-30861", vectors={"nvd": VERSION_2_VECTOR})
    raised = (disagreeing, agreeing, refused)
    council = (council_ran("CVE-2020-14343"), council_ran("CVE-2019-14234", **DISSENTING))
    return build_report(
        PROVENANCE,
        catalogue(DJANGO, PYYAML, FLASK, unidentified=(unidentified(),)),
        raised,
        {"pkg:pypi/absent@1.0": (advisory(purl="pkg:pypi/absent@1.0"),)},
        council,
        [assess(one, ANSWERS, per_source(one)) for one in raised],
        APPROVAL,
        ("CVE-9999-0001",),
        secrets=(secret(),),
    )


def full_report_with_link() -> Report:
    """A record whose one finding carries an advisory url, the only address allowed."""
    one = finding(DJANGO, url="https://avd.aquasec.com/nvd/cve-2019-14234")
    return build_report(PROVENANCE, catalogue(DJANGO), (one,), {})


def report_with_models() -> Report:
    """One record whose provenance says which weights the server held, for the digest line."""
    asked = LocalModels(
        server="http://127.0.0.1:11434", context_tokens=8192, timeout_seconds=180.0,
        temperature=0, seed=11, think=False, order_check=True, escalation_model=None,
        ollama_version=OllamaVersion("0.34.3"),
        models=(ModelDigest("qwen2.5:7b", MEMBER_ROLE, "845dbda0ea48ed749caafd"),),
    )
    provenance = RunProvenance("fetched/vulnscout", "syft-x", "trivy-x", PROVENANCE.database, asked)
    return build_report(provenance, catalogue(DJANGO), (finding(DJANGO),), {})


class Page(HTMLParser):
    """Parse the page once, gathering everything a fetch-nothing and no-JS guard checks."""

    def __init__(self) -> None:
        """Start with nothing collected."""
        super().__init__()
        self.in_script = self.in_style = False
        self.script = self.style = self.html_class = ""
        self.scripts = self.links = self.uses = self.xlink = 0
        self.with_src: list = []
        self.external: list = []
        self.styled_url: list = []
        self.hidden: list = []
        self.panels: list = []
        self.tabs: list = []
        self.ids: set = set()
        self.filter_hosts: set = set()
        self.toggle_hosts: set = set()

    def handle_starttag(self, tag: str, attrs: list) -> None:
        """Record scripts, styles, links, addresses, panels, tabs and hidden elements."""
        seen = dict(attrs)
        self.in_script = self.in_script or tag == "script"
        self.in_style = self.in_style or tag == "style"
        self.scripts += tag == "script"
        self.links += tag == "link"
        self.uses += tag == "use"
        self._addresses(tag, seen)
        self._structure(tag, seen)

    def _addresses(self, tag: str, seen: dict) -> None:
        """Note every attribute that could reach off the page: src, external URL, url() or xlink."""
        if "src" in seen:
            self.with_src.append((tag, seen["src"]))
        if "xlink:href" in seen:
            self.xlink += 1
        if "url(" in (seen.get("style") or ""):
            self.styled_url.append((tag, seen["style"]))
        for name, value in seen.items():
            if value and EXTERNAL.search(value):
                self.external.append((tag, name, value))

    def _structure(self, tag: str, seen: dict) -> None:
        """Note the html class, panels, tabs, ids, hidden elements and filter hosts."""
        if tag == "html":
            self.html_class = seen.get("class", "") or ""
        if "hidden" in seen:
            self.hidden.append(seen.get("class"))
        if tag == "section" and "panel" in (seen.get("class") or ""):
            self.panels.append(seen.get("id"))
        if seen.get("role") == "tab":
            self.tabs.append((seen.get("data-tab"), seen.get("aria-controls")))
        if "id" in seen:
            self.ids.add(seen["id"])
        if "data-filter-for" in seen:
            self.filter_hosts.add(seen["data-filter-for"])
        if "data-toggle-all" in seen:
            self.toggle_hosts.add(seen["data-toggle-all"])

    def handle_endtag(self, tag: str) -> None:
        """Close the script or style once its content is gathered."""
        self.in_script = self.in_script and tag != "script"
        self.in_style = self.in_style and tag != "style"

    def handle_data(self, data: str) -> None:
        """Gather the inline script and style so their contents can be checked."""
        self.script += data if self.in_script else ""
        self.style += data if self.in_style else ""

    @property
    def offsite(self) -> list:
        """Give every external address that is not an advisory link a reader may follow."""
        return [one for one in self.external if not (one[0] == "a" and one[1] == "href")]


def parsed(page: str) -> Page:
    """Parse one page for the guards."""
    reader = Page()
    reader.feed(page)
    return reader
