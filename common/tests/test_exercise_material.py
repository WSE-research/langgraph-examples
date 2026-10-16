"""Every exercise names its version, and what its material assumes is what that version serves.

These tests read the course folders (course5 = the Saint-Etienne edition,
course6 = the Athens edition) next to `common/`. They catch the two ways an
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


@pytest.mark.parametrize("course, n", [(c, n) for c in COURSES for n in (1, 2, 3)])
def test_the_client_and_env_example_default_to_the_exercise_version(course, n):
    expected = f"https://wse-research.org/pizza-api/v{n}"
    client_source = (folder(course, n) / "pizzabot" / "pizza_api.py").read_text(encoding="utf-8")
    assert f'os.environ.get("PIZZA_API_BASE", "{expected}")' in client_source
    env = (folder(course, n) / ".env.example").read_text(encoding="utf-8")
    assert re.search(rf"^PIZZA_API_BASE={re.escape(expected)}$", env, re.M), env


@pytest.mark.parametrize("course, n", [(c, n) for c in COURSES for n in (4, 5)])
def test_the_additive_exercises_pin_their_version_in_the_test_fixtures(course, n):
    """From Iteration 4 on the material is copied into a team's repository, whose
    client and .env still name the version of Iteration 3 -- tests/conftest.py
    sets the exercise's own version before `pizzabot` is imported."""
    conftest = (folder(course, n) / "tests" / "conftest.py").read_text(encoding="utf-8")
    expected = f'os.environ.setdefault("PIZZA_API_BASE", "https://wse-research.org/pizza-api/v{n}")'
    assert expected in conftest
    assert conftest.index(expected) < conftest.index("import pytest"), "must run before any import"


@pytest.mark.parametrize("course, n", [(c, n) for c in COURSES for n in (4, 5, 6)])
def test_the_additive_sheets_tell_the_team_to_switch_the_version(course, n):
    sheet = (folder(course, n) / "README.md").read_text(encoding="utf-8")
    assert f"PIZZA_API_BASE=https://wse-research.org/pizza-api/v{n}" in sheet


@pytest.mark.parametrize("course", COURSES)
def test_the_course_readme_lists_every_version_with_its_exercise(course):
    readme = (REPO / course / "README.md").read_text(encoding="utf-8")
    for n in range(1, 7):
        assert re.search(rf"<https://wse-research\.org/pizza-api/v{n}> \| `exercise-0{n}/`", readme), n


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


@pytest.mark.parametrize("course", COURSES)
def test_exercise_3_ships_the_delivery_area_of_the_service(course):
    shipped = folder(course, 3) / "data" / "cities.tsv.gz"
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
