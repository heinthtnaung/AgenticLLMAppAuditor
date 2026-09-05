"""Express-style route registrations, the JS data-source detector's HTTP entry points.

Kept apart from test_detectors_js.py, which is already at its size budget. No
test may run an HTTP server, so every case here is an inline snippet and
this detector has no measured false-positive rate (docs/TODO.md).
"""

import textwrap

import pytest
from detector_helpers_js import FILE, only, other_detectors, run
from detectors.data_sources_js import find_data_sources
from detectors.detector_names import HTTP_METHODS, ROUTE_DECORATOR_ROOTS
from detectors.detector_names_js import ROUTE_METHODS, ROUTE_OBJECTS
from parsing.extractor_js import GRAMMARS
from parsing.languages import JAVASCRIPT, TYPESCRIPT, grammar_of
from artifacts.surface import DATA_SOURCE
from tree_sitter import Parser

# A .js file to check the language a surface records; the shared helper always
# parses as TypeScript, and the point of that test is that the file decides.
JS_FILE = "app/server.js"

GET_ROUTE = """
app.get('/users/:id', (req, res) => res.send(1));
"""

NAMED_HANDLER_ROUTE = """
router.post("/x", handler);
"""

MOUNTED_ROUTER = """
app.use('/api', apiRouter);
"""

CHAINED_ROUTE = """
app.route('/legacy').get(h);
"""

EXPRESS_ALL_ROUTE = """
app.all('/x', handler);
"""

CONFIG_GETTER = """
const port = app.get('port');
"""

JSON_MIDDLEWARE = """
app.use(express.json());
"""

NON_LITERAL_PATH = """
app.get(routePath, handler);
"""

UNRELATED_RECEIVER = """
thing.get("/x", handler);
"""

PATH_WITHOUT_SLASH = """
app.get('users', handler);
"""

PATH_WITH_NO_HANDLER = """
app.use('/api');
"""

TEMPLATE_PATH_ROUTE = """
app.get(`/tpl/${id}`, handler);
"""

REQUEST_READS_IN_HANDLER = """
app.post('/chat', (req, res) => {
  const question = req.body.question;
  res.send(req.query.mode + question);
});
"""

ROUTE_BELOW_IMPORTS = """
import express from "express";

const app = express();

app.get('/health', handler);
"""


def run_in_file(source: str, file: str) -> list:
    """Find data sources in a snippet parsed as the grammar its own extension registers."""
    text = textwrap.dedent(source).lstrip("\n").encode("utf-8")
    root = Parser(GRAMMARS[grammar_of(file)]).parse(text).root_node
    return find_data_sources(root, file, text)


@pytest.mark.parametrize(
    "source, name, detail",
    [
        (GET_ROUTE, "app.get", "http get route input"),
        (NAMED_HANDLER_ROUTE, "router.post", "http post route input"),
        (MOUNTED_ROUTER, "app.use", "http use route input"),
        (CHAINED_ROUTE, "app.route", "http route input"),
        (EXPRESS_ALL_ROUTE, "app.all", "http all route input"),
    ],
)
def test_route_registration_is_a_data_source(source: str, name: str, detail: str) -> None:
    """Each route registration is one DATA_SOURCE, named after the call, describing the verb."""
    surface = only(run(find_data_sources, source))
    assert (surface.kind, surface.name, surface.detail) == (DATA_SOURCE, name, detail)


def test_finds_express_get_route_as_data_source() -> None:
    """A GET route with an inline arrow handler is where request data enters the app."""
    surface = only(run(find_data_sources, GET_ROUTE))
    assert (surface.kind, surface.name, surface.line) == (DATA_SOURCE, "app.get", 1)


def test_finds_route_registered_with_a_named_handler() -> None:
    """The handler may be a bare identifier, so the match cannot require a callback argument."""
    surface = only(run(find_data_sources, NAMED_HANDLER_ROUTE))
    assert (surface.kind, surface.name) == (DATA_SOURCE, "router.post")


def test_express_config_getter_is_not_a_route() -> None:
    """`app.get('port')` reads config: 'port' is no path, so it is not an HTTP entry point."""
    assert run(find_data_sources, CONFIG_GETTER) == []


def test_path_with_no_handler_is_not_a_route() -> None:
    """A path on its own registers nothing, so a registration needs two arguments."""
    assert run(find_data_sources, PATH_WITH_NO_HANDLER) == []


def test_chained_route_fires_on_its_path_alone() -> None:
    """`app.route('/x')` takes only the path -- the handler chains onto its return value."""
    assert only(run(find_data_sources, CHAINED_ROUTE)).detail == "http route input"


@pytest.mark.parametrize(
    "source",
    [CONFIG_GETTER, JSON_MIDDLEWARE, NON_LITERAL_PATH, UNRELATED_RECEIVER,
     PATH_WITHOUT_SLASH],
)
def test_non_route_call_reports_nothing(source: str) -> None:
    """Config reads, path-less middleware, non-literal paths and other objects stay quiet."""
    assert run(find_data_sources, source) == []


def test_route_path_may_be_a_template_literal() -> None:
    """A path written as a template literal is still a literal path, so the route is found."""
    assert only(run(find_data_sources, TEMPLATE_PATH_ROUTE)).name == "app.get"


def test_empty_file_reports_no_route() -> None:
    """A file with no code has no entry points, and that is not an error."""
    assert run(find_data_sources, "\n") == []


def test_route_line_number_is_where_it_is_registered() -> None:
    """The line points at the registration call, not the file or the enclosing block."""
    assert only(run(find_data_sources, ROUTE_BELOW_IMPORTS)).line == 5


@pytest.mark.parametrize("file, language", [(FILE, TYPESCRIPT), (JS_FILE, JAVASCRIPT)])
def test_route_records_the_language_of_its_file(file: str, language: str) -> None:
    """The language comes from the file being read, via surface_from_node."""
    assert only(run_in_file(GET_ROUTE, file)).language == language


def test_request_reads_inside_the_handler_are_not_surfaces() -> None:
    """Phase 1 records the source site only; following req.body into a prompt is Phase 3."""
    surfaces = run(find_data_sources, REQUEST_READS_IN_HANDLER)
    assert [(s.name, s.detail) for s in surfaces] == [("app.post", "http post route input")]


def test_other_detectors_ignore_a_route() -> None:
    """A route is a data source and nothing else, so the four kinds never overlap."""
    for other in other_detectors(find_data_sources):
        assert run(other, GET_ROUTE) == [], f"{other.__name__} also fired on a route"


def test_route_objects_are_the_python_sides_table() -> None:
    """Both backends read the same receiver table, so they cannot drift on what a router is."""
    assert ROUTE_OBJECTS is ROUTE_DECORATOR_ROOTS


def test_route_methods_cover_every_shared_http_verb_plus_express_own() -> None:
    """Express adds `all` and `use` to the verbs the Python side already recognises."""
    assert ROUTE_METHODS == HTTP_METHODS | {"all", "use"}
