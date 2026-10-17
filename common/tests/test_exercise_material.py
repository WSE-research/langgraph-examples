"""Every exercise names its version, and what its material assumes is what that version serves.

These tests read the course folders (course5 = the Athens edition, and course6)
next to `common/`. They catch the two ways an
exercise breaks without anybody touching it: the material points at a version
it was not written for, or the service and the material disagree about a pizza
or a city the material relies on.
"""

from __future__ import annotations

import ast
import filecmp
import gzip
import re
from pathlib import Path

import pytest

import main
from conftest import COMMON, COURSES, REPO, base, validate

URL = re.compile(r"https://wse-research\.org/pizza-api(/v(\d+))?")
EXERCISES = [(course, n) for course in COURSES for n in range(1, 7)]
# Written as a city on purpose and refused on purpose: the standing example outside
# the area, the abbreviations of the Exercise 3 benchmark noise, a test sentinel.
REFUSAL_CITIES = {"Barcelona", "St. Etienne", "St Etienne", "St-Étienne", "Ath.", "Ag. Paraskevi", "MARKER"}


def folder(course: str, n: int) -> Path:
    return REPO / course / f"exercise-0{n}"


def text_files(root: Path):
    for path in sorted(root.rglob("*")):
        if path.is_file() and (path.suffix in {".py", ".md", ".txt", ".ttl", ".json", ".jsonl", ".sh"}
                               or path.name == ".env.example") and "__pycache__" not in path.parts:
            yield path


def literal(path: Path, name: str):
    """The value of a module-level assignment `name = <literal>` in a Python file."""
    for node in ast.parse(path.read_text(encoding="utf-8")).body:
        if isinstance(node, ast.Assign) and any(getattr(t, "id", None) == name for t in node.targets):
            return ast.literal_eval(node.value)
    raise AssertionError(f"{path} has no {name} = ...")


def menu_of(client, key):
    return [{"id": p["id"], "name": p["name"]} for p in client.get(f"{base(key)}/pizza").json()]


# ------------------------------------------------ every exercise names its version --

def test_both_editions_are_here():
    assert COURSES == ["course5", "course6"]


@pytest.mark.parametrize("course, n", EXERCISES)
def test_every_service_url_in_an_exercise_names_its_own_version(course, n):
    """No exercise may use the unversioned (newest) service, nor another exercise's version."""
    wrong = []
    for path in text_files(folder(course, n)):
        for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            for match in URL.finditer(line):
                if match.group(2) != str(n):
                    wrong.append(f"{path.relative_to(REPO)}:{line_no}: {match.group(0)}")
    assert not wrong, "\n".join(wrong)


@pytest.mark.parametrize("course", COURSES)
def test_exercise_1_names_its_version_in_the_client_and_in_env_example(course):
    """Exercise 1 is frozen: its client defaults to v1 and its .env.example pins v1."""
    expected = "https://wse-research.org/pizza-api/v1"
    client_source = (folder(course, 1) / "pizzabot" / "pizza_api.py").read_text(encoding="utf-8")
    assert f'os.environ.get("PIZZA_API_BASE", "{expected}")' in client_source
    env = (folder(course, 1) / ".env.example").read_text(encoding="utf-8")
    assert re.search(rf"^PIZZA_API_BASE={re.escape(expected)}$", env, re.M), env


def adapter_base(path: Path):
    """`_base()` of an adapter, run on its own: VERSION, DEFAULT, _UNIVERSITY and the
    function itself, taken out of the file -- the adapter imports `requests`, which
    this test environment does not need."""
    source = path.read_text(encoding="utf-8")
    keep = [node for node in ast.parse(source).body
            if (isinstance(node, ast.Assign) and any(getattr(t, "id", None) in {"VERSION", "DEFAULT", "_UNIVERSITY"}
                                                      for t in node.targets))
            or (isinstance(node, ast.FunctionDef) and node.name == "_base")]
    namespace = {"os": __import__("os"), "re": re}
    exec(compile(ast.Module(body=keep, type_ignores=[]), str(path), "exec"), namespace)
    return namespace["_base"]


@pytest.mark.parametrize("course, n", [(c, n) for c in COURSES for n in range(2, 7)])
def test_every_exercise_from_2_on_ships_an_adapter_that_names_its_version(course, n, monkeypatch):
    """The version is in the adapter, not in .env: every exercise 2-6 ships
    pizzabot/pizza_api.py with its own VERSION and DEFAULT, and the adapter ignores
    a PIZZA_API_BASE that names any other version of the service (a line left in
    .env from an earlier iteration) -- the local stub is the only override."""
    adapter = folder(course, n) / "pizzabot" / "pizza_api.py"
    assert literal(adapter, "VERSION") == f"v{n}"
    assert literal(adapter, "DEFAULT") == f"https://wse-research.org/pizza-api/v{n}"
    base = adapter_base(adapter)
    own = f"https://wse-research.org/pizza-api/v{n}"
    monkeypatch.delenv("PIZZA_API_BASE", raising=False)
    assert base() == (own, "")
    for stale in (f"https://wse-research.org/pizza-api/v{n - 1}", "https://wse-research.org/pizza-api",
                  f"https://wse-research.org/pizza-api/v{n + 1}/"):
        monkeypatch.setenv("PIZZA_API_BASE", stale)
        url, warning = base()
        assert url == own and "delete it from .env" in warning, stale
    for override in (own, "http://127.0.0.1:8000"):
        monkeypatch.setenv("PIZZA_API_BASE", override)
        assert base() == (override, "")


