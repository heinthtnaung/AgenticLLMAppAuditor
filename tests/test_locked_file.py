"""The helper that locks a file must skip, not pass, where the lock does not take.

`locked` is the one piece of test setup in this suite that can silently stop
testing anything: `chmod 000` does not deny the owner when the owner is root,
and some filesystems ignore the mode entirely. On such a machine every test that
asks for an unopenable file would get a perfectly readable one -- and every
assertion about refusing it would pass, having exercised the ordinary path.

So the skip is a guard like any other, and it is held here.
"""

from pathlib import Path

import pytest

from locked_file import locked

SOME_JSON = "{}\n"


def a_file(tmp_path: Path) -> Path:
    """One small readable file, which is what every caller of `locked` starts from."""
    path = tmp_path / "pin.json"
    path.write_text(SOME_JSON, encoding="utf-8")
    return path


def test_a_file_that_can_still_be_read_skips_the_test(tmp_path, monkeypatch) -> None:
    """A `chmod` that does nothing is what running as root looks like from here."""
    monkeypatch.setattr(Path, "chmod", lambda self, mode: None)
    with pytest.raises(pytest.skip.Exception):
        locked(a_file(tmp_path))


def test_a_file_the_mode_really_denies_comes_back_to_be_used(tmp_path) -> None:
    """The ordinary machine, so the test above is not satisfied by skipping always.

    On a machine that does not enforce the mode this skips through `locked`
    itself, which is the behaviour the first test holds -- there is no third
    outcome to describe.
    """
    path = a_file(tmp_path)
    assert locked(path) == path
