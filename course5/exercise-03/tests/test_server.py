"""Serving the data inside the test environment.

The in-process catalog is the default; these tests prove that the same graph
is available over HTTP for anything that cannot import Python -- a second
process, a notebook, a SPARQL client, the frontend.
"""

import json
import urllib.error
import urllib.parse
import urllib.request

from rdflib import Graph

COUNT_PIZZAS = """
PREFIX pz: <http://example.org/pizza/>
SELECT (COUNT(?pizza) AS ?n) WHERE { ?pizza a pz:PIZZA }
"""


def get(url: str) -> tuple[int, str]:
    try:
        with urllib.request.urlopen(url, timeout=5) as response:
            return response.status, response.read().decode("utf-8")
    except urllib.error.HTTPError as error:
        return error.code, error.read().decode("utf-8")


def sparql(endpoint, query: str) -> dict:
    status, body = get(f"{endpoint.url}/sparql?" + urllib.parse.urlencode({"query": query}))
    assert status == 200, body
    return json.loads(body)


def test_health_reports_the_size_of_the_served_graph(endpoint, catalog):
    status, body = get(endpoint.url + "/health")
    assert status == 200
    assert json.loads(body) == {"status": "ok", "triples": len(catalog)}


def test_a_query_over_http_gives_the_same_answer_as_in_process(endpoint, catalog):
    served = sparql(endpoint, COUNT_PIZZAS)["results"]["bindings"][0]["n"]["value"]
    assert int(served) == len(catalog.instances("PIZZA"))


def test_the_whole_graph_can_be_fetched_and_parsed_back(endpoint, catalog):
    status, turtle = get(endpoint.url + "/graph")
    assert status == 200
    fetched = Graph().parse(data=turtle, format="turtle")
    assert len(fetched) == len(catalog)
    assert fetched.isomorphic(catalog.g)


def test_a_broken_query_is_a_client_error_not_a_crash(endpoint):
    status, body = get(f"{endpoint.url}/sparql?" + urllib.parse.urlencode({"query": "SELECT ?x WHERE"}))
    assert status == 400
    assert "error" in json.loads(body)
    assert get(endpoint.url + "/health")[0] == 200, "the server died on a bad query"


def test_an_unknown_route_is_a_404(endpoint):
    status, _ = get(endpoint.url + "/orders")
    assert status == 404


def test_a_post_query_works_too(endpoint, catalog):
    data = urllib.parse.urlencode({"query": COUNT_PIZZAS}).encode("utf-8")
    request = urllib.request.Request(endpoint.url + "/sparql", data=data)
    with urllib.request.urlopen(request, timeout=5) as response:
        payload = json.loads(response.read())
    assert int(payload["results"]["bindings"][0]["n"]["value"]) == len(catalog.instances("PIZZA"))