@pytest.mark.parametrize("course, n", [(c, n) for c in COURSES for n in (2, 3)])
def test_no_env_example_from_exercise_2_on_pins_a_version(course, n):
    """Only a commented line for the local stub; the version is the adapter's."""
    env = (folder(course, n) / ".env.example").read_text(encoding="utf-8")
    assert not re.search(r"^\s*PIZZA_API_BASE=", env, re.M), env
    assert re.search(r"^# PIZZA_API_BASE=http://127\.0\.0\.1:8000$", env, re.M)


@pytest.mark.parametrize("course, n", [(c, n) for c in COURSES for n in (4, 5)])
def test_the_additive_test_fixtures_insist_on_the_adapter_of_their_iteration(course, n):
    """From Iteration 4 on the material is copied into a team's repository. Its
    tests/conftest.py no longer sets a version; it stops the run when the adapter in
    the repository is older than this iteration's (a later one serves the same)."""
    conftest = (folder(course, n) / "tests" / "conftest.py").read_text(encoding="utf-8")
    assert not re.search(r"""environ(\.setdefault\(|\[)["']PIZZA_API_BASE""", conftest), "conftest.py must not set the version"
    assert 'getattr(pizza_api, "VERSION", "v0")' in conftest
    assert f"int(_VERSION[1:]) < {n}" in conftest, "an older adapter must stop the run"
    assert "pytest.exit(" in conftest


@pytest.mark.parametrize("course, n", [(c, n) for c in COURSES for n in range(2, 7)])
def test_the_sheets_tell_the_team_to_take_the_adapter(course, n):
    """Every sheet 2-6 says it once: take this iteration's adapter, delete any
    PIZZA_API_BASE left in .env -- and never asks for a version line in .env."""
    sheet = (folder(course, n) / "README.md").read_text(encoding="utf-8")
    assert "pizzabot/pizza_api.py" in sheet
    assert f"https://wse-research.org/pizza-api/v{n}" in sheet
    assert re.search(r"delete any `PIZZA_API_BASE` line", sheet), "the sheet must say to delete the old line"
    assert "PIZZA_API_BASE=https://" not in sheet, "no sheet may pin a version in .env"


@pytest.mark.parametrize("course", COURSES)
def test_exercise_6_names_the_rag_client_as_the_slides_do(course):
    """The RAG service is provided on-site like the LLM endpoint: the sheet uses the
    names of the slides -- the client module and its three settings, next to the
    three of the LLM endpoint."""
    sheet = (folder(course, 6) / "README.md").read_text(encoding="utf-8")
    assert "from rag_client import RagClient" in sheet and "RagClient.from_env()" in sheet
    for name in ("RAG_API_BASE", "RAG_API_KEY", "RAG_CHAT_MODEL", "OPENAI_API_BASE", "OPENAI_API_KEY", "MODEL_NAME"):
        assert name in sheet, name


@pytest.mark.parametrize("course", COURSES)
def test_the_course_readme_lists_every_version_with_its_exercise(course):
    readme = (REPO / course / "README.md").read_text(encoding="utf-8")
    for n in range(1, 7):
        assert re.search(rf"<https://wse-research\.org/pizza-api/v{n}> \| `exercise-0{n}/`", readme), n
    assert "pizzabot/pizza_api.py" in readme and "PIZZA_API_BASE=https://" not in readme


# ------------------------------------------------------------ menus agree --

@pytest.mark.parametrize("course, n", [(c, n) for c in COURSES for n in (1, 2, 3)])
def test_the_stub_serves_the_menu_of_its_version(client, course, n):
    assert literal(folder(course, n) / "pizza_api_stub.py", "MENU") == menu_of(client, f"v{n}")


@pytest.mark.parametrize("course", COURSES)
def test_the_menu_snapshot_of_exercise_3_is_version_3(client, course):
    known = literal(folder(course, 3) / "tests" / "test_dataset.py", "KNOWN_MENU")
    assert known == {p["id"]: p["name"] for p in menu_of(client, "v3")}


