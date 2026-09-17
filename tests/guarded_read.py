"""The two sentences every guarded read of a hand-editable file refuses with.

Four modules now read a file a person is expected to edit -- a grading key, a
drafted key, either manifest -- and each one turns three failures into a
refusal a reader can act on: the file would not parse, the file parsed into
something that is not an object, or the file could not be opened at all.

The *texts* that break a file are local to each tree, because they quote that
file's own content: `fetch_helpers.py` half-saves a pin, `corrupt_fixtures.py`
half-saves a drafted key. The *sentences* are not local, and this is the fourth
place one of them would have been spelled as a literal. Spelled once here
instead, because a wording change is exactly what made eleven tests fail at
once, and a copy that drifts is a test asserting a message nothing sends.

**"Cannot be read as json" is deliberate and it is not a typo for "is not
readable json".** The same `except` clause now catches `OSError`, and a file
with no read permission *is* readable json -- nobody could open it. One
sentence has to be true of both.

`refusal_from` is here for the same reason: every one of these guards was
defeated by raising the *wrong class* rather than by raising nothing, so the
tests have to catch broadly and assert the class. `pytest.raises(ValueError)`
reports the escaping `AttributeError` or `PermissionError` as an error in the
test rather than as the wrong answer it is.
"""

from typing import Callable

# Everything that stopped the file becoming a document: a syntax error, or an
# open that failed.
UNPARSEABLE = "cannot be read as json"

# It opened and parsed, and what came back cannot be subscripted the way every
# caller subscripts it.
WRONG_SHAPE = "not a json object"


def refusal_from(call: Callable[[], object], what: str = "the guarded read") -> Exception:
    """Whatever one call raised, returned as an object so its *class* can be asserted.

    Deliberately broad: the class is the subject. `what` names the call in the
    message a silent success earns, so a test that stops refusing says which.
    """
    try:
        call()
    except Exception as raised:  # noqa: BLE001 - the class raised is the subject
        return raised
    raise AssertionError(f"{what} returned without complaint")
