"""Where the chat steps write, checked before anything is written, so a refusal leaves nothing.

A step that wrote its first output and then found it could not write its second
would leave half a result behind, and a re-run would then refuse the half as a
file already there. So every output is checked first: its own path, not there
yet, in a folder that is.
"""

from pathlib import Path


def refuse_unwritable(paths: tuple[Path, ...]) -> None:
    """Refuse outputs that share a path, are already there, or have no folder to go in."""
    if len({one.resolve() for one in paths}) != len(paths):
        raise ValueError(f"{', '.join(map(str, paths))} name one path twice; each needs its own")
    taken = [str(one) for one in paths if one.exists()]
    if taken:
        raise FileExistsError(f"{', '.join(taken)} already exists, and nothing is written over")
    unplaced = [str(one) for one in paths if not one.parent.is_dir()]
    if unplaced:
        raise FileNotFoundError(f"no folder exists to hold {', '.join(unplaced)}")


def refuse_inside(folder: Path, path: Path) -> None:
    """Refuse a file that would land inside a folder kept for what is safe to paste."""
    if folder.resolve() not in path.resolve().parents:
        return
    raise ValueError(
        f"{path} would be written inside {folder}, which holds only what is safe to paste; "
        "the manifest names every advisory, so it goes elsewhere"
    )
