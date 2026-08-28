"""Re-emits the generator's own CycloneDX document, made reproducible.

Separate from `sbom.py` because the two answer different questions. `sbom.py`
builds this project's contract, which records how far each version can be
trusted; this module hands the same scan to other supply-chain tooling in the
standard format, and CycloneDX has nowhere to put that judgement.
"""

from artifacts.sbom import LIBRARY

# Fields a generator fills in that differ between two runs of the same scan, or
# that it guessed. All are optional in CycloneDX, so dropping them leaves a
# valid document that is byte-identical every time.
VARYING_DOCUMENT_FIELDS = ("serialNumber", "metadata")
VARYING_COMPONENT_FIELDS = ("bom-ref", "cpe")
GENERATOR_PROPERTY_PREFIX = "syft:"


def _stable_component(component: dict) -> dict:
    """Return one CycloneDX component without the parts that vary or were guessed."""
    kept = {k: v for k, v in component.items() if k not in VARYING_COMPONENT_FIELDS}
    properties = [
        p for p in kept.get("properties", [])
        if not p.get("name", "").startswith(GENERATOR_PROPERTY_PREFIX)
    ]
    kept.pop("properties", None)
    if properties:
        kept["properties"] = properties
    return kept


def to_cyclonedx(generator_output: dict) -> dict:
    """Return the generator's CycloneDX document, made reproducible.

    Kept alongside sbom.json so the result can be fed to other supply-chain
    tooling and checked independently. sbom.json stays the contract the later
    phases read, because CycloneDX has no field for how much a version can be
    trusted -- a version guessed from `~=0.3.25` looks exactly like an exact
    pin -- and it omits the dependencies the generator did not find.

    Only optional fields are dropped, so this is still valid CycloneDX. Only
    library components are kept: the generator also emits one for the manifest
    file it read, named by its absolute path, which would make the document
    describe the machine that produced it. Which manifest was read is recorded
    in sbom.json's `scanned_manifests`, relative to the repository.
    """
    document = {k: v for k, v in generator_output.items() if k not in VARYING_DOCUMENT_FIELDS}
    document["components"] = sorted(
        (_stable_component(c) for c in generator_output.get("components", [])
         if c.get("type") == LIBRARY),
        key=lambda c: (c.get("type", ""), c.get("name", ""), c.get("version") or ""),
    )
    return document
