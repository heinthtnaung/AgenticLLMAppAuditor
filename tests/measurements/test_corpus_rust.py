"""Guards on the corpus's Rust manifest: every crate it pins is one fetched from crates.io.

A `[[package]]` in a `Cargo.lock` with no `source` is a crate of the workspace
itself, not one from a registry, and Syft 1.52 gives such a crate no purl.
Written without one, all ten corpus crates came out unidentified and
`audit measurements/corpus/rust` refused the scan, while Trivy, which matches a
crate's name and version whatever its source, found the same 29 advisories
either way.
"""

import tomllib
from pathlib import Path

RUST_LOCK = Path(__file__).resolve().parents[2] / "measurements" / "corpus" / "rust" / "Cargo.lock"
CRATES_IO = "registry+https://github.com/rust-lang/crates.io-index"


def locked_packages() -> list[dict]:
    """Read every package the corpus's Rust lock file pins."""
    return tomllib.loads(RUST_LOCK.read_text(encoding="utf-8")).get("package", [])


def test_every_crate_the_rust_corpus_pins_is_sourced_from_crates_io():
    """A crate with no registry source gets no purl from Syft, so no advisory can join to it."""
    packages = locked_packages()
    assert packages, "the Rust corpus pins no crate at all"
    assert [one["name"] for one in packages if one.get("source") != CRATES_IO] == []