def _graph(path: Path):
    rdflib = pytest.importorskip("rdflib")
    graph = rdflib.Graph()
    graph.parse(path, format="turtle")
    return graph


@pytest.mark.parametrize("course", COURSES)
def test_every_pizza_of_the_exercise_3_catalog_is_on_the_v3_menu_with_its_id(client, course):
    graph = _graph(folder(course, 3) / "benchmark" / "data" / "catalog.ttl")
    menu = {p["id"]: p["name"] for p in menu_of(client, "v3")}
    rows = graph.query("""PREFIX : <http://example.org/pizza/>
        SELECT ?name ?id WHERE { ?p :pizzaId ?id ; :name ?name }""")
    pairs = {(str(name), int(pid)) for name, pid in rows}
    assert pairs, "no pizza in the catalog"
    assert all(menu.get(pid) == name for name, pid in pairs), pairs - {(n, i) for i, n in menu.items()}


@pytest.mark.parametrize("course, n", [(c, n) for c in COURSES for n in (4, 5)])
def test_the_menu_facts_join_on_the_ids_of_the_exercise_version(client, course, n):
    graph = _graph(folder(course, n) / "data" / "menu-facts.ttl")
    rows = graph.query("""PREFIX pz: <http://example.org/pizza/>
        SELECT ?name ?id WHERE { ?p a pz:Pizza ; pz:apiId ?id ; pz:name ?name }""")
    facts = {int(pid): str(name) for name, pid in rows}
    assert facts == {p["id"]: p["name"] for p in menu_of(client, f"v{n}")}


# ------------------------------------------------------------ cities agree --

@pytest.mark.parametrize("course", COURSES)
def test_every_city_flag_of_the_exercise_3_catalog_is_what_v3_answers(client, course):
    graph = _graph(folder(course, 3) / "benchmark" / "data" / "catalog.ttl")
    rows = graph.query("""PREFIX : <http://example.org/pizza/>
        SELECT ?name ?flag WHERE { ?c :deliverable ?flag ; :name ?name }""")
    flags = {str(name): flag.toPython() for name, flag in rows}
    assert flags and not all(flags.values()), "the catalog needs a city outside the area"
    wrong = {name: flag for name, flag in flags.items()
             if (validate(client, "v3", name).status_code == 200) != flag}
    assert not wrong, f"catalog says deliverable={wrong}, v3 disagrees"


@pytest.mark.parametrize("course, n", [(c, n) for c in COURSES for n in (2, 3)])
def test_the_stubs_of_exercises_2_and_3_ship_the_delivery_area_of_the_service(course, n):
    shipped = folder(course, n) / "data" / "cities.tsv.gz"
    assert filecmp.cmp(shipped, COMMON / "data" / "cities.tsv.gz", shallow=False)


@pytest.mark.parametrize("course, n", [(c, n) for c in COURSES for n in (1, 2)])
def test_the_small_stubs_know_the_nine_cities_and_their_spellings(client, course, n):
    stub = folder(course, n) / "pizza_api_stub.py"
    assert literal(stub, "VALID_CITIES") == main.COURSE_CITIES
    spellings = literal(stub, "OTHER_SPELLINGS")
    rows = {line.split("\t")[0]: line.rstrip("\n").split("\t")
            for line in gzip.open(COMMON / "data" / "cities.tsv.gz", "rt", encoding="utf-8")}
    for city, other in spellings.items():
        assert other == rows[city][3].split("|"), city
        for spelling in other:
            assert validate(client, f"v{n}", spelling).status_code == 200, spelling


CITY_IN_DATA = re.compile(r"""["']city["']\s*:\s*["']([^"'{}\\]+)["']""")


@pytest.mark.parametrize("course, n", EXERCISES)
def test_every_city_the_material_writes_as_data_is_in_the_area_of_its_version(client, course, n):
    """Every `"city": "..."` in the exercise's code, tests and data files -- an expected
    record, a request body, a benchmark case -- is delivered to by the exercise's version,
    unless it is the standing refusal example."""
    seen, wrong = set(), []
    for path in text_files(folder(course, n)):
        if path.suffix not in {".py", ".json", ".jsonl"}:
            continue
        for city in CITY_IN_DATA.findall(path.read_text(encoding="utf-8")):
            if city in seen or city in REFUSAL_CITIES:
                continue
            seen.add(city)
            if validate(client, f"v{n}", city).status_code != 200:
                wrong.append(f"{city!r} ({path.relative_to(REPO)})")
    assert not wrong, "not in the delivery area of v%d: %s" % (n, ", ".join(wrong))


@pytest.mark.parametrize("course", COURSES)
def test_the_refusal_example_is_used_and_refused(client, course):
    tests = (folder(course, 2) / "tests" / "test_both_configurations.py").read_text(encoding="utf-8")
    assert "Barcelona" in tests
    assert validate(client, "v2", "Barcelona").status_code == 400
