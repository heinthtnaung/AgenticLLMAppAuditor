"""The drafted key is fetched by the app's *name*, and the loaded draft is a different thing.

One variable held both: the app a draft was wanted for, and the draft once it
had arrived. So saving put the loaded document back into the value the fetch was
keyed on, the effect ran again, and the page asked the server for
`/api/keys/[object Object]` -- `encodeURIComponent` of an object, which is what
JavaScript's string coercion produces and what the address bar showed. The
server refused it, so nothing broke visibly; the editor simply lost the draft it
had just saved.

Two states now: `app`, which is a string off the run record and the only thing
the effect depends on, and `draft`, which is what arrived and what the editor is
handed. This file holds the pair apart.

**Text, and the file says so rather than implying otherwise.** A React effect's
dependency list cannot be run without React, so what is checked is the list as
written: that the effect keyed on the app depends on the app and on nothing
else, and that the setter for the draft is not in it. What that cannot show is
whether React re-runs the effect when it should, or what the component does with
what arrives.

**The server's own refusal is not this file's subject.** `key_routes._path`
checks the name against `APP_NAME` and answers 404 for anything else, and
`test_key_routes.py` holds that -- which is what kept this defect from being
worse than a lost draft. A page that cannot send a bad name and a server that
refuses one are two guards, and this is the first.

Read with comments stripped, so prose explaining the defect is not read as code.
No fastapi and no node.
"""

import re

from .jsx_sweep import FRONTEND_SRC, strip_comments

RUN_PAGE = FRONTEND_SRC / "pages" / "RunPage.jsx"

# The hook that fetches a draft, and the three things about it that matter: what
# it is given, what it calls, and what it re-runs on.
HOOK = re.compile(r"function useDraft\((\w+)\)\s*\{(.*?)\n\}", re.DOTALL)
FETCH_CALL = re.compile(r"fetchDraft\((\w+)\)")
DEPENDENCIES = re.compile(r"\}, \[([^\]]*)\]\);")

# The state the editor is handed, which must not be what the fetch is keyed on.
DRAFT_STATE = "draft"
DRAFT_SETTER = "setDraft"

# What the page really passes as the key: a field of the run record, not a
# document. Written as the JSX writes it, optional chaining and all.
KEYED_ON = "runId"


def hook_source() -> tuple[str, str]:
    """The draft hook's parameter and body, insisting the page still has one."""
    found = HOOK.search(strip_comments(RUN_PAGE.read_text(encoding="utf-8")))
    assert found, f"{RUN_PAGE.name} no longer declares a useDraft hook this test can read"
    return found.group(1), found.group(2)


def dependencies() -> list[str]:
    """The names the draft hook's effect re-runs on, as written."""
    _parameter, body = hook_source()
    found = DEPENDENCIES.search(body)
    assert found, "the draft hook's effect has no dependency list this test can read"
    return [name.strip() for name in found.group(1).split(",") if name.strip()]


# --- the fetch is keyed on a name ---------------------------------------------

def test_the_hook_fetches_by_the_name_it_was_given() -> None:
    """The defect in one line: it fetched by whatever that variable held at the time."""
    parameter, body = hook_source()
    assert FETCH_CALL.findall(body) == [parameter]


def test_the_effect_re_runs_on_that_name_and_on_nothing_else() -> None:
    """A dependency list holding the draft is what made saving re-fetch by a document."""
    parameter, _body = hook_source()
    assert dependencies() == [parameter]


def test_neither_the_draft_nor_its_setter_is_a_dependency() -> None:
    """Said by name, because both are in scope right there and either would reopen it."""
    listed = dependencies()
    assert DRAFT_STATE not in listed
    assert DRAFT_SETTER not in listed


def test_the_page_keys_the_hook_on_a_field_of_the_run_record() -> None:
    """Non-vacuity: a hook keyed correctly on the wrong value is still keyed on the wrong value."""
    assert f"useDraft({KEYED_ON})" in strip_comments(RUN_PAGE.read_text(encoding="utf-8"))


# --- and what arrives is held separately --------------------------------------

def test_the_loaded_draft_is_its_own_state() -> None:
    """Two states, which is the whole fix: one is asked for, the other is what came back."""
    _parameter, body = hook_source()
    assert "useState" in body
    assert f"[{DRAFT_STATE}, {DRAFT_SETTER}]" in body


def test_saving_writes_back_to_the_draft_and_not_to_the_key() -> None:
    """The editor hands back what the server wrote; that must not become the next fetch."""
    page = strip_comments(RUN_PAGE.read_text(encoding="utf-8"))
    assert f"onSaved={{{DRAFT_SETTER}}}" in page
