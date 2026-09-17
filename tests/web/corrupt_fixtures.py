"""The two shapes a hand-edited file goes wrong in, and the three routes that meet them.

`key_draft_store` opens **two** hand-editable files, and both are hand-edited by
design: a person corrects `<app>.ground_truth.json`, and
`key_promotion.GRADED_PIN_FIELDS` says a person types the framework and language
into `<app>.manifest.json`. So a truncated one of either is ordinary input and
not a hostile case, and one guarded reader -- `_json_object` -- serves both.

Shared by `test_key_draft_corruption.py`, whose subject is a corrupt key, and
`test_key_manifest_corruption.py`, whose subject is a corrupt manifest and the
order a route does its work in. Spelled once here because the two files have to
agree about what "corrupt" means; if they drifted, the second could pass while
describing the first's fault.

**The routes are a table rather than three copies of a test.** All three go
through the same guarded read, and two of them go on to *write* -- which is the
distinction the manifest file turns on, so the writing pair is named separately.

Nothing here writes to the checkout's own `grading_keys/drafts/`: every path is
under whatever `tmp_path` folder `planted_client` was given.
"""

import json
from pathlib import Path

import httpx
from fastapi.testclient import TestClient

from guarded_read import UNPARSEABLE, WRONG_SHAPE
from keys.grading_keys import GROUND_TRUTH_SUFFIX, MANIFEST_SUFFIX

from .key_fixtures import APP, KEYS_ENDPOINT, OK
from .key_verify_fixtures import CHECKED_BY, claim

# What a text editor leaves behind when a save is interrupted: not json at all.
HALF_SAVED = '{"app": "demo-app", "findings": ['

# Readable json that is not an object. Three shapes, because the fault is "not
# an object" and not "is a list": a hand edit that deleted everything but the
# entries leaves the first, and a truncated file can leave either of the others.
NOT_AN_OBJECT = ("[]", '"demo-app"', "7")

# The two sentences a corrupt file is refused with, from the one module that
# spells them. Distinct from each other on purpose: the status is the same 400
# either way, so the sentence is the only thing telling a reader whether to hunt
# a syntax error or a document of the wrong shape. Re-exported here so the files
# in this folder keep importing one vocabulary.

# Every corrupt file, paired with the sentence it must be refused with. One
# table, so a test cannot assert a shape without saying which message it earns.
CORRUPT_SHAPES = [(HALF_SAVED, UNPARSEABLE)] + [(text, WRONG_SHAPE) for text in NOT_AN_OBJECT]

# A body the save route accepts, so a refusal that comes back is about the file
# on disk and never about the request.
AN_EDIT = {"key": {"findings": []}}


def _path(drafts: Path, suffix: str) -> Path:
    """One of the two files a drafted app has, under the folder a test was given."""
    return drafts / f"{APP}{suffix}"


def corrupt_key(drafts: Path, text: str) -> None:
    """Leave the drafted key holding something a hand edit could have left."""
    _path(drafts, GROUND_TRUTH_SUFFIX).write_text(text, encoding="utf-8")


def corrupt_pin(drafts: Path, text: str) -> None:
    """Leave the manifest holding something a hand edit could have left."""
    _path(drafts, MANIFEST_SUFFIX).write_text(text, encoding="utf-8")


def key_file(drafts: Path) -> Path:
    """The drafted key's own path, for a test that writes a state of its own.

    `corrupt_entry_field` covers the edit every caller makes; a test needing a
    different one should join the path here rather than spell the suffix again.
    """
    return _path(drafts, GROUND_TRUTH_SUFFIX)


def corrupt_entry_field(drafts: Path, field: str, shape: object) -> None:
    """Leave the key valid json with its first entry's `field` holding `shape`.

    The member-shape edits above break a whole file or a whole member; this one
    goes one level further in, to a field of one entry, which is where a hand
    edit that keeps the document readable usually lands.
    """
    path = _path(drafts, GROUND_TRUTH_SUFFIX)
    document = json.loads(path.read_text(encoding="utf-8"))
    document["findings"][0] = {**document["findings"][0], field: shape}
    path.write_text(json.dumps(document, indent=2, sort_keys=True), encoding="utf-8")


def answered(response: httpx.Response) -> dict:
    """One route's body, insisting it answered rather than crashed or refused."""
    assert response.status_code == OK, f"{response.status_code}: {response.text}"
    return response.json()


def stored_key(drafts: Path) -> str:
    """The key file as it stands, which a refusal must not have rewritten."""
    return _path(drafts, GROUND_TRUTH_SUFFIX).read_text(encoding="utf-8")


def draft_files(drafts: Path) -> dict[str, Path]:
    """Both hand-editable files of one draft, keyed by the name a refusal has to call them.

    The third way a hand edit breaks a file is that nobody can open it, and that
    is a state rather than a text -- so it needs the path, where `CORRUPT_SHAPES`
    needs only the bytes to write.
    """
    return {key_file_name(): _path(drafts, GROUND_TRUTH_SUFFIX),
            pin_file_name(): _path(drafts, MANIFEST_SUFFIX)}


def key_file_name() -> str:
    """What the key file is called, so a message can be checked for naming the right one."""
    return f"{APP}{GROUND_TRUTH_SUFFIX}"


def pin_file_name() -> str:
    """What the manifest is called, for the same reason."""
    return f"{APP}{MANIFEST_SUFFIX}"


def get_draft(client: TestClient) -> httpx.Response:
    """Read one draft, whatever the answer."""
    return client.get(f"{KEYS_ENDPOINT}/{APP}")


def put_draft(client: TestClient) -> httpx.Response:
    """Save a correction the route would otherwise accept, whatever the answer."""
    return client.put(f"{KEYS_ENDPOINT}/{APP}", json=AN_EDIT)


def verify_draft(client: TestClient) -> httpx.Response:
    """Record a check under a name the rules accept, whatever the answer."""
    return claim(client, CHECKED_BY)


# Every route that goes through the guarded read, by the method and path a
# reader would recognise. Parametrised over rather than copied three times.
ROUTES = {"GET": get_draft, "PUT": put_draft, "POST /verify": verify_draft}

# The two that go on to write. Named apart because "a refusal wrote nothing" is
# only a claim about these, and it is the claim the manifest file turns on.
WRITING_ROUTES = {name: call for name, call in ROUTES.items() if name != "GET"}
