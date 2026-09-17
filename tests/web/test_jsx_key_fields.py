"""Every field the key editor reads off a drafted key is a field that key carries.

The sixth, seventh and eighth prefixes swept. `test_jsx_record_fields.py` states
why this kind of test exists at all: the page reads Python-authored documents
across a language boundary with no compiler and no type across it, JavaScript
answers `undefined` for a field that does not exist, and React renders
`undefined` as nothing. `FindingList.jsx` read `finding.evidence` for weeks and
`Finding` has never had such a field. The key editor is the same join over a
shape nothing else in the page touches, so it gets the same sweep.

**Three prefixes, three different producers.** `key` is the grading key
`keys/key_drafting.key_document` writes. `entry` is one of its `findings`, whose
fields are what `key_promotion` requires plus the four `docs/SCHEMAS.md` lists as
optional -- allowed as the union, because a check stricter than the schema is as
wrong as a looser one. `draft` is the envelope `GET /api/keys/{app}` answers
with, derived by asking the route rather than by transcribing it, plus the one
key `KeysPage` adds on its way to `KeyEditor`.

**`entry` is swept in the key editor alone, and that narrowing is deliberate.**
`TopBar.jsx` binds `entry` too -- a navigation entry, with `path`, `page`, `icon`
and `name` -- so a whole-tree sweep of that name would report four fields of a
different shape as missing from a grading key. The files whose `entry` is a key
entry are named below; the cost is that a component added later reading
`entry.x` off a key would go unswept until it is named here.

**The `EDITABLE` array is the part the sweep cannot see at all**, and it is the
part that matters most: the editor renders one input per name in it and writes
back `entry[field]`, which is the "field read through a variable" blind spot
`jsx_sweep.py` records. It is parsed out of the JSX as text and checked three
ways -- every name is a real entry field, none is frozen, none is an anchor --
because an editable field the API refuses would make every save a 400.

**The two lists an editable field is checked against come from
`key_edit_guard`**, which declares them, and not from `key_routes`, which
imports one of the two. The verify button's own reads are swept in
`test_jsx_key_verify.py`, because it binds the key document under another name.

No Node: the JSX is read as text, and the documents come from `src/` and from
the route itself.
"""

import re
from pathlib import Path

import pytest

pytest.importorskip("fastapi", reason="the web extra is not installed, so there is no endpoint")
pytest.importorskip("httpx", reason="fastapi's TestClient needs httpx to drive the endpoint")

import key_edit_guard                                         # noqa: E402
from keys.key_promotion import ANCHOR_FIELD, ENTRY_FIELDS     # noqa: E402

from .jsx_sweep import FRONTEND_SRC, accessors, accessors_in, unknown   # noqa: E402
from .key_fixtures import a_drafted_key, planted_client, read_draft     # noqa: E402

# The names the components bind. `key` is the whole document, `entry` one of its
# findings, `draft` the envelope the route answered with.
KEY = "key"
ENTRY = "entry"
DRAFT = "draft"

# Where an `entry` is a grading-key entry rather than a navigation entry.
KEY_ENTRY_FILES = ("KeyEditor.jsx",)

# What `KeysPage` adds to the route's reply before handing it on: the flag that
# says the second fetch has come back.
PAGE_ADDITIONS = frozenset({"loaded"})

# Optional and nullable entry fields, from `docs/SCHEMAS.md`. Required ones come
# from `key_promotion`; these have no constant to read, and leaving them out
# would make this check stricter than the schema it is checking against.
OPTIONAL_ENTRY_FIELDS = frozenset({"surface_name", "component", "detection", "line_end"})

# Where the editor declares which fields it offers, and how to read it: the
# array literal `const EDITABLE = [...]`, then one quoted name at a time.
EDITABLE_PATTERN = re.compile(r"const EDITABLE = \[(.*?)\];", re.DOTALL)
NAME_PATTERN = re.compile(r'"([A-Za-z_]\w*)"')

# What the editor offers today. Named as a whole set so that a field added to
# the page has to be added here, where the three checks below apply to it.
EXPECTED_EDITABLE = {"owasp_id", "title", "description"}

# Floors under each sweep: one that matched nothing would pass having read
# nothing. Measured today at six, four and four.
MINIMUM_KEY_ACCESSORS = 3
MINIMUM_ENTRY_ACCESSORS = 3
MINIMUM_DRAFT_ACCESSORS = 3

# A field no drafted key has ever carried, to show the check reports rather than
# tolerates one. `findings_count` is the plausible misspelling: the real field
# is `finding_count`, singular.
FIELD_THAT_DOES_NOT_EXIST = "findings_count"


