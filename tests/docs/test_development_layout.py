"""Every path the layout tree names is really the repository's, never a local-only file.

`docs/DEVELOPMENT.md` draws the repository layout. A path it lists must be part
of the repository a clone gets, never one of the files kept on the development
machine (`CLAUDE.md`, `.claude/`, `docs/sources/`), which are git-ignored and so
are absent from a `git archive` export and present-but-ignored in a checkout.
`is_local_only` refuses both: it flags a path that is absent from disk or that
git ignores. Listed-but-real is the whole of this check; real-but-unlisted is
out of scope.
"""

from doc_layout import is_local_only, layout_paths, layout_tree
from doc_pages import DEVELOPMENT, PROJECT_ROOT, read


def test_every_path_in_the_layout_tree_is_a_real_repository_path():
    paths = layout_paths(layout_tree(read(DEVELOPMENT)))
    assert paths, "the 'Repository layout' tree named no paths, so this check tested nothing"
    offenders = [path for path in paths if is_local_only(PROJECT_ROOT, path)]
    assert not offenders, _named(offenders)


def _named(offenders: list[str]) -> str:
    """Name each layout path that a clone does not have, for the failure message."""
    listed = ", ".join(offenders)
    return (
        f"the layout tree names {listed}, which a clone does not have: each is either absent "
        "from disk or git-ignored, so it is a local-only file, not part of the repository"
    )
