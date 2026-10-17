"""Every exercise's offline stub answers like the version of its exercise.

The stubs of Exercises 1-3 (`pizza_api_stub.py`, standard library only) are the
fallback for a session without network; a stub that drifted from its version
would make a team's results depend on whether the Wi-Fi worked. Each stub is
started as a real process, on a free port, and asked the same questions as the
service.
"""

from __future__ import annotations

import json
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

import pytest

from conftest import COURSES, REPO, base, validate

STUBS = [(course, n) for course in COURSES for n in (1, 2, 3)]

CITIES = [
    "Athens", "athina", "Αθήνα", "ATHENS", "Piraeus", "Pireas", "Agia Paraskevi", "Αγία Παρασκευή",
    "Saint-Étienne", "saint etienne", "Saint-Priest-en-Jarez", "Lyon", "Leipzig", "Halle", "Dresden",
    "Barcelona", "Ath.", "Ag. Paraskevi", "St. Etienne",
]


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def _call(url: str, body: dict | None = None):
    data = json.dumps(body).encode() if body is not None else None
    request = urllib.request.Request(url, data=data, method="POST" if body is not None else "GET",
                                     headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            return response.status, dict(response.headers), response.read().decode("utf-8")
    except urllib.error.HTTPError as error:
        return error.code, dict(error.headers), error.read().decode("utf-8")


@pytest.fixture(scope="module", params=STUBS, ids=[f"{c}-exercise-0{n}" for c, n in STUBS])
def stub(request):
    course, n = request.param
    port = _free_port()
    folder = REPO / course / f"exercise-0{n}"
    process = subprocess.Popen([sys.executable, "pizza_api_stub.py", "--port", str(port)], cwd=folder,
                               stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
                               env={"PATH": "/usr/bin:/bin", "NO_COLOR": "1", "PYTHONUTF8": "1"})
    url = f"http://127.0.0.1:{port}"
    for _ in range(100):
        try:
            _call(f"{url}/pizza")
            break
        except OSError:
            if process.poll() is not None:
                pytest.fail(f"the stub of {course}/exercise-0{n} did not start: "
                            f"{process.stderr.read().decode()[-800:]}")
            time.sleep(0.1)
    yield {"url": url, "key": f"v{n}", "n": n, "course": course}
    process.terminate()
    process.wait(timeout=10)


def test_the_menu_is_the_menu_of_the_version(client, stub):
    status, headers, body = _call(f"{stub['url']}/pizza")
    assert status == 200
    assert json.loads(body) == client.get(f"{base(stub['key'])}/pizza").json()
    assert not any(h.lower().startswith("x-availability") for h in headers), "v1-v3 never sell out"


@pytest.mark.parametrize("city", CITIES)
def test_the_stub_accepts_and_refuses_what_the_version_does(client, stub, city):
    status, _, body = _call(f"{stub['url']}/address/validate",
                            {"city": city, "street": "Ermou", "house_number": "5"})
    service = validate(client, stub["key"], city)
    assert status == service.status_code, (city, body)
    if status == 400 and stub["n"] in (1, 2, 3):
        # The same refusal, word for word: the Exercise 2 stub loads the full
        # delivery area of v2 from its own copy of data/cities.tsv.gz.
        assert json.loads(body)["detail"] == service.json()["detail"]


def test_every_pizza_can_be_ordered_and_read_back(client, stub):
    menu = client.get(f"{base(stub['key'])}/pizza").json()
    for pizza in menu:
        status, _, body = _call(f"{stub['url']}/order", {"pizza_id": pizza["id"], "city": "Athens",
                                                        "street": "Ermou", "house_number": "5"})
        assert status == 200 and json.loads(body)["status"] == "received", (pizza, body)
    order_id = json.loads(body)["order_id"]
    status, _, stored = _call(f"{stub['url']}/order/{order_id}")
    assert status == 200 and json.loads(stored)["address"]["city"] == "Athens"
    assert _call(f"{stub['url']}/order/does-not-exist")[0] == 404


def test_the_order_checks_answer_like_the_version(client, stub):
    unknown = len(client.get(f"{base(stub['key'])}/pizza").json()) + 1
    assert _call(f"{stub['url']}/order", {"pizza_id": unknown, "city": "Athens", "street": "Ermou",
                                          "house_number": "5"})[0] == 404
    assert _call(f"{stub['url']}/order", {"pizza_id": 1, "city": "Barcelona", "street": "Carrer de Mallorca",
                                          "house_number": "401"})[0] == 400


@pytest.mark.parametrize("query", ["saint-eti", "athina", "Αθήνα", "patra", "lyon", "agia", "", "barcelona"])
def test_the_city_search_of_exercise_3_answers_like_v3(client, stub, query):
    if stub["n"] != 3:
        status, _, _ = _call(f"{stub['url']}/city")
        assert status == 404, "GET /city arrives with Exercise 3"
        return
    params = urllib.parse.urlencode({"q": query, "limit": 7} if query else {"limit": 7})
    status, headers, body = _call(f"{stub['url']}/city?{params}")
    service = client.get(f"{base('v3')}/city?{params}")
    assert status == 200
    assert json.loads(body) == service.json()
    assert headers.get("X-Total-Count") == service.headers["x-total-count"]


def test_the_stub_documents_itself(stub):
    status, headers, body = _call(f"{stub['url']}/")
    assert status == 200 and headers.get("Content-Type", "").startswith("text/html")
    assert f"https://wse-research.org/pizza-api/v{stub['n']}" in body