def key_fields(tmp_path: Path) -> set[str]:
    """Every top-level field of the key a real `--draft-key` run writes."""
    return set(a_drafted_key(tmp_path))


def entry_fields() -> set[str]:
    """Every field an entry may carry: what promotion requires, plus the optional four."""
    return {*ENTRY_FIELDS, ANCHOR_FIELD, *OPTIONAL_ENTRY_FIELDS}


def draft_fields(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> set[str]:
    """Every field of the envelope the route answers with, plus what the page adds to it."""
    client, _drafts = planted_client(monkeypatch, tmp_path)
    return set(read_draft(client)) | PAGE_ADDITIONS


def entry_accessors() -> list[tuple[str, str]]:
    """Every `entry.field` read in the files whose entries are grading-key entries."""
    found: list[tuple[str, str]] = []
    for name in KEY_ENTRY_FILES:
        text = (FRONTEND_SRC / "components" / name).read_text(encoding="utf-8")
        found += [(name, field) for field in accessors_in(text, ENTRY)]
    return found


def editable_fields() -> set[str]:
    """The fields the editor renders an input for, read out of the JSX as text."""
    source = (FRONTEND_SRC / "components" / KEY_ENTRY_FILES[0]).read_text(encoding="utf-8")
    declared = EDITABLE_PATTERN.search(source)
    assert declared is not None, f"no `const EDITABLE = [...]` in {KEY_ENTRY_FILES[0]}"
    return set(NAME_PATTERN.findall(declared.group(1)))


# --- what the page reads exists -----------------------------------------------

def test_every_key_field_the_editor_reads_exists(tmp_path) -> None:
    """`key.source` and `key.verified` are rendered as the key's standing; a typo shows nothing."""
    assert unknown(KEY, key_fields(tmp_path), accessors(KEY)) == []


def test_every_entry_field_the_editor_reads_exists() -> None:
    """The editor labels each entry `id — file:line`, which is three joins to get wrong."""
    assert unknown(ENTRY, entry_fields(), entry_accessors()) == []


def test_every_envelope_field_the_editor_reads_exists(monkeypatch, tmp_path) -> None:
    """`draft.key`, `draft.refusals`, `draft.app`: the route's reply, not a shape in `src/`."""
    assert unknown(DRAFT, draft_fields(monkeypatch, tmp_path), accessors(DRAFT)) == []


# --- the sweep really swept ---------------------------------------------------

def test_the_sweep_read_the_accessors_the_editor_is_written_with() -> None:
    """Guard: three empty lists would satisfy every check above having read nothing."""
    assert len(accessors(KEY)) >= MINIMUM_KEY_ACCESSORS
    assert len(entry_accessors()) >= MINIMUM_ENTRY_ACCESSORS
    assert len(accessors(DRAFT)) >= MINIMUM_DRAFT_ACCESSORS


def test_an_accessor_no_key_answers_is_reported_and_named(tmp_path) -> None:
    """Guard on the check itself: a bad field is named with its file, not passed over."""
    planted = [("KeyEditor.jsx", FIELD_THAT_DOES_NOT_EXIST)]
    assert unknown(KEY, key_fields(tmp_path), planted) == [
        f"KeyEditor.jsx: {KEY}.{FIELD_THAT_DOES_NOT_EXIST}"]


def test_the_entry_sweep_is_narrowed_to_the_editor_on_purpose() -> None:
    """The narrowing said out loud: `entry` names a navigation row elsewhere in the page."""
    assert len(accessors(ENTRY)) > len(entry_accessors())


# --- the fields the editor offers, which no sweep can see ---------------------

def test_the_editor_offers_exactly_the_fields_it_declares() -> None:
    """Read from the JSX, so the three checks below apply to what the page really renders."""
    assert editable_fields() == EXPECTED_EDITABLE


def test_every_field_the_editor_offers_is_one_an_entry_carries() -> None:
    """Read and written through a variable, so the sweep cannot see these at all."""
    assert editable_fields() <= entry_fields()


def test_no_field_the_editor_offers_is_one_the_endpoint_freezes() -> None:
    """An input for a frozen field would make every save a 400 the page could not explain."""
    assert editable_fields() & set(key_edit_guard.FROZEN_FIELDS) == set()


def test_no_field_the_editor_offers_is_an_anchor() -> None:
    """The rule the page states in its own hint: a quotation from source is shown, not typed."""
    assert editable_fields() & set(key_edit_guard.ANCHORED_FIELDS) == set()
