"""Command line entry point: extract one repository's LLM surfaces to JSON."""

import argparse
import sys
from pathlib import Path

from extractor import extract_repo
from repo_loader import list_oversized_files
from surface import surfaces_to_json

DEFAULT_ARTIFACTS_DIR = Path("artifacts")
OUTPUT_NAME = "surfaces.json"


def build_parser() -> argparse.ArgumentParser:
    """Describe the command line arguments."""
    parser = argparse.ArgumentParser(description="Extract the LLM surfaces of a Python repository.")
    parser.add_argument("repo_path", help="path to the repository to analyse")
    parser.add_argument(
        "--artifacts-dir",
        type=Path,
        default=DEFAULT_ARTIFACTS_DIR,
        help=f"where to write <app>/{OUTPUT_NAME} (default: {DEFAULT_ARTIFACTS_DIR})",
    )
    return parser


def report_skipped_files(repo_path: str) -> None:
    """Tell the user about files left out for size, so nothing is missed silently."""
    for path in list_oversized_files(repo_path):
        print(f"warning: skipped oversized file {path}", file=sys.stderr)


def main() -> int:
    """Extract surfaces and write the artifact. Returns the process exit code."""
    args = build_parser().parse_args()
    report_skipped_files(args.repo_path)

    surfaces = extract_repo(args.repo_path)
    if not surfaces:
        print(f"warning: no LLM surfaces found in {args.repo_path}", file=sys.stderr)

    app_name = Path(args.repo_path).resolve().name
    output_path = args.artifacts_dir / app_name / OUTPUT_NAME
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(surfaces_to_json(surfaces), encoding="utf-8")
    print(f"wrote {len(surfaces)} surfaces to {output_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
