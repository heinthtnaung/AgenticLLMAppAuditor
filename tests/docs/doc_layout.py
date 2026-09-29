"""The repository-layout tree on a page, and whether each path it names is really the repository's.

`docs/DEVELOPMENT.md` draws the tree once; the check reads the paths off it
rather than keeping its own copy. A path is the repository's when it exists on
disk and git does not ignore it. That pair holds in both environments the suite
must pass in: a git checkout, where the local-only files (`CLAUDE.md`,
`.claude/`, `docs/sources/`) are present but ignored, and a `git archive`
export, where they are absent and there is no `.git` to consult.

`git check-ignore` answers the ignore question, so the `.gitignore` rules --
anchoring, directory markers, and the `!` negations that restore an excluded
path -- are applied by git rather than reimplemented here. An export holds only
what the archive gave, so a path it has is the repository's without asking git.
"""

import re
import subprocess
from pathlib import Path

from doc_markers import FENCE
from doc_pages import Page

INDENT_UNIT = 4  # each nesting level is four columns of the drawn tree
CONNECTORS = ("├── ", "└── ")
LAYOUT_HEADING = re.compile(r"^## Repository layout\s*$", re.MULTILINE)
GIT_DIRECTORY = ".git"
CHECK_IGNORE = ("git", "check-ignore", "--quiet", "--")
IGNORED, NOT_IGNORED = 0, 1


def layout_tree(page: Page) -> str:
    """Give the fenced tree under the 'Repository layout' heading, raising if it is gone."""
    heading = LAYOUT_HEADING.search(page.text)
    if heading is None:
        raise ValueError(
            f"{page.document.path} has no '## Repository layout' heading; the tree is gone"
        )
    fence = next((one for one in FENCE.finditer(page.text) if one.start() > heading.end()), None)
    if fence is None:
        raise ValueError(
            f"{page.document.path} has no fence under 'Repository layout'; the tree is gone"
        )
    return fence.group("body")


def layout_paths(tree: str) -> list[str]:
    """Give every repository path the layout tree names, root-relative and POSIX."""
    ancestors: list[tuple[int, str]] = []
    paths: list[str] = []
    for line in tree.splitlines():
        entry = _entry(line)
        if entry is None:
            continue
        depth, name, is_directory = entry
        ancestors = [held for held in ancestors if held[0] < depth]
        prefix = "/".join(part for _, part in ancestors)
        paths.append(f"{prefix}/{name}" if prefix else name)
        if is_directory:
            ancestors.append((depth, name))
    return paths


def _entry(line: str) -> tuple[int, str, bool] | None:
    """Read one tree line into its depth, name and directory flag, or None when it names nothing."""
    for connector in CONNECTORS:
        index = line.find(connector)
        if index != -1:
            token = line[index + len(connector):].split()[0]
            return index // INDENT_UNIT, token.rstrip("/"), token.endswith("/")
    return None


def is_local_only(root: Path, relative: str) -> bool:
    """Say whether a listed path is absent, as in an export, or git-ignored, as in a checkout."""
    if not (root / relative).exists():
        return True
    # An export holds only what the archive gave, so a path it has is the repository's.
    if not (root / GIT_DIRECTORY).exists():
        return False
    done = subprocess.run([*CHECK_IGNORE, relative], cwd=root, capture_output=True, text=True)
    if done.returncode not in (IGNORED, NOT_IGNORED):
        raise RuntimeError(
            f"git check-ignore {relative} exited {done.returncode}: {done.stderr.strip()}"
        )
    return done.returncode == IGNORED
