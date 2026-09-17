"""Every field the model panel and the model chooser read is a field `/api/model` answers.

The ninth and tenth prefixes swept, and they arrived with the option to choose
which pulled model a run audits with: `OptionsMenu.jsx` lists the models the
server holds and posts the chosen name, and `ModelStatus.jsx` renders the whole
status. Both read the reply of `GET /api/model` across the boundary
`test_jsx_record_fields.py` exists for -- no compiler, no type, and `undefined`
rendered as nothing at all.

**The two shapes are not one.** `status` is the reply; `model` is one entry of
its `models` array, which `web/model_routes._named` reduces to three keys --
`name`, `digest` and `bytes`. That reduction is the trap worth a test: the
listing Ollama sends calls the third one `size`, so a component reading
`model.size` would render an empty column against a field the route deliberately
renamed.

**The allowed names come from the route, not from a transcript.** The status is
read by driving the endpoint with the transport replaced by
`tests/model_server_stub.py`, so the keys asserted against are the ones a
running server would really answer with. Nothing here opens a socket, and no
Ollama is needed.

What this cannot see is what `jsx_sweep.py` records: a field read through a
variable or after destructuring, and one read in a `.js` module. `model` is a
name a future component could bind to something else entirely, exactly as
`entry` already is in `TopBar.jsx`; the floors below would not catch that, and
the check would report the other shape's fields as unknown.
"""

import pytest

pytest.importorskip("fastapi", reason="the web extra is not installed, so there is no endpoint")
pytest.importorskip("httpx", reason="fastapi's TestClient needs httpx to drive the endpoint")

from fastapi import FastAPI                                   # noqa: E402
from fastapi.testclient import TestClient                     # noqa: E402

import model_client                                           # noqa: E402
import model_routes                                           # noqa: E402
from model_server_stub import a_model, listing, serve         # noqa: E402

from .jsx_sweep import accessors, unknown                     # noqa: E402

MODEL_ENDPOINT = "/api/model"

# The names the components bind: the whole reply, and one listed model.
STATUS = "status"
LISTED_MODEL = "model"

# A second model the machine holds, so the listing the fields are read off is
# never a listing of one.
OTHER_MODEL = "llama3:latest"

# Floors under each sweep: one that matched nothing would pass having read
# nothing. Measured today at thirteen and four.
MINIMUM_STATUS_ACCESSORS = 8
MINIMUM_MODEL_ACCESSORS = 3

# What Ollama calls the field the route renames, and what the route calls it.
# A component reading the first would render nothing at all.
OLLAMA_SIZE_FIELD = "size"
SERVED_SIZE_FIELD = "bytes"

# A field the reply has never carried, to show the check reports rather than
# tolerates one.
FIELD_THAT_DOES_NOT_EXIST = "model_pulled"


def served_status(monkeypatch) -> dict:
    """The status reply a reachable server really produces, with the transport replaced."""
    serve(monkeypatch, listing(a_model(model_client.MODEL), a_model(OTHER_MODEL)))
    app = FastAPI()
    model_routes.register(app)
    response = TestClient(app).get(MODEL_ENDPOINT)
    assert response.status_code == 200, response.text
    return response.json()


def status_fields(monkeypatch) -> set[str]:
    """Every key the status reply carries."""
    return set(served_status(monkeypatch))


def listed_model_fields(monkeypatch) -> set[str]:
    """Every key one listed model carries, as the route reduces it."""
    listed = served_status(monkeypatch)["models"]
    assert len(listed) == 2, f"expected the two models served, got {len(listed)}"
    return set(listed[0])


# --- what the page reads exists -----------------------------------------------

def test_every_status_field_the_page_reads_exists(monkeypatch) -> None:
    """`status.reachable` and the two `_pulled` nulls decide what the panel says at all."""
    assert unknown(STATUS, status_fields(monkeypatch), accessors(STATUS)) == []


def test_every_listed_model_field_the_chooser_reads_exists(monkeypatch) -> None:
    """The chooser posts `model.name`, so a wrong name here posts an empty model."""
    assert unknown(LISTED_MODEL, listed_model_fields(monkeypatch),
                   accessors(LISTED_MODEL)) == []


def test_the_size_of_a_model_is_served_under_the_name_the_route_gives_it(
        monkeypatch) -> None:
    """The rename, pinned: Ollama says `size` and the reply says `bytes`."""
    fields = listed_model_fields(monkeypatch)
    assert SERVED_SIZE_FIELD in fields
    assert OLLAMA_SIZE_FIELD not in fields


# --- the sweep really swept ---------------------------------------------------

def test_the_sweep_read_the_accessors_the_components_are_written_with() -> None:
    """Guard: two empty lists would satisfy both checks above having read nothing."""
    assert len(accessors(STATUS)) >= MINIMUM_STATUS_ACCESSORS
    assert len(accessors(LISTED_MODEL)) >= MINIMUM_MODEL_ACCESSORS


def test_an_accessor_the_reply_does_not_answer_is_reported_and_named(monkeypatch) -> None:
    """Guard on the check itself: a bad field is named with its file, not passed over."""
    planted = [("OptionsMenu.jsx", FIELD_THAT_DOES_NOT_EXIST)]
    assert unknown(STATUS, status_fields(monkeypatch), planted) == [
        f"OptionsMenu.jsx: {STATUS}.{FIELD_THAT_DOES_NOT_EXIST}"]
