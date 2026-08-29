"""Baseline B: run Syft and report what the components alone can support.

What an off-the-shelf supply-chain tool gives you: the bill of materials, and
nothing about how the app uses it. It reports LLM03 and nothing else, because
that is genuinely all it can see -- every other risk class is **absent** from
`risk_classes_checked` rather than present and empty, so a reader can tell "no
check covers this" from "a check looked and found nothing".

**Its ceiling against these grading keys is zero, and that is the result rather
than a failure.** A component-level finding carries no file and no line, and the
one LLM03 key entry is anchored at `utils.py:75` on the `yaml.load` surface. The
join needs a line; this system has none to give. Naming a risky package is not
the same as pointing at the code that uses it, and only the surface-to-component
mapping gets from one to the other -- which is precisely what this baseline
does not have.

It calls Syft itself rather than reading the auditor's `sbom.json`: that file
carries `build_sbom`'s `declared` and `version_source` judgements, which are
this project's own work and off-limits here.
"""

from pathlib import Path

from artifacts.finding import STATIC, Finding
from deps import syft_runner
from deps.package_names import NPM, PYPI, base_purl

CHECK_NAME = "sbom_component_scan"
OWASP_ID = "LLM03"
TITLE = "Dependency is present in the bill of materials and unreviewed"

# Only what does not vary between runs. Syft's document carries a UUID, a
# timestamp and absolute scan paths; reading three fields touches none of them,
# so no stripping step is needed to stay byte-identical.
LIBRARY_TYPE = "library"


def _ecosystem_of(app_dir: Path) -> str:
    """Say which ecosystem this app declares, so a purl can be built for it."""
    return NPM if (app_dir / "package.json").is_file() else PYPI


def component_names(document: dict) -> list[str]:
    """Return each distinct library name Syft reported, sorted.

    One finding per *name*, never per (name, version): `Finding.id` anchors on
    `component_name` before `purl`, so two versions of one package would produce
    two identical ids and the document would refuse them as duplicates.
    """
    names = {
        component["name"]
        for component in document.get("components", [])
        if component.get("type") == LIBRARY_TYPE and component.get("name")
    }
    return sorted(names)


def _finding_for(name: str, ecosystem: str) -> Finding:
    """Report one component, with no file or line because this system has neither."""
    return Finding(
        owasp_id=OWASP_ID, rule_id=CHECK_NAME, title=TITLE, detection=STATIC,
        component_name=name,
        # Versionless: this baseline makes no claim about which version is
        # installed, and a purl carrying a guess would invite an advisory lookup
        # to answer about a package the app may not have.
        purl=base_purl(name, ecosystem),
    )


def scan_repo(repo_path: str) -> list[Finding]:
    """Report every library Syft finds, or nothing at all when there is no manifest."""
    app_dir = Path(repo_path)
    ecosystem = _ecosystem_of(app_dir)
    names = component_names(syft_runner.scan(app_dir))
    return [_finding_for(name, ecosystem) for name in names]
